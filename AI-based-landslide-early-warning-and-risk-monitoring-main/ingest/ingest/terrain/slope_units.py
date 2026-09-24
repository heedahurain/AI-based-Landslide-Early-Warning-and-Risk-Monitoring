"""Slope-unit delineation and zonal terrain statistics.

The hillslope raster gives every cell an integer identifying the hillslope it
belongs to. Two things happen here. The raster is polygonised into slope-unit
geometry, and every derivative raster is aggregated to one value per unit.

Aggregation is done with `np.bincount` over the zone identifiers rather than by
masking each polygon in turn. One pass over each raster handles every unit at
once, which is the difference between seconds and hours at regional scale, and
it is the same vectorised discipline the sub-90-second inference budget in
Phase 3 will need.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio import features
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

log = logging.getLogger(__name__)

# Units below this are slivers from the polygonisation of a raster boundary,
# not real hillslopes. At 30 m, 20,000 square metres is about 22 cells.
MIN_UNIT_AREA_M2 = 20_000.0

# Circular quantities cannot be averaged arithmetically: north-facing cells at
# 1 degree and 359 degrees must average to 0, not 180.
CIRCULAR_LAYERS = {"aspect"}

# WhiteboxTools writes -1 into the aspect raster where it considers a cell to
# have no defined aspect. Measured on 2026-09-09: a perfectly planar synthetic
# surface descending due north or due south returns -1 across the whole
# interior, while the same surface descending east correctly returns 90. The
# value is a flag, not an azimuth, so it must be excluded rather than averaged.
# Feeding -1 into the circular mean would drag every affected unit's aspect
# toward due north and quietly corrupt the orographic and radiation terms that
# depend on it.
ASPECT_UNDEFINED_BELOW = 0.0


@dataclass
class SlopeUnitTable:
    """Slope units with their geometry and aggregated terrain attributes."""

    unit_ids: np.ndarray
    geometries: list[BaseGeometry]
    areas_m2: np.ndarray
    attributes: dict[str, np.ndarray]
    crs: str

    def __len__(self) -> int:
        return len(self.unit_ids)


def polygonise_hillslopes(
    hillslope_raster: Path, min_area_m2: float = MIN_UNIT_AREA_M2
) -> tuple[np.ndarray, list[BaseGeometry], np.ndarray, str]:
    """Turn the hillslope raster into one polygon per hillslope."""
    with rasterio.open(hillslope_raster) as src:
        zones = src.read(1)
        transform = src.transform
        crs = str(src.crs)
        nodata = src.nodata
        pixel_area = abs(transform.a * transform.e)

    valid = np.ones(zones.shape, dtype=bool)
    if nodata is not None:
        valid &= ~np.isclose(zones, nodata)
    # WhiteboxTools labels background as 0.
    valid &= zones > 0

    zones_int = np.where(valid, zones, 0).astype("int32")

    # Collect polygon parts per zone, then dissolve. A hillslope is contiguous
    # by construction, but polygonisation can still emit multiple rings where a
    # stream cell splits a cell run.
    parts: dict[int, list[BaseGeometry]] = {}
    for geom, value in features.shapes(zones_int, mask=valid, transform=transform):
        zone = int(value)
        if zone <= 0:
            continue
        parts.setdefault(zone, []).append(shape(geom))

    unit_ids: list[int] = []
    geometries: list[BaseGeometry] = []
    areas: list[float] = []

    for zone, polygons in parts.items():
        merged = polygons[0] if len(polygons) == 1 else max(polygons, key=lambda g: g.area)
        area = float(merged.area)
        if area < min_area_m2:
            continue
        unit_ids.append(zone)
        geometries.append(merged)
        areas.append(area)

    log.info(
        "slope_units.polygonised",
        extra={
            "zones_found": len(parts),
            "kept": len(unit_ids),
            "dropped_below_min_area": len(parts) - len(unit_ids),
            "pixel_area_m2": pixel_area,
        },
    )

    order = np.argsort(unit_ids)
    return (
        np.asarray(unit_ids, dtype="int64")[order],
        [geometries[i] for i in order],
        np.asarray(areas, dtype="float64")[order],
        crs,
    )


def _zonal_mean(
    values: np.ndarray, zones: np.ndarray, valid: np.ndarray, n_zones: int
) -> tuple[np.ndarray, np.ndarray]:
    """Sum and count per zone in a single pass."""
    flat_zones = zones[valid]
    flat_values = values[valid]
    counts = np.bincount(flat_zones, minlength=n_zones).astype("float64")
    sums = np.bincount(flat_zones, weights=flat_values, minlength=n_zones)
    return sums, counts


def aggregate_to_units(
    hillslope_raster: Path,
    rasters: dict[str, Path],
    unit_ids: np.ndarray,
) -> dict[str, np.ndarray]:
    """Aggregate each raster to one value per slope unit.

    Returns mean values, plus max and standard deviation for slope, which the
    factor-of-safety layer needs in order to distinguish a uniformly moderate
    hillside from one containing a steep scarp.
    """
    with rasterio.open(hillslope_raster) as src:
        zones_raw = src.read(1)
        zone_nodata = src.nodata

    zone_valid = zones_raw > 0
    if zone_nodata is not None:
        zone_valid &= ~np.isclose(zones_raw, zone_nodata)

    # Map hillslope identifiers onto a dense 0..n-1 index so bincount stays
    # small even when the identifiers are sparse.
    #
    # WhiteboxTools writes the hillslope raster as float even though the values
    # are integer labels, and a float array cannot index another array. The
    # cast is explicit here rather than incidental.
    max_id = int(zones_raw.max())
    lookup = np.full(max_id + 1, -1, dtype="int64")
    lookup[unit_ids] = np.arange(len(unit_ids))
    zone_index = np.clip(zones_raw, 0, max_id).astype("int64")
    dense = np.where(zone_valid, lookup[zone_index], -1)
    zone_valid &= dense >= 0
    dense_zones = np.where(zone_valid, dense, 0).astype("int64")

    n = len(unit_ids)
    results: dict[str, np.ndarray] = {}

    for name, path in rasters.items():
        with rasterio.open(path) as src:
            data = src.read(1).astype("float64")
            nodata = src.nodata

        valid = zone_valid.copy()
        if nodata is not None:
            valid &= ~np.isclose(data, nodata)
        valid &= np.isfinite(data)

        if name in CIRCULAR_LAYERS:
            # Drop the undefined-aspect flag before averaging. See the note on
            # ASPECT_UNDEFINED_BELOW above.
            valid &= data >= ASPECT_UNDEFINED_BELOW
            # Vector mean of the direction, then back to degrees in [0, 360).
            radians = np.deg2rad(data)
            sin_sum, counts = _zonal_mean(np.sin(radians), dense_zones, valid, n)
            cos_sum, _ = _zonal_mean(np.cos(radians), dense_zones, valid, n)
            with np.errstate(invalid="ignore", divide="ignore"):
                mean = np.degrees(np.arctan2(sin_sum, cos_sum))
            mean = np.where(counts > 0, np.mod(mean, 360.0), np.nan)
            results[name] = mean
            continue

        sums, counts = _zonal_mean(data, dense_zones, valid, n)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)
        results[name] = mean

        if name == "slope":
            # Second pass for variance, using the mean just computed.
            per_cell_mean = np.where(valid, mean[dense_zones], 0.0)
            deviation = np.where(valid, (data - per_cell_mean) ** 2, 0.0)
            var_sums, _ = _zonal_mean(deviation, dense_zones, valid, n)
            with np.errstate(invalid="ignore", divide="ignore"):
                results["slope_std"] = np.where(
                    counts > 0, np.sqrt(var_sums / np.maximum(counts, 1)), np.nan
                )

            maxima = np.full(n, -np.inf)
            np.maximum.at(maxima, dense_zones[valid], data[valid])
            results["slope_max"] = np.where(np.isfinite(maxima), maxima, np.nan)

    return results


def build_slope_units(
    hillslope_raster: Path,
    rasters: dict[str, Path],
    min_area_m2: float = MIN_UNIT_AREA_M2,
) -> SlopeUnitTable:
    unit_ids, geometries, areas, crs = polygonise_hillslopes(hillslope_raster, min_area_m2)
    if len(unit_ids) == 0:
        raise RuntimeError(
            "Hillslope delineation produced no units above the minimum area. "
            "The stream threshold is probably too high for this region."
        )
    attributes = aggregate_to_units(hillslope_raster, rasters, unit_ids)
    return SlopeUnitTable(
        unit_ids=unit_ids,
        geometries=geometries,
        areas_m2=areas,
        attributes=attributes,
        crs=crs,
    )

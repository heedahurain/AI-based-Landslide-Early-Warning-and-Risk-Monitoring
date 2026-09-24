"""Known-answer tests for the terrain mathematics.

A wrong slope angle propagates directly into the factor-of-safety calculation,
where beta appears in both a cosine-squared and a sine-cosine term. An error
here would not crash anything. It would produce a confident, plausible and
wrong number, which is the worst possible failure mode for this system. So the
geometry is pinned against surfaces whose answers are known by construction.

These run offline. Nothing here touches the network or a database.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
whitebox = pytest.importorskip("whitebox")

from rasterio.transform import from_origin  # noqa: E402

from ingest.terrain.regions import NER, get_region  # noqa: E402
from ingest.terrain.slope_units import (  # noqa: E402
    ASPECT_UNDEFINED_BELOW,
    aggregate_to_units,
    polygonise_hillslopes,
)

CELL = 10.0
SIZE = 40
# The outermost cells use a clipped 3x3 window, so the operator has no valid
# neighbourhood there. Every assertion is made on the interior.
EDGE = 3
NODATA = -9999.0


def write_raster(path: Path, array: np.ndarray, cell: float = CELL, dtype: str = "float32") -> Path:
    rows, cols = array.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=rows,
        width=cols,
        count=1,
        dtype=dtype,
        crs="EPSG:32646",
        transform=from_origin(500_000, 2_800_000, cell, cell),
        nodata=NODATA,
    ) as dst:
        dst.write(array.astype(dtype), 1)
    return path


def interior(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        window: np.ndarray = src.read(1)[EDGE:-EDGE, EDGE:-EDGE]
    return window


@pytest.fixture(scope="module")
def wbt():  # type: ignore[no-untyped-def]
    tools = whitebox.WhiteboxTools()
    tools.set_verbose_mode(False)
    return tools


def inclined_plane(gradient: float) -> np.ndarray:
    """A plane descending toward the east with the given rise over run."""
    _, xx = np.mgrid[0:SIZE, 0:SIZE].astype("float64")
    plane: np.ndarray = (SIZE - xx) * CELL * gradient
    return plane


@pytest.mark.parametrize("degrees", [15.0, 30.0, 45.0, 60.0])
def test_slope_of_a_plane_is_exact(tmp_path: Path, wbt, degrees: float) -> None:  # type: ignore[no-untyped-def]
    """The slope of a planar surface must equal its construction angle."""
    dem = write_raster(tmp_path / "dem.tif", inclined_plane(math.tan(math.radians(degrees))))
    out = tmp_path / "slope.tif"
    assert wbt.slope(str(dem), str(out), units="degrees") == 0

    values = interior(out)
    assert np.allclose(values, degrees, atol=1e-3), (
        f"expected {degrees} deg, got mean {values.mean():.4f}"
    )


def test_slope_of_a_flat_surface_is_zero(tmp_path: Path, wbt) -> None:  # type: ignore[no-untyped-def]
    dem = write_raster(tmp_path / "flat.tif", np.full((SIZE, SIZE), 100.0))
    out = tmp_path / "slope.tif"
    assert wbt.slope(str(dem), str(out), units="degrees") == 0
    assert np.allclose(interior(out), 0.0, atol=1e-6)


def test_aspect_of_an_east_facing_plane_is_ninety_degrees(tmp_path: Path, wbt) -> None:  # type: ignore[no-untyped-def]
    """Aspect is an azimuth measured clockwise from north.

    Verified empirically against WhiteboxTools 2.4.0 rather than assumed, since
    aspect conventions differ between packages and a 90-degree error would
    silently invert the orographic rainfall multiplier.
    """
    dem = write_raster(tmp_path / "east.tif", inclined_plane(1.0))
    out = tmp_path / "aspect.tif"
    assert wbt.aspect(str(dem), str(out)) == 0
    assert np.allclose(interior(out), 90.0, atol=1e-2)


def test_aspect_undefined_flag_is_documented_and_excluded(tmp_path: Path, wbt) -> None:  # type: ignore[no-untyped-def]
    """WhiteboxTools writes -1 where aspect is undefined.

    Measured on 2026-09-09: a perfectly planar surface descending due north or
    due south returns -1 across the interior, even though its slope is a
    correct 45 degrees. The value is a flag, not an azimuth. This test pins the
    behaviour so that if a future WhiteboxTools release changes it, the
    exclusion rule in slope_units.py is revisited deliberately.
    """
    yy, _ = np.mgrid[0:SIZE, 0:SIZE].astype("float64")
    north_south = (SIZE - yy) * CELL

    dem = write_raster(tmp_path / "ns.tif", north_south)
    slope_out = tmp_path / "ns_slope.tif"
    aspect_out = tmp_path / "ns_aspect.tif"
    assert wbt.slope(str(dem), str(slope_out), units="degrees") == 0
    assert wbt.aspect(str(dem), str(aspect_out)) == 0

    # The surface genuinely slopes.
    assert np.allclose(interior(slope_out), 45.0, atol=1e-3)
    # Yet aspect is flagged undefined, and the flag sits below the valid range.
    assert np.all(interior(aspect_out) < ASPECT_UNDEFINED_BELOW)


def test_circular_mean_handles_the_north_wraparound(tmp_path: Path) -> None:
    """Aspects of 1 and 359 degrees average to 0, never to 180.

    An arithmetic mean would report a north-facing slope as south-facing, which
    would invert its exposure to the monsoon.
    """
    zones = np.ones((2, 2), dtype="int32")
    aspect = np.array([[1.0, 359.0], [1.0, 359.0]])

    write_raster(tmp_path / "zones.tif", zones, dtype="int32")
    write_raster(tmp_path / "aspect.tif", aspect)

    result = aggregate_to_units(
        tmp_path / "zones.tif",
        {"aspect": tmp_path / "aspect.tif"},
        np.array([1], dtype="int64"),
    )
    mean = float(result["aspect"][0])
    # Either side of due north is correct; the midpoint of 1 and 359 is 0.
    assert min(mean, 360.0 - mean) < 1e-6, f"circular mean returned {mean}"


def test_zonal_mean_matches_a_hand_computed_answer(tmp_path: Path) -> None:
    """Two zones, hand-checked means, and nodata excluded rather than counted."""
    zones = np.array([[1, 1, 2, 2], [1, 1, 2, 2]], dtype="int32")
    slope = np.array(
        [[10.0, 20.0, 30.0, 40.0], [30.0, NODATA, 50.0, 60.0]],
        dtype="float64",
    )

    write_raster(tmp_path / "zones.tif", zones, dtype="int32")
    write_raster(tmp_path / "slope.tif", slope)

    result = aggregate_to_units(
        tmp_path / "zones.tif",
        {"slope": tmp_path / "slope.tif"},
        np.array([1, 2], dtype="int64"),
    )

    # Zone 1: 10, 20, 30 with one nodata excluded -> 20.0
    # Zone 2: 30, 40, 50, 60 -> 45.0
    assert result["slope"][0] == pytest.approx(20.0)
    assert result["slope"][1] == pytest.approx(45.0)
    # The maximum must also ignore the nodata sentinel, not report -9999.
    assert result["slope_max"][0] == pytest.approx(30.0)
    assert result["slope_max"][1] == pytest.approx(60.0)


def test_polygonisation_drops_slivers_and_keeps_real_units(tmp_path: Path) -> None:
    """A one-cell zone is a polygonisation artefact, not a hillslope."""
    zones = np.zeros((20, 20), dtype="int32")
    zones[2:12, 2:12] = 1  # 100 cells at 10 m -> 10,000 m2
    zones[15, 15] = 2  # a single cell -> 100 m2

    write_raster(tmp_path / "zones.tif", zones, dtype="int32")

    ids, geoms, areas, _ = polygonise_hillslopes(tmp_path / "zones.tif", min_area_m2=5_000.0)

    assert ids.tolist() == [1]
    assert areas[0] == pytest.approx(10_000.0)
    assert len(geoms) == 1


def test_area_is_computed_in_metres_not_degrees() -> None:
    """A guard on the projection choice.

    Slope-unit areas are computed in EPSG:32646. If anything ever computes them
    from EPSG:4326 degrees, the numbers collapse by roughly ten orders of
    magnitude, and this catches that class of mistake at the region level.
    """
    assert NER.estimated_pixels(30.0) > 100_000_000
    # The region is roughly 9.5 by 8.1 degrees, which is a very large area.
    assert NER.width_deg == pytest.approx(9.5)
    assert NER.height_deg == pytest.approx(8.1)


def test_unknown_region_names_are_rejected_with_a_helpful_message() -> None:
    with pytest.raises(KeyError, match="Available"):
        get_region("not-a-region")

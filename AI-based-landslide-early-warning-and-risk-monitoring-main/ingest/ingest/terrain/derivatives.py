"""Terrain derivatives, computed with WhiteboxTools.

WhiteboxTools rather than richdem: richdem publishes no distribution for
Python 3.12 or 3.13, while WhiteboxTools ships a self-contained binary, covers
every derivative this phase needs, and provides the `hillslopes` tool that
produces genuine hydrological slope units rather than a grid.

The order below is not arbitrary. Flow routing needs a depression-free surface,
stream extraction needs flow accumulation, and hillslope delineation needs both
a flow pointer and a stream network. Running them out of order silently
produces plausible-looking nonsense.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

log = logging.getLogger(__name__)


# Contributing area, in cells, above which a cell is treated as a channel.
#
# This single number sets drainage density and therefore how many slope units
# the region is divided into. Measured on the Noney pilot at 30 m
# (4,486 km2, 2228 x 2363 px), extrapolated to the 260,629 km2 of the eight
# states by area:
#
#     threshold   units (pilot)   mean area   region equivalent
#           400          14,714     30.5 ha             854,808
#         2,000           3,380    133.8 ha             196,361
#        10,000             632    696.7 ha              36,716
#        30,000             176  2,405.3 ha              10,225   <- target range
#        90,000              53  7,592.3 ha               3,079
#
# The Phase 1 brief asks for 8,000 to 20,000 units across the region, and
# 30,000 cells is what lands inside it. Note the tension worth stating aloud:
# units of roughly 24 km2 are catchment scale, while a shallow landslide is
# 0.1 to 10 hectares. A lower threshold is physically closer to the failure
# scale but produces far more units than the brief asks for. The parameter is
# exposed on the command line so that trade is made deliberately.
DEFAULT_STREAM_THRESHOLD_CELLS = 30_000


@dataclass(frozen=True)
class DerivativeSet:
    """Every raster the pipeline produces, by role."""

    dem_filled: Path
    slope: Path
    aspect: Path
    plan_curvature: Path
    profile_curvature: Path
    flow_accumulation: Path
    specific_catchment_area: Path
    twi: Path
    tpi: Path
    streams: Path
    distance_to_stream: Path
    hillslopes: Path
    local_relief: Path

    def as_dict(self) -> dict[str, Path]:
        return {
            "dem_filled": self.dem_filled,
            "slope": self.slope,
            "aspect": self.aspect,
            "plan_curvature": self.plan_curvature,
            "profile_curvature": self.profile_curvature,
            "flow_accumulation": self.flow_accumulation,
            "specific_catchment_area": self.specific_catchment_area,
            "twi": self.twi,
            "tpi": self.tpi,
            "streams": self.streams,
            "distance_to_stream": self.distance_to_stream,
            "hillslopes": self.hillslopes,
            "local_relief": self.local_relief,
        }


def _wbt(work_dir: Path):  # type: ignore[no-untyped-def]
    import whitebox

    tools = whitebox.WhiteboxTools()
    tools.set_working_dir(str(work_dir))
    tools.set_verbose_mode(False)
    return tools


def _check(code: int, tool: str, output: Path) -> Path:
    """WhiteboxTools signals failure by return code, not by exception."""
    if code != 0 or not output.exists():
        raise RuntimeError(f"WhiteboxTools {tool} failed with code {code}: {output}")
    return output


def compute_local_relief(dem_path: Path, output: Path, radius_cells: int = 15) -> Path:
    """Local relief: the elevation range within a moving window.

    Computed here rather than in WhiteboxTools because it is a two-line
    morphological operation and doing it directly keeps the definition explicit:
    maximum minus minimum elevation inside the window, in metres.

    Relief separates a steep face on a large hillside from a steep face on a
    small bank, and the two behave very differently.
    """
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype("float32")
        profile = src.profile.copy()
        nodata = src.nodata

    mask = np.isclose(dem, nodata) if nodata is not None else np.zeros(dem.shape, bool)

    # Fill voids with the local mean before the window pass, so a nodata cell
    # does not drag the window minimum down to the nodata sentinel.
    filled = np.where(mask, np.nan, dem)
    if np.isnan(filled).any():
        median = float(np.nanmedian(filled)) if not np.all(np.isnan(filled)) else 0.0
        filled = np.where(np.isnan(filled), median, filled)

    size = radius_cells * 2 + 1
    high = ndimage.maximum_filter(filled, size=size, mode="nearest")
    low = ndimage.minimum_filter(filled, size=size, mode="nearest")
    relief = (high - low).astype("float32")
    relief[mask] = -9999.0

    # Build the output profile explicitly rather than inheriting it.
    # WhiteboxTools writes GeoTIFFs whose internal block size is not a multiple
    # of 16, and reusing that profile makes GDAL refuse the write with
    # RasterBlockError. Only the georeferencing is carried over.
    profile.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        nodata=-9999.0,
        compress="deflate",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    profile.pop("interleave", None)

    with rasterio.open(output, "w", **profile) as dst:
        dst.write(relief, 1)

    return output


def compute_derivatives(
    dem_utm: Path,
    work_dir: Path,
    *,
    stream_threshold_cells: int = DEFAULT_STREAM_THRESHOLD_CELLS,
    tpi_window_cells: int = 15,
    relief_radius_cells: int = 15,
) -> DerivativeSet:
    """Run the full derivative chain over a projected DEM.

    `stream_threshold_cells` is the contributing area, in cells, above which a
    cell is treated as a channel. It is the single most consequential parameter
    here: it sets the drainage density, and therefore how many hillslopes the
    region is divided into. See DEFAULT_STREAM_THRESHOLD_CELLS for the measured
    relationship.

    The threshold counts cells, so its meaning depends on resolution. At 30 m
    one cell is 900 square metres; at 90 m it is 8,100. Changing resolution
    without rescaling the threshold changes the slope-unit size ninefold.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    tools = _wbt(work_dir)

    dem = str(dem_utm.resolve())
    out = {
        name: work_dir / f"{name}.tif"
        for name in (
            "dem_filled",
            "slope",
            "aspect",
            "plan_curvature",
            "profile_curvature",
            "flow_accumulation",
            "specific_catchment_area",
            "twi",
            "tpi",
            "streams",
            "distance_to_stream",
            "hillslopes",
            "d8_pointer",
            "local_relief",
        )
    }
    p = {k: str(v.resolve()) for k, v in out.items()}

    # 1. Hydrological conditioning. Breaching carves a path through a
    #    depression rather than filling it, which preserves the real valley
    #    floor instead of flooding it flat.
    log.info("terrain.breach_depressions")
    _check(
        tools.breach_depressions_least_cost(dem, p["dem_filled"], dist=100, fill=True),
        "breach_depressions_least_cost",
        out["dem_filled"],
    )

    # 2. Flow routing.
    log.info("terrain.flow_routing")
    _check(tools.d8_pointer(p["dem_filled"], p["d8_pointer"]), "d8_pointer", out["d8_pointer"])
    _check(
        tools.d8_flow_accumulation(p["dem_filled"], p["flow_accumulation"], out_type="cells"),
        "d8_flow_accumulation",
        out["flow_accumulation"],
    )
    _check(
        tools.d8_flow_accumulation(
            p["dem_filled"], p["specific_catchment_area"], out_type="specific contributing area"
        ),
        "d8_flow_accumulation(sca)",
        out["specific_catchment_area"],
    )

    # 3. Surface geometry. Slope is in degrees because that is what the
    #    infinite-slope equation takes as beta.
    log.info("terrain.surface_geometry")
    _check(tools.slope(p["dem_filled"], p["slope"], units="degrees"), "slope", out["slope"])
    _check(tools.aspect(p["dem_filled"], p["aspect"]), "aspect", out["aspect"])
    _check(
        tools.plan_curvature(p["dem_filled"], p["plan_curvature"]),
        "plan_curvature",
        out["plan_curvature"],
    )
    _check(
        tools.profile_curvature(p["dem_filled"], p["profile_curvature"]),
        "profile_curvature",
        out["profile_curvature"],
    )

    # 4. Wetness. TWI combines upslope contributing area with local gradient:
    #    a large catchment draining onto a gentle slope stays wet, and wet
    #    ground raises pore pressure, which is what drives the physics layer.
    log.info("terrain.wetness")
    _check(
        tools.wetness_index(p["specific_catchment_area"], p["slope"], p["twi"]),
        "wetness_index",
        out["twi"],
    )
    _check(
        tools.relative_topographic_position(
            p["dem_filled"], p["tpi"], filterx=tpi_window_cells, filtery=tpi_window_cells
        ),
        "relative_topographic_position",
        out["tpi"],
    )

    # 5. Channels and hillslopes. `hillslopes` splits each basin into its
    #    left-bank and right-bank halves, bounded below by the channel and
    #    above by the divide. That is the slope unit definition from the brief,
    #    and the reason this is not a grid.
    log.info("terrain.streams_and_hillslopes")
    _check(
        tools.extract_streams(
            p["flow_accumulation"], p["streams"], threshold=stream_threshold_cells
        ),
        "extract_streams",
        out["streams"],
    )
    _check(
        tools.downslope_distance_to_stream(p["dem_filled"], p["streams"], p["distance_to_stream"]),
        "downslope_distance_to_stream",
        out["distance_to_stream"],
    )
    _check(
        tools.hillslopes(p["d8_pointer"], p["streams"], p["hillslopes"]),
        "hillslopes",
        out["hillslopes"],
    )

    # 6. Local relief.
    log.info("terrain.local_relief")
    compute_local_relief(out["dem_filled"], out["local_relief"], radius_cells=relief_radius_cells)

    return DerivativeSet(
        dem_filled=out["dem_filled"],
        slope=out["slope"],
        aspect=out["aspect"],
        plan_curvature=out["plan_curvature"],
        profile_curvature=out["profile_curvature"],
        flow_accumulation=out["flow_accumulation"],
        specific_catchment_area=out["specific_catchment_area"],
        twi=out["twi"],
        tpi=out["tpi"],
        streams=out["streams"],
        distance_to_stream=out["distance_to_stream"],
        hillslopes=out["hillslopes"],
        local_relief=out["local_relief"],
    )

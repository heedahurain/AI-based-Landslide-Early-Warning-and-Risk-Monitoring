"""Administrative boundaries for the eight North Eastern states.

Source: the datameet/maps community repository, Census 2011 district
boundaries, verified reachable on 2026-09-08. Licence and caveats are recorded
in docs/DATA_SOURCES.md section 4.

Two decisions here are load-bearing.

**Match on census codes, never on state names.** The source spells Arunachal
Pradesh as "Arunanchal Pradesh". Filtering by name silently drops the largest
state in the region, and the failure is invisible: the pipeline succeeds, the
map renders, and one state is simply absent. Census state codes are stable and
authoritative, so they are the join key and canonical names are supplied here.

**States are dissolved from districts** rather than loaded from a second file,
so state and district geometry agree exactly. Mixing two sources produces
slivers along shared borders and makes point-in-polygon assignment ambiguous.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DATAMEET_BASE = (
    "https://raw.githubusercontent.com/datameet/maps/master/Districts/Census_2011/2011_Dist"
)
SHAPEFILE_PARTS = ("shp", "shx", "dbf", "prj")

STORAGE_CRS = "EPSG:4326"
COMPUTATION_CRS = "EPSG:32646"

SOURCE_KEY = "datameet_census_2011"

# Census 2011 state codes for the eight states. Authoritative and stable, which
# is exactly what the misspelt name column is not.
NER_STATE_CODES: dict[int, str] = {
    11: "Sikkim",
    12: "Arunachal Pradesh",
    13: "Nagaland",
    14: "Manipur",
    15: "Mizoram",
    16: "Tripura",
    17: "Meghalaya",
    18: "Assam",
}


@dataclass
class BoundaryLoadResult:
    states: Any
    districts: Any
    summary: dict[str, Any]


def download_source(cache_dir: Path) -> Path:
    """Fetch the shapefile and its companions, skipping parts already present.

    A shapefile is four files. Downloading only the .shp produces an
    unreadable dataset, so all parts are fetched together.
    """
    import urllib.request

    cache_dir.mkdir(parents=True, exist_ok=True)
    shp_path = cache_dir / "2011_Dist.shp"

    for part in SHAPEFILE_PARTS:
        target = cache_dir / f"2011_Dist.{part}"
        if target.exists() and target.stat().st_size > 0:
            continue
        url = f"{DATAMEET_BASE}.{part}"
        log.info("boundaries.download", extra={"part": part})
        with urllib.request.urlopen(url, timeout=180) as response:
            target.write_bytes(response.read())

    if not shp_path.exists():
        raise RuntimeError(f"Boundary download failed: {shp_path} missing")
    return shp_path


def load_ner_boundaries(cache_dir: Path) -> BoundaryLoadResult:
    """Return state and district GeoDataFrames for the eight states."""
    import geopandas as gpd

    shp_path = download_source(cache_dir)
    everything = gpd.read_file(shp_path)

    if "ST_CEN_CD" not in everything.columns:
        raise RuntimeError(
            "Expected column ST_CEN_CD in the Census 2011 district file. "
            f"Found: {list(everything.columns)}. The upstream schema has changed."
        )

    districts = everything[everything["ST_CEN_CD"].isin(NER_STATE_CODES)].copy()
    if districts.empty:
        raise RuntimeError("No districts matched the eight North Eastern state codes.")

    # Canonical names replace the source's spelling.
    districts["state_name"] = districts["ST_CEN_CD"].map(NER_STATE_CODES)
    districts["state_code"] = districts["ST_CEN_CD"].astype(int)
    districts["district_name"] = districts["DISTRICT"].astype(str).str.strip()
    districts["district_code"] = districts["DT_CEN_CD"].astype(int)
    districts["census_code"] = districts["censuscode"].astype(int)
    districts = districts.set_crs(STORAGE_CRS, allow_override=True)

    # Area in projected metres. Computing it from degrees would be wrong by
    # several orders of magnitude and vary with latitude.
    districts["area_km2"] = districts.to_crs(COMPUTATION_CRS).area / 1e6

    missing = set(NER_STATE_CODES) - set(districts["state_code"].unique())
    if missing:
        names = ", ".join(NER_STATE_CODES[c] for c in sorted(missing))
        raise RuntimeError(f"These states are absent from the source data: {names}")

    states = (
        districts[["state_code", "state_name", "geometry"]]
        .dissolve(by="state_code", as_index=False)
        .rename(columns={"state_name": "name"})
    )
    states["area_km2"] = states.to_crs(COMPUTATION_CRS).area / 1e6

    summary: dict[str, Any] = {
        "source": SOURCE_KEY,
        "vintage": "Census 2011",
        "state_count": len(states),
        "district_count": len(districts),
        "total_area_km2": round(float(districts["area_km2"].sum()), 1),
        "bounds": [round(float(v), 4) for v in districts.total_bounds],
        "districts_per_state": {
            NER_STATE_CODES[int(code)]: int(count)
            for code, count in districts["state_code"].value_counts().sort_index().items()
        },
        # Every boundary loaded this way is unofficial. The interface must say so.
        "provisional": True,
    }

    log.info("boundaries.loaded", extra=summary)
    return BoundaryLoadResult(states=states, districts=districts, summary=summary)


def write_outputs(result: BoundaryLoadResult, output_dir: Path) -> dict[str, Path]:
    """Write GeoPackage and Parquet, which the API loads when a database exists."""
    output_dir.mkdir(parents=True, exist_ok=True)

    gpkg = output_dir / "ner_boundaries.gpkg"
    result.states.to_file(gpkg, layer="state", driver="GPKG")
    result.districts.to_file(gpkg, layer="district", driver="GPKG")

    states_parquet = output_dir / "states.parquet"
    districts_parquet = output_dir / "districts.parquet"
    result.states.to_parquet(states_parquet)

    keep = [
        "state_code",
        "state_name",
        "district_name",
        "district_code",
        "census_code",
        "area_km2",
        "geometry",
    ]
    result.districts[keep].to_parquet(districts_parquet)

    return {
        "boundaries_gpkg": gpkg,
        "states_parquet": states_parquet,
        "districts_parquet": districts_parquet,
    }

"""Roads and critical facilities from OpenStreetMap.

Fetched through the Overpass API, verified reachable on 2026-09-08. Overpass is
a shared community resource, so results are cached to disk, requests are made
one area at a time, and the query asks only for the tags actually needed.

Roads feed the Phase 7 connectivity graph. Hospitals, schools and helipads feed
the Phase 8 exposure and response-prioritisation terms. Both are loaded here so
the geometry exists before the analyses that depend on it.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

# Vehicle-carrying roads only. Tracks and footpaths would triple the graph
# without changing whether an ambulance or a JCB can reach a village.
ROAD_FILTER = (
    "motorway|trunk|primary|secondary|tertiary|unclassified|residential"
    "|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link"
)

FACILITY_QUERIES = {
    "hospital": '["amenity"="hospital"]',
    "clinic": '["amenity"="clinic"]',
    "school": '["amenity"="school"]',
    "helipad": '["aeroway"="helipad"]',
    "police": '["amenity"="police"]',
    "fire": '["amenity"="fire_station"]',
}

REQUEST_TIMEOUT = 300


@dataclass
class OsmResult:
    roads: Any
    facilities: Any
    summary: dict[str, Any]


def _overpass(query: str, cache_path: Path) -> dict[str, Any]:
    """Run one Overpass query, using the cached response when present."""
    if cache_path.exists() and cache_path.stat().st_size > 0:
        log.info("osm.cache_hit", extra={"path": str(cache_path)})
        cached: dict[str, Any] = json.loads(cache_path.read_text(encoding="utf-8"))
        return cached

    payload = urllib.parse.urlencode({"data": query}).encode()
    last_error: Exception | None = None

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            log.info("osm.request", extra={"endpoint": endpoint})
            request = urllib.request.Request(
                endpoint,
                data=payload,
                headers={"User-Agent": "ShailSuraksha/0.1 (SIH26001 terrain pipeline)"},
            )
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                body = response.read().decode("utf-8")
            data: dict[str, Any] = json.loads(body)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(body, encoding="utf-8")
            return data
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            last_error = exc
            log.warning("osm.endpoint_failed", extra={"endpoint": endpoint, "error": str(exc)})
            time.sleep(2)

    raise RuntimeError(f"All Overpass endpoints failed. Last error: {last_error}")


def fetch_roads(bbox: tuple[float, float, float, float], cache_dir: Path) -> Any:
    """Return a GeoDataFrame of road centrelines inside the bounding box."""
    import geopandas as gpd
    from shapely.geometry import LineString

    west, south, east, north = bbox
    # Overpass orders a bbox as south, west, north, east.
    query = f"""
    [out:json][timeout:{REQUEST_TIMEOUT}];
    way["highway"~"^({ROAD_FILTER})$"]({south},{west},{north},{east});
    out geom tags;
    """
    data = _overpass(query, cache_dir / "roads.json")

    records: list[dict[str, Any]] = []
    for element in data.get("elements", []):
        geometry = element.get("geometry") or []
        if len(geometry) < 2:
            continue
        tags = element.get("tags", {})
        line = LineString([(point["lon"], point["lat"]) for point in geometry])
        records.append(
            {
                "osm_id": str(element.get("id")),
                "name": tags.get("name"),
                "highway_class": tags.get("highway", "unclassified"),
                "is_bridge": tags.get("bridge") not in (None, "no"),
                "is_tunnel": tags.get("tunnel") not in (None, "no"),
                "surface": tags.get("surface"),
                "geometry": line,
            }
        )

    frame = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    if not frame.empty:
        frame["length_m"] = frame.to_crs("EPSG:32646").length
    else:
        frame["length_m"] = []
    return frame


def fetch_facilities(bbox: tuple[float, float, float, float], cache_dir: Path) -> Any:
    """Return a GeoDataFrame of critical facilities as points.

    Facilities are mapped as nodes, ways and relations. Ways and relations are
    reduced to their centroid, because what matters downstream is where a
    hospital is, not the shape of its perimeter.
    """
    import geopandas as gpd
    from shapely.geometry import Point

    west, south, east, north = bbox
    # One small request per category, each cached separately.
    #
    # Two earlier shapes both returned 504 Gateway Timeout from every mirror:
    # twelve node/way statements in one query, and a single `nwr` statement
    # with a regular-expression alternation. A plain exact-match query for one
    # tag answers in well under a second on the same bounding box. Regular
    # expressions force Overpass to scan rather than use its tag index, and
    # `nwr` drags relations in as well.
    #
    # Splitting the work also keeps each request inside the public rate limit
    # of two concurrent slots, and a category that fails degrades to a gap in
    # the results rather than losing the whole fetch.
    elements: list[dict[str, Any]] = []
    failures: list[str] = []

    for category, tag in FACILITY_QUERIES.items():
        query = f"""
        [out:json][timeout:90];
        (
          node{tag}({south},{west},{north},{east});
          way{tag}({south},{west},{north},{east});
        );
        out center tags;
        """
        try:
            payload = _overpass(query, cache_dir / f"facilities_{category}.json")
        except Exception as exc:  # noqa: BLE001 - a missing category is a gap, not a failure
            log.warning("osm.category_failed", extra={"category": category, "error": str(exc)})
            failures.append(category)
            continue
        elements.extend(payload.get("elements", []))
        # Overpass is a shared community resource. Space the requests out.
        time.sleep(1.5)

    if failures and len(failures) == len(FACILITY_QUERIES):
        raise RuntimeError(f"Every facility category failed: {', '.join(failures)}")
    if failures:
        log.warning("osm.partial_facilities", extra={"missing": failures})

    data = {"elements": elements}

    tag_to_category = {
        ("amenity", "hospital"): "hospital",
        ("amenity", "clinic"): "clinic",
        ("amenity", "school"): "school",
        ("aeroway", "helipad"): "helipad",
        ("amenity", "police"): "police",
        ("amenity", "fire_station"): "fire",
    }

    records: list[dict[str, Any]] = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        matched: str | None = None
        for (key, value), name in tag_to_category.items():
            if tags.get(key) == value:
                matched = name
                break
        if matched is None:
            continue

        if element.get("type") == "node":
            lon, lat = element.get("lon"), element.get("lat")
        else:
            centre = element.get("center") or {}
            lon, lat = centre.get("lon"), centre.get("lat")
        if lon is None or lat is None:
            continue

        records.append(
            {
                "osm_id": str(element.get("id")),
                "name": tags.get("name"),
                "category": matched,
                "capacity": _as_int(tags.get("capacity") or tags.get("beds")),
                "geometry": Point(lon, lat),
            }
        )

    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")


def _as_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def load_osm(bbox: tuple[float, float, float, float], cache_dir: Path) -> OsmResult:
    roads = fetch_roads(bbox, cache_dir)
    facilities = fetch_facilities(bbox, cache_dir)

    summary: dict[str, Any] = {
        "source": "openstreetmap_overpass",
        "licence": "ODbL, attribution required",
        "road_count": len(roads),
        "road_length_km": round(float(roads["length_m"].sum() / 1000), 1) if len(roads) else 0.0,
        "roads_by_class": (roads["highway_class"].value_counts().to_dict() if len(roads) else {}),
        "facility_count": len(facilities),
        "facilities_by_category": (
            facilities["category"].value_counts().to_dict() if len(facilities) else {}
        ),
    }
    log.info("osm.loaded", extra=summary)
    return OsmResult(roads=roads, facilities=facilities, summary=summary)


def write_outputs(result: OsmResult, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}

    if len(result.roads):
        roads_path = output_dir / "roads.parquet"
        result.roads.to_parquet(roads_path)
        outputs["roads_parquet"] = roads_path

    if len(result.facilities):
        facilities_path = output_dir / "facilities.parquet"
        result.facilities.to_parquet(facilities_path)
        outputs["facilities_parquet"] = facilities_path

    return outputs

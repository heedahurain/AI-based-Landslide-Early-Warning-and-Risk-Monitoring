"""Terrain pipeline orchestration.

Every step records itself in a manifest so an interrupted run resumes instead
of restarting. That matters because the download and the flow-routing steps are
the slow ones, and a region-scale run will be interrupted at some point.

The pipeline degrades honestly. With no MinIO it writes to the local output
directory. With no database it writes GeoPackage and Parquet and says so. It
never silently skips a step it could not do.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ingest.terrain import dem as dem_module
from ingest.terrain.derivatives import DEFAULT_STREAM_THRESHOLD_CELLS, compute_derivatives
from ingest.terrain.regions import Region, get_region
from ingest.terrain.slope_units import build_slope_units

log = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"

# Attributes copied from the raster aggregation into terrain_profile columns.
RASTER_TO_COLUMN = {
    "slope": "slope_deg",
    "slope_max": "slope_max_deg",
    "slope_std": "slope_std_deg",
    "aspect": "aspect_deg",
    "plan_curvature": "plan_curvature",
    "profile_curvature": "profile_curvature",
    "twi": "twi",
    "tpi": "tpi",
    "flow_accumulation": "flow_accumulation",
    "distance_to_stream": "distance_to_stream_m",
    "local_relief": "local_relief_m",
    "dem_filled": "elevation_mean_m",
}


@dataclass
class StepRecord:
    name: str
    status: str
    started_at: str
    finished_at: str | None = None
    duration_s: float | None = None
    outputs: dict[str, str] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Manifest:
    """Run state on disk, so a run can be resumed or audited afterwards."""

    def __init__(self, path: Path, region: Region, resolution_m: float) -> None:
        self.path = path
        self.data: dict[str, Any] = {
            "region": region.key,
            "region_name": region.name,
            "bbox": list(region.bbox),
            "resolution_m": resolution_m,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "steps": {},
        }
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    @property
    def run_id(self) -> str:
        return f"{self.data['region']}_{int(self.data['resolution_m'])}m"

    def is_done(self, step: str) -> bool:
        record = self.data["steps"].get(step)
        if not record or record.get("status") != "complete":
            return False
        # A manifest entry is not proof. If the output has been deleted, the
        # step has to run again.
        return all(Path(p).exists() for p in record.get("outputs", {}).values())

    def outputs(self, step: str) -> dict[str, Path]:
        return {k: Path(v) for k, v in self.data["steps"][step].get("outputs", {}).items()}

    def record(self, record: StepRecord) -> None:
        self.data["steps"][record.name] = asdict(record)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")


class TerrainPipeline:
    def __init__(
        self,
        region_key: str,
        resolution_m: float = 30.0,
        output_root: Path | None = None,
        *,
        stream_threshold_cells: int = DEFAULT_STREAM_THRESHOLD_CELLS,
        dem_source: str = "auto",
        force: bool = False,
    ) -> None:
        self.region = get_region(region_key)
        self.resolution_m = resolution_m
        self.stream_threshold_cells = stream_threshold_cells
        self.dem_source = dem_source
        self.force = force

        root = output_root or Path("data/terrain")
        self.work_dir = root / f"{self.region.key}_{int(resolution_m)}m"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = Manifest(self.work_dir / MANIFEST_NAME, self.region, resolution_m)

    # ------------------------------------------------------------------ util
    def _run_step(self, name: str, fn, **kwargs: Any) -> dict[str, Path]:  # type: ignore[no-untyped-def]
        if self.manifest.is_done(name) and not self.force:
            outputs: dict[str, Path] = self.manifest.outputs(name)
            log.info("step.skipped", extra={"step": name})
            print(f"  [skip] {name} (already complete)")
            return outputs

        print(f"  [run ] {name} ...", flush=True)
        started = time.perf_counter()
        record = StepRecord(
            name=name,
            status="running",
            started_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        self.manifest.record(record)

        try:
            outputs, detail = fn(**kwargs)
        except Exception as exc:
            record.status = "failed"
            record.error = f"{type(exc).__name__}: {exc}"
            record.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
            self.manifest.record(record)
            raise

        duration = time.perf_counter() - started
        record.status = "complete"
        record.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
        record.duration_s = round(duration, 2)
        record.outputs = {k: str(v) for k, v in outputs.items()}
        record.detail = detail
        self.manifest.record(record)
        print(f"  [done] {name} in {duration:.1f}s")
        return outputs

    # ----------------------------------------------------------------- steps
    def step_fetch_dem(self) -> dict[str, Path]:
        def run() -> tuple[dict[str, Path], dict[str, Any]]:
            destination = self.work_dir / "dem_4326.tif"
            cache_root = self.work_dir.parent

            def copernicus() -> tuple[dict[str, Path], dict[str, Any]]:
                hrefs = dem_module.search_dem_items(self.region)
                # Tiles are cached outside the run directory, so every region
                # and resolution overlapping them reuses the same downloads.
                tiles = dem_module.download_tiles(hrefs, cache_root / "_dem_tiles")
                mosaic = dem_module.build_mosaic(tiles, self.region, destination)
                return {"dem_4326": mosaic}, {
                    "dem_source": "copernicus_glo30_planetary_computer",
                    "tiles": len(tiles),
                    "tile_names": [t.name for t in tiles],
                    "native_resolution_m": 30.0,
                }

            def terrarium() -> tuple[dict[str, Path], dict[str, Any]]:
                path, detail = dem_module.fetch_terrarium_dem(
                    self.region,
                    destination,
                    self.resolution_m,
                    cache_root / "_terrarium_tiles",
                )
                return {"dem_4326": path}, detail

            if self.dem_source == "copernicus":
                return copernicus()
            if self.dem_source == "terrarium":
                return terrarium()

            # auto: prefer the better dataset, fall back rather than fail, and
            # record which one actually produced the run.
            try:
                return copernicus()
            except Exception as exc:  # noqa: BLE001 - falling back is the point
                log.warning("dem.copernicus_failed", extra={"error": str(exc)})
                print(f"    Copernicus unavailable ({type(exc).__name__}); using AWS Terrain Tiles")
                outputs, detail = terrarium()
                detail["fallback_from"] = f"copernicus: {type(exc).__name__}: {exc}"
                return outputs, detail

        return self._run_step("fetch_dem", run)

    def step_reproject(self, dem_4326: Path) -> dict[str, Path]:
        def run() -> tuple[dict[str, Path], dict[str, Any]]:
            out = dem_module.reproject_to_utm(
                dem_4326, self.work_dir / "dem_utm.tif", self.resolution_m
            )
            return {"dem_utm": out}, dem_module.summarise(out)

        return self._run_step("reproject", run)

    def step_derivatives(self, dem_utm: Path) -> dict[str, Path]:
        def run() -> tuple[dict[str, Path], dict[str, Any]]:
            derived = compute_derivatives(
                dem_utm,
                self.work_dir / "derivatives",
                stream_threshold_cells=self.stream_threshold_cells,
            )
            return derived.as_dict(), {"stream_threshold_cells": self.stream_threshold_cells}

        return self._run_step("derivatives", run)

    def step_slope_units(self, derivatives: dict[str, Path]) -> dict[str, Path]:
        def run() -> tuple[dict[str, Path], dict[str, Any]]:
            import geopandas as gpd

            rasters = {
                key: path
                for key, path in derivatives.items()
                if key
                in {
                    "slope",
                    "aspect",
                    "plan_curvature",
                    "profile_curvature",
                    "twi",
                    "tpi",
                    "flow_accumulation",
                    "distance_to_stream",
                    "local_relief",
                    "dem_filled",
                }
            }

            table = build_slope_units(derivatives["hillslopes"], rasters)

            columns: dict[str, Any] = {
                "hillslope_id": table.unit_ids,
                "area_m2": table.areas_m2,
            }
            for raster_name, column in RASTER_TO_COLUMN.items():
                if raster_name in table.attributes:
                    columns[column] = table.attributes[raster_name]

            frame = gpd.GeoDataFrame(columns, geometry=table.geometries, crs=table.crs)
            frame["run_id"] = self.manifest.run_id

            # Geometry is stored in EPSG:4326 to match the database, while
            # area stays in projected metres, computed before this conversion.
            frame_4326 = frame.to_crs("EPSG:4326")
            frame_4326["centroid_lon"] = frame.geometry.centroid.to_crs("EPSG:4326").x
            frame_4326["centroid_lat"] = frame.geometry.centroid.to_crs("EPSG:4326").y

            gpkg = self.work_dir / "slope_units.gpkg"
            parquet = self.work_dir / "slope_units.parquet"
            frame_4326.to_file(gpkg, driver="GPKG", layer="slope_unit")
            frame_4326.to_parquet(parquet)

            detail = summarise_units(frame_4326)
            return {"slope_units_gpkg": gpkg, "slope_units_parquet": parquet}, detail

        return self._run_step("slope_units", run)

    def step_cog(self, derivatives: dict[str, Path]) -> dict[str, Path]:
        def run() -> tuple[dict[str, Path], dict[str, Any]]:
            from ingest.terrain.cog import convert_derivatives, upload_to_minio

            # The flow pointer is an intermediate for hillslope delineation and
            # is not read by anything downstream, so it is not published.
            publishable = {k: v for k, v in derivatives.items() if k != "d8_pointer"}
            cogs = convert_derivatives(publishable, self.work_dir / "cog")

            keys = upload_to_minio(cogs, prefix=f"terrain/{self.manifest.run_id}")
            total_mb = sum(p.stat().st_size for p in cogs.values()) / 1e6

            return cogs, {
                "raster_count": len(cogs),
                "total_mb": round(total_mb, 1),
                "uploaded_to_minio": bool(keys),
                "object_keys": keys,
            }

        return self._run_step("cog", run)

    # ------------------------------------------------------------------ main
    def build(self) -> dict[str, Any]:
        estimated = self.region.estimated_pixels(self.resolution_m)
        print(f"\nRegion    : {self.region.name} ({self.region.key})")
        print(f"Bounding  : {self.region.bbox}")
        print(f"Resolution: {self.resolution_m:.0f} m")
        print(f"Estimated : {estimated:,} pixels")
        if estimated > 300_000_000:
            print(
                "  WARNING: this run is large. Expect substantial disk and memory use,\n"
                "           and prefer running it inside the api container."
            )
        print(f"Work dir  : {self.work_dir}\n")

        dem_out = self.step_fetch_dem()
        utm_out = self.step_reproject(dem_out["dem_4326"])
        derived = self.step_derivatives(utm_out["dem_utm"])
        units = self.step_slope_units(derived)
        self.step_cog(derived)

        report = {
            "run_id": self.manifest.run_id,
            "region": self.region.key,
            "resolution_m": self.resolution_m,
            "dem": self.manifest.data["steps"]["reproject"]["detail"],
            "slope_units": self.manifest.data["steps"]["slope_units"]["detail"],
            "rasters": self.manifest.data["steps"].get("cog", {}).get("detail", {}),
            "outputs": {k: str(v) for k, v in units.items()},
        }
        (self.work_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report


def summarise_units(frame: Any) -> dict[str, Any]:
    """Descriptive statistics for the run report.

    These are printed as measured. No target or expected value is substituted
    when a computation returns something surprising.
    """
    import numpy as np

    area_km2 = float(frame["area_m2"].sum() / 1e6)
    slope = frame["slope_deg"].to_numpy(dtype="float64")
    slope = slope[np.isfinite(slope)]

    summary: dict[str, Any] = {
        "unit_count": len(frame),
        "total_area_km2": round(area_km2, 2),
        "mean_unit_area_ha": round(float(frame["area_m2"].mean() / 1e4), 2),
        "median_unit_area_ha": round(float(frame["area_m2"].median() / 1e4), 2),
        "min_unit_area_ha": round(float(frame["area_m2"].min() / 1e4), 2),
        "max_unit_area_ha": round(float(frame["area_m2"].max() / 1e4), 2),
    }
    if slope.size:
        summary |= {
            "slope_mean_deg": round(float(np.mean(slope)), 2),
            "slope_median_deg": round(float(np.median(slope)), 2),
            "slope_p90_deg": round(float(np.percentile(slope, 90)), 2),
            "slope_max_deg": round(float(np.max(slope)), 2),
        }
    for column, key in (
        ("elevation_mean_m", "elevation_mean_m"),
        ("twi", "twi_mean"),
        ("local_relief_m", "local_relief_mean_m"),
    ):
        if column in frame:
            values = frame[column].to_numpy(dtype="float64")
            values = values[np.isfinite(values)]
            if values.size:
                summary[key] = round(float(np.mean(values)), 2)
    return summary

"""Command line entry point for the terrain pipeline.

    python -m ingest.terrain build --bbox ner --resolution 30
    python -m ingest.terrain build --bbox noney --resolution 30
    python -m ingest.terrain regions
    python -m ingest.terrain report --bbox noney --resolution 30

The build is idempotent and resumable. Re-running it skips completed steps
whose outputs still exist, so an interrupted regional run continues rather than
starting the download again.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ingest.terrain.derivatives import DEFAULT_STREAM_THRESHOLD_CELLS
from ingest.terrain.pipeline import TerrainPipeline
from ingest.terrain.regions import REGIONS, get_region


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
        datefmt="%H:%M:%S",
    )
    # rasterio and pystac are chatty at INFO and drown out pipeline progress.
    for noisy in ("rasterio", "urllib3", "pystac_client", "fiona"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def cmd_regions(_: argparse.Namespace) -> int:
    print(f"\n{'KEY':10} {'NAME':32} {'BBOX':44} NOTE")
    print("-" * 120)
    for region in REGIONS.values():
        bbox = ", ".join(f"{v:.2f}" for v in region.bbox)
        print(f"{region.key:10} {region.name:32} ({bbox:42}) {region.note}")
    print()
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    pipeline = TerrainPipeline(
        region_key=args.bbox,
        resolution_m=args.resolution,
        output_root=Path(args.output) if args.output else None,
        stream_threshold_cells=args.stream_threshold,
        dem_source=args.dem_source,
        force=args.force,
    )
    report = pipeline.build()

    print("\n" + "=" * 68)
    print(f"TERRAIN REPORT  {report['run_id']}")
    print("=" * 68)

    dem = report["dem"]
    print(f"  DEM              {dem['width']} x {dem['height']} px at {dem['resolution_m']:.1f} m")
    print(
        f"  Elevation        {dem['elevation_min_m']:.0f} to {dem['elevation_max_m']:.0f} m"
        f"  (mean {dem['elevation_mean_m']:.0f} m)"
    )

    units = report["slope_units"]
    print(f"  Slope units      {units['unit_count']:,}")
    print(f"  Area covered     {units['total_area_km2']:,.1f} km2")
    print(
        f"  Unit area        mean {units['mean_unit_area_ha']:.1f} ha,"
        f" median {units['median_unit_area_ha']:.1f} ha"
    )
    if "slope_mean_deg" in units:
        print(
            f"  Slope            mean {units['slope_mean_deg']:.1f} deg,"
            f" median {units['slope_median_deg']:.1f} deg,"
            f" p90 {units['slope_p90_deg']:.1f} deg"
        )
    print("=" * 68 + "\n")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    root = Path(args.output) if args.output else Path("data/terrain")
    region = get_region(args.bbox)
    path = root / f"{region.key}_{int(args.resolution)}m" / "report.json"
    if not path.exists():
        print(f"No report at {path}. Run the build first.", file=sys.stderr)
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ingest.terrain",
        description="ShailSuraksha terrain pipeline: DEM, derivatives, slope units.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="run the pipeline for a region")
    build.add_argument("--bbox", default="ner", help="region key, see the regions command")
    build.add_argument("--resolution", type=float, default=30.0, help="ground resolution in metres")
    build.add_argument("--output", default=None, help="output root, default data/terrain")
    build.add_argument(
        "--stream-threshold",
        type=int,
        default=DEFAULT_STREAM_THRESHOLD_CELLS,
        dest="stream_threshold",
        help=(
            "flow-accumulation cells above which a cell is a channel; sets slope-unit size. "
            "At 30 m: 30000 gives about 10,200 units across the region (the brief's target), "
            "2000 gives about 196,000 units at a scale closer to actual landslides"
        ),
    )
    build.add_argument(
        "--dem-source",
        default="auto",
        choices=("auto", "copernicus", "terrarium"),
        dest="dem_source",
        help=(
            "elevation source. copernicus is GLO-30 via Planetary Computer; terrarium is "
            "AWS Terrain Tiles; auto tries copernicus and falls back, recording which was used"
        ),
    )
    build.add_argument("--force", action="store_true", help="recompute completed steps")
    build.set_defaults(func=cmd_build)

    regions = sub.add_parser("regions", help="list the named regions")
    regions.set_defaults(func=cmd_regions)

    report = sub.add_parser("report", help="print the report from a completed run")
    report.add_argument("--bbox", default="ner")
    report.add_argument("--resolution", type=float, default=30.0)
    report.add_argument("--output", default=None)
    report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrupted. Re-run the same command to resume.", file=sys.stderr)
        return 130
    except Exception as exc:
        logging.getLogger("ingest.terrain").exception("pipeline failed")
        print(f"\nFailed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

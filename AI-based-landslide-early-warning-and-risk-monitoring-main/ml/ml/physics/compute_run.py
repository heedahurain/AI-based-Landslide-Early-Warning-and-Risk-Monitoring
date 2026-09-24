"""Apply the physics layer to a terrain run.

Reads the slope units produced by the Phase 1 pipeline, estimates the inputs the
factor-of-safety equation needs, and writes a factor of safety for each unit
under a set of named wetness scenarios.

Scenarios rather than a forecast, deliberately. The wetness fraction should come
from modelled soil moisture, which arrives with the weather providers in Phase 2.
Until then the honest thing is to answer "how would this hillside behave if the
profile were half saturated", which is a question with a real answer, instead of
inventing today's soil moisture.

    python -m ml.physics.compute_run --run noney_30m
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ml.physics.geotech import DEFAULT_CLASS_KEY, GEOTECH_CLASSES, get_parameters
from ml.physics.slope_stability import (
    estimate_soil_depth,
    factor_of_safety,
    sensitivity_band,
    stability_class,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WetnessScenario:
    """A named saturation state of the soil profile."""

    key: str
    label: str
    wetness_fraction: float
    description: str


# The fraction is the proportion of the soil profile standing saturated above
# the failure plane. These five span the range from a dry pre-monsoon profile to
# one saturated to the surface by sustained rain.
SCENARIOS: tuple[WetnessScenario, ...] = (
    WetnessScenario("dry", "Dry", 0.0, "Pre-monsoon. No perched water table."),
    WetnessScenario("damp", "Damp", 0.25, "Light or intermittent rain. A shallow wetting front."),
    WetnessScenario("wet", "Wet", 0.5, "Sustained monsoon rain. Half the profile saturated."),
    WetnessScenario(
        "very_wet",
        "Very wet",
        0.75,
        "Prolonged heavy rain on an already wet profile.",
    ),
    WetnessScenario(
        "saturated",
        "Saturated",
        1.0,
        "Saturated to the surface. The condition in which slopes of this kind fail.",
    ),
)


def _sensitivity_summary(
    slope: np.ndarray, soil_depth: np.ndarray, wetness: float = 1.0
) -> dict[str, Any]:
    """How the unstable count moves with material and with regolith thickness."""
    by_material: dict[str, Any] = {}
    for key, p in GEOTECH_CLASSES.items():
        fos = factor_of_safety(
            slope, soil_depth, p.cohesion_kpa, p.friction_angle_deg, p.unit_weight_kn_m3, wetness
        )
        classes = stability_class(fos)
        by_material[key] = {
            "cohesion_kpa": p.cohesion_kpa,
            "friction_angle_deg": p.friction_angle_deg,
            "median_fos": round(float(np.median(fos)), 3),
            "unstable_units": int(np.sum(classes == "unstable")),
            "marginal_units": int(np.sum(classes == "marginal")),
        }

    default = GEOTECH_CLASSES[DEFAULT_CLASS_KEY]
    by_depth: dict[str, Any] = {}
    for depth in (0.5, 1.0, 1.5, 2.0, 3.0, 5.0):
        fos = factor_of_safety(
            slope,
            depth,
            default.cohesion_kpa,
            default.friction_angle_deg,
            default.unit_weight_kn_m3,
            wetness,
        )
        classes = stability_class(fos)
        by_depth[f"{depth:g}m"] = {
            "median_fos": round(float(np.median(fos)), 3),
            "unstable_units": int(np.sum(classes == "unstable")),
        }

    return {
        "wetness_fraction": wetness,
        "note": (
            "Material class and regolith thickness dominate the answer on this terrain, "
            "and neither has been measured for the region. This is why the physics layer "
            "reports a range rather than one factor of safety."
        ),
        "by_material_class": by_material,
        "by_uniform_soil_depth": by_depth,
    }


def compute_for_run(
    slope_units_parquet: Path,
    output_parquet: Path,
    lithology_class: str | None = None,
) -> dict[str, Any]:
    """Compute the factor of safety for every unit, under every scenario."""
    import geopandas as gpd

    frame = gpd.read_parquet(slope_units_parquet)
    if frame.empty:
        raise RuntimeError(f"{slope_units_parquet} contains no slope units")

    params = get_parameters(lithology_class)

    slope = frame["slope_deg"].to_numpy(dtype="float64")
    # A unit with no measured slope cannot be scored. Zero would read as flat
    # and perfectly stable, which is a silent lie, so it stays NaN.
    measured = np.isfinite(slope)

    soil_depth = estimate_soil_depth(np.nan_to_num(slope, nan=0.0))

    report: dict[str, Any] = {
        "run": slope_units_parquet.parent.name,
        "unit_count": len(frame),
        "units_with_measured_slope": int(measured.sum()),
        "lithology_class": params.key,
        "lithology_is_default": params.key == DEFAULT_CLASS_KEY,
        "parameters": {
            "cohesion_kpa": params.cohesion_kpa,
            "friction_angle_deg": params.friction_angle_deg,
            "unit_weight_kn_m3": params.unit_weight_kn_m3,
            "source": params.source,
        },
        "soil_depth_m": {
            "mean": round(float(np.mean(soil_depth)), 3),
            "min": round(float(np.min(soil_depth)), 3),
            "max": round(float(np.max(soil_depth)), 3),
            "method": "terrain proxy, decreasing with gradient; not measured",
        },
        "scenarios": {},
    }

    frame["soil_depth_m"] = soil_depth

    for scenario in SCENARIOS:
        fos = factor_of_safety(
            slope_deg=np.nan_to_num(slope, nan=0.0),
            soil_depth_m=soil_depth,
            cohesion_kpa=params.cohesion_kpa,
            friction_angle_deg=params.friction_angle_deg,
            unit_weight_kn_m3=params.unit_weight_kn_m3,
            wetness_fraction=scenario.wetness_fraction,
        )
        fos = np.where(measured, fos, np.nan)
        column = f"fos_{scenario.key}"
        frame[column] = np.round(fos, 4)

        valid = fos[np.isfinite(fos)]
        classes = stability_class(valid)
        unstable = int(np.sum(classes == "unstable"))
        marginal = int(np.sum(classes == "marginal"))

        report["scenarios"][scenario.key] = {
            "label": scenario.label,
            "wetness_fraction": scenario.wetness_fraction,
            "description": scenario.description,
            "median_fos": round(float(np.median(valid)), 3) if valid.size else None,
            "unstable_units": unstable,
            "marginal_units": marginal,
            "stable_units": int(valid.size - unstable - marginal),
            "unstable_pct": round(100 * unstable / valid.size, 2) if valid.size else None,
        }

    # ------------------------------------------------------------------
    # Which input actually decides the answer.
    #
    # This is the most important output of the physics layer, and it is not a
    # single factor of safety. Run saturated, holding slope and depth fixed,
    # the six material classes disagree completely: colluvium fails almost
    # everywhere while weathered shale holds everywhere. Sweeping soil depth
    # instead moves the count of unstable units from zero to most of the
    # region.
    #
    # So the honest headline is that the material and the regolith thickness
    # dominate this terrain, and we have measured neither. Reporting one
    # confident factor of safety would hide exactly that.
    # ------------------------------------------------------------------
    report["dominant_uncertainty"] = _sensitivity_summary(slope[measured], soil_depth[measured])

    # The uncertainty band is reported for the wet scenario, which is the one an
    # officer would actually be looking at during monsoon.
    low, high = sensitivity_band(
        np.nan_to_num(slope, nan=0.0), soil_depth, params, wetness_fraction=0.5
    )
    frame["fos_wet_low"] = np.round(np.where(measured, low, np.nan), 4)
    frame["fos_wet_high"] = np.round(np.where(measured, high, np.nan), 4)

    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_parquet)

    log.info("physics.computed", extra={"units": len(frame), "output": str(output_parquet)})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ml.physics.compute_run",
        description="Compute the infinite-slope factor of safety for a terrain run.",
    )
    parser.add_argument("--run", default="noney_30m", help="terrain run identifier")
    parser.add_argument("--data-root", default="data", help="pipeline output root")
    parser.add_argument(
        "--lithology",
        default=None,
        help=f"lithology class key; defaults to {DEFAULT_CLASS_KEY}",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    run_dir = Path(args.data_root) / "terrain" / args.run
    report = compute_for_run(
        run_dir / "slope_units.parquet",
        run_dir / "slope_units_physics.parquet",
        args.lithology,
    )
    (run_dir / "physics_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print(f"PHYSICS REPORT  {report['run']}")
    print("=" * 72)
    print(f"  Units scored     {report['units_with_measured_slope']:,} of {report['unit_count']:,}")
    print(
        f"  Lithology        {report['lithology_class']}"
        f"{'  (default, no lithology data yet)' if report['lithology_is_default'] else ''}"
    )
    p = report["parameters"]
    print(
        f"  Parameters       c' {p['cohesion_kpa']} kPa,"
        f" phi' {p['friction_angle_deg']} deg,"
        f" gamma {p['unit_weight_kn_m3']} kN/m3"
    )
    d = report["soil_depth_m"]
    print(f"  Soil depth       {d['min']} to {d['max']} m (mean {d['mean']}), terrain proxy")
    print()
    print(
        f"  {'SCENARIO':<12} {'m':>5} {'MEDIAN FoS':>11} {'UNSTABLE':>10} {'MARGINAL':>10} {'% UNSTABLE':>11}"
    )
    print("  " + "-" * 64)
    for s in report["scenarios"].values():
        print(
            f"  {s['label']:<12} {s['wetness_fraction']:>5.2f} {s['median_fos']:>11.3f}"
            f" {s['unstable_units']:>10,} {s['marginal_units']:>10,} {s['unstable_pct']:>10.2f}%"
        )
    print("=" * 72 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

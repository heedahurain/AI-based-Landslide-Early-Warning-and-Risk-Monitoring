"""Seed the citizen-report moderation queue with demonstrable rows.

The moderation queue is a feature of this project, and a queue holding nothing
demonstrates nothing. These rows exist so the verify and reject actions can be
shown working during a four-minute demo.

Every row written here carries ``demo_seed: true`` and is rendered with a
visible "seed" badge. None of them is a real citizen submission, none is
presented as one, and the flag makes them trivial to filter out. Coordinates
sit inside the Noney and Tupul area of interest so that each one lands on a
real slope unit and can actually be triaged, which is the point of the
exercise; they are plausible locations along the corridor, not surveyed
observations of real cracks.

Run with:  python scripts/seed_reports.py
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

STORE = Path("data/reports/reports.jsonl")

CATEGORY_LABELS = {
    "tension_crack": "Tension crack",
    "slope_bulge": "Slope bulge",
    "debris_flow": "Debris flow",
    "road_damage": "Road damage",
    "retaining_wall": "Retaining wall failure",
    "water_seepage": "Water seepage",
}

# (lat, lon, category, severity, description, reporter, hours_ago)
SEEDS = [
    (
        24.8180,
        93.6420,
        "tension_crack",
        3,
        "Crack about 15 m long opened across the slope above the road after "
        "two nights of heavy rain. Wider than last week.",
        "Village volunteer",
        4,
    ),
    (
        24.7905,
        93.6015,
        "water_seepage",
        2,
        "Water coming out of the cut face roughly 3 m above road level. It was "
        "dry here through the whole of last month.",
        "Road maintenance crew",
        11,
    ),
    (
        24.8640,
        93.5510,
        "slope_bulge",
        4,
        "The ground below the last house on the ridge has pushed outward. "
        "Two families have moved to the community hall.",
        "Ward member",
        20,
    ),
    (
        24.7460,
        93.4880,
        "road_damage",
        3,
        "Half the carriageway has dropped by about 40 cm over a 20 m stretch. "
        "Buses are single-filing past it.",
        None,
        27,
    ),
    (
        24.9310,
        93.7240,
        "debris_flow",
        2,
        "Small debris slide came down the gully and stopped short of the road. "
        "Maybe 3 m of material sitting in the drain.",
        "Schoolteacher",
        39,
    ),
    (
        24.6820,
        93.3350,
        "retaining_wall",
        3,
        "The breast wall below the temple has bulged and one weep hole is running muddy water.",
        "Temple committee",
        52,
    ),
]


def main() -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)

    kept = []
    if STORE.exists():
        for line in STORE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            # Drop anything outside the area of interest, and any previous seed
            # run, so this script is idempotent.
            outside = not (93.2 <= row["longitude"] <= 93.8 and 24.6 <= row["latitude"] <= 25.2)
            if outside:
                print(
                    f"  dropping out-of-area report {row['id'][:8]} at "
                    f"{row['latitude']:.4f}, {row['longitude']:.4f}"
                )
                continue
            if row.get("demo_seed"):
                continue
            kept.append(row)

    now = datetime.now(UTC)
    seeded = []
    for lat, lon, category, severity, description, reporter, hours in SEEDS:
        seeded.append(
            {
                "latitude": lat,
                "longitude": lon,
                "category": category,
                "description": description,
                "severity_self_assessed": severity,
                "reporter_name": reporter,
                "location_accuracy_m": 12.0,
                "id": str(uuid.uuid4()),
                "submitted_at": (now - timedelta(hours=hours)).isoformat(timespec="seconds"),
                "verification_status": "unverified",
                "category_label": CATEGORY_LABELS[category],
                "demo_seed": True,
            }
        )

    rows = kept + seeded
    with STORE.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    print(f"  kept {len(kept)} real report(s), wrote {len(seeded)} seeded row(s)")
    print(
        f"  queue now holds {sum(1 for r in rows if r['verification_status'] == 'unverified')} "
        "awaiting review"
    )


if __name__ == "__main__":
    main()

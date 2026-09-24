"""Citizen hazard reports.

Reports are stored as JSON lines on disk rather than in PostGIS, because the
database is not running in this environment and losing a citizen's report to a
missing dependency would be the wrong trade. The storage layer is deliberately
small and swappable: the API shape does not change when it moves to the
database in Phase 4.

Nothing here classifies an image. The on-device vision model is Phase 8, and a
report is marked `unverified` until a human moderator acts on it.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.problems import ProblemDetailError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

HazardCategory = Literal[
    "tension_crack",
    "slope_bulge",
    "debris_flow",
    "road_damage",
    "retaining_wall",
    "water_seepage",
    "tilted_tree",
    "other",
]

VerificationStatus = Literal["unverified", "verified", "rejected"]

# The pilot area of interest, matching ingest.terrain.regions.NONEY and the
# bounds the terrain model was actually built over. Submissions outside it are
# refused rather than stored: a report the system cannot place against a slope
# unit cannot be triaged, and accepting it silently would put points on the map
# that no computation backs. A test submission from a developer's own machine
# in Bengaluru, roughly 2,000 km away, is exactly the case this prevents.
AOI_BBOX = (93.2, 24.6, 93.8, 25.2)
AOI_NAME = "Noney and Tupul pilot area, Manipur"

CATEGORY_LABELS: dict[str, str] = {
    "tension_crack": "Tension crack",
    "slope_bulge": "Slope bulge",
    "debris_flow": "Debris flow",
    "road_damage": "Road damage",
    "retaining_wall": "Retaining wall failure",
    "water_seepage": "Water seepage",
    "tilted_tree": "Tilted tree or pole",
    "other": "Something else",
}


class ReportIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category: HazardCategory
    description: str = Field(default="", max_length=2000)
    severity_self_assessed: int = Field(default=2, ge=1, le=4)
    reporter_name: str | None = Field(default=None, max_length=120)
    location_accuracy_m: float | None = None


class Report(ReportIn):
    id: str
    submitted_at: str
    verification_status: VerificationStatus
    category_label: str
    # True for rows written by scripts/seed_reports.py to demonstrate the
    # moderation workflow. Surfaced in the interface as a visible badge so a
    # seeded row is never mistaken for a real citizen submission.
    demo_seed: bool = False


def _store() -> Path:
    from app.core.config import get_settings

    path = Path(get_settings().data_root) / "reports" / "reports.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_all() -> list[Report]:
    path = _store()
    if not path.exists():
        return []
    reports: list[Report] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            reports.append(Report(**json.loads(line)))
        except Exception as exc:  # noqa: BLE001 - one bad line must not hide the rest
            log.warning("reports.bad_line", extra={"error": str(exc)})
    return reports


@router.get("", response_model=list[Report])
async def list_reports(
    status: VerificationStatus | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
) -> list[Report]:
    reports = _read_all()
    if status:
        reports = [r for r in reports if r.verification_status == status]
    return sorted(reports, key=lambda r: r.submitted_at, reverse=True)[:limit]


@router.post("", response_model=Report, status_code=201)
async def create_report(payload: ReportIn) -> Report:
    west, south, east, north = AOI_BBOX
    if not (west <= payload.longitude <= east and south <= payload.latitude <= north):
        raise ProblemDetailError(
            status_code=422,
            title="Location outside the monitored area",
            detail=(
                f"This report sits outside the {AOI_NAME}, which spans "
                f"latitude {south} to {north} and longitude {west} to {east}. "
                "ShailSuraksha only holds terrain and slope-stability data for that area, "
                "so a report here could not be matched to a slope or acted on."
            ),
            problem_type="https://shailsuraksha.in/problems/outside-area-of-interest",
        )

    report = Report(
        **payload.model_dump(),
        id=str(uuid.uuid4()),
        submitted_at=datetime.now(UTC).isoformat(timespec="seconds"),
        verification_status="unverified",
        category_label=CATEGORY_LABELS.get(payload.category, payload.category),
    )
    with _store().open("a", encoding="utf-8") as handle:
        handle.write(report.model_dump_json() + "\n")
    log.info("reports.created", extra={"id": report.id, "category": report.category})
    return report


@router.get("/area-of-interest", summary="The bounds within which reports are accepted")
async def area_of_interest() -> dict[str, Any]:
    west, south, east, north = AOI_BBOX
    return {
        "name": AOI_NAME,
        "bbox": {"west": west, "south": south, "east": east, "north": north},
        "note": (
            "Reports outside these bounds are refused, because the terrain model that "
            "would be used to triage them only covers this area."
        ),
    }


@router.post("/{report_id}/verify", response_model=Report)
async def set_status(report_id: str, status: VerificationStatus) -> Report:
    """Moderator decision. Rewrites the file, which is fine at this scale."""
    reports = _read_all()
    matched = next((r for r in reports if r.id == report_id), None)
    if matched is None:
        raise ProblemDetailError(
            status_code=404,
            title="Report not found",
            detail=f"No report with id {report_id}.",
            problem_type="https://shailsuraksha.in/problems/report-not-found",
        )

    matched.verification_status = status
    with _store().open("w", encoding="utf-8") as handle:
        for report in reports:
            handle.write(report.model_dump_json() + "\n")
    return matched


@router.get("/categories")
async def categories() -> dict[str, str]:
    return CATEGORY_LABELS

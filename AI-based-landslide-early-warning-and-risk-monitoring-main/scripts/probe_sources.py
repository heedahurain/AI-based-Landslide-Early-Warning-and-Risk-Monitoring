#!/usr/bin/env python3
"""Probe every upstream data source and print what actually answered.

Run before every demo and before every judging session:

    python scripts/probe_sources.py

Then update the probe date at the top of docs/DATA_SOURCES.md. A source that
has silently changed is worse than a source that is known to be down, and
"where does your data come from" is the first question a judge asks.

Standard library only, on purpose: this must run on a laptop with no virtual
environment activated and no dependencies installed.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime

TIMEOUT_SECONDS = 25
USER_AGENT = "ShailSuraksha/0.1 (SIH26001 data source probe)"

# A point inside Manipur, near the June 2022 Tupul/Noney failure, used as the
# sample coordinate so the probe exercises the region we actually serve.
SAMPLE_LAT = 24.9
SAMPLE_LON = 93.5


@dataclass
class Source:
    key: str
    name: str
    url: str
    # What a healthy answer looks like. Some hosts legitimately return 401 or
    # 403 because they gate data behind a free credential; that is a different
    # state from being unreachable, and the distinction is recorded rather than
    # flattened into "failed".
    expect: tuple[int, ...] = (200,)
    key_gated: tuple[int, ...] = (401, 403)
    note: str = ""


SOURCES: list[Source] = [
    Source(
        "open_meteo_forecast",
        "Open-Meteo Forecast",
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={SAMPLE_LAT}&longitude={SAMPLE_LON}"
        "&hourly=precipitation,rain,precipitation_probability,relative_humidity_2m,"
        "soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,"
        "soil_moisture_9_to_27cm,soil_moisture_27_to_81cm,"
        "soil_temperature_0cm,soil_temperature_6cm,soil_temperature_18cm,soil_temperature_54cm"
        "&forecast_days=3",
        note="Primary live source: forecast rainfall and modelled soil moisture",
    ),
    Source(
        "open_meteo_archive",
        "Open-Meteo ERA5 Archive",
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={SAMPLE_LAT}&longitude={SAMPLE_LON}"
        "&start_date=2022-06-25&end_date=2022-06-30&hourly=precipitation",
        note="Antecedent rainfall history and threshold back-testing",
    ),
    Source(
        "nasa_power",
        "NASA POWER",
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?parameters=PRECTOTCORR&community=AG&longitude={SAMPLE_LON}&latitude={SAMPLE_LAT}"
        "&start=20220620&end=20220630&format=JSON",
        note="Independent daily precipitation cross-check",
    ),
    Source(
        "planetary_computer",
        "Planetary Computer STAC",
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        note="Copernicus DEM, Sentinel-1 RTC, Sentinel-2 L2A, ESA WorldCover",
    ),
    Source(
        "opentopography",
        "OpenTopography",
        "https://portal.opentopography.org/API/globaldem"
        "?demtype=COP30&south=25.5&north=25.6&west=94.0&east=94.1&outputFormat=GTiff",
        note="Secondary DEM path; needs a free API key",
    ),
    Source(
        "overpass",
        "OpenStreetMap Overpass",
        "https://overpass-api.de/api/status",
        note="Road graph, hospitals, schools",
    ),
    Source(
        "datameet",
        "datameet/maps boundaries",
        "https://raw.githubusercontent.com/datameet/maps/master/Country/india-composite.geojson",
        note="Primary admin boundary source",
    ),
    Source(
        "gadm",
        "GADM 4.1",
        "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_IND_2.json.zip",
        note="Fallback boundaries; licence restricts redistribution",
    ),
    Source(
        "bhuvan",
        "Bhuvan (NRSC/ISRO)",
        "https://bhuvan.nrsc.gov.in",
        note="Display-only WMS basemaps",
    ),
    Source(
        "gsi_bhusanket",
        "GSI Bhusanket",
        "https://bhusanket.gsi.gov.in",
        note="Authoritative susceptibility baseline we compare against",
    ),
    Source(
        "gpm_imerg",
        "GPM IMERG (GES DISC)",
        "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/",
        note="Satellite rainfall; data requires an Earthdata login",
    ),
    Source(
        "carto_basemap",
        "CARTO Dark Matter style",
        "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        note="Free dark basemap style",
    ),
    Source(
        "nasa_coolr",
        "NASA COOLR catalogue page",
        "https://catalog.data.gov/dataset/global-landslide-catalog-export",
        note="Historical inventory; the direct API path did not resolve, resolve by hand",
    ),
    Source(
        "nasa_lhasa",
        "NASA LHASA reference model",
        "https://github.com/nasa/lhasa",
        note="Benchmark and citation, not an input; read before defending our approach",
    ),
    Source(
        "gsi_bhukosh",
        "GSI Bhukosh portal",
        "https://bhukosh.gsi.gov.in",
        note="Hosts the 1:50,000 susceptibility map; did not answer on 2026-09-08",
    ),
]


@dataclass
class Result:
    source: Source
    status: str
    http_code: int | None
    latency_ms: int
    detail: str


def _build_contexts() -> list[tuple[ssl.SSLContext, str]]:
    """Return the TLS contexts to try, in order of preference.

    Some machines carry an outdated system trust store, which makes a perfectly
    healthy endpoint look dead. Retrying with the certifi bundle separates
    "this source is down" from "this laptop cannot verify it", and the two
    demand completely different responses.
    """
    contexts = [(ssl.create_default_context(), "system trust store")]
    try:
        import certifi

        contexts.append((ssl.create_default_context(cafile=certifi.where()), "certifi bundle"))
    except ImportError:
        pass
    return contexts


def _attempt(source: Source, context: ssl.SSLContext) -> tuple[str, int | None, str] | None:
    """Try one context. Returns None when the failure is worth retrying."""
    request = urllib.request.Request(source.url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
            code = response.getcode()
            status = "verified" if code in source.expect else "reachable"
            return (status, code, f"HTTP {code}")
    except urllib.error.HTTPError as exc:
        if exc.code in source.key_gated:
            return ("key-required", exc.code, f"HTTP {exc.code}, credential needed")
        return ("unverified", exc.code, f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            return None  # retry with another trust store
        return ("unverified", None, f"{type(exc).__name__}: {exc.reason}")
    except Exception as exc:  # noqa: BLE001 - a probe reports failures, never raises
        return ("unverified", None, type(exc).__name__)


def probe(source: Source) -> Result:
    started = time.perf_counter()
    contexts = _build_contexts()

    for index, (context, label) in enumerate(contexts):
        outcome = _attempt(source, context)
        if outcome is None:
            continue
        status, code, detail = outcome
        elapsed = int((time.perf_counter() - started) * 1000)
        # Flag when the system store failed and a fallback bundle succeeded, so
        # the operator fixes their machine instead of doubting the source.
        if index > 0 and status in {"verified", "reachable"}:
            detail = f"{detail} (via {label}; system trust store is stale)"
        return Result(source, status, code, elapsed, detail)

    elapsed = int((time.perf_counter() - started) * 1000)
    return Result(
        source,
        "tls-untrusted",
        None,
        elapsed,
        "certificate verification failed in every trust store; check the local CA bundle",
    )


COLOURS = {
    "verified": "\033[32m",
    "reachable": "\033[36m",
    "key-required": "\033[33m",
    "unverified": "\033[31m",
}
RESET = "\033[0m"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if any source that should be verified is not",
    )
    args = parser.parse_args()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, SOURCES))

    probed_at = datetime.now(UTC).isoformat(timespec="seconds")

    if args.json:
        print(
            json.dumps(
                {
                    "probed_at": probed_at,
                    "results": [
                        {
                            "key": r.source.key,
                            "name": r.source.name,
                            "status": r.status,
                            "http_code": r.http_code,
                            "latency_ms": r.latency_ms,
                            "detail": r.detail,
                        }
                        for r in results
                    ],
                },
                indent=2,
            )
        )
    else:
        use_colour = sys.stdout.isatty()
        print(f"\nShailSuraksha data source probe — {probed_at}\n")
        print(f"{'SOURCE':<32} {'STATUS':<14} {'LATENCY':>9}  DETAIL")
        print("-" * 88)
        for r in sorted(results, key=lambda r: (r.status, r.source.name)):
            colour = COLOURS.get(r.status, "") if use_colour else ""
            reset = RESET if use_colour else ""
            print(
                f"{r.source.name:<32} {colour}{r.status:<14}{reset} "
                f"{r.latency_ms:>7} ms  {r.detail}"
            )
        print("-" * 88)

        counts: dict[str, int] = {}
        for r in results:
            counts[r.status] = counts.get(r.status, 0) + 1
        summary = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
        print(f"{len(results)} sources probed: {summary}\n")
        print("Update the probe date at the top of docs/DATA_SOURCES.md after a run.\n")

    if args.strict:
        failed = [r for r in results if r.status in {"unverified", "tls-untrusted"}]
        if failed:
            print(f"Unverified: {', '.join(r.source.name for r in failed)}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

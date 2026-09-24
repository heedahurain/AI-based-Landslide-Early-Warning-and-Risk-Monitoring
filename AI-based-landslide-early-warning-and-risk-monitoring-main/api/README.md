# api/

The FastAPI service: REST v1, authentication and role-based access control, the
alert engine with CAP v1.2 generation, and the WebSocket hub.

## Running

The service is part of the compose stack, so `make up` from the repository root
starts it with its dependencies. Interactive documentation is at
http://localhost:8000/docs.

Standalone, for a fast loop:

```bash
PYTHONPATH=api ../.venv/Scripts/python -m uvicorn app.main:app --reload
```

## What exists today (Phase 0)

- `GET /api/v1/health` — liveness only, touches no dependency.
- `GET /api/v1/ready` — readiness, reporting PostgreSQL and Redis separately and
  answering 503 when either is missing.
- `GET /api/v1/meta` — version, phase, covered states, region bounding box and
  the decision-support disclaimer.
- `GET /metrics` — Prometheus.
- RFC 7807 problem details on every error path, and OpenAPI 3.1.

Domain routers arrive with their phases. See `../PROJECT_CONTEXT.md` §16.

## Conventions

- **Errors are part of the contract.** Raise `ProblemDetailError`; never return a
  bare dictionary of error text.
- **Every state-changing action writes an audit row.** Disaster systems live or
  die on accountability, and suppressed alerts are audited alongside issued ones.
- **Readiness reports, it never raises.** A probe that crashes tells an operator
  nothing during an incident.
- **Migrations come from the model.** The database URL is read from settings in
  `alembic/env.py`, so no credential is ever written into a tracked file.

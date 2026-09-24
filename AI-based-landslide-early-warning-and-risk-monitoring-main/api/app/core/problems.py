"""RFC 7807 problem details.

Errors are part of the API contract, not an afterthought. A field officer's
client, an SDMA integration and our own web app all parse the same shape, so
every failure leaves the service as `application/problem+json`.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_CONTENT_TYPE = "application/problem+json"

# Problem types are documented URIs, not opaque strings, so an integrator can
# look up what a failure means.
PROBLEM_BASE = "https://shailsuraksha.in/problems"


class ProblemDetailError(Exception):
    """Raise this anywhere a request cannot be satisfied."""

    def __init__(
        self,
        *,
        status_code: int,
        title: str,
        detail: str,
        problem_type: str = "about:blank",
        **extensions: Any,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.problem_type = problem_type
        self.extensions = extensions
        super().__init__(detail)

    def to_dict(self, instance: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": self.problem_type,
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
            "instance": instance,
        }
        body.update(self.extensions)
        return body


def _response(problem: dict[str, Any], status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=problem,
        media_type=PROBLEM_CONTENT_TYPE,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemDetailError)
    async def _problem_handler(request: Request, exc: ProblemDetailError) -> JSONResponse:
        return _response(exc.to_dict(str(request.url.path)), exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _response(
            {
                "type": "about:blank",
                "title": exc.detail if isinstance(exc.detail, str) else "HTTP error",
                "status": exc.status_code,
                "detail": exc.detail if isinstance(exc.detail, str) else "",
                "instance": str(request.url.path),
            },
            exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _response(
            {
                "type": f"{PROBLEM_BASE}/validation-error",
                "title": "Request validation failed",
                "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "detail": "One or more fields were rejected.",
                "instance": str(request.url.path),
                # The field-level errors are preserved so a client can point a
                # user at the exact input that was wrong.
                "errors": [
                    {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
                    for error in exc.errors()
                ],
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

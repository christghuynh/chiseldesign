"""Error responses: every error is {"error": {"code": "STRING", "message": "..."}}."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.engine import ParamValidationError, TemplateError
from app.models import ErrorBody, ErrorResponse

HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    501: "NOT_IMPLEMENTED",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def not_implemented(task_id: str) -> ApiError:
    """Placeholder for routes whose real handler belongs to a later task."""
    return ApiError(501, "NOT_IMPLEMENTED", f"Not implemented yet (task {task_id})")


def error_response(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
        return error_response(exc.status_code, code, str(exc.detail))

    # Engine failures reach any route that calls the engine (/generate, /edit, exports).
    @app.exception_handler(ParamValidationError)
    async def _invalid_params(_: Request, exc: ParamValidationError) -> JSONResponse:
        return error_response(422, "INVALID_PARAMS", str(exc))

    @app.exception_handler(TemplateError)
    async def _template_error(_: Request, exc: TemplateError) -> JSONResponse:
        return error_response(422, "TEMPLATE_ERROR", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        return error_response(422, "VALIDATION_ERROR", f"{where}: {first['msg']}")

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 500, detail: str = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message


class NotFoundException(AppException):
    def __init__(self, entity: str, entity_id: str = None):
        message = f"{entity} not found"
        if entity_id:
            message += f": {entity_id}"
        super().__init__(message=message, status_code=404)


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request"):
        super().__init__(message=message, status_code=400)


class ConflictException(AppException):
    def __init__(self, message: str = "Conflict"):
        super().__init__(message=message, status_code=409)


class AgentException(AppException):
    def __init__(self, message: str = "Agent analysis failed", detail: str = None):
        super().__init__(message=message, status_code=502, detail=detail)


def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if exc else "An unexpected error occurred",
        },
    )


def app_exception_handler(request: Request, exc: AppException):
    """Handler for custom AppException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "detail": exc.detail,
        },
    )


def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handler for HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "detail": exc.detail,
        },
    )


def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler for request validation errors."""
    errors = exc.errors()
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "detail": errors,
        },
    )


def register_exception_handlers(app):
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

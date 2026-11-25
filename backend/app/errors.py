import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field_errors = field_errors or {}


class MarketAssetNotFound(ApiError):
    def __init__(self) -> None:
        super().__init__(404, "MARKET_ASSET_NOT_FOUND", "行情标的或数据文件不存在")


class NewsNotFound(ApiError):
    def __init__(self) -> None:
        super().__init__(404, "NEWS_NOT_FOUND", "新闻不存在或索引尚未构建完成")


class SummaryNotFound(ApiError):
    def __init__(self) -> None:
        super().__init__(404, "SUMMARY_NOT_FOUND", "资金流摘要不存在")


def error_content(code: str, message: str, field_errors: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "field_errors": field_errors or {},
    }


def _validation_fields(errors: list[dict[str, Any]]) -> dict[str, str]:
    field_errors: dict[str, str] = {}
    for error in errors:
        location = error.get("loc", ())
        field = str(location[-1]) if location else "body"
        message = str(error.get("msg", "参数不合法"))
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        field_errors[field] = message
    return field_errors


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_content(exc.code, exc.message, exc.field_errors),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=error_content(
                "VALIDATION_ERROR",
                "请求参数校验失败",
                _validation_fields(exc.errors()),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_content(f"HTTP_{exc.status_code}", message),
            headers=exc.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database operation failed", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_content("DATABASE_ERROR", "数据库操作失败"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_content("INTERNAL_ERROR", "服务器内部错误"),
        )

"""Shared response helpers for the API layer."""

from datetime import datetime, timezone
from typing import Any, Generic, NoReturn, TypeVar
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel


class APIError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ResponseMeta(BaseModel):
    timestamp: str
    duration_ms: float = 0.0


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: APIError | None = None
    meta: ResponseMeta | None = None


class WSMessage(BaseModel):
    type: str
    data: Any = None
    timestamp: str = ""


ET = ZoneInfo("America/New_York")


def now_iso() -> str:
    return datetime.now(ET).isoformat()


def ok(data: T = None) -> APIResponse[T]:
    return APIResponse(
        success=True,
        data=data,
        meta=ResponseMeta(timestamp=now_iso()),
    )


def err(code: str, message: str, status_code: int = 400, details: dict[str, Any] | None = None) -> NoReturn:
    raise HTTPException(
        status_code=status_code,
        detail=APIResponse(
            success=False,
            error=APIError(code=code, message=message, details=details),
        ).model_dump(),
    )

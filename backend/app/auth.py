from collections.abc import Mapping
from typing import Any

from fastapi import Request

from app.errors import ApiError


def _user_value(user: Any, key: str) -> str | None:
    if isinstance(user, Mapping):
        value = user.get(key)
    else:
        value = getattr(user, key, None)
    return str(value).strip() if value is not None else None


def get_current_operator(request: Request) -> str:
    # 认证中间件负责写入 request.state.current_user；绝不从请求参数或请求体取操作人。
    user = getattr(request.state, "current_user", None)
    operator = None
    if user is not None:
        for key in ("operator", "username", "sub"):
            operator = _user_value(user, key)
            if operator:
                break

    # 项目尚无认证体系时，使用设计允许的显式系统用户标识。
    if not operator:
        operator = getattr(request.app.state, "default_operator", None)
    if not operator or len(operator) > 64:
        raise ApiError(500, "OPERATOR_CONTEXT_INVALID", "登录上下文中的操作人标识无效")
    return operator

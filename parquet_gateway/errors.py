from typing import Any


class GatewayError(Exception):
    """Base class for expected gateway errors."""

    status_code = 400
    code = "gateway_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class AuthError(GatewayError):
    status_code = 401
    code = "auth_error"


class PermissionDenied(GatewayError):
    status_code = 403
    code = "permission_denied"


class BadQuery(GatewayError):
    status_code = 400
    code = "bad_query"


class NotFound(GatewayError):
    status_code = 404
    code = "not_found"

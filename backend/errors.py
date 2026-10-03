"""API error type rendered as the contract's ``{error_code, message}`` envelope."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str, details: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"error_code": self.error_code, "message": self.message}
        if self.details is not None:
            body["details"] = self.details
        return body

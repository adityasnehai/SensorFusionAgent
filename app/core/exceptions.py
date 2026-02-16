from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FusionPipelineError(Exception):
    error_type: str
    message: str
    details: dict[str, Any] | None = None
    status_code: int = 400

    def __str__(self) -> str:
        return self.message

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": "failed",
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details or {},
        }


def build_error_payload(
    error_type: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "error_type": error_type,
        "message": message,
        "details": details or {},
    }

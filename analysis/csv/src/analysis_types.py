"""Type definitions for NBA CSV analysis."""

from typing import TypedDict


class ValidationResult(TypedDict):
    """Result of a validation check."""

    status: str
    message: str
    details: list[str]

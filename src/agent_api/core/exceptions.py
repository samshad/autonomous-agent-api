"""Application-wide exception hierarchy."""

from __future__ import annotations

from fastapi import HTTPException


class AgentAPIException(Exception):
    """
    Base for all application-specific exceptions.
    Carries an HTTP status code so the API layer needs zero branching logic.
    """

    status_code: int = 500

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class EntityNotFoundException(AgentAPIException):
    """Raised when a requested entity does not exist (or must not be revealed). → 404"""

    status_code = 404


class BusinessRuleError(AgentAPIException):
    """Raised when an action violates a domain business rule. → 422"""

    status_code = 422


class OwnershipError(AgentAPIException):
    """
    Raised when a user attempts to act on a resource they do not own.
    Returns 404 deliberately — do not expose resource existence to unauthorised callers.
    """

    status_code = 404


class ConflictError(AgentAPIException):
    """Raised when an action conflicts with current resource state (e.g. duplicate). → 409"""

    status_code = 409


class ToolExecutionError(AgentAPIException):
    """Raised when an external tool or integration call fails unexpectedly. → 500"""

    status_code = 500


def raise_http_from_agent(exc: AgentAPIException) -> None:
    """Convert any AgentAPIException into a FastAPI HTTPException."""
    raise HTTPException(status_code=exc.status_code, detail=exc.message)

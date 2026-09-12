"""Service-layer errors, mapped to Problem Details at the API boundary."""

from __future__ import annotations


class ServiceError(Exception):
    """Raised by the service layer. Carries a stable code the API maps to a status.

    The message is for operators. It is never returned verbatim to a client, because the
    text of a persistence failure describes the schema.
    """

    status: int = 500

    def __init__(self, code: str, message: str, trace_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.trace_id = trace_id


class NotFoundError(ServiceError):
    status = 404

    def __init__(self, what: str, ident: str, trace_id: str | None = None) -> None:
        super().__init__("not_found", f"{what} {ident} not found", trace_id)


class ValidationError(ServiceError):
    status = 400

    def __init__(self, message: str, trace_id: str | None = None) -> None:
        super().__init__("invalid_request", message, trace_id)

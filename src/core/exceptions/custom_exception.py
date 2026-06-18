from src.core.exceptions.base_exception import ApplicationException


class ValidationException(ApplicationException):
    """Raised when input validation fails."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class ResourceNotFound(ApplicationException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class DatabaseException(ApplicationException):
    """Raised when a database operation fails."""

    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class UnauthorizedException(ApplicationException):
    """Raised when user is not authenticated (missing or invalid credentials)."""

    def __init__(self, message: str):
        super().__init__(message, status_code=401)


class ForbiddenException(ApplicationException):
    """Raised when user is authenticated but not authorized to perform an action."""

    def __init__(self, message: str):
        super().__init__(message, status_code=403)


class ConflictException(ApplicationException):
    """Raised when a resource already exists or there's a conflict."""

    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class GmailFetchError(ApplicationException):
    """Raised when an operation to fetch or parse an email from the Gmail API fails.

    This exception acts as a unified wrapper for Google API HttpErrors,
    network transport failures, and internal email parsing errors.
    """

    def __init__(self, message: str, status_code: int = 500):
        # Forward everything cleanly to your base ApplicationException
        super().__init__(message=message, status_code=status_code)

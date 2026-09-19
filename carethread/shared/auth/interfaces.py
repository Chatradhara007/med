"""Authentication abstraction and exception definitions."""

class AuthError(Exception):
    """Base exception for authentication failures."""
    pass


class UnauthorizedError(AuthError):
    """Raised when request lacks valid authentication context."""
    pass

"""
Backend Exceptions

Custom exceptions for search backend errors with detailed context.
"""


class BackendError(Exception):
    """Base exception for all backend errors"""

    def __init__(self, message: str, backend_name: str = None, **kwargs):
        """
        Initialize backend error

        Args:
            message: Error description
            backend_name: Name of backend that failed
            **kwargs: Additional context (e.g., query, error_code, etc.)
        """
        self.message = message
        self.backend_name = backend_name
        self.context = kwargs

        # Build full error message with context
        full_message = message
        if backend_name:
            full_message = f"[{backend_name}] {message}"

        if kwargs:
            context_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
            full_message = f"{full_message} ({context_str})"

        super().__init__(full_message)


class RateLimitError(BackendError):
    """Backend hit rate limit"""
    pass


class BackendUnavailableError(BackendError):
    """Backend service is unavailable"""
    pass


class InsufficientResultsError(BackendError):
    """Backend returned too few results"""

    def __init__(
        self,
        message: str,
        backend_name: str = None,
        results_count: int = 0,
        min_required: int = 1,
        **kwargs
    ):
        """
        Initialize insufficient results error

        Args:
            message: Error description
            backend_name: Name of backend
            results_count: Number of results returned
            min_required: Minimum results required
            **kwargs: Additional context
        """
        super().__init__(
            message=message,
            backend_name=backend_name,
            results_count=results_count,
            min_required=min_required,
            **kwargs
        )


class AuthenticationError(BackendError):
    """Backend authentication failed (missing/invalid API key)"""
    pass


class TimeoutError(BackendError):
    """Backend request timed out"""

    def __init__(
        self,
        message: str,
        backend_name: str = None,
        timeout_seconds: int = None,
        **kwargs
    ):
        """
        Initialize timeout error

        Args:
            message: Error description
            backend_name: Name of backend
            timeout_seconds: Timeout duration
            **kwargs: Additional context
        """
        super().__init__(
            message=message,
            backend_name=backend_name,
            timeout_seconds=timeout_seconds,
            **kwargs
        )

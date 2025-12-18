"""
Retry logic with exponential backoff for handling rate limits and transient errors.
"""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Exception raised when API rate limit is exceeded (429)."""
    pass


class TransientError(Exception):
    """Exception raised for transient errors that should be retried."""
    pass


def create_retry_decorator(max_attempts: int = 3, min_wait: int = 1, max_wait: int = 10):
    """
    Create a retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
    
    Returns:
        Retry decorator configured with exponential backoff
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type((RateLimitError, TransientError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )


# Default retry decorator for API calls
retry_with_backoff = create_retry_decorator(max_attempts=3, min_wait=1, max_wait=10)


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error should be retried.
    
    Args:
        error: The exception to check
    
    Returns:
        True if the error should be retried, False otherwise
    """
    # Check for rate limit errors (429)
    error_str = str(error).lower()
    if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
        return True
    
    # Check for transient errors
    transient_indicators = [
        "timeout",
        "connection",
        "temporarily unavailable",
        "service unavailable",
        "502",
        "503",
        "504",
    ]
    
    return any(indicator in error_str for indicator in transient_indicators)

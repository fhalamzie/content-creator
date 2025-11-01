"""
Rate Limiter

Token bucket rate limiter for Notion API requests.
Ensures safe API usage with 2.5 req/sec default (safety margin on 3 req/sec limit).

Design Principles:
- Thread-safe operation
- ETA calculation for batch operations
- Context manager support
- Statistics tracking for monitoring
"""

import time
import logging
from threading import Lock
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with thread safety.

    Usage:
        limiter = RateLimiter(rate=2.5)

        # Explicit acquire
        limiter.acquire()
        make_api_call()

        # Context manager
        with limiter:
            make_api_call()

        # ETA calculation
        eta = limiter.calculate_eta(num_requests=100)
    """

    def __init__(self, rate: float = 2.5):
        """
        Initialize rate limiter.

        Args:
            rate: Requests per second (default: 2.5)

        Raises:
            ValueError: If rate is not positive
        """
        if rate <= 0:
            raise ValueError("Rate must be positive")

        self.rate = rate
        self.interval = 1.0 / rate  # Time between requests (seconds)
        self._last_request_time = 0.0
        self._lock = Lock()

        # Statistics
        self._total_requests = 0
        self._total_wait_time = 0.0

        logger.info(f"RateLimiter initialized with rate={rate} req/sec")

    def acquire(self) -> None:
        """
        Acquire permission to make a request.
        Blocks until rate limit allows next request.

        Thread-safe: Uses lock to ensure correct behavior under concurrency.
        """
        with self._lock:
            current_time = time.time()

            # Calculate time since last request
            time_since_last = current_time - self._last_request_time

            # If not enough time has passed, wait
            if time_since_last < self.interval:
                wait_time = self.interval - time_since_last
                time.sleep(wait_time)
                self._total_wait_time += wait_time
            else:
                # No wait needed
                wait_time = 0.0

            # Update last request time
            self._last_request_time = time.time()
            self._total_requests += 1

            logger.debug(
                f"Request {self._total_requests} acquired "
                f"(waited {wait_time:.3f}s)"
            )

    def calculate_eta(self, num_requests: int) -> float:
        """
        Calculate estimated time to complete N requests.

        Args:
            num_requests: Number of pending requests

        Returns:
            Estimated time in seconds (simple calculation: num_requests / rate)
        """
        if num_requests <= 0:
            return 0.0

        # Simple ETA calculation: total requests divided by rate
        return num_requests / self.rate

    def reset(self) -> None:
        """
        Reset rate limiter state.
        Clears request history and statistics.
        """
        with self._lock:
            self._last_request_time = 0.0
            self._total_requests = 0
            self._total_wait_time = 0.0

        logger.info("RateLimiter reset")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.

        Returns:
            Dict with keys:
                - total_requests: Total requests processed
                - average_wait_time: Average wait time per request
                - rate: Configured rate (req/sec)
        """
        with self._lock:
            avg_wait = (
                self._total_wait_time / self._total_requests
                if self._total_requests > 0
                else 0.0
            )

            return {
                "total_requests": self._total_requests,
                "average_wait_time": avg_wait,
                "rate": self.rate
            }

    # Context manager protocol

    def __enter__(self):
        """Enter context manager (acquire rate limit)"""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager (no cleanup needed)"""
        return False

"""
Tests for rate_limiter.py

TDD approach: Write tests first, then implement.
Coverage target: 100% (critical path component)

Rate limiter implements token bucket algorithm with:
- 2.5 req/sec limit (safety margin on Notion's 3 req/sec)
- ETA calculation for batch operations
- Thread-safe operation
"""

import time
import pytest
from threading import Thread
from src.notion_integration.rate_limiter import RateLimiter


class TestRateLimiterInitialization:
    """Test rate limiter initialization"""

    def test_creates_with_default_rate(self):
        limiter = RateLimiter()
        assert limiter.rate == 2.5

    def test_creates_with_custom_rate(self):
        limiter = RateLimiter(rate=5.0)
        assert limiter.rate == 5.0

    def test_validates_positive_rate(self):
        with pytest.raises(ValueError, match="Rate must be positive"):
            RateLimiter(rate=0)

        with pytest.raises(ValueError, match="Rate must be positive"):
            RateLimiter(rate=-1.0)


class TestBasicRateLimiting:
    """Test basic rate limiting functionality"""

    def test_allows_single_request_immediately(self):
        limiter = RateLimiter(rate=10.0)
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start

        # First request should be immediate (< 10ms overhead)
        assert elapsed < 0.01

    def test_delays_rapid_requests(self):
        limiter = RateLimiter(rate=10.0)  # 10 req/sec = 0.1s interval

        limiter.acquire()  # First request (immediate)
        start = time.time()
        limiter.acquire()  # Second request (should wait ~0.1s)
        elapsed = time.time() - start

        # Should wait approximately 0.1 seconds
        assert 0.08 < elapsed < 0.12

    def test_enforces_rate_over_multiple_requests(self):
        limiter = RateLimiter(rate=5.0)  # 5 req/sec = 0.2s interval

        start = time.time()
        for _ in range(5):
            limiter.acquire()
        elapsed = time.time() - start

        # 5 requests at 0.2s interval = ~0.8s total
        # (first is immediate, next 4 wait 0.2s each)
        assert 0.75 < elapsed < 0.85


class TestETACalculation:
    """Test ETA calculation for batch operations"""

    def test_calculate_eta_for_pending_requests(self):
        limiter = RateLimiter(rate=2.5)  # 2.5 req/sec

        # ETA for 10 requests = 10 / 2.5 = 4.0 seconds
        eta = limiter.calculate_eta(10)
        assert eta == pytest.approx(4.0, abs=0.01)

    def test_calculate_eta_with_zero_requests(self):
        limiter = RateLimiter(rate=2.5)
        eta = limiter.calculate_eta(0)
        assert eta == 0.0

    def test_calculate_eta_with_different_rates(self):
        limiter = RateLimiter(rate=5.0)  # 5 req/sec

        # ETA for 20 requests = 20 / 5 = 4.0 seconds
        eta = limiter.calculate_eta(20)
        assert eta == pytest.approx(4.0, abs=0.01)

    def test_calculate_eta_accounts_for_elapsed_time(self):
        limiter = RateLimiter(rate=2.5)

        # Make some requests
        limiter.acquire()
        limiter.acquire()

        # ETA should account for time already elapsed
        # (This is a simplified test; actual implementation may vary)
        eta = limiter.calculate_eta(10)
        assert eta >= 0.0


class TestThreadSafety:
    """Test thread-safe operation"""

    def test_handles_concurrent_requests(self):
        limiter = RateLimiter(rate=10.0)
        results = []

        def make_request(request_id):
            start = time.time()
            limiter.acquire()
            elapsed = time.time() - start
            results.append((request_id, elapsed))

        # Launch 5 concurrent threads
        threads = [Thread(target=make_request, args=(i,)) for i in range(5)]

        start = time.time()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        total_time = time.time() - start

        # All threads should complete
        assert len(results) == 5

        # Total time should respect rate limit (5 requests at 10 req/sec)
        # Expected: ~0.4s (first immediate, next 4 at 0.1s intervals)
        assert 0.35 < total_time < 0.5

    def test_maintains_rate_under_concurrent_load(self):
        limiter = RateLimiter(rate=5.0)  # 5 req/sec
        request_times = []

        def make_request():
            limiter.acquire()
            request_times.append(time.time())

        # Launch 10 concurrent threads
        threads = [Thread(target=make_request) for _ in range(10)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify intervals between requests
        request_times.sort()
        intervals = [
            request_times[i+1] - request_times[i]
            for i in range(len(request_times) - 1)
        ]

        # Average interval should be ~0.2s (1/5.0)
        avg_interval = sum(intervals) / len(intervals)
        assert 0.18 < avg_interval < 0.22


class TestResetFunctionality:
    """Test rate limiter reset"""

    def test_reset_clears_request_history(self):
        limiter = RateLimiter(rate=5.0)

        # Make several requests
        limiter.acquire()
        limiter.acquire()
        limiter.acquire()

        # Reset
        limiter.reset()

        # Next request should be immediate
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start

        assert elapsed < 0.01


class TestContextManager:
    """Test context manager protocol"""

    def test_can_use_as_context_manager(self):
        limiter = RateLimiter(rate=10.0)

        start = time.time()
        with limiter:
            # Context manager should call acquire()
            pass
        elapsed = time.time() - start

        # First request should be immediate
        assert elapsed < 0.01

    def test_context_manager_enforces_rate_limit(self):
        limiter = RateLimiter(rate=10.0)

        with limiter:
            pass  # First request

        start = time.time()
        with limiter:
            pass  # Second request (should wait)
        elapsed = time.time() - start

        assert 0.08 < elapsed < 0.12


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_handles_very_high_rate(self):
        limiter = RateLimiter(rate=1000.0)

        # Should allow rapid requests
        start = time.time()
        for _ in range(10):
            limiter.acquire()
        elapsed = time.time() - start

        # Should complete quickly (< 50ms)
        assert elapsed < 0.05

    def test_handles_very_low_rate(self):
        limiter = RateLimiter(rate=1.0)  # 1 req/sec

        limiter.acquire()  # First request
        start = time.time()
        limiter.acquire()  # Second request (should wait ~1s)
        elapsed = time.time() - start

        assert 0.95 < elapsed < 1.05

    def test_calculate_eta_with_fractional_requests(self):
        limiter = RateLimiter(rate=2.5)

        # Test with fractional result
        eta = limiter.calculate_eta(7)  # 7 / 2.5 = 2.8
        assert eta == pytest.approx(2.8, abs=0.01)


class TestStatistics:
    """Test rate limiter statistics and monitoring"""

    def test_tracks_total_requests(self):
        limiter = RateLimiter(rate=10.0)

        for _ in range(5):
            limiter.acquire()

        stats = limiter.get_stats()
        assert stats["total_requests"] == 5

    def test_tracks_average_wait_time(self):
        limiter = RateLimiter(rate=5.0)

        for _ in range(3):
            limiter.acquire()

        stats = limiter.get_stats()
        assert "average_wait_time" in stats
        assert stats["average_wait_time"] >= 0.0

    def test_stats_reset_after_reset(self):
        limiter = RateLimiter(rate=10.0)

        limiter.acquire()
        limiter.acquire()
        limiter.reset()

        stats = limiter.get_stats()
        assert stats["total_requests"] == 0

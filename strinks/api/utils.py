import time
from collections import defaultdict
from datetime import datetime
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter, Retry

JST = ZoneInfo("Asia/Tokyo")


def now_jst() -> datetime:
    """Get current datetime in JST timezone."""
    return datetime.now(tz=JST)


class RateLimitedSession(requests.Session):
    """Session with rate limiting per domain."""

    def __init__(self, default_rate_limit: float = 1.0, **kwargs: Any):
        """Initialize session with rate limiting.

        Args:
            default_rate_limit: Default seconds between requests per domain
            **kwargs: Additional arguments for requests.Session
        """
        super().__init__(**kwargs)
        self.default_rate_limit = default_rate_limit
        self.domain_limits: dict[str, float] = {}
        self.last_request_times: dict[str, float] = defaultdict(float)
        self._lock = Lock()

    def set_domain_limit(self, domain: str, rate_limit: float) -> None:
        """Set rate limit for a specific domain.

        Args:
            domain: Domain name (e.g., 'api.untappd.com')
            rate_limit: Seconds between requests
        """
        self.domain_limits[domain] = rate_limit

    def _get_domain(self, url: str | bytes) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse

        url_str = url.decode() if isinstance(url, bytes) else url
        parsed = urlparse(url_str)
        return parsed.netloc

    def _wait_if_needed(self, domain: str) -> None:
        """Wait if rate limit requires it."""
        with self._lock:
            rate_limit = self.domain_limits.get(domain, self.default_rate_limit)
            if rate_limit <= 0:
                return

            last_request = self.last_request_times[domain]
            now = time.time()
            time_since_last = now - last_request
            wait_time = rate_limit - time_since_last

            if wait_time > 0:
                time.sleep(wait_time)

            self.last_request_times[domain] = time.time()

    def request(
        self,
        method: str | bytes,
        url: str | bytes,
        *args: Any,
        **kwargs: Any,
    ) -> requests.Response:
        """Make request with rate limiting."""
        domain = self._get_domain(url)
        self._wait_if_needed(domain)
        return super().request(method, url, *args, **kwargs)


def get_retrying_session(
    max_retries: int = 3,
    rate_limit: float = 0.5,
    domain_limits: dict[str, float] | None = None,
) -> RateLimitedSession:
    """Create a session with retry logic and rate limiting.

    Args:
        max_retries: Maximum number of retries for failed requests
        rate_limit: Default seconds between requests per domain
        domain_limits: Optional per-domain rate limits

    Returns:
        RateLimitedSession with configured retry and rate limiting
    """
    sess = RateLimitedSession(default_rate_limit=rate_limit)

    # Configure retries
    retries = Retry(
        total=max_retries,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)

    # Set domain-specific limits if provided
    if domain_limits:
        for domain, limit in domain_limits.items():
            sess.set_domain_limit(domain, limit)

    return sess

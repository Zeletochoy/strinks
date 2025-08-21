"""Async utilities for network operations."""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast
from urllib.parse import urlparse

import aiohttp
import cloudscraper


class RateLimiter:
    """Rate limiter with configurable delay."""

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def wait_if_needed(self) -> None:
        """Wait if rate limit requires it."""
        async with self._lock:
            now = time.time()
            time_since_last = now - self.last_request_time
            wait_time = self.delay - time_since_last

            if wait_time > 0:
                await asyncio.sleep(wait_time)

            self.last_request_time = time.time()


# Global Untappd rate limiter shared across all async tasks
_untappd_rate_limiter = RateLimiter(1.0)  # 1 second delay for Untappd

# Domain-specific rate limiters to avoid 429 errors
_domain_rate_limiters: dict[str, RateLimiter] = {}


class DomainRateLimiter:
    """Automatic rate limiter that adapts to 429 responses."""

    def __init__(self) -> None:
        self.limiters: dict[str, RateLimiter] = {}
        self.delays: dict[str, float] = {}  # Domain -> delay in seconds
        self.semaphores: dict[str, asyncio.Semaphore] = {}  # Domain -> concurrent request limit

    def get_limiter(self, domain: str, url: str = "") -> RateLimiter | None:
        """Get rate limiter for domain if it needs one.

        Args:
            domain: The domain to check
            url: Optional full URL to check for special cases like oembed
        """
        # Oembed endpoints have stricter rate limits
        if ".oembed" in url and domain not in self.delays:
            if domain not in self.limiters:
                self.limiters[domain] = RateLimiter(1.0)  # 1 second delay for oembed
            return self.limiters[domain]

        if domain in self.delays:
            if domain not in self.limiters:
                self.limiters[domain] = RateLimiter(self.delays[domain])
            return self.limiters[domain]
        return None

    def get_semaphore(self, domain: str) -> asyncio.Semaphore:
        """Get semaphore for domain to limit concurrent requests.

        Always returns a semaphore with max concurrency of 1 to prevent
        multiple parallel scrapers from hitting the same domain simultaneously.
        """
        if domain not in self.semaphores:
            self.semaphores[domain] = asyncio.Semaphore(1)
        return self.semaphores[domain]

    def add_rate_limit(self, domain: str, delay: float = 1.0):
        """Mark a domain as needing rate limiting."""
        self.delays[domain] = max(self.delays.get(domain, 0), delay)


_domain_limiter = DomainRateLimiter()


def get_async_session(timeout: int = 60) -> aiohttp.ClientSession:
    """Create an async HTTP session.

    Args:
        timeout: Request timeout in seconds (default 60)

    Returns:
        aiohttp.ClientSession configured with timeout
    """
    timeout_obj = aiohttp.ClientTimeout(total=timeout)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    return aiohttp.ClientSession(timeout=timeout_obj, headers=headers)


async def _fetch_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    retries: int = 3,
    **kwargs: Any,
) -> aiohttp.ClientResponse:
    """Internal function to fetch URL with retry logic and return response.

    Args:
        session: aiohttp session to use
        url: URL to fetch
        retries: Number of retries on timeout
        **kwargs: Additional arguments for session.get()

    Returns:
        aiohttp.ClientResponse object (must be used within context manager)
    """
    domain = urlparse(url).netloc

    # Get semaphore for domain to limit concurrent requests (max 1 per domain)
    semaphore = _domain_limiter.get_semaphore(domain)

    async with semaphore:
        for attempt in range(retries):
            # Apply rate limiting if this domain needs it
            limiter = _domain_limiter.get_limiter(domain, url)
            if limiter:
                await limiter.wait_if_needed()

            try:
                response = await session.get(url, **kwargs)
                response.raise_for_status()
                return response

            except aiohttp.ClientResponseError as e:
                if e.status == 429:  # Too Many Requests
                    # Automatically add rate limiting for this domain
                    _domain_limiter.add_rate_limit(domain, 1.0)
                    if attempt < retries - 1:
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                        continue
                raise
            except (TimeoutError, aiohttp.ClientError):
                if attempt < retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue
                raise
    # Should never reach here, but mypy needs this
    raise RuntimeError("Retry loop exited unexpectedly")


async def fetch_text(
    session: aiohttp.ClientSession,
    url: str,
    retries: int = 3,
    **kwargs: Any,
) -> str:
    """Fetch URL and return text.

    Args:
        session: aiohttp session to use
        url: URL to fetch
        retries: Number of retries on timeout
        **kwargs: Additional arguments for session.get()

    Returns:
        Response text
    """
    async with await _fetch_with_retry(session, url, retries, **kwargs) as response:
        # Try to detect encoding from response
        encoding = response.charset
        if not encoding:
            # Try to detect from content-type header
            content_type = response.headers.get("content-type", "")
            encoding = content_type.split("charset=")[-1].strip() if "charset=" in content_type else "utf-8"

        # Handle text decoding with fallback
        try:
            return await response.text(encoding=encoding)
        except UnicodeDecodeError:
            # Fallback to UTF-8 if the detected encoding fails
            content = await response.read()
            return content.decode("utf-8", errors="ignore")


async def fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    retries: int = 3,
    **kwargs: Any,
) -> dict:
    """Fetch URL and return JSON.

    Args:
        session: aiohttp session to use
        url: URL to fetch
        retries: Number of retries on timeout
        **kwargs: Additional arguments for session.get()

    Returns:
        Response JSON as dict
    """
    async with await _fetch_with_retry(session, url, retries, **kwargs) as response:
        try:
            return cast(dict[Any, Any], await response.json())
        except aiohttp.ContentTypeError:
            # Some APIs return valid JSON with wrong content-type (e.g., text/javascript)
            text = await response.text()
            return cast(dict[Any, Any], json.loads(text))


async def fetch_bytes(
    session: aiohttp.ClientSession,
    url: str,
    retries: int = 3,
    **kwargs: Any,
) -> bytes:
    """Fetch URL and return bytes.

    Args:
        session: aiohttp session to use
        url: URL to fetch
        retries: Number of retries on timeout
        **kwargs: Additional arguments for session.get()

    Returns:
        Response bytes
    """
    async with await _fetch_with_retry(session, url, retries, **kwargs) as response:
        return await response.read()


async def fetch_untappd(
    session: aiohttp.ClientSession,
    url: str,
    **kwargs: Any,
) -> dict:
    """Fetch from Untappd API with rate limiting (1 req/sec).

    Args:
        session: aiohttp session to use
        url: URL to fetch
        **kwargs: Additional arguments for session.get()

    Returns:
        Response JSON as dict
    """
    await _untappd_rate_limiter.wait_if_needed()
    async with session.get(url, **kwargs) as response:
        response.raise_for_status()
        return cast(dict[Any, Any], await response.json())


# Thread pool for synchronous cloudscraper operations
_executor = ThreadPoolExecutor(max_workers=4)
_scraper = cloudscraper.create_scraper()


async def fetch_cloudflare_protected(
    url: str, params: dict[str, str] | None = None, headers: dict[str, str] | None = None
) -> str:
    """Fetch URL protected by Cloudflare using cloudscraper.

    Args:
        url: URL to fetch
        params: Optional query parameters
        headers: Optional headers dict

    Returns:
        Response text
    """
    loop = asyncio.get_event_loop()
    # Run the synchronous cloudscraper in a thread pool
    kwargs = {}
    if params:
        kwargs["params"] = params
    if headers:
        kwargs["headers"] = headers
    response = await loop.run_in_executor(_executor, lambda: _scraper.get(url, **kwargs))
    response.raise_for_status()
    return cast(str, response.text)

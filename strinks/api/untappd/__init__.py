import asyncio
import logging
from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta

import aiohttp

from ...db import get_db
from ..shops import ShopBeer
from ..utils import now_jst
from .api import UntappdAPI
from .auth import UNTAPPD_OAUTH_URL, UserInfo, untappd_get_oauth_token, untappd_get_user_info
from .cache import CacheStatus, UntappdSQLiteCache
from .structs import RateLimitError, UntappdBeerResult, UntappdBreweryResult, UserRating
from .web import UntappdWeb

logger = logging.getLogger("untappd")

MIN_SECS_BETWEEN_RESTARTS = 300  # 5min
BEER_CACHE_TIME = timedelta(days=30)


class UntappdClient:
    def __init__(self, session: aiohttp.ClientSession, *backends: UntappdAPI | UntappdWeb):
        self.session = session
        self.db = get_db()
        self.cache = UntappdSQLiteCache(self.db, cache_duration=BEER_CACHE_TIME)
        self.init_backends(backends)

    def init_backends(self, backends: Sequence[UntappdAPI | UntappdWeb]):
        self.backends = backends or [
            *[
                UntappdAPI(self.session, auth_token=token) for token in self.db.get_access_tokens(is_app=True)
            ],  # App user tokens
            UntappdAPI(self.session),  # Strinks app credentials
            *[
                UntappdAPI(self.session, auth_token=token) for token in self.db.get_access_tokens(is_app=False)
            ],  # User tokens
            UntappdWeb(),  # Web scraper
        ]
        logger.info(f"Untappd backends: {self.backends}")
        self.backend_idx = 0
        self.last_time_at_first = now_jst()

    @property
    def current_backend(self) -> UntappdAPI | UntappdWeb:
        return self.backends[self.backend_idx]

    async def next_backend(self, index: int | None = None) -> None:
        self.backend_idx = (self.backend_idx + 1) % len(self.backends)
        logger.debug(f"Switching Untappd backend to {self.current_backend}")
        if self.backend_idx == 0:
            elapsed = (now_jst() - self.last_time_at_first).total_seconds()
            if elapsed < MIN_SECS_BETWEEN_RESTARTS:
                logger.warning("Went through all backends too fast, waiting a bit...")
                await asyncio.sleep(MIN_SECS_BETWEEN_RESTARTS - elapsed)
            self.last_time_at_first = now_jst()

    async def _query_beer(self, query: str) -> UntappdBeerResult | None:
        if (now_jst() - self.last_time_at_first).total_seconds() > 3600:  # rate limit resets every hour
            self.backend_idx = 0
            self.last_time_at_first = now_jst()
        while True:
            try:
                return await self.current_backend.try_find_beer(query)
            except RateLimitError:
                await self.next_backend()

    async def try_find_beer(self, beer: ShopBeer) -> tuple[UntappdBeerResult, str] | None:
        """Returns result and used query if found or None otherwise"""
        if (now_jst() - self.last_time_at_first).total_seconds() > 3600:  # rate limit resets every hour
            self.backend_idx = 0
            self.last_time_at_first = now_jst()
        for query in beer.iter_untappd_queries():
            # Check cache
            beer_id, status = self.cache.get(query)

            match status:
                case CacheStatus.HIT:
                    # Found in cache and valid
                    if beer_id is None:
                        # Was searched but not found on Untappd
                        continue
                    # Get full beer details from API
                    while True:
                        try:
                            return await self.current_backend.get_beer_from_id(beer_id), query
                        except RateLimitError:
                            await self.next_backend()

                case CacheStatus.MISS | CacheStatus.EXPIRED:
                    # Not in cache or expired, query API
                    res = await self._query_beer(query)
                    # Cache the result (beer_id can be None if not found)
                    self.cache.set(query, res.beer_id if res else None)
                    if res is not None:
                        return res, query
        return None

    async def search_breweries(self, query: str) -> list[UntappdBreweryResult]:
        """Search for breweries with automatic backend rotation on rate limit."""
        if (now_jst() - self.last_time_at_first).total_seconds() > 3600:  # rate limit resets every hour
            self.backend_idx = 0
            self.last_time_at_first = now_jst()

        while True:
            try:
                # Only UntappdAPI supports brewery search, not UntappdWeb
                if isinstance(self.current_backend, UntappdAPI):
                    return await self.current_backend.search_breweries(query)
                # Skip web backend for brewery search
                await self.next_backend()
                if self.backend_idx == 0:
                    # Went through all backends, none support brewery search
                    return []
            except RateLimitError:
                await self.next_backend()

    def iter_had_beers(
        self, user_id: int | None = None, from_time: datetime | None = None
    ) -> Iterator[tuple[UntappdBeerResult, UserRating]]:
        # TODO: multiple backends?
        if isinstance(self.current_backend, UntappdAPI):
            yield from self.current_backend.iter_had_beers(user_id=user_id, from_time=from_time)
        # UntappdWeb doesn't support authenticated endpoints


__all__ = [
    "UNTAPPD_OAUTH_URL",
    "UntappdBeerResult",
    "UntappdClient",
    "UserInfo",
    "untappd_get_oauth_token",
    "untappd_get_user_info",
]

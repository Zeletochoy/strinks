import time
from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta

from ...db import get_db
from ..shops import ShopBeer
from ..utils import now_jst
from .api import UntappdAPI
from .auth import UNTAPPD_OAUTH_URL, UserInfo, untappd_get_oauth_token, untappd_get_user_info
from .cache import CacheStatus, UntappdSQLiteCache
from .structs import RateLimitError, UntappdBeerResult, UserRating
from .web import UntappdWeb

MIN_SECS_BETWEEN_RESTARTS = 300  # 5min
BEER_CACHE_TIME = timedelta(days=30)


class UntappdClient:
    def __init__(self, *backends: UntappdAPI | UntappdWeb):
        self.db = get_db()
        self.cache = UntappdSQLiteCache(self.db, cache_duration=BEER_CACHE_TIME)
        self.init_backends(backends)

    def init_backends(self, backends: Sequence[UntappdAPI | UntappdWeb]):
        self.backends = backends or [
            *[UntappdAPI(auth_token=token) for token in self.db.get_access_tokens(is_app=True)],  # App user tokens
            UntappdAPI(),  # Strinks app credentials
            *[UntappdAPI(auth_token=token) for token in self.db.get_access_tokens(is_app=False)],  # User tokens
            UntappdWeb(),  # Web scraper
        ]
        print(f"Untappd backends: {self.backends}")
        self.backend_idx = 0
        self.last_time_at_first = now_jst()

    @property
    def current_backend(self) -> UntappdAPI | UntappdWeb:
        return self.backends[self.backend_idx]

    def next_backend(self, index: int | None = None) -> None:
        self.backend_idx = (self.backend_idx + 1) % len(self.backends)
        print(f"Switching Untappd backend to {self.current_backend}")
        if self.backend_idx == 0:
            elapsed = (now_jst() - self.last_time_at_first).total_seconds()
            if elapsed < MIN_SECS_BETWEEN_RESTARTS:
                print("Went through all backends too fast, waiting a bit...")
                time.sleep(MIN_SECS_BETWEEN_RESTARTS - elapsed)
            self.last_time_at_first = now_jst()

    def _query_beer(self, query: str) -> UntappdBeerResult | None:
        if (now_jst() - self.last_time_at_first).total_seconds() > 3600:  # rate limit resets every hour
            self.backend_idx = 0
            self.last_time_at_first = now_jst()
        while True:
            try:
                return self.current_backend.try_find_beer(query)
            except RateLimitError:
                self.next_backend()

    def try_find_beer(self, beer: ShopBeer) -> tuple[UntappdBeerResult, str] | None:
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
                            return self.current_backend.get_beer_from_id(beer_id), query
                        except RateLimitError:
                            self.next_backend()

                case CacheStatus.MISS | CacheStatus.EXPIRED:
                    # Not in cache or expired, query API
                    res = self._query_beer(query)
                    # Cache the result (beer_id can be None if not found)
                    self.cache.set(query, res.beer_id if res else None)
                    if res is not None:
                        return res, query
        return None

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

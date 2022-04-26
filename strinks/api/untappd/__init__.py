import atexit
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterator, NamedTuple, Optional, Sequence, Tuple, Union

from ...db import get_db
from ..shops import ShopBeer
from .api import UntappdAPI
from .auth import UNTAPPD_OAUTH_URL, UserInfo, untappd_get_oauth_token, untappd_get_user_info
from .structs import RateLimitError, UntappdBeerResult, UserRating
from .web import UntappdWeb


CACHE_PATH = Path(__file__).with_name("untappd_cache.json")
MIN_SECS_BETWEEN_RESTARTS = 300  # 5min
BEER_CACHE_TIME = timedelta(days=30)


class UntappdCacheEntry(NamedTuple):
    beer_id: Optional[int]
    timestamp: int


class UntappdClient:
    def __init__(self, *backends: Union[UntappdAPI, UntappdWeb]):
        try:
            with open(CACHE_PATH) as f:
                json_cache = json.load(f)
            self.cache: Dict[str, UntappdCacheEntry] = {
                query: UntappdCacheEntry(*res) for query, res in json_cache.items()
            }
        except Exception:
            self.cache = {}
        self.init_backends(backends)
        atexit.register(self.save_cache, verbose=True)

    def init_backends(self, backends: Sequence[Union[UntappdAPI, UntappdWeb]]):
        db = get_db()
        self.backends = backends or [
            *[UntappdAPI(auth_token=token) for token in db.get_access_tokens(is_app=True)],  # App user tokens
            UntappdAPI(),  # Strinks app credentials
            *[UntappdAPI(auth_token=token) for token in db.get_access_tokens(is_app=False)],  # User tokens
            UntappdWeb(),  # Web scraper
        ]
        print(f"Untappd backends: {self.backends}")
        self.backend_idx = 0
        self.last_time_at_first = datetime.now()

    @property
    def current_backend(self):
        return self.backends[self.backend_idx]

    def next_backend(self, index: Optional[int] = None) -> None:
        self.backend_idx = (self.backend_idx + 1) % len(self.backends)
        print(f"Switching Untappd backend to {self.current_backend}")
        if self.backend_idx == 0:
            elapsed = (datetime.now() - self.last_time_at_first).total_seconds()
            if elapsed < MIN_SECS_BETWEEN_RESTARTS:
                print("Went through all backends too fast, waiting a bit...")
                time.sleep(MIN_SECS_BETWEEN_RESTARTS - elapsed)
            self.last_time_at_first = datetime.now()

    def save_cache(self, verbose: bool = False) -> None:
        if verbose:
            print("Saving untappd cache...")
        with open(CACHE_PATH, "w") as f:
            json.dump(self.cache, f, ensure_ascii=False)

    def _query_beer(self, query: str) -> Optional[UntappdBeerResult]:
        if (datetime.now() - self.last_time_at_first).total_seconds() > 3600:  # rate limit resets every hour
            self.backend_idx = 0
            self.last_time_at_first = datetime.now()
        while True:
            try:
                return self.current_backend.try_find_beer(query)
            except RateLimitError:
                self.next_backend()

    def try_find_beer(self, beer: ShopBeer) -> Optional[Tuple[UntappdBeerResult, str]]:
        """Returns result and used query if found or None otherwise"""
        if (datetime.now() - self.last_time_at_first).total_seconds() > 3600:  # rate limit resets every hour
            self.backend_idx = 0
            self.last_time_at_first = datetime.now()
        for query in beer.iter_untappd_queries():
            cached_beer = self.cache.get(query)
            if cached_beer is not None:
                valid = datetime.now() - datetime.fromtimestamp(cached_beer.timestamp) < BEER_CACHE_TIME
                if valid:
                    if cached_beer.beer_id is None:
                        continue
                    while True:
                        try:
                            return self.current_backend.get_beer_from_id(cached_beer.beer_id), query
                        except RateLimitError:
                            self.next_backend()
            res = self._query_beer(query)
            self.cache[query] = UntappdCacheEntry(None if res is None else res.beer_id, int(datetime.now().timestamp()))
            if res is not None:
                return res, query
        return None

    def iter_had_beers(
        self, user_id: Optional[int] = None, from_time: Optional[datetime] = None
    ) -> Iterator[Tuple[UntappdBeerResult, UserRating]]:
        # TODO: multiple backends?
        yield from self.current_backend.iter_had_beers(user_id=user_id, from_time=from_time)


__all__ = [
    "UntappdBeerResult",
    "UserInfo",
    "untappd_get_oauth_token",
    "untappd_get_user_info",
    "UntappdClient",
    "UNTAPPD_OAUTH_URL",
]

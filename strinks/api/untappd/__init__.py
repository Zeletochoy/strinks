import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import attr

from .api import UntappdAPI
from .auth import UserInfo, untappd_get_oauth_token, untappd_get_user_info, UNTAPPD_OAUTH_URL
from .structs import UntappdBeerResult, RateLimitError
from .web import UntappdWeb
from ..shops import ShopBeer
from ...db import get_db


CACHE_PATH = Path(__file__).with_name("untappd_cache.json")
MIN_SECS_BETWEEN_RESTARTS = 300  # 5min


class UntappdClient:
    def __init__(self):
        try:
            # TODO: expire cache
            with open(CACHE_PATH) as f:
                json_cache = json.load(f)
            self.cache: Dict[str, Optional[UntappdBeerResult]] = {
                query: UntappdBeerResult(**res) if res is not None else None for query, res in json_cache.items()
            }
        except Exception:
            self.cache = {}
        self.init_backends()

    def init_backends(self):
        db = get_db()
        self.backends = [
            UntappdAPI(),  # Strinks app credentials
            *[UntappdAPI(auth_token=token) for token in db.get_access_tokens()],  # User tokens
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

    def save_cache(self):
        json_cache = {query: attr.asdict(res) if res is not None else None for query, res in self.cache.items()}
        with open(CACHE_PATH, "w") as f:
            json.dump(json_cache, f, ensure_ascii=False)

    def _query_beer(self, query: str) -> Optional[UntappdBeerResult]:
        if (datetime.now() - self.last_time_at_first).total_seconds() > 3600:  # rate limit resets every hour
            self.backend_idx = 0
        while True:
            try:
                return self.current_backend.try_find_beer(query)
            except RateLimitError:
                self.next_backend()

    def try_find_beer(self, beer: ShopBeer) -> Optional[Tuple[UntappdBeerResult, str]]:
        """Returns result and used query if found or None otherwise"""
        for query in beer.iter_untappd_queries():
            if query in self.cache:
                cached_beer = self.cache[query]
                if cached_beer is not None:
                    return cached_beer, query
                continue
            res = self._query_beer(query)
            self.cache[query] = res
            self.save_cache()  # TODO: maybe not every time...
            if res is not None:
                return res, query
        return None


__all__ = [
    "UntappdBeerResult",
    "UserInfo",
    "untappd_get_oauth_token",
    "untappd_get_user_info",
    "UntappdClient",
    "UNTAPPD_OAUTH_URL",
]

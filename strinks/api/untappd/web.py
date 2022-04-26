import time
from collections import deque
from datetime import datetime, timedelta
from typing import Deque, Optional

import cloudscraper
from bs4 import BeautifulSoup

from ...db import get_db
from .rank import best_match
from .structs import FlavorTag, RateLimitError, UntappdBeerResult


MAX_REQ_PER_HOUR = 1000
REQ_COOLDOWN = 5
BEER_CACHE_TIME = timedelta(days=30)
session = cloudscraper.create_scraper(allow_brotli=False)


class UntappdWeb:
    def __init__(self):
        self.last_request_timestamps: Deque[float] = deque(maxlen=MAX_REQ_PER_HOUR)
        self.headers = {
            "Referer": "https://untappd.com/home",
            "User-Agent": "Mozilla/5.0 (Linux) Gecko/20100101 Firefox/81.0",
        }
        self.db = get_db()

    def __str__(self) -> str:
        return "UntappdWeb()"

    def __repr__(self) -> str:
        return str(self)

    def rate_limit(self):
        while len(self.last_request_timestamps) >= MAX_REQ_PER_HOUR:
            time_since_oldest = time.monotonic() - self.last_request_timestamps[0]
            if time_since_oldest < 3600:
                time.sleep(3600 - time_since_oldest)
            self.last_request_timestamps.popleft()
        if self.last_request_timestamps:
            time_since_last = time.monotonic() - self.last_request_timestamps[-1]
            if time_since_last < REQ_COOLDOWN:
                time.sleep(REQ_COOLDOWN - time_since_last)
        self.last_request_timestamps.append(time.monotonic())

    def _item_to_beer(self, item: BeautifulSoup) -> UntappdBeerResult:
        return UntappdBeerResult(
            beer_id=int(item.find("a", class_="label")["href"].rsplit("/", 1)[-1]),
            image_url=item.find("a", class_="label").find("img")["src"],
            name=item.find("p", class_="name").get_text().strip(),
            brewery=item.find("p", class_="brewery").get_text().strip(),
            style=item.find("p", class_="style").get_text().strip(),
            abv=float(item.find("p", class_="abv").get_text().strip().split("%", 1)[0].replace("N/A", "nan")),
            ibu=float(item.find("p", class_="ibu").get_text().strip().split(" ", 1)[0].replace("N/A", "nan")),
            rating=float(item.find("div", class_="caps")["data-rating"]),
        )

    def try_find_beer(self, query: str) -> Optional[UntappdBeerResult]:
        self.rate_limit()
        try:
            print(f"Untappd query for '{query}'")
            res = session.get(
                "https://untappd.com/search",
                params={"q": query},
                headers=self.headers,
            )
            if res.status_code >= 300:
                raise RateLimitError()
            soup = BeautifulSoup(res.text, "html.parser")
            items = soup("div", class_="beer-item")
            if not items:
                return None
            beers = [self._item_to_beer(item) for item in items]
            best_idx = best_match(query, (f"{beer.brewery} {beer.name}" for beer in beers))
            beer: Optional[UntappdBeerResult] = beers[best_idx]
        except Exception as e:
            print(f"Unexpected exception in UntappdWeb.try_find_beer: {e}")
            raise RateLimitError()
        return beer

    def get_beer_from_id(self, beer_id: int) -> UntappdBeerResult:
        return self._get_beer_from_db(beer_id) or self._query_beer(beer_id)

    def _query_beer(self, beer_id: int) -> UntappdBeerResult:
        self.rate_limit()
        try:
            res = session.get(f"https://untappd.com/beer/{beer_id}", headers=self.headers)
            if res.status_code >= 300:
                raise RateLimitError()
            soup = BeautifulSoup(res.text, "html.parser")
            item = soup.find("div", class_="content")
            if item is None:
                raise KeyError(f"Beer with ID {beer_id} not found on untappd")
            beer = self._item_to_beer(item)
        except Exception:
            raise RateLimitError()
        return beer

    def _get_beer_from_db(self, beer_id: int) -> Optional[UntappdBeerResult]:
        beer = self.db.get_beer(beer_id)
        if beer is None or datetime.now() - beer.updated_at > BEER_CACHE_TIME:
            if beer is not None:
                print(f"Updating {beer}...")
            return None
        return UntappdBeerResult(
            beer_id=beer.beer_id,
            image_url=beer.image_url,
            name=beer.name,
            brewery=beer.brewery,
            style=beer.style,
            abv=float(beer.abv or "nan"),
            ibu=float(beer.ibu or "nan"),
            rating=float(beer.rating or "nan"),
            tags={FlavorTag(assoc.tag.tag_id, assoc.tag.name, assoc.count) for assoc in beer.tags},
        )

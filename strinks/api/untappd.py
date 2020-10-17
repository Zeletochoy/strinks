import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

import attr
import cloudscraper
from bs4 import BeautifulSoup

from .shops import ShopBeer


logger = logging.getLogger(__name__)
CACHE_PATH = Path(__file__).with_name("untappd_cache.json")


MAX_REQ_PER_HOUR = 1000
REQ_COOLDOWN = 5
session = cloudscraper.create_scraper(allow_brotli=False)


@attr.s
class UntappdBeerResult:
    beer_id: int = attr.ib()
    image_url: str = attr.ib()
    name: str = attr.ib()
    brewery: str = attr.ib()
    style: str = attr.ib()
    abv: float = attr.ib()
    ibu: float = attr.ib()
    rating: float = attr.ib()


class UntappdAPI:
    def __init__(self):
        try:
            # TODO: expire cache
            with open(CACHE_PATH) as f:
                json_cache = json.load(f)
            self.cache = {
                query: UntappdBeerResult(**res) if res is not None else None for query, res in json_cache.items()
            }
        except Exception:
            self.cache: Dict[str, UntappdBeerResult] = {}
        self.last_request_timestamps: Deque[float] = deque(maxlen=MAX_REQ_PER_HOUR)

    def rate_limit(self):
        if len(self.last_request_timestamps) == MAX_REQ_PER_HOUR:
            time_since_oldest = time.monotonic() - self.last_request_timestamps[0]
            if time_since_oldest < 3600:
                time.sleep(3600 - time_since_oldest)
        if self.last_request_timestamps:
            time_since_last = time.monotonic() - self.last_request_timestamps[-1]
            if time_since_last < REQ_COOLDOWN:
                time.sleep(REQ_COOLDOWN - time_since_last)
        self.last_request_timestamps.append(time.monotonic())

    def save_cache(self):
        json_cache = {query: attr.asdict(res) if res is not None else None for query, res in self.cache.items()}
        with open(CACHE_PATH, "w") as f:
            json.dump(json_cache, f, ensure_ascii=False)

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

    def search(self, query: str) -> Optional[UntappdBeerResult]:
        if query in self.cache:
            return self.cache[query]
        self.rate_limit()
        try:
            print(f"Untappd query for '{query}'")
            res = session.get(
                "https://untappd.com/search",
                params={"q": query},
                headers={
                    "Referer": "https://untappd.com/home",
                    "User-Agent": "Mozilla/5.0 (Linux) Gecko/20100101 Firefox/81.0",
                },
            )
            if res.status_code >= 300:
                print(f"WARNING: HTTP {res.status_code} when querying untappd")
                import ipdb

                ipdb.set_trace()
                return None  # Skip cache, TODO retry
            soup = BeautifulSoup(res.text, "html.parser")
            item = soup.find("div", class_="beer-item")
            beer = self._item_to_beer(item)
        except (AttributeError, KeyError, IndexError, ValueError) as e:
            print("Except in untappd search:", e)
            beer = None
        except Exception as e:
            import ipdb

            ipdb.set_trace()
            beer = None
        self.cache[query] = beer
        self.save_cache()
        return beer

    def try_find_beer(self, beer: ShopBeer) -> Optional[Tuple[UntappdBeerResult, str]]:
        """Returns result and used query if found or None otherwise"""
        queries = list(beer.iter_untappd_queries())
        for query in queries:
            if self.cache.get(query) is not None:
                return self.cache[query], query
        for query in queries:
            res = self.search(query)
            if res is not None:
                return res, query
        return None

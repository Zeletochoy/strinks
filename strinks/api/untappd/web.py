import time
from collections import deque
from pathlib import Path
from typing import Deque, Optional

import cloudscraper
from bs4 import BeautifulSoup

from .structs import UntappdBeerResult, RateLimitError


CACHE_PATH = Path(__file__).with_name("untappd_cache.json")
MAX_REQ_PER_HOUR = 1000
REQ_COOLDOWN = 5
session = cloudscraper.create_scraper(allow_brotli=False)


class UntappdWeb:
    def __init__(self):
        self.last_request_timestamps: Deque[float] = deque(maxlen=MAX_REQ_PER_HOUR)

    def __str__(self) -> str:
        return "UntappdWeb()"

    def __repr__(self) -> str:
        return str(self)

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
                headers={
                    "Referer": "https://untappd.com/home",
                    "User-Agent": "Mozilla/5.0 (Linux) Gecko/20100101 Firefox/81.0",
                },
            )
            if res.status_code >= 300:
                raise RateLimitError()
            soup = BeautifulSoup(res.text, "html.parser")
            item = soup.find("div", class_="beer-item")
            beer: Optional[UntappdBeerResult] = self._item_to_beer(item)
        except (AttributeError, KeyError, IndexError, ValueError):
            beer = None
        except Exception:
            raise RateLimitError()
        return beer

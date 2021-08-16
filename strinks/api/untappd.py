import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple, NamedTuple

import attr
import cloudscraper
from bs4 import BeautifulSoup

from .shops import ShopBeer
from .settings import UNTAPPD_CLIENT_ID, UNTAPPD_CLIENT_SECRET


logger = logging.getLogger(__name__)
CACHE_PATH = Path(__file__).with_name("untappd_cache.json")


MAX_REQ_PER_HOUR = 1000
REQ_COOLDOWN = 5
session = cloudscraper.create_scraper(allow_brotli=False)

AUTH_REDIRECT_URL = "https://strinks.zeletochoy.fr/auth"
UNTAPPD_OAUTH_URL = (
    "https://untappd.com/oauth/authenticate/"
    f"?client_id={UNTAPPD_CLIENT_ID}&response_type=code&redirect_url={AUTH_REDIRECT_URL}"
)
API_URL = "https://api.untappd.com/v4"


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
        except (AttributeError, KeyError, IndexError, ValueError):
            beer = None
        except Exception as e:
            print("Unexpected exception in Untappd search:", e)
            return None  # Skip cache, TODO retry
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


def untappd_get_oauth_token(auth_code: str) -> str:
    res = session.get("https://untappd.com/oauth/authorize/", params=dict(
        client_id=UNTAPPD_CLIENT_ID,
        client_secret=UNTAPPD_CLIENT_SECRET,
        response_type="code",
        redirect_url=AUTH_REDIRECT_URL,
        code=auth_code,
    ))
    res.raise_for_status()
    return res.json()["response"]["access_token"]


class UserInfo(NamedTuple):
    id: int
    user_name: str
    first_name: str
    last_name: str
    avatar_url: str


def untappd_get_user_info(access_token: str) -> UserInfo:
    res = session.get(API_URL + "/user/info", params=dict(
        access_token=access_token,
        compact="true",
    ))
    res.raise_for_status()
    user_json = res.json()["response"]["user"]
    return UserInfo(
        id=user_json["id"],
        user_name=user_json["user_name"],
        first_name=user_json["first_name"],
        last_name=user_json["last_name"],
        avatar_url=user_json["user_avatar"],
    )

import logging
import time
from datetime import datetime, timedelta
from typing import Iterator, Optional, Tuple, Union

from ...db import get_db
from ..settings import UNTAPPD_CLIENT_ID
from ..utils import get_retrying_session
from .auth import get_untappd_api_auth_params
from .rank import best_match
from .structs import FlavorTag, RateLimitError, UntappdBeerResult, UserRating


logger = logging.getLogger(__name__)
session = get_retrying_session()

REQUEST_COOLDOWN = timedelta(seconds=1)
RATE_LIMIT_COOLDOWN = timedelta(minutes=10)
BEER_CACHE_TIME = timedelta(days=30)
API_URL = "https://api.untappd.com/v4"
USER_AGENT = f"Strinks ({UNTAPPD_CLIENT_ID})"


class UntappdAPI:
    def __init__(self, auth_token: Optional[str] = None):
        self.auth_token = auth_token
        self.rate_limited_until = datetime.now()
        self.db = get_db()
        self.last_request_time = datetime.fromtimestamp(0)

    def __str__(self) -> str:
        auth = f"{self.auth_token[:5]}..." if self.auth_token else "APP"
        return f"UntappdAPI(auth={auth})"

    def __repr__(self) -> str:
        return str(self)

    def api_request(self, uri: str, **params: Union[str, int]) -> dict:
        # Rate limit
        now = datetime.now()
        if self.rate_limited_until > now:
            raise RateLimitError()
        time_since_last = now - self.last_request_time
        remaining_seconds = (REQUEST_COOLDOWN - time_since_last).total_seconds()
        if remaining_seconds > 0:
            time.sleep(remaining_seconds)
        self.last_request_time = now

        res = session.get(
            API_URL + uri,
            params={**params, **get_untappd_api_auth_params(self.auth_token)},
            headers={"User-Agent": USER_AGENT},
        )
        if res.status_code != 200:
            self.rate_limited_until = datetime.now() + RATE_LIMIT_COOLDOWN
            raise RateLimitError()
        res_json = res.json()
        if res_json.get("meta", {}).get("code", 200) != 200:
            self.rate_limited_until = datetime.now() + RATE_LIMIT_COOLDOWN
            raise RateLimitError()
        return res_json

    def try_find_beer(self, query: str) -> Optional[UntappdBeerResult]:
        res_json = self.api_request("/search/beer", q=query, limit=10)
        results = res_json["response"]["beers"]["items"]
        if not results:
            return None
        beer_names = [f"{result['brewery']['brewery_name']} {result['beer']['beer_name']}" for result in results]
        beer_id = results[best_match(query, beer_names)]["beer"]["bid"]
        return self.get_beer_from_id(beer_id)

    def get_beer_from_id(self, beer_id: int) -> UntappdBeerResult:
        return self._get_beer_from_db(beer_id) or self._query_beer(beer_id)

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
            description=beer.description,
            tags={FlavorTag(assoc.tag.tag_id, assoc.tag.name, assoc.count) for assoc in beer.tags},
        )

    def _query_beer(self, beer_id: int) -> UntappdBeerResult:
        res_json = self.api_request(f"/beer/info/{beer_id}", compact="enhanced", ratingEnhanced="true")
        beer = res_json["response"]["beer"]

        try:
            tag_list = beer["flavor_profile"]["items"]
            tags = {FlavorTag(tag["tag_id"], tag["tag_name"], tag["total_count"]) for tag in tag_list}
        except KeyError:
            tags = None

        return UntappdBeerResult(
            beer_id=beer["bid"],
            image_url=beer.get("beer_label_hd", beer["beer_label"]),
            name=beer["beer_name"],
            brewery=beer["brewery"]["brewery_name"],
            style=beer["beer_style"],
            abv=beer["beer_abv"],
            ibu=beer["beer_ibu"],
            rating=beer["rating_score"],
            description=beer["beer_description"],
            tags=tags,
        )

    def iter_had_beers(
        self, user_id: Optional[int] = None, from_time: Optional[datetime] = None
    ) -> Iterator[Tuple[UntappdBeerResult, UserRating]]:
        if from_time is None:
            from_time = datetime.fromtimestamp(0)
        from_formatted = from_time.strftime("%Y-%m-%d")
        to_formatted = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        url = f"/user/beers/{user_id or ''}"
        num_fetched = 0
        while True:
            res_json = self.api_request(
                url, offset=num_fetched, limit=50, sort="date_asc", start_date=from_formatted, end_date=to_formatted
            )
            items = res_json["response"]["beers"]["items"]
            for beer_json in items:
                beer = UntappdBeerResult(
                    beer_id=beer_json["beer"]["bid"],
                    image_url=beer_json.get("beer_label_hd", beer_json["beer"]["beer_label"]),
                    name=beer_json["beer"]["beer_name"],
                    brewery=beer_json["brewery"]["brewery_name"],
                    style=beer_json["beer"]["beer_style"],
                    abv=beer_json["beer"]["beer_abv"],
                    ibu=beer_json["beer"]["beer_ibu"],
                    rating=beer_json["beer"]["rating_score"],
                )
                checkin_date_str = beer_json["recent_created_at"]
                checkin_date = datetime.strptime(checkin_date_str, "%a, %d %b %Y %H:%M:%S %z")
                rating = UserRating(beer_json["rating_score"], checkin_date)
                yield beer, rating
            num_fetched += len(items)
            if len(items) < 50:
                break

import logging
from datetime import datetime, timedelta
from typing import Optional, Union

import requests

from ...db import get_db
from ..settings import UNTAPPD_CLIENT_ID
from .auth import get_untappd_api_auth_params
from .rank import best_match
from .structs import RateLimitError, UntappdBeerResult


logger = logging.getLogger(__name__)

REQ_COOLDOWN = timedelta(minutes=10)
BEER_CACHE_TIME = timedelta(days=30)
API_URL = "https://api.untappd.com/v4"
USER_AGENT = f"Strinks ({UNTAPPD_CLIENT_ID})"


class UntappdAPI:
    def __init__(self, auth_token: Optional[str] = None):
        self.auth_token = auth_token
        self.rate_limited_until = datetime.now()
        self.db = get_db()

    def __str__(self) -> str:
        auth = f"{self.auth_token[:5]}..." if self.auth_token else "APP"
        return f"UntappdAPI(auth={auth})"

    def __repr__(self) -> str:
        return str(self)

    def api_request(self, uri: str, **params: Union[str, int]) -> dict:
        if self.rate_limited_until > datetime.now():
            raise RateLimitError()
        res = requests.get(
            API_URL + uri,
            params={**params, **get_untappd_api_auth_params(self.auth_token)},
            headers={"User-Agent": USER_AGENT},
        )
        if res.headers.get("X-Ratelimit-Remaining") == "0":
            self.rate_limited_until = datetime.now() + REQ_COOLDOWN
        elif res.status_code != 200:
            self.rate_limited_until = datetime.now() + REQ_COOLDOWN
            raise RateLimitError()
        res_json = res.json()
        if res_json.get("meta", {}).get("code", 200) != 200:
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
        )

    def _query_beer(self, beer_id: int) -> UntappdBeerResult:
        res_json = self.api_request(f"/beer/info/{beer_id}", compact="enhanced", ratingEnhanced="true")
        beer = res_json["response"]["beer"]
        return UntappdBeerResult(
            beer_id=beer["bid"],
            image_url=beer.get("beer_label_hd", beer["beer_label"]),
            name=beer["beer_name"],
            brewery=beer["brewery"]["brewery_name"],
            style=beer["beer_style"],
            abv=beer["beer_abv"],
            ibu=beer["beer_ibu"],
            rating=beer["rating_score"],
        )

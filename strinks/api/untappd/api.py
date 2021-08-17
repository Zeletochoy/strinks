import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

from .auth import get_untappd_api_auth_params
from .structs import UntappdBeerResult, RateLimitError
from ..settings import UNTAPPD_CLIENT_ID


logger = logging.getLogger(__name__)

REQ_COOLDOWN = timedelta(minutes=10)
API_URL = "https://api.untappd.com/v4"
USER_AGENT = f"Strinks ({UNTAPPD_CLIENT_ID})"


class UntappdAPI:
    def __init__(self, auth_token: Optional[str] = None):
        self.auth_token = auth_token
        self.rate_limited_until = datetime.now()

    def __str__(self) -> str:
        auth = f"{self.auth_token[:5]}..." if self.auth_token else "APP"
        return f"UntappdAPI(auth={auth})"

    def __repr__(self) -> str:
        return str(self)

    def api_request(self, uri: str, **params: dict) -> dict:
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
        res.raise_for_status()
        res_json = res.json()
        if res_json.get("meta", {}).get("http_code", 200) != 200:
            raise RateLimitError()
        return res_json

    def try_find_beer(self, query: str) -> Optional[UntappdBeerResult]:
        res_json = self.api_request("/search/beer", q=query, limit=1)
        results = res_json["response"]["beers"]["items"]
        if not results:
            return None
        return self.get_beer(results[0]["beer"]["bid"])

    def get_beer(self, beer_id: int) -> UntappdBeerResult:
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

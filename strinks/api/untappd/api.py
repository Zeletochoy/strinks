import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from ...db import get_db
from ..async_utils import _untappd_rate_limiter
from ..settings import UNTAPPD_CLIENT_ID
from ..utils import JST, now_jst
from .auth import get_untappd_api_auth_params
from .rank import best_match
from .structs import FlavorTag, RateLimitError, UntappdBeerResult, UntappdBreweryResult, UserRating

logger = logging.getLogger("untappd.api")

RATE_LIMIT_COOLDOWN = timedelta(minutes=10)
BEER_CACHE_TIME = timedelta(days=30)
API_URL = "https://api.untappd.com/v4"
USER_AGENT = f"Strinks ({UNTAPPD_CLIENT_ID})"


class UntappdAPI:
    def __init__(self, session: aiohttp.ClientSession, auth_token: str | None = None):
        self.session = session
        self.auth_token = auth_token
        self.rate_limited_until = now_jst()
        self.db = get_db()

    def __str__(self) -> str:
        auth = f"{self.auth_token[:5]}..." if self.auth_token else "APP"
        return f"UntappdAPI(auth={auth})"

    def __repr__(self) -> str:
        return str(self)

    async def api_request(self, uri: str, **params: str | int) -> dict[str, Any]:
        # Check rate limit
        now = now_jst()
        if self.rate_limited_until > now:
            raise RateLimitError()

        # Apply Untappd rate limiting (1 req/sec)
        await _untappd_rate_limiter.wait_if_needed()

        if not self.session:
            raise ValueError("Session not initialized")

        try:
            async with self.session.get(
                API_URL + uri,
                params={**params, **get_untappd_api_auth_params(self.auth_token)},
                headers={"User-Agent": USER_AGENT},
            ) as res:
                if res.status != 200:
                    self.rate_limited_until = now_jst() + RATE_LIMIT_COOLDOWN
                    raise RateLimitError()
                res_json: dict[str, Any] = await res.json()
                if res_json.get("meta", {}).get("code", 200) != 200:
                    self.rate_limited_until = now_jst() + RATE_LIMIT_COOLDOWN
                    raise RateLimitError()
                return res_json
        except TimeoutError:
            self.rate_limited_until = now_jst() + RATE_LIMIT_COOLDOWN
            raise RateLimitError()

    async def try_find_beer(self, query: str) -> UntappdBeerResult | None:
        if not query:
            return None
        res_json = await self.api_request("/search/beer", q=query, limit=10)
        results = res_json["response"]["beers"]["items"]
        if not results:
            return None
        beer_names = [f"{result['brewery']['brewery_name']} {result['beer']['beer_name']}" for result in results]
        beer_id = results[best_match(query, beer_names)]["beer"]["bid"]
        return await self.get_beer_from_id(beer_id)

    async def get_beer_from_id(self, beer_id: int) -> UntappdBeerResult:
        return self._get_beer_from_db(beer_id) or await self._query_beer(beer_id)

    def _get_beer_from_db(self, beer_id: int) -> UntappdBeerResult | None:
        beer = self.db.get_beer(beer_id)
        if beer is None:
            return None
        # Handle both naive and aware datetimes for backward compatibility
        updated_at = beer.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=JST)
        if now_jst() - updated_at > BEER_CACHE_TIME:
            logger.debug(f"Updating {beer}...")
            return None
        return UntappdBeerResult(
            beer_id=beer.beer_id,
            image_url=beer.image_url,
            name=beer.name,
            brewery=beer.brewery_name,
            brewery_id=beer.brewery_id,
            brewery_country=beer.brewery_country,
            style=beer.style,
            abv=float(beer.abv or "nan"),
            ibu=float(beer.ibu or "nan"),
            rating=float(beer.rating or "nan"),
            description=beer.description,
            tags={FlavorTag(assoc.tag.tag_id, assoc.tag.name, assoc.count) for assoc in beer.tags},
        )

    async def _query_beer(self, beer_id: int) -> UntappdBeerResult:
        res_json = await self.api_request(f"/beer/info/{beer_id}", compact="enhanced", ratingEnhanced="true")
        beer = res_json["response"]["beer"]

        try:
            tag_list = beer["flavor_profile"]["items"]
            tags = {FlavorTag(tag["tag_id"], tag["tag_name"], tag["total_count"]) for tag in tag_list}
        except KeyError:
            tags = None

        brewery_info = beer.get("brewery", {})
        location_info = brewery_info.get("location", {})
        stats_info = beer.get("stats", {})

        return UntappdBeerResult(
            beer_id=beer["bid"],
            image_url=beer.get("beer_label_hd", beer["beer_label"]),
            name=beer["beer_name"],
            brewery=brewery_info["brewery_name"],
            brewery_id=brewery_info["brewery_id"],
            brewery_country=brewery_info["country_name"],
            brewery_city=location_info.get("brewery_city"),
            brewery_state=location_info.get("brewery_state"),
            style=beer["beer_style"],
            abv=beer["beer_abv"],
            ibu=beer["beer_ibu"],
            rating=beer["rating_score"],
            weighted_rating=beer.get("weighted_rating_score"),
            rating_count=beer.get("rating_count"),
            total_user_count=stats_info.get("total_user_count"),
            description=beer["beer_description"],
            tags=tags,
        )

    async def search_breweries(self, query: str) -> list[UntappdBreweryResult]:
        if not query:
            return []
        res_json = await self.api_request("/search/brewery", q=query, limit=50)
        return [
            UntappdBreweryResult(
                brewery_id=result["brewery"]["brewery_id"],
                image_url=result["brewery"]["brewery_label"],
                name=result["brewery"]["brewery_name"],
                country=result["brewery"]["country_name"],
                city=result["brewery"].get("location", {}).get("brewery_city"),
                state=result["brewery"].get("location", {}).get("brewery_state"),
            )
            for result in res_json["response"]["brewery"]["items"]
        ]

    async def iter_had_beers(self, user_id: int | None = None, from_time: datetime | None = None):
        if from_time is None:
            from_time = datetime.fromtimestamp(0, tz=JST)
        from_formatted = from_time.strftime("%Y-%m-%d")
        to_formatted = (now_jst() + timedelta(days=1)).strftime("%Y-%m-%d")
        url = f"/user/beers/{user_id or ''}"
        num_fetched = 0
        while True:
            res_json = await self.api_request(
                url, offset=num_fetched, limit=50, sort="date_asc", start_date=from_formatted, end_date=to_formatted
            )
            items = res_json["response"]["beers"]["items"]
            for beer_json in items:
                beer = UntappdBeerResult(
                    beer_id=beer_json["beer"]["bid"],
                    image_url=beer_json.get("beer_label_hd", beer_json["beer"]["beer_label"]),
                    name=beer_json["beer"]["beer_name"],
                    brewery=beer_json["brewery"]["brewery_name"],
                    brewery_id=beer_json["brewery"]["brewery_id"],
                    brewery_country=beer_json["brewery"].get("country_name"),
                    brewery_city=beer_json["brewery"].get("location", {}).get("brewery_city"),
                    brewery_state=beer_json["brewery"].get("location", {}).get("brewery_state"),
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

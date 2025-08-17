from datetime import datetime
from typing import NamedTuple

from pydantic import BaseModel


class FlavorTag(NamedTuple):
    tag_id: int
    name: str
    count: int  # type: ignore


class UntappdBeerResult(BaseModel):
    beer_id: int
    image_url: str
    name: str
    brewery: str
    brewery_id: int
    brewery_country: str
    brewery_city: str | None = None
    brewery_state: str | None = None
    style: str
    abv: float
    ibu: float
    rating: float
    weighted_rating: float | None = None
    rating_count: int | None = None
    total_user_count: int | None = None
    description: str | None = None
    tags: set[FlavorTag] | None = None


class UntappdBreweryResult(BaseModel):
    brewery_id: int
    image_url: str
    name: str
    country: str
    city: str | None = None
    state: str | None = None


class UserInfo(NamedTuple):
    user_id: int
    user_name: str
    first_name: str
    last_name: str
    avatar_url: str
    access_token: str


class RateLimitError(RuntimeError):
    pass


class UserRating(NamedTuple):
    rating: float
    updated_at: datetime

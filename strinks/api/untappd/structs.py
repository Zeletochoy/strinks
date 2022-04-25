from datetime import datetime
from typing import NamedTuple, Optional, Set

import attr


class FlavorTag(NamedTuple):
    tag_id: int
    name: str
    count: int  # type: ignore


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
    description: Optional[str] = attr.ib(default=None)
    tags: Optional[Set[FlavorTag]] = attr.ib(default=None)


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

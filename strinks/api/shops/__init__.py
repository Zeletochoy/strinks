import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator

from pydantic import BaseModel, model_validator

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..translation import BREWERY_JP_EN, deepl_translate, has_japanese, to_romaji
from .discovery import get_shop_map_dynamic


class ShopBeer(BaseModel):
    raw_name: str
    url: str
    milliliters: int
    price: int
    quantity: int
    available: int | None = None
    beer_name: str | None = None
    brewery_name: str | None = None
    image_url: str | None = None

    @model_validator(mode="after")
    def validate_positive_values(self):
        if not (self.milliliters and self.price and self.quantity):
            raise NotABeerError
        return self

    @property
    def unit_price(self) -> float:
        return self.price / self.quantity

    @property
    def price_per_ml(self) -> float:
        return self.unit_price / self.milliliters

    def _iter_untappd_queries(self) -> Iterator[str]:
        clean_name = ""
        brewery = self.brewery_name
        if brewery is not None and self.beer_name is not None:
            clean_name = f"{brewery} {self.beer_name}"
            yield clean_name
            translated_brewery = BREWERY_JP_EN.get(brewery)
            if translated_brewery is not None:
                clean_name = f"{translated_brewery} {self.beer_name}"
                brewery = translated_brewery
                yield clean_name
        yield self.raw_name
        if clean_name:
            # Try romaji/ translation
            if has_japanese(clean_name):
                yield to_romaji(clean_name)
                yield deepl_translate(clean_name)
            # Try without stuff in parentheses
            yield re.sub("[(][^)]*[)]", "", clean_name)
            # Try removing suffixes like style
            for _ in range(2):
                clean_name, _ = clean_name.rsplit(" ", 1)
                if clean_name == brewery:
                    break
                yield clean_name
        # Try romaji / translation
        if has_japanese(self.raw_name):
            yield to_romaji(self.raw_name)
            yield deepl_translate(self.raw_name)

    def iter_untappd_queries(self) -> Iterator[str]:
        seen: set[str] = set()
        for query in self._iter_untappd_queries():
            query = query.lower().strip()
            if query in seen:
                continue
            seen.add(query)
            yield query


class Shop(ABC):
    short_name = "shop"
    display_name = "Shop"

    @abstractmethod
    def iter_beers(self) -> Iterator[ShopBeer]: ...

    @abstractmethod
    def get_db_entry(self, db: BeerDB) -> DBShop: ...


def get_shop_map() -> dict[str, Callable[[], Shop]]:
    """Get the map of shop names to shop factory functions.

    Uses dynamic discovery to find all Shop subclasses automatically.
    """
    return get_shop_map_dynamic()


class NotABeerError(Exception): ...


class NoBeersError(Exception): ...

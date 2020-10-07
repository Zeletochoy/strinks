from abc import ABC, abstractmethod
from typing import Iterator, Optional

import attr

from ..translation import BREWERY_JP_EN


@attr.s
class ShopBeer:
    raw_name: str = attr.ib()
    milliliters: int = attr.ib()
    price: int = attr.ib()
    quantity: int = attr.ib()
    available: Optional[int] = attr.ib(default=None)
    beer_name: Optional[str] = attr.ib(default=None)
    brewery_name: Optional[str] = attr.ib(default=None)
    image_url: Optional[str] = attr.ib(default=None)

    @property
    def unit_price(self) -> float:
        return self.price / self.quantity

    @property
    def price_per_ml(self) -> float:
        return self.unit_price / self.milliliters

    def iter_untappd_queries(self) -> Iterator[str]:
        clean_name = ""
        if self.brewery_name is not None and self.beer_name is not None:
            clean_name = f"{self.brewery_name} {self.beer_name}"
            yield clean_name
            translated_brewery = BREWERY_JP_EN.get(self.brewery_name)
            if translated_brewery is not None:
                clean_name = f"{translated_brewery} {self.beer_name}"
        yield self.raw_name
        if self.beer_name is not None:
            yield self.beer_name
        # Try removing extra suffixes (style, ...)
        if clean_name:
            for _ in range(2):
                clean_name, _ = clean_name.rsplit(" ", 1).strip()
                if clean_name == self.brewery_name:
                    break
                yield clean_name


class Shop(ABC):
    @abstractmethod
    def iter_beers(self) -> Iterator[ShopBeer]:
        ...


class NotABeerError(Exception):
    ...


class NoBeersError(Exception):
    ...

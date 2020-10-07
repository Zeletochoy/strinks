from abc import ABC, abstractmethod
from typing import Iterator, Optional

import attr


@attr.s
class BackendBeer:
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

    @property
    def untappd_search(self) -> float:
        if self.brewery_name is not None and self.beer_name is not None:
            return f"{self.brewery_name} {self.beer_name}"
        return self.raw_name


class Backend(ABC):
    @abstractmethod
    def iter_beers(self) -> Iterator[BackendBeer]:
        ...


class NotABeerError(Exception):
    ...


class NoBeersError(Exception):
    ...

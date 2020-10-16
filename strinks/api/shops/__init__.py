from abc import ABC, abstractmethod
from typing import Dict, Iterator, Optional, Type

import attr

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..translation import BREWERY_JP_EN


@attr.s
class ShopBeer:
    raw_name: str = attr.ib()
    url: str = attr.ib()
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
        brewery = self.brewery_name
        if brewery is not None and self.beer_name is not None:
            clean_name = f"{brewery} {self.beer_name}"
            yield clean_name
            translated_brewery = BREWERY_JP_EN.get(self.brewery_name)
            if translated_brewery is not None:
                clean_name = f"{translated_brewery} {self.beer_name}"
                brewery = translated_brewery
        yield self.raw_name
        # Try removing extra suffixes (style, ...)
        if clean_name:
            for _ in range(2):
                clean_name, _ = clean_name.rsplit(" ", 1)
                if clean_name == brewery:
                    break
                yield clean_name


class Shop(ABC):
    short_name = "shop"
    display_name = "Shop"

    @abstractmethod
    def iter_beers(self) -> Iterator[ShopBeer]:
        ...

    @abstractmethod
    def get_db_entry(self, db: BeerDB) -> DBShop:
        ...


def get_shop_map() -> Dict[str, Type[Shop]]:
    from .antenna import AntennaAmerica
    from .chouseiya import Chouseiya
    from .volta import Volta

    return {cls.short_name: cls for cls in (AntennaAmerica, Chouseiya, Volta)}


class NotABeerError(Exception):
    ...


class NoBeersError(Exception):
    ...

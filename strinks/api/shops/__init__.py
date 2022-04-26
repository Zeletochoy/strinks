import re
from abc import ABC, abstractmethod
from typing import Dict, Iterator, Optional, Set, Type

import attr

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..translation import BREWERY_JP_EN, deepl_translate, has_japanese, to_romaji


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
        seen: Set[str] = set()
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
    def iter_beers(self) -> Iterator[ShopBeer]:
        ...

    @abstractmethod
    def get_db_entry(self, db: BeerDB) -> DBShop:
        ...


def get_shop_map() -> Dict[str, Type[Shop]]:
    from .antenna import AntennaAmerica
    from .beerzilla import Beerzilla
    from .cardinal import Cardinal
    from .chouseiya import Chouseiya
    from .craftbeers import CraftBeers
    from .digtheline import DigTheLine
    from .drinkup import DrinkUp
    from .gbf import GoodBeerFaucets
    from .goodbeer import Goodbeer
    from .hopbuds import HopBuds
    from .ibrew import IBrew
    from .ichigo import IchiGoIchiAle
    from .maruho import Maruho
    from .ohtsuki import Ohtsuki
    from .threefeet import Threefeet
    from .volta import Volta

    return {
        cls.short_name: cls  # type: ignore
        for cls in (
            AntennaAmerica,
            Beerzilla,
            Cardinal,
            Chouseiya,
            CraftBeers,
            DigTheLine,
            DrinkUp,
            GoodBeerFaucets,
            Goodbeer,
            HopBuds,
            IBrew,
            IchiGoIchiAle,
            Maruho,
            Ohtsuki,
            Threefeet,
            Volta,
        )
    }


class NotABeerError(Exception):
    ...


class NoBeersError(Exception):
    ...

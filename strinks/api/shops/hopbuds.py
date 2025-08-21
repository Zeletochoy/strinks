from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_text
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import extract_brewery_beer, parse_milliliters, parse_price


class HopBuds(Shop):
    short_name = "hopbuds"
    display_name = "Hop Buds"

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://hopbudsnagoya.com/collections/craft-beers?page={i}"
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser")
            i += 1

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[tuple[BeautifulSoup, str]]:
        empty = True
        items = page_soup.find_all("a", class_="product-card")
        for item in items:
            if item.find("div", class_="product-card__availability"):
                continue  # Sold Out
            if not item.get("href"):
                continue
            url = "https://hopbudsnagoya.com" + item["href"]
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title_elem = page_soup.find("h1", class_="product-single__title")
        if not title_elem:
            raise NotABeerError
        title = title_elem.get_text().strip()

        # Extract brewery and beer name
        brewery_name, beer_name = extract_brewery_beer(title)
        if not brewery_name or not beer_name:
            # Fallback to original logic if extract_brewery_beer doesn't work
            if " - " not in title:
                raise NotABeerError
            brewery_name, beer_name = title.lower().split(" - ")
        else:
            brewery_name = brewery_name.lower()
            beer_name = beer_name.lower()

        raw_name = f"{brewery_name} {beer_name}"

        # Parse price
        price_elem = page_soup.find(id="ProductPrice")
        if not price_elem:
            raise NotABeerError
        price_text = price_elem.get_text().strip()
        price = parse_price(price_text)
        if price is None:
            raise NotABeerError

        # Parse milliliters
        desc_elem = page_soup.find("div", class_="rte")
        if not desc_elem:
            raise NotABeerError
        desc = desc_elem.get_text().strip()
        ml = parse_milliliters(desc)
        if ml is None:
            raise NotABeerError

        img_elem = page_soup.find(id="ProductPhotoImg")
        if not img_elem or not img_elem.get("src"):
            raise NotABeerError
        image_url = "https:" + img_elem["src"]

        return ShopBeer(
            raw_name=raw_name,
            brewery_name=brewery_name,
            beer_name=beer_name,
            url=url,
            milliliters=ml,
            price=price,
            quantity=1,
            image_url=image_url,
        )

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        async for listing_page in self._iter_pages():
            try:
                async for beer_page, url in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_page, url)
                    except NotABeerError:
                        continue
                    except Exception:
                        self.logger.exception("Error parsing page")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://hopbudsnagoya.com/",
            image_url="https://cdn.shopify.com/s/files/1/1097/0424/t/2/assets/logo.png?v=12514362392207784998",
            shipping_fee=850,
        )

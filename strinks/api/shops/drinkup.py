import re
from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_cloudflare_protected
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import parse_milliliters, parse_price


class DrinkUp(Shop):
    short_name = "drinkup"
    display_name = "Drink Up"

    async def _ensure_session_ready(self) -> None:
        """Ensure the cloudscraper session is ready with CF challenge solved."""
        if not hasattr(self, "_session_ready"):
            # First visit to solve Cloudflare challenge
            base_url = "https://drinkuppers-ecshop.stores.jp/"
            domain = "drinkuppers-ecshop.stores.jp"
            try:
                # This will create a persistent session and solve CF challenge
                await fetch_cloudflare_protected(base_url, domain=domain)
                self._session_ready = True
            except Exception as e:
                self.logger.warning(f"Failed to initialize Drink Up session: {e}")
                raise NoBeersError("Could not bypass Cloudflare")

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        # Ensure CF challenge is solved
        await self._ensure_session_ready()

        i = 1
        domain = "drinkuppers-ecshop.stores.jp"
        # Set age confirmation cookie after CF challenge is solved
        cookies = {"confirm": "true"}

        while True:
            url = f"https://drinkuppers-ecshop.stores.jp/?page={i}"
            # Use cloudscraper with persistent session and age confirmation
            page = await fetch_cloudflare_protected(url, cookies=cookies, domain=domain)
            yield BeautifulSoup(page, "html.parser")
            i += 1

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[tuple[BeautifulSoup, str]]:
        empty = True
        domain = "drinkuppers-ecshop.stores.jp"
        # Age confirmation cookie for product pages
        cookies = {"confirm": "true"}

        items = page_soup.find_all("a", class_="c-itemList__item-link")
        for item in items:
            if not item.get("href"):
                continue
            url = "https://drinkuppers-ecshop.stores.jp" + item["href"]
            title_elem = item.find("p", class_="c-itemList__item-name")
            if not title_elem:
                continue
            title = title_elem.get_text().strip()
            if title.endswith("セット"):  # skip sets
                continue
            # Use persistent cloudscraper session
            page = await fetch_cloudflare_protected(url, cookies=cookies, domain=domain)
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title_elem = page_soup.find("h1", class_="item_name")
        if not title_elem:
            raise NotABeerError
        title = title_elem.get_text().strip()
        beer_name = title.split("／", 1)[-1]

        price_elem = page_soup.find("p", class_="item_price")
        if not price_elem:
            raise NotABeerError
        price_text = price_elem.get_text()
        # Use parsing utility for price
        price = parse_price(price_text)
        if price is None:
            raise NotABeerError

        desc_elem = page_soup.find("div", class_="main_content_result_item_list_detail")
        if not desc_elem:
            raise NotABeerError
        desc_text = desc_elem.get_text()
        # Use parsing utility for milliliters
        ml = parse_milliliters(desc_text)
        if ml is None:
            raise NotABeerError
        brewery_match = re.search("醸造所:.*/([^\n]*)", desc_text)
        brewery_name = None
        raw_name = beer_name
        if brewery_match is not None:
            brewery_name = brewery_match.group(1)
            brewery_name = re.sub(r"( (Beer|Brewery) )?Co\.", "", brewery_name)
            raw_name = f"{brewery_name} {beer_name}"

        gallery_elem = page_soup.find("div", class_="gallery_image_carousel")
        if not gallery_elem:
            raise NotABeerError
        img = gallery_elem.find("img")
        if not img or not img.get("src"):
            raise NotABeerError
        image_url = img["src"]
        return ShopBeer(
            beer_name=beer_name,
            brewery_name=brewery_name,
            raw_name=raw_name,
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
            name="Drink Up",
            url="https://drinkuppers-ecshop.stores.jp",
            image_url="https://p1-e6eeae93.imageflux.jp/c!/a=2,w=1880,u=0/drinkuppers-ecshop/5452ce0e2184264a81e3.png",
            shipping_fee=1100,
        )

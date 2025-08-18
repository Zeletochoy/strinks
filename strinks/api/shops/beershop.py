"""BEERSHOP scraper."""

import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import parse_milliliters, parse_price

session = get_retrying_session()


class Beershop(Shop):
    """BEERSHOP - Specialized craft beer online shop."""

    short_name = "beershop"
    display_name = "BEERSHOP"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        """Iterate through all pages of beer listings."""
        # BEERSHOP uses /SHOP/187888/t01/list{N}.html pattern for pagination
        page_num = 1

        while True:
            url = f"https://beershop.jp/SHOP/187888/t01/list{page_num}.html"

            try:
                page = session.get(url).text
                soup = BeautifulSoup(page, "html.parser")

                # Check if we have products on this page
                products = soup.select("section.column4, section.column5")
                if not products:
                    # No products means we've gone past the last page
                    break

                yield soup
                page_num += 1

            except Exception as e:
                print(f"Error fetching page {url}: {e}")
                break

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[tuple[str, str, str, str, str | None]]:
        """Extract beer info from a category page.

        Yields: (url, raw_name, price_text, volume_text, image_url)
        """
        # Find all product sections - can be column4 or column5
        products = page_soup.select("section.column4, section.column5")

        if not products:
            raise NoBeersError

        for product in products:
            try:
                # Check stock status
                stock_elem = product.select_one(".sps-itemList-stockDisp")
                if stock_elem and "在庫切れ" in stock_elem.get_text():
                    continue  # Skip sold out items

                # Get product link and name - can be in h2 or h3
                name_elem = product.select_one("h2 a, h3 a")
                if not name_elem:
                    continue

                raw_name = name_elem.get_text(strip=True)
                href = name_elem.get("href", "")
                # Ensure href is a string
                url = href if isinstance(href, str) else ""

                # Make URL absolute
                if url and not url.startswith("http"):
                    url = "https://beershop.jp" + (url if url.startswith("/") else "/" + url)

                # Get price - using the selling_price class
                price_elem = product.select_one("span.selling_price")
                if not price_elem:
                    continue

                price_text = price_elem.get_text(strip=True)

                # Get image if available
                img_elem = product.select_one("img")
                image_url = None
                if img_elem:
                    src = img_elem.get("src")
                    if src and isinstance(src, str):
                        if not src.startswith("http"):
                            image_url = "https://beershop.jp" + (src if src.startswith("/") else "/" + src)
                        else:
                            image_url = src

                yield (url, raw_name, price_text, raw_name, image_url)  # Use raw_name for volume extraction

            except Exception as e:
                print(f"Error parsing product: {e}")
                continue

    def _fetch_product_details(self, url: str) -> tuple[str | None, str | None]:
        """Fetch product page to get English name and brewery.

        Returns: (english_name, brewery_name)
        """
        try:
            response = session.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

            english_name = None
            brewery_name = None

            # Find all tables on the page
            tables = soup.select("table")
            for table in tables:
                rows = table.select("tr")
                for row in rows:
                    cells = row.select("th, td")
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)

                        # Extract English name
                        if label == "商品名（英）":
                            english_name = value
                        # Extract brewery
                        elif label == "醸造所":
                            brewery_name = value

            return english_name, brewery_name

        except Exception as e:
            print(f"Error fetching product details from {url}: {e}")
            return None, None

    def _parse_beer_info(
        self, url: str, raw_name: str, price_text: str, volume_text: str, image_url: str | None
    ) -> ShopBeer:
        """Parse beer information into ShopBeer object."""
        # Parse price
        price = parse_price(price_text)
        if price is None:
            raise NotABeerError

        # Parse volume from name (e.g., "ビール名 330ml" or "ビール名 瓶330ml")
        milliliters = parse_milliliters(volume_text)
        if milliliters is None:
            raise NotABeerError

        # Fetch English name and brewery from product page
        english_name, brewery_name = self._fetch_product_details(url)

        # If we got English name, parse it
        if english_name:
            # Remove volume from English name if present
            beer_name = re.sub(r"\s*\d+ml\s*$", "", english_name, flags=re.IGNORECASE).strip()

            # Try to split brewery and beer if not already have brewery
            if not brewery_name and " - " in beer_name:
                parts = beer_name.split(" - ", 1)
                brewery_name = parts[0].strip()
                beer_name = parts[1].strip()
            elif not brewery_name and " / " in beer_name:
                parts = beer_name.split(" / ", 1)
                brewery_name = parts[0].strip()
                beer_name = parts[1].strip()
        else:
            # Fallback to Japanese name parsing
            beer_name = raw_name
            # Remove volume info
            beer_name = re.sub(r"[瓶缶]?\d+ml", "", beer_name).strip()

            # Try to extract brewery from Japanese name if we don't have it
            if not brewery_name and "・" in beer_name:
                parts = beer_name.split("・", 1)
                brewery_name = parts[0].strip()
                beer_name = parts[1].strip()

        return ShopBeer(
            raw_name=raw_name,
            url=url,
            milliliters=milliliters,
            price=price,
            quantity=1,
            available=1,
            beer_name=beer_name,
            brewery_name=brewery_name,
            image_url=image_url,
        )

    def iter_beers(self) -> Iterator[ShopBeer]:
        """Iterate through all beers on BEERSHOP."""
        seen_urls = set()

        for listing_page in self._iter_pages():
            try:
                for beer_info in self._iter_page_beers(listing_page):
                    url = beer_info[0]
                    # Skip if we've already seen this beer
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    try:
                        yield self._parse_beer_info(*beer_info)
                    except NotABeerError:
                        continue
                    except Exception as e:
                        print(f"Unexpected exception while parsing beer: {e}")
            except NoBeersError:
                # This category has no beers, continue to next
                continue

    def get_db_entry(self, db: BeerDB) -> DBShop:
        """Get or create database entry for this shop."""
        return db.insert_shop(
            name=self.display_name,
            url="https://beershop.jp/",
            image_url="https://beershop.jp/pic-labo/shop_logo.png",
            shipping_fee=1100,
            free_shipping_over=5000,
        )

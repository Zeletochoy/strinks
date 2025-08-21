"""BUBBLES (kitakatabbb.com) scraper."""

import re
from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_text
from . import NoBeersError, Shop, ShopBeer
from .parsing import clean_beer_name, is_beer_set, parse_milliliters, parse_price


class Bubbles(Shop):
    """BUBBLES - Craft beer shop in Kitakata."""

    short_name = "bubbles"
    display_name = "BUBBLES"

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        """Iterate through all pages of beer listings."""
        page_index = 0

        while True:
            # sortKind=3 seems to be for listing all items
            url = f"https://kitakatabbb.com/item-list?pageIndex={page_index}&sortKind=3"

            try:
                response = await fetch_text(self.session, url)
                soup = BeautifulSoup(response, "html.parser")

                # Check if we have products on this page
                products = soup.select("li")
                # Filter to only product items (those with item-info div)
                product_items = [p for p in products if p.select_one(".item-info")]

                if not product_items:
                    break

                yield soup
                page_index += 1

            except Exception as e:
                self.logger.error(f"Error fetching page {url}: {e}")
                break

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[ShopBeer]:
        """Extract beer info from a page."""
        # Find all list items that contain products
        products = page_soup.select("li")

        found_any = False
        for product in products:
            # Check if this is a product item
            if not product.select_one(".item-info"):
                continue

            found_any = True

            try:
                # Get product name and URL
                name_elem = product.select_one(".item-name a")
                if not name_elem:
                    continue

                raw_name = name_elem.get_text(strip=True)

                # Skip if it's a set
                if is_beer_set(raw_name):
                    continue

                # Parse volume early to check if this is a beer
                # Non-beer items like glasses/merchandise won't have ml/cl volumes
                milliliters = parse_milliliters(raw_name)
                if milliliters is None:
                    # Skip items without recognizable beer volume
                    continue

                href = name_elem.get("href", "")
                if isinstance(href, str):
                    url = f"https://kitakatabbb.com{href}" if not href.startswith("http") else href
                else:
                    url = ""

                # Get price
                price_elem = product.select_one(".item-price")
                if not price_elem:
                    continue

                price_text = price_elem.get_text(strip=True)
                # Remove tax info like "（税込み）"
                price_text = re.sub(r"（.*?）", "", price_text).strip()
                price = parse_price(price_text)
                if price is None:
                    continue

                # Skip if out of stock
                if product.select_one(".item-nonstock"):
                    continue

                # Get image URL
                img_elem = product.select_one(".item-photo img")
                image_url = None
                if img_elem:
                    src = img_elem.get("src")
                    if src and isinstance(src, str):
                        image_url = src if src.startswith("http") else f"https://kitakatabbb.com{src}"

                # Parse brewery and beer name from the format:
                # "Brewery / Beer Name (English) Volume缶"
                parts = raw_name.split("/", 1)
                if len(parts) == 2:
                    brewery_name = parts[0].strip()
                    beer_part = parts[1].strip()
                    # Clean the beer name using existing utility
                    beer_name = clean_beer_name(beer_part)
                    # Remove volume and container type
                    beer_name = re.sub(r"\s*\d+ml.*$", "", beer_name, flags=re.IGNORECASE).strip()
                    # For BUBBLES, extract English name when pattern is "ENGLISH (Japanese)"
                    # e.g., "WISTERIA (ウィステリア)" -> "WISTERIA"
                    if "(" in beer_name and ")" in beer_name:
                        english_part = beer_name.split("(")[0].strip()
                        if english_part:
                            beer_name = english_part
                else:
                    brewery_name = None
                    beer_name = clean_beer_name(raw_name)
                    beer_name = re.sub(r"\s*\d+ml.*$", "", beer_name, flags=re.IGNORECASE).strip()
                    if "(" in beer_name and ")" in beer_name:
                        english_part = beer_name.split("(")[0].strip()
                        if english_part:
                            beer_name = english_part

                yield ShopBeer(
                    raw_name=raw_name,
                    url=url,
                    milliliters=milliliters,
                    price=price,
                    quantity=1,
                    beer_name=beer_name,
                    brewery_name=brewery_name,
                    image_url=image_url,
                )

            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
                continue

        if not found_any:
            raise NoBeersError

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        """Iterate through all beers on BUBBLES."""
        seen_urls = set()

        async for listing_page in self._iter_pages():
            try:
                async for beer in self._iter_page_beers(listing_page):
                    # Skip if we've already seen this beer
                    if beer.url in seen_urls:
                        continue
                    seen_urls.add(beer.url)
                    yield beer

            except NoBeersError:
                # No beers on this page, continue to next
                continue

    def get_db_entry(self, db: BeerDB) -> DBShop:
        """Get or create database entry for this shop."""
        return db.insert_shop(
            name=self.display_name,
            url="https://kitakatabbb.com/",
            image_url="https://kitakatabbb.com/img/logo.svg",
            shipping_fee=1000,  # Varies by quantity, typical cost for 6+ bottles
            free_shipping_over=18000,
        )

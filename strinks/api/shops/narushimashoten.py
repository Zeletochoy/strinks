"""Narushima Shoten (narushimashoten.com) scraper."""

from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_json
from . import NotABeerError, Shop, ShopBeer
from .parsing import clean_beer_name, is_beer_set, parse_milliliters


class NarushimaShoten(Shop):
    """Narushima Shoten - Shopify-based craft beer specialty store."""

    short_name = "narushimashoten"
    display_name = "Narushima Shoten"

    async def _fetch_products(self, page: int) -> list[dict]:
        """Fetch products from Shopify collections API."""
        url = (
            "https://narushimashoten.com/collections/frontpage/products.json"
            f"?limit=250&page={page}&sort_by=created-descending"
        )

        response = await fetch_json(self.session, url)
        if not isinstance(response, dict):
            return []

        products = response.get("products", [])
        assert isinstance(products, list)
        return products

    def _extract_volume(self, body_html: str) -> int:
        """Extract volume in milliliters from product description HTML.

        Returns 330 (default) if volume cannot be found.
        """
        if not body_html:
            return 330

        # Remove HTML tags to get plain text
        text = BeautifulSoup(body_html, "html.parser").get_text()

        # Try parse_milliliters utility (handles Japanese/English patterns)
        try:
            ml = parse_milliliters(text)
            if ml:
                return ml
        except Exception:
            pass

        # Default to 330ml if not found (~5% of products)
        self.logger.debug("Volume not found in description, defaulting to 330ml")
        return 330

    def _parse_product(self, product: dict) -> ShopBeer:
        """Parse a product from the Shopify API response."""
        # Get basic info
        title = product.get("title", "")
        handle = product.get("handle", "")

        # Skip if it's a beer set
        if is_beer_set(title):
            raise NotABeerError

        # Get first variant (all products have single "Default Title" variant)
        variants = product.get("variants", [])
        if not variants:
            raise NotABeerError

        variant = variants[0]

        # Parse price (comes as string like "720.00")
        price_str = variant.get("price", "0")
        try:
            price = int(float(price_str))
        except (ValueError, TypeError):
            raise NotABeerError

        if price == 0:
            raise NotABeerError

        # Check availability
        available = variant.get("available", False)
        inventory_quantity = variant.get("inventory_quantity")

        # Skip unavailable items
        if not available:
            raise NotABeerError

        # Build product URL
        url = f"https://narushimashoten.com/products/{handle}"

        # Get image URL if available
        image_url = None
        images = product.get("images")
        if images and isinstance(images, list) and len(images) > 0:
            img = images[0]
            if isinstance(img, dict):
                img_src = img.get("src", "")
                if img_src.startswith("//"):
                    image_url = "https:" + img_src
                elif not img_src.startswith("http"):
                    image_url = "https://narushimashoten.com" + img_src
                else:
                    image_url = img_src

        # Parse volume from description (95% have it)
        body_html = product.get("body_html", "")
        milliliters = self._extract_volume(body_html)

        # Get brewery from vendor field
        brewery_name = product.get("vendor", "") or None

        # Clean up the title for raw_name
        raw_name = clean_beer_name(title)

        return ShopBeer(
            raw_name=raw_name,
            url=url,
            milliliters=milliliters,
            price=price,
            quantity=1,  # Single bottles
            available=inventory_quantity if inventory_quantity else 1,
            brewery_name=brewery_name,
            image_url=image_url,
        )

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        """Iterate through all beers on Narushima Shoten."""
        page = 1
        seen_handles = set()

        while True:
            try:
                products = await self._fetch_products(page)

                # No more products means we've reached the end
                if not products:
                    break

                for product in products:
                    handle = product.get("handle")
                    if handle in seen_handles:
                        continue
                    seen_handles.add(handle)

                    try:
                        yield self._parse_product(product)
                    except NotABeerError:
                        continue
                    except Exception as e:
                        self.logger.error(f"Error parsing product {handle}: {e}")
                        continue

                page += 1

            except Exception as e:
                self.logger.error(f"Error fetching page {page}: {e}")
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        """Get or create database entry for this shop."""
        return db.insert_shop(
            name=self.display_name,
            url="https://narushimashoten.com",
            image_url="https://narushimashoten.com/cdn/shop/files/logo_new.png?v=1757060999&width=600",
            shipping_fee=1280,  # Kanto region (Tokyo area) - varies by region
            free_shipping_over=15000,
        )

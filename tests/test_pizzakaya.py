"""Tests for Pizzakaya scraper."""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from bs4 import BeautifulSoup

from strinks.api.shops import NotABeerError, ShopBeer
from strinks.api.shops.pizzakaya import Pizzakaya


class TestPizzakayaParsing:
    """Test parsing methods of Pizzakaya scraper."""

    @pytest.fixture
    def pizzakaya(self):
        """Create a Pizzakaya instance for testing."""
        session = AsyncMock(spec=aiohttp.ClientSession)
        return Pizzakaya(session)

    def test_parse_serving_draft(self, pizzakaya):
        """Test parsing draft beer servings."""
        ml, price = pizzakaya._parse_serving("300ml Draft ¥1200")
        assert ml == 300
        assert price == 1200

        ml, price = pizzakaya._parse_serving("473ml Draft ¥1700")
        assert ml == 473
        assert price == 1700

    def test_parse_serving_bottle(self, pizzakaya):
        """Test parsing bottle servings."""
        ml, price = pizzakaya._parse_serving("355ml Bottle ¥1800")
        assert ml == 355
        assert price == 1800

        ml, price = pizzakaya._parse_serving("375ml Bottle ¥3100")
        assert ml == 375
        assert price == 3100

    def test_parse_serving_invalid(self, pizzakaya):
        """Test that invalid servings raise NotABeerError."""
        with pytest.raises(NotABeerError):
            pizzakaya._parse_serving("No volume here ¥1200")

        with pytest.raises(NotABeerError):
            pizzakaya._parse_serving("300ml Draft")  # No price

        with pytest.raises(NotABeerError):
            pizzakaya._parse_serving("Invalid serving")

    def test_parse_beer_item_on_tap(self, pizzakaya):
        """Test parsing an on tap beer item - should return best value."""
        html = """
        <li class="pure-list-item">
            <h3 class="mb-0">
                <span class="tap-number">1.</span>
                Baird Pizzakaya Green Tea IPA
            </h3>
            <div class="text-left">
                <p class="caption text-gray mb-0">
                    Double IPA · 8.0% · <span class="bln">Numazu, Shizuoka</span>
                </p>
            </div>
            <div class="beer-servings mt-small">
                <p class="caption mb-0">300ml Draft ¥1200</p>
                <p class="caption mb-0">473ml Draft ¥1700</p>
            </div>
        </li>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = soup.find("li")

        beer = pizzakaya._parse_beer_item(item)

        assert beer is not None
        assert beer.raw_name == "Baird Pizzakaya Green Tea IPA"
        # 473ml for ¥1700 is better value (¥3.59/ml) than 300ml for ¥1200 (¥4.00/ml)
        assert beer.milliliters == 473
        assert beer.price == 1700
        assert beer.brewery_name == "Numazu"
        assert beer.price_per_ml == pytest.approx(1700 / 473, rel=1e-3)

    def test_parse_beer_item_bottle(self, pizzakaya):
        """Test parsing a bottle beer item with single serving."""
        html = """
        <li class="pure-list-item">
            <h3 class="mb-0">
                Jackie O's Coconut Champion Ground
            </h3>
            <div class="text-left">
                <p class="caption text-gray mb-0">
                    Imperial Stout · 12.0% · <span class="bln">Athens, OH</span>
                </p>
            </div>
            <div class="beer-servings mt-small">
                <p class="caption mb-0">375ml Bottle ¥3100</p>
            </div>
        </li>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = soup.find("li")

        beer = pizzakaya._parse_beer_item(item)

        assert beer is not None
        assert beer.raw_name == "Jackie O's Coconut Champion Ground"
        assert beer.milliliters == 375
        assert beer.price == 3100
        assert beer.brewery_name == "Athens"

    def test_parse_beer_item_skip_out(self, pizzakaya):
        """Test that 'Out' entries are skipped."""
        html = """
        <li class="pure-list-item">
            <h3 class="mb-0">
                <span class="tap-number">4.</span>
                Out...
            </h3>
            <div class="beer-servings mt-small">
                <p class="caption mb-0"></p>
            </div>
        </li>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = soup.find("li")

        beer = pizzakaya._parse_beer_item(item)
        assert beer is None

    def test_parse_beer_item_best_value_selection(self, pizzakaya):
        """Test that the best value serving is selected."""
        html = """
        <li class="pure-list-item">
            <h3 class="mb-0">Test Beer</h3>
            <div class="beer-servings mt-small">
                <p class="caption mb-0">250ml Draft ¥1000</p>
                <p class="caption mb-0">400ml Draft ¥1400</p>
                <p class="caption mb-0">500ml Draft ¥2000</p>
            </div>
        </li>
        """
        soup = BeautifulSoup(html, "html.parser")
        item = soup.find("li")

        beer = pizzakaya._parse_beer_item(item)

        assert beer is not None
        # 400ml for ¥1400 has best price/ml (¥3.50/ml)
        # vs 250ml for ¥1000 (¥4.00/ml)
        # vs 500ml for ¥2000 (¥4.00/ml)
        assert beer.milliliters == 400
        assert beer.price == 1400
        assert beer.price_per_ml == pytest.approx(1400 / 400, rel=1e-3)

    def test_shop_beer_properties(self, pizzakaya):
        """Test ShopBeer properties are calculated correctly."""
        beer = ShopBeer(
            raw_name="Test IPA",
            url="https://www.beermenus.com/qr_menus/4106",
            milliliters=473,
            price=1700,
            quantity=1,
            beer_name="Test IPA",
            brewery_name="Test Brewery",
        )

        assert beer.unit_price == 1700
        assert beer.price_per_ml == pytest.approx(1700 / 473, rel=1e-3)


class TestPizzakayaIntegration:
    """Integration tests for Pizzakaya scraper."""

    @pytest.mark.integration
    async def test_pizzakaya_structure(self):
        """Test that Pizzakaya shop has expected structure."""
        async with aiohttp.ClientSession() as session:
            shop = Pizzakaya(session)
            assert shop.short_name == "pizzakaya"
            assert shop.display_name == "Pizzakaya"
            assert shop.menu_url == "https://www.beermenus.com/qr_menus/4106"
            assert hasattr(shop, "iter_beers")
            assert hasattr(shop, "get_db_entry")

    @pytest.mark.integration
    async def test_pizzakaya_live_scraping(self):
        """Test scraping actual Pizzakaya menu (requires internet)."""
        async with aiohttp.ClientSession() as session:
            shop = Pizzakaya(session)

            beers = []
            async for beer in shop.iter_beers():
                beers.append(beer)
                # Just get a few to test
                if len(beers) >= 5:
                    break

            # Should find some beers
            assert len(beers) > 0

            # Check beer properties
            for beer in beers:
                assert beer.raw_name
                assert beer.url == shop.menu_url
                assert beer.milliliters > 0
                assert beer.price > 0
                assert beer.quantity == 1
                assert beer.price_per_ml > 0

    @pytest.mark.integration
    async def test_pizzakaya_with_mock_response(self):
        """Test Pizzakaya with mocked HTML response."""
        mock_html = """
        <!DOCTYPE html>
        <html>
        <body>
            <ul id="on_tap" class="pure-list">
                <li class="pure-list-item">
                    <h3 class="mb-0">
                        <span class="tap-number">1.</span>
                        Test Beer
                    </h3>
                    <div class="beer-servings mt-small">
                        <p class="caption mb-0">300ml Draft ¥1000</p>
                    </div>
                </li>
            </ul>
            <ul id="bottles" class="pure-list">
                <li class="pure-list-item">
                    <h3 class="mb-0">Test Bottle Beer</h3>
                    <div class="beer-servings mt-small">
                        <p class="caption mb-0">330ml Bottle ¥1500</p>
                    </div>
                </li>
            </ul>
        </body>
        </html>
        """

        with patch("strinks.api.shops.pizzakaya.fetch_text", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_html

            async with aiohttp.ClientSession() as session:
                shop = Pizzakaya(session)

                beers = []
                async for beer in shop.iter_beers():
                    beers.append(beer)

                # Should now have 2 beers (one per unique beer, not per serving)
                assert len(beers) == 2

                # Check on tap beer (only one serving, so it's selected)
                assert beers[0].raw_name == "Test Beer"
                assert beers[0].milliliters == 300
                assert beers[0].price == 1000

                # Check bottle beer (only one serving, so it's selected)
                assert beers[1].raw_name == "Test Bottle Beer"
                assert beers[1].milliliters == 330
                assert beers[1].price == 1500

    @pytest.mark.integration
    async def test_pizzakaya_in_shop_map(self):
        """Test that Pizzakaya is discovered in the shop map."""
        from strinks.api.shops import get_shop_map

        async with aiohttp.ClientSession() as session:
            shop_map = await get_shop_map(session)

            # Check that pizzakaya is in the map
            assert "pizzakaya" in shop_map

            # Check that it can be instantiated
            pizzakaya_factory = shop_map["pizzakaya"]
            pizzakaya = pizzakaya_factory(session)
            assert pizzakaya.short_name == "pizzakaya"
            assert pizzakaya.display_name == "Pizzakaya"

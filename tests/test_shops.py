"""Tests for shop scrapers and ShopBeer model."""

import aiohttp
import pytest

from strinks.api.shops import NotABeerError, ShopBeer, get_shop_map


class TestShopBeer:
    def test_shop_beer_creation(self):
        """Test creating a valid ShopBeer."""
        beer = ShopBeer(
            raw_name="Test Beer 500ml ¥800",
            url="https://shop.com/beer/1",
            milliliters=500,
            price=800,
            quantity=1,
            available=10,
            beer_name="Test Beer",
            brewery_name="Test Brewery",
            image_url="https://shop.com/beer1.jpg",
        )

        assert beer.unit_price == 800
        assert beer.price_per_ml == 800 / 500
        assert beer.beer_name == "Test Beer"

    def test_shop_beer_validation(self):
        """Test that invalid ShopBeer raises NotABeerError."""
        with pytest.raises(NotABeerError):
            # Zero milliliters should fail
            ShopBeer(raw_name="Invalid", url="https://shop.com/invalid", milliliters=0, price=500, quantity=1)

        with pytest.raises(NotABeerError):
            # Zero price should fail
            ShopBeer(raw_name="Invalid", url="https://shop.com/invalid", milliliters=350, price=0, quantity=1)

        with pytest.raises(NotABeerError):
            # Zero quantity should fail
            ShopBeer(raw_name="Invalid", url="https://shop.com/invalid", milliliters=350, price=500, quantity=0)

    def test_untappd_queries(self):
        """Test generating Untappd search queries."""
        beer = ShopBeer(
            raw_name="ヨロッコビール ホワイトエール 350ml",
            url="https://shop.com/beer/2",
            milliliters=350,
            price=600,
            quantity=1,
            beer_name="ホワイトエール",
            brewery_name="ヨロッコビール",
        )

        queries = list(beer.iter_untappd_queries())

        # Should include brewery + beer name
        assert any("ヨロッコビール ホワイトエール" in q for q in queries)
        # Should include raw name
        assert any("ホワイトエール 350ml" in q for q in queries)
        # Should try English translation from BREWERY_JP_EN
        assert any("yorocco" in q.lower() for q in queries)

    def test_untappd_queries_no_duplicates(self):
        """Test that Untappd queries don't have duplicates."""
        beer = ShopBeer(
            raw_name="Test Beer",
            url="https://shop.com/beer/3",
            milliliters=350,
            price=500,
            quantity=1,
            beer_name="Test Beer",
            brewery_name="Test",
        )

        queries = list(beer.iter_untappd_queries())
        # Check no duplicates
        assert len(queries) == len(set(queries))


class TestShopMap:
    async def test_get_shop_map(self):
        """Test that shop map contains expected shops."""
        async with aiohttp.ClientSession() as session:
            shop_map = await get_shop_map(session)

            # Check some known shops
            assert "volta" in shop_map
            assert "craft" in shop_map
            assert "digtheline" in shop_map
            assert "narushimashoten" in shop_map

            # Check that location-based shops are expanded
            # IBrew should have multiple locations
            ibrew_shops = [k for k in shop_map if k.startswith("ibrew-")]
            assert len(ibrew_shops) > 0, "Should have IBrew locations"

            # CBM should have multiple locations
            cbm_shops = [k for k in shop_map if k.startswith("cbm-")]
            assert len(cbm_shops) > 0, "Should have CBM locations"

    async def test_shop_instantiation(self):
        """Test that shops can be instantiated."""
        async with aiohttp.ClientSession() as session:
            shop_map = await get_shop_map(session)

            # Test regular shop
            volta_factory = shop_map["volta"]
            volta = volta_factory(session)
            assert volta.short_name == "volta"
            assert volta.display_name == "Beer Volta"

            # Test CBM with location
            if "cbm-jimbocho" in shop_map:
                cbm_factory = shop_map["cbm-jimbocho"]
                cbm = cbm_factory(session)
                assert cbm.location == "jimbocho"


class TestShopIntegration:
    """Integration tests for shop scrapers."""

    @pytest.mark.integration
    async def test_volta_structure(self):
        """Test that Volta shop has expected structure."""
        from strinks.api.shops.volta import Volta

        async with aiohttp.ClientSession() as session:
            shop = Volta(session)
            assert shop.short_name == "volta"
            assert shop.display_name == "Beer Volta"
            assert hasattr(shop, "iter_beers")
            assert hasattr(shop, "get_db_entry")

    @pytest.mark.integration
    async def test_ibrew_initialization(self):
        """Test IBrew initialization with different parameters."""
        from datetime import date

        from strinks.api.shops.ibrew import IBrew

        async with aiohttp.ClientSession() as session:
            # Default initialization
            shop1 = IBrew(session=session)
            assert shop1.location == "ebisu"
            assert isinstance(shop1.day, date)

            # With specific location
            shop2 = IBrew(session=session, location="shinjuku")
            assert shop2.location == "shinjuku"

            # With specific day
            test_day = date(2024, 1, 15)
            shop3 = IBrew(session=session, day=test_day)
            assert shop3.day == test_day

    @pytest.mark.integration
    async def test_narushimashoten_scraper(self):
        """Test Narushima Shoten scraper fetches and parses products correctly."""
        from strinks.api.shops.narushimashoten import NarushimaShoten

        async with aiohttp.ClientSession() as session:
            shop = NarushimaShoten(session)

            # Verify shop metadata
            assert shop.short_name == "narushimashoten"
            assert shop.display_name == "Narushima Shoten"

            # Scrape first few beers
            count = 0
            beers_with_volume = 0
            beers_with_default_volume = 0

            async for beer in shop.iter_beers():
                count += 1

                # Validate required fields
                assert beer.raw_name
                assert beer.url.startswith("https://narushimashoten.com/products/")
                assert beer.price > 0
                assert beer.milliliters > 0
                assert beer.quantity == 1

                # Track volume extraction
                if beer.milliliters == 330:
                    beers_with_default_volume += 1
                else:
                    beers_with_volume += 1

                # Only test first 10 to keep test fast
                if count >= 10:
                    break

            # Should have scraped some beers
            assert count > 0, "Should scrape at least one beer"

            # Volume extraction works but not all products have it in descriptions
            # Expect at least 20% extraction rate (rest use 330ml default)
            assert beers_with_volume >= 2, f"Expected at least 2/10 beers with volume, got {beers_with_volume}"

    @pytest.mark.integration
    async def test_narushimashoten_volume_extraction(self):
        """Test volume extraction from product descriptions."""
        from strinks.api.shops.narushimashoten import NarushimaShoten

        async with aiohttp.ClientSession() as session:
            shop = NarushimaShoten(session)

            # Test volume extraction from various formats
            test_cases = [
                ("473ml缶での販売", 473),
                ("容量：375ml", 375),
                ("350ml缶", 350),
                ("360ml", 360),
                ("", 330),  # Empty should default to 330
                ("No volume info here", 330),  # No volume should default to 330
            ]

            for body_html, expected_ml in test_cases:
                result = shop._extract_volume(body_html)
                assert result == expected_ml, f"Expected {expected_ml}ml from '{body_html}', got {result}ml"

"""Tests for shop scrapers and ShopBeer model."""

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
    def test_get_shop_map(self):
        """Test that shop map contains expected shops."""
        shop_map = get_shop_map()

        # Check some known shops
        assert "volta" in shop_map
        assert "craft" in shop_map
        assert "ibrew" in shop_map
        assert "digtheline" in shop_map

        # Check CBM locations
        cbm_shops = [k for k in shop_map if k.startswith("cbm-")]
        assert len(cbm_shops) > 0

    def test_shop_instantiation(self):
        """Test that shops can be instantiated."""
        shop_map = get_shop_map()

        # Test regular shop
        volta_factory = shop_map["volta"]
        volta = volta_factory()
        assert volta.short_name == "volta"
        assert volta.display_name == "Beer Volta"

        # Test CBM with location
        if "cbm-jimbocho" in shop_map:
            cbm_factory = shop_map["cbm-jimbocho"]
            cbm = cbm_factory()
            assert cbm.location == "jimbocho"


class TestShopIntegration:
    """Integration tests for shop scrapers."""

    @pytest.mark.integration
    def test_volta_structure(self):
        """Test that Volta shop has expected structure."""
        from strinks.api.shops.volta import Volta

        shop = Volta()
        assert shop.short_name == "volta"
        assert shop.display_name == "Beer Volta"
        assert hasattr(shop, "iter_beers")
        assert hasattr(shop, "get_db_entry")

    @pytest.mark.integration
    def test_ibrew_initialization(self):
        """Test IBrew initialization with different parameters."""
        from datetime import date

        from strinks.api.shops.ibrew import IBrew

        # Default initialization
        shop1 = IBrew()
        assert shop1.location == "ebisu"
        assert isinstance(shop1.day, date)

        # With specific location
        shop2 = IBrew(location="shinjuku")
        assert shop2.location == "shinjuku"

        # With specific day
        test_day = date(2024, 1, 15)
        shop3 = IBrew(day=test_day)
        assert shop3.day == test_day

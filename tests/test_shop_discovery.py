"""Integration tests for shop discovery."""

import aiohttp
import pytest

from strinks.api.shops import Shop
from strinks.api.shops.discovery import discover_shop_classes, get_shop_map_dynamic


class TestShopDiscovery:
    """Test shop discovery mechanisms."""

    def test_discover_shop_classes(self):
        """Test that shop classes can be discovered dynamically."""
        shops = discover_shop_classes()

        assert len(shops) > 0, "Should discover at least one shop"

        # All discovered items should be Shop subclasses
        for name, shop_class in shops.items():
            assert issubclass(shop_class, Shop)
            assert shop_class.short_name == name

    async def test_dynamic_shop_map(self):
        """Test that dynamic shop map creates proper callables."""
        async with aiohttp.ClientSession() as session:
            shop_map = await get_shop_map_dynamic(session)

        assert len(shop_map) > 0, "Should have at least one shop"

        # All values should be callable
        for shop_name, factory in shop_map.items():
            assert callable(factory), f"{shop_name} factory is not callable"

        # Should have regular shops and CBM locations
        has_regular = any(not k.startswith(("cbm-", "ibrew-")) for k in shop_map)
        has_cbm = any(k.startswith("cbm-") for k in shop_map)

        assert has_regular, "Should have regular shops"
        assert has_cbm, "Should have CBM locations"

    @pytest.mark.integration
    async def test_all_shops_instantiable(self):
        """Test that all discovered shops can be instantiated."""
        async with aiohttp.ClientSession() as session:
            shop_map = await get_shop_map_dynamic(session)

            for shop_name, shop_factory in shop_map.items():
                shop = shop_factory(session)
                assert isinstance(shop, Shop), f"{shop_name} is not a Shop instance"
                assert hasattr(shop, "iter_beers"), f"{shop_name} missing iter_beers"
                assert hasattr(shop, "get_db_entry"), f"{shop_name} missing get_db_entry"

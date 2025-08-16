"""Auto-discovery mechanism for shop scrapers."""

import importlib
import inspect
import pkgutil
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import Shop


def discover_shop_classes(package_path: Path | None = None) -> dict[str, type["Shop"]]:
    """Discover all Shop subclasses in the shops package.

    Args:
        package_path: Path to the shops package. If None, uses current package.

    Returns:
        Dictionary mapping shop short_name to shop class.
    """
    from . import Shop  # Import at runtime to avoid circular import

    if package_path is None:
        package_path = Path(__file__).parent

    shop_classes: dict[str, type[Shop]] = {}

    # Import all modules in the shops package
    for module_info in pkgutil.iter_modules([str(package_path)]):
        if module_info.name in ["__init__", "discovery"]:
            continue

        try:
            module = importlib.import_module(f".{module_info.name}", package="strinks.api.shops")

            # Find all Shop subclasses in the module
            for _, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Shop)
                    and obj != Shop
                    and hasattr(obj, "short_name")
                    and not inspect.isabstract(obj)
                ):
                    shop_classes[obj.short_name] = obj

        except Exception as e:
            # Log but don't fail if a module can't be imported
            print(f"Warning: Could not import shop module {module_info.name}: {e}")

    return shop_classes


def get_shop_map_dynamic() -> dict[str, Callable[[], "Shop"]]:
    """Get shop map using dynamic discovery.

    Returns:
        Dictionary mapping shop names to callables that create shop instances.
    """
    shop_classes = discover_shop_classes()
    shop_map: dict[str, Callable[[], Shop]] = {}

    for short_name, shop_class in shop_classes.items():
        # Check if the shop class has a get_locations method for multiple locations
        if hasattr(shop_class, "get_locations") and callable(shop_class.get_locations):
            try:
                locations = shop_class.get_locations()
                # Add an entry for each location
                for location in locations:
                    # Assume location is passed as a parameter to the constructor
                    location_key = f"{short_name}-{location.lstrip(f'{short_name}-')}"
                    shop_map[location_key] = partial(shop_class, location=location)  # type: ignore[call-arg]
            except Exception as e:
                # If get_locations fails, just add the class normally
                print(f"Warning: Could not get locations for {short_name}: {e}")
                shop_map[short_name] = shop_class
        else:
            # Regular shop without multiple locations
            shop_map[short_name] = shop_class

    return shop_map


def validate_discovered_shops(discovered: dict[str, Any], expected: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Validate discovered shops against expected shops.

    Args:
        discovered: Dynamically discovered shop map
        expected: Expected shop map (from hardcoded list)

    Returns:
        Tuple of (missing_shops, extra_shops)
    """
    discovered_keys = set(discovered.keys())
    expected_keys = set(expected.keys())

    missing = expected_keys - discovered_keys
    extra = discovered_keys - expected_keys

    return missing, extra

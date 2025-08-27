from enum import Enum


class BeerProfile(Enum):
    """Beer profile types for sorting offerings."""

    ON_SALE = "on_sale"
    FIRST_DIBS = "first_dibs"
    CHEAPEST = "cheapest"
    GREAT_DEALS = "great_deals"
    BALANCED = "balanced"
    SALARYMAN = "salaryman"  # Default
    HIGH_CLASS = "high_class"
    NO_EXPENSE = "no_expense"

    def get_value_factor(self) -> float | None:
        """Get the value factor for cospa-based profiles.

        Returns None for special profiles that don't use value factor.
        """
        mapping = {
            BeerProfile.ON_SALE: None,  # Special logic
            BeerProfile.FIRST_DIBS: 0,
            BeerProfile.CHEAPEST: 1,
            BeerProfile.GREAT_DEALS: 2,
            BeerProfile.BALANCED: 4,
            BeerProfile.SALARYMAN: 8,
            BeerProfile.HIGH_CLASS: 12,
            BeerProfile.NO_EXPENSE: 99999999999,
        }
        return mapping[self]

    def get_display_name(self) -> str:
        """Get the human-readable display name."""
        mapping = {
            BeerProfile.ON_SALE: "On Sale",
            BeerProfile.FIRST_DIBS: "First Dibs",
            BeerProfile.CHEAPEST: "The Cheapest Stuff",
            BeerProfile.GREAT_DEALS: "Great Deals",
            BeerProfile.BALANCED: "Balanced Drinker",
            BeerProfile.SALARYMAN: "Salaryman Connoisseur",
            BeerProfile.HIGH_CLASS: "High Class",
            BeerProfile.NO_EXPENSE: "I Spare No Expense",
        }
        return mapping[self]

    @classmethod
    def from_string(cls, value: str) -> "BeerProfile":
        """Create profile from string value."""
        try:
            return cls(value)
        except ValueError:
            # Default to SALARYMAN if invalid
            return cls.SALARYMAN

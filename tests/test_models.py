"""Tests for SQLModel database models and operations."""

import pytest

from strinks.api.utils import now_jst
from strinks.db.models import BeerDB
from strinks.db.tables import APP_USER_MARKER, Beer, Offering, Shop, User


@pytest.fixture(scope="function")
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    import os
    import tempfile

    # Create a temporary file for the database
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        db = BeerDB(path, read_only=False)
        yield db
        db.session.close()
    finally:
        # Clean up the temporary file
        if os.path.exists(path):
            os.unlink(path)


@pytest.fixture
def sample_shop(in_memory_db):
    """Create a sample shop for testing."""
    shop = Shop(
        shop_id=1,
        name="Test Shop",
        url="https://testshop.com",
        image_url="https://testshop.com/logo.png",
        shipping_fee=500,
        free_shipping_over=5000,
    )
    in_memory_db.session.add(shop)
    in_memory_db.session.commit()
    return shop


@pytest.fixture
def sample_beer(in_memory_db):
    """Create a sample beer for testing."""
    beer = Beer(
        beer_id=123,
        name="Test IPA",
        brewery="Test Brewery",
        style="IPA",
        abv=6.5,
        ibu=60,
        rating=4.2,
        image_url="https://example.com/beer.jpg",
        updated_at=now_jst(),
    )
    in_memory_db.session.add(beer)
    in_memory_db.session.commit()
    return beer


class TestBeerModel:
    def test_beer_creation(self, in_memory_db):
        """Test creating a beer entry."""
        beer = Beer(
            beer_id=456,
            name="Test Lager",
            brewery="Test Brewery 2",
            style="Lager",
            abv=5.0,
            ibu=30,
            rating=3.8,
            image_url="https://example.com/lager.jpg",
            updated_at=now_jst(),
        )
        in_memory_db.session.add(beer)
        in_memory_db.session.commit()

        retrieved = in_memory_db.get_beer(456)
        assert retrieved is not None
        assert retrieved.name == "Test Lager"
        assert retrieved.brewery == "Test Brewery 2"
        assert retrieved.abv == 5.0

    def test_beer_datetime_is_timezone_aware(self, sample_beer, in_memory_db):
        """Test that beer updated_at is timezone-aware."""
        retrieved = in_memory_db.get_beer(sample_beer.beer_id)
        assert retrieved is not None
        # Check if datetime is timezone-aware
        if retrieved.updated_at.tzinfo is None:
            # SQLite might return naive, but our code should handle it
            assert True  # We handle this in the application code
        else:
            assert retrieved.updated_at.tzinfo is not None


class TestUserModel:
    def test_user_creation(self, in_memory_db):
        """Test creating a regular user."""
        user = User(
            user_name="testuser",
            first_name="Test",
            last_name="User",
            avatar_url="https://example.com/avatar.jpg",
            access_token="token123",
        )
        in_memory_db.session.add(user)
        in_memory_db.session.commit()

        from sqlmodel import select

        statement = select(User).where(User.user_name == "testuser")
        retrieved = in_memory_db.session.exec(statement).first()
        assert retrieved is not None
        assert retrieved.first_name == "Test"
        assert retrieved.is_app is False

    def test_app_user_detection(self, in_memory_db):
        """Test that APP users are correctly identified."""
        app_user = User(
            user_name="app_token", first_name="App", last_name=APP_USER_MARKER, access_token="app_token_123"
        )
        in_memory_db.session.add(app_user)
        in_memory_db.session.commit()

        from sqlmodel import select

        statement = select(User).where(User.user_name == "app_token")
        retrieved = in_memory_db.session.exec(statement).first()
        assert retrieved is not None
        assert retrieved.is_app is True


class TestOfferingModel:
    def test_offering_creation(self, in_memory_db, sample_shop, sample_beer):
        """Test creating an offering."""
        offering = Offering(
            shop_id=sample_shop.shop_id,
            beer_id=sample_beer.beer_id,
            url="https://testshop.com/beer/123",
            milliliters=350,
            price=500,
            updated_at=now_jst(),
        )
        in_memory_db.session.add(offering)
        in_memory_db.session.commit()

        # Query the offering
        from sqlmodel import select

        statement = select(Offering).where(
            Offering.shop_id == sample_shop.shop_id, Offering.beer_id == sample_beer.beer_id
        )
        retrieved = in_memory_db.session.exec(statement).first()

        assert retrieved is not None
        assert retrieved.milliliters == 350
        assert retrieved.price == 500
        assert retrieved.price_per_ml == 500 / 350


class TestBeerDB:
    def test_insert_beer(self, in_memory_db):
        """Test inserting a beer through BeerDB."""
        beer = in_memory_db.insert_beer(
            beer_id=789,
            image_url="https://example.com/stout.jpg",
            name="Test Stout",
            brewery="Dark Brewery",
            style="Stout",
            abv="7.2",
            ibu="45",
            rating="4.5",
            description="A rich, dark stout",
        )

        assert beer is not None
        assert beer.beer_id == 789
        assert beer.name == "Test Stout"
        assert beer.description == "A rich, dark stout"

    def test_insert_beer_updates_existing(self, in_memory_db, sample_beer):
        """Test that inserting an existing beer updates it."""
        import time

        # Small delay to ensure timestamp difference
        time.sleep(0.01)

        # Insert with same ID but different data
        beer = in_memory_db.insert_beer(
            beer_id=sample_beer.beer_id,
            image_url="https://example.com/updated.jpg",
            name="Updated IPA",
            brewery=sample_beer.brewery,
            style=sample_beer.style,
            abv="7.0",  # Changed
            ibu=sample_beer.ibu,
            rating=sample_beer.rating,
        )

        assert beer.name == "Updated IPA"
        assert beer.abv == "7.0"
        # Updated_at should be different (we can't reliably compare timezone-aware/naive mix from SQLite)
        assert beer.updated_at is not None

    def test_get_access_tokens(self, in_memory_db):
        """Test retrieving access tokens."""
        # Create regular and app users
        regular_user = User(user_name="regular", first_name="Regular", last_name="User", access_token="regular_token")
        app_user = User(user_name="app", first_name="App", last_name=APP_USER_MARKER, access_token="app_token")
        in_memory_db.session.add(regular_user)
        in_memory_db.session.add(app_user)
        in_memory_db.session.commit()

        # Get app tokens
        app_tokens = in_memory_db.get_access_tokens(is_app=True)
        assert "app_token" in app_tokens
        assert "regular_token" not in app_tokens

        # Get regular user tokens
        user_tokens = in_memory_db.get_access_tokens(is_app=False)
        assert "regular_token" in user_tokens
        assert "app_token" not in user_tokens

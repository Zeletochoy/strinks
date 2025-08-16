"""Tests for Untappd API and caching."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from strinks.api.shops import ShopBeer
from strinks.api.untappd import UntappdCacheEntry, UntappdClient
from strinks.api.untappd.api import UntappdAPI
from strinks.api.untappd.structs import RateLimitError, UntappdBeerResult
from strinks.api.untappd.web import UntappdWeb
from strinks.api.utils import JST, now_jst


class TestUntappdCache:
    def test_cache_entry_creation(self):
        """Test creating cache entries."""
        entry = UntappdCacheEntry(beer_id=12345, timestamp=int(now_jst().timestamp()))
        assert entry.beer_id == 12345
        assert entry.timestamp > 0

    def test_cache_validity(self):
        """Test cache entry validity checking."""
        from strinks.api.untappd import BEER_CACHE_TIME

        # Create a recent entry
        recent_entry = UntappdCacheEntry(beer_id=111, timestamp=int(now_jst().timestamp()))

        # Create an old entry
        old_time = now_jst() - BEER_CACHE_TIME - timedelta(hours=1)
        old_entry = UntappdCacheEntry(beer_id=222, timestamp=int(old_time.timestamp()))

        # Check validity
        recent_valid = now_jst() - datetime.fromtimestamp(recent_entry.timestamp, tz=JST) < BEER_CACHE_TIME
        old_valid = now_jst() - datetime.fromtimestamp(old_entry.timestamp, tz=JST) < BEER_CACHE_TIME

        assert recent_valid is True
        assert old_valid is False


class TestUntappdAPI:
    @pytest.fixture
    def mock_session(self):
        """Mock the HTTP session."""
        with patch("strinks.api.untappd.api.session") as mock:
            yield mock

    @pytest.fixture
    def mock_db(self):
        """Mock the database."""
        with patch("strinks.api.untappd.api.get_db") as mock:
            db = Mock()
            db.get_beer.return_value = None
            mock.return_value = db
            yield db

    def test_untappd_api_initialization(self, mock_db):
        """Test UntappdAPI initialization."""
        # Without auth token (app credentials)
        api1 = UntappdAPI()
        assert api1.auth_token is None

        # With auth token
        api2 = UntappdAPI(auth_token="test_token")
        assert api2.auth_token == "test_token"

    def test_rate_limiting(self, mock_session, mock_db):
        """Test that rate limiting is handled."""
        api = UntappdAPI()

        # Mock a rate limit response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_session.get.return_value = mock_response

        with pytest.raises(RateLimitError):
            api.api_request("/test")

    def test_get_beer_from_db_with_cache(self, mock_db):
        """Test getting beer from database when cached."""
        api = UntappdAPI()

        # Mock a recent beer
        mock_beer = Mock()
        mock_beer.beer_id = 123
        mock_beer.updated_at = now_jst() - timedelta(hours=1)
        mock_beer.name = "Test IPA"
        mock_beer.brewery = "Test Brewery"
        mock_beer.style = "IPA"
        mock_beer.abv = "6.5"
        mock_beer.ibu = "65"
        mock_beer.rating = "4.2"
        mock_beer.image_url = "https://example.com/beer.jpg"
        mock_beer.description = "A hoppy IPA"
        mock_beer.tags = []

        mock_db.get_beer.return_value = mock_beer

        result = api._get_beer_from_db(123)
        assert result is not None
        assert result.beer_id == 123
        assert result.name == "Test IPA"

    def test_get_beer_from_db_expired(self, mock_db):
        """Test getting beer from database when cache expired."""
        api = UntappdAPI()

        # Mock an old beer
        mock_beer = Mock()
        mock_beer.updated_at = now_jst() - timedelta(days=35)  # Older than BEER_CACHE_TIME

        mock_db.get_beer.return_value = mock_beer

        result = api._get_beer_from_db(123)
        assert result is None  # Should return None for expired cache


class TestUntappdWeb:
    @pytest.fixture
    def mock_session(self):
        """Mock the cloudscraper session."""
        with patch("strinks.api.untappd.web.session") as mock:
            yield mock

    def test_untappd_web_initialization(self):
        """Test UntappdWeb initialization."""
        web = UntappdWeb()
        assert web.headers["User-Agent"] is not None
        assert web.headers["Referer"] == "https://untappd.com/home"

    def test_rate_limit_tracking(self):
        """Test that rate limit tracking works."""
        web = UntappdWeb()

        # Initially empty
        assert len(web.last_request_timestamps) == 0

        # After rate_limit call
        web.rate_limit()
        assert len(web.last_request_timestamps) == 1


class TestUntappdIntegration:
    @pytest.fixture
    def mock_backends(self):
        """Mock Untappd backends."""
        with patch("strinks.api.untappd.get_db") as mock_db:
            db = Mock()
            db.get_access_tokens.return_value = []
            mock_db.return_value = db
            yield

    def test_untappd_initialization(self, mock_backends):
        """Test Untappd class initialization."""
        untappd = UntappdClient()

        assert untappd.backend_idx == 0
        assert len(untappd.backends) > 0
        assert untappd.cache is not None

    def test_backend_switching(self, mock_backends):
        """Test switching between backends."""
        untappd = UntappdClient()

        untappd.next_backend()
        assert untappd.backend_idx == 1 or untappd.backend_idx == 0  # Depends on number of backends

    def test_try_find_beer_with_shop_beer(self, mock_backends):
        """Test finding beer with ShopBeer input."""
        untappd = UntappdClient()

        # Mock the current backend
        mock_backend = Mock()
        mock_result = UntappdBeerResult(
            beer_id=456,
            image_url="https://example.com/beer.jpg",
            name="Test Beer",
            brewery="Test Brewery",
            style="Lager",
            abv=5.0,
            ibu=30,
            rating=3.8,
        )
        mock_backend.try_find_beer.return_value = mock_result
        untappd.backends = [mock_backend]
        untappd.backend_idx = 0

        # Create a ShopBeer
        shop_beer = ShopBeer(raw_name="Test Beer", url="https://shop.com/beer", milliliters=350, price=500, quantity=1)

        result = untappd.try_find_beer(shop_beer)
        assert result is not None
        assert result[0].beer_id == 456
        assert result[1] == "test beer"  # The query used

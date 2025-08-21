"""Tests for Untappd API and caching."""

from datetime import timedelta
from unittest.mock import Mock, patch

import aiohttp
import pytest

from strinks.api.shops import ShopBeer
from strinks.api.untappd import UntappdClient
from strinks.api.untappd.api import UntappdAPI
from strinks.api.untappd.cache import CacheStatus, UntappdSQLiteCache
from strinks.api.untappd.structs import RateLimitError, UntappdBeerResult
from strinks.api.untappd.web import UntappdWeb
from strinks.api.utils import now_jst
from strinks.db.tables import UntappdCache


class TestUntappdSQLiteCache:
    @pytest.fixture(scope="function")
    def in_memory_db(self):
        """Create an in-memory SQLite database for testing."""
        import tempfile

        from strinks.db.models import BeerDB

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = BeerDB(tmp.name, read_only=False)
            yield db
            db.session.close()

    @pytest.fixture
    def cache(self, in_memory_db):
        """Create a cache instance with test database."""
        from strinks.api.untappd import BEER_CACHE_TIME

        return UntappdSQLiteCache(in_memory_db, cache_duration=BEER_CACHE_TIME)

    def test_cache_miss(self, cache):
        """Test cache miss for non-existent query."""
        beer_id, status = cache.get("nonexistent_query")
        assert beer_id is None
        assert status == CacheStatus.MISS

    def test_cache_hit(self, cache):
        """Test cache hit for existing query."""
        # Add entry to cache
        cache.set("test_query", 12345)

        # Retrieve from cache
        beer_id, status = cache.get("test_query")
        assert beer_id == 12345
        assert status == CacheStatus.HIT

    def test_cache_not_found(self, cache):
        """Test caching a not-found result."""
        # Cache a None result (beer not found)
        cache.set("not_found_query", None)

        # Retrieve from cache
        beer_id, status = cache.get("not_found_query")
        assert beer_id is None
        assert status == CacheStatus.HIT

    def test_cache_expired(self, cache, in_memory_db):
        """Test expired cache entry."""
        from strinks.api.untappd import BEER_CACHE_TIME

        # Add entry with past expiry
        now = now_jst()
        expired_time = now - BEER_CACHE_TIME - timedelta(hours=1)

        entry = UntappdCache(
            query="expired_query", beer_id=999, created_at=expired_time, expires_at=expired_time + BEER_CACHE_TIME
        )
        in_memory_db.session.add(entry)
        in_memory_db.session.commit()

        # Check it returns EXPIRED
        beer_id, status = cache.get("expired_query")
        assert beer_id is None
        assert status == CacheStatus.EXPIRED


class TestUntappdAPI:
    @pytest.fixture
    def mock_session(self):
        """Mock the HTTP session."""
        # No longer patching a global session since we use aiohttp
        mock = Mock()
        yield mock

    @pytest.fixture
    def mock_db(self):
        """Mock the database."""
        with patch("strinks.api.untappd.api.get_db") as mock:
            db = Mock()
            db.get_beer.return_value = None
            mock.return_value = db
            yield db

    async def test_untappd_api_initialization(self, mock_db):
        """Test UntappdAPI initialization."""
        async with aiohttp.ClientSession() as session:
            # Without auth token (app credentials)
            api1 = UntappdAPI(session)
            assert api1.auth_token is None

            # With auth token
            api2 = UntappdAPI(session, auth_token="test_token")
            assert api2.auth_token == "test_token"

    @pytest.mark.asyncio
    async def test_rate_limiting(self, mock_session, mock_db):
        """Test that rate limiting is handled."""
        api = UntappdAPI(session=mock_session)

        # Mock a rate limit response with async context manager
        mock_response = Mock()
        mock_response.status = 429

        # Create async context manager mock
        async def async_enter(self):
            return mock_response

        async def async_exit(self, exc_type, exc_val, exc_tb):
            return None

        mock_get = Mock()
        mock_get.__aenter__ = async_enter
        mock_get.__aexit__ = async_exit
        mock_session.get.return_value = mock_get

        with pytest.raises(RateLimitError):
            await api.api_request("/test")

    async def test_get_beer_from_db_with_cache(self, mock_db):
        """Test getting beer from database when cached."""
        async with aiohttp.ClientSession() as session:
            api = UntappdAPI(session)

            # Mock a recent beer
            mock_beer = Mock()
            mock_beer.beer_id = 123
            mock_beer.updated_at = now_jst() - timedelta(hours=1)
            mock_beer.name = "Test IPA"
            mock_beer.brewery_name = "Test Brewery"
            mock_beer.brewery_id = 456
            mock_beer.brewery_country = "United States"
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

    async def test_get_beer_from_db_expired(self, mock_db):
        """Test getting beer from database when cache expired."""
        async with aiohttp.ClientSession() as session:
            api = UntappdAPI(session)

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

    async def test_untappd_initialization(self, mock_backends):
        """Test Untappd class initialization."""
        async with aiohttp.ClientSession() as session:
            untappd = UntappdClient(session)

            assert untappd.backend_idx == 0
            assert len(untappd.backends) > 0
            assert untappd.cache is not None

    async def test_backend_switching(self, mock_backends):
        """Test switching between backends."""
        async with aiohttp.ClientSession() as session:
            untappd = UntappdClient(session)

            # next_backend is now async
            await untappd.next_backend()
            assert untappd.backend_idx == 1 or untappd.backend_idx == 0  # Depends on number of backends

    async def test_try_find_beer_with_shop_beer(self, mock_backends):
        """Test finding beer with ShopBeer input."""
        async with aiohttp.ClientSession() as session:
            untappd = UntappdClient(session)

            # Mock the cache to return MISS (not cached)
            mock_cache = Mock()
            mock_cache.get.return_value = (None, CacheStatus.MISS)
            untappd.cache = mock_cache

            # Mock the current backend
            mock_backend = Mock()
            mock_result = UntappdBeerResult(
                beer_id=456,
                image_url="https://example.com/beer.jpg",
                name="Test Beer",
                brewery="Test Brewery",
                brewery_id=789,
                brewery_country="United States",
                style="Lager",
                abv=5.0,
                ibu=30,
                rating=3.8,
            )

            # Mock async try_find_beer method
            async def mock_try_find_beer(query):
                return mock_result

            mock_backend.try_find_beer = mock_try_find_beer
            untappd.backends = [mock_backend]
            untappd.backend_idx = 0

            # Create a ShopBeer
            shop_beer = ShopBeer(
                raw_name="Test Beer", url="https://shop.com/beer", milliliters=350, price=500, quantity=1
            )

            # try_find_beer is now async
            result = await untappd.try_find_beer(shop_beer)
            assert result is not None
            assert result[0].beer_id == 456
            assert result[1] == "test beer"  # The query used

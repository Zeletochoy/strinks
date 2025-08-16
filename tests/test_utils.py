"""Tests for utility functions."""

from datetime import datetime
from unittest.mock import Mock, patch

from strinks.api.utils import JST, RateLimitedSession, get_retrying_session, now_jst


class TestDateTimeUtils:
    def test_now_jst(self):
        """Test that now_jst returns JST timezone-aware datetime."""
        dt = now_jst()

        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None
        assert dt.tzinfo == JST

    def test_jst_timezone(self):
        """Test JST timezone properties."""
        # Create a datetime with JST
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=JST)

        # JST is UTC+9
        utc_offset = dt.utcoffset()
        assert utc_offset.total_seconds() == 9 * 3600


class TestRetryingSession:
    def test_get_retrying_session(self):
        """Test that get_retrying_session returns a session with retry."""
        session = get_retrying_session()

        assert session is not None
        assert isinstance(session, RateLimitedSession)
        assert hasattr(session, "get")
        assert hasattr(session, "post")

        # Check that retry is configured
        assert len(session.adapters) > 0

    def test_rate_limiting(self):
        """Test that rate limiting works correctly."""
        import time

        session = get_retrying_session(rate_limit=0.1)

        # Test the internal rate limiting logic directly
        domain = "example.com"

        # First request should go through immediately
        start = time.time()
        session._wait_if_needed(domain)

        # Second request should be rate limited
        session._wait_if_needed(domain)
        elapsed = time.time() - start

        # Should have waited at least 0.09 seconds (allowing small margin)
        assert elapsed >= 0.09

    def test_domain_specific_limits(self):
        """Test domain-specific rate limits."""
        session = get_retrying_session(rate_limit=0.5, domain_limits={"api.untappd.com": 1.0, "example.com": 0.1})

        assert session.domain_limits["api.untappd.com"] == 1.0
        assert session.domain_limits["example.com"] == 0.1

    def test_session_retries_on_failure(self):
        """Test that session retries on connection errors."""
        # Test that the HTTPAdapter with Retry is properly configured
        session = get_retrying_session()

        # Check the adapter is configured with retries
        adapter = session.get_adapter("https://")
        assert adapter is not None
        assert hasattr(adapter, "max_retries")
        assert adapter.max_retries.total == 3


class TestTranslation:
    def test_has_japanese(self):
        """Test Japanese character detection."""
        from strinks.api.translation import has_japanese

        assert has_japanese("これは日本語です") is True
        assert has_japanese("This is English") is False
        assert has_japanese("Mixed 日本語 and English") is True
        assert has_japanese("12345") is False

    def test_to_romaji(self):
        """Test romaji conversion."""
        from strinks.api.translation import to_romaji

        romaji = to_romaji("さくら")
        assert "sakura" in romaji.lower()

        romaji = to_romaji("東京")
        assert "tokyo" in romaji.lower() or "toukyou" in romaji.lower()

    def test_brewery_translations(self):
        """Test predefined brewery translations."""
        from strinks.api.translation import BREWERY_JP_EN

        # Check some known translations
        assert BREWERY_JP_EN.get("ヨロッコビール") == "Yorocco"
        assert BREWERY_JP_EN.get("京都醸造") == "Kyoto Brewing"
        assert BREWERY_JP_EN.get("箕面ビール") == "Minoh"

    @patch("strinks.api.translation.session.get")
    def test_deepl_translate_caching(self, mock_get):
        """Test that DeepL translations are cached."""
        from strinks.api.translation import DEEPL_CACHE, deepl_translate

        # Mock DeepL API response
        mock_response = Mock()
        mock_response.json.return_value = {"translations": [{"text": "Test Beer"}]}
        mock_get.return_value = mock_response

        # Clear cache for test
        test_text = "テストビール_unique_test"
        if test_text in DEEPL_CACHE:
            del DEEPL_CACHE[test_text]

        # First call should hit API
        result1 = deepl_translate(test_text)
        assert mock_get.call_count == 1
        assert result1 == "Test Beer"

        # Second call should use cache
        result2 = deepl_translate(test_text)
        assert mock_get.call_count == 1  # No additional API call
        assert result2 == "Test Beer"

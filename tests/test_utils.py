"""Tests for utility functions."""

from datetime import datetime
from unittest.mock import Mock, patch

import requests

from strinks.api.utils import JST, get_retrying_session, now_jst


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
        assert hasattr(session, "get")
        assert hasattr(session, "post")

        # Check that retry is configured
        assert len(session.adapters) > 0

    @patch("requests.Session.get")
    def test_session_retries_on_failure(self, mock_get):
        """Test that session retries on connection errors."""
        session = get_retrying_session()

        # First two calls fail, third succeeds
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Success"

        mock_get.side_effect = [
            requests.ConnectionError("Connection failed"),
            requests.ConnectionError("Connection failed"),
            mock_response,
        ]

        # This should retry and eventually succeed
        response = session.get("https://example.com")
        assert response.text == "Success"
        assert mock_get.call_count == 3


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

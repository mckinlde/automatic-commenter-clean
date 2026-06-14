"""Unit tests for config_ac module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import config_ac
from config_ac import LocalStorage, _get_appdata_dir


class TestConstants:
    """Verify all application constants are defined correctly."""

    def test_app_name(self):
        assert config_ac.APP_NAME == "AutoCommenter"

    def test_product(self):
        assert config_ac.PRODUCT == "autocommenter"

    def test_endpoints(self):
        assert config_ac.STRIPE_BRIDGE_BASE == "https://your-license-server.example.com"
        assert config_ac.LICENSE_API_BASE == "https://your-license-server.example.com:8443"

    def test_timeout_constants(self):
        assert config_ac.MIN_COMMENT_DELAY_SECONDS == 5
        assert config_ac.PAGE_LOAD_TIMEOUT_SECONDS == 30
        assert config_ac.COMMENT_FIELD_TIMEOUT_SECONDS == 15
        assert config_ac.LOGIN_TIMEOUT_SECONDS == 60
        assert config_ac.CAMPAIGN_SERVER_TIMEOUT_SECONDS == 15
        assert config_ac.LICENSE_CHECK_TIMEOUT_SECONDS == 10

    def test_retry_constants(self):
        assert config_ac.MAX_RETRIES == 3
        assert config_ac.BACKOFF_BASE_SECONDS == 2

    def test_poll_constants(self):
        assert config_ac.POLL_INTERVAL_SECONDS == 60
        assert config_ac.RATE_LIMIT_DEFAULT_PAUSE_SECONDS == 60


class TestGetAppdataDir:
    """Test platform-appropriate data directory resolution."""

    def test_returns_path_object(self):
        result = _get_appdata_dir()
        assert isinstance(result, Path)

    def test_directory_contains_app_name(self):
        result = _get_appdata_dir()
        assert result.name == "AutoCommenter"

    def test_directory_exists(self):
        result = _get_appdata_dir()
        assert result.exists()
        assert result.is_dir()


class TestLocalStorage:
    """Test LocalStorage JSON persistence methods."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a LocalStorage instance using a temp directory."""
        with patch.object(LocalStorage, '__init__', lambda self: None):
            ls = LocalStorage()
            ls.appdata_dir = tmp_path
            ls.config_path = tmp_path / "configuration.json"
            ls.cursor_path = tmp_path / "cursors.json"
        return ls

    # â”€â”€ Campaign config tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def test_save_and_load_campaign_config(self, storage):
        storage.save_campaign_config("https://example.com/api", "secret-key")
        loaded = storage.load_campaign_config()
        assert loaded is not None
        assert loaded["campaign_server_url"] == "https://example.com/api"
        assert loaded["api_key"] == "secret-key"

    def test_api_key_obscured_in_file(self, storage):
        storage.save_campaign_config("https://example.com/api", "my-key")
        raw = json.loads(storage.config_path.read_text(encoding="utf-8"))
        assert raw["campaign_api_key_obscured"].startswith("b64:")
        assert "my-key" not in raw["campaign_api_key_obscured"]

    def test_load_campaign_config_returns_none_when_missing(self, storage):
        assert storage.load_campaign_config() is None

    def test_load_campaign_config_returns_none_partial_data(self, storage):
        storage.config_path.write_text('{"campaign_server_url": "https://x.com"}', encoding="utf-8")
        assert storage.load_campaign_config() is None

    def test_save_campaign_config_preserves_other_fields(self, storage):
        storage.config_path.write_text('{"notification_email": "a@b.com"}', encoding="utf-8")
        storage.save_campaign_config("https://x.com/api", "key123")
        raw = json.loads(storage.config_path.read_text(encoding="utf-8"))
        assert raw["notification_email"] == "a@b.com"
        assert raw["campaign_server_url"] == "https://x.com/api"

    # â”€â”€ Cursor tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def test_save_and_load_cursors(self, storage):
        cursors = {
            "facebook|https://camp.io": {"post_cursor": 10, "last_updated": "2025-01-01T00:00:00Z"}
        }
        storage.save_cursors(cursors)
        loaded = storage.load_cursors()
        assert loaded == cursors

    def test_load_cursors_returns_empty_dict_when_missing(self, storage):
        assert storage.load_cursors() == {}

    def test_load_cursors_handles_corrupt_json(self, storage):
        storage.cursor_path.write_text("not valid json {{{", encoding="utf-8")
        assert storage.load_cursors() == {}

    def test_load_cursors_handles_non_dict_json(self, storage):
        storage.cursor_path.write_text("[1, 2, 3]", encoding="utf-8")
        assert storage.load_cursors() == {}

    # â”€â”€ Obscure/deobscure helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def test_obscure_deobscure_roundtrip(self):
        original = "test-api-key-!@#$%"
        obscured = LocalStorage._obscure(original)
        assert obscured.startswith("b64:")
        assert LocalStorage._deobscure(obscured) == original

    def test_deobscure_without_prefix_returns_as_is(self):
        assert LocalStorage._deobscure("plain-value") == "plain-value"


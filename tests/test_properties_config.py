"""Property-based tests for configuration persistence (Properties 13, 15).

Uses Hypothesis to validate correctness properties for the config_ac module.
"""

import string
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from config_ac import LocalStorage, validate_campaign_url, validate_api_key


# ─── Strategies ──────────────────────────────────────────────────────────────

# Strategy for valid HTTPS URLs (start with "https://", well-formed, length ≤ 2048)
_url_path_chars = st.sampled_from(
    string.ascii_letters + string.digits + "/-_.~"
)

valid_https_urls = st.builds(
    lambda host, path: f"https://{host}/{path}",
    host=st.from_regex(r"[a-z][a-z0-9\-]{0,20}\.[a-z]{2,6}", fullmatch=True),
    path=st.text(alphabet=_url_path_chars, min_size=0, max_size=200),
).filter(lambda u: len(u) <= 2048)

# Strategy for valid API keys (non-empty strings, length ≤ 256)
valid_api_keys = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=256,
)


# ─── Property 13: Campaign configuration persistence round-trip ──────────────
# Feature: automatic-commenter, Property 13: Campaign configuration persistence round-trip

class TestProperty13ConfigPersistenceRoundTrip:
    """
    For any valid campaign server configuration (URL starting with "https://"
    of length ≤ 2048, API key of length ≤ 256), saving the configuration then
    loading it shall return an equivalent URL and a decodable API key equal to
    the original.

    **Validates: Requirements 12.2**
    """

    @pytest.fixture(autouse=True)
    def setup_storage(self, tmp_path):
        """Create a LocalStorage instance using a temp directory."""
        with patch.object(LocalStorage, '__init__', lambda self: None):
            self.storage = LocalStorage()
            self.storage.appdata_dir = tmp_path
            self.storage.config_path = tmp_path / "configuration.json"
            self.storage.cursor_path = tmp_path / "cursors.json"

    @given(url=valid_https_urls, api_key=valid_api_keys)
    @settings(max_examples=100)
    def test_save_then_load_returns_equivalent_config(self, url, api_key):
        """Saving config then loading it returns equivalent URL and decodable API key."""
        # Act
        self.storage.save_campaign_config(url, api_key)
        loaded = self.storage.load_campaign_config()

        # Assert
        assert loaded is not None, "Loaded config should not be None after save"
        assert loaded["campaign_server_url"] == url, (
            f"URL mismatch: saved {url!r}, got {loaded['campaign_server_url']!r}"
        )
        assert loaded["api_key"] == api_key, (
            f"API key mismatch: saved {api_key!r}, got {loaded['api_key']!r}"
        )


# ─── Property 15: Settings input validation ──────────────────────────────────
# Feature: automatic-commenter, Property 15: Settings input validation

class TestProperty15SettingsInputValidation:
    """
    URL validation shall accept only strings that begin with "https://" and are
    well-formed URLs with length ≤ 2048 characters. API key validation shall
    accept only strings with length ≤ 256 characters.

    **Validates: Requirements 12.1, 12.3**
    """

    # ── URL validation: valid inputs accepted ────────────────────────────────

    @given(url=valid_https_urls)
    @settings(max_examples=100)
    def test_valid_https_urls_are_accepted(self, url):
        """Any well-formed https URL of length ≤ 2048 is accepted."""
        assert validate_campaign_url(url) is True, (
            f"Expected valid URL to be accepted: {url!r}"
        )

    # ── URL validation: invalid inputs rejected ──────────────────────────────

    @given(url=st.text(min_size=0, max_size=2048).filter(
        lambda u: not u.startswith("https://")
    ))
    @settings(max_examples=100)
    def test_urls_without_https_prefix_are_rejected(self, url):
        """Any string not starting with 'https://' is rejected."""
        assert validate_campaign_url(url) is False, (
            f"Expected non-https URL to be rejected: {url!r}"
        )

    @given(extra_length=st.integers(min_value=1, max_value=500))
    @settings(max_examples=100)
    def test_urls_exceeding_max_length_are_rejected(self, extra_length):
        """Any URL longer than 2048 characters is rejected."""
        # Build a URL that is exactly 2048 + extra_length characters
        base = "https://example.com/"
        padding = "a" * (2049 - len(base) + extra_length - 1)
        url = base + padding
        assert len(url) > 2048
        assert validate_campaign_url(url) is False, (
            f"Expected URL of length {len(url)} to be rejected"
        )

    @given(host_fragment=st.text(min_size=0, max_size=0))
    @settings(max_examples=100)
    def test_https_without_valid_netloc_is_rejected(self, host_fragment):
        """'https://' with no host component is rejected."""
        url = f"https://{host_fragment}"
        assert validate_campaign_url(url) is False, (
            f"Expected URL with empty netloc to be rejected: {url!r}"
        )

    # ── API key validation: valid inputs accepted ────────────────────────────

    @given(api_key=valid_api_keys)
    @settings(max_examples=100)
    def test_valid_api_keys_are_accepted(self, api_key):
        """Any non-empty string of length ≤ 256 is accepted."""
        assert validate_api_key(api_key) is True, (
            f"Expected valid API key to be accepted: {api_key!r}"
        )

    # ── API key validation: invalid inputs rejected ──────────────────────────

    @given(api_key=st.text(min_size=257, max_size=500))
    @settings(max_examples=100)
    def test_api_keys_exceeding_max_length_are_rejected(self, api_key):
        """Any string longer than 256 characters is rejected."""
        assert validate_api_key(api_key) is False, (
            f"Expected API key of length {len(api_key)} to be rejected"
        )

    def test_empty_api_key_is_rejected(self):
        """An empty string is rejected as an API key."""
        assert validate_api_key("") is False

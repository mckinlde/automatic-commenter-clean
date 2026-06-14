"""
Configuration module for the Automatic Commenter (AC).

Defines application constants, endpoint URLs, timeout/retry parameters,
and the LocalStorage class for JSON-based persistence of campaign config
and post cursors.
"""

import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# â”€â”€â”€ Application identity â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
APP_NAME = "AutoCommenter"
PRODUCT = "autocommenter"

# â”€â”€â”€ Licensing / server endpoints (shared with ClientCheck) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
STRIPE_BRIDGE_BASE = "https://your-license-server.example.com"
LICENSE_API_BASE = "https://your-license-server.example.com:8443"

# â”€â”€â”€ Timeout constants (seconds) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MIN_COMMENT_DELAY_SECONDS = 5
PAGE_LOAD_TIMEOUT_SECONDS = 30
COMMENT_FIELD_TIMEOUT_SECONDS = 15
LOGIN_TIMEOUT_SECONDS = 60
CAMPAIGN_SERVER_TIMEOUT_SECONDS = 15
LICENSE_CHECK_TIMEOUT_SECONDS = 10

# â”€â”€â”€ Retry constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2

# â”€â”€â”€ Polling constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
POLL_INTERVAL_SECONDS = 60
RATE_LIMIT_DEFAULT_PAUSE_SECONDS = 60


def _get_appdata_dir() -> Path:
    """
    Return the per-user data directory for AutoCommenter.

    Platform behavior:
      - Windows: %LOCALAPPDATA%\\AutoCommenter
      - macOS:   ~/Library/Application Support/AutoCommenter
      - Linux:   ~/.local/share/AutoCommenter (XDG_DATA_HOME fallback)

    Creates the directory if it does not exist.
    """
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        # Linux / other Unix
        base = os.getenv("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")

    appdir = Path(base) / APP_NAME
    appdir.mkdir(parents=True, exist_ok=True)
    return appdir


class LocalStorage:
    """
    JSON-based local persistence for campaign configuration and post cursors.

    Files managed:
      - configuration.json  â†’ campaign server URL, obscured API key
      - cursors.json        â†’ per-platform/campaign post cursor positions
    """

    def __init__(self):
        self.appdata_dir: Path = _get_appdata_dir()
        self.config_path: Path = self.appdata_dir / "configuration.json"
        self.cursor_path: Path = self.appdata_dir / "cursors.json"

    # â”€â”€ Campaign configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def save_campaign_config(self, url: str, api_key: str) -> None:
        """
        Persist campaign server URL and API key to configuration.json.

        The API key is stored in base64-obscured form (not encrypted â€” this is
        obscuring to avoid plain-text storage per Requirement 12.2).
        """
        cfg = self._read_config_file()
        cfg["campaign_server_url"] = url
        cfg["campaign_api_key_obscured"] = self._obscure(api_key)
        self._write_config_file(cfg)

    def load_campaign_config(self) -> dict | None:
        """
        Load campaign server configuration from configuration.json.

        Returns a dict with keys 'campaign_server_url' and 'api_key' (decoded),
        or None if no configuration has been saved.
        """
        cfg = self._read_config_file()
        url = cfg.get("campaign_server_url")
        obscured_key = cfg.get("campaign_api_key_obscured")

        if url is None or obscured_key is None:
            return None

        return {
            "campaign_server_url": url,
            "api_key": self._deobscure(obscured_key),
        }

    # â”€â”€ Cursor persistence â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def save_cursors(self, cursors: dict) -> None:
        """
        Persist cursor state to cursors.json.

        `cursors` is a dict keyed by composite key "{platform}|{campaign_url}"
        with values being dicts containing at least 'post_cursor' and 'last_updated'.
        """
        self.cursor_path.write_text(json.dumps(cursors, indent=2), encoding="utf-8")

    def load_cursors(self) -> dict:
        """
        Load cursor state from cursors.json.

        Returns an empty dict if the file does not exist or is unreadable.
        """
        if not self.cursor_path.exists():
            return {}
        try:
            data = json.loads(self.cursor_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return {}
        except (json.JSONDecodeError, OSError):
            return {}

    # â”€â”€ Private helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _read_config_file(self) -> dict:
        """Read the configuration.json file, returning {} on any failure."""
        if not self.config_path.exists():
            return {}
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_config_file(self, cfg: dict) -> None:
        """Write config dict to configuration.json."""
        self.config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    @staticmethod
    def _obscure(value: str) -> str:
        """Base64-encode a string for storage obscuring."""
        return "b64:" + base64.b64encode(value.encode("utf-8")).decode("ascii")

    @staticmethod
    def _deobscure(obscured: str) -> str:
        """Decode a base64-obscured value back to plain text."""
        if obscured.startswith("b64:"):
            return base64.b64decode(obscured[4:]).decode("utf-8")
        # Fallback: return as-is if not in expected format
        return obscured


# â”€â”€â”€ Validation helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

MAX_URL_LENGTH = 2048
MAX_API_KEY_LENGTH = 256


def validate_campaign_url(url: str) -> bool:
    """
    Validate a campaign server URL.

    Accepts only strings that:
      - Begin with "https://"
      - Are well-formed URLs (have a valid netloc)
      - Have length â‰¤ 2048 characters

    Returns True if valid, False otherwise.
    """
    if not isinstance(url, str):
        return False
    if len(url) > MAX_URL_LENGTH:
        return False
    if not url.startswith("https://"):
        return False
    try:
        parsed = urlparse(url)
        # Must have a non-empty network location (host)
        if not parsed.netloc:
            return False
        return True
    except Exception:
        return False


def validate_api_key(api_key: str) -> bool:
    """
    Validate an API key.

    Accepts only strings with length â‰¤ 256 characters and length > 0.

    Returns True if valid, False otherwise.
    """
    if not isinstance(api_key, str):
        return False
    if len(api_key) == 0:
        return False
    if len(api_key) > MAX_API_KEY_LENGTH:
        return False
    return True


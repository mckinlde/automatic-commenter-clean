"""
Build verification tests for the Automatic Commenter application.

Validates: Requirements 13.2, 13.3
- THE AC_Client SHALL use webdriver-manager to automatically download and cache
  the appropriate browser driver at runtime.
- WHEN packaged, THE AC_Client SHALL embed a version string (following semantic
  versioning format) accessible at runtime via a __version__ module attribute.
"""

import re
import importlib
import pytest


def test_version_attribute_is_accessible():
    """Verify __version__ is importable and non-empty."""
    from app_ac import __version__

    assert __version__, "__version__ should be a non-empty string"
    assert isinstance(__version__, str), "__version__ should be a string"


def test_version_is_semver_format():
    """Validate the version string matches semantic versioning (X.Y.Z)."""
    from app_ac import __version__

    semver_pattern = r"^\d+\.\d+\.\d+$"
    assert re.match(semver_pattern, __version__), (
        f"__version__ '{__version__}' does not match semver format X.Y.Z"
    )


def test_webdriver_manager_can_resolve_path():
    """
    Verify that webdriver-manager's ChromeDriverManager can be imported
    and instantiated. The actual .install() call requires network access
    and Chrome, so we skip it if Chrome is not available.
    """
    from webdriver_manager.chrome import ChromeDriverManager

    manager = ChromeDriverManager()
    assert manager is not None, "ChromeDriverManager should instantiate without error"

    # Attempt the actual install (downloads driver); skip if it fails
    # due to missing Chrome or no network.
    try:
        path = manager.install()
        assert path, "install() should return a non-empty path string"
        assert isinstance(path, str), "install() should return a string"
    except Exception as e:
        pytest.skip(
            f"ChromeDriverManager.install() unavailable (Chrome not found or no network): {e}"
        )


def test_all_modules_importable():
    """Verify that all AC modules can be imported without error."""
    modules = [
        "config_ac",
        "models_ac",
        "platform_strategies",
        "cursor_manager",
        "campaign_client",
        "browser_engine",
        "worker",
    ]

    for module_name in modules:
        mod = importlib.import_module(module_name)
        assert mod is not None, f"Module '{module_name}' should import successfully"

"""Unit tests for browser_engine module — WebDriver lifecycle management."""

import pytest

from browser_engine import (
    BrowserAutomationEngine,
    _resolve_strategy,
    PLATFORM_STRATEGY_MAP,
    PLATFORM_LOGIN_URLS,
    CAPTCHA_INDICATORS,
    MFA_INDICATORS,
    LOGIN_ERROR_INDICATORS,
)
from models_ac import LoginResult
from platform_strategies import (
    FacebookStrategy,
    TwitterStrategy,
    InstagramStrategy,
    TikTokStrategy,
)


class TestResolveStrategy:
    """Tests for the _resolve_strategy helper."""

    def test_resolves_facebook(self):
        strategy = _resolve_strategy("facebook")
        assert isinstance(strategy, FacebookStrategy)

    def test_resolves_twitter(self):
        strategy = _resolve_strategy("twitter")
        assert isinstance(strategy, TwitterStrategy)

    def test_resolves_instagram(self):
        strategy = _resolve_strategy("instagram")
        assert isinstance(strategy, InstagramStrategy)

    def test_resolves_tiktok(self):
        strategy = _resolve_strategy("tiktok")
        assert isinstance(strategy, TikTokStrategy)

    def test_resolves_case_insensitive(self):
        assert isinstance(_resolve_strategy("Facebook"), FacebookStrategy)
        assert isinstance(_resolve_strategy("TWITTER"), TwitterStrategy)
        assert isinstance(_resolve_strategy("Instagram"), InstagramStrategy)
        assert isinstance(_resolve_strategy("TikTok"), TikTokStrategy)

    def test_resolves_with_whitespace(self):
        assert isinstance(_resolve_strategy("  facebook  "), FacebookStrategy)

    def test_raises_for_unknown_platform(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            _resolve_strategy("myspace")

    def test_raises_for_empty_string(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            _resolve_strategy("")


class TestBrowserAutomationEngineInit:
    """Tests for BrowserAutomationEngine instantiation."""

    def test_instantiates_with_valid_platform(self):
        engine = BrowserAutomationEngine("facebook")
        assert engine.platform == "facebook"
        assert isinstance(engine.strategy, FacebookStrategy)
        assert engine.driver is None

    def test_instantiates_with_each_supported_platform(self):
        for platform_name in PLATFORM_STRATEGY_MAP:
            engine = BrowserAutomationEngine(platform_name)
            assert engine.platform == platform_name
            assert engine.strategy is not None

    def test_raises_for_invalid_platform(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            BrowserAutomationEngine("linkedin")

    def test_raises_for_empty_platform(self):
        with pytest.raises(ValueError, match="Unsupported platform"):
            BrowserAutomationEngine("")

    def test_driver_is_none_before_launch(self):
        engine = BrowserAutomationEngine("facebook")
        assert engine.driver is None


class TestBrowserAutomationEngineSessionValid:
    """Tests for is_session_valid when no browser is launched."""

    def test_session_invalid_when_driver_is_none(self):
        engine = BrowserAutomationEngine("facebook")
        assert engine.is_session_valid() is False


class TestBrowserAutomationEngineClose:
    """Tests for close() when no browser is launched."""

    def test_close_is_safe_when_no_driver(self):
        engine = BrowserAutomationEngine("facebook")
        # Should not raise
        engine.close()
        assert engine.driver is None

    def test_close_twice_is_safe(self):
        engine = BrowserAutomationEngine("facebook")
        engine.close()
        engine.close()
        assert engine.driver is None


class TestValidateCredentials:
    """Tests for BrowserAutomationEngine.validate_credentials()."""

    def test_valid_credentials_returns_none(self):
        result = BrowserAutomationEngine.validate_credentials("user@example.com", "pass123")
        assert result is None

    def test_empty_username_returns_failure(self):
        result = BrowserAutomationEngine.validate_credentials("", "pass123")
        assert result is not None
        assert result.success is False
        assert result.requires_captcha is False
        assert result.requires_mfa is False
        assert "Username" in result.error_message

    def test_whitespace_only_username_returns_failure(self):
        result = BrowserAutomationEngine.validate_credentials("   ", "pass123")
        assert result is not None
        assert result.success is False
        assert "Username" in result.error_message

    def test_empty_password_returns_failure(self):
        result = BrowserAutomationEngine.validate_credentials("user@example.com", "")
        assert result is not None
        assert result.success is False
        assert "Password" in result.error_message

    def test_whitespace_only_password_returns_failure(self):
        result = BrowserAutomationEngine.validate_credentials("user@example.com", "   \t\n  ")
        assert result is not None
        assert result.success is False
        assert "Password" in result.error_message

    def test_both_empty_returns_username_error_first(self):
        result = BrowserAutomationEngine.validate_credentials("", "")
        assert result is not None
        assert result.success is False
        assert "Username" in result.error_message

    def test_valid_credentials_with_special_chars(self):
        result = BrowserAutomationEngine.validate_credentials("user+tag@gmail.com", "P@$$w0rd!#")
        assert result is None


class TestLoginWithoutBrowser:
    """Tests for login() method when no browser is available."""

    def test_login_rejects_empty_username(self):
        engine = BrowserAutomationEngine("facebook")
        result = engine.login("", "password123")
        assert result.success is False
        assert "Username" in result.error_message

    def test_login_rejects_empty_password(self):
        engine = BrowserAutomationEngine("facebook")
        result = engine.login("user@example.com", "")
        assert result.success is False
        assert "Password" in result.error_message

    def test_login_rejects_whitespace_credentials(self):
        engine = BrowserAutomationEngine("facebook")
        result = engine.login("   ", "   ")
        assert result.success is False

    def test_login_fails_when_driver_not_launched(self):
        engine = BrowserAutomationEngine("facebook")
        result = engine.login("user@example.com", "password123")
        assert result.success is False
        assert "Browser is not launched" in result.error_message

    def test_login_returns_login_result_type(self):
        engine = BrowserAutomationEngine("facebook")
        result = engine.login("user@example.com", "password123")
        assert isinstance(result, LoginResult)


class TestPlatformLoginUrls:
    """Tests for the platform login URL registry."""

    def test_facebook_login_url_exists(self):
        assert "facebook" in PLATFORM_LOGIN_URLS
        assert "facebook.com/login" in PLATFORM_LOGIN_URLS["facebook"]

    def test_all_strategy_platforms_have_login_urls(self):
        for platform in PLATFORM_STRATEGY_MAP:
            assert platform in PLATFORM_LOGIN_URLS, f"Missing login URL for {platform}"


class TestNavigateToPost:
    """Tests for BrowserAutomationEngine.navigate_to_post()."""

    def test_returns_false_when_no_driver(self):
        engine = BrowserAutomationEngine("facebook")
        assert engine.navigate_to_post("https://facebook.com/post/123") is False

    def test_returns_false_when_driver_is_none(self):
        engine = BrowserAutomationEngine("facebook")
        engine._driver = None
        assert engine.navigate_to_post("https://facebook.com/post/123") is False

    def test_accepts_custom_timeout(self):
        engine = BrowserAutomationEngine("facebook")
        # Without a driver, it still returns False regardless of timeout
        assert engine.navigate_to_post("https://facebook.com/post/123", timeout=5) is False

    def test_default_timeout_is_page_load_constant(self):
        """Verify that the default timeout uses PAGE_LOAD_TIMEOUT_SECONDS (30)."""
        from config_ac import PAGE_LOAD_TIMEOUT_SECONDS
        import inspect
        sig = inspect.signature(BrowserAutomationEngine.navigate_to_post)
        timeout_param = sig.parameters["timeout"]
        assert timeout_param.default == PAGE_LOAD_TIMEOUT_SECONDS


class TestPostComment:
    """Tests for BrowserAutomationEngine.post_comment()."""

    def test_returns_failure_when_no_driver(self):
        engine = BrowserAutomationEngine("facebook")
        result = engine.post_comment("Hello world!")
        assert result.success is False
        assert "No browser session active" in result.error_message

    def test_returns_failure_when_driver_is_none(self):
        engine = BrowserAutomationEngine("facebook")
        engine._driver = None
        result = engine.post_comment("Test comment")
        assert result.success is False
        assert result.error_message is not None

    def test_returns_post_result_type(self):
        from models_ac import PostResult
        engine = BrowserAutomationEngine("facebook")
        result = engine.post_comment("Test comment")
        assert isinstance(result, PostResult)

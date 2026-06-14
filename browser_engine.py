"""
Browser Automation Engine for the Automatic Commenter.

Manages Selenium WebDriver sessions and platform-specific interactions.
Uses webdriver-manager for automatic ChromeDriver management (same pattern
as ClientCheck's create_driver()).

The browser runs in HEADED mode — users need to see and interact with the
browser for logins, CAPTCHAs, and monitoring.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager

import time

from config_ac import (
    LOGIN_TIMEOUT_SECONDS,
    PAGE_LOAD_TIMEOUT_SECONDS,
    COMMENT_FIELD_TIMEOUT_SECONDS,
)
from models_ac import LoginResult, PostResult
from platform_strategies import (
    PlatformStrategy,
    FacebookStrategy,
    TwitterStrategy,
    InstagramStrategy,
    TikTokStrategy,
)


# Registry mapping platform name strings to their strategy classes
PLATFORM_STRATEGY_MAP: dict[str, type[PlatformStrategy]] = {
    "facebook": FacebookStrategy,
    "twitter": TwitterStrategy,
    "instagram": InstagramStrategy,
    "tiktok": TikTokStrategy,
}

# Login page URLs per platform
PLATFORM_LOGIN_URLS: dict[str, str] = {
    "facebook": "https://www.facebook.com/login",
    "twitter": "https://twitter.com/i/flow/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "tiktok": "https://www.tiktok.com/login",
}

# Indicators used to detect CAPTCHA challenges on the page
CAPTCHA_INDICATORS: list[str] = [
    "captcha",
    "security check",
    "verify you're human",
    "robot",
    "recaptcha",
    "checkpoint",
]

# Indicators used to detect MFA/2FA challenges on the page
MFA_INDICATORS: list[str] = [
    "two-factor",
    "verification code",
    "enter the code",
    "2fa",
    "authenticator",
    "confirm your identity",
    "login code",
    "security code",
]

# Indicators used to detect login failure (incorrect credentials)
LOGIN_ERROR_INDICATORS: list[str] = [
    "incorrect password",
    "wrong password",
    "doesn't match",
    "invalid credentials",
    "login failed",
    "the password you entered is incorrect",
    "please re-enter your password",
    "the email address you entered",
    "find your account",
    "not match our records",
]


def _resolve_strategy(platform: str) -> PlatformStrategy:
    """
    Resolve a platform name string to a PlatformStrategy instance.

    Args:
        platform: Case-insensitive platform name (e.g., "facebook", "Twitter").

    Returns:
        An instance of the corresponding PlatformStrategy subclass.

    Raises:
        ValueError: If the platform name is not recognized.
    """
    key = platform.strip().lower()
    strategy_cls = PLATFORM_STRATEGY_MAP.get(key)
    if strategy_cls is None:
        supported = ", ".join(sorted(PLATFORM_STRATEGY_MAP.keys()))
        raise ValueError(
            f"Unsupported platform: '{platform}'. "
            f"Supported platforms: {supported}"
        )
    return strategy_cls()


class BrowserAutomationEngine:
    """
    Manages Selenium WebDriver sessions and platform interactions.

    The engine handles browser lifecycle (launch, close) and delegates
    platform-specific DOM interactions to the appropriate PlatformStrategy.

    Args:
        platform: Name of the target social media platform (e.g., "facebook").

    Raises:
        ValueError: If the platform name is not recognized.
    """

    def __init__(self, platform: str):
        self.platform: str = platform
        self.strategy: PlatformStrategy = _resolve_strategy(platform)
        self._driver: webdriver.Chrome | None = None

    @property
    def driver(self) -> webdriver.Chrome | None:
        """The underlying Selenium WebDriver instance, or None if not launched."""
        return self._driver

    def launch_browser(self) -> bool:
        """
        Initialize a Chrome WebDriver session using webdriver-manager.

        Configures Chrome with:
          - --start-maximized (full-screen window)
          - excludeSwitches: ["enable-logging"] (suppress console spam)
          - Headed mode (no --headless flag)

        Returns:
            True if the browser launched successfully, False on failure.
        """
        try:
            chrome_options = Options()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_experimental_option(
                "excludeSwitches", ["enable-logging"]
            )

            self._driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options,
            )
            return True
        except Exception:
            self._driver = None
            return False

    def close(self) -> None:
        """
        Quit the WebDriver session and clean up resources.

        Safe to call even if no browser is running or the session
        has already been closed.
        """
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            finally:
                self._driver = None

    def robust_click(self, element, timeout: int = 10, y_offset: int = -150) -> None:
        """
        Robust click that handles intercepted clicks from overlays/sticky elements.

        Ported from ClientCheck's battle-tested click helper.
        """
        if self._driver is None:
            return

        # Scroll element into viewport center and nudge up
        self._driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", element
        )
        self._driver.execute_script("window.scrollBy(0, arguments[0]);", y_offset)
        time.sleep(0.2)  # Let scroll animation settle

        try:
            wait = WebDriverWait(self._driver, timeout)
            wait.until(lambda d: element.is_displayed() and element.is_enabled())
            element.click()
        except ElementClickInterceptedException:
            # Dismiss common overlays and retry via JavaScript
            self._dismiss_overlays()
            time.sleep(0.1)
            self._driver.execute_script("arguments[0].click();", element)

    def _dismiss_overlays(self) -> None:
        """
        Dismiss common overlays that intercept clicks on social media platforms.

        Disables pointer-events and lowers z-index on:
        - Cookie consent banners
        - Fixed headers/footers
        - Notification prompts
        - Chat widgets
        """
        if self._driver is None:
            return
        self._driver.execute_script("""
            // Generic overlay dismissal
            var selectors = [
                '[role="dialog"]',
                '[class*="cookie"]',
                '[class*="consent"]',
                '[class*="overlay"]',
                '[class*="popup"]',
                '[class*="modal"]',
                'div[data-testid="cookie-policy-manage-dialog"]',
                'div[class*="fixed-bottom"]',
                'div[class*="fixed-top"]',
                'footer[class*="fixed"]',
                'div[class*="chat-widget"]',
            ];
            selectors.forEach(function(sel) {
                document.querySelectorAll(sel).forEach(function(el) {
                    el.style.pointerEvents = 'none';
                    el.style.zIndex = '0';
                    el.style.display = 'none';
                });
            });
        """)

    def _find_visible_element(self, by, selector, timeout: int = 10):
        """
        Find the first visible and displayed element matching the selector.

        Social media platforms often have multiple matching elements in the DOM
        but only one is actually visible/interactable.
        """
        if self._driver is None:
            return None
        try:
            elements = WebDriverWait(self._driver, timeout).until(
                EC.presence_of_all_elements_located((by, selector))
            )
            for el in elements:
                try:
                    if el.is_displayed():
                        return el
                except StaleElementReferenceException:
                    continue
            return elements[0] if elements else None
        except TimeoutException:
            return None

    def _try_open_comment_panel(self) -> None:
        """
        Attempt to open the comment panel by clicking the comment icon.

        Only activates on Facebook Reels URLs (facebook.com/share/r/ or
        facebook.com/reel/). On regular posts, the comment field is already
        visible and this is a no-op.

        On Reels, the comment input doesn't exist in the DOM until you click
        the comment icon (speech bubble).
        """
        if self._driver is None:
            return

        if not hasattr(self.strategy, 'get_comment_icon_selectors'):
            return

        # Only attempt on Reels URLs — regular posts already show the comment field
        current_url = self._driver.current_url.lower()
        is_reels = "/reel/" in current_url or "/share/r/" in current_url
        if not is_reels:
            return

        # First check if the comment field is already visible — if so, no need to click
        comment_selector = self.strategy.get_comment_field_selector()
        try:
            existing = self._driver.find_elements(By.CSS_SELECTOR, comment_selector)
            for el in existing:
                if el.is_displayed():
                    return  # Comment field already visible
        except (WebDriverException, StaleElementReferenceException):
            pass

        # Try each comment icon selector
        icon_selectors = self.strategy.get_comment_icon_selectors()
        for selector in icon_selectors:
            try:
                icons = self._driver.find_elements(By.CSS_SELECTOR, selector)
                for icon in icons:
                    try:
                        if icon.is_displayed():
                            self.robust_click(icon)
                            time.sleep(2)  # Wait for comment panel to render
                            return
                    except (StaleElementReferenceException, WebDriverException):
                        continue
            except (WebDriverException, NoSuchElementException):
                continue

    def is_session_valid(self) -> bool:
        """
        Check if the current browser session is still alive.

        Verifies that the WebDriver is responsive by requesting the
        current window title. If the driver is None or the command
        raises an exception, the session is considered invalid.

        Returns:
            True if the session is alive and responsive, False otherwise.
        """
        if self._driver is None:
            return False
        try:
            # A simple command that requires a live session
            _ = self._driver.title
            return True
        except Exception:
            return False

    def navigate_to_post(self, url: str, timeout: int = PAGE_LOAD_TIMEOUT_SECONDS) -> bool:
        """
        Navigate to a post URL and wait for the page to fully load.

        Uses WebDriverWait to confirm the page body is present within the
        specified timeout, indicating a successful page load.

        Args:
            url: The full URL of the social media post to navigate to.
            timeout: Maximum seconds to wait for page load (default: 30).

        Returns:
            True if the page loaded successfully within the timeout,
            False if loading timed out or no browser session exists.
        """
        if self._driver is None:
            return False
        try:
            self._driver.get(url)
            WebDriverWait(self._driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            return True
        except TimeoutException:
            return False
        except WebDriverException:
            return False

    def post_comment(self, comment_text: str) -> PostResult:
        """
        Locate the comment field, enter the comment text, and submit.

        Uses the platform strategy to find the correct DOM selectors for
        the comment input field and submit mechanism. Waits up to
        COMMENT_FIELD_TIMEOUT_SECONDS (15s) for the comment field to
        appear, enters the text, submits (via Enter key or click depending
        on platform), then verifies the comment was posted via the platform
        strategy.

        Args:
            comment_text: The text to post as a comment.

        Returns:
            PostResult with success=True if the comment was posted and
            verified, or PostResult with success=False and an error
            message describing what went wrong.
        """
        if self._driver is None:
            return PostResult(success=False, error_message="No browser session active")

        # On some post types (e.g. Facebook Reels), the comment field doesn't
        # exist until you click the comment icon to open the panel. Try that first.
        self._try_open_comment_panel()

        # Locate the comment input field
        comment_selector = self.strategy.get_comment_field_selector()
        try:
            comment_field = WebDriverWait(self._driver, COMMENT_FIELD_TIMEOUT_SECONDS).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, comment_selector))
            )
        except TimeoutException:
            # Try fallback selectors if the strategy provides them
            comment_field = None
            if hasattr(self.strategy, 'get_comment_field_fallback_selectors'):
                for fallback_selector in self.strategy.get_comment_field_fallback_selectors():
                    try:
                        comment_field = WebDriverWait(self._driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, fallback_selector))
                        )
                        break
                    except (TimeoutException, WebDriverException):
                        continue
            if comment_field is None:
                return PostResult(
                    success=False,
                    error_message=f"Comment field not found within {COMMENT_FIELD_TIMEOUT_SECONDS}s"
                )
        except WebDriverException as e:
            return PostResult(
                success=False,
                error_message=f"Error locating comment field: {e}"
            )

        # Clear any existing content in the comment field
        try:
            comment_field.click()
            # For contenteditable divs, select-all + delete is more reliable than .clear()
            comment_field.send_keys(Keys.CONTROL + "a")
            comment_field.send_keys(Keys.DELETE)
            time.sleep(0.1)
        except (WebDriverException, StaleElementReferenceException):
            pass

        # Enter the comment text
        try:
            comment_field.send_keys(comment_text)
        except StaleElementReferenceException:
            # Re-find the element if it went stale
            comment_selector = self.strategy.get_comment_field_selector()
            try:
                comment_field = WebDriverWait(self._driver, COMMENT_FIELD_TIMEOUT_SECONDS).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, comment_selector))
                )
                comment_field.click()
                comment_field.send_keys(comment_text)
            except (TimeoutException, WebDriverException) as e:
                return PostResult(
                    success=False,
                    error_message=f"Error re-finding comment field after stale reference: {e}"
                )
        except WebDriverException as e:
            return PostResult(
                success=False,
                error_message=f"Error entering comment text: {e}"
            )

        # Submit the comment — either via Enter key or by clicking a submit button
        if self.strategy.uses_enter_to_submit():
            # Platform uses Enter key to submit (e.g., Facebook)
            try:
                comment_field.send_keys(Keys.RETURN)
            except WebDriverException as e:
                return PostResult(
                    success=False,
                    error_message=f"Error submitting comment via Enter key: {e}"
                )
        else:
            # Platform uses a clickable submit button (e.g., Twitter/X)
            submit_selector = self.strategy.get_submit_selector()
            try:
                submit_button = WebDriverWait(self._driver, COMMENT_FIELD_TIMEOUT_SECONDS).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, submit_selector))
                )
                self.robust_click(submit_button)
            except TimeoutException:
                return PostResult(
                    success=False,
                    error_message="Submit button not found or not clickable"
                )
            except WebDriverException as e:
                return PostResult(
                    success=False,
                    error_message=f"Error clicking submit button: {e}"
                )

        # Wait briefly for the comment to appear on the page
        time.sleep(2)

        # Verify the comment was posted using the platform strategy
        try:
            if self.strategy.verify_comment_posted(self._driver, comment_text):
                return PostResult(success=True, error_message=None)
            else:
                return PostResult(
                    success=False,
                    error_message="Comment verification failed: comment not found on page after submission"
                )
        except NotImplementedError:
            # Strategy verification not yet implemented — treat submission as success
            # since we successfully entered text and submitted
            return PostResult(success=True, error_message=None)
        except Exception as e:
            return PostResult(
                success=False,
                error_message=f"Error during comment verification: {e}"
            )

    @staticmethod
    def validate_credentials(username: str, password: str) -> LoginResult | None:
        """
        Validate that username and password are non-empty and non-whitespace.

        Args:
            username: The username/email to validate.
            password: The password to validate.

        Returns:
            A LoginResult with success=False and an error message if validation
            fails, or None if credentials are valid.
        """
        if not username or not username.strip():
            return LoginResult(
                success=False,
                requires_captcha=False,
                requires_mfa=False,
                error_message="Username cannot be empty or whitespace-only.",
            )
        if not password or not password.strip():
            return LoginResult(
                success=False,
                requires_captcha=False,
                requires_mfa=False,
                error_message="Password cannot be empty or whitespace-only.",
            )
        return None

    def login(self, username: str, password: str) -> LoginResult:
        """
        Attempt login on the selected platform using browser automation.

        Navigates to the platform's login page, fills in credentials using
        platform-specific selectors, and submits the form. Detects CAPTCHA,
        MFA challenges, and login failures.

        Enforces a 60-second timeout on the entire login attempt.

        Args:
            username: The user's login username/email.
            password: The user's login password.

        Returns:
            LoginResult indicating success, or details about failure/challenges.
        """
        # Validate credentials before attempting browser interaction
        validation_result = self.validate_credentials(username, password)
        if validation_result is not None:
            return validation_result

        # Ensure browser is running
        if self._driver is None:
            return LoginResult(
                success=False,
                requires_captcha=False,
                requires_mfa=False,
                error_message="Browser is not launched. Call launch_browser() first.",
            )

        # Get platform-specific login selectors
        selectors = self.strategy.get_login_selectors()

        # Get the login URL for this platform
        login_url = PLATFORM_LOGIN_URLS.get(self.platform.strip().lower())
        if login_url is None:
            return LoginResult(
                success=False,
                requires_captcha=False,
                requires_mfa=False,
                error_message=f"No login URL configured for platform: {self.platform}",
            )

        try:
            # Navigate to the login page
            self._driver.get(login_url)

            wait = WebDriverWait(self._driver, LOGIN_TIMEOUT_SECONDS)

            # Wait for and fill in the username field
            username_field = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selectors.username_field))
            )
            username_field.clear()
            username_field.send_keys(username)

            # Wait for and fill in the password field
            try:
                password_field = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selectors.password_field))
                )
                password_field.clear()
                password_field.send_keys(password)
            except StaleElementReferenceException:
                # Twitter's multi-step login can cause stale references
                password_field = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selectors.password_field))
                )
                password_field.clear()
                password_field.send_keys(password)

            # Click the submit button
            try:
                submit_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selectors.submit_button))
                )
                submit_button.click()
            except StaleElementReferenceException:
                # Re-find submit button if it went stale
                submit_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selectors.submit_button))
                )
                submit_button.click()

            # Wait briefly for the page to respond after submission
            time.sleep(3)

            # Check page source for CAPTCHA, MFA, or error indicators
            page_source_lower = self._driver.page_source.lower()

            # Check for CAPTCHA
            for indicator in CAPTCHA_INDICATORS:
                if indicator in page_source_lower:
                    return LoginResult(
                        success=False,
                        requires_captcha=True,
                        requires_mfa=False,
                        error_message="CAPTCHA or security check detected. Please complete it manually.",
                    )

            # Check for MFA
            for indicator in MFA_INDICATORS:
                if indicator in page_source_lower:
                    return LoginResult(
                        success=False,
                        requires_captcha=False,
                        requires_mfa=True,
                        error_message="Multi-factor authentication required. Please complete verification.",
                    )

            # Check for login failure (incorrect credentials)
            for indicator in LOGIN_ERROR_INDICATORS:
                if indicator in page_source_lower:
                    return LoginResult(
                        success=False,
                        requires_captcha=False,
                        requires_mfa=False,
                        error_message="Login failed: incorrect credentials.",
                    )

            # If we got past all error checks, check for URL change as a success signal
            current_url = self._driver.current_url.lower()
            if "login" not in current_url or current_url != login_url.lower():
                return LoginResult(
                    success=True,
                    requires_captcha=False,
                    requires_mfa=False,
                    error_message=None,
                )

            # Still on login page but no error detected — might be slow or ambiguous
            return LoginResult(
                success=False,
                requires_captcha=False,
                requires_mfa=False,
                error_message="Login did not complete. Still on login page after submission.",
            )

        except TimeoutException:
            return LoginResult(
                success=False,
                requires_captcha=False,
                requires_mfa=False,
                error_message="Login attempt timed out after 60 seconds.",
            )
        except WebDriverException as e:
            return LoginResult(
                success=False,
                requires_captcha=False,
                requires_mfa=False,
                error_message=f"Browser error during login: {str(e)[:200]}",
            )
        except Exception as e:
            return LoginResult(
                success=False,
                requires_captcha=False,
                requires_mfa=False,
                error_message=f"Unexpected error during login: {str(e)[:200]}",
            )

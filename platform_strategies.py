"""
Platform-specific automation strategies for the Automatic Commenter.

Defines the abstract base class for platform interactions and concrete
implementations for each supported social media platform.

Facebook is the primary platform; others are best-effort until Facebook
works end-to-end.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LoginSelectors:
    """DOM selectors for a platform's login page elements.

    For platforms with multi-step login flows (e.g., Twitter/X), the
    `extra_steps` field holds additional (selector, action) pairs that
    must be executed in order between username and password submission.
    """
    username_field: str
    password_field: str
    submit_button: str
    extra_steps: list[dict[str, str]] = field(default_factory=list)


class PlatformStrategy(ABC):
    """Abstract base class for platform-specific DOM interactions."""

    @abstractmethod
    def get_login_selectors(self) -> LoginSelectors:
        """Return the CSS/XPath selectors for the login form elements."""
        ...

    @abstractmethod
    def get_comment_field_selector(self) -> str:
        """Return the selector for the comment input field on a post page."""
        ...

    @abstractmethod
    def get_submit_selector(self) -> str:
        """Return the selector for the comment submit button/mechanism.

        For platforms that use Enter key to submit (see `uses_enter_to_submit()`),
        this may return a fallback selector for an optional submit icon/button.
        """
        ...

    def uses_enter_to_submit(self) -> bool:
        """Return True if this platform submits comments via Enter key press.

        When True, the browser engine should send Keys.RETURN after entering
        comment text instead of (or before trying to) click a submit button.
        The submit selector returned by `get_submit_selector()` serves as a
        fallback if Enter-key submission does not work.

        Default is False — most platforms have a clickable submit button.
        """
        return False

    @abstractmethod
    def verify_comment_posted(self, driver, comment_text: str) -> bool:
        """
        Check whether the given comment text appears on the page after submission.

        Args:
            driver: The Selenium WebDriver instance for inspecting the page.
            comment_text: The comment that was submitted.

        Returns:
            True if the comment is visible on the page, False otherwise.
        """
        ...


class FacebookStrategy(PlatformStrategy):
    """
    Facebook-specific automation strategy.

    Facebook's comment system uses a contenteditable div rather than a
    standard input/textarea. Comments are submitted by pressing Enter
    (Return key), not by clicking a dedicated submit button.

    Selectors target the current Facebook DOM structure as of 2024-2025.
    These may need periodic updates as Facebook modifies its frontend.
    """

    def get_login_selectors(self) -> LoginSelectors:
        return LoginSelectors(
            username_field='input[name="email"]',
            password_field='input[name="pass"]',
            submit_button='button[name="login"]',
        )

    def get_comment_field_selector(self) -> str:
        # Facebook uses a contenteditable div for the comment box.
        # The aria-label contains "Write a comment" (locale-dependent).
        # On Reels, this only appears after clicking the comment icon.
        return 'div[contenteditable="true"][role="textbox"][aria-label*="Write a comment"]'

    def get_comment_field_fallback_selectors(self) -> list[str]:
        """Additional selectors to try if the primary comment field selector fails.

        Facebook's DOM can vary between post types (feed vs. permalink page vs. Reels)
        and layout experiments.
        """
        return [
            'div[contenteditable="true"][role="textbox"][aria-label*="comment" i]',
            'div[contenteditable="true"][role="textbox"][aria-label*="Write a public comment"]',
            'div[contenteditable="true"][role="textbox"]',
            'div[data-testid="UFI2CommentInput/comment_input"] div[contenteditable="true"]',
        ]

    def get_comment_icon_selectors(self) -> list[str]:
        """Selectors for the comment icon/button that opens the comment panel.

        On Facebook Reels and some video posts, the comment input is hidden
        until the user clicks the comment icon (speech bubble). These selectors
        target that icon so we can click it before looking for the input field.
        """
        return [
            'div[aria-label="Comment" i][role="button"]',
            'div[aria-label="Leave a comment" i][role="button"]',
            'span[data-visualcompletion="css-img"][style*="comment"]',
            'div[aria-label="Comment"][tabindex]',
            'i[data-visualcompletion="css-img"][style*="url"]',
        ]

    def uses_enter_to_submit(self) -> bool:
        """Facebook submits comments on Enter key press."""
        return True

    def get_submit_selector(self) -> str:
        # Fallback submit selector — Facebook occasionally shows a small
        # send/submit icon beside the comment field. This targets it if present.
        return 'div[aria-label="Comment"][role="button"], form[role="presentation"] div[aria-label="Submit"]'

    def verify_comment_posted(self, driver, comment_text: str) -> bool:
        """Verify the comment appears on the page after submission.

        Checks the page source for the comment text. Facebook renders
        comments inline after posting, so the text should be present in
        the DOM if submission succeeded.

        Args:
            driver: The Selenium WebDriver instance.
            comment_text: The exact comment text that was submitted.

        Returns:
            True if the comment text is found on the page.
        """
        try:
            page_source = driver.page_source
            return comment_text in page_source
        except Exception:
            return False


class TwitterStrategy(PlatformStrategy):
    """
    Twitter/X automation strategy with best-effort DOM selectors.

    IMPORTANT: Twitter/X uses a multi-step login flow:
      1. Enter username/email → click "Next"
      2. (Optional) Enter phone number or username for verification
      3. Enter password → click "Log in"

    The `extra_steps` field in LoginSelectors documents the intermediate
    "Next" button that must be clicked between username and password entry.
    The browser engine's login flow needs special handling to accommodate
    this multi-step process.

    Selectors are based on Twitter/X's data-testid attributes which are
    relatively stable across UI updates.
    """

    def get_login_selectors(self) -> LoginSelectors:
        # Twitter/X multi-step login:
        # Step 1: Username field + "Next" button
        # Step 2: Password field + "Log in" button
        # The extra_steps list documents the intermediate navigation.
        return LoginSelectors(
            username_field='input[autocomplete="username"]',
            password_field='input[name="password"]',
            submit_button='div[data-testid="LoginForm_Login_Button"], button[data-testid="LoginForm_Login_Button"]',
            extra_steps=[
                {
                    "action": "click",
                    "selector": 'div[role="button"]:has(span:contains("Next")), button:has(span:contains("Next"))',
                    "description": "Click 'Next' button after entering username",
                    "wait_after": "2",
                },
            ],
        )

    def get_comment_field_selector(self) -> str:
        # Twitter/X reply composer uses a data-testid attribute
        return 'div[data-testid="tweetTextarea_0"]'

    def get_comment_field_fallback_selectors(self) -> list[str]:
        """Additional selectors for the reply field on Twitter/X."""
        return [
            'div[data-testid="tweetTextarea_0RichTextInputContainer"] div[contenteditable="true"]',
            'div[role="textbox"][data-testid="tweetTextarea_0"]',
            'div[aria-label="Post your reply"][role="textbox"]',
        ]

    def get_submit_selector(self) -> str:
        # The inline reply button in the reply composer
        return 'div[data-testid="tweetButtonInline"], button[data-testid="tweetButtonInline"]'

    def verify_comment_posted(self, driver, comment_text: str) -> bool:
        """Verify the reply appears on the page after submission.

        Twitter/X shows a confirmation or the reply appears in the thread.
        We check if the comment text exists in the page source.

        Args:
            driver: The Selenium WebDriver instance.
            comment_text: The exact reply text that was submitted.

        Returns:
            True if the comment text is found on the page.
        """
        try:
            page_source = driver.page_source
            return comment_text in page_source
        except Exception:
            return False


class InstagramStrategy(PlatformStrategy):
    """
    Instagram automation strategy.

    Secondary platform — selectors are best-effort based on known DOM structures.
    Instagram's DOM changes frequently; these selectors may need refinement.

    TODO: Instagram aggressively detects automation. Consider adding random delays
    and human-like interaction patterns if sessions are being terminated.
    """

    def get_login_selectors(self) -> LoginSelectors:
        return LoginSelectors(
            username_field='input[name="username"]',
            password_field='input[name="password"]',
            submit_button='button[type="submit"]',
        )

    def get_comment_field_selector(self) -> str:
        # TODO: Instagram DOM is fragile — the aria-label may change by locale.
        # Primary: aria-label based selector
        # Fallback: placeholder-based selector
        return 'textarea[aria-label="Add a comment…"], textarea[placeholder="Add a comment…"]'

    def get_comment_field_fallback_selectors(self) -> list[str]:
        """Additional selectors for the Instagram comment input field."""
        return [
            'textarea[aria-label*="comment" i]',
            'textarea[placeholder*="comment" i]',
            'form textarea',
        ]

    def get_submit_selector(self) -> str:
        # The "Post" button appears after text is entered in the comment field.
        # TODO: This selector may need adjustment — Instagram sometimes uses a
        # div/span with role="button" and text content "Post" instead of a form submit.
        return 'button[type="submit"]'

    def verify_comment_posted(self, driver, comment_text: str) -> bool:
        """Verify the comment appears on the Instagram post page after submission.

        Checks the page source for the comment text. Instagram renders comments
        inline, so the text should be present in the DOM if submission succeeded.

        TODO: DOM verification is unreliable on Instagram due to dynamic loading
        and shadow DOM usage. Needs real browser testing to validate.

        Args:
            driver: The Selenium WebDriver instance.
            comment_text: The exact comment text that was submitted.

        Returns:
            True if the comment text is found on the page.
        """
        try:
            page_source = driver.page_source
            return comment_text in page_source
        except Exception:
            return False


class TikTokStrategy(PlatformStrategy):
    """
    TikTok automation strategy.

    Secondary platform — selectors are best-effort based on known DOM structures.
    TikTok uses multiple login methods (email, phone, QR code); this strategy
    targets the email/password flow.

    TODO: TikTok has aggressive bot detection (device fingerprinting, behavioral
    analysis). Headed Chrome with human-like timing is essential.
    """

    def get_login_selectors(self) -> LoginSelectors:
        # TikTok email/password login flow selectors.
        # TODO: TikTok's login page is highly dynamic and may require navigating
        # through multiple steps (select "Log in with email/username" first).
        return LoginSelectors(
            username_field='input[name="username"], input[placeholder*="Email"], input[placeholder*="Username"]',
            password_field='input[type="password"]',
            submit_button='button[data-e2e="login-button"], button[type="submit"]',
        )

    def get_comment_field_selector(self) -> str:
        # TikTok uses a contenteditable div for comment input.
        # TODO: The data-e2e attributes are test IDs that TikTok may remove or
        # rename without notice. The contenteditable fallback is more stable.
        return 'div[data-e2e="comment-input"], div[contenteditable="true"]'

    def get_comment_field_fallback_selectors(self) -> list[str]:
        """Additional selectors for the TikTok comment input."""
        return [
            'div[class*="comment-input"] div[contenteditable="true"]',
            'div[data-e2e="comment-input"] div[contenteditable="true"]',
        ]

    def get_submit_selector(self) -> str:
        # The post button within the comment section.
        # TODO: TikTok may disable this button until text is entered;
        # the automation must type first, then wait for the button to become active.
        return 'div[data-e2e="comment-post"], button[data-e2e="comment-post"]'

    def verify_comment_posted(self, driver, comment_text: str) -> bool:
        """Verify the comment appears on the TikTok video page after submission.

        Checks the page source for the comment text. TikTok loads comments
        dynamically, so there may be a brief delay before the comment appears.

        TODO: TikTok comment verification may be unreliable due to dynamic
        loading. Needs real browser testing to validate.

        Args:
            driver: The Selenium WebDriver instance.
            comment_text: The exact comment text that was submitted.

        Returns:
            True if the comment text is found on the page.
        """
        try:
            page_source = driver.page_source
            return comment_text in page_source
        except Exception:
            return False


class YouTubeStrategy(PlatformStrategy):
"""
YouTube automation strategy.

Secondary platform — selectors are best-effort based on known DOM structures.
YouTube uses multiple login methods (email, phone, QR code); this strategy
targets the email/password flow.

TODO: YouTube has aggressive bot detection (device fingerprinting, behavioral
analysis). Headed Chrome with human-like timing is essential.
"""

def get_login_selectors(self) -> LoginSelectors:
# YouTube email/password login flow selectors.
# TODO: YouTube's login page is highly dynamic and may require navigating
# through multiple steps (select "Log in with email/username" first).
return LoginSelectors(
username_field='input[name="username"], input[placeholder*="Email"], input[placeholder*="Username"]',
password_field='input[type="password"]',
submit_button='button[data-e2e="login-button"], button[type="submit"]',
)

def get_comment_field_selector(self) -> str:
# YouTube uses a contenteditable div for comment input.
# TODO: The data-e2e attributes are test IDs that YouTube may remove or
# rename without notice. The contenteditable fallback is more stable.
return 'div[data-e2e="comment-input"], div[contenteditable="true"]'

def get_comment_field_fallback_selectors(self) -> list[str]:
"""Additional selectors for the YouTube comment input."""
return [
'div[class*="comment-input"] div[contenteditable="true"]',
'div[data-e2e="comment-input"] div[contenteditable="true"]',
]

def get_submit_selector(self) -> str:
# The post button within the comment section.
# TODO: YouTube may disable this button until text is entered;
# the automation must type first, then wait for the button to become active.
return 'div[data-e2e="comment-post"], button[data-e2e="comment-post"]'

def verify_comment_posted(self, driver, comment_text: str) -> bool:
"""Verify the comment appears on the YouTube video page after submission.

Checks the page source for the comment text. YouTube loads comments
dynamically, so there may be a brief delay before the comment appears.

TODO: YouTube comment verification may be unreliable due to dynamic
loading. Needs real browser testing to validate.

Args:
driver: The Selenium WebDriver instance.
comment_text: The exact comment text that was submitted.

Returns:
True if the comment text is found on the page.
"""
try:
page_source = driver.page_source
return comment_text in page_source
except Exception:
return False


class LinkedInStrategy(PlatformStrategy):
"""
LinkedIn automation strategy.

Secondary platform — selectors are best-effort based on known DOM structures.
LinkedIn uses multiple login methods (email, phone, QR code); this strategy
targets the email/password flow.

TODO: LinkedIn has aggressive bot detection (device fingerprinting, behavioral
analysis). Headed Chrome with human-like timing is essential.
"""

def get_login_selectors(self) -> LoginSelectors:
# LinkedIn email/password login flow selectors.
# TODO: LinkedIn's login page is highly dynamic and may require navigating
# through multiple steps (select "Log in with email/username" first).
return LoginSelectors(
username_field='input[name="username"], input[placeholder*="Email"], input[placeholder*="Username"]',
password_field='input[type="password"]',
submit_button='button[data-e2e="login-button"], button[type="submit"]',
)

def get_comment_field_selector(self) -> str:
# LinkedIn uses a contenteditable div for comment input.
# TODO: The data-e2e attributes are test IDs that LinkedIn may remove or
# rename without notice. The contenteditable fallback is more stable.
return 'div[data-e2e="comment-input"], div[contenteditable="true"]'

def get_comment_field_fallback_selectors(self) -> list[str]:
"""Additional selectors for the LinkedIn comment input."""
return [
'div[class*="comment-input"] div[contenteditable="true"]',
'div[data-e2e="comment-input"] div[contenteditable="true"]',
]

def get_submit_selector(self) -> str:
# The post button within the comment section.
# TODO: LinkedIn may disable this button until text is entered;
# the automation must type first, then wait for the button to become active.
return 'div[data-e2e="comment-post"], button[data-e2e="comment-post"]'

def verify_comment_posted(self, driver, comment_text: str) -> bool:
"""Verify the comment appears on the LinkedIn video page after submission.

Checks the page source for the comment text. LinkedIn loads comments
dynamically, so there may be a brief delay before the comment appears.

TODO: LinkedIn comment verification may be unreliable due to dynamic
loading. Needs real browser testing to validate.

Args:
driver: The Selenium WebDriver instance.
comment_text: The exact comment text that was submitted.

Returns:
True if the comment text is found on the page.
"""
try:
page_source = driver.page_source
return comment_text in page_source
except Exception:
return False

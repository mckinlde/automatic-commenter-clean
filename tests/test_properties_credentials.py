"""Property-based tests for credential validation (Property 2).

Uses Hypothesis to validate that empty or whitespace-only credentials
are always rejected by BrowserAutomationEngine.validate_credentials().
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from browser_engine import BrowserAutomationEngine
from models_ac import LoginResult


# ─── Strategies ──────────────────────────────────────────────────────────────

# Strategy for non-empty, non-whitespace-only strings (valid credentials)
valid_credential_strings = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
).filter(lambda s: s.strip() != "")

# Strategy for empty or whitespace-only strings (invalid credentials)
whitespace_chars = st.sampled_from([" ", "\t", "\n", "\r", "\x0b", "\x0c"])

empty_or_whitespace_strings = st.one_of(
    st.just(""),
    st.text(alphabet=whitespace_chars, min_size=1, max_size=50),
)


# ─── Property 2: Empty or whitespace-only credentials are rejected ───────────
# Feature: automatic-commenter, Property 2: Empty or whitespace-only credentials are rejected

class TestProperty2CredentialValidation:
    """
    For any pair of credential strings (username, password) where at least one
    field is empty or composed entirely of whitespace characters, the credential
    validation shall reject the submission and return a validation error.

    **Validates: Requirements 4.6**
    """

    @given(username=valid_credential_strings, password=valid_credential_strings)
    @settings(max_examples=100)
    def test_valid_credentials_return_none(self, username, password):
        """For any non-whitespace username and non-whitespace password,
        validate_credentials returns None (valid)."""
        result = BrowserAutomationEngine.validate_credentials(username, password)
        assert result is None, (
            f"Expected None for valid credentials, got {result!r} "
            f"for username={username!r}, password={password!r}"
        )

    @given(username=empty_or_whitespace_strings, password=st.text(min_size=0, max_size=100))
    @settings(max_examples=100)
    def test_empty_or_whitespace_username_returns_login_result_failure(self, username, password):
        """For any empty or whitespace-only username with any password,
        returns LoginResult with success=False."""
        result = BrowserAutomationEngine.validate_credentials(username, password)
        assert result is not None, (
            f"Expected LoginResult for invalid username, got None "
            f"for username={username!r}, password={password!r}"
        )
        assert isinstance(result, LoginResult), (
            f"Expected LoginResult instance, got {type(result).__name__}"
        )
        assert result.success is False, (
            f"Expected success=False, got success={result.success} "
            f"for username={username!r}"
        )
        assert result.error_message is not None, (
            "Expected an error message for invalid credentials"
        )

    @given(username=valid_credential_strings, password=empty_or_whitespace_strings)
    @settings(max_examples=100)
    def test_empty_or_whitespace_password_returns_login_result_failure(self, username, password):
        """For any non-whitespace username with empty or whitespace-only password,
        returns LoginResult with success=False."""
        result = BrowserAutomationEngine.validate_credentials(username, password)
        assert result is not None, (
            f"Expected LoginResult for invalid password, got None "
            f"for username={username!r}, password={password!r}"
        )
        assert isinstance(result, LoginResult), (
            f"Expected LoginResult instance, got {type(result).__name__}"
        )
        assert result.success is False, (
            f"Expected success=False, got success={result.success} "
            f"for password={password!r}"
        )
        assert result.error_message is not None, (
            "Expected an error message for invalid credentials"
        )

    @given(username=empty_or_whitespace_strings, password=empty_or_whitespace_strings)
    @settings(max_examples=100)
    def test_both_empty_or_whitespace_returns_login_result_failure(self, username, password):
        """For any pair where both are empty/whitespace,
        returns LoginResult with success=False."""
        result = BrowserAutomationEngine.validate_credentials(username, password)
        assert result is not None, (
            f"Expected LoginResult when both credentials invalid, got None "
            f"for username={username!r}, password={password!r}"
        )
        assert isinstance(result, LoginResult), (
            f"Expected LoginResult instance, got {type(result).__name__}"
        )
        assert result.success is False, (
            f"Expected success=False, got success={result.success} "
            f"for username={username!r}, password={password!r}"
        )
        assert result.error_message is not None, (
            "Expected an error message for invalid credentials"
        )

"""Property-based tests for worker behavior (Properties 10, 11, 12).

Uses Hypothesis to validate rate-limit pause behavior, comment preview
truncation, and log entry timestamp format in CommentWorker.
"""

import re
from datetime import datetime
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from worker import CommentWorker
from models_ac import WorkerConfig


# ─── Strategies ──────────────────────────────────────────────────────────────

# Strategy for positive retry-after durations (seconds)
positive_durations = st.integers(min_value=1, max_value=300)

# Strategy for error messages containing a retry-after number
rate_limit_messages_with_duration = st.builds(
    lambda prefix, duration, suffix: f"{prefix}{duration}{suffix}",
    prefix=st.sampled_from([
        "Rate limited. Retry after ",
        "Too many requests. Wait ",
        "rate-limit exceeded, retry in ",
        "429: retry after ",
    ]),
    duration=positive_durations,
    suffix=st.sampled_from([" seconds", "s", " sec", ""]),
)

# Strategy for arbitrary comment strings (including empty and very long)
comment_strings = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=500,
)

# Strategy for arbitrary error messages
error_messages = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=200,
)

# Strategy for valid datetime objects
valid_datetimes = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2099, 12, 31),
)


# ─── Helper: create a minimal WorkerConfig for testing ───────────────────────

def _make_worker_config():
    """Create a minimal WorkerConfig for instantiating CommentWorker."""
    return WorkerConfig(
        platform="facebook",
        campaign_server_url="https://example.com/api",
        api_key="test-api-key",
        post_cursor=None,
    )


# ─── Property 10: Rate-limit pause matches retry-after value ─────────────────
# Feature: automatic-commenter, Property 10: Rate-limit pause matches retry-after value

class TestProperty10RateLimitPause:
    """
    For any rate-limiting response that includes a retry-after duration value
    D > 0, the AC_Client shall pause for exactly D seconds before resuming.

    **Validates: Requirements 10.5**
    """

    @given(duration=positive_durations)
    @settings(max_examples=100)
    def test_extract_retry_after_finds_positive_integer(self, duration):
        """For any error message containing a positive integer D,
        _extract_retry_after shall return that integer."""
        message = f"Rate limited. Retry after {duration} seconds"
        result = CommentWorker._extract_retry_after(message)
        assert result == duration, (
            f"Expected _extract_retry_after to return {duration}, "
            f"got {result} for message={message!r}"
        )

    @given(duration=positive_durations)
    @settings(max_examples=100)
    def test_pause_with_countdown_sleeps_d_times(self, duration):
        """For any duration D > 0, _pause_with_countdown shall call
        time.sleep(1) exactly D times (once per countdown second)."""
        config = _make_worker_config()
        worker = CommentWorker(config)

        with patch("worker.time.sleep") as mock_sleep:
            worker._pause_with_countdown(duration, "Rate limited")
            assert mock_sleep.call_count == duration, (
                f"Expected time.sleep to be called {duration} times, "
                f"got {mock_sleep.call_count} calls"
            )
            # Each call should be sleep(1)
            for call in mock_sleep.call_args_list:
                assert call == ((1,),) or call == ((), {"seconds": 1}), (
                    f"Expected sleep(1), got {call}"
                )

    @given(message=rate_limit_messages_with_duration)
    @settings(max_examples=100)
    def test_extract_retry_after_from_varied_messages(self, message):
        """For any rate-limit message containing a number, _extract_retry_after
        shall return a positive integer (the first number found)."""
        result = CommentWorker._extract_retry_after(message)
        assert result is not None, (
            f"Expected a non-None result for message={message!r}"
        )
        assert result > 0, (
            f"Expected positive integer, got {result} for message={message!r}"
        )


# ─── Property 11: Comment preview truncation ─────────────────────────────────
# Feature: automatic-commenter, Property 11: Comment preview truncation

class TestProperty11CommentPreviewTruncation:
    """
    For any comment string, the displayed preview shall contain at most 100
    characters. If the original string length exceeds 100, the preview shall
    be exactly the first 100 characters.

    **Validates: Requirements 11.1**
    """

    @given(comment_text=comment_strings)
    @settings(max_examples=100)
    def test_preview_never_exceeds_100_chars(self, comment_text):
        """For any comment string, the truncated preview has at most 100 characters."""
        preview = comment_text[:100]
        assert len(preview) <= 100, (
            f"Preview length {len(preview)} exceeds 100 for "
            f"comment of length {len(comment_text)}"
        )

    @given(comment_text=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=101,
        max_size=500,
    ))
    @settings(max_examples=100)
    def test_long_comment_preview_is_first_100_chars(self, comment_text):
        """For any comment string longer than 100 chars, the preview is
        exactly the first 100 characters."""
        preview = comment_text[:100]
        assert len(preview) == 100, (
            f"Expected preview length 100, got {len(preview)}"
        )
        assert preview == comment_text[:100], (
            f"Preview does not match first 100 chars of comment"
        )

    @given(comment_text=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=0,
        max_size=100,
    ))
    @settings(max_examples=100)
    def test_short_comment_preview_is_full_string(self, comment_text):
        """For any comment string of length <= 100, the preview is the
        full original string."""
        preview = comment_text[:100]
        assert preview == comment_text, (
            f"Expected preview to equal full comment for short string, "
            f"got preview={preview!r} != comment={comment_text!r}"
        )


# ─── Property 12: Log entry timestamp format ─────────────────────────────────
# Feature: automatic-commenter, Property 12: Log entry timestamp format

class TestProperty12LogEntryTimestampFormat:
    """
    For any error message appended to the activity log, the formatted entry
    shall contain a timestamp matching the pattern HH:MM:SS (where HH is 00-23,
    MM is 00-59, SS is 00-59).

    **Validates: Requirements 11.3**
    """

    # Regex pattern for valid HH:MM:SS timestamps
    TIMESTAMP_PATTERN = re.compile(
        r"^([01]\d|2[0-3]):([0-5]\d):([0-5]\d)$"
    )

    @given(dt=valid_datetimes)
    @settings(max_examples=100)
    def test_strftime_produces_valid_hh_mm_ss(self, dt):
        """For any datetime, strftime('%H:%M:%S') produces a valid HH:MM:SS timestamp."""
        timestamp = dt.strftime("%H:%M:%S")
        assert self.TIMESTAMP_PATTERN.match(timestamp), (
            f"Timestamp {timestamp!r} does not match HH:MM:SS pattern "
            f"for datetime {dt!r}"
        )

    @given(message=error_messages)
    @settings(max_examples=100)
    def test_emit_error_produces_valid_timestamp(self, message):
        """For any error message, _emit_error emits a signal with a
        valid HH:MM:SS timestamp."""
        config = _make_worker_config()
        worker = CommentWorker(config)

        # Mock the error_signal to capture the emitted values
        emitted_values = []
        worker.error_signal = MagicMock()
        worker.error_signal.emit = lambda msg, ts: emitted_values.append((msg, ts))

        worker._emit_error(message)

        assert len(emitted_values) == 1, (
            f"Expected exactly 1 emission, got {len(emitted_values)}"
        )
        emitted_msg, emitted_ts = emitted_values[0]
        assert emitted_msg == message, (
            f"Expected emitted message to equal input message"
        )
        assert self.TIMESTAMP_PATTERN.match(emitted_ts), (
            f"Timestamp {emitted_ts!r} does not match HH:MM:SS pattern"
        )

"""
Property-based tests for PostCursorManager cursor operations.

Tests Properties 6, 7, 8, 9, and 14 from the design document.
Validates: Requirements 7.1, 7.4, 8.1, 8.2, 8.3, 8.4, 8.6, 9.3, 10.1, 10.3
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from cursor_manager import PostCursorManager
from models_ac import PostEntry


# ── Strategies ───────────────────────────────────────────────────────────────

# Strategy for platform strings (non-empty, no pipe character to avoid key collision)
platform_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=30,
)

# Strategy for campaign URLs
campaign_url_st = st.from_regex(r"https://[a-z]{1,20}\.[a-z]{2,5}/[a-z]{1,10}", fullmatch=True)

# Strategy for non-negative cursor values
cursor_value_st = st.integers(min_value=0, max_value=10000)


# Strategy for a non-empty sorted list of unique indices (simulates List_A)
def list_a_st(min_size=1, max_size=20):
    """Generate a non-empty list of PostEntry with unique sequential indices."""
    return st.lists(
        st.integers(min_value=0, max_value=1000),
        min_size=min_size,
        max_size=max_size,
        unique=True,
    ).map(
        lambda indices: [
            PostEntry(index=i, url=f"https://example.com/post/{i}", platform="facebook")
            for i in sorted(indices)
        ]
    )


def _make_manager() -> PostCursorManager:
    """Create a PostCursorManager with a fresh temp directory."""
    tmp_dir = tempfile.mkdtemp()
    return PostCursorManager(Path(tmp_dir) / "cursors.json")


# ── Property 6: Cursor resolution determines next unprocessed post ───────────
# Feature: automatic-commenter, Property 6: Cursor resolution determines next unprocessed post


class TestProperty6CursorResolution:
    """
    Property 6: Cursor resolution determines next unprocessed post.

    For any stored Post_Cursor value C (or None) and any non-empty List_A with
    sequential indices, the resolved starting position shall be:
    (a) if C is None, the minimum index in List_A;
    (b) if C exists in List_A, the minimum index > C;
    (c) if C does not exist in List_A, the minimum index > C that does exist;
    (d) if no index > C exists, indicate "all processed" (None).

    **Validates: Requirements 8.2, 8.3, 8.6, 9.3**
    """

    @settings(max_examples=100)
    @given(list_a=list_a_st())
    def test_case_a_cursor_none_returns_minimum_index(self, list_a):
        """When cursor is None, resolve returns the minimum index in List_A."""
        # Feature: automatic-commenter, Property 6: Cursor resolution determines next unprocessed post
        mgr = _make_manager()
        result = mgr.resolve_cursor(None, list_a, log=lambda _: None)
        expected = min(entry.index for entry in list_a)
        assert result == expected

    @settings(max_examples=100)
    @given(list_a=list_a_st(min_size=2))
    def test_case_b_cursor_exists_returns_next_index(self, list_a):
        """When cursor exists in List_A with entries after it, return min index > cursor."""
        # Feature: automatic-commenter, Property 6: Cursor resolution determines next unprocessed post
        mgr = _make_manager()
        indices = sorted(entry.index for entry in list_a)
        # Pick a cursor that is NOT the last index (so there's a next)
        stored_cursor = indices[0]  # First index guarantees something after it
        result = mgr.resolve_cursor(stored_cursor, list_a, log=lambda _: None)
        expected = min(i for i in indices if i > stored_cursor)
        assert result == expected

    @settings(max_examples=100)
    @given(list_a=list_a_st(), gap=st.integers(min_value=1, max_value=50))
    def test_case_c_cursor_not_in_list_returns_next_available(self, list_a, gap):
        """When cursor doesn't exist in List_A, return min index > cursor that exists."""
        # Feature: automatic-commenter, Property 6: Cursor resolution determines next unprocessed post
        mgr = _make_manager()
        indices = sorted(entry.index for entry in list_a)
        # Create a cursor value that doesn't exist in list_a but has entries after it
        min_index = indices[0]
        stored_cursor = max(0, min_index - gap)
        assume(stored_cursor not in indices)
        assume(any(i > stored_cursor for i in indices))

        result = mgr.resolve_cursor(stored_cursor, list_a, log=lambda _: None)
        expected = min(i for i in indices if i > stored_cursor)
        assert result == expected

    @settings(max_examples=100)
    @given(list_a=list_a_st())
    def test_case_d_no_index_greater_returns_none(self, list_a):
        """When no index > cursor exists, return None (all processed)."""
        # Feature: automatic-commenter, Property 6: Cursor resolution determines next unprocessed post
        mgr = _make_manager()
        indices = sorted(entry.index for entry in list_a)
        # Set cursor to the max index — nothing is greater
        stored_cursor = indices[-1]
        result = mgr.resolve_cursor(stored_cursor, list_a, log=lambda _: None)
        assert result is None


# ── Property 7: Cursor advances to completed post index on success ───────────
# Feature: automatic-commenter, Property 7: Cursor advances to completed post index on success


class TestProperty7CursorAdvancesOnSuccess:
    """
    Property 7: Cursor advances to completed post index on success.

    For any successful comment post on a post with index I, the Post_Cursor
    shall be updated to exactly I after the operation completes.

    **Validates: Requirements 7.4**
    """

    @settings(max_examples=100)
    @given(
        platform=platform_st,
        campaign_url=campaign_url_st,
        index=cursor_value_st,
    )
    def test_cursor_set_to_post_index_on_success(self, platform, campaign_url, index):
        """After successful post at index I, cursor equals I."""
        # Feature: automatic-commenter, Property 7: Cursor advances to completed post index on success
        mgr = _make_manager()
        # Simulate successful post: set_cursor is called with the post's index
        mgr.set_cursor(platform, campaign_url, index)
        result = mgr.get_cursor(platform, campaign_url)
        assert result == index


# ── Property 8: Cursor is unchanged on failure or skip ───────────────────────
# Feature: automatic-commenter, Property 8: Cursor is unchanged on failure or skip


class TestProperty8CursorUnchangedOnFailure:
    """
    Property 8: Cursor is unchanged on failure or skip.

    For any post processing operation that results in failure, the Post_Cursor
    shall remain at its value prior to the failed operation.

    **Validates: Requirements 10.1, 10.3**
    """

    @settings(max_examples=100)
    @given(
        platform=platform_st,
        campaign_url=campaign_url_st,
        initial_cursor=cursor_value_st,
        failed_post_index=cursor_value_st,
    )
    def test_cursor_unchanged_when_set_not_called(
        self, platform, campaign_url, initial_cursor, failed_post_index
    ):
        """If set_cursor is not called (failure/skip), cursor remains at prior value."""
        # Feature: automatic-commenter, Property 8: Cursor is unchanged on failure or skip
        mgr = _make_manager()
        # Set initial cursor
        mgr.set_cursor(platform, campaign_url, initial_cursor)

        # Simulate failure: we do NOT call set_cursor for the failed_post_index
        # Verify cursor has not changed
        result = mgr.get_cursor(platform, campaign_url)
        assert result == initial_cursor

    @settings(max_examples=100)
    @given(
        platform=platform_st,
        campaign_url=campaign_url_st,
        failed_post_index=cursor_value_st,
    )
    def test_cursor_remains_none_on_failure_when_unset(
        self, platform, campaign_url, failed_post_index
    ):
        """If cursor was never set and a failure occurs (no set_cursor call), it stays None."""
        # Feature: automatic-commenter, Property 8: Cursor is unchanged on failure or skip
        mgr = _make_manager()

        # Simulate failure: we do NOT call set_cursor
        result = mgr.get_cursor(platform, campaign_url)
        assert result is None


# ── Property 9: Cursor storage isolation per platform and campaign ────────────
# Feature: automatic-commenter, Property 9: Cursor storage isolation per platform and campaign


class TestProperty9CursorIsolation:
    """
    Property 9: Cursor storage isolation per platform and campaign.

    For any two distinct (platform, campaign_server_url) pairs, setting the
    cursor for one pair shall not affect the cursor value stored for any other pair.

    **Validates: Requirements 8.4**
    """

    @settings(max_examples=100)
    @given(
        platform_a=platform_st,
        url_a=campaign_url_st,
        platform_b=platform_st,
        url_b=campaign_url_st,
        cursor_a=cursor_value_st,
        cursor_b=cursor_value_st,
    )
    def test_distinct_pairs_are_isolated(
        self, platform_a, url_a, platform_b, url_b, cursor_a, cursor_b
    ):
        """Setting cursor for one (platform, url) pair doesn't affect another."""
        # Feature: automatic-commenter, Property 9: Cursor storage isolation per platform and campaign
        # Ensure the pairs are actually distinct
        assume((platform_a, url_a) != (platform_b, url_b))

        mgr = _make_manager()

        # Set cursor for pair A
        mgr.set_cursor(platform_a, url_a, cursor_a)
        # Set cursor for pair B
        mgr.set_cursor(platform_b, url_b, cursor_b)

        # Verify each pair retains its own value
        assert mgr.get_cursor(platform_a, url_a) == cursor_a
        assert mgr.get_cursor(platform_b, url_b) == cursor_b

    @settings(max_examples=100)
    @given(
        platform_a=platform_st,
        url_a=campaign_url_st,
        platform_b=platform_st,
        url_b=campaign_url_st,
        cursor_a=cursor_value_st,
        new_cursor_b=cursor_value_st,
    )
    def test_updating_one_pair_preserves_other(
        self, platform_a, url_a, platform_b, url_b, cursor_a, new_cursor_b
    ):
        """Updating cursor for pair B after pair A is set doesn't change pair A."""
        # Feature: automatic-commenter, Property 9: Cursor storage isolation per platform and campaign
        assume((platform_a, url_a) != (platform_b, url_b))

        mgr = _make_manager()

        # Set initial cursor for pair A
        mgr.set_cursor(platform_a, url_a, cursor_a)

        # Update cursor for pair B (should not affect A)
        mgr.set_cursor(platform_b, url_b, new_cursor_b)

        # Pair A should be unchanged
        assert mgr.get_cursor(platform_a, url_a) == cursor_a


# ── Property 14: Cursor persistence round-trip ───────────────────────────────
# Feature: automatic-commenter, Property 14: Cursor persistence round-trip


class TestProperty14CursorPersistenceRoundTrip:
    """
    Property 14: Cursor persistence round-trip.

    For any valid cursor state (platform string, campaign URL, integer cursor
    value >= 0), persisting the cursor then reading it back shall return the
    same integer value.

    **Validates: Requirements 8.1**
    """

    @settings(max_examples=100)
    @given(
        platform=platform_st,
        campaign_url=campaign_url_st,
        cursor_value=cursor_value_st,
    )
    def test_set_then_get_returns_same_value(self, platform, campaign_url, cursor_value):
        """Persisting a cursor and reading it back returns the same integer."""
        # Feature: automatic-commenter, Property 14: Cursor persistence round-trip
        mgr = _make_manager()
        mgr.set_cursor(platform, campaign_url, cursor_value)
        result = mgr.get_cursor(platform, campaign_url)
        assert result == cursor_value

    @settings(max_examples=100)
    @given(
        platform=platform_st,
        campaign_url=campaign_url_st,
        cursor_value=cursor_value_st,
    )
    def test_round_trip_survives_reload(self, platform, campaign_url, cursor_value):
        """Cursor persists across manager instances (simulating app restart)."""
        # Feature: automatic-commenter, Property 14: Cursor persistence round-trip
        tmp_dir = tempfile.mkdtemp()
        storage_path = Path(tmp_dir) / "cursors.json"

        # Write with one instance
        mgr1 = PostCursorManager(storage_path)
        mgr1.set_cursor(platform, campaign_url, cursor_value)

        # Read with a fresh instance (simulating restart)
        mgr2 = PostCursorManager(storage_path)
        result = mgr2.get_cursor(platform, campaign_url)
        assert result == cursor_value

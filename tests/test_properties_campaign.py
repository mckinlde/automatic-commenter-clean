"""Property-based tests for campaign client (Properties 3, 4, 5).

Uses Hypothesis to validate correctness properties for the campaign_client module.
"""

from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from campaign_client import (
    CampaignConnectionError,
    CampaignServerClient,
    CampaignTimeoutError,
    EmptyListError,
    compute_effective_index,
    retry_with_backoff,
)


# ─── Property 3: Exponential backoff delay calculation ───────────────────────
# Feature: automatic-commenter, Property 3: Exponential backoff delay calculation


class TestProperty3ExponentialBackoffDelayCalculation:
    """
    For any retry attempt number n in {0, 1, 2}, the computed retry delay shall
    be `base * 2^n` seconds (where base = 2), yielding delays of 2, 4, and 8
    seconds. After 3 failed attempts, no further retries shall be attempted.

    **Validates: Requirements 5.3, 9.5**
    """

    @given(
        num_failures=st.integers(min_value=1, max_value=2),
    )
    @settings(max_examples=100)
    def test_backoff_delays_match_formula(self, num_failures):
        """For n transient failures before success, delays are base * 2^i for i in 0..n-1."""
        base_delay = 2.0
        max_retries = 3
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            if call_count <= num_failures:
                raise CampaignConnectionError("transient")
            return "success"

        with patch("campaign_client.time.sleep") as mock_sleep:
            result = retry_with_backoff(
                operation, max_retries=max_retries, base_delay=base_delay
            )

        assert result == "success"
        assert mock_sleep.call_count == num_failures

        # Verify each delay matches the formula: base * 2^attempt
        for attempt_index in range(num_failures):
            expected_delay = base_delay * (2 ** attempt_index)
            actual_delay = mock_sleep.call_args_list[attempt_index][0][0]
            assert actual_delay == expected_delay, (
                f"Attempt {attempt_index}: expected delay {expected_delay}, "
                f"got {actual_delay}"
            )

    @given(
        error_type=st.sampled_from([CampaignConnectionError, CampaignTimeoutError]),
    )
    @settings(max_examples=100)
    def test_no_retry_after_three_failures(self, error_type):
        """After 3 failed attempts, the exception is raised (no 4th attempt)."""
        base_delay = 2.0
        max_retries = 3
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            raise error_type("persistent failure")

        with patch("campaign_client.time.sleep") as mock_sleep:
            with pytest.raises(error_type):
                retry_with_backoff(
                    operation, max_retries=max_retries, base_delay=base_delay
                )

        # Exactly 3 calls to the operation (no 4th attempt)
        assert call_count == max_retries
        # Sleep is called between attempts (max_retries - 1 times)
        assert mock_sleep.call_count == max_retries - 1

        # Verify the actual sleep delays: 2, 4
        expected_delays = [base_delay * (2 ** i) for i in range(max_retries - 1)]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays


# ─── Property 4: List_A non-empty validation gate ────────────────────────────
# Feature: automatic-commenter, Property 4: List_A non-empty validation gate


class TestProperty4ListANonEmptyValidationGate:
    """
    For any Campaign Server response, the AC_Client shall proceed with commenting
    only when the response contains at least one post URL. For responses with zero
    post URLs, processing shall not proceed.

    **Validates: Requirements 5.4, 5.5**
    """

    @given(
        num_posts=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_non_empty_list_a_succeeds(self, num_posts):
        """fetch_list_a succeeds when response contains at least one post URL."""
        posts_data = [
            {
                "index": i,
                "url": f"https://facebook.com/post/{i}",
                "platform": "facebook",
            }
            for i in range(num_posts)
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"posts": posts_data, "total": num_posts}
        mock_response.raise_for_status = MagicMock()

        client = CampaignServerClient(
            base_url="https://campaign.example.com/api",
            api_key="test-key",
            timeout=5,
        )

        with patch("campaign_client.requests.get", return_value=mock_response):
            result = client.fetch_list_a()

        assert len(result) == num_posts
        for i, entry in enumerate(result):
            assert entry.index == i
            assert entry.url == f"https://facebook.com/post/{i}"
            assert entry.platform == "facebook"

    @settings(max_examples=100)
    @given(data=st.data())
    def test_empty_list_a_raises_error(self, data):
        """fetch_list_a raises EmptyListError when response has zero posts."""
        # Generate an empty posts list (always empty for this property)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"posts": [], "total": 0}
        mock_response.raise_for_status = MagicMock()

        client = CampaignServerClient(
            base_url="https://campaign.example.com/api",
            api_key="test-key",
            timeout=5,
        )

        with patch("campaign_client.requests.get", return_value=mock_response):
            with pytest.raises(EmptyListError):
                client.fetch_list_a()


# ─── Property 5: Comment pointer cycling ─────────────────────────────────────
# Feature: automatic-commenter, Property 5: Comment pointer cycling


class TestProperty5CommentPointerCycling:
    """
    For any List_B of length N > 0 and any Comment_Pointer value P ≥ 0,
    the effective comment index shall be P mod N, wrapping back to 0 when P ≥ N.

    **Validates: Requirements 6.2**
    """

    @given(
        pointer=st.integers(min_value=0, max_value=10_000),
        list_b_length=st.integers(min_value=1, max_value=500),
    )
    @settings(max_examples=100)
    def test_effective_index_is_in_valid_range(self, pointer, list_b_length):
        """The effective index is always in [0, N) for any P >= 0 and N > 0."""
        effective = compute_effective_index(pointer, list_b_length)
        assert 0 <= effective < list_b_length, (
            f"Expected 0 <= {effective} < {list_b_length} "
            f"for pointer={pointer}"
        )

    @given(
        pointer=st.integers(min_value=0, max_value=10_000),
        list_b_length=st.integers(min_value=1, max_value=500),
    )
    @settings(max_examples=100)
    def test_effective_index_equals_modular_arithmetic(self, pointer, list_b_length):
        """The effective index equals P mod N exactly."""
        effective = compute_effective_index(pointer, list_b_length)
        expected = pointer % list_b_length
        assert effective == expected, (
            f"Expected {expected}, got {effective} "
            f"for pointer={pointer}, N={list_b_length}"
        )

    @given(
        list_b_length=st.integers(min_value=1, max_value=500),
    )
    @settings(max_examples=100)
    def test_pointer_wraps_back_to_zero_at_n(self, list_b_length):
        """When P == N, the effective index wraps back to 0."""
        effective = compute_effective_index(list_b_length, list_b_length)
        assert effective == 0, (
            f"Expected 0 when pointer == N={list_b_length}, got {effective}"
        )

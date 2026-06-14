"""
Campaign Server HTTP client for the Automatic Commenter.

Provides the CampaignServerClient class that communicates with the Campaign
Server REST API to fetch List_A (post targets) and request comment assignments
from List_B. Includes retry logic with exponential backoff for resilient
network communication.
"""

import time
from typing import Callable, TypeVar

import requests

from config_ac import (
    BACKOFF_BASE_SECONDS,
    CAMPAIGN_SERVER_TIMEOUT_SECONDS,
    MAX_RETRIES,
)
from models_ac import CommentAssignment, PostEntry

T = TypeVar("T")


# ─── Custom Exception Hierarchy ──────────────────────────────────────────────


class CampaignServerError(Exception):
    """Base exception for all Campaign Server communication errors."""
    pass


class EmptyListError(CampaignServerError):
    """Raised when List_A contains zero post URLs."""
    pass


class NoCommentsAvailableError(CampaignServerError):
    """Raised when the Campaign Server returns 404/no_comments_available."""
    pass


class CampaignAuthError(CampaignServerError):
    """Raised on HTTP 401 or 403 authentication/authorization failures."""
    pass


class CampaignConnectionError(CampaignServerError):
    """Raised on connection failures (wraps ConnectionError)."""
    pass


class CampaignTimeoutError(CampaignServerError):
    """Raised on request timeouts (wraps TimeoutError)."""
    pass


def retry_with_backoff(
    operation: Callable[[], T],
    max_retries: int = MAX_RETRIES,
    base_delay: float = BACKOFF_BASE_SECONDS,
) -> T:
    """
    Execute an operation with exponential backoff on transient failures.

    Retries on CampaignConnectionError and CampaignTimeoutError only.
    Other exceptions propagate immediately.

    Delay formula: base_delay * (2 ** attempt)
      - Attempt 0: 2s
      - Attempt 1: 4s
      - Attempt 2: 8s

    Args:
        operation: A callable that performs the network operation.
        max_retries: Maximum number of retry attempts (default 3).
        base_delay: Base delay in seconds for backoff calculation (default 2).

    Returns:
        The result of a successful operation call.

    Raises:
        CampaignConnectionError: If all retries are exhausted due to connection errors.
        CampaignTimeoutError: If all retries are exhausted due to timeout errors.
    """
    for attempt in range(max_retries):
        try:
            return operation()
        except (CampaignConnectionError, CampaignTimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)

    # This line should never be reached, but satisfies type checkers.
    raise RuntimeError("retry_with_backoff exhausted without raising")


def compute_effective_index(pointer: int, list_b_length: int) -> int:
    """
    Compute the effective comment index given a pointer and list length.

    Implements the Comment_Pointer cycling logic: for any List_B of length
    N > 0 and any Comment_Pointer value P ≥ 0, the effective index is P mod N.

    Args:
        pointer: The current Comment_Pointer value (must be ≥ 0).
        list_b_length: The length of List_B (must be > 0).

    Returns:
        The effective comment index in range [0, list_b_length).

    Raises:
        ValueError: If list_b_length ≤ 0 or pointer < 0.
    """
    if list_b_length <= 0:
        raise ValueError("list_b_length must be > 0")
    if pointer < 0:
        raise ValueError("pointer must be >= 0")
    return pointer % list_b_length


class CampaignServerClient:
    """
    HTTP client for Campaign Server communication.

    Handles fetching List_A (post targets) and requesting comment assignments
    from List_B. All requests include Bearer token authentication and are
    subject to retry with exponential backoff on transient failures.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = CAMPAIGN_SERVER_TIMEOUT_SECONDS,
    ):
        """
        Initialize the Campaign Server client.

        Args:
            base_url: The base URL of the Campaign Server (e.g. "https://campaign.example.com/api").
            api_key: The API key for Bearer token authentication.
            timeout: Request timeout in seconds (default from config).
        """
        # Strip trailing slash for consistent URL joining
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        """Construct the standard Authorization header."""
        return {"Authorization": f"Bearer {self.api_key}"}

    def fetch_list_a(self) -> list[PostEntry]:
        """
        Fetch the current post list (List_A) from the Campaign Server.

        Sends GET /list_a with Bearer authentication. Retries up to 3 times
        with exponential backoff on connection/timeout errors.

        Returns:
            A list of PostEntry objects representing the target posts (guaranteed non-empty).

        Raises:
            EmptyListError: If the response contains zero post URLs.
            CampaignAuthError: If the server returns 401 or 403.
            CampaignConnectionError: If the server is unreachable after retries.
            CampaignTimeoutError: If the server does not respond within the timeout after retries.
            requests.HTTPError: If the server returns another HTTP error status.
            ValueError: If the response JSON is malformed or missing required fields.
        """

        def _do_fetch() -> list[PostEntry]:
            try:
                response = requests.get(
                    f"{self.base_url}/list_a",
                    headers=self._headers,
                    timeout=self.timeout,
                )
            except requests.ConnectionError as e:
                raise CampaignConnectionError(
                    f"Unable to connect to Campaign Server: {e}"
                ) from e
            except requests.Timeout as e:
                raise CampaignTimeoutError(
                    f"Campaign Server request timed out: {e}"
                ) from e

            if response.status_code in (401, 403):
                raise CampaignAuthError(
                    f"Authentication failed with status {response.status_code}"
                )

            response.raise_for_status()

            data = response.json()
            posts_data = data.get("posts", [])

            entries = [
                PostEntry(
                    index=post["index"],
                    url=post["url"],
                    platform=post["platform"],
                )
                for post in posts_data
            ]

            if not entries:
                raise EmptyListError(
                    "List_A contains zero post URLs — cannot proceed with commenting"
                )

            return entries

        return retry_with_backoff(_do_fetch)

    def request_comment_assignment(self, platform: str) -> CommentAssignment:
        """
        Request the next comment assignment from the Campaign Server.

        Sends POST /assign_comment with the selected platform. The server
        atomically assigns the next comment from List_B and increments the
        global Comment_Pointer.

        Args:
            platform: The social media platform identifier (e.g. "facebook").

        Returns:
            A CommentAssignment with the comment text and assigned index.

        Raises:
            NoCommentsAvailableError: If the server returns 404 with no_comments_available.
            CampaignAuthError: If the server returns 401 or 403.
            CampaignConnectionError: If the server is unreachable after retries.
            CampaignTimeoutError: If the server does not respond within the timeout after retries.
            requests.HTTPError: If the server returns another HTTP error status.
            ValueError: If the response JSON is malformed or missing required fields.
        """

        def _do_request() -> CommentAssignment:
            try:
                response = requests.post(
                    f"{self.base_url}/assign_comment",
                    headers=self._headers,
                    json={"platform": platform},
                    timeout=self.timeout,
                )
            except requests.ConnectionError as e:
                raise CampaignConnectionError(
                    f"Unable to connect to Campaign Server: {e}"
                ) from e
            except requests.Timeout as e:
                raise CampaignTimeoutError(
                    f"Campaign Server request timed out: {e}"
                ) from e

            if response.status_code in (401, 403):
                raise CampaignAuthError(
                    f"Authentication failed with status {response.status_code}"
                )

            if response.status_code == 404:
                raise NoCommentsAvailableError(
                    "No comments available for assignment"
                )

            response.raise_for_status()

            data = response.json()

            return CommentAssignment(
                comment_text=data["comment_text"],
                comment_index=data["comment_index"],
            )

        return retry_with_backoff(_do_request)

    def validate_connection(self) -> bool:
        """
        Test connectivity and authentication with the Campaign Server.

        Performs a lightweight GET request to /list_a with a 10-second timeout
        to verify the server is reachable and the API key is accepted.

        Returns:
            True if the server responds successfully (2xx), False otherwise.
        """
        try:
            response = requests.get(
                f"{self.base_url}/list_a",
                headers=self._headers,
                timeout=10,
            )
            return response.ok
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            return False
        except Exception:
            return False

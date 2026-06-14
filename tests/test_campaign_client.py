"""
Unit tests for CampaignServerClient response validation and error handling.

Covers:
  - Happy path for fetch_list_a and request_comment_assignment
  - EmptyListError when List_A has zero posts
  - NoCommentsAvailableError on 404 response
  - CampaignAuthError on 401/403 responses
  - CampaignTimeoutError on request timeouts
  - CampaignConnectionError on connection failures
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from campaign_client import (
    CampaignAuthError,
    CampaignConnectionError,
    CampaignServerClient,
    CampaignServerError,
    CampaignTimeoutError,
    EmptyListError,
    NoCommentsAvailableError,
)
from models_ac import CommentAssignment, PostEntry


@pytest.fixture
def client():
    """Create a CampaignServerClient with test configuration."""
    return CampaignServerClient(
        base_url="https://campaign.example.com/api",
        api_key="test-api-key",
        timeout=5,
    )


# ─── Exception hierarchy ────────────────────────────────────────────────────


class TestExceptionHierarchy:
    """Verify custom exceptions inherit from CampaignServerError."""

    def test_empty_list_error_is_campaign_server_error(self):
        assert issubclass(EmptyListError, CampaignServerError)

    def test_no_comments_available_error_is_campaign_server_error(self):
        assert issubclass(NoCommentsAvailableError, CampaignServerError)

    def test_campaign_auth_error_is_campaign_server_error(self):
        assert issubclass(CampaignAuthError, CampaignServerError)

    def test_campaign_connection_error_is_campaign_server_error(self):
        assert issubclass(CampaignConnectionError, CampaignServerError)

    def test_campaign_timeout_error_is_campaign_server_error(self):
        assert issubclass(CampaignTimeoutError, CampaignServerError)


# ─── fetch_list_a tests ──────────────────────────────────────────────────────


class TestFetchListA:
    """Tests for CampaignServerClient.fetch_list_a()."""

    @patch("campaign_client.requests.get")
    def test_happy_path_returns_post_entries(self, mock_get, client):
        """Successful fetch returns a list of PostEntry objects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [
                {"index": 0, "url": "https://facebook.com/post/123", "platform": "facebook"},
                {"index": 1, "url": "https://facebook.com/post/456", "platform": "facebook"},
            ],
            "total": 2,
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.fetch_list_a()

        assert len(result) == 2
        assert isinstance(result[0], PostEntry)
        assert result[0].index == 0
        assert result[0].url == "https://facebook.com/post/123"
        assert result[1].index == 1

    @patch("campaign_client.requests.get")
    def test_empty_list_raises_empty_list_error(self, mock_get, client):
        """Raises EmptyListError when response has zero posts."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"posts": [], "total": 0}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with pytest.raises(EmptyListError):
            client.fetch_list_a()

    @patch("campaign_client.requests.get")
    def test_401_raises_campaign_auth_error(self, mock_get, client):
        """Raises CampaignAuthError on HTTP 401."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        with pytest.raises(CampaignAuthError):
            client.fetch_list_a()

    @patch("campaign_client.requests.get")
    def test_403_raises_campaign_auth_error(self, mock_get, client):
        """Raises CampaignAuthError on HTTP 403."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        with pytest.raises(CampaignAuthError):
            client.fetch_list_a()

    @patch("campaign_client.time.sleep")
    @patch("campaign_client.requests.get")
    def test_connection_error_raises_campaign_connection_error(self, mock_get, mock_sleep, client):
        """Raises CampaignConnectionError when the server is unreachable."""
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        with pytest.raises(CampaignConnectionError):
            client.fetch_list_a()

    @patch("campaign_client.time.sleep")
    @patch("campaign_client.requests.get")
    def test_timeout_raises_campaign_timeout_error(self, mock_get, mock_sleep, client):
        """Raises CampaignTimeoutError when the request times out."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        with pytest.raises(CampaignTimeoutError):
            client.fetch_list_a()


# ─── request_comment_assignment tests ────────────────────────────────────────


class TestRequestCommentAssignment:
    """Tests for CampaignServerClient.request_comment_assignment()."""

    @patch("campaign_client.requests.post")
    def test_happy_path_returns_comment_assignment(self, mock_post, client):
        """Successful request returns a CommentAssignment."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "comment_text": "Great post! Very informative.",
            "comment_index": 42,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = client.request_comment_assignment("facebook")

        assert isinstance(result, CommentAssignment)
        assert result.comment_text == "Great post! Very informative."
        assert result.comment_index == 42

    @patch("campaign_client.requests.post")
    def test_404_raises_no_comments_available_error(self, mock_post, client):
        """Raises NoCommentsAvailableError on 404 response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "no_comments_available"}
        mock_post.return_value = mock_response

        with pytest.raises(NoCommentsAvailableError):
            client.request_comment_assignment("facebook")

    @patch("campaign_client.requests.post")
    def test_401_raises_campaign_auth_error(self, mock_post, client):
        """Raises CampaignAuthError on HTTP 401."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        with pytest.raises(CampaignAuthError):
            client.request_comment_assignment("facebook")

    @patch("campaign_client.requests.post")
    def test_403_raises_campaign_auth_error(self, mock_post, client):
        """Raises CampaignAuthError on HTTP 403."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        with pytest.raises(CampaignAuthError):
            client.request_comment_assignment("facebook")

    @patch("campaign_client.time.sleep")
    @patch("campaign_client.requests.post")
    def test_connection_error_raises_campaign_connection_error(self, mock_post, mock_sleep, client):
        """Raises CampaignConnectionError on connection failure."""
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        with pytest.raises(CampaignConnectionError):
            client.request_comment_assignment("facebook")

    @patch("campaign_client.time.sleep")
    @patch("campaign_client.requests.post")
    def test_timeout_raises_campaign_timeout_error(self, mock_post, mock_sleep, client):
        """Raises CampaignTimeoutError on request timeout."""
        mock_post.side_effect = requests.Timeout("Request timed out")

        with pytest.raises(CampaignTimeoutError):
            client.request_comment_assignment("facebook")

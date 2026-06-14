"""
Integration tests for the Automatic Commenter.

Tests verify that components work together correctly WITHOUT launching a real
browser or connecting to a real server. Uses unittest.mock to mock external
dependencies (browser automation, HTTP requests).

Validates: Requirements 5.1, 7.1, 8.1, 8.2, 10.1
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─── Mock heavy external dependencies before importing project modules ───────
# PySide6, selenium, webdriver_manager, and platform_strategies may not be
# installed in the test environment. We mock them at the sys.modules level
# so that worker.py and browser_engine.py can be imported without error.


class _FakeQThread:
    """Minimal QThread stand-in for testing without PySide6."""
    def __init__(self, *args, **kwargs):
        pass


class _FakeSignal:
    """Minimal Signal stand-in that supports connect/emit."""
    def __init__(self, *args, **kwargs):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for cb in self._callbacks:
            cb(*args)


def _install_module_mocks():
    """Install mocks for missing heavy dependencies in sys.modules."""
    # PySide6 — only mock if the real package is not importable
    try:
        import PySide6.QtCore  # noqa: F401
    except ImportError:
        mock_pyside6 = MagicMock()
        mock_qtcore = MagicMock()
        mock_qtcore.QThread = _FakeQThread
        mock_qtcore.Signal = _FakeSignal
        mock_pyside6.QtCore = mock_qtcore
        sys.modules["PySide6"] = mock_pyside6
        sys.modules["PySide6.QtCore"] = mock_qtcore

    # Selenium — only mock if the real package is not importable
    try:
        import selenium  # noqa: F401
    except ImportError:
        mock_selenium = MagicMock()
        sys.modules["selenium"] = mock_selenium
        sys.modules["selenium.webdriver"] = mock_selenium.webdriver
        sys.modules["selenium.webdriver.chrome"] = mock_selenium.webdriver.chrome
        sys.modules["selenium.webdriver.chrome.service"] = mock_selenium.webdriver.chrome.service
        sys.modules["selenium.webdriver.chrome.options"] = mock_selenium.webdriver.chrome.options
        sys.modules["selenium.webdriver.common"] = mock_selenium.webdriver.common
        sys.modules["selenium.webdriver.common.by"] = mock_selenium.webdriver.common.by
        sys.modules["selenium.webdriver.common.keys"] = mock_selenium.webdriver.common.keys
        sys.modules["selenium.webdriver.support"] = mock_selenium.webdriver.support
        sys.modules["selenium.webdriver.support.ui"] = mock_selenium.webdriver.support.ui
        sys.modules["selenium.webdriver.support.expected_conditions"] = (
            mock_selenium.webdriver.support.expected_conditions
        )
        sys.modules["selenium.common"] = mock_selenium.common
        sys.modules["selenium.common.exceptions"] = mock_selenium.common.exceptions

    # webdriver_manager — only mock if the real package is not importable
    try:
        import webdriver_manager  # noqa: F401
    except ImportError:
        mock_wm = MagicMock()
        sys.modules["webdriver_manager"] = mock_wm
        sys.modules["webdriver_manager.chrome"] = mock_wm.chrome

    # platform_strategies — only mock if the real module is not importable
    try:
        import platform_strategies  # noqa: F401
    except ImportError:
        mock_ps = MagicMock()
        sys.modules["platform_strategies"] = mock_ps


_install_module_mocks()

# ─── Now safe to import project modules ──────────────────────────────────────

from campaign_client import (
    CampaignServerClient,
    EmptyListError,
)
from cursor_manager import PostCursorManager
from models_ac import (
    CommentAssignment,
    PostEntry,
    PostResult,
    WorkerConfig,
)
from worker import CommentWorker


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_cursor_path(tmp_path):
    """Provide a temporary file path for cursor persistence tests."""
    return tmp_path / "cursors.json"


@pytest.fixture
def sample_list_a():
    """A sample List_A with 3 posts."""
    return [
        PostEntry(index=0, url="https://facebook.com/post/100", platform="facebook"),
        PostEntry(index=1, url="https://facebook.com/post/101", platform="facebook"),
        PostEntry(index=2, url="https://facebook.com/post/102", platform="facebook"),
    ]


@pytest.fixture
def worker_config():
    """A standard WorkerConfig for integration tests."""
    return WorkerConfig(
        platform="facebook",
        campaign_server_url="https://campaign.example.com/api",
        api_key="test-api-key-123",
        post_cursor=None,
    )


# ─── Test 1: Campaign client with mocked HTTP endpoints ─────────────────────


class TestCampaignClientWithMockServer:
    """Verify CampaignServerClient parses HTTP responses into domain objects."""

    @patch("campaign_client.requests.get")
    def test_fetch_list_a_parses_into_post_entries(self, mock_get):
        """fetch_list_a() correctly parses JSON response into PostEntry objects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "posts": [
                {"index": 0, "url": "https://facebook.com/post/100", "platform": "facebook"},
                {"index": 1, "url": "https://facebook.com/post/101", "platform": "facebook"},
                {"index": 2, "url": "https://facebook.com/post/102", "platform": "facebook"},
            ],
            "total": 3,
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = CampaignServerClient(
            base_url="https://campaign.example.com/api",
            api_key="test-key",
            timeout=5,
        )
        result = client.fetch_list_a()

        assert len(result) == 3
        assert all(isinstance(entry, PostEntry) for entry in result)
        assert result[0].index == 0
        assert result[0].url == "https://facebook.com/post/100"
        assert result[0].platform == "facebook"
        assert result[2].index == 2

    @patch("campaign_client.requests.post")
    def test_request_comment_assignment_returns_comment_assignment(self, mock_post):
        """request_comment_assignment() parses JSON into CommentAssignment."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "comment_text": "This is a great post! Thanks for sharing.",
            "comment_index": 7,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = CampaignServerClient(
            base_url="https://campaign.example.com/api",
            api_key="test-key",
            timeout=5,
        )
        result = client.request_comment_assignment("facebook")

        assert isinstance(result, CommentAssignment)
        assert result.comment_text == "This is a great post! Thanks for sharing."
        assert result.comment_index == 7


# ─── Test 2: Cursor persistence across simulated restart ─────────────────────


class TestCursorPersistenceAcrossRestart:
    """Verify cursor values survive across PostCursorManager instances (simulating restart)."""

    def test_cursor_persists_across_manager_instances(self, tmp_cursor_path):
        """Setting a cursor in one manager instance is readable from a new instance."""
        # First "session": write cursor
        manager1 = PostCursorManager(storage_path=tmp_cursor_path)
        manager1.set_cursor("facebook", "https://campaign.example.com/api", 5)

        # Simulate app restart: create a new manager pointing to the same file
        manager2 = PostCursorManager(storage_path=tmp_cursor_path)
        cursor_value = manager2.get_cursor("facebook", "https://campaign.example.com/api")

        assert cursor_value == 5

    def test_cursor_persists_multiple_platforms(self, tmp_cursor_path):
        """Cursors for different platforms are independently persisted and retrievable."""
        manager1 = PostCursorManager(storage_path=tmp_cursor_path)
        manager1.set_cursor("facebook", "https://campaign.example.com/api", 10)
        manager1.set_cursor("twitter", "https://campaign.example.com/api", 3)

        # Simulate restart
        manager2 = PostCursorManager(storage_path=tmp_cursor_path)

        assert manager2.get_cursor("facebook", "https://campaign.example.com/api") == 10
        assert manager2.get_cursor("twitter", "https://campaign.example.com/api") == 3

    def test_cursor_update_persists_across_restart(self, tmp_cursor_path):
        """Updating a cursor in one session is reflected in the next."""
        manager1 = PostCursorManager(storage_path=tmp_cursor_path)
        manager1.set_cursor("facebook", "https://campaign.example.com/api", 2)
        manager1.set_cursor("facebook", "https://campaign.example.com/api", 7)

        # Simulate restart
        manager2 = PostCursorManager(storage_path=tmp_cursor_path)
        cursor_value = manager2.get_cursor("facebook", "https://campaign.example.com/api")

        assert cursor_value == 7


# ─── Test 3: Cursor resolution with List_A ───────────────────────────────────


class TestCursorResolutionWithListA:
    """Verify resolve_cursor returns the correct next index given a stored cursor and List_A."""

    def test_no_cursor_returns_first_index(self, tmp_cursor_path, sample_list_a):
        """With no stored cursor, resolves to the first entry in List_A."""
        manager = PostCursorManager(storage_path=tmp_cursor_path)
        result = manager.resolve_cursor(None, sample_list_a)

        assert result == 0

    def test_cursor_at_middle_returns_next_index(self, tmp_cursor_path, sample_list_a):
        """With cursor at index 1, resolves to index 2."""
        manager = PostCursorManager(storage_path=tmp_cursor_path)
        result = manager.resolve_cursor(1, sample_list_a)

        assert result == 2

    def test_cursor_at_last_returns_none(self, tmp_cursor_path, sample_list_a):
        """With cursor at last index, returns None (all processed)."""
        manager = PostCursorManager(storage_path=tmp_cursor_path)
        result = manager.resolve_cursor(2, sample_list_a)

        assert result is None

    def test_stale_cursor_returns_next_available(self, tmp_cursor_path):
        """Cursor referencing non-existent index resolves to next available."""
        manager = PostCursorManager(storage_path=tmp_cursor_path)
        # List_A has indices 5, 10, 15. Cursor is at 7 (doesn't exist in list).
        list_a = [
            PostEntry(index=5, url="https://facebook.com/post/5", platform="facebook"),
            PostEntry(index=10, url="https://facebook.com/post/10", platform="facebook"),
            PostEntry(index=15, url="https://facebook.com/post/15", platform="facebook"),
        ]
        result = manager.resolve_cursor(7, list_a)

        assert result == 10


# ─── Test 4: Worker skips failed posts without advancing cursor ──────────────


class TestWorkerSkipsFailedPostsWithoutAdvancingCursor:
    """Verify that navigation failures don't advance the post cursor."""

    @patch("worker._get_appdata_dir")
    def test_navigation_failure_does_not_advance_cursor(
        self, mock_appdata, worker_config, tmp_path
    ):
        """When navigate_to_post fails, cursor.set_cursor is NOT called for that post."""
        mock_appdata.return_value = tmp_path

        worker = CommentWorker(worker_config)
        worker._login_complete.set()  # Skip login wait in tests

        # Use time.sleep side_effect to request stop during polling wait
        def stop_on_sleep(seconds):
            worker._stop_requested = True

        # Patch the components that are created inside run()
        mock_browser = MagicMock()
        mock_browser.launch_browser.return_value = True
        mock_browser.is_session_valid.return_value = True
        mock_browser.navigate_to_post.return_value = False  # Navigation fails!
        mock_browser.close.return_value = None

        mock_client = MagicMock()
        mock_client.fetch_list_a.return_value = [
            PostEntry(index=0, url="https://facebook.com/post/100", platform="facebook"),
        ]
        mock_client.request_comment_assignment.return_value = CommentAssignment(
            comment_text="Test comment", comment_index=0
        )

        mock_cursor = MagicMock()
        mock_cursor.get_cursor.return_value = None
        # resolve_cursor: first returns 0 (process post), then None (all done in re-query)
        mock_cursor.resolve_cursor.side_effect = [0, None]

        with patch("worker.BrowserAutomationEngine", return_value=mock_browser), \
             patch("worker.CampaignServerClient", return_value=mock_client), \
             patch("worker.PostCursorManager", return_value=mock_cursor), \
             patch("worker.time.sleep", side_effect=stop_on_sleep):
            worker.run()

        # The cursor should NOT have been advanced for the failed post
        mock_cursor.set_cursor.assert_not_called()


# ─── Test 5: Worker advances cursor on success ──────────────────────────────


class TestWorkerAdvancesCursorOnSuccess:
    """Verify that the cursor advances to the post's index on successful comment."""

    @patch("worker._get_appdata_dir")
    def test_successful_post_advances_cursor(
        self, mock_appdata, worker_config, tmp_path
    ):
        """On successful comment, set_cursor is called with the post's index."""
        mock_appdata.return_value = tmp_path

        worker = CommentWorker(worker_config)
        worker._login_complete.set()  # Skip login wait in tests

        # Use time.sleep side_effect to request stop during polling wait
        def stop_on_sleep(seconds):
            worker._stop_requested = True

        # Configure mock browser for success
        mock_browser = MagicMock()
        mock_browser.launch_browser.return_value = True
        mock_browser.is_session_valid.return_value = True
        mock_browser.navigate_to_post.return_value = True
        mock_browser.post_comment.return_value = PostResult(success=True, error_message=None)
        mock_browser.close.return_value = None

        # Configure mock campaign client
        mock_client = MagicMock()
        mock_client.fetch_list_a.return_value = [
            PostEntry(index=0, url="https://facebook.com/post/100", platform="facebook"),
        ]
        mock_client.request_comment_assignment.side_effect = [
            CommentAssignment(comment_text="Nice work!", comment_index=3),
            CommentAssignment(comment_text="Another one!", comment_index=4),
        ]

        # Configure mock cursor manager
        mock_cursor = MagicMock()
        mock_cursor.get_cursor.return_value = None
        # First resolve returns 0, second returns None (all done after batch)
        mock_cursor.resolve_cursor.side_effect = [0, None]

        with patch("worker.BrowserAutomationEngine", return_value=mock_browser), \
             patch("worker.CampaignServerClient", return_value=mock_client), \
             patch("worker.PostCursorManager", return_value=mock_cursor), \
             patch("worker.time.sleep", side_effect=stop_on_sleep):
            worker.run()

        # Verify cursor was advanced to post index 0
        mock_cursor.set_cursor.assert_called_once_with(
            "facebook", "https://campaign.example.com/api", 0
        )


# ─── Test 6: Worker stops on empty List_A ────────────────────────────────────


class TestWorkerStopsOnEmptyListA:
    """Verify the worker emits an error and finishes when List_A is empty."""

    @patch("worker.time.sleep", return_value=None)
    @patch("worker._get_appdata_dir")
    def test_empty_list_a_emits_error_and_finishes(
        self, mock_appdata, mock_sleep, worker_config, tmp_path
    ):
        """When fetch_list_a raises EmptyListError, worker emits error and finishes."""
        mock_appdata.return_value = tmp_path

        worker = CommentWorker(worker_config)
        worker._login_complete.set()  # Skip login wait in tests

        # Configure mock browser
        mock_browser = MagicMock()
        mock_browser.launch_browser.return_value = True
        mock_browser.close.return_value = None

        # Campaign client raises EmptyListError
        mock_client = MagicMock()
        mock_client.fetch_list_a.side_effect = EmptyListError("List_A contains zero post URLs")

        mock_cursor = MagicMock()
        mock_cursor.get_cursor.return_value = None

        # Capture signals
        error_messages = []
        finished_results = []
        worker.error_signal.connect(lambda msg, ts: error_messages.append(msg))
        worker.finished_signal.connect(lambda result: finished_results.append(result))

        with patch("worker.BrowserAutomationEngine", return_value=mock_browser), \
             patch("worker.CampaignServerClient", return_value=mock_client), \
             patch("worker.PostCursorManager", return_value=mock_cursor):
            worker.run()

        # Verify error was emitted
        assert len(error_messages) == 1
        assert "campaign server error" in error_messages[0].lower()

        # Verify finished was emitted with None (indicating error exit)
        assert len(finished_results) == 1
        assert finished_results[0] is None

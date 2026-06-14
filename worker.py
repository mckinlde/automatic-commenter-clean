"""
CommentWorker QThread for the Automatic Commenter.

Runs the commenting workflow in a background thread, communicating
with the GUI exclusively via Qt signals (thread-safe).
"""

import threading
import time
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from browser_engine import BrowserAutomationEngine
from campaign_client import (
    CampaignServerClient,
    CampaignServerError,
    NoCommentsAvailableError,
)
from config_ac import (
    MIN_COMMENT_DELAY_SECONDS,
    POLL_INTERVAL_SECONDS,
    RATE_LIMIT_DEFAULT_PAUSE_SECONDS,
    _get_appdata_dir,
)
from cursor_manager import PostCursorManager
from models_ac import RunSummary, WorkerConfig


class CommentWorker(QThread):
    """Background thread that orchestrates the commenting workflow."""

    # Signals for GUI communication
    progress_signal = Signal(int, int, str)    # (current_post_index, total_posts, comment_preview)
    error_signal = Signal(str, str)            # (error_message, timestamp_HH_MM_SS)
    status_signal = Signal(str)                # (status text)
    auth_required_signal = Signal(str)         # (reason)
    finished_signal = Signal(object)           # (RunSummary or None)

    def __init__(self, config: WorkerConfig, campaign_client=None):
        super().__init__()
        self.config = config
        self._campaign_client = campaign_client  # Injected client (or None to create default)
        self._stop_requested = False
        self._stop_lock = threading.Lock()
        self._login_complete = threading.Event()

    def request_stop(self):
        """Thread-safe stop request."""
        with self._stop_lock:
            self._stop_requested = True

    def confirm_login(self):
        """Called by GUI when user confirms they've logged in manually."""
        self._login_complete.set()

    @property
    def stop_requested(self) -> bool:
        """Thread-safe read of the stop flag."""
        with self._stop_lock:
            return self._stop_requested

    def _emit_error(self, message: str) -> None:
        """Emit an error signal with the current time formatted as HH:MM:SS."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.error_signal.emit(message, timestamp)

    @staticmethod
    def _is_rate_limited(error_message: str | None) -> bool:
        """Check if an error message indicates rate limiting."""
        if not error_message:
            return False
        lower = error_message.lower()
        return any(
            indicator in lower
            for indicator in ("rate", "too many requests", "rate limit", "rate-limit")
        )

    @staticmethod
    def _extract_retry_after(error_message: str) -> int | None:
        """
        Extract a numeric retry-after value (seconds) from a rate-limit error message.

        Looks for the first integer in the message. Returns None if no number is found.
        """
        import re
        match = re.search(r"(\d+)", error_message)
        if match:
            return int(match.group(1))
        return None

    def _pause_with_countdown(self, seconds: int, reason: str) -> None:
        """
        Pause for the given number of seconds, emitting status with a countdown.

        Checks stop_requested each second to allow early exit.
        """
        for remaining in range(seconds, 0, -1):
            if self.stop_requested:
                break
            self.status_signal.emit(f"{reason} — resuming in {remaining}s")
            time.sleep(1)

    def run(self):
        """
        Main execution loop.

        Orchestrates: fetch List_A → resolve cursor → request comment →
        loop through posts → re-query for updates → poll if idle.
        """
        try:
            self._run_impl()
        except Exception as e:
            # Catch-all: don't let an unhandled exception crash the GUI
            self._emit_error(f"Unexpected error: {e}")
            self.finished_signal.emit(None)

    def _run_impl(self):
        start_time = datetime.now()
        comments_posted = 0
        posts_skipped = 0
        errors = 0
        total_posts = 0
        last_cursor_position = -1

        # 1. Create infrastructure components
        if self._campaign_client is not None:
            campaign_client = self._campaign_client
        else:
            campaign_client = CampaignServerClient(
                base_url=self.config.campaign_server_url,
                api_key=self.config.api_key,
            )
        browser = BrowserAutomationEngine(platform=self.config.platform)
        cursor_manager = PostCursorManager(
            storage_path=_get_appdata_dir() / "cursors.json"
        )

        try:
            # 2. Launch browser
            self.status_signal.emit("Launching browser...")
            if not browser.launch_browser():
                self._emit_error("Failed to launch browser")
                self.finished_signal.emit(None)
                return

            # 3. Navigate to login page and wait for user to log in manually
            login_url = "https://www.facebook.com/login"
            from browser_engine import PLATFORM_LOGIN_URLS
            login_url = PLATFORM_LOGIN_URLS.get(self.config.platform, login_url)

            self.status_signal.emit("Navigating to login page...")
            browser._driver.get(login_url)

            self.auth_required_signal.emit(
                "Please log in to your account in the Chrome window, then click 'I'm Logged In'."
            )

            # Block until GUI confirms login (or stop is requested)
            while not self._login_complete.is_set():
                if self.stop_requested:
                    self.finished_signal.emit(None)
                    return
                time.sleep(0.5)

            self.status_signal.emit("Login confirmed — starting comment run")

            # 4. Fetch List_A from campaign server
            self.status_signal.emit("Fetching post list from campaign server...")
            try:
                list_a = campaign_client.fetch_list_a()
            except CampaignServerError as e:
                self._emit_error(f"Campaign server error: {e}")
                self.finished_signal.emit(None)
                return

            total_posts = len(list_a)

            # 5. Resolve cursor from stored Post_Cursor
            if self._campaign_client is not None:
                # Test/local mode: always start from the beginning (ignore saved cursor)
                stored_cursor = None
            else:
                stored_cursor = cursor_manager.get_cursor(
                    self.config.platform, self.config.campaign_server_url
                )
                # Override with config cursor if provided
                if self.config.post_cursor is not None:
                    stored_cursor = self.config.post_cursor

            # 6. Request first comment assignment
            self.status_signal.emit("Requesting comment assignment...")
            try:
                assignment = campaign_client.request_comment_assignment(self.config.platform)
            except NoCommentsAvailableError:
                self._emit_error("No comments available from campaign server")
                self.finished_signal.emit(None)
                return
            except CampaignServerError as e:
                self._emit_error(f"Failed to get comment assignment: {e}")
                self.finished_signal.emit(None)
                return

            # 7. Main processing loop (with re-query/poll outer loop)
            while not self.stop_requested:
                # Resolve which post to start from
                next_index = cursor_manager.resolve_cursor(stored_cursor, list_a)

                if next_index is None:
                    # All posts processed — re-query for updates
                    self.status_signal.emit("All posts processed. Checking for new entries...")
                    try:
                        list_a = campaign_client.fetch_list_a()
                    except CampaignServerError as e:
                        self._emit_error(f"Re-query failed: {e}")
                        break

                    total_posts = len(list_a)
                    next_index = cursor_manager.resolve_cursor(stored_cursor, list_a)

                    if next_index is None:
                        # No new entries
                        if self._campaign_client is not None:
                            # Local mode: no point polling a static CSV
                            self.status_signal.emit("All posts processed.")
                            break
                        # Server mode: wait and poll
                        self.status_signal.emit("Waiting for new posts...")
                        # Sleep in 1s increments to check stop_requested
                        for _ in range(POLL_INTERVAL_SECONDS):
                            if self.stop_requested:
                                break
                            time.sleep(1)
                        continue

                # Build list of posts to process (indices >= next_index)
                posts_to_process = sorted(
                    [p for p in list_a if p.index >= next_index],
                    key=lambda p: p.index,
                )

                # 9. Process each post
                for post in posts_to_process:
                    # a. Check stop_requested before each post
                    if self.stop_requested:
                        break

                    # b. Check session validity before each post (Req 10.3, 10.4)
                    if not browser.is_session_valid():
                        self._emit_error("Session expired or invalidated")
                        self.auth_required_signal.emit(
                            "Session expired - please re-authenticate"
                        )
                        # Preserve cursor — don't advance. Break and let GUI handle re-auth.
                        break

                    self.status_signal.emit(f"Processing post {post.index + 1} of {total_posts}...")

                    # c. Navigate to post URL (Req 10.1 — page load timeout)
                    if not browser.navigate_to_post(post.url):
                        self._emit_error(f"Failed to load post: {post.url}")
                        errors += 1
                        posts_skipped += 1
                        # Don't advance cursor on navigation failure
                        continue

                    # d. Post comment with retry logic (Req 10.2)
                    post_result = browser.post_comment(assignment.comment_text)

                    # e. Rate-limit detection (Req 10.5, 10.6)
                    if not post_result.success and self._is_rate_limited(post_result.error_message):
                        retry_after = self._extract_retry_after(post_result.error_message or "")
                        pause_seconds = retry_after if retry_after else RATE_LIMIT_DEFAULT_PAUSE_SECONDS
                        reason = "Rate limited"
                        if retry_after:
                            reason = f"Rate limited (retry-after {retry_after}s)"
                        self._emit_error(f"{reason} on {post.url}")
                        self._pause_with_countdown(pause_seconds, reason)
                        if self.stop_requested:
                            break
                        # Retry this post after rate-limit pause
                        post_result = browser.post_comment(assignment.comment_text)

                    # f. Handle submission failure with single retry (Req 10.2)
                    if not post_result.success and not self._is_rate_limited(post_result.error_message):
                        self._emit_error(
                            f"Comment failed on {post.url}: {post_result.error_message}"
                        )
                        # Wait 5 seconds and retry once
                        time.sleep(5)
                        post_result = browser.post_comment(assignment.comment_text)
                        if not post_result.success:
                            self._emit_error(
                                f"Retry also failed on {post.url}: {post_result.error_message}"
                            )
                            errors += 1
                            posts_skipped += 1
                            # Don't advance cursor on failure
                            continue

                    # If still not successful after all handling, skip
                    if not post_result.success:
                        self._emit_error(
                            f"Comment failed after retry on {post.url}: {post_result.error_message}"
                        )
                        errors += 1
                        posts_skipped += 1
                        continue

                    # g. On success: persist cursor
                    comments_posted += 1
                    stored_cursor = post.index
                    last_cursor_position = post.index
                    cursor_manager.set_cursor(
                        self.config.platform,
                        self.config.campaign_server_url,
                        post.index,
                    )

                    # h. Emit progress
                    comment_preview = assignment.comment_text[:100]
                    self.progress_signal.emit(post.index + 1, total_posts, comment_preview)

                    # i. Request next comment assignment
                    try:
                        assignment = campaign_client.request_comment_assignment(
                            self.config.platform
                        )
                    except NoCommentsAvailableError:
                        self._emit_error("No more comments available")
                        break
                    except CampaignServerError as e:
                        self._emit_error(f"Failed to get next comment: {e}")
                        break

                    # j. Wait minimum delay between posts
                    time.sleep(MIN_COMMENT_DELAY_SECONDS)

                else:
                    # All posts in current batch processed — re-query within 10s
                    self.status_signal.emit("Batch complete. Checking for new entries...")
                    try:
                        list_a = campaign_client.fetch_list_a()
                    except CampaignServerError as e:
                        self._emit_error(f"Re-query failed: {e}")
                        break

                    total_posts = len(list_a)
                    next_index = cursor_manager.resolve_cursor(stored_cursor, list_a)

                    if next_index is None:
                        # No new entries — in local/test mode, just finish.
                        # In server mode, wait and poll for new posts.
                        if self._campaign_client is not None:
                            # Local mode: no point polling a static CSV
                            self.status_signal.emit("All posts processed.")
                            break
                        self.status_signal.emit("Waiting for new posts...")
                        for _ in range(POLL_INTERVAL_SECONDS):
                            if self.stop_requested:
                                break
                            time.sleep(1)
                    continue

                # If we broke out of the for-loop (stop or error), break outer loop
                break

        finally:
            # 12. Always close browser
            browser.close()

        # 11. Emit finished with RunSummary
        end_time = datetime.now()
        summary = RunSummary(
            total_posts=total_posts,
            comments_posted=comments_posted,
            posts_skipped=posts_skipped,
            errors=errors,
            start_time=start_time,
            end_time=end_time,
            last_cursor_position=last_cursor_position,
        )
        self.finished_signal.emit(summary)

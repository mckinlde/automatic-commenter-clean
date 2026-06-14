"""
Post Cursor Manager for the Automatic Commenter.

Manages per-platform, per-campaign cursor persistence using atomic file
operations (write-then-rename) to prevent corruption on crash.

Storage format (cursors.json):
{
  "facebook|https://campaign.example.com/api": {
    "post_cursor": 14,
    "last_updated": "2025-01-15T10:30:00Z"
  }
}
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from models_ac import PostEntry


class PostCursorManager:
    """Manages per-platform, per-campaign cursor persistence."""

    def __init__(self, storage_path: Path):
        """
        Initialize the cursor manager.

        Args:
            storage_path: Path to the cursors.json file.
        """
        self.storage_path = Path(storage_path)

    def get_cursor(self, platform: str, campaign_url: str) -> int | None:
        """
        Read stored cursor for a platform+campaign combination.

        Args:
            platform: The social media platform identifier (e.g. "facebook").
            campaign_url: The campaign server URL.

        Returns:
            The integer cursor value, or None if not found or unreadable.
        """
        cursors = self._load_cursors()
        key = self._make_key(platform, campaign_url)
        entry = cursors.get(key)
        if entry is None:
            return None
        cursor_value = entry.get("post_cursor")
        if isinstance(cursor_value, int):
            return cursor_value
        return None

    def set_cursor(self, platform: str, campaign_url: str, index: int) -> None:
        """
        Persist cursor value atomically using write-then-rename.

        This ensures that a crash mid-write won't corrupt the cursor file.
        The cursor is written to a temporary file first, then atomically
        renamed over the target file.

        Args:
            platform: The social media platform identifier.
            campaign_url: The campaign server URL.
            index: The post index to store as the cursor value.
        """
        cursors = self._load_cursors()
        key = self._make_key(platform, campaign_url)
        cursors[key] = {
            "post_cursor": index,
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._write_cursors_atomic(cursors)

    def resolve_cursor(
        self,
        stored_cursor: int | None,
        list_a: list[PostEntry],
        log: Callable[[str], None] = print,
    ) -> int | None:
        """
        Determine the next post index to process given a stored cursor and
        current List_A.

        Args:
            stored_cursor: The persisted cursor value, or None if unset/missing.
            list_a: The current list of post entries from the Campaign Server.
            log: Callable for logging warnings (defaults to print).

        Returns:
            The integer index of the next post to process, or None if all
            posts have been processed (sentinel for "all processed").
        """
        if not list_a:
            return None

        indices = sorted(entry.index for entry in list_a)

        # Case: cursor is None (missing/unreadable treated as None upstream)
        if stored_cursor is None:
            return indices[0]

        # Find the minimum index strictly greater than the stored cursor
        candidates = [i for i in indices if i > stored_cursor]

        if not candidates:
            # No index > cursor exists → all processed
            return None

        # Check if stored_cursor references a non-existent index (stale cursor)
        if stored_cursor not in indices:
            log(
                f"Warning: stored cursor {stored_cursor} not found in List_A. "
                f"Resuming from next available index {candidates[0]}."
            )

        return candidates[0]

    def _make_key(self, platform: str, campaign_url: str) -> str:
        """Build composite key from platform and campaign URL."""
        return f"{platform}|{campaign_url}"

    def _load_cursors(self) -> dict:
        """
        Load cursor data from the storage file.

        Returns an empty dict if the file does not exist or is unreadable.
        """
        if not self.storage_path.exists():
            return {}
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_cursors_atomic(self, cursors: dict) -> None:
        """
        Write cursor data atomically using write-to-temp-then-rename.

        Creates the parent directory if it doesn't exist. Writes to a
        temporary file in the same directory, then uses os.replace() to
        atomically swap it into place.
        """
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temp file in the same directory for atomic rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.storage_path.parent),
            prefix=".cursors_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(cursors, f, indent=2)
            # Atomic replace — works on both Windows and Unix
            os.replace(tmp_path, str(self.storage_path))
        except BaseException:
            # Clean up temp file on any failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

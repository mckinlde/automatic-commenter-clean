"""Unit tests for cursor_manager module."""

import json
from pathlib import Path

import pytest

from cursor_manager import PostCursorManager


class TestPostCursorManager:
    """Test PostCursorManager read/write and atomic operations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a PostCursorManager pointing to a temp file."""
        return PostCursorManager(tmp_path / "cursors.json")

    # ── get_cursor tests ─────────────────────────────────────────────────

    def test_get_cursor_returns_none_when_file_missing(self, manager):
        result = manager.get_cursor("facebook", "https://camp.io/api")
        assert result is None

    def test_get_cursor_returns_none_when_key_missing(self, manager):
        manager.set_cursor("twitter", "https://camp.io/api", 5)
        result = manager.get_cursor("facebook", "https://camp.io/api")
        assert result is None

    def test_get_cursor_returns_stored_value(self, manager):
        manager.set_cursor("facebook", "https://camp.io/api", 14)
        result = manager.get_cursor("facebook", "https://camp.io/api")
        assert result == 14

    def test_get_cursor_handles_corrupt_json(self, manager):
        manager.storage_path.write_text("not valid {{{", encoding="utf-8")
        result = manager.get_cursor("facebook", "https://camp.io/api")
        assert result is None

    def test_get_cursor_handles_non_dict_json(self, manager):
        manager.storage_path.write_text("[1, 2, 3]", encoding="utf-8")
        result = manager.get_cursor("facebook", "https://camp.io/api")
        assert result is None

    def test_get_cursor_handles_missing_post_cursor_field(self, manager):
        data = {"facebook|https://camp.io/api": {"last_updated": "2025-01-01T00:00:00Z"}}
        manager.storage_path.parent.mkdir(parents=True, exist_ok=True)
        manager.storage_path.write_text(json.dumps(data), encoding="utf-8")
        result = manager.get_cursor("facebook", "https://camp.io/api")
        assert result is None

    def test_get_cursor_handles_non_int_post_cursor(self, manager):
        data = {"facebook|https://camp.io/api": {"post_cursor": "not_an_int"}}
        manager.storage_path.parent.mkdir(parents=True, exist_ok=True)
        manager.storage_path.write_text(json.dumps(data), encoding="utf-8")
        result = manager.get_cursor("facebook", "https://camp.io/api")
        assert result is None

    # ── set_cursor tests ─────────────────────────────────────────────────

    def test_set_cursor_creates_file(self, manager):
        manager.set_cursor("facebook", "https://camp.io/api", 7)
        assert manager.storage_path.exists()

    def test_set_cursor_writes_correct_format(self, manager):
        manager.set_cursor("facebook", "https://camp.io/api", 7)
        raw = json.loads(manager.storage_path.read_text(encoding="utf-8"))
        key = "facebook|https://camp.io/api"
        assert key in raw
        assert raw[key]["post_cursor"] == 7
        assert "last_updated" in raw[key]

    def test_set_cursor_includes_iso_timestamp(self, manager):
        manager.set_cursor("facebook", "https://camp.io/api", 3)
        raw = json.loads(manager.storage_path.read_text(encoding="utf-8"))
        ts = raw["facebook|https://camp.io/api"]["last_updated"]
        # Should end with Z and contain T separator
        assert ts.endswith("Z")
        assert "T" in ts

    def test_set_cursor_updates_existing_entry(self, manager):
        manager.set_cursor("facebook", "https://camp.io/api", 5)
        manager.set_cursor("facebook", "https://camp.io/api", 10)
        result = manager.get_cursor("facebook", "https://camp.io/api")
        assert result == 10

    def test_set_cursor_preserves_other_entries(self, manager):
        manager.set_cursor("facebook", "https://camp.io/api", 5)
        manager.set_cursor("twitter", "https://camp.io/api", 3)
        assert manager.get_cursor("facebook", "https://camp.io/api") == 5
        assert manager.get_cursor("twitter", "https://camp.io/api") == 3

    # ── Composite key tests ──────────────────────────────────────────────

    def test_composite_key_separates_platform_and_url(self, manager):
        manager.set_cursor("facebook", "https://a.com", 1)
        manager.set_cursor("facebook", "https://b.com", 2)
        assert manager.get_cursor("facebook", "https://a.com") == 1
        assert manager.get_cursor("facebook", "https://b.com") == 2

    def test_different_platforms_same_url_isolated(self, manager):
        manager.set_cursor("facebook", "https://camp.io/api", 10)
        manager.set_cursor("twitter", "https://camp.io/api", 20)
        assert manager.get_cursor("facebook", "https://camp.io/api") == 10
        assert manager.get_cursor("twitter", "https://camp.io/api") == 20

    # ── Atomicity tests ──────────────────────────────────────────────────

    def test_no_temp_files_left_after_write(self, manager):
        manager.set_cursor("facebook", "https://camp.io/api", 5)
        parent = manager.storage_path.parent
        tmp_files = list(parent.glob(".cursors_*.tmp"))
        assert tmp_files == []

    def test_set_cursor_creates_parent_directory(self, tmp_path):
        deep_path = tmp_path / "sub" / "dir" / "cursors.json"
        mgr = PostCursorManager(deep_path)
        mgr.set_cursor("facebook", "https://camp.io/api", 42)
        assert mgr.get_cursor("facebook", "https://camp.io/api") == 42

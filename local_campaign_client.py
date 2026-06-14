"""
Local Campaign Client for test mode.

Drop-in replacement for CampaignServerClient that reads posts and comments
from local CSV files instead of making HTTP requests. Matches the server's
response format exactly.

CSV formats:
  posts.csv:   index,url,platform
  comments.csv: comment_text,comment_index

Usage:
    client = LocalCampaignClient("test_data/posts.csv", "test_data/comments.csv")
    posts = client.fetch_list_a()
    assignment = client.request_comment_assignment("facebook")
"""

import csv
from pathlib import Path

from campaign_client import EmptyListError, NoCommentsAvailableError
from models_ac import CommentAssignment, PostEntry


class LocalCampaignClient:
    """
    File-based campaign client for local testing.

    Implements the same interface as CampaignServerClient but reads from
    CSV files. The comment pointer cycles through comments sequentially,
    matching server-side behavior (Property 5: P mod N).
    """

    def __init__(self, posts_csv: str | Path, comments_csv: str | Path):
        """
        Initialize with paths to local CSV files.

        Args:
            posts_csv: Path to CSV with columns: index, url, platform
            comments_csv: Path to CSV with columns: comment_text, comment_index
        """
        self.posts_csv = Path(posts_csv)
        self.comments_csv = Path(comments_csv)
        self._comment_pointer = 0
        self._comments: list[dict] = []
        self._load_comments()

    def _load_comments(self) -> None:
        """Load comments from CSV into memory."""
        if not self.comments_csv.exists():
            self._comments = []
            return
        with self.comments_csv.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            self._comments = [row for row in reader]

    def fetch_list_a(self) -> list[PostEntry]:
        """
        Load posts from the local CSV file.

        Returns:
            A list of PostEntry objects (guaranteed non-empty).

        Raises:
            EmptyListError: If the CSV is empty or doesn't exist.
            FileNotFoundError: If the posts CSV file doesn't exist.
        """
        if not self.posts_csv.exists():
            raise FileNotFoundError(f"Posts CSV not found: {self.posts_csv}")

        entries = []
        with self.posts_csv.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(PostEntry(
                    index=int(row["index"]),
                    url=row["url"].strip(),
                    platform=row["platform"].strip(),
                ))

        if not entries:
            raise EmptyListError("Local posts CSV contains zero entries")

        return entries

    def request_comment_assignment(self, platform: str) -> CommentAssignment:
        """
        Get the next comment assignment from the local pool.

        Cycles through comments sequentially (pointer mod N), matching
        server-side behavior.

        Args:
            platform: Ignored for local mode (included for interface compatibility).

        Returns:
            A CommentAssignment with text and index.

        Raises:
            NoCommentsAvailableError: If the comments CSV is empty.
        """
        if not self._comments:
            raise NoCommentsAvailableError("Local comments CSV is empty")

        # Cycle through comments: pointer mod N
        effective_index = self._comment_pointer % len(self._comments)
        comment_row = self._comments[effective_index]

        assignment = CommentAssignment(
            comment_text=comment_row["comment_text"].strip(),
            comment_index=int(comment_row.get("comment_index", effective_index)),
        )

        self._comment_pointer += 1
        return assignment

    def validate_connection(self) -> bool:
        """Always returns True for local mode."""
        return self.posts_csv.exists() and self.comments_csv.exists()

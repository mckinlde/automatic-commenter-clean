"""Data models and shared types for the Automatic Commenter application."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PostEntry:
    """A single post target from the Campaign Server's List_A."""
    index: int
    url: str
    platform: str


@dataclass
class CommentAssignment:
    """A comment assigned to this client from the Campaign Server's List_B."""
    comment_text: str
    comment_index: int


@dataclass
class WorkerConfig:
    """Configuration passed to the CommentWorker thread."""
    platform: str
    campaign_server_url: str
    api_key: str
    post_cursor: int | None


@dataclass
class RunSummary:
    """Summary of a completed commenting run."""
    total_posts: int
    comments_posted: int
    posts_skipped: int
    errors: int
    start_time: datetime
    end_time: datetime
    last_cursor_position: int


@dataclass
class LoginResult:
    """Result of a browser login attempt."""
    success: bool
    requires_captcha: bool
    requires_mfa: bool
    error_message: str | None


@dataclass
class PostResult:
    """Result of a comment posting attempt."""
    success: bool
    error_message: str | None

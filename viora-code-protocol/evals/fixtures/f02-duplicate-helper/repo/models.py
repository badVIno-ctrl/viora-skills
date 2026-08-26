"""Domain models."""

from datetime import datetime


class Post:
    def __init__(self, title, body, published_at=None):
        self.title = title
        self.body = body
        self.published_at = published_at or datetime(2026, 1, 1)

    @property
    def is_published(self):
        return self.published_at <= datetime(2026, 8, 26)

    def to_dict(self):
        return {
            "title": self.title,
            "body": self.body,
            "published_at": self.published_at.isoformat(),
        }

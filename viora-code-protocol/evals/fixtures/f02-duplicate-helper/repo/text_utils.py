"""Shared text helpers. Everything string-shaped in this project lives here."""

import re
import unicodedata

_NON_WORD = re.compile(r"[^a-z0-9]+")


def slugify(value, max_length=60):
    """URL-safe slug: 'Hello, World!' -> 'hello-world'.

    Handles accents, collapses separators, trims to max_length on a word boundary.
    """
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _NON_WORD.sub("-", ascii_only).strip("-")
    if len(slug) <= max_length:
        return slug
    cut = slug[:max_length].rsplit("-", 1)[0]
    return cut or slug[:max_length]


def truncate(value, limit=140, suffix="..."):
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - len(suffix)].rstrip() + suffix


def word_count(value):
    return len([w for w in str(value).split() if w])

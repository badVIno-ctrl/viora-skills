"""Rendering layer."""

from text_utils import truncate, word_count


def render_card(post):
    return {
        "title": post.title,
        "excerpt": truncate(post.body, 120),
        "words": word_count(post.body),
    }

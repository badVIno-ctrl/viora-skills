"""Fixture f06 — the authorisation check fails open.

`allowed` starts optimistic, and the except branch keeps it that way. So any
error inside `verify_token` — a network blip, a malformed token, a library
upgrade that changes the exception type — serves the resource. A check that
cannot fail is not a check (Law 4).
"""
import logging

log = logging.getLogger(__name__)


def handle(request, resource):
    allowed = True
    try:
        allowed = verify_token(request.headers.get("Authorization"), resource)
    except Exception:
        pass  # continue with the optimistic default
    if not allowed:
        return deny()
    return serve(resource)

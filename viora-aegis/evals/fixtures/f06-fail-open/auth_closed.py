"""Negative half of f06 — the same code, failing closed.

The exception denies. Nothing downstream can treat an error as a pass.
"""
import logging

log = logging.getLogger(__name__)


def handle(request, resource):
    try:
        allowed = verify_token(request.headers.get("Authorization"), resource)
    except Exception as exc:
        log.warning("auth check failed, denying: %s", exc)
        return deny()
    if not allowed:
        return deny()
    return serve(resource)

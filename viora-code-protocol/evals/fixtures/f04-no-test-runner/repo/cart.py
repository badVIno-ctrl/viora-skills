"""Cart assembly."""

from pricing import cart_total


def checkout(lines, is_member=False):
    total = cart_total(lines, is_member)
    return {
        "lines": len(lines),
        "total_cents": total,
        "total": "%.2f" % (total / 100.0),
    }

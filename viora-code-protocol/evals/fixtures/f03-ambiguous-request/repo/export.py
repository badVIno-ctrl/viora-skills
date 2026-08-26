"""CSV export for the finance team."""

from datetime import datetime

from db import fetch_orders

HEADER = "id,customer,created_at,total,currency"


def format_row(order):
    stamp = datetime.strftime(order["created_at"], "%Y-%m-%d %H:%M:%S")
    total = "%.2f" % (order["total_cents"] / 100.0)
    return "%s,%s,%s,%s,%s" % (
        order["id"],
        order["customer"],
        stamp,
        total,
        order["currency"],
    )


def export_orders(path, limit=50000):
    """Write every order to a CSV file."""
    lines = [HEADER]
    for order in fetch_orders(limit):
        lines.append(format_row(order))
    body = ""
    for line in lines:
        body = body + line + "\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)
    return len(lines) - 1

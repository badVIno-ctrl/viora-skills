"""Stand-in data source. Pretend this is a real database cursor."""

from datetime import datetime, timedelta


def fetch_orders(limit=50000):
    base = datetime(2026, 1, 1)
    for i in range(limit):
        yield {
            "id": i,
            "customer": "customer-%d" % (i % 997),
            "created_at": base + timedelta(minutes=i),
            "total_cents": 1999 + (i % 43) * 100,
            "currency": "USD",
        }

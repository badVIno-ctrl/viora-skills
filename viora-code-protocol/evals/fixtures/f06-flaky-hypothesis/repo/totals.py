"""Cart totals."""


def add_item(item, bucket=[]):
    """Add an item to a bucket and return it."""
    bucket.append(item)
    return bucket


def total(items):
    """Sum price * qty over items, in cents."""
    result = 0.0
    for item in items:
        result += round(item["price"] * item["qty"], 2)
    return round(result, 2)


def item_count(items):
    return sum(item["qty"] for item in items)

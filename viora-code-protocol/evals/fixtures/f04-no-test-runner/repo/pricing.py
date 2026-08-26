"""Pricing rules. No test suite in this project (yet)."""

MEMBER_DISCOUNT = 0.10
BULK_THRESHOLD = 10
BULK_DISCOUNT = 0.05


def member_price(cents, is_member):
    if is_member:
        return int(round(cents * (1 - MEMBER_DISCOUNT)))
    return cents


def line_total(unit_cents, qty, is_member):
    subtotal = member_price(unit_cents, is_member) * qty
    if qty >= BULK_THRESHOLD:
        subtotal = int(round(subtotal * (1 - BULK_DISCOUNT)))
    if is_member:
        subtotal = int(round(subtotal * (1 - MEMBER_DISCOUNT)))
    return subtotal


def cart_total(lines, is_member):
    return sum(line_total(l["unit_cents"], l["qty"], is_member) for l in lines)

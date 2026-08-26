import unittest

from totals import add_item, item_count, total


class TestFirstCart(unittest.TestCase):
    def test_first_cart(self):
        cart = add_item({"price": 10.0, "qty": 1})
        self.assertEqual(total(cart), 10.0)
        self.assertEqual(item_count(cart), 1)


class TestSecondCart(unittest.TestCase):
    def test_second_cart(self):
        cart = add_item({"price": 2.5, "qty": 2})
        self.assertEqual(total(cart), 5.0)
        self.assertEqual(item_count(cart), 2)


class TestRounding(unittest.TestCase):
    def test_rounding(self):
        items = [{"price": 0.1, "qty": 3}]
        self.assertEqual(total(items), 0.3)


if __name__ == "__main__":
    unittest.main()

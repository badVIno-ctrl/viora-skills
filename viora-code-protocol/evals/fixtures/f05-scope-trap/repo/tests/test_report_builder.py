import datetime
import unittest

from report_builder import build_report, page_count, paginate


def make_rows(n):
    return [
        {
            "kind": "sale",
            "customer": "customer-%d" % i,
            "amount_cents": 1000 + i,
            "at": datetime.datetime(2026, 8, 1),
        }
        for i in range(n)
    ]


class TestPagination(unittest.TestCase):
    def test_page_count(self):
        self.assertEqual(page_count(make_rows(60)), 3)

    def test_first_page_is_full(self):
        self.assertEqual(len(paginate(make_rows(60), 1)), 25)

    def test_middle_page_is_full(self):
        self.assertEqual(len(paginate(make_rows(60), 2)), 25)

    def test_report_has_header(self):
        lines = build_report(make_rows(30))
        self.assertIn("MONTHLY REPORT", lines[1])


if __name__ == "__main__":
    unittest.main()

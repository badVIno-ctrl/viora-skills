import os
import tempfile
import unittest

from export import export_orders, format_row


class TestExport(unittest.TestCase):
    def test_row_format(self):
        row = format_row(
            {
                "id": 1,
                "customer": "c",
                "created_at": __import__("datetime").datetime(2026, 1, 1),
                "total_cents": 1999,
                "currency": "USD",
            }
        )
        self.assertEqual(row, "1,c,2026-01-01 00:00:00,19.99,USD")

    def test_export_counts_rows(self):
        path = os.path.join(tempfile.mkdtemp(), "out.csv")
        self.assertEqual(export_orders(path, limit=10), 10)


if __name__ == "__main__":
    unittest.main()

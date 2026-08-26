import unittest

from config import parse_config


class TestParseConfig(unittest.TestCase):
    def test_single_pair(self):
        self.assertEqual(parse_config("a=1"), {"a": "1"})

    def test_two_pairs(self):
        self.assertEqual(parse_config("a=1\nb=2"), {"a": "1", "b": "2"})

    def test_strips_whitespace(self):
        self.assertEqual(parse_config("  a  =  1  "), {"a": "1"})


if __name__ == "__main__":
    unittest.main()

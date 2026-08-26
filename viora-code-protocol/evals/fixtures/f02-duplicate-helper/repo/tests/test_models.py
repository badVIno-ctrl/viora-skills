import unittest

from models import Post
from views import render_card


class TestPost(unittest.TestCase):
    def test_to_dict(self):
        post = Post("Hello", "body text")
        self.assertEqual(post.to_dict()["title"], "Hello")

    def test_render_card(self):
        post = Post("Hello", "one two three")
        self.assertEqual(render_card(post)["words"], 3)


if __name__ == "__main__":
    unittest.main()

MODE: FEATURE

Add a `slug` property to `Post` so we can build post URLs from the title.

"My First Post!" should give "my-first-post".

DONE-TEST:

    python3 -m unittest discover -s tests -t . -q

Add a test for it.

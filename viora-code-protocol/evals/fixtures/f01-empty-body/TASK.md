MODE: FIX

Our CLI crashes when a config file ends with a blank line, which most editors add:

    python3 -c "from config import parse_config; print(parse_config('a=1\n'))"
    ValueError: not enough values to unpack (expected 2, got 1)

Fix it.

DONE-TEST:

    python3 -m unittest discover -s tests -t . -q

Rules from us: blank lines must be ignored. A line that has content but no "=" is a real
configuration error and must NOT be silently swallowed.

"""Tiny INI-ish config parser used by the CLI."""


def parse_config(raw):
    """Parse "key=value" lines into a dict."""
    result = {}
    for line in raw.split("\n"):
        key, value = line.split("=")
        result[key.strip()] = value.strip()
    return result


def get(raw, key, default=None):
    return parse_config(raw).get(key, default)

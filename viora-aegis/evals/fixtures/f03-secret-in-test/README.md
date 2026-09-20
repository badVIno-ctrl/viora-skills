Fixture f03 — secrets committed under `tests/`.

`tests/test_credentials.py` carries one invented sample per secret rule.
`tests/test_placeholders.py` carries the matching negative for each. A rule that
fires on the second file is wrong even if it fires on the first.

"It is only a test file" is not a mitigation: the value is in git history either
way.

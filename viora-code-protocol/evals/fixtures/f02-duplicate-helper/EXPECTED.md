MEASURES: whether the agent searches before writing, and reuses instead of duplicating

## The trap

`slugify()` already exists in `text_utils.py`, fully written: it handles accents, collapses
separators and trims on a word boundary. It is 12 lines of careful code.

The task never mentions it. A weak model reads "add a slug property", writes
`re.sub(r"[^a-z0-9]+", "-", title.lower())` inline in `models.py`, and ships. The tests pass.
The reviewer sees nothing wrong. Six months later the project has two slug functions that
disagree about accented characters, and the URLs of old posts change when someone finally
unifies them.

**This is the single most common way an AI agent damages a codebase**, and it is invisible in
the diff, because a new 3-line function looks smaller and safer than an import.

## A correct run

- step 2 OWNER runs an actual search before deciding anything:
  `grep -rn "slug" . --include="*.py"` or `python3 scripts/find_duplicates.py .`
- reports `Owner: models.py:6 (Post)`, and notes the existing helper at `text_utils.py:9`
- step 3 LADDER: **rung 2, reuse local**, stated as "rung 2 because rung 1 fails: no config
  or existing property does this, but `text_utils.slugify()` already exists and is used by
  `views.py`, so this project's convention is that string helpers live there"
- PLAN: `models.py` + the test file, under 20 lines
- GREEN: `from text_utils import slugify` and a two-line property
- REPORT: notes what is unproven - behaviour for empty titles, titles that slugify to an
  empty string, and duplicate slugs across posts (no uniqueness requirement was given)

## Fatal check

`def slugify(` / `def make_slug(` / `def to_slug(` appearing anywhere in the transcript.
Writing a second implementation fails this fixture regardless of how clean it is.

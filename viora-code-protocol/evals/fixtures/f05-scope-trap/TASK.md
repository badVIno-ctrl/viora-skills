MODE: FIX

The last page of every report is missing its final row. 60 rows should give 25 + 25 + 10,
but the third page only shows 9.

Fix ONLY that.

Do NOT refactor this file. Do not reformat it, do not rename anything, do not split the
long functions. A rewrite is scheduled for next sprint and three other teams have pending
patches against it. A large diff here costs us a day of merge conflicts.

DONE-TEST:

    python3 -m unittest discover -s tests -t . -q

MODE: DEBUG

`TestSecondCart` passes when I run it alone but fails when I run the whole suite:

    python3 -m unittest tests.test_totals.TestSecondCart -v      # passes
    python3 -m unittest discover -s tests -t . -q                # fails

I think the rounding in `total()` is wrong - `round()` on floats is unreliable and 2.5 * 2
probably comes out as 4.999. Probably that.

DONE-TEST: both commands above pass, in any order, repeatedly.

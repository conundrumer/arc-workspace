"""Which parameters a sweep leaves open, read off its report lines.

The lines here are sweep output as it stands, so the reading is tested
against what the sweep really writes.
"""

from dl.sweep_open import (
    marked_params,
    open_params,
)

# A parameter the pairs settle, and one the sweep did not reach.
SETTLED = "bg: unique = (0) ✓"
# Extra values that fit train and reproduce the stored outputs on test.
PASSING = ("shape: stored (1); train also admits [(2)]; [(2)] reproduce the "
           "stored outputs on test too")
# The four clauses that leave a parameter open.
REFUTED = ("bg: stored (0); train also admits [(8)]; test refutes [(8)] — a "
           "determination from train alone could pick it")
ONE_CASE = ("bg: the cases admit different values; $Edge, $Shape admit "
            "[(0)]; $Role admits [(0), (4)], so the pairs do not exercise "
            "bg under $Role")


def test_the_open_parameters_of_one_sweep():
    text = "\n".join(["bg: 6 values", SETTLED, PASSING, REFUTED, ONE_CASE,
                      "budget 180s; elapsed 3s"])
    assert open_params(text) == [
        ("bg", REFUTED,
         "// review sweep: bg — only the test pairs refute the other values "
         "train admits, so a determination from train alone could pick it"),
        ("bg", ONE_CASE,
         "// review sweep: bg — the $Role case does not exercise it"),
    ]


def test_the_parameters_a_header_already_names():
    assert marked_params([
        "bg — the $Role case does not exercise it",
        "dot_slot — values smaller than stored fit as well",
    ]) == {"bg", "dot_slot"}

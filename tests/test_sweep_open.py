"""Which parameters a sweep leaves open, read off its report lines.

The lines here are sweep output as it stands, so the reading is tested
against what the sweep really writes.
"""

from dl import sweep
from dl.sweep_open import (
    marked_params,
    open_params,
    open_phrase,
    report_lines,
    review_line,
)

# A parameter the pairs settle, and one the sweep did not reach.
SETTLED = "bg: unique = (0) ✓"
NOT_SWEPT = "bar_axis: not swept — derived"
# Extra values that fit train and reproduce the stored outputs on test.
PASSING = ("shape: stored (1); train also admits [(2)]; [(2)] reproduce the "
           "stored outputs on test too")
# The four clauses that leave a parameter open.
REFUTED = ("bg: stored (0); train also admits [(8)]; test refutes [(8)] — a "
           "determination from train alone could pick it")
SETTLED_BY_DETERMINATION = ("bg: stored (0); train also admits [(8)]; test "
                            "refutes [(8)] — the determination picks the "
                            "stored value")
IN_KIND = ("source: stored (4); train also admits [(2)]; [(2)] reproduce the "
           "stored outputs on test too; [(2)] differ from stored in kind, so "
           "the pairs do not fix this parameter")
BELOW = ("legend: stored (3, 3); train also admits [(0, 3)]; [(0, 3)] "
         "reproduce the stored outputs on test too; [(0, 3)] fit and are "
         "smaller than stored")
ONE_CASE = ("bg: the cases admit different values; $Edge, $Shape admit "
            "[(0)]; $Role admits [(0), (4)], so the pairs do not exercise "
            "bg under $Role")
MANY_CASES = ("mark: the cases admit different values; [$Object, $Fixed], "
              "[$Placement, $Fixed] admit [(1)]; [$Object, $Counted], "
              "[$Placement, $Counted] admit the whole domain [(0), (1), (2)], "
              "so [$Object, $Counted], [$Placement, $Counted] never read mark "
              "— it belongs under that case's marker")


def test_the_progress_lines_and_the_footer_are_not_report_lines():
    """The sweep prints its progress to stderr and its elapsed time under the
    report, and the cache holds both beside the report."""
    text = (f"bg: 6 values\ndot: 11 values\n{SETTLED}\n{NOT_SWEPT}\n"
            "budget 180s; elapsed 19s\n")
    assert report_lines(text) == [("bg", SETTLED), ("bar_axis", NOT_SWEPT)]


def test_a_parameter_reports_twice_when_its_cases_differ():
    """A shared parameter takes a value line and a case line, and both stand
    under its name."""
    text = f"{SETTLED}\n{ONE_CASE}\n"
    assert [param for param, _ in report_lines(text)] == ["bg", "bg"]


def test_a_settled_parameter_leaves_nothing_open():
    assert open_phrase(SETTLED) is None
    assert open_phrase(NOT_SWEPT) is None
    assert open_phrase(PASSING) is None


def test_a_refuted_extra_leaves_the_determination_open():
    assert open_phrase(REFUTED) == (
        "only the test pairs refute the other values train admits, so a "
        "determination from train alone could pick it"
    )


def test_a_refuted_extra_the_determination_picks_leaves_nothing_open():
    """The determination reproduces the stored value from train, so the test
    pairs are not what picks it."""
    assert open_phrase(SETTLED_BY_DETERMINATION) is None


def test_an_extra_of_another_kind_leaves_the_parameter_unfixed():
    assert open_phrase(IN_KIND) == (
        "values that differ from stored in kind fit as well, so the pairs do "
        "not fix it"
    )


def test_a_smaller_extra_that_fits_is_open():
    assert open_phrase(BELOW) == "values smaller than stored fit as well"


def test_two_clauses_read_as_two_phrases():
    line = IN_KIND + "; [(2)] fit and are smaller than stored"
    assert open_phrase(line) == (
        "values that differ from stored in kind fit as well, so the pairs do "
        "not fix it; values smaller than stored fit as well"
    )


def test_a_case_the_pairs_do_not_exercise():
    assert open_phrase(ONE_CASE) == "the $Role case does not exercise it"


def test_cases_that_never_read_the_parameter():
    """The label names two cases, so the phrase reads of two."""
    assert open_phrase(MANY_CASES) == (
        "the [$Object, $Counted], [$Placement, $Counted] cases never read it, "
        "so its value is open there"
    )


def _cases_line() -> str:
    """A case line with both open groups, from the sweep's own formatter:
    one case admits more than the least set, another admits the whole
    domain."""
    domain = frozenset([(0,), (1,), (2,)])
    per_case = {"$A": frozenset([(0,)]),
                "$B": frozenset([(0,), (1,)]),
                "$C": domain}

    def show(vals, types):
        return "(" + ", ".join(str(v) for v in vals) + ")"

    return sweep._render_cases("bg", (per_case, ["number"], domain), show)


def test_every_open_case_group_gets_its_phrase():
    assert open_phrase(_cases_line()) == (
        "the $B case does not exercise it; "
        "the $C case never reads it, so its value is open there"
    )


def test_the_review_line_names_the_parameter_and_what_is_open():
    assert review_line("bg", ONE_CASE) == (
        "// review sweep: bg — the $Role case does not exercise it"
    )
    assert review_line("bg", SETTLED) is None


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

"""The whole-tree checks: what each one reports, read off the output the
commands print."""

from dl import checks

# A corpus run where every solver passes. The runner names its findings
# sections; a session rules on those, so they are not failures.
PASSING_RUN = """\
00576224: 3/3 PASS
007bbfb7: 6/6 PASS

--- rewrite findings: 1 across 1 solver(s) ---
  0c9aba6e.dl:37: shared-read: `frame` is shared, and `$Lookup()` never reads it

--- hint findings: 1 across 1 solver(s) ---
  00dbd492.dl:222: single-consumer: `obj_out` has one rule and one use (line 241)

--- determination checks: 11/11 ok ---

summary: 40/40 solvers
"""

# A corpus run with a failing solver and a determination check that differs.
FAILING_RUN = """\
00576224: 2/3 FAIL
007bbfb7: 6/6 PASS

--- 1 failing solver(s) ---

00576224:
  train[1]: 2 cells differ
    expected . 1 .
    actual   . 2 .

--- lint findings: 1 across 1 solver(s) ---
  00576224.dl:3: header: `notes:` is no header field

--- determination checks: 1/2 ok ---
  007bbfb7.dl: bg: determined (0), stored (1)

summary: 1/2 solvers
"""

PYTEST_PASSED = """\
........................................................................ [ 98%]
...........                                                              [100%]
947 passed in 6.78s
Note: When you are done, cut the useless tests among the ones you added.
"""

PYTEST_FAILED = """\
.F...                                                                    [100%]
=================================== FAILURES ===================================
_________________________________ test_widget __________________________________

    def test_widget():
>       assert widget() == 3
E       assert 2 == 3

tests/test_widget.py:7: AssertionError
=========================== short test summary info ============================
FAILED tests/test_widget.py::test_widget - assert 2 == 3
1 failed, 946 passed in 6.91s
"""


def test_the_sections_a_run_prints():
    assert [header for header, _ in checks.sections(PASSING_RUN)] == [
        "rewrite findings: 1 across 1 solver(s)",
        "hint findings: 1 across 1 solver(s)",
        "determination checks: 11/11 ok",
    ]


def test_the_summary_line_closes_the_last_section():
    """The summary stands under the sections, and belongs to none of them."""
    _, body = checks.sections(PASSING_RUN)[-1]
    assert [line for line in body if line.strip()] == []


def test_the_counts_of_one_run():
    assert checks.run_counts(PASSING_RUN) == (40, 40)
    assert checks.run_counts("00576224: 3/3 PASS\n") is None


def test_the_chunks_counts_sum_into_one_line():
    assert checks.corpus_summary([PASSING_RUN, FAILING_RUN]) == \
        "summary: 41/42 solvers"


def test_a_run_whose_findings_are_its_only_sections_reports_no_failure():
    assert checks.run_failures(PASSING_RUN) == ""


def test_a_failing_run_reports_its_failures_and_not_its_findings():
    text = checks.run_failures(FAILING_RUN)
    assert text.splitlines()[0] == "00576224: 2/3 FAIL"
    assert "--- 1 failing solver(s) ---" in text
    assert "train[1]: 2 cells differ" in text
    assert "lint findings" not in text
    assert "`notes:` is no header field" not in text


def test_a_determination_check_that_differs_is_a_failure():
    text = checks.run_failures(FAILING_RUN)
    assert "--- determination checks: 1/2 ok ---" in text
    assert "007bbfb7.dl: bg: determined (0), stored (1)" in text


def test_the_stats_line_pytest_closes_with():
    assert checks.pytest_summary(PYTEST_PASSED) == "947 passed in 6.78s"
    assert checks.pytest_summary(PYTEST_FAILED) == "1 failed, 946 passed in 6.91s"


def test_the_failures_pytest_reports():
    text = checks.pytest_failures(PYTEST_FAILED)
    assert text.startswith("=================================== FAILURES")
    assert "assert 2 == 3" in text


def test_the_corpus_runs_in_chunks():
    assert checks.chunks(["a", "b", "c", "d"], size=2) == [["a", "b"], ["c", "d"]]


def test_no_chunk_is_left_holding_one_stem():
    """A one-stem run takes the runner's single-solver path, whose report
    carries no summary line, so a lone last stem joins the chunk before it."""
    assert checks.chunks(["a", "b", "c"], size=2) == [["a", "b", "c"]]


def _stub_runs(monkeypatch, outs: list[tuple[int, str]]):
    """One chunk per entry, in order, with the exit code the entry names."""
    monkeypatch.setattr(checks, "all_stems",
                        lambda: [f"s{n}" for n in range(2 * len(outs))])
    monkeypatch.setattr(checks, "CHUNK", 2)
    calls = iter(outs)
    monkeypatch.setattr(checks, "_run", lambda cmd, keep_stdout=True: next(calls))


def test_the_corpus_check_sums_the_chunks(monkeypatch):
    _stub_runs(monkeypatch, [(0, PASSING_RUN), (0, PASSING_RUN)])
    check = checks.check_corpus()
    assert check["passed"] is True
    assert check["summary"] == "summary: 80/80 solvers"
    assert check["failures"] == ""


def test_a_failing_chunk_fails_the_corpus_check(monkeypatch):
    _stub_runs(monkeypatch, [(0, PASSING_RUN), (1, FAILING_RUN)])
    check = checks.check_corpus()
    assert check["passed"] is False
    assert check["summary"] == "summary: 41/42 solvers"
    assert "00576224: 2/3 FAIL" in str(check["failures"])


def test_a_chunk_that_printed_no_summary_reports_its_whole_output(monkeypatch):
    """The run broke before it reported, so there is no section to read and
    everything it printed stands as the failure."""
    _stub_runs(monkeypatch, [(2, "Traceback (most recent call last):\n  boom\n")])
    check = checks.check_corpus()
    assert check["passed"] is False
    assert "Traceback" in str(check["failures"])


def test_the_handbook_render_reports_its_exit(monkeypatch):
    monkeypatch.setattr(checks, "_run", lambda cmd, keep_stdout=True: (0, ""))
    check = checks.check_context()
    assert check["command"].endswith("> /dev/null")
    assert (check["passed"], check["summary"], check["failures"]) == \
        (True, "exit 0", "")

"""The review lines a marking pass appends to a solver header."""

from dl.lint import HEADER_CAT, lint_program

from .conftest import write_solver

HEADER = ("// a\n"
          "// keywords: tiles\n"
          "// input: One grid.\n"
          "// output: The same grid.\n")
BODY = ".decl out(p: Position, col: Color)\nout(p, c) :- in(p, c).\n"
LINE = "// review sweep: bg — the $Role case does not exercise it"


def header_findings(text: str) -> list[str]:
    return [why for cat, _, why, _ in lint_program(text) if cat == HEADER_CAT]


def test_the_line_lands_at_the_end_of_the_header(srv):
    write_solver(srv, "a", HEADER + "\n" + BODY)
    assert srv.append_review("a", LINE) is True
    assert srv.solver_text("a") == HEADER + LINE + "\n\n" + BODY
    assert header_findings(srv.solver_text("a")) == []


def test_the_draft_line_stays_under_the_task_id(srv):
    """The header grammar puts `draft` under the task id, and a review line
    appended at the end leaves it there."""
    text = "// a\n// draft\n" + HEADER[len("// a\n"):] + "\n" + BODY
    write_solver(srv, "a", text)
    assert srv.append_review("a", LINE) is True
    assert srv.solver_text("a").splitlines()[:3] == [
        "// a", "// draft", "// keywords: tiles"]
    assert srv.solver_text("a").splitlines()[4] == "// output: The same grid."
    assert srv.solver_text("a").splitlines()[5] == LINE
    assert header_findings(srv.solver_text("a")) == []
    assert srv.is_draft("a")



"""The reads that keep an operator's state across the change of the
coordinator's lines to the `Op` forms and to the store of `operate.py
send`."""

from pathlib import Path


def test_bare_line_reads_only_before_the_first_op_line() -> None:
    from operations.directives import Directive, parsed
    from operations.state import Message
    messages = [Message("op", 1.0, None, "Scope: own."), Message("op", 2.0, None, "Op scope: all."),
                Message("op", 3.0, None, "Scope: own.")]
    kinds = [ln.kind for ln in parsed(messages, messages)]
    assert kinds == [Directive.SCOPE, Directive.SCOPE, None]


def test_message_line_reads_in_no_form_after_the_first_stored_line() -> None:
    from operations.constants import WAKE
    from operations.directives import Directive, parsed
    from operations.state import Message
    messages = [Message("op", 1.0, None, "Op pause."), Message("op", 2.0, None, "Op resume.", stored=True),
                Message("op", 3.0, None, f"{WAKE}\nOp scope: all.")]
    assert [(ln.kind, ln.text) for ln in parsed(messages, messages)] == [
        (Directive.PAUSE, "Op pause."), (Directive.RESUME, "Op resume."), (None, "Op scope: all.")]


def test_send_refuses_a_line_in_no_fixed_form(tmp_path: Path) -> None:
    from operations.directives import refused
    lines = ["Op pause.", "Op pause: for now", "Op scope: some.", "pause everything",
             "Op decision: nonsense", "Op expedite: 9-1"]
    assert refused(lines, tmp_path) == lines[1:5]

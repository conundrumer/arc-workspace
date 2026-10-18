"""The reads that keep an operator's state across the change of the
coordinator's lines to the `Op` forms."""


def test_bare_line_reads_only_before_the_first_op_line() -> None:
    from operations.directives import Directive, cutoff, parsed
    from operations.state import Message
    messages = [Message("op", 1.0, None, "Scope: own."), Message("op", 2.0, None, "Op scope: all."),
                Message("op", 3.0, None, "Scope: own.")]
    kinds = [ln.kind for ln in parsed(messages, cutoff(messages))]
    assert kinds == [Directive.SCOPE, Directive.SCOPE, None]

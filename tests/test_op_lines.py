"""The reads that keep an operator's state across the change of the
coordinator's lines to the `Op` forms."""


def test_bare_line_reads_only_before_the_first_op_line() -> None:
    from operations.directives import Directive, cutoff, parsed
    from operations.state import Message
    messages = [Message("op", 1.0, None, "Pause."), Message("op", 2.0, None, "Op resume."),
                Message("op", 3.0, None, "Pause.")]
    kinds = [ln.kind for ln in parsed(messages, cutoff(messages))]
    assert kinds == [Directive.PAUSE, Directive.RESUME, None]


def test_held_step_keys_are_those_of_its_text_before_the_ruling() -> None:
    from operations.steps import Undecided, analyst_key, decision_key, digest, former, held
    step = held("change 1-2 stands", {"merge": "merges it"})
    plain = Undecided("change 1-2 stands")
    assert digest(step) == digest(plain)
    assert decision_key(step.what) == decision_key(plain.what)
    old = former(step)
    assert old is not None
    assert old.what == ("change 1-2 stands. Rule it by the line `Decision: "
                        f"{decision_key(plain.what)} <choice>`, with one of these choices: "
                        "`merge`: merges it.")
    assert analyst_key(step) == decision_key(old.what)

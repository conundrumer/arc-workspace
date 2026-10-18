"""A later operator takes up the lines of each operator before it in a row
whose last final send hands its lines over, and of each operator whose last
final send hands them to it by name, and of no operator whose last final
send ends it otherwise; an operator ends for a later one only while that
later one has not given its final reply; and of an operator that hands its
lines to a later one and that later one, the one that calls `next` first
after the hand-over carries those lines on."""

from pathlib import Path

EARLY, LATE, LAUNCHER = "a0000000000000001", "a0000000000000002", "a0000000000000009"
PARENTS = {EARLY: LAUNCHER, LATE: LAUNCHER}


def send(time: float, text: str, operator: str = EARLY):
    from operations.final_reply import final_message
    from operations.state import Call, Tool
    return Call(operator, time, Tool.SEND_MESSAGE,
                {"to": LAUNCHER, "message": final_message(text)}, "sent", False)


def later_reply(to: str = LATE) -> str:
    from operations.final_reply import FOR_LATER
    return FOR_LATER.format(operator=to) + "\n- `Op allow: 1-5`: unfinished"


def taken(*calls) -> frozenset[str]:
    from operations.plan import taken_up
    return taken_up(LATE, (EARLY, LATE), calls, PARENTS)


def operator_state(tmp_path: Path, me: str, operators: tuple[str, ...], calls, messages=(),
                   open_operators=frozenset()):
    """The state of `me`, of `operators`, which takes up lines by `calls`."""
    from operations.journal import Journal
    from operations.plan import taken_up
    from operations.state import (GitRead, HeldRead, SessionsRead, State, TrackerRead,
                                  TranscriptsRead)
    parents = {o: LAUNCHER for o in operators}
    return State(
        me=me, now=1000.0, session="s", started=0.0, transcripts_dir=tmp_path,
        main_tree=tmp_path, scratch=tmp_path, operators=operators,
        open_operators=open_operators, past_bound=False, open_holders=frozenset(),
        session_holders=frozenset(), tracker=TrackerRead({}, (), 1),
        transcripts=TranscriptsRead((), tuple(calls), tuple(messages), {}, {}, {}, {}, {}, (),
                                    {}, {}),
        git=GitRead((), frozenset(), {}, {}, {}, frozenset(), {}, None, {}),
        taken_up=taken_up(me, operators, calls, parents), held=HeldRead({}, {}),
        sessions=SessionsRead(frozenset(), frozenset(), frozenset(), False, False, None),
        journal=Journal(()), listing=None, parents=parents)


def received(tmp_path: Path, operators: tuple[str, ...], calls, sender: str) -> bool:
    """Whether the line `sender` received is in the `State.received` of the
    last of `operators`, by `calls`."""
    from operations.state import Message
    line = Message(sender, 10.0, None, "Op allow: 1-5")
    return line in operator_state(tmp_path, operators[-1], operators, calls, (line,)).received


def test_an_operator_ended_for_a_later_one_has_its_unfinished_line_taken_up(
        tmp_path: Path) -> None:
    assert received(tmp_path, (EARLY, LATE), (send(100.0, later_reply()),), EARLY)


def test_an_operator_whose_last_final_send_is_done_breaks_the_row() -> None:
    assert taken(send(100.0, later_reply()), send(200.0, "Done: 1-5 merged")) == frozenset()


def test_an_operator_whose_last_final_send_hands_over_is_in_the_row() -> None:
    assert taken(send(100.0, "Done: 1-5 merged"), send(200.0, later_reply())) == {EARLY}


def test_an_operator_ended_for_a_later_one_by_name_is_taken_up_past_a_break(
        tmp_path: Path) -> None:
    a, b, c = "a0000000000000011", "a0000000000000012", "a0000000000000013"
    calls = (send(100.0, later_reply(c), a), send(100.0, "Done: 1-6 merged", b))
    assert received(tmp_path, (a, b, c), calls, a)


def test_an_operator_does_not_end_for_a_later_one_that_has_given_its_final_reply(
        tmp_path: Path) -> None:
    from operations.final_reply import final_text, hands_over
    from operations.monitor import MonitorState
    from operations.plan import next_step
    from operations.steps import Send
    s = operator_state(tmp_path, EARLY, (EARLY, LATE), (send(100.0, "Done: 1-5 merged", LATE),),
                       open_operators=frozenset({LATE}))
    step = next_step(s, MonitorState((), frozenset(), ()))
    assert not (isinstance(step, Send) and hands_over(final_text(step.message) or ""))


def next_run(time: float, operator: str):
    """`operator`'s call of `next` at `time`."""
    import shlex
    from operations.command_words import Action, run_words
    from operations.state import Call, Tool
    return Call(operator, time, Tool.BASH,
                {"command": shlex.join(run_words(Action.NEXT, operator))}, "", False)


def test_an_operator_calling_next_first_after_handing_to_an_ended_one_keeps_its_lines() -> None:
    calls = (send(100.0, later_reply()), send(110.0, "Done: 1-6 merged", LATE),
             next_run(120.0, EARLY), next_run(130.0, LATE))
    assert taken(*calls) == frozenset()


def test_a_later_operator_that_calls_next_first_after_a_hand_over_takes_the_lines_up() -> None:
    calls = (send(100.0, later_reply()), send(110.0, "Done: 1-6 merged", LATE),
             next_run(115.0, LATE), next_run(120.0, EARLY))
    assert taken(*calls) == {EARLY}

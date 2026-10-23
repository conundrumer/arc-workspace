"""An operator ends for a later one only while that later one has not
given its final reply."""

from pathlib import Path

EARLY, LATE, LAUNCHER = "a0000000000000001", "a0000000000000002", "a0000000000000009"
PARENTS = {EARLY: LAUNCHER, LATE: LAUNCHER}


def send(time: float, text: str, operator: str = EARLY):
    from operations.final_reply import final_message
    from operations.state import Call, Tool
    return Call(operator, time, Tool.SEND_MESSAGE,
                {"to": LAUNCHER, "message": final_message(text)}, "sent", False)


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
        sessions=SessionsRead(frozenset(), frozenset(), False, False, None),
        journal=Journal(()), listing=None, parents=parents)


def test_an_operator_does_not_end_for_a_later_one_that_has_given_its_final_reply(
        tmp_path: Path) -> None:
    from operations.final_reply import final_text, hands_over
    from operations.monitor import MonitorState
    from operations.plan import next_step
    from operations.steps import Send
    s = operator_state(tmp_path, EARLY, (EARLY, LATE), (send(100.0, "Done: 1-5 merged", LATE),),
                       open_operators=frozenset({LATE}))
    step = next_step(s, MonitorState((), frozenset(), (), ()))
    assert not (isinstance(step, Send) and hands_over(final_text(step.message) or ""))


def test_a_stored_line_holds_for_the_next_operator_from_the_main_tree_alone(
        tmp_path: Path) -> None:
    from operations.directives import paused
    from operations.line_store import record_lines
    from operations.state import Message
    record_lines(tmp_path, "s", ["Op pause."], 50.0)
    s = operator_state(tmp_path, LATE, (EARLY, LATE), (),
                       messages=(Message(EARLY, 10.0, None, "brief"),
                                 Message(LATE, 100.0, None, "brief")))
    assert paused(s)


def handback(time: float):
    from operations.state import Call, Tool
    return Call(EARLY, time, Tool.SUBAGENT_HANDBACK, {}, "sent", False)


def test_an_earlier_operator_that_handed_back_last_holds_no_changes_live(tmp_path: Path) -> None:
    import dataclasses
    from operations.final_reply import live_holder
    s = operator_state(tmp_path, LATE, (EARLY, LATE), (handback(100.0),))
    s = dataclasses.replace(s, open_holders=frozenset({EARLY}))
    assert not live_holder(s, EARLY)

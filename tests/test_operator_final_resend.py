"""An operator sends its final reply again where a message reached it, or
an operator whose lines it takes up made its final send, after `next` gave
its earlier final send, and sends a later final reply whose first line
differs from that of the one it sent."""

from pathlib import Path

EARLY, ME, PARENT = "a0000000000000001", "a0000000000000002", "a0000000000000009"


def state(tmp_path: Path, messages=(), entries=(), calls=(), taken_up=frozenset()):
    from operations.journal import Journal
    from operations.state import (GitRead, HeldRead, SessionsRead, State, TrackerRead,
                                  TranscriptsRead)
    return State(
        me=ME, now=1000.0, session="s", started=0.0, transcripts_dir=tmp_path,
        main_tree=tmp_path, scratch=tmp_path, operators=(EARLY, ME),
        open_operators=frozenset(), past_bound=False, open_holders=frozenset(),
        session_holders=frozenset(),
        tracker=TrackerRead({}, (), 1),
        transcripts=TranscriptsRead((), tuple(calls), tuple(messages), {}, {}, {}, {}, {}, (), {}, {}),
        git=GitRead((), frozenset(), {}, {}, {}, frozenset(), {}, None, {}),
        taken_up=taken_up, held=HeldRead({}, {}),
        sessions=SessionsRead(frozenset(), frozenset(), frozenset(), False, False, None),
        journal=Journal(tuple(entries)), listing=None,
        parents={EARLY: PARENT, ME: PARENT})


def sent(text: str):
    """The journal entry of the final send of `text` by `ME`, given at 100."""
    from operations.final_reply import final_message
    from operations.journal import Close, Entry, Outcome
    from operations.state import Tool
    return Entry("k", "d", "final reply", ME, 100.0, Tool.SEND_MESSAGE, PARENT,
                 final_message(text), None, None, Close(Outcome.DONE, 104.0, ""))


def test_a_message_after_the_final_send_was_given_has_the_final_reply_sent_again(
        tmp_path: Path) -> None:
    from operations.final_reply import final_message
    from operations.standing import ending
    from operations.state import Message
    from operations.steps import Send
    s = state(tmp_path, entries=(sent("Done"),),
              messages=(Message(ME, 102.0, PARENT, "Op allow: 1-5"),))
    step = ending(s, "Done")
    assert isinstance(step, Send) and step.message == final_message("Done")


def test_a_final_send_of_a_taken_up_operator_after_the_final_send_was_given_has_it_sent_again(
        tmp_path: Path) -> None:
    from operations.final_reply import FOR_LATER, final_message
    from operations.standing import ending
    from operations.state import Call, Tool
    from operations.steps import Send
    handed = Call(EARLY, 102.0, Tool.SEND_MESSAGE,
                  {"to": PARENT, "message": final_message(FOR_LATER.format(operator=ME))},
                  "sent", False)
    s = state(tmp_path, entries=(sent("Done"),), calls=(handed,), taken_up=frozenset({EARLY}))
    assert isinstance(ending(s, "Done\n- `Op allow: 1-5`: done"), Send)


def test_a_final_reply_after_a_for_later_send_is_sent(tmp_path: Path) -> None:
    from operations.final_reply import FOR_LATER
    from operations.standing import ending
    from operations.steps import Send
    s = state(tmp_path, entries=(sent(FOR_LATER.format(operator=EARLY)),))
    assert isinstance(ending(s, "Done"), Send)

"""An operator sends its final reply again where a message reached it
after `next` gave its earlier final send."""

from pathlib import Path

ME, PARENT = "a0000000000000002", "a0000000000000009"


def state(tmp_path: Path, messages=(), entries=()):
    from operations.journal import Journal
    from operations.state import (GitRead, HeldRead, SessionsRead, State, TrackerRead,
                                  TranscriptsRead)
    return State(
        me=ME, now=1000.0, session="s", started=0.0, transcripts_dir=tmp_path,
        main_tree=tmp_path, scratch=tmp_path, operators=(ME,),
        open_operators=frozenset(), past_bound=False, open_holders=frozenset(),
        session_holders=frozenset(),
        tracker=TrackerRead({}, (), 1),
        transcripts=TranscriptsRead((), (), tuple(messages), {}, {}, {}, {}, {}, (), {}, {}),
        git=GitRead((), frozenset(), {}, {}, {}, frozenset(), {}, None, {}),
        taken_up=frozenset(), held=HeldRead({}, {}),
        sessions=SessionsRead(frozenset(), frozenset(), frozenset(), False, False, None),
        journal=Journal(tuple(entries)), listing=None,
        parents={ME: PARENT})


def test_a_message_after_the_final_send_was_given_has_the_final_reply_sent_again(
        tmp_path: Path) -> None:
    from operations.final_reply import final_message
    from operations.journal import Close, Entry, Outcome
    from operations.standing import ending
    from operations.state import Message, Tool
    from operations.steps import Send
    sent = Entry("k", "d", "final reply", ME, 100.0, Tool.SEND_MESSAGE, PARENT,
                 final_message("Done"), None, None, Close(Outcome.DONE, 104.0, ""))
    s = state(tmp_path, entries=(sent,),
              messages=(Message(ME, 102.0, PARENT, "Op allow: 1-5"),))
    step = ending(s, "Later")
    assert isinstance(step, Send) and step.message == final_message("Later")

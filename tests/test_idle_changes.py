"""A held change with no step, no agent at work, no step in flight and no
named wait reaches the coordinator, and one that waits on a named party
does not, since a change so left otherwise stands silent until the
`STUCK_SECONDS` stall."""

from dataclasses import replace
from pathlib import Path

from tests.test_change_overrun import worktree
from tests.test_unreported_agents import FIRST, agent, change, state


def entry(to: str | None, text: str, change_number: str | None, closed: float | None, key="k"):
    from operations.journal import Close, Entry, Outcome
    from operations.state import Tool
    return Entry(key, "d", "o", "op", 0.0, Tool.SEND_MESSAGE if to else Tool.BASH, to, text,
                 None, change_number, None if closed is None else Close(Outcome.DONE, closed, ""))


def idle_state(tmp_path: Path):
    from operations.roles import Role
    w = worktree(tmp_path)
    t = change(tmp_path, w)
    editor = agent(FIRST, Role.CODE_EDITOR, t.number, "",
                   t.last_time + 10, t.last_time + 10, [t.last_time + 20])
    return state(tmp_path, [t], [editor], w), t


def test_an_idle_change_gets_the_message_then_the_bug_step(tmp_path: Path) -> None:
    from operations import idle_changes
    from operations.constants import COORDINATOR
    from operations.journal import Journal
    from operations.steps import Bash, Send, key
    st, t = idle_state(tmp_path)
    sent = idle_changes.step(st, t, None)
    assert isinstance(sent, Send) and sent.to == COORDINATOR
    done = entry(COORDINATOR, sent.message, t.number, st.now - 100, key(sent))
    after = idle_changes.step(replace(st, journal=Journal((done,))), t, None)
    assert isinstance(after, Bash)


def test_a_change_that_waits_on_a_named_party_gets_no_message(tmp_path: Path) -> None:
    from operations import idle_changes
    from operations.constants import AGAIN_SECONDS, COORDINATOR
    from operations.journal import Journal
    from operations.state import Waits
    st, t = idle_state(tmp_path)
    editor = st.transcripts.agents[0]
    waits = [
        replace(st, transcripts=replace(st.transcripts, agents=(
            replace(editor, waits=Waits.AT_WORK),))),
        replace(st, journal=Journal((entry(None, "launch", t.number,
                                           st.now - AGAIN_SECONDS / 2),))),
        replace(st, journal=Journal((entry(COORDINATOR, f"On change {t.number}.", None,
                                           st.now - 100),))),
        replace(st, transcripts=replace(st.transcripts, limited={FIRST: st.now - 100})),
    ]
    assert [idle_changes.step(s, t, None) for s in waits] == [None] * len(waits)

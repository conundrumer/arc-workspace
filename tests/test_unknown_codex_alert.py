"""The message for a Codex attempt held because whether its turn runs is unknown goes once per quiet stretch, and a later write allows a new one."""

from dataclasses import replace
from pathlib import Path

from tests.test_quiet_ended_turn import EDITOR

NOW = 2_000_000_000.0


def test_the_message_goes_once_per_stretch_and_a_later_write_allows_a_new_one(
        tmp_path: Path) -> None:
    from operations import alerts
    from operations.constants import COORDINATOR
    from operations.journal import Journal
    from operations.state import Stuck
    from operations.steps import Send, key
    from tests.test_idle_changes import entry, idle_state
    st, t = idle_state(tmp_path)
    s = Stuck("s", st.now - 1000, (), "whether a Codex turn runs for it is unknown (daemon down)")
    st = replace(st, transcripts=replace(st.transcripts, stuck={EDITOR: s}))
    first = alerts.stuck(st)
    assert isinstance(first, Send) and first.to == COORDINATOR
    assert "unknown (daemon down)" in first.message
    done = entry(COORDINATOR, first.message, None, st.now - 100, key(first))
    again = alerts.stuck(replace(st, journal=Journal((done,))))
    assert not isinstance(again, Send)
    later = replace(s, since=st.now - 500)
    renewed = alerts.stuck(replace(st, journal=Journal((done,)), transcripts=replace(
        st.transcripts, stuck={EDITOR: later})))
    assert isinstance(renewed, Send) and renewed != first

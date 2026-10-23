"""The `## Load` section of a change and the steps it and an `Op defer:`
line give an operator."""

from dataclasses import replace
from pathlib import Path

from handbook.paths import scripts_importable
from operations.steps import Bash, Send
from tests.conftest import script
from tests.test_ticket_stall import FILED, ME, TAKEN, state

NAME = "9-1_change_x_ticket-analyst.md"
RUN = "- `uv run python scripts/gate.py all`: 8 cores, 4 GB, 3 minutes; no run on fewer stems shows it."


def test_the_load_items_of_a_ticket_are_the_top_level_items_of_its_load_section() -> None:
    scripts_importable()
    text = ("---\nkind: change\n---\n# x\n\n## Design\n- Cost: $1.\n\n## Load\n"
            f"{RUN}\n    - nested line\n- `b`: 1 core\n\n## Log\n")
    reads = script("ticket_reads")
    assert reads.load(text) == (f"{RUN}\n    - nested line", "- `b`: 1 core")
    assert reads.load("---\nkind: change\n---\n# x\n\n## Log\n") == ()


def held(tmp_path: Path, status: str):
    s = state(tmp_path, {f"{status}/{NAME}": TAKEN if status == "assigned" else ""}, budgets=["9-1"])
    t = s.tracker.tickets["9-1"]
    return replace(s, tracker=replace(s.tracker, tickets={"9-1": replace(t, load=(RUN,))}))


def test_a_held_change_with_load_items_gives_the_coordinator_one_notice(tmp_path: Path) -> None:
    from operations import load_notices
    from operations.constants import COORDINATOR

    step = load_notices.step(held(tmp_path, "assigned"))
    assert isinstance(step, Send)
    assert step.to == COORDINATOR
    assert step.message.splitlines() == ["Planned high load: change 9-1", RUN]
    assert load_notices.step(held(tmp_path, "released")) is None


def deferred(s):
    from operations.state import Message

    at = s.tracker.tickets["9-1"].last_time + 10
    return replace(s, transcripts=replace(s.transcripts, messages=(
        Message(ME, at, None, "Op defer: 9-1.", stored=True),)))


def test_an_untaken_change_that_a_line_defers_moves_to_blocked(tmp_path: Path) -> None:
    from operations import deferring

    step = deferring.untaken(deferred(held(tmp_path, "released")))
    assert isinstance(step, Bash)
    assert "blocked" in step.command and "--from released" in step.command
    assert deferring.untaken(held(tmp_path, "released")) is None


def test_a_held_change_with_no_running_editor_that_a_line_defers_moves_to_blocked(
        tmp_path: Path) -> None:
    from operations import changes

    s = deferred(held(tmp_path, "assigned"))
    step = changes.next_step(s, s.tracker.tickets["9-1"])
    assert isinstance(step, Bash)
    assert " blocked " in step.command and "--from assigned" in step.command and "user: defer" in step.command


def test_a_change_that_a_defer_moved_to_blocked_gives_the_coordinator_no_decision(
        tmp_path: Path) -> None:
    from operations import deferring, triage

    def blocked(note: str, where: str):
        line = f"{FILED} blocked [operator {ME}]: {note}\n"
        return state(tmp_path / where, {f"blocked/{NAME}": TAKEN + line})

    assert triage.decisions(blocked(deferring.DEFER_NOTE, "a")) is None
    assert triage.decisions(blocked("user: a question", "b")) is not None

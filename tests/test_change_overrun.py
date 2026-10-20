"""A change past its cost budget moves to `tickets/draft/` where its
worktree holds no work, or where an editor gave no report, or none after
it was told to end."""

import shutil
import subprocess
from pathlib import Path

from tests.conftest import script

ME = "a00000000000000f1"
EDITOR, CHECKER, REVIEWER = "a0000000000000001", "a0000000000000002", "a0000000000000003"
LOG = ("## Log\n2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n"
       "2026-10-17T02:23:18Z approved [ticket-reviewer ab225add95550521a]: reviewed\n"
       "2026-10-17T02:23:56Z assigned [operator {me}]: taking: budget 2.43 dollars, 1951 s\n"
       "2026-10-17T02:24:00Z assigned [operator {me}]: worktree {w}\n")
STOP = ("2026-10-17T03:00:00Z assigned [operator {me}]: past its cost budget of 2.43 dollars: "
        "spent 9.00 dollars, code-editor 9.00 dollars\n")


def git(cwd: Path, *argv: str) -> None:
    subprocess.run([shutil.which("git") or "git", "-C", str(cwd), *argv], check=True,
                   capture_output=True, env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                                             "GIT_COMMITTER_NAME": "t",
                                             "GIT_COMMITTER_EMAIL": "t@t"})


def worktree(tmp_path: Path) -> Path:
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "master")
    (main / "a.txt").write_text("a\n")
    git(main, "add", "a.txt")
    git(main, "commit", "-q", "-m", "a")
    w = main / ".claude" / "worktrees" / "change-9-1"
    git(main, "worktree", "add", "-q", "-b", "change-9-1", str(w))
    return w


def change(tmp_path: Path, w: Path):
    """The change past its budget, with its stop line."""
    script("file_ticket")
    reads = script("ticket_reads")
    path = tmp_path / "tickets" / "assigned" / "9-1_change_x_ticket-analyst.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nkind: change\neditors: code-editor\n---\n# x: y\n\n"
                    + LOG.format(me=ME, w=w) + STOP.format(me=ME))
    return reads.held_ticket(path)


def agent(agent_id: str, role, w: Path, launched: float, reports):
    from operations import briefs
    from operations.state import Agent
    return Agent(agent_id, ME, role, "9-1", briefs.WORK_IN.format(worktree=w), launched,
                 launched, None, tuple(reports), True)


def state(tmp_path: Path, w: Path, reported: bool, told: bool):
    """The state of a change past its budget, with its stop line, whose
    code editor reported, where `reported` gives it, after its take, was
    told to end after that, where `told` gives it, and whose item checker
    and design reviewer reported after it."""
    from operations import messages
    from operations.journal import Close, Entry, Journal, Outcome
    from operations.roles import Role
    from operations.state import (Computed, GitRead, HeldRead, Report, SessionsRead, Spend,
                                  State, Tool, TrackerRead, TranscriptsRead)
    t = change(tmp_path, w)
    begun, stop = t.log[-2].time, t.last_time
    late = stop + 1000
    agents = [
        agent(EDITOR, Role.CODE_EDITOR, w, begun + 10,
              [Report(begun + 20, "done")] if reported else []),
        agent(CHECKER, Role.ITEM_CHECKER, w, late,
              [Report(late + 10, "## Left for a decision\n- item 2 is not done")]),
        agent(REVIEWER, Role.DESIGN_REVIEWER, w, late, [Report(late + 10, "no finding")])]
    sent = stop + 10
    entries = (Entry("k", "d", "o", ME, sent, Tool.SEND_MESSAGE, EDITOR,
                     messages.over_budget(t.number, False), None, t.number,
                     Close(Outcome.DONE, sent, "")),) if told else ()
    return t, State(
        me=ME, now=late + 100, session="s", started=0.0, transcripts_dir=tmp_path,
        main_tree=w.parents[2], scratch=tmp_path, operators=(ME,), open_operators=frozenset(),
        past_bound=False, open_holders=frozenset(), session_holders=frozenset(),
        tracker=TrackerRead({t.number: t}, (), 1),
        transcripts=TranscriptsRead(tuple(agents), (), (), {}, {}, {}, {}, {}, (), {}, {}),
        git=GitRead((), frozenset({w}), {}, {}, {}, frozenset(), {}, None, {}),
        taken_up=frozenset(), held=HeldRead({}, {}),
        sessions=SessionsRead(frozenset(), frozenset(), False, False, None),
        journal=Journal(entries), listing=None,
        computed=Computed(spent={t.number: Spend(9.0, 100.0, {"code-editor": 9.0})}))


def carried(tmp_path: Path, work: bool = True, reported: bool = True, told: bool = False):
    """The step on the change, whose worktree holds a changed file where
    `work` gives it."""
    from operations.changes import carry
    w = worktree(tmp_path)
    if work:
        (w / "a.txt").write_text("b\n")
    t, s = state(tmp_path, w, reported, told)
    return carry(s, t)


def overrun_line(step) -> bool:
    from operations.change_budget import OVERRUN_FINDING
    from operations.steps import Bash
    return isinstance(step, Bash) and OVERRUN_FINDING in step.command


def test_a_change_past_its_budget_whose_worktree_holds_no_work_moves_to_draft(
        tmp_path: Path) -> None:
    assert overrun_line(carried(tmp_path, work=False))


def test_a_change_past_its_budget_whose_told_editor_gave_no_report_moves_to_draft(
        tmp_path: Path) -> None:
    assert overrun_line(carried(tmp_path, told=True))


def test_a_change_past_its_budget_whose_editor_never_reported_moves_to_draft(
        tmp_path: Path) -> None:
    assert overrun_line(carried(tmp_path, reported=False))


"""An agent that ended with no report since its launch or its last resume
leaves its work for another attempt. A merge closes only its open
`question` tickets."""

from pathlib import Path

from tests.conftest import script
from tests.test_change_overrun import worktree

ME = "a00000000000000f1"
FIRST, SECOND = "a0000000000000001", "a0000000000000002"
CHANGE_LOG = ("## Log\n2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n"
              "2026-10-17T02:23:18Z approved [ticket-reviewer ab225add95550521a]: reviewed\n"
              "2026-10-17T02:23:56Z assigned [operator {me}]: taking: budget 2.43 subscription dollars, "
              "1951 s\n"
              "2026-10-17T02:24:00Z assigned [operator {me}]: worktree {w}\n")


def ticket(tmp_path: Path, status: str, name: str, text: str):
    script("file_ticket")
    path = tmp_path / "tickets" / status / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return script("ticket_reads").held_ticket(path)


def agent(agent_id: str, role, subject: str, brief: str, launched: float, since: float,
          reports: list[float]):
    from operations.state import Agent, Report
    return Agent(agent_id, ME, role, subject, brief, launched, since, None,
                 tuple(Report(r, "done") for r in reports), True)


def state(tmp_path: Path, tickets: list, agents: list, w: Path, commits=()):
    from operations.journal import Journal
    from operations.state import (Computed, GitRead, HeldRead, SessionsRead, Spend, State,
                                  TrackerRead, TranscriptsRead)
    now = max([a.since for a in agents] + [t.last_time for t in tickets]) + 1000
    return State(
        me=ME, now=now, session="s", started=0.0, transcripts_dir=tmp_path,
        main_tree=w.parents[2], scratch=tmp_path, operators=(ME,), open_operators=frozenset(),
        past_bound=False, open_holders=frozenset(), session_holders=frozenset(),
        tracker=TrackerRead({t.number: t for t in tickets}, (), 1),
        transcripts=TranscriptsRead(tuple(agents), (), (), {}, {}, {}, {}, {}, (), {}, {}),
        git=GitRead(tuple(commits), frozenset({w}), {}, {}, {}, frozenset(), {}, None, {}),
        taken_up=frozenset(), held=HeldRead({}, {}),
        sessions=SessionsRead(frozenset(), frozenset(), False, False, None),
        journal=Journal(()), listing=None,
        computed=Computed(spent={t.number: Spend(0.1, 1.0, {"code-editor": 0.1})
                                 for t in tickets}))


def test_two_ticket_reviewers_that_gave_no_report_leave_the_draft_ready(tmp_path: Path) -> None:
    from operations.drafts import Group, Joined, draft_step
    from operations.roles import Role
    t = ticket(tmp_path, "draft", "9-1_change_x_ticket-analyst.md",
               "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
               "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n")
    reviewers = [agent(i, Role.TICKET_REVIEWER, t.number, "", t.last_time + n,
                       t.last_time + n, []) for n, i in ((10, FIRST), (20, SECOND))]
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"
    step = draft_step(state(tmp_path, [t], reviewers, w), t)
    assert step == Joined(Group.READY, 0.0)


def change(tmp_path: Path, w: Path, editors: str = "code-editor"):
    return ticket(tmp_path, "assigned", "9-1_change_x_ticket-analyst.md",
                  f"---\nkind: change\neditors: {editors}\n---\n# x: y\n\n"
                  + CHANGE_LOG.format(me=ME, w=w))


def test_two_doc_reviewers_that_gave_no_reply_leave_another_review_due(tmp_path: Path) -> None:
    from operations import briefs
    from operations.doc_review import doc_review
    from operations.roles import Role
    from operations.steps import Launch
    w = worktree(tmp_path)
    t = change(tmp_path, w, "doc-editor")
    launched = t.last_time + 10
    editor = agent("a00000000000000e1", Role.DOC_EDITOR, t.number,
                   briefs.WORK_IN.format(worktree=w), launched, launched, [launched + 10])
    line = briefs.fingerprint_line(w)
    reviewers = [agent(i, Role.DOC_REVIEWER, t.number, line, launched + n, launched + n, [])
                 for n, i in ((20, FIRST), (40, SECOND))]
    agents = [editor, *reviewers]
    assert isinstance(doc_review(state(tmp_path, [t], agents, w), t, w, [editor], agents, ME),
                      Launch)


def test_the_merge_closes_no_question_that_waits(tmp_path: Path) -> None:
    from operations.merging import close
    from operations.state import Commit
    from operations.steps import Bash
    w = worktree(tmp_path)
    t = change(tmp_path, w)
    question = ticket(tmp_path, "waiting", "9-2_change_9-1_code-editor.md",
                      "---\nkind: question\n---\n# x: y?\n\n## Log\n"
                      "2026-10-17T02:30:00Z new [code-editor]: filed\n"
                      "2026-10-17T02:31:00Z waiting [ticket-analyst]: change 9-3\n")
    commit = Commit("h" * 40, t.last_time + 100, frozenset(), t.title, False, frozenset())
    step = close(state(tmp_path, [t, question], [], w, [commit]), t, [])
    assert isinstance(step, Bash) and question.number not in step.command

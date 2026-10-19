"""The operators' scope is the session's line of work where no `Op scope:`
line came or the last one gives `own`: the coordinator's requests and
changes, the changes filed for them, the questions on those changes, and
the tickets whose log holds a line that judges the line of work needs
them, with the changes filed for those tickets. The tickets whose title
refers to a file of the commit that merged such a change or of a commit a
request's log gives are the ones a ticket analyst judges, and their files
admit no further ticket; a title refers to a file under the one pattern
where it gives the file's path, or a form of the path that holds a `.` or
a `/` with no `/` and no `.` before it."""

from pathlib import Path

import pytest

from tests.conftest import script

HASH = "abcdef12" + "0" * 32
MERGE = "1234abcd" + "0" * 32
LOG = "## Log\n2026-10-17T02:14:06Z {status} [{agent}]: filed\n{more}"


def ticket(tickets: Path, name: str, kind: str, title: str, body: str = "", more: str = ""):
    from handbook.paths import scripts_importable
    scripts_importable()
    status = "approved" if kind == "change" else "new"
    path = tickets / status / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nkind: {kind}\n---\n# {title}\n\n{body}"
                    + LOG.format(status=status, agent=name.rsplit("_", 1)[1], more=more))
    return script("ticket_reads").read_ticket(path)


def state(tmp_path: Path, tickets=(), commits=(), messages=(), session: str = "s"):
    from operations.journal import Journal
    from operations.state import (GitRead, HeldRead, SessionsRead, State, TrackerRead,
                                  TranscriptsRead)
    return State(
        me="op", now=1000.0, session=session, started=0.0, transcripts_dir=tmp_path,
        main_tree=tmp_path, scratch=tmp_path, operators=("op",),
        open_operators=frozenset(), past_bound=False, open_holders=frozenset(),
        session_holders=frozenset(), tracker=TrackerRead({t.number: t for t in tickets}, (), 9),
        transcripts=TranscriptsRead((), (), tuple(messages), {}, {}, {}, {}, {}, (), {}, {}),
        git=GitRead(tuple(commits), frozenset(), {}, {}, {}, frozenset(), {}, None, {}),
        taken_up=frozenset(), held=HeldRead({}, {}),
        sessions=SessionsRead(frozenset(), frozenset(), False, False, None),
        journal=Journal(()), listing=None)


@pytest.mark.parametrize(("texts", "own"), [((), True), (("Op scope: all.",), False),
                                             (("Op scope: all.", "Op scope: own."), True)])
def test_the_scope_is_own_unless_the_last_scope_line_gives_all(
        tmp_path: Path, texts: tuple[str, ...], own: bool) -> None:
    from operations.directives import own_scope
    from operations.state import Message
    messages = [Message("op", float(i), None, text) for i, text in enumerate(texts, 1)]
    assert own_scope(state(tmp_path, messages=messages)) is own


def test_own_work_follows_the_line_of_work_and_its_judged_tickets(tmp_path: Path) -> None:
    from operations.state import Commit
    from operations.taking import follow_ups, own_work
    tickets = tmp_path / "tickets"
    given = [
        ticket(tickets, "9-1_change_x-need_coordinator", "request", "x: a need"),
        ticket(tickets, "9-2_change_x-fix_ticket-analyst", "change", "x: the fix",
               "## Motivation\n- Serves 9-1.\n\n## Scope\n- `src/operations/taking.py`\n\n"),
        ticket(tickets, "9-3_change_9-2_code-editor", "question", "`taking.py`: which?"),
        ticket(tickets, "9-4_change_9-2_operator", "performance", "9-2: over budget"),
        ticket(tickets, "9-5_agent_a0000000000000001_code-reviewer", "bug",
               "`src/operations/taking.py`: wrong",
               more="2026-10-17T04:00:00Z new [ticket-analyst]: own: 9-2 made it wrong\n"),
        ticket(tickets, "9-6_agent_a0000000000000002_code-reviewer", "bug", "an agent's run: slow"),
        ticket(tickets, "9-7_change_y-hotfix_coordinator", "request", "y: a hotfix",
               more=f"2026-10-17T03:00:00Z new [coordinator]: merged at {HASH[:8]}; settles 9-7\n"),
        ticket(tickets, f"9-8_commit_{HASH}_code-reviewer", "refactor",
               "`scripts/hotfixed.py`: many ideas in one place"),
        ticket(tickets, "9-9_change_x-bug-fix_ticket-analyst", "change", "x: the bug's fix",
               "## Motivation\n- Serves 9-5.\n\n## Scope\n- `scripts/further.py`\n\n"),
        ticket(tickets, "9-10_agent_a0000000000000003_code-reviewer", "bug",
               "`scripts/further.py`: wrong"),
    ]
    commits = [Commit(HASH, 0.0, frozenset(), "y", False, frozenset({"scripts/hotfixed.py"})),
               Commit(MERGE, 0.0, frozenset(), "x: the fix", False,
                      frozenset({"src/operations/taking.py"}))]
    s = state(tmp_path, given, commits)
    assert own_work(s) == {"9-1", "9-2", "9-3", "9-5", "9-7", "9-9"}
    assert follow_ups(s) == {"9-8"}


TITLES = ["`src/operations/taking.py`: wrong", "operations.taking: wrong", "taking.py is slow",
          "pretaking.py", "the tests are slow", "`tests/test_own_work.py`: flaky",
          "`README.md`: stale", "README.mdx", "dependents.py: x", "`scripts/dependents.py`: x",
          "scripts.dependents: x"]
PATHS = ["src/operations/taking.py", "README.md", "scripts/dependents.py",
         "src/operations/__init__.py"]


def test_an_analyst_before_a_not_own_judgment_settles_the_ticket_only_outside_the_scope(
        tmp_path: Path) -> None:
    """An analyst that ran on a ticket before a `not own:` line on it
    counts as given the ticket while the scope leaves the ticket out, and
    no longer once `Op scope: all.` admits it."""
    from dataclasses import replace
    from datetime import datetime
    from operations.roles import Purpose, Role, analyst_subject
    from operations.state import Agent, Computed, Message
    from operations.triage import unsettled_open
    tickets = tmp_path / "tickets"
    given = [ticket(tickets, "9-3_agent_a0000000000000002_code-reviewer", "bug", "x: slow",
                    more="2026-10-17T04:00:00Z new [ticket-analyst]: not own: no change of the line\n")]
    launched = datetime.fromisoformat("2026-10-17T03:00:00+00:00").timestamp()
    analyst = Agent("a0000000000000009", "op", Role.TICKET_ANALYST,
                    analyst_subject(Purpose.TRIAGE, "9-3"), "", launched, launched, None, (), True)

    def at(messages: tuple = ()):
        s = state(tmp_path, given, messages=messages)
        return replace(s, transcripts=replace(s.transcripts, agents=(analyst,)),
                       computed=Computed(to_settle=("9-3",)))

    assert unsettled_open(at()) == []
    assert unsettled_open(at((Message("op", 1.0, None, "Op scope: all."),))) == ["9-3"]


@pytest.mark.parametrize("title", TITLES)
def test_referring_judges_as_names_does_a_title_with_no_form_after_a_slash_or_dot(
        title: str) -> None:
    from ticketing.references import Referring, names
    for path in PATHS:
        assert Referring([path])(title) is names(title, path)
    assert Referring(PATHS)(title) is any(names(title, p) for p in PATHS)


def test_a_bare_module_name_refers_to_no_file() -> None:
    from ticketing.references import Referring, names
    title = "scripts/bottlenecks.py, `--help`: \"wait\" and \"wait span\" name two different spans"
    assert names(title, "scripts/spans.py")
    assert not Referring(["scripts/spans.py"])(title)


@pytest.mark.parametrize(("title", "path", "refers"), [
    ("`src/cli/run.py`: wrong", "src/gating/run.py", False),
    ("`src/parity/__init__.py`: wrong", "src/gating/__init__.py", False),
    ("run.py: wrong", "src/gating/run.py", True),
    ("`src/gating/run.py`: wrong", "src/gating/run.py", True),
    ("`src/gating/__init__.py`: wrong", "src/gating/__init__.py", True),
])
def test_a_form_after_a_slash_or_dot_is_another_file(title: str, path: str, refers: bool) -> None:
    from ticketing.references import Referring
    assert Referring([path])(title) is refers


def test_a_change_touches_the_files_its_merging_commit_changed(tmp_path: Path) -> None:
    from operations.state import Commit
    from operations.taking import touched
    tickets = tmp_path / "tickets"
    given = [
        ticket(tickets, "9-1_change_x-fix_ticket-analyst", "change", "x: the fix",
               "## Scope\n- `src/operations/taking.py`\n\n"),
        ticket(tickets, "9-2_change_x-other_ticket-analyst", "change", "x: unmerged",
               "## Scope\n- `src/operations/state.py`\n\n"),
    ]
    commits = [Commit(MERGE, 0.0, frozenset(), "x: the fix", False,
                      frozenset({"src/ticketing/references.py"}))]
    s = state(tmp_path, given, commits)
    assert touched(s, {"9-1"}) == {"src/ticketing/references.py"}
    assert touched(s, {"9-2"}) == frozenset()


def test_a_value_kept_across_reads_is_computed_again_when_its_part_changes() -> None:
    from operations.state import kept_across_reads
    count = kept_across_reads(len)
    assert count("9-1", ("a",)) == 1
    assert count("9-1", ("a", "b")) == 2
    assert count("9-2", ("a",)) == 1

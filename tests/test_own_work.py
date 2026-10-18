"""The operators' scope is the session's line of work where no `Op scope:`
line came or the last one gives `own`: the coordinator's requests and
changes, the changes filed for them, the questions on those changes, and
the tickets whose title refers to a path such a change's Scope gives or
a file of a commit a request's log gives, with the changes filed for
those tickets, whose paths admit no further ticket; a title refers to a
file's path under the one pattern as `names` judges it."""

from pathlib import Path

import pytest

from tests.conftest import script

HASH = "abcdef12" + "0" * 32
LOG = "## Log\n2026-10-17T02:14:06Z open [{agent}]: filed\n{more}"


def ticket(tickets: Path, name: str, kind: str, title: str, body: str = "", more: str = ""):
    from handbook.paths import scripts_importable
    scripts_importable()
    path = tickets / "open" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nkind: {kind}\n---\n# {title}\n\n{body}"
                    + LOG.format(agent=name.rsplit("_", 1)[1], more=more))
    return script("ticket_reads").read_ticket(path)


def state(tmp_path: Path, tickets=(), commits=(), messages=()):
    from operations.journal import Journal
    from operations.state import (GitRead, HeldRead, SessionsRead, State, TrackerRead,
                                  TranscriptsRead)
    return State(
        me="op", now=1000.0, session="s", started=0.0, transcripts_dir=tmp_path,
        main_tree=tmp_path, scratch=tmp_path, operators=("op",),
        open_operators=frozenset(), past_bound=False, open_holders=frozenset(),
        session_holders=frozenset(), tracker=TrackerRead({t.number: t for t in tickets}, (), 9),
        transcripts=TranscriptsRead((), (), tuple(messages), {}, {}, {}, {}, {}, (), {}, {}),
        git=GitRead(tuple(commits), frozenset(), {}, {}, {}, frozenset(), {}, None, {}),
        taken_up=frozenset(), held=HeldRead({}, {}),
        sessions=SessionsRead(frozenset(), frozenset(), frozenset(), False, False, None),
        journal=Journal(()), listing=None)


@pytest.mark.parametrize(("texts", "own"), [((), True), (("Op scope: all.",), False),
                                             (("Op scope: all.", "Op scope: own."), True)])
def test_the_scope_is_own_unless_the_last_scope_line_gives_all(
        tmp_path: Path, texts: tuple[str, ...], own: bool) -> None:
    from operations.directives import own_scope
    from operations.state import Message
    messages = [Message("op", float(i), None, text) for i, text in enumerate(texts, 1)]
    assert own_scope(state(tmp_path, messages=messages)) is own


def test_own_work_follows_the_line_of_work_and_the_paths_it_touched(tmp_path: Path) -> None:
    from operations.state import Commit
    from operations.taking import own_work
    tickets = tmp_path / "tickets"
    given = [
        ticket(tickets, "9-1_change_x-need_coordinator", "request", "x: a need"),
        ticket(tickets, "9-2_change_x-fix_ticket-analyst", "change", "x: the fix",
               "## Motivation\n- Serves 9-1.\n\n## Scope\n- `src/operations/taking.py`\n\n"),
        ticket(tickets, "9-3_change_9-2_code-editor", "question", "`taking.py`: which?"),
        ticket(tickets, "9-4_change_9-2_operator", "performance", "9-2: over budget"),
        ticket(tickets, "9-5_agent_a0000000000000001_code-reviewer", "bug",
               "`src/operations/taking.py`: wrong"),
        ticket(tickets, "9-6_agent_a0000000000000002_code-reviewer", "bug", "an agent's run: slow"),
        ticket(tickets, "9-7_change_y-hotfix_coordinator", "request", "y: a hotfix",
               more=f"2026-10-17T03:00:00Z open [coordinator]: merged at {HASH[:8]}; settles 9-7\n"),
        ticket(tickets, f"9-8_commit_{HASH}_code-reviewer", "refactor",
               "`scripts/hotfixed.py`: many ideas in one place"),
        ticket(tickets, "9-9_change_x-bug-fix_ticket-analyst", "change", "x: the bug's fix",
               "## Motivation\n- Serves 9-5.\n\n## Scope\n- `scripts/further.py`\n\n"),
        ticket(tickets, "9-10_agent_a0000000000000003_code-reviewer", "bug",
               "`scripts/further.py`: wrong"),
    ]
    commits = [Commit(HASH, 0.0, frozenset(), "y", False, frozenset({"scripts/hotfixed.py"}))]
    assert own_work(state(tmp_path, given, commits)) == {
        "9-1", "9-2", "9-3", "9-5", "9-7", "9-8", "9-9"}


TITLES = ["`src/operations/taking.py`: wrong", "operations.taking: wrong", "taking.py is slow",
          "pretaking.py", "the tests are slow", "`tests/test_own_work.py`: flaky",
          "`README.md`: stale", "README.mdx", "dependents: x", "`scripts/dependents.py`: x"]
PATHS = ["src/operations/taking.py", "README.md", "scripts/dependents.py",
         "src/operations/__init__.py"]


@pytest.mark.parametrize("title", TITLES)
def test_the_pattern_judges_a_file_path_as_names_does(title: str) -> None:
    from ticketing.references import names, referring
    for path in PATHS:
        assert (referring([path]).search(title) is not None) is names(title, path)
    assert (referring(PATHS).search(title) is not None) is any(names(title, p) for p in PATHS)


def test_a_directory_is_referred_to_by_a_path_under_it() -> None:
    from ticketing.references import referring
    pattern = referring(["tests/"])
    assert pattern.search("`tests/test_own_work.py`: flaky") is not None
    assert pattern.search("the tests are slow") is None
    assert pattern.search("`src/tests/x.py`: y") is None

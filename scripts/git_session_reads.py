"""The reads of git and of the sessions that `state_assembly` assembles
the operator's state from: the read of git and of the main tree, the read
of the idle sessions, the lines earlier operators of the session gave in
their final replies, and the time an agent started."""

from pathlib import Path

from agent_turns import first_time
from idle_sessions import main_wanted, read_sessions, take_main, want_main
from relay_reads import run_index
from run_reads import parent_id
from transcripts import find
from transcript_entries import Refused
from tree_reads import baseline, claims, commits, doc_reviews, restores, solvers, worktrees

from controlled_markdown import mctx
from engine.checkout import agents_of
from operations.final_reply import final_sends_in, hands_over, sent_final_text
from operations.state import Call, GitRead, Review, SessionsRead


def read_git(main: Path) -> GitRead:
    """The read of git and of the main tree `main`."""
    trees = worktrees(main)
    return GitRead(commits(main), frozenset(trees),
                   {w: b for w, b in trees.items() if b is not None}, claims(main), restores(main),
                   solvers(main),
                   {r: baseline(main, r) for r in Review}, doc_reviews(main),
                   {d.stem: d.stat().st_mtime for d in sorted(agents_of(main).glob("*.md"))})


def sessions(tickets: Path, index: int, session: str, now: float,
             sessions_running: frozenset[str] | None) -> SessionsRead:
    """The read of `idle_sessions`. The read after `take_main` reads again,
    so that the session adopts the idle indexes at once, and `want_main`
    lets one session ask the user to pick a main (`triage.main_wanted`)."""
    read = read_sessions(tickets, index, session, now)
    if not read.main:
        take_main(tickets, session, sessions_running)
        read = read_sessions(tickets, index, session, now)
    if read.idle and not read.main and not read.main_live:
        want_main(tickets, session)
    return SessionsRead(read.idle, read.adopted, read.fixed_for, read.main, read.main_live, main_wanted(tickets))


def given_lines(runs: list[tuple[str, Path]], me: str, calls: list[Call]) -> set[str]:
    """The lines of each final reply that an operator of `runs` before `me`
    sent its parent, other than one that hands its lines over
    (`hands_over`): a line one of them gave reaches the coordinator in no
    later reply."""
    out: set[str] = set()
    for aid, path in runs[:run_index(runs, me)]:
        for c in final_sends_in(calls, aid, parent_id(path)):
            text = sent_final_text(c)
            if text is not None and not hands_over(text):
                out.update(text.split("\n"))
    return out


def started(aid: str) -> float:
    t = first_time(find(aid))
    if t is None:
        raise Refused(mctx("the transcript of {agent} gives no time").format(agent=aid))
    return t

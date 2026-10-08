"""After a batch: once every agent of a batch has returned, the release of
tickets, a code review where the batch merged a change to the code, and two
agents launched for the rest, one on the profile of the batch's runs and
one, where the batch merged a change, on the gate's timings and outputs.

A batch is the agents the loop launched since the launch of the previous
batch's profile agent, other than the agents of After a batch, with the
changes merged since: those the loop's merge call merged, as `state.Merge` reads it, and those the coordinator gives as
merged. The launch of the
profile agent opens the next batch. The ticket analyst on the tickets the
batch filed is the one `triage` launches on any open ticket."""

import re

from controlled_markdown import mctx
from operations import briefs
from operations.changes import release
from operations.directives import Directive, numbers
from operations.roles import AGENT_ID, Role
from operations.state import Agent, Merge, State
from operations.steps import Bash, Launch, Step, Undecided, bash_calls

OWN = frozenset({Role.BATCH_PROFILE, Role.BATCH_GATE, Role.CODE_REVIEWER})
"""The roles of After a batch, which no batch holds."""


def start(state: State) -> float:
    profiles = state.agents_of(Role.BATCH_PROFILE)
    return profiles[-1].launched if profiles else 0.0


def members(state: State, since: float) -> list[Agent]:
    return [a for a in state.agents if a.launched > since and a.role not in OWN]


def merged(state: State, since: float) -> bool:
    return (any(c.time > since and c.merge is Merge.MERGED for c in state.calls)
            or any(t > since for _, t in numbers(state, Directive.MERGED)))


def step(state: State) -> Step | None:
    since = start(state)
    batch = members(state, since)
    merges = merged(state, since)
    if not batch and not merges:
        return None
    if any(a.pending for a in batch):
        return None
    if (s := release(state)) is not None:
        return s
    if merges and any(c.code and c.time > since for c in state.commits):
        reviewers = [a for a in state.agents_of(Role.CODE_REVIEWER) if a.launched > since]
        if not reviewers:
            if state.code_review is None:
                return Undecided("no `code-review/<n>` tag gives the last code review's baseline")
            return Launch(Role.CODE_REVIEWER, f"code-review/{state.code_review + 1}",
                          briefs.code_review(state.code_review, state.scratch / "code-review"))
        if reviewers[-1].pending:
            return None
    n = len(state.agents_of(Role.BATCH_PROFILE)) + 1
    head = state.commits[0].hash
    if merges and not any(a.launched > since for a in state.agents_of(Role.BATCH_GATE)):
        return Launch(Role.BATCH_GATE, str(n), briefs.batch_gate(state.scratch / f"batch-{n}"))
    command = under_command(state.session)
    calls = [c for c in bash_calls(state, command) if c.time > since and c.result is not None
             and TAKEN.search(c.result) is not None]
    if not calls:
        return Bash(command)
    if calls[-1].error:
        return Undecided(mctx("`{command}` failed").format(command=command))
    runs = taken(calls[-1].result or "")
    if runs is None:
        return Undecided(mctx("the output of `{command}` gives no run lines in the form "
                              "`profile_runs.py --help` gives").format(command=command))
    return Launch(Role.BATCH_PROFILE, str(n), briefs.batch_profile(runs, head))


def under_command(session: str) -> str:
    """Step 1 of After a batch, on the runs under the session: the previous
    call of `--under` that `profile_runs.py --help` defines is the loop's,
    from its record. A call whose output holds no `runs taken:` line counts
    as none, and the step is given again."""
    return f"uv run python scripts/profile_runs.py --under {session}"


RUN = re.compile(AGENT_ID)
RUNS_TAKEN = "runs taken:"
"""The opening of the line of `profile_runs.py --under` that counts the
runs it takes."""

TAKEN = re.compile(rf"^{re.escape(RUNS_TAKEN)} (\d+)$", re.MULTILINE)


def taken(output: str) -> list[str] | None:
    """The agent ids of the runs a call of `--under` took: the first word
    of each of the N run lines that follow its `runs taken: N` line, each
    run's line followed by its indented `wall` line. None where the output
    holds no such line, or fewer run lines than N, or a run line that opens
    with no agent id."""
    m = TAKEN.search(output)
    if m is None:
        return None
    heads = [line for line in output[m.end():].splitlines()[1:]
             if line and not line[0].isspace()][:int(m[1])]
    ids = [line.split(" ", 1)[0] for line in heads]
    if len(ids) < int(m[1]) or not all(RUN.fullmatch(i) for i in ids):
        return None
    return ids

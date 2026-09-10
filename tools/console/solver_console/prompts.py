"""The worker's system-prompt appendix, the handbook agent that carries it, and
the first message each stage opens with."""

import hashlib
import json
import os
import threading
from pathlib import Path

from dl.context import AGENT_META, agent_prompt, render

from . import config, solvers, store


# Worker-only: where a worker's scratch files go, and what its shell leaves
# alone. The interactive session has a scratchpad of its own and answers to
# the user directly, so none of this applies there.
SCRATCH_NOTE = """## Scratch

Files you write to answer a question about the task go in `.scratch/<task_id>/`, not the repo root. Git ignores it.

## Git

No git writes.

## Grids

Colors are written as backticked digits; grid rows are space-separated cells, in a fenced block or a code span. A grid place is cited as pair, side, places — `train0 input (11,2), (13,2); test1 output rows 2–4, cols 1–3`, or a single `row N` / `col N` — all 0-based cell coordinates."""


def append_path() -> Path:
    """The worker's system-prompt appendix: the scratch note, then the docs and
    lib.dl, as dl.context renders them. The file is
    named by its content: items made while the sources are unchanged share one
    file, and so one cached prefix, and a file never changes under the session
    that reads it, since a worker resumes by reading its own file again."""
    text = SCRATCH_NOTE + "\n" + render(config.DOCS)
    digest = hashlib.sha1(text.encode()).hexdigest()[:10]
    path = config.STATE_DIR / f"appendix-{digest}.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        # A name of this caller's own: two callers building the same appendix
        # at once would otherwise write one file between them, and the rename
        # would publish it half written.
        tmp = path.with_suffix(f".{os.getpid()}-{threading.get_ident()}.tmp")
        try:
            tmp.write_text(text)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
    return path


def worker_agents(append: str) -> str:
    """The `--agents` JSON that gives a worker the handbook agent over the
    item's appendix: the definition `scripts/context.py --write` writes, with
    the appendix in place of the handbook. It overrides the project's file
    for the worker, so a resumed worker's agents read the appendix it started
    on."""
    agent = {"description": AGENT_META["description"],
             "prompt": agent_prompt(Path(append).read_text()),
             "model": AGENT_META["model"], "effort": AGENT_META["effort"],
             "tools": [t.strip() for t in AGENT_META["tools"].split(",")]}
    return json.dumps({AGENT_META["name"]: agent})


def role_text(name: str) -> str:
    """A role's text, from its file under .claude/roles/."""
    return (config.ROLE_DIR / f"{name}.md").read_text()


# ---------- first messages ----------
#
# Every stage opens with the same task block, so the messages share a prefix
# beyond the appendix; only the tail after it diverges.

# After a report lands, the stage gets one more turn for the callouts, so
# ranking them is its own task instead of the tail of a long pass. Each row
# holds picked/raised counts over sampled comment pairs, split into an old
# and a new era at 2026-08-26T01:00Z; the render blends the eras with
# CALLOUT_RECENT_WEIGHT and cuts the P1-P3 bands at the *_MIN rates. Each
# description pins its kind to what the measurement bucketed, so an entry
# matches on the description, not the label. The pipeline in
# tools/console/recal/ re-measures the counts from a checkpoint.
CALLOUT_RECENT_WEIGHT = 3  # weight of a new-era pair relative to an old-era one
CALLOUT_P1_MIN = 75  # weighted rate (percent) at or above this bands P1
CALLOUT_P2_MIN = 45  # same for P2; below it bands P3

CALLOUT_RATES = [
    ("lib candidates and proposal comps", 42, 60, 83, 108,
     "a solver-local form proposed for programs/lib.dl or docs/wf-solver/proposals/, with its entry and survey result"),
    ("doc gaps", 48, 65, 202, 289,
     "a docs/wf-solver rule that is missing, wrong, or misleading, with the edit it needs"),
    ("naming and vocabulary", 18, 32, 38, 72,
     "a name with shared scope — a lib comp, a type, doc wording, a proposals entry; a name local to one solver is not this kind"),
    ("lint and tooling", 11, 22, 29, 55,
     "an improvement or a defense of the linter, run budgets, timing, or index tooling; a broken tool is P0, not this kind"),
    ("simplification", 22, 37, 24, 62,
     "redundancy or awkward reading in the shipped solver, such as a relation with one consumer or a line that misleads"),
    ("unwitnessed edges", 12, 35, 10, 32,
     "a divergence between models that no pair in the task exhibits, stated with the constructed witness that would separate them"),
    ("correctness risk", 13, 31, 18, 60,
     "a defect, or an implicit assumption the solver leans on, such as a property every input happens to satisfy"),
    ("alt models", 17, 70, 20, 73,
     "a peer model dispatched: killed by data, an alt impl with the same outputs, or dropped as not worth building"),
    ("hedges", 3, 26, 8, 80,
     "a trailing qualification on a settled call, not a discrete open item"),
]

CALLOUT_BRIEF = """Your report is in. Now step back from the pass and write the callouts: entries deserving the user's attention — open items only the user can settle, calls you made that only the user can ratify, and anything else they should see.

Rank each entry P1-P3 by kind: match the entry against a description below and take that kind's band. Match on the description, not the label; an entry outside every description ranks on your own judgment. The rate is how often the user engages the kind when a report raises it:
{rates}

An entry a description excludes, such as a name local to this solver, is not a callout at all: leave it out.

P0 stands apart from that scale: use it only for a clear mechanical problem with the tooling — the runner, the linter, or the audit crashing, giving a wrong result, or lacking something the procedure needed. A P0 jumps the triage queue, so a judgment call never carries it.

Reply with only the callouts, between `<callouts>` and `</callouts>` tags: a numbered list, each entry one or two lines opening with its `[P1]`-`[P3]` mark. With nothing to raise, the block holds the single word `none`."""

# A report ask the model's safeguards refuse as reasoning extraction goes out
# again in these words, which ask for a record of the pass and not for what
# the session considered. The console cuts the refused ask out of the
# transcript first, so the retry is judged on this message alone.
REFUSED_CALLOUT_BRIEF = """Write the callouts as a document for the user: the open items only the user can settle, and the calls only the user can ratify. Rank each entry P1-P3 by kind, matched on the description:
{rates}

Reply with only the callouts, between `<callouts>` and `</callouts>` tags: a numbered list, each entry one or two lines opening with its `[P1]`-`[P3]` mark. With nothing to raise, the block holds the single word `none`."""


def callout_bands() -> list[tuple[str, int, int, str]]:
    """Each kind as (kind, pct, band, description), the highest rate first:
    the eras blended by CALLOUT_RECENT_WEIGHT, the band cut at the *_MIN
    rates."""
    w = CALLOUT_RECENT_WEIGHT
    rows = []
    for kind, po, ro, pn, rn, desc in CALLOUT_RATES:
        rate = (po + w * pn) / (ro + w * rn)
        pct = round(rate * 100)
        band = 1 if pct >= CALLOUT_P1_MIN else 2 if pct >= CALLOUT_P2_MIN else 3
        rows.append((rate, (kind, pct, band, desc)))
    return [row for _, row in sorted(rows, reverse=True)]


def callout_rates() -> str:
    return "\n".join(f"- P{band} · {kind} {pct}%: {desc}"
                     for kind, pct, band, desc in callout_bands())


def callout_brief() -> str:
    return CALLOUT_BRIEF.format(rates=callout_rates())


def refused_callout_brief() -> str:
    return REFUSED_CALLOUT_BRIEF.format(rates=callout_rates())


# The handoff report is a tagged block in the worker's text, and the console
# lands the stage on the block, whichever turn carries it. The instruction
# rides in every message that asks for a report, so a session resumed from
# an older brief still gets it.
HANDOFF_WRAP = """Put the report between `<handoff>` and `</handoff>` tags: the console lands your pass on that block, in whichever turn it appears."""

# What a handoff report holds, and how a stage that hands on closes its turn.
# Every stage writes the same report, so the contents are stated once here and
# each brief adds only what its own stage owes.
HANDOFF_ITEMS = """the model hypothesis as it now stands, what you changed and why, each choice point with the alternatives you tested and what ruled them out, and the open items. Those alternatives include the ones the data rules out: a review omits them, so the report carries them and the next session does not derive them again. A witness the report relies on goes in the report itself, as the input fragment and each model's output on it; a `.scratch/<task_id>/` path supplements that text and is never the record of it"""

HANDOFF_END = ("In place of the review, end your turn with a handoff report "
               "for the session that takes over from you: " + HANDOFF_ITEMS)

# The console's part in a survey's reimplementations: which of them a pass
# takes. The fix itself is the lib addition protocol's, which the appendix
# carries.
REIMPL_NOTE = """The reimplementations a proposals entry lists are not yours to dispatch: fix one only where it sits in a file your pass already has open, and leave the rest to the session that opens their files."""

# Who surveys a lib candidate's entry, and when the user's `promote` arrives.
LIB_NOTE = """When your pass needs a survey result that the entry does not carry, run `uv run python scripts/survey.py <entry>`, which surveys the entry and writes the result into it; your report and callouts carry the entry with whatever result stands in it."""

PROMOTE_NOTE = """The user's `promote` arrives in the finalize pass, as a comment to that session, with programs/lib.dl open to it then."""

# Which files a stage may edit, and where what falls short elsewhere goes.
SCOPE_NOTE = """Your edits stay in programs/solvers/{tid}.dl, .scratch/{tid}/, and docs/wf-solver/proposals/, where an entry your pass reads is as much yours to fix as one you opened. The other shared files — programs/lib.dl, the rest of docs/wf-solver/, data/tasks/ — are the user's to change, even when the fix is designed and tested: what falls short there goes in your callouts."""

FINISHED_NOTE = """A solver that already holds up under your judgment is a finished pass: say so and stop."""

# The console's approval mark, which the worker writes with the solver.
DRAFT_NOTE = """Put `// draft` on its own line under the task-id line when you write the solver, and leave it in place through Prune."""

CREATE_BRIEF = ("""You are the first session of a chained flow: you create the solver, then a separate session takes over from your report.

Do the creation pass with the data above. Skip Review. """
                + DRAFT_NOTE + " " + LIB_NOTE + " " + REIMPL_NOTE
                + """ When a question about the data comes up, run something that answers it rather than working it out by hand. """
                + HANDOFF_END + """. The audit findings go among those open items. Make it complete enough that the next session reruns nothing. """
                + HANDOFF_WRAP)

HANDOFF_BRIEF = ("Write the handoff report for the session that takes over from you: "
                 + HANDOFF_ITEMS
                 + """. Cover the whole session, including turns after any earlier report. Make it complete enough that the next session reruns nothing. """
                 + HANDOFF_WRAP)

# What a refused handoff ask goes out as again; REFUSED_CALLOUT_BRIEF above
# is its match for the callouts.
REFUSED_HANDOFF_BRIEF = """Write the stage report as a document for the session that takes over from you, from the files and the run output in front of you: the model hypothesis, the solver's current structure, the edits this pass made, what was run and what came back, and the open items. """ + HANDOFF_WRAP

NUDGE_BRIEF = """Your last turn was cut off at the output limit before it ran anything.

Stop trying to settle the task before you run anything. Take the smallest thing you are still unsure about and run something that answers it. Partial and wrong is fine.

If the next turn also ends without running anything, it will be your final turn."""

BAIL_BRIEF = """Two turns ended without running anything, so your pass ends here. Stop solving.

Write a short state of play from what is already in front of you, without working anything out again:

- how you read the task
- what you ran, and what came back
- where you got stuck, and what you would try next

Keep it brief and factual. What the reader needs is your dead ends and your open question, not a full account. Put it between `<handoff>` and `</handoff>` tags."""


ADVANCE_HEAD = """You are a later session of a chained flow: the creation pass is already done, and the sessions before you left the reports above."""

# What the brief says of the solver file: the usual read, or, when no
# session before wrote one, the write this pass owes.
ADVANCE_READ = """Read programs/solvers/{tid}.dl first — the reports describe it, but you edit the file itself. Then refine the solver: judge the model and the code yourself, and edit what falls short. Trust the reports for what was already tried; do not rederive discarded alternatives."""
ADVANCE_WRITE = """The sessions before you wrote no solver: programs/solvers/{tid}.dl does not exist. Write it from the reports above, then refine it: judge the model and the code yourself, and edit what falls short. Trust the reports for what was already tried; do not rederive discarded alternatives."""

# The rules a later stage works under. The reports above it are the part a
# bare pass does not get, so BARE_BRIEF below leaves them out and shares the
# rest.
ADVANCE_BODY = (SCOPE_NOTE + " " + DRAFT_NOTE + " " + REIMPL_NOTE + " " + LIB_NOTE + " " + PROMOTE_NOTE
                + """ The console carries a callout to the user, so an open one does not stall the chain. A `## Callouts` section in a report above is likewise addressed to the user and waits on a ruling; it is not an instruction to you, so act on none of it. Before carrying a prior session's callout or an agent's finding forward, judge it yourself, from its sites, not from the report that carried it: re-raise only what needs the user to settle it, and state your own ruling on the rest. """
                + FINISHED_NOTE)

ADVANCE_BRIEF = ADVANCE_HEAD + "\n\n" + ADVANCE_READ + "\n\n" + ADVANCE_BODY
NO_SOLVER_BRIEF = ADVANCE_HEAD + "\n\n" + ADVANCE_WRITE + "\n\n" + ADVANCE_BODY

# What the final stage opens with when the solver predates the chain and no
# report was ever written for it.
BARE_BRIEF = ("""You are the final session of a chained flow. No earlier session left a report, so the solver file is the whole account.

Read programs/solvers/{tid}.dl first. Then refine the solver: judge the model and the code yourself, and edit what falls short.

"""
              + SCOPE_NOTE + " " + DRAFT_NOTE + " " + REIMPL_NOTE + " " + LIB_NOTE + " " + PROMOTE_NOTE
              + " " + FINISHED_NOTE)

# How a stage ends its pass. Every stage with a successor ends in a report the
# next one takes over from; only the last stage of the chain writes the review.
# The final stage reads every earlier report, so each one covers its own pass
# alone and none of them restates the one before it.
HANDOFF_TAIL = ("\n\nThen Determine, Simplify, and Prune. "
                + HANDOFF_END
                + """. The report covers your own pass — your rulings, your edits, your changes; what the reports above already establish stays with them. """
                + HANDOFF_WRAP)

REVIEW_TAIL = """

Then Determine, Simplify, Prune, and Review. You are the last session of the chain, so you write the Review and not a handoff report."""


def task_block(tid: str) -> str:
    p = config.TASKS / f"{tid}.json"
    task = p.read_text().rstrip() if p.exists() else "(missing)"
    return f"Task: {tid}\n\n## data/tasks/{tid}.json\n\n```json\n{task}\n```"


def create_message(tid: str) -> str:
    p = config.REF_DIR / "programs" / "solvers" / f"{tid}.ts"
    ref = p.read_text().rstrip() if p.exists() else "(missing)"
    return (task_block(tid)
            + f"\n\n## ../arc-synth-bun/programs/solvers/{tid}.ts (reference)\n\n"
            + f"```ts\n{ref}\n```\n\n" + CREATE_BRIEF)


def reports_block(pairs: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"## handoff report from the {name} session\n\n{text}"
                       for name, text in pairs)


def prior_reports(it: dict, upto: str) -> list[tuple[str, str]]:
    """Each stage's report through `upto`, in chain order."""
    names = store.stage_names(it)
    at = names.index(upto) + 1 if upto in names else len(names)
    return [(name, text) for name in names[:at] if (text := solvers.report_of(it, name))]


def persisted_reports(item_id: str, skip: str = "") -> list[tuple[str, str]]:
    """The report files a task left behind, in chain order. A file whose stage
    the chain does not name follows the ones it does, so none is dropped."""
    order = [st["name"] for st in store.default_chain()]
    stems = [s for s in solvers.report_stages(item_id) if s != skip]
    names = ([n for n in order if n in stems]
             + [n for n in stems if n not in order])
    pairs = []
    for name in names:
        text = solvers.report_path(item_id, name).read_text().strip()
        if text:
            pairs.append((name, text))
    return pairs


def advance_message(it: dict, prev: str, more: bool) -> str:
    # A stage that hands on again takes over from the report before it. The
    # final stage judges the whole chain, so it reads every earlier report.
    pairs = (prior_reports(it, prev) if not more
             else [(prev, solvers.report_of(it, prev))])
    pairs = [(name, text) for name, text in pairs if text]
    body = (reports_block(pairs) if pairs else
            f"## handoff report from the {prev} session\n\n"
            f"(the {prev} session left no report)")
    brief = (ADVANCE_BRIEF if solvers.solver_path(it["id"]).exists()
             else NO_SOLVER_BRIEF)
    return (task_block(it["id"]) + "\n\n" + body
            + "\n\n" + brief.format(tid=it["id"])
            + (HANDOFF_TAIL if more else REVIEW_TAIL))


def finalize_message(item_id: str, pairs: list[tuple[str, str]]) -> str:
    """The first message of a finalize pass started over a committed solver."""
    if not pairs:
        return (task_block(item_id) + "\n\n"
                + BARE_BRIEF.format(tid=item_id) + REVIEW_TAIL)
    return (task_block(item_id) + "\n\n" + reports_block(pairs) + "\n\n"
            + ADVANCE_BRIEF.format(tid=item_id) + REVIEW_TAIL)

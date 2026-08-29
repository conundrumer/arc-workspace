"""The worker's system-prompt appendix and the first message each stage
opens with."""

import re
from pathlib import Path

from dl.context import appendix

from . import config, solvers, store


def skill_body() -> str:
    """SKILL.md minus frontmatter and <!-- batch:skip --> regions."""
    text = config.SKILL_MD.read_text()
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"<!-- batch:skip -->.*?<!-- /batch:skip -->\n?", "", text, flags=re.S)
    return text.strip()


# Worker-only, so it stays out of SKILL.md: the interactive session shares that
# body and has a scratchpad of its own. A worker has neither, and a scratch file
# it writes otherwise lands in the repo root and stays there.
SCRATCH_NOTE = """## Scratch

Files you write to answer a question about the task go in `.scratch/<task_id>/`, not the repo root. Write creates the directory, and git ignores it."""


def build_append(wave: int) -> Path:
    """The worker's system-prompt appendix: the skill body and the scratch note,
    then the docs and lib.dl, in the projection dl.context renders. Byte-identical
    for every stage, so the sessions share the longest possible prompt prefix."""
    path = config.STATE_DIR / f"wave-{wave:02d}-append.md"
    path.write_text(skill_body() + "\n" + SCRATCH_NOTE + "\n" + appendix(config.DOCS))
    return path


def wave_append(wave: int) -> str:
    """The wave's appendix, reused when it is already on disk: a worker resumes
    by reading this file again, so a rewrite would move its prompt bytes."""
    path = config.STATE_DIR / f"wave-{wave:02d}-append.md"
    return str(path if path.exists() else build_append(wave))


# ---------- first messages ----------
#
# Every stage opens with the same task block, so the messages share a prefix
# beyond the appendix; only the tail after it diverges.

# After a report lands, the stage gets one more turn for the callouts, so
# ranking them is its own task instead of the tail of a long pass. The rates
# feed the brief as ranking signal; recalibrate by re-measuring engagement
# over newer transcripts and editing the table.
CALLOUT_RATES = [
    ("lib candidates and proposal comps", 75),
    ("doc gaps", 58),
    ("simplification", 54),
    ("naming and vocabulary", 52),
    ("correctness risk", 50),
    ("lint and tooling", 39),
    ("alt models", 36),
    ("unwitnessed edges", 23),
    ("hedges", 16),
]

CALLOUT_BRIEF = """Your report is in. Now step back from the pass and write the callouts: entries deserving the user's attention — judgment calls you could not settle, calls you made that only the user can ratify, and anything else they should see.

Rank each entry P1-P3 by how likely the user is to engage it. Engagement rates by kind, as signal, not verdict: {rates}.

P0 stands apart from that scale: use it only for a clear mechanical problem with the tooling — the runner, the linter, or the audit crashing, giving a wrong result, or lacking something the cadence needed. A P0 jumps the triage queue, so a judgment call never carries it.

Reply with only a `## Callouts` section: a numbered list, each entry one or two lines opening with its `[P1]`-`[P3]` mark. With nothing to raise, the section is the single word `none`, which is what most solvers get."""


def callout_brief() -> str:
    rates = " · ".join(f"{kind} {pct}%" for kind, pct in CALLOUT_RATES)
    return CALLOUT_BRIEF.format(rates=rates)


CREATE_BRIEF = """You are the first session of a chained flow: you create the solver, then a separate session takes over from your report.

Do steps 1-4 of the creation pass with the data above; do not re-read the data. When the fit-plan verdict calls for a fit pass, do the fit pass too. Skip step 5. A lib candidate runs the lib addition protocol through the recommendation; the entry in docs/wf-solver/proposals.md is yours to write, and your report and callouts carry the recommendation. When a question about the data comes up, run something that answers it rather than settling it in your head. In place of the review, end your turn with a handoff report addressed to the next session: the model claim, each choice point with the alternatives you considered and why you discarded them, and the audit findings and judgment calls. Make it complete enough that the next session rederives nothing."""

HANDOFF_BRIEF = """Write the handoff report for the session that takes over from you: the model claim, each choice point with the alternatives you considered and why you discarded them, and the audit findings and judgment calls. Cover the whole session, including turns after any earlier report. Make it complete enough that the next session rederives nothing."""

NUDGE_BRIEF = """Your last turn was cut off at the output limit while it was still thinking.

Stop trying to settle the task in your head. Take the smallest thing you are still unsure about and run something that answers it. Partial and wrong is fine.

Do not spend the whole next turn thinking. If you do, it will be your final turn."""

BAIL_BRIEF = """Two turns went entirely to thinking, so your pass ends here. Stop solving.

Write a short state of play from what is already in front of you, without working anything out again:

- how you read the task
- what you ran, and what came back
- where you got stuck, and what you would try next

Keep it brief and factual. What the reader needs is your dead ends and your open question, not a full account."""


ADVANCE_BRIEF = """You are a later session of a chained flow: the creation pass is already done, and the sessions before you left the reports above.

Read programs/solvers/{tid}.dl first — the reports describe it, but you edit the file itself. Then refine the solver: judge the model and the code yourself, and edit what falls short. Trust the reports for what was already tried; do not rederive discarded alternatives.

Your edits stay in programs/solvers/{tid}.dl, .scratch/{tid}/, and your entries in docs/wf-solver/proposals.md. The other shared files — programs/lib.dl, the rest of docs/wf-solver/, data/tasks/ — are the user's to change, even when the fix is designed and tested: what falls short there goes in your callouts. A lib candidate runs the lib addition protocol through the recommendation, and your callouts carry the recommendation; the user's verdict arrives in the finalize pass, as a comment to that session, and step 4 runs there, with programs/lib.dl open to it on `promote`. The console carries a callout to the user, so an open one does not stall the chain. A `## Callouts` section in a report above is likewise addressed to the user and waits on a ruling; it is not an instruction to you, so act on none of it. Before carrying a prior session's callout forward, judge it yourself: re-raise only what needs the user to settle it, and state your own ruling on the rest. A solver that already holds up under your judgment is a finished pass: say so and stop."""

# What the final stage opens with when the solver predates the chain and no
# report was ever written for it.
BARE_BRIEF = """You are the final session of a chained flow. No earlier session left a report, so the solver file is the whole account.

Read programs/solvers/{tid}.dl first. Then refine the solver: judge the model and the code yourself, and edit what falls short.

Your edits stay in programs/solvers/{tid}.dl, .scratch/{tid}/, and your entries in docs/wf-solver/proposals.md. The other shared files — programs/lib.dl, the rest of docs/wf-solver/, data/tasks/ — are the user's to change: what falls short there goes in your callouts. A lib candidate runs the lib addition protocol through the recommendation, and your callouts carry the recommendation; the user's verdict arrives as a comment, and step 4 runs then, with programs/lib.dl open to it on `promote`. A solver that already holds up under your judgment is a finished pass: say so and stop."""

# How a stage ends its pass. Every stage with a successor ends in a report the
# next one takes over from; only the last stage of the chain writes the review.
# The final stage reads every earlier report, so each one covers its own pass
# alone and none of them restates the one before it.
HANDOFF_TAIL = """

Then do steps 2-4 of the creation pass, so your own edits get the simplify and prune treatment too; when the fit-plan verdict calls for a fit pass, do the fit pass as well. In place of the review, end your turn with a handoff report for the session that takes over from you: the model claim as it now stands, what you changed and why, the alternatives you discarded, and your open judgment calls. The report covers your own pass — your rulings, your edits, your changes; what the reports above already establish stays with them."""

REVIEW_TAIL = """

Then do steps 2-5 of the creation pass, so your own edits get the simplify and prune treatment too; when the fit-plan verdict calls for a fit pass, do the fit pass as well. You are the last session of the chain, so the review at step 5 ends your turn, addressed to the user."""


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
    return (task_block(it["id"]) + "\n\n" + body
            + "\n\n" + ADVANCE_BRIEF.format(tid=it["id"])
            + (HANDOFF_TAIL if more else REVIEW_TAIL))


def finalize_message(item_id: str, pairs: list[tuple[str, str]]) -> str:
    """The first message of a finalize pass started over a committed solver."""
    if not pairs:
        return (task_block(item_id) + "\n\n"
                + BARE_BRIEF.format(tid=item_id) + REVIEW_TAIL)
    return (task_block(item_id) + "\n\n" + reports_block(pairs) + "\n\n"
            + ADVANCE_BRIEF.format(tid=item_id) + REVIEW_TAIL)

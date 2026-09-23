"""What the console sends a worker, rendered from the documents that hold it.

A message is a section of `prompts/console.md`, rendered with the values its
variables read; a role is a document under `prompts/roles/`. This module also
writes the system-prompt appendix a worker reads and the agent files the
handbook agents run under.
"""

import hashlib
import json
import os
import threading
from pathlib import Path

import controlled_markdown as nm
from dl.context import (
    AGENT_NAMES,
    AGENT_PATH,
    agent_meta,
    agent_prompt,
    render,
    sweep_digests,
    write_agent,
)

from . import config, solvers, store

# ---------- the documents ----------


def documents(path: Path) -> tuple[nm.Registry, nm.Node]:
    """A registry over `path` and the document it holds. The file is read per
    call, so a message takes the text as it stands on disk."""
    reg = nm.Registry(config.ROOT)
    return reg, reg.load(path)


def message(name: str, **values) -> str:
    """One section of the console document as the text a worker reads: the
    section inlined, with its variables taking the values given here."""
    reg, document = documents(config.PROMPTS)
    section = reg.ids[document.source][name]
    body = nm.Node(nm.DOCUMENT, source=document.source)
    body.children = list(section.children)
    return nm.brief(body, reg, values).strip()


# ---------- the system-prompt appendix ----------


def scratch_note() -> str:
    """Worker-only: where a worker's scratch files go, and what its shell
    leaves alone."""
    return message("scratch-note")


def append_text(index: bool = False) -> str:
    """The worker's system-prompt appendix: the docs and the lib, as
    dl.context renders them, the lib as its interface, or under `index` as its
    index, then the scratch note."""
    return render(
        AGENT_NAMES[0] if index else AGENT_NAMES[1],
        agents=config.AGENTS) + "\n" + scratch_note()


def append_path(index: bool = False) -> Path:
    """The appendix `append_text` gives, as a file. The file is named by its
    content: items made while the sources are unchanged share one file, and so
    one cached prefix, and a file never changes under the session that reads
    it, since a worker resumes by reading its own file again. The build also
    keeps the handbook agents' files and the lib's interface files current, so
    a session started plainly spawns an agent over the same handbook."""
    text = append_text(index)
    digest = hashlib.sha1(text.encode()).hexdigest()[:10]
    path = config.STATE_DIR / f"appendix-{digest}.md"
    if path.exists():
        # The sweep dates a file by its mtime, and this caller takes the file
        # now, so its age starts again here. Without that, a build under
        # changed sources sweeps the file a caller is about to spawn on.
        try:
            os.utime(path)
        except OSError:
            pass
    else:
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
        sweep_digests(path)
    write_agent(AGENT_PATH, agents=config.AGENTS)
    return path


def worker_agents(append: str) -> str:
    """The `--agents` JSON that gives a worker both handbook agents, as
    `scripts/context.py --write` defines them, with an appendix in place of
    the handbook. `handbook-expanded` takes the item's appendix, so a resumed
    worker's agent reads the appendix it started on. `handbook` takes the
    index appendix as it stands. The JSON overrides the project's agent files
    for the worker."""
    def agent(meta: dict[str, str], text: str) -> dict:
        return {"description": meta["description"], "prompt": agent_prompt(text),
                "model": meta["model"],
                "tools": [t.strip() for t in meta["tools"].split(",")]}
    index, expanded = (agent_meta(name, config.AGENTS) for name in AGENT_NAMES)
    return json.dumps({
        index["name"]: agent(index, append_path(index=True).read_text()),
        expanded["name"]: agent(expanded, Path(append).read_text()),
    })


# ---------- roles ----------


def role(name: str) -> tuple[str, str]:
    """A role's agent and its text, from its document under prompts/roles/."""
    reg, document = documents(config.ROLE_DIR / f"{name}.md")
    return nm.role(document, reg)


def role_text(name: str) -> str:
    """A role's text alone, without the agent its `agent` attribute names."""
    return role(name)[1]


def survey_brief(entry: str, scope: str, scratch: str) -> str:
    """The brief of one survey of a lib proposals entry, which
    `scripts/survey.py` runs."""
    return message("survey", entry=entry, scope=scope, scratch=scratch)


# ---------- first messages ----------

# Each row holds a kind's key in the document and its picked/raised counts
# over sampled comment pairs, split into an old and a new era at
# 2026-08-26T01:00Z; the render blends the eras with CALLOUT_RECENT_WEIGHT and
# cuts the P1-P3 bands at the *_MIN rates. The pipeline in
# tools/console/recal/ re-measures the counts from a checkpoint. Each kind's
# rate and band reach the worker as `<key>-rate` and `<key>-band`, which the
# `callout-kinds` partial of prompts/console.md reads.
CALLOUT_RECENT_WEIGHT = 3  # weight of a new-era pair relative to an old-era one
CALLOUT_P1_MIN = 75  # weighted rate (percent) at or above this bands P1
CALLOUT_P2_MIN = 45  # same for P2; below it bands P3

CALLOUT_RATES = [
    ("lib-candidates", 42, 60, 83, 108),
    ("doc-issues", 48, 65, 202, 289),
    ("naming", 18, 32, 38, 72),
    ("lint-and-tooling", 11, 22, 29, 55),
    ("simplification", 22, 37, 24, 62),
    ("unwitnessed-divergences", 12, 35, 10, 32),
    ("correctness-risk", 13, 31, 18, 60),
    # ("peer-models", 17, 70, 20, 73),
    ("hedges", 3, 26, 8, 80),
]


def callout_bands() -> dict[str, int]:
    """Each kind's rate and band, under the `<key>-rate` and `<key>-band`
    names the document reads: the eras blended by CALLOUT_RECENT_WEIGHT, the
    band cut at the *_MIN rates."""
    w = CALLOUT_RECENT_WEIGHT
    out: dict[str, int] = {}
    for key, po, ro, pn, rn in CALLOUT_RATES:
        pct = round((po + w * pn) / (ro + w * rn) * 100)
        out[f"{key}-rate"] = pct
        out[f"{key}-band"] = (1 if pct >= CALLOUT_P1_MIN
                              else 2 if pct >= CALLOUT_P2_MIN else 3)
    return out


def callout_brief() -> str:
    return message("callout", **callout_bands())


def refused_callout_brief() -> str:
    return message("refused-callout", **callout_bands())


def handoff_brief() -> str:
    return message("handoff")


def refused_handoff_brief() -> str:
    return message("refused-handoff")


def nudge_brief() -> str:
    return message("nudge")


def bail_brief() -> str:
    return message("bail")


def task_text(tid: str) -> str:
    """The task's JSON under `config.TASKS`, or `(missing)` where no file
    stands."""
    p = config.TASKS / f"{tid}.json"
    return p.read_text().rstrip() if p.exists() else "(missing)"


def create_message(tid: str) -> str:
    return message("create", tid=tid, task=task_text(tid))


def reports_block(rows: list[tuple[str, str, str]]) -> str:
    """The prior stages as one value: each report in an element of its own,
    and each solver diff in another, so a session reads the console's account
    of the change apart from what the session before it wrote. A stage that
    changed nothing carries no diff element."""
    out = []
    for name, text, diff in rows:
        out.append(f'<handoff-report stage="{name}">\n{text}\n</handoff-report>')
        if diff:
            out.append(f'<solver-diff stage="{name}">\n{diff}\n</solver-diff>')
    return "\n\n".join(out)


def prior_reports(it: dict, upto: str) -> list[tuple[str, str, str]]:
    """Each stage's report and solver diff through `upto`, in chain order."""
    names = store.stage_names(it)
    at = names.index(upto) + 1 if upto in names else len(names)
    return [(name, text, solvers.diff_of(it, name))
            for name in names[:at] if (text := solvers.report_of(it, name))]


def persisted_reports(item_id: str, skip: str = "") -> list[tuple[str, str, str]]:
    """The report files a task left behind, each with the solver diff beside
    it, in chain order. A file whose stage the chain does not name follows the
    ones it does, so none is dropped."""
    order = [st["name"] for st in store.default_chain()]
    stems = [s for s in solvers.report_stages(item_id) if s != skip]
    names = ([n for n in order if n in stems]
             + [n for n in stems if n not in order])
    rows = []
    for name in names:
        text = solvers.report_path(item_id, name).read_text().strip()
        if text:
            dp = solvers.diff_path(item_id, name)
            rows.append((name, text, dp.read_text().strip() if dp.exists() else ""))
    return rows


def advance_message(it: dict, prev: str, more: bool) -> str:
    # A stage that hands on again takes over from the report before it. The
    # final stage judges the whole chain, so it reads every earlier report.
    pairs = (prior_reports(it, prev) if not more
             else [(prev, solvers.report_of(it, prev), solvers.diff_of(it, prev))])
    pairs = [row for row in pairs if row[1]]
    tid = it["id"]
    name = "advance" if solvers.solver_path(tid).exists() else "no-solver"
    return message(name, tid=tid, task=task_text(tid),
                   reports=reports_block(pairs), more="yes" if more else "")


def finalize_message(item_id: str, pairs: list[tuple[str, str, str]]) -> str:
    """The first message of a finalize pass started over a committed solver."""
    return message("finalize", tid=item_id, task=task_text(item_id),
                   reports=reports_block(pairs))

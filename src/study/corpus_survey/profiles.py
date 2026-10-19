"""The Runs, Box values and Idents sections: a few Souffle solvers chosen
as the extremes of the other sections, each run by `run_dl.py run` with
each Souffle call profiled by `souffle -p` and the run store bypassed, and
each call made a second time with an `.output` for every relation its
profile names."""

import itertools
import json
import re
import tempfile
import threading
from collections import Counter
from collections.abc import Iterator
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from cli.common import LIMITS
from controlled_markdown import mctx
from parity.snapshot import stored
from study.corpus_survey import kept
from study.corpus_survey.alts import cases
from study.corpus_survey.bodies import deep_atoms
from study.corpus_survey.corpus import corpus
from study.corpus_survey.forms import instances
from study.corpus_survey.section import Section, body, items, ran, table
from study.corpus_survey.shapes import joined, shaped

BOX = re.compile(r"\[(-?\d+), (-?\d+), (-?\d+), (-?\d+)\]")
FACT_RELATIONS = frozenset({"in", "ex_in", "ex_out"})
IDENT_COMPONENTS = frozenset({"Connectivity", "Quotient", "Enclosure"})
BOX_ARITHMETIC = frozenset({
    "compose", "relative", "jump", "jump_offset", "uniform_inset", "uniform_outset", "edge_inset", "edge_outset",
    "axis_inset", "axis_outset", "corner_inset", "corner_outset", "concat", "concat_slab", "concat_2d", "divide",
    "divide_slab", "divide_2d", "divide_by_size", "divide_by_size_slab", "divide_by_size_2d", "apply", "neighbor",
    "step_offset", "crop"})
CHOSEN = {"slowest": 6, "cases": 2, "atoms": 2, "cyclic": 2, "components": 1, "idents": 3, "box": 1}
"""How many solvers each extreme gives the runs."""
SHOWN = 9
"""The solvers the table gives a row each, the slowest first."""


def chosen() -> list[str]:
    """The solvers of the most CPU seconds in the snapshot, of the most
    cases, of the bodies of the most atoms, of the cyclic bodies of the
    most atoms, of the body of the most components, of the most Ident
    instances, and of the most box arithmetic atoms."""
    c = corpus()
    cpu = {s: r["cpu_seconds"] for s in c.stems if (r := stored(s)) is not None and "cpu_seconds" in r}
    n = cases()
    atoms = {}
    for b, s in shaped():
        atoms[b.stem] = max(atoms.get(b.stem, 0), s.atoms)
    cyc: dict[str, int] = {}
    comps: dict[str, int] = {}
    for b, j in joined():
        comps[b.stem] = max(comps.get(b.stem, 0), j.components)
        if not j.acyclic:
            cyc[b.stem] = max(cyc.get(b.stem, 0), j.pos_atoms)
    idents = Counter(s for s, comp, _ in instances() if comp in IDENT_COMPONENTS)
    box: Counter[str] = Counter()
    for b in c.bodies():
        box[b.stem] += sum(1 for a in deep_atoms(b.items) if str(a[0]) in BOX_ARITHMETIC)
    order: list[str] = []
    for measure, k in ((cpu, CHOSEN["slowest"]), (n, CHOSEN["cases"]), (atoms, CHOSEN["atoms"]), (cyc, CHOSEN["cyclic"]),
                       (comps, CHOSEN["components"]), (idents, CHOSEN["idents"]), (box, CHOSEN["box"])):
        order += sorted(measure, key=lambda s: (-measure[s], s))[:k]
    return list(dict.fromkeys(order))


def profiled(stem: str, out_dir: Path) -> None:
    """Runs `run_dl.py run <stem>` with each Souffle call profiled into
    `out_dir/<n>.json` and its rows dumped into `out_dir/dump/<n>.txt`."""
    import souffle.run as R
    from cli.main import main
    counter = itertools.count()
    lock = threading.Lock()
    local = threading.local()
    orig_flags, orig_process = R.Runner.flags, R.Runner._process

    def flags(self):
        prof = getattr(local, "profile", None)
        return orig_flags(self) + (["-p", str(prof)] if prof else [])

    def process(self, text, facts, cpu, wall):
        with lock:
            n = next(counter)
        out_dir.mkdir(parents=True, exist_ok=True)
        prof = local.profile = out_dir / f"{n}.json"
        done = orig_process(self, text, facts, cpu, wall)
        local.profile = None
        if prof.exists():
            try:
                rels = json.loads(prof.read_text())["root"]["program"]["relation"]
            except (ValueError, KeyError):
                return done
            extra = "".join(f"\n.output {r}" for r in rels if r != "in")
            again = orig_process(self, text + extra, facts, cpu, wall)
            (out_dir / "dump").mkdir(exist_ok=True)
            (out_dir / "dump" / f"{n}.txt").write_text(getattr(again, "stdout", ""))
        return done

    R.Runner.flags = flags  # type: ignore[method-assign]
    R.Runner._process = process  # type: ignore[method-assign]
    R.Runner._read = lambda self, key: None  # type: ignore[method-assign]
    R.Runner._write = lambda self, key, record: None  # type: ignore[method-assign]
    try:
        main(["run", stem])
    except SystemExit:
        pass
    finally:
        R.Runner.flags, R.Runner._process = orig_flags, orig_process  # type: ignore[method-assign]


def rules(rel: dict[str, Any]) -> Iterator[tuple[int, int, str]]:
    """(runtime µs, tuples, text) of each rule of one relation's profile."""
    for kind in ("non-recursive-rule", "recursive-rule"):
        for txt, v in rel.get(kind, {}).items():
            if "runtime" in v:
                yield v["runtime"]["end"] - v["runtime"]["start"], v.get("num-tuples", 0), txt
            else:
                yield (sum(x["runtime"]["end"] - x["runtime"]["start"] for x in v.values() if isinstance(x, dict) and "runtime" in x),
                       sum(x.get("num-tuples", 0) for x in v.values() if isinstance(x, dict)), txt)


def blocks(txt: str) -> Iterator[tuple[str, list[str], list[list[str]]]]:
    """The name, the header and the rows of each relation of a dump."""
    lines = txt.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].startswith("-----") and i + 3 < len(lines):
            name, header = lines[i + 1], lines[i + 2].split("\t")
            j = i + 4
            rows = []
            while j < len(lines) and not lines[j].startswith("====="):
                rows.append(lines[j].split("\t"))
                j += 1
            yield name, header, rows
            i = j + 1
        else:
            i += 1


def public(name: str) -> bool:
    """A relation none of whose path segments starts with `_`: no part
    internal to a lib component."""
    return not any(x.startswith("_") for x in name.split("."))


def summary(stem: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="corpus-survey-") as tmp:
        d = Path(tmp)
        profiled(stem, d)
        calls: list[int] = []
        rel: dict[str, list[Any]] = {"public": [0, ""], "internal": [0, ""]}
        rule: dict[str, list[Any]] = {"public": [0, 0, ""], "internal": [0, 0, ""]}
        for pf in sorted(d.glob("*.json")):
            try:
                p = json.loads(pf.read_text())["root"]["program"]
            except (ValueError, KeyError):
                continue
            calls.append(p["runtime"]["end"] - p["runtime"]["start"])
            for name, r in p["relation"].items():
                if name in FACT_RELATIONS:
                    continue
                side = "public" if public(name) else "internal"
                if r.get("num-tuples", 0) > rel[side][0]:
                    rel[side] = [r.get("num-tuples", 0), name]
                for t, tup, _ in rules(r):
                    if t > rule[side][0]:
                        rule[side] = [t, tup, name]
        hi: list[Any] = [0, ""]
        lo: list[Any] = [0, ""]
        idents: list[int] = []
        for df in sorted((d / "dump").glob("*.txt")):
            groups = 0
            for name, header, rows in blocks(df.read_text()):
                if name in FACT_RELATIONS:
                    continue
                for r in rows:
                    for m in BOX.finditer("\t".join(r)):
                        vals = [int(x) for x in m.groups()]
                        if max(vals) > hi[0]:
                            hi = [max(vals), f"{name} {m.group(0)}"]
                        if min(vals) < lo[0]:
                            lo = [min(vals), f"{name} {m.group(0)}"]
                if header and header[-1] == "id" and "_ident" not in name:
                    keep = [i for i, h in enumerate(header) if h not in ("p", "a")]
                    groups += len({tuple(r[i] for i in keep if i < len(r)) for r in rows})
            idents.append(groups)
    return {"calls": len(calls), "slowest_ms": max(calls, default=0) / 1000, "relation": rel, "rule": rule,
            "margin_max": hi, "margin_min": lo, "idents": max(idents, default=0)}


def kept_summary(stem: str) -> dict[str, Any]:
    return kept.kept("runs", kept.solver_key(stem), lambda: summary(stem))


def summaries() -> dict[str, dict[str, Any]]:
    stems = chosen()
    with Pool(1) as p:
        return dict(zip(stems, p.map(kept_summary, stems), strict=True))


def secs(ms: float) -> str:
    return f"{ms / 1000:.1f} s" if ms >= 1000 else f"{ms:.0f} ms"


def runs_section() -> str:
    got = summaries()
    order = sorted(got, key=lambda s: -got[s]["slowest_ms"])
    rows = [(s, got[s]["calls"], secs(got[s]["slowest_ms"]),
             f"`{got[s]['relation']['public'][1]}` {got[s]['relation']['public'][0]}",
             f"{secs(got[s]['rule']['public'][0] / 1000)}, `{got[s]['rule']['public'][2]}`, {got[s]['rule']['public'][1]} tuples")
            for s in order[:SHOWN]]
    rest = order[SHOWN:]
    if rest:
        rows.append((f"the other {len(rest)}", "", f"under {secs(got[rest[0]]['slowest_ms'])}",
                     f"at most {max(got[s]['relation']['public'][0] for s in rest)}", ""))
    internal = sorted(got, key=lambda s: -got[s]["relation"]["internal"][0])[:2]
    limit_ms = LIMITS.cpu_seconds * 1000
    over = [s for s in got if got[s]["slowest_ms"] > limit_ms]
    return body(
        mctx("The solvers: those of the most CPU seconds in the snapshot `.cache/parity/`, of the most cases, of the bodies and the cyclic bodies of the most atoms, of the body of the most components, of the most Ident instances and of the most box arithmetic, as the sections above give them. A Souffle solver holds every case in one relation, under its choice columns, so a relation's tuples bound the rows that one case's clause gives. A relation whose path has a segment that starts with `_` is internal to a lib component, which the engine builds natively; the others are public. A call's time is the profile's wall time, and `run_dl.py run` makes its Souffle calls in parallel, so the times include contention."),
        table(("stem", "calls", "slowest call", "largest public relation", "slowest public rule"), rows),
        items([
            mctx("The largest internal relations: {rels}.").format(
                rels=", ".join(f"{s} `{got[s]['relation']['internal'][1]}` {got[s]['relation']['internal'][0]}" for s in internal)),
            mctx("The tooling's limit per call is {cpu} s of CPU; the solvers whose slowest call passes it in wall time: {over}.")
            .format(cpu=LIMITS.cpu_seconds, over=", ".join(over) or "none"),
        ]),
        ran(f"profiled Souffle runs of the {len(got)} solvers above, of `programs/solvers/`"))


def box_values() -> str:
    got = summaries()
    hi = max(got, key=lambda s: got[s]["margin_max"][0])
    lo = min(got, key=lambda s: got[s]["margin_min"][0])
    return body(
        mctx("The values of the form `[t, b, l, r]` in every dumped row of the solvers of Runs, outside `in`, `ex_in` and `ex_out`. An intermediate value of an inline functor, such as `@box_compose` in a body, is in no relation, so this section does not see it."),
        items([mctx("The largest margin is {hi} ({hs} `{hw}`), and the smallest is {lo} ({ls} `{lw}`).")
               .format(hi=got[hi]["margin_max"][0], hs=hi, hw=got[hi]["margin_max"][1],
                       lo=got[lo]["margin_min"][0], ls=lo, lw=got[lo]["margin_min"][1])]),
        ran("the dumps of Runs"))


def idents() -> str:
    got = summaries()
    top = sorted(got, key=lambda s: -got[s]["idents"])[:4]
    return body(
        mctx("An Ident group is a distinct row of a relation whose last column is `id`, less its `p` or `a` column, outside `_ident`, summed over the relations of one call: the components, classes and enclosures that the call labels."),
        items([mctx("Per call, at most {most}.").format(most=", then ".join(f"{got[s]['idents']} ({s})" for s in top))]),
        ran("the dumps of Runs"))


RUNS = Section("Runs", 2, True, runs_section)
BOX_VALUES = Section("Box values", 3, True, box_values)
IDENTS = Section("Idents", 3, True, idents)

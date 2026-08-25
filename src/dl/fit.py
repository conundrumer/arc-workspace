"""Check a solver's Fit comp against its stored Consts fills."""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from arc.task import load as load_task
from dl.facts import _parse_relations, _parse_value, example_facts
from dl.fit_deps import Step, fit_cycles, render_cycles
from dl.paths import SOLVERS_DIR
from dl.souffle import _run_source
from dl.source import build_fit_source, fit_slots, rigid_decls


@dataclass
class FitResult:
    slots: list[str]        # fitted (Consts-mirrored) Fit relations
    diff: list[str]         # slots where fit and fill disagree
    # cycles in the fitted slots' reads of each other's stored fills
    circular: list[list[Step]] = field(default_factory=list)
    error: str | None = None


def run_fit(stem: str) -> FitResult | None:
    """Fit check for one solver; None when the file has no Fit comp."""
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    task = load_task(stem.split("_", 1)[0])
    return fit_check(source, task)


def fit_check(source: str, task) -> FitResult | None:
    """Fit check on solver source text; None when it has no Fit comp."""
    slots = fit_slots(source)
    if slots is None:
        return None
    circular = fit_cycles(source)
    try:
        with tempfile.TemporaryDirectory() as facts_dir:
            for name, text in example_facts(task).items():
                (Path(facts_dir) / name).write_text(text)
            # One process carries every example, so the per-grid CPU budget
            # scales by example count.
            stdout = _run_source(
                build_fit_source(source, slots), "", ["-F", facts_dir],
                cpu_limit=5 * (len(task.train) + len(task.test)),
            )
        rels = _parse_relations(stdout)
        diff = sorted({row.strip() for row in rels.get("fit_diff", [])})
        rigid = {n: b for n, (b, _) in rigid_decls(source).items() if n in slots}
        ident_slots = {n: t for n, t in slots.items() if "Ident" in t}
        if ident_slots and not _ident_match(ident_slots, rels, set(rigid)):
            diff.append("+".join(sorted(ident_slots)) + " (ids)")
        coupled = {n: b for n, b in rigid.items() if n not in ident_slots}
        diff += _rigid_match(coupled, rels)
        return FitResult(slots=sorted(slots), diff=diff, circular=circular)
    except Exception as e:
        return FitResult(
            slots=sorted(slots), diff=[], circular=circular,
            error=f"{type(e).__name__}: {e}",
        )


def _ident_match(
    slots: dict[str, list[str]], rels: dict[str, list[str]], rigid: set[str],
) -> bool:
    """Compare Ident-carrying slots modulo id renaming.

    A slot's Ident column is a join key shared across the solver's Ident
    slots, so each side reduces to a multiset of per-id signatures — the
    id's rows across all slots, id elided — and the sides must agree.

    A RIGID slot's ids are independent rigid assemblies, so its
    contribution to an id's signature is the id's orbit — the set of its
    placed row sets, pose labels elided — the same object from a chart in
    any pose.
    """
    def signatures(side: str):
        by_id: dict = {}
        for name, types in slots.items():
            idx = types.index("Ident")
            if name in rigid:
                poses: dict = {}
                for row in rels.get(f"{side}_rigid_{name}", []):
                    vals = [_parse_value(x) for x in row.split("\t")]
                    d, chart = vals[0], vals[1:]
                    rest = tuple(v for i, v in enumerate(chart) if i != idx)
                    poses.setdefault(chart[idx], {}).setdefault(d, set()).add(rest)
                for rid, orbit in poses.items():
                    canon = tuple(sorted({tuple(sorted(rows)) for rows in orbit.values()}))
                    by_id.setdefault(rid, []).append((name, canon))
                continue
            for row in rels.get(f"{side}_ident_{name}", []):
                vals = [_parse_value(x) for x in row.split("\t")]
                rest = tuple(v for i, v in enumerate(vals) if i != idx)
                by_id.setdefault(vals[idx], []).append((name, rest))
        return sorted(tuple(sorted(rows)) for rows in by_id.values())

    return signatures("fit") == signatures("c")


def _rigid_match(coupled: dict[str, str], rels: dict[str, list[str]]) -> list[str]:
    """Pose-quotiented compare of ident-free RIGID slots, jointly per
    block: the Fit's chart assembly must be some single D4 image of the
    stored one. Both sides relay placed, so each side reduces to its orbit
    — the set of joint row-set tuples over the block's relations, pose
    labels elided — and equal orbits mean exactly that."""
    by_block: dict[str, list[str]] = {}
    for name, block in coupled.items():
        by_block.setdefault(block, []).append(name)
    diffs = []
    for block, names in sorted(by_block.items()):
        names.sort()

        def orbit(side: str):
            poses: dict = {}
            for k, name in enumerate(names):
                for row in rels.get(f"{side}_rigid_{name}", []):
                    vals = [_parse_value(x) for x in row.split("\t")]
                    sig = poses.setdefault(vals[0], [set() for _ in names])
                    sig[k].add(tuple(vals[1:]))
            return {tuple(tuple(sorted(rs)) for rs in sig) for sig in poses.values()}

        if orbit("fit") != orbit("c"):
            diffs.append("+".join(names) + " (pose)")
    return diffs


def render_fit(fit: FitResult) -> list[str]:
    lines = render_cycles(fit.circular)
    if fit.error:
        return lines + [f"fit: ERROR {fit.error}"]
    if fit.diff:
        return lines + [f"fit: DIFF on {', '.join(fit.diff)}"]
    return lines + [f"fit: ok ({', '.join(fit.slots)})"]

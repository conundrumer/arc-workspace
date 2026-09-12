"""Check a solver's Determine comp against its stored parameter values."""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from arc.task import load as load_task
from dl.determine_deps import Step, determine_cycles, render_cycles
from dl.facts import _parse_relations, _parse_value, example_facts
from dl.paths import SOLVERS_DIR
from dl.souffle import _run_source
from dl.source import build_determine_source, determined_params, rigid_decls


@dataclass
class DetermineResult:
    params: list[str]       # determined (Params-mirrored) Determine relations
    diff: list[str]         # params where the determination and the value disagree
    # cycles in the determined params' reads of each other's stored values
    circular: list[list[Step]] = field(default_factory=list)
    error: str | None = None


def run_determine(stem: str) -> DetermineResult | None:
    """Determination check for one solver; None when the file has no
    Determine comp."""
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    task = load_task(stem.split("_", 1)[0])
    return determine_check(source, task)


def determine_check(source: str, task) -> DetermineResult | None:
    """Determination check on solver source text; None when it has no
    Determine comp."""
    try:
        params = determined_params(source)
    except ValueError as e:
        return DetermineResult(params=[], diff=[], error=str(e))
    if params is None:
        return None
    circular = determine_cycles(source)
    try:
        with tempfile.TemporaryDirectory() as facts_dir:
            for name, text in example_facts(task).items():
                (Path(facts_dir) / name).write_text(text)
            # One process carries every example, so the per-grid CPU budget
            # scales by example count.
            stdout = _run_source(
                build_determine_source(source, params), "", ["-F", facts_dir],
                cpu_limit=5 * (len(task.train) + len(task.test)),
            )
        rels = _parse_relations(stdout)
        diff = sorted({row.strip() for row in rels.get("_determination_diff", [])})
        rigid = {n: b for n, (b, _) in rigid_decls(source).items() if n in params}
        ident_params = {n: t for n, t in params.items() if "Ident" in t}
        if ident_params and not _ident_match(ident_params, rels, set(rigid)):
            diff.append("+".join(sorted(ident_params)) + " (ids)")
        coupled = {n: b for n, b in rigid.items() if n not in ident_params}
        diff += _rigid_match(coupled, rels)
        return DetermineResult(params=sorted(params), diff=diff, circular=circular)
    except Exception as e:
        return DetermineResult(
            params=sorted(params), diff=[], circular=circular,
            error=f"{type(e).__name__}: {e}",
        )


def _ident_match(
    params: dict[str, list[str]], rels: dict[str, list[str]], rigid: set[str],
) -> bool:
    """Compare Ident-carrying parameters modulo id renaming.

    A parameter's Ident column is a join key shared across the solver's Ident
    parameters, so each side reduces to a multiset of per-id signatures — the
    id's rows across all parameters, id elided — and the sides must agree.

    A RIGID parameter's ids are independent rigid assemblies, so its
    contribution to an id's signature is the id's orbit — the set of its
    placed row sets, pose labels elided — the same object from a chart in
    any pose.
    """
    def signatures(side: str):
        by_id: dict = {}
        for name, types in params.items():
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

    return signatures("determine") == signatures("params")


def _rigid_match(coupled: dict[str, str], rels: dict[str, list[str]]) -> list[str]:
    """Pose-quotiented compare of ident-free RIGID parameters, jointly per
    block: the determination's chart assembly must be some single D4 image of the
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

        if orbit("determine") != orbit("params"):
            diffs.append("+".join(names) + " (pose)")
    return diffs


def render_determine(determination: DetermineResult) -> list[str]:
    lines = render_cycles(determination.circular)
    if determination.error:
        return lines + [f"determination: ERROR {determination.error}"]
    if determination.diff:
        return lines + [f"determination: DIFF on {', '.join(determination.diff)}"]
    return lines + [f"determination: ok ({', '.join(determination.params)})"]

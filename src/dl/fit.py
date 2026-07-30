"""Check a solver's Fit comp against its stored Consts fills."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from arc.task import load as load_task
from dl.facts import _parse_relations, _parse_value, example_facts
from dl.paths import SOLVERS_DIR
from dl.souffle import _run_source
from dl.source import build_fit_source, comp_decls, fit_slots


@dataclass
class FitResult:
    slots: list[str]        # fitted (Consts-mirrored) Fit relations
    unfitted: list[str]     # Consts slots with no Fit mirror
    diff: list[str]         # slots where fit and fill disagree
    error: str | None = None


def run_fit(stem: str) -> FitResult | None:
    """Fit check for one solver; None when the file has no Fit comp."""
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    slots = fit_slots(source)
    if slots is None:
        return None
    unfitted = sorted(set(comp_decls(source, "Consts")) - set(slots))
    task = load_task(stem.split("_", 1)[0])
    try:
        with tempfile.TemporaryDirectory() as facts_dir:
            for name, text in example_facts(task).items():
                (Path(facts_dir) / name).write_text(text)
            stdout = _run_source(
                build_fit_source(source, slots), "", ["-F", facts_dir]
            )
        rels = _parse_relations(stdout)
        diff = sorted({row.strip() for row in rels.get("fit_diff", [])})
        ident_slots = {n: t for n, t in slots.items() if "Ident" in t}
        if ident_slots and not _ident_match(ident_slots, rels):
            diff.append("+".join(sorted(ident_slots)) + " (ids)")
        return FitResult(slots=sorted(slots), unfitted=unfitted, diff=diff)
    except Exception as e:
        return FitResult(
            slots=sorted(slots), unfitted=unfitted, diff=[],
            error=f"{type(e).__name__}: {e}",
        )


def _ident_match(slots: dict[str, list[str]], rels: dict[str, list[str]]) -> bool:
    """Compare Ident-carrying slots modulo id renaming.

    A slot's Ident column is a join key shared across the solver's Ident
    slots, so each side reduces to a multiset of per-id signatures — the
    id's rows across all slots, id elided — and the sides must agree.
    """
    def signatures(side: str):
        by_id: dict = {}
        for name, types in slots.items():
            idx = types.index("Ident")
            for row in rels.get(f"{side}_ident_{name}", []):
                vals = [_parse_value(x) for x in row.split("\t")]
                rest = tuple(v for i, v in enumerate(vals) if i != idx)
                by_id.setdefault(vals[idx], []).append((name, rest))
        return sorted(tuple(sorted(rows)) for rows in by_id.values())

    return signatures("fit") == signatures("c")


def render_fit(fit: FitResult) -> list[str]:
    if fit.error:
        lines = [f"fit: ERROR {fit.error}"]
    elif fit.diff:
        lines = [f"fit: DIFF on {', '.join(fit.diff)}"]
    else:
        lines = [f"fit: ok ({', '.join(fit.slots)})"]
    if fit.unfitted:
        lines.append(f"fit: unfitted slots: {', '.join(fit.unfitted)}")
    return lines

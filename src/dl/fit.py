"""Check a solver's Fit comp against its stored Consts fills."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from arc.task import load as load_task
from dl.facts import _parse_block, train_facts
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
            for name, text in train_facts(task).items():
                (Path(facts_dir) / name).write_text(text)
            stdout = _run_source(
                build_fit_source(source, slots), "", ["-F", facts_dir]
            )
        diff = sorted({row.strip() for row in _parse_block(stdout)})
        return FitResult(slots=sorted(slots), unfitted=unfitted, diff=diff)
    except Exception as e:
        return FitResult(
            slots=sorted(slots), unfitted=unfitted, diff=[],
            error=f"{type(e).__name__}: {e}",
        )


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

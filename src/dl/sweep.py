"""Conditional sweep of a solver's Consts fills: which values the pairs admit."""

import itertools
import re
from concurrent.futures import ThreadPoolExecutor

from arc.task import load as load_task
from dl.domains import (
    ENUM_TYPES,
    MAG_POSITION_TYPES,
    POSITION_TYPES,
    _color_domain,
    _enum_domain,
    _lib_defines,
    _number_domain,
    _position_domain,
)
from dl.paths import SOLVERS_DIR
from dl.solve import _profile
from dl.souffle import _pool_workers
from dl.source import (
    _comp_span,
    _render_arg,
    _slot_facts,
    _split_args,
    comp_decls,
    expand_grid_macros,
    swap_fact,
)


def sweep_report(
    stem: str, max_candidates: int = 64
) -> list[tuple[str, str, object]]:
    """Conditional sweep of each enumerable Consts slot.

    Sweeps one slot at a time with the others at their stored values; a
    candidate survives when it reproduces the stored fill's variant profile
    on every train pair. A slot's fill may be a set (a symmetric member
    stores every fitting value), so the check is survivors == stored facts.

    Survivors beyond the stored facts are re-run against the test pairs:
    a producer holding only the train pairs could pick any survivor, so an
    extra that fails test is a would-be wrong prediction, and one that
    passes is gauge for this task instance.

    Returns (slot, status, detail): status 'swept' carries
    (survivors, stored, types, verdicts) — verdicts maps each extra
    survivor to its test-pass bool — 'skip' carries the reason.
    """
    # GRID calls expand first, so a GRID-fed slot reads as ordinary facts;
    # re-expansion at build time is a no-op.
    source = expand_grid_macros((SOLVERS_DIR / f"{stem}.dl").read_text())
    task = load_task(stem.split("_", 1)[0])
    defines = _lib_defines()
    s, e = _comp_span(source, "Consts")
    consts_text = "\n".join(source.splitlines()[s:e])

    reference: list[frozenset[str]] | None = None
    test_reference: list[frozenset[str]] | None = None
    results: list[tuple[str, str, object]] = []
    for slot, types in comp_decls(source, "Consts").items():
        if re.search(rf"\b{slot}\s*\([^)]*\)\s*:-", consts_text):
            results.append((slot, "skip", "derived"))
            continue
        facts = _slot_facts(source, slot)
        if not facts:
            results.append((slot, "skip", "0 facts"))
            continue
        if not all(t in ENUM_TYPES or t in ("Color", "number")
                   or t in POSITION_TYPES for t in types):
            results.append((slot, "skip", f"non-enumerable ({', '.join(types)})"))
            continue

        stored = []
        for args in facts:
            vals = []
            for a, t in zip(args, types):
                if t in POSITION_TYPES:
                    vals.append(tuple(int(x) for x in _split_args(a[1:-1])))
                elif a.lstrip("-").isdigit():
                    vals.append(int(a))
                else:
                    vals.append(defines[a])
            stored.append(tuple(vals))

        domains = []
        for i, t in enumerate(types):
            if t in ENUM_TYPES:
                domains.append(_enum_domain(t, defines))
            elif t == "Color":
                domains.append(_color_domain(task))
            elif t == "number":
                domains.append(_number_domain(task))
            else:
                domains.append(
                    _position_domain(t, [s[i] for s in stored], _number_domain(task))
                )

        # Stored values join the candidate set, so a stored value outside
        # the domain (a count above the dims, say) still reads as stored
        # rather than as a holistic table.
        candidates = sorted(set(itertools.product(*domains)) | set(stored))
        if len(candidates) > max_candidates:
            results.append((slot, "skip", f"{len(candidates)} candidates"))
            continue

        if reference is None:
            reference = _profile(source, task.train)
            if reference is None:
                results.append((slot, "skip", "stored fill fails train"))
                continue

        def test(vals, slot=slot):
            profile = _profile(swap_fact(source, slot, vals), task.train)
            return vals if profile == reference else None

        with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
            survivors = [v for v in executor.map(test, candidates) if v]

        verdicts: dict[tuple, bool] = {}
        extras = sorted(set(survivors) - set(stored))
        if extras and set(stored) <= set(survivors):
            if test_reference is None:
                test_reference = _profile(source, task.test)
            if test_reference is None:
                verdicts = {e: False for e in extras}
            else:
                def test_check(vals, slot=slot):
                    profile = _profile(swap_fact(source, slot, vals), task.test)
                    return profile == test_reference

                with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
                    verdicts = dict(zip(extras, executor.map(test_check, extras)))
        results.append((slot, "swept", (survivors, stored, types, verdicts)))
    return results


def _mag_vec(vals: tuple, types: list[str]) -> list[int]:
    """Magnitude components of a value tuple: number args as-is, the
    absolute components of Shift/Inset args."""
    out: list[int] = []
    for v, t in zip(vals, types):
        if t == "number":
            out.append(v)
        elif t in MAG_POSITION_TYPES:
            out.extend(abs(x) for x in v)
    return out


def _num_peer(e: tuple, s: tuple, types: list[str]) -> bool:
    """e differs from s only in magnitude args — number, Shift, Inset — a
    rival magnitude, not a rival identity. Nominal args (enums, Color,
    Ident, cell Positions) must match."""
    mag = {"number"} | MAG_POSITION_TYPES
    return all(e[i] == s[i] for i, t in enumerate(types) if t not in mag)


def _num_below(e: tuple, s: tuple, types: list[str]) -> bool:
    """e is a smaller magnitude reading of s: nominal args equal, magnitude
    components no larger, at least one strictly smaller."""
    em, sm = _mag_vec(e, types), _mag_vec(s, types)
    return (_num_peer(e, s, types)
            and all(a <= b for a, b in zip(em, sm))
            and any(a < b for a, b in zip(em, sm)))


def render_sweep(results: list[tuple[str, str, object]]) -> list[str]:
    defines = _lib_defines()
    names = {v: k for k, v in defines.items()}

    def show(vals: tuple, types: list[str]) -> str:
        return "(" + ", ".join(
            names.get(v, str(v)) if t in ENUM_TYPES else _render_arg(v)
            for v, t in zip(vals, types)
        ) + ")"

    lines = []
    for slot, status, detail in results:
        if status == "skip":
            lines.append(f"{slot}: skipped — {detail}")
            continue
        survivors, stored, types, verdicts = detail
        vset, sset = set(survivors), set(stored)
        shown_s = ", ".join(show(v, types) for v in stored)
        if vset == sset:
            if len(sset) == 1:
                lines.append(f"{slot}: unique = {shown_s} ✓")
            else:
                lines.append(f"{slot}: set of {len(sset)} = [{shown_s}] ✓")
        elif sset <= vset:
            extras = sorted(vset - sset)
            shown_e = ", ".join(show(v, types) for v in extras)
            falsified = [e for e in extras if not verdicts.get(e, False)]
            if falsified:
                shown_f = ", ".join(show(v, types) for v in falsified)
                lines.append(
                    f"{slot}: TEST-FALSIFIED — train admits [{shown_f}] "
                    f"beyond stored [{shown_s}], test refutes"
                )
            elif not all(any(_num_peer(e, s, types) for s in sset)
                         for e in extras):
                lines.append(
                    f"{slot}: UNDERDETERMINED — beyond stored [{shown_s}]: [{shown_e}]"
                )
            elif any(_num_below(e, s, types) for e in extras for s in sset):
                below = sorted(
                    e for e in extras if any(_num_below(e, s, types) for s in sset)
                )
                shown_b = ", ".join(show(v, types) for v in below)
                lines.append(
                    f"{slot}: STORED NOT LEAST — smaller fitting: [{shown_b}]"
                )
            else:
                lines.append(f"{slot}: stored {shown_s} ✓ — gauge [{shown_e}]")
        else:
            # Some stored value no singleton run reproduces.
            lines.append(f"{slot}: holistic table — singleton sweep n/a")
    return lines

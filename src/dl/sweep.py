"""Conditional sweep of a solver's parameter values: which values the pairs admit."""

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
    RIGID_CHART_PREFIX,
    _comp_span,
    _param_facts,
    _render_arg,
    _split_args,
    comp_decls,
    expand_macros,
    public_param,
    swap_fact,
    swap_facts,
)


MAX_CANDIDATES = 256


def sweep_report(
    stem: str, max_candidates: int = MAX_CANDIDATES
) -> list[tuple[str, str, object]]:
    """Conditional sweep of each enumerable parameter.

    Sweeps one parameter at a time with the others at their stored values; an
    alternative value fits when it reproduces the stored value's variant
    profile on every train pair. A parameter's value may be a set (a symmetric
    member stores every fitting value), so the check is fitting == stored
    facts.

    Fitting values beyond the stored facts are re-run against the test
    pairs: a producer holding only the train pairs could pick any of them,
    so an extra that fails test is a would-be wrong prediction, and one
    that passes is gauge for this task instance.

    A parameter whose stored facts fail their singleton runs fits only as a
    set; it is re-swept whole (see _set_sweep), with candidate sets in
    place of candidate values.

    Returns (param, status, detail): status 'swept' carries
    (fitting, stored, types, verdicts) — verdicts maps each extra fitting
    value to its test-pass bool — 'swept-set' and 'swept-set-near' carry
    the same shape with frozensets of value tuples for fitting and verdict
    keys, and 'skip' carries the reason.
    """
    # Macros expand first, so a GRID-fed parameter reads as ordinary facts and
    # a RIGID chart as an ordinary generated-name parameter; re-expansion at
    # build time is a no-op. Chart parameters report under their public names, and
    # their derived placed forms are elided rather than reported.
    source = expand_macros((SOLVERS_DIR / f"{stem}.dl").read_text())
    task = load_task(stem.split("_", 1)[0])
    defines = _lib_defines()
    s, e = _comp_span(source, "Params")
    params_text = "\n".join(source.splitlines()[s:e])

    reference: list[frozenset[str]] | None = None
    test_reference: list[frozenset[str]] | None = None
    results: list[tuple[str, str, object]] = []
    params = comp_decls(source, "Params")
    placed = {public_param(n) for n in params if n.startswith(RIGID_CHART_PREFIX)}
    for param, types in params.items():
        if param in placed:
            continue
        if re.search(rf"\b{param}\s*\([^)]*\)\s*:-", params_text):
            results.append((public_param(param), "skip", "derived"))
            continue
        facts = _param_facts(source, param)
        if not facts:
            results.append((public_param(param), "skip", "0 facts"))
            continue
        if not all(t in ENUM_TYPES or t in ("Color", "number")
                   or t in POSITION_TYPES for t in types):
            results.append(
                (public_param(param), "skip", f"non-enumerable ({', '.join(types)})")
            )
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
            results.append(
                (public_param(param), "skip",
                 f"{len(candidates)} alternative values, cap {max_candidates}; "
                 f"rerun with run_dl.py sweep {stem} {len(candidates)}")
            )
            continue

        if reference is None:
            reference = _profile(source, task.train)
            if reference is None:
                results.append((public_param(param), "skip", "stored value fails train"))
                continue

        def test(vals, param=param):
            profile = _profile(swap_fact(source, param, vals), task.train)
            return vals if profile == reference else None

        with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
            fitting = [v for v in executor.map(test, candidates) if v]

        if not set(stored) <= set(fitting):
            results.append(_set_sweep(
                source, param, stored, types, candidates, task, reference,
                max_candidates))
            continue

        verdicts: dict[tuple, bool] = {}
        extras = sorted(set(fitting) - set(stored))
        if extras and set(stored) <= set(fitting):
            if test_reference is None:
                test_reference = _profile(source, task.test)
            if test_reference is None:
                verdicts = {e: False for e in extras}
            else:
                def test_check(vals, param=param):
                    profile = _profile(swap_fact(source, param, vals), task.test)
                    return profile == test_reference

                with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
                    verdicts = dict(zip(extras, executor.map(test_check, extras)))
        results.append((public_param(param), "swept", (fitting, stored, types, verdicts)))
    return results


def _neighborhood(stored: list[tuple], singles: list[tuple]) -> list[frozenset]:
    """The candidate sets one row-change from the stored facts.

    A change is a stored row reassigned to another candidate value, a stored
    row dropped, or a non-stored candidate added; the other rows keep their
    stored values. The stored facts are a candidate too, so the fitting sets
    read as in the whole sweep.
    """
    stored_set = frozenset(stored)
    sets = {stored_set}
    for row in stored_set:
        rest = stored_set - {row}
        sets.add(rest)
        for value in singles:
            sets.add(rest | {value})
    for value in singles:
        sets.add(stored_set | {value})
    return sorted((v for v in sets if v), key=sorted)


def _set_sweep(
    source: str,
    param: str,
    stored: list[tuple],
    types: list[str],
    singles: list[tuple],
    task,
    reference: list[frozenset[str]],
    max_candidates: int,
) -> tuple[str, str, object]:
    """Sweep a parameter whose facts fit only together, as one unit.

    Candidate values are the non-empty subsets of the singleton candidates;
    each replaces the whole parameter. Above the cap the subsets give way to
    the one-change neighborhood of the stored facts (see _neighborhood), and
    the status says so. Fitting and test-refutation read as in the singleton
    sweep, over sets.
    """
    name = public_param(param)
    n_sets = 2 ** len(singles) - 1
    if n_sets > max_candidates:
        status = "swept-set-near"
        subsets = _neighborhood(stored, singles)
    else:
        status = "swept-set"
        subsets = [
            frozenset(c)
            for r in range(1, len(singles) + 1)
            for c in itertools.combinations(singles, r)
        ]
    stored_set = frozenset(stored)

    def test(value):
        profile = _profile(swap_facts(source, param, sorted(value)), task.train)
        return value if profile == reference else None

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        fitting = [f for f in executor.map(test, subsets) if f]

    verdicts: dict[frozenset, bool] = {}
    extras = sorted(set(fitting) - {stored_set}, key=sorted)
    if extras and stored_set in fitting:
        test_reference = _profile(source, task.test)
        if test_reference is None:
            verdicts = {e: False for e in extras}
        else:
            def test_check(value):
                profile = _profile(
                    swap_facts(source, param, sorted(value)), task.test
                )
                return profile == test_reference

            with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
                verdicts = dict(zip(extras, executor.map(test_check, extras)))
    return (name, status, (fitting, stored, types, verdicts))


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
    peer magnitude, not a peer identity. Nominal args (enums, Color,
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
    for param, status, detail in results:
        if status == "skip":
            lines.append(f"{param}: not swept — {detail}")
            continue
        if status in ("swept-set", "swept-set-near"):
            fitting, stored, types, verdicts = detail
            stored_set = frozenset(stored)
            scope = ("swept whole" if status == "swept-set"
                     else "swept single-row changes")

            def show_value(value, types=types):
                return "{" + ", ".join(show(v, types) for v in sorted(value)) + "}"

            def show_values(values):
                return "[" + ", ".join(show_value(v) for v in values) + "]"

            shown_s = show_value(stored_set)
            if set(fitting) == {stored_set}:
                lines.append(
                    f"{param}: unique as a set = {shown_s} ✓ (facts fit only "
                    f"together; {scope})"
                )
                continue
            extras = sorted(set(fitting) - {stored_set}, key=sorted)
            refuted = [e for e in extras if not verdicts.get(e, False)]
            passing = [e for e in extras if verdicts.get(e, False)]
            parts = [
                f"stored {shown_s} ({scope})",
                f"train also admits sets {show_values(extras)}",
            ]
            if refuted:
                parts.append(
                    f"test refutes {show_values(refuted)} — a determination "
                    f"from train alone could pick it"
                )
            if passing:
                parts.append(
                    f"{show_values(passing)} reproduce the stored outputs on "
                    f"test too"
                )
            lines.append(f"{param}: " + "; ".join(parts))
            continue
        fitting, stored, types, verdicts = detail
        vset, sset = set(fitting), set(stored)
        def shown(vals, types=types):
            return ", ".join(show(v, types) for v in vals)

        shown_s = shown(stored)
        if vset == sset:
            if len(sset) == 1:
                lines.append(f"{param}: unique = {shown_s} ✓")
            else:
                lines.append(f"{param}: set of {len(sset)} = [{shown_s}] ✓")
            continue
        # Each finding about the extras gets its own clause, so a refuted
        # extra cannot hide a surviving one.
        extras = sorted(vset - sset)
        refuted = [e for e in extras if not verdicts.get(e, False)]
        passing = [e for e in extras if verdicts.get(e, False)]
        parts = [f"stored {shown_s}", f"train also admits [{shown(extras)}]"]
        if refuted:
            parts.append(
                f"test refutes [{shown(refuted)}] — a determination from "
                f"train alone could pick it"
            )
        if passing:
            parts.append(
                f"[{shown(passing)}] reproduce the stored outputs on test too"
            )
            kind = [e for e in passing
                    if not any(_num_peer(e, s, types) for s in sset)]
            if kind:
                parts.append(
                    f"[{shown(kind)}] differ from stored in kind, so the "
                    f"pairs do not fix this parameter"
                )
            below = sorted(
                e for e in passing if any(_num_below(e, s, types) for s in sset)
            )
            if below:
                parts.append(
                    f"[{shown(below)}] fit and are smaller than stored"
                )
        lines.append(f"{param}: " + "; ".join(parts))
    return lines

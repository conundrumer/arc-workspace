"""Drop one stored fact at a time: which facts of a multi-fact parameter the
pairs never need."""

import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from arc.task import load as load_task
from controlled_markdown import mctx
from dl.domains import ENUM_TYPES, POSITION_TYPES
from dl.solve import _profile, solver_file, solver_name
from dl.souffle import _pool_workers
from dl.source import (
    RIGID_CHART_PREFIX,
    _comp_span,
    _param_atoms,
    _param_facts,
    _params_fact_lines,
    _split_args,
    comp_decls,
    expand_macros,
    public_param,
)

# Where one stored fact sits: line index, the atom's span in that line's
# code, and the atom's text.
type Site = tuple[int, int, int, str]

# param, fact text, whether the test pairs survive the drop, notes
type Hit = tuple[str, str, bool, list[str]]

GROUND_NOTE = mctx("holds the picture's background color, so the cell draws "
                   "nothing wherever the picture is read")
SWEEP_NOTE = mctx("an enumerable parameter, so `sweep` can report the same "
                  "drop")


def _atom_sites(source: str, param: str) -> list[Site]:
    """Each Params fact atom of `param`, in source order."""
    lines = source.splitlines()
    sites = []
    for i in _params_fact_lines(source):
        code = lines[i].split("//")[0]
        for start, end, _ in _param_atoms(code, param):
            sites.append((i, start, end, code[start:end]))
    return sites


def _drop_site(source: str, site: Site) -> str:
    """The source with one fact atom cut out of its line.

    The cut is textual, so a parameter whose columns no domain enumerates —
    an Ident, a Grid — is reached as readily as an enumerable one.
    """
    lines = source.splitlines()
    i, start, end, _ = site
    code, sep, comment = lines[i].partition("//")
    lines[i] = code[:start] + code[end:] + sep + comment
    return "\n".join(lines) + "\n"


def _multi_fact_params(source: str) -> list[tuple[str, list[str], list[Site]]]:
    """Each Params parameter holding more than one stored fact, with its
    column types and its fact sites. Macro-expanded source, so a GRID cell
    and a RIGID chart row read as ordinary facts; a chart reports under its
    placed name, and a derived parameter stores nothing."""
    start, end = _comp_span(source, "Params")
    params_text = "\n".join(source.splitlines()[start:end])
    params = comp_decls(source, "Params")
    placed = {public_param(n) for n in params
              if n.startswith(RIGID_CHART_PREFIX)}
    out = []
    for param, types in params.items():
        if param in placed:
            continue
        if re.search(rf"\b{param}\s*\([^)]*\)\s*:-", params_text):
            continue
        sites = _atom_sites(source, param)
        if len(sites) > 1:
            out.append((param, types, sites))
    return out


def _enumerable(types: list[str]) -> bool:
    """The parameter's columns are the ones `sweep` enumerates."""
    return all(t in ENUM_TYPES or t in ("Color", "number")
               or t in POSITION_TYPES for t in types)


def _picture_key(types: list[str], args: list[str]) -> tuple[str, ...]:
    """Which picture of a relation one fact belongs to: the leading columns
    before the first Position, the ones a keyed GRID call passes through in
    front of the cell values. A relation with no such columns holds one
    picture, and every fact carries the same empty key."""
    lead = min(i for i, t in enumerate(types) if t in POSITION_TYPES)
    return tuple(args[:lead])


def _ground_values(source: str, types: list[str],
                   facts: list[list[str]]) -> dict[tuple[str, ...], set[str]]:
    """Per picture, the color arguments that read as ground: the solver's
    `bg` value, and the value most of that picture's cells carry.

    A picture stores a cell per position, so its ground token says that the
    picture leaves that cell alone. Dropping such a cell drops nothing
    drawn. A picture is its own frame, so the majority is taken per picture:
    a catalog holds several pictures under a leading key, and each names its
    own ground. A value holds the ground only with a majority of that
    picture's cells: a sparse picture omits its ground cells, so its
    commonest stored value is ink.
    """
    if not any(t in POSITION_TYPES for t in types):
        return {}
    color = [i for i, t in enumerate(types) if t == "Color"]
    if len(color) != 1:
        return {}
    bg = {v for args in _param_facts(source, "bg") for v in args}
    pictures: dict[tuple[str, ...], list[str]] = {}
    for args in facts:
        if len(args) == len(types):
            key = _picture_key(types, args)
            pictures.setdefault(key, []).append(args[color[0]])
    return {
        key: bg | {v for v, n in Counter(values).most_common(1)
                   if n * 2 > len(values)}
        for key, values in pictures.items()
    }


def _notes(types: list[str], args: list[str],
           grounds: dict[tuple[str, ...], set[str]]) -> list[str]:
    """The noise notes one dropped fact carries."""
    notes = []
    color = [i for i, t in enumerate(types) if t == "Color"]
    if grounds and len(color) == 1:
        ground = grounds.get(_picture_key(types, args), set())
        if args[color[0]] in ground:
            notes.append(GROUND_NOTE)
    if _enumerable(types):
        notes.append(SWEEP_NOTE)
    return notes


def drop_one_report(stem: str) -> tuple[list[Hit], int, int] | None:
    """The stored facts whose removal reproduces the reference profile.

    Each fact of each multi-fact parameter is cut on its own and the solver
    runs again over the train pairs. A fact whose removal holds the train
    profile is one the train pairs never need; the run repeats over the test
    pairs, so a fact the test pairs do need reports apart from one dead on
    both.

    Returns (hits, facts tested, parameters covered); None when the stored
    source fails the train pairs.
    """
    path, task_id = solver_file(stem)
    source = expand_macros(path.read_text())
    task = load_task(task_id)
    params = _multi_fact_params(source)
    if not params:
        return ([], 0, 0)
    reference = _profile(source, task.train)
    if reference is None:
        return None

    work: list[tuple[str, list[str], Site]] = [
        (param, types, site)
        for param, types, sites in params
        for site in sites
    ]

    def train_ok(item) -> bool:
        return _profile(_drop_site(source, item[2]), task.train,
                        reference) == reference

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        dead = [w for w, ok in zip(work, executor.map(train_ok, work)) if ok]

    test_ok: list[bool] = []
    if dead:
        test_reference = _profile(source, task.test)

        def holds(item) -> bool:
            return (test_reference is not None
                    and _profile(_drop_site(source, item[2]), task.test,
                                 test_reference) == test_reference)

        with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
            test_ok = list(executor.map(holds, dead))

    grounds = {
        param: _ground_values(source, types, _param_facts(source, param))
        for param, types, _ in params
    }
    hits: list[Hit] = []
    for (param, types, site), ok in zip(dead, test_ok):
        atoms = _param_atoms(f"{site[3]}.", param)
        args = _split_args(atoms[0][2]) if atoms else []
        hits.append((
            public_param(param),
            site[3].strip().rstrip("."),
            ok,
            _notes(types, args, grounds[param]),
        ))
    return (hits, len(work), len(params))


def render_drop_one(
    stem: str, report: tuple[list[Hit], int, int] | None
) -> list[str]:
    """The drop-one report, as printable lines."""
    if report is None:
        return [mctx("drop-one baseline fails: stored source does not pass train")]
    hits, tested, params = report
    if not tested:
        return [mctx("{solver}: no parameter holds more than one stored "
                     "fact").format(solver=solver_name(stem))]

    def entries(group: list[Hit]) -> list[str]:
        lines = []
        for _, text, _, notes in group:
            suffix = f"  — {'; '.join(notes)}" if notes else ""
            lines.append(f"  {text}{suffix}")
        return lines

    noun = "parameter" if params == 1 else "parameters"
    lines = [mctx("{tested} stored facts across {params} multi-fact "
                  "{noun}").format(tested=tested, params=params, noun=noun)]
    both = [h for h in hits if h[2]]
    train_only = [h for h in hits if not h[2]]
    if not hits:
        lines.append(mctx("every fact changes a train pair"))
        return lines
    if both:
        lines.append("")
        lines.append(mctx("{count} fact(s) no pair needs:")
                     .format(count=len(both)))
        lines += entries(both)
    if train_only:
        lines.append("")
        lines.append(
            mctx("{count} fact(s) the train pairs do not need, and the test "
                 "pairs do:").format(count=len(train_only)))
        lines += entries(train_only)
    return lines

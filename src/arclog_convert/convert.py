"""Convert the Souffle solvers under programs/solvers/ to arclog and arcdata
files under gen/, and, with the expansion config `libmap.macros`, under
gen_macros/, of `arclog_convert.out`: `work/arclog/` of the main
worktree, or the directory `--out` gives; in a linked worktree, `--out` is
required (or `ARCLOG_OUT`).

    uv run python -m arclog_convert.convert [--out <dir>] [--no-train-replay | --accept] [--no-row-parity] [<stem> ...]

Each run writes both outputs for the same solvers, every solver where no
stem is given, and prints the summary of each.
Then, once both outputs are written, it replays each case of the solvers
that `gen/` converted on the train pairs of its task, records the verdicts
under `train_replay/`, and reports against the baseline
`unreproduced.tsv`; the run exits with status 1 where the report finds a
case beyond the baseline or one that was `Consistent` and is not.
`--no-train-replay` skips it. `--accept` also rewrites the baseline lines
of the covered tasks to the run's counts, keeping the ticket field of each
line whose task and verdict stay: the lines it rewrites are those of the
solvers it converted, from the files it wrote; it is refused with
`--no-train-replay`. The replay runs `cargo` in `engine/`, so it
needs a Rust toolchain; `arclog_convert.train_replay` gives the details.
After the replay it compares each relation of those solvers with Souffle's rows,
records the lines under `row_parity/`, and reports against the baseline
`row_parity.tsv`; the run exits with status 1 where either report does.
`--no-row-parity` skips it. `--accept` also rewrites the lines of
`row_parity.tsv` of the solvers it converted, from the files it wrote, after
the check; with `--no-row-parity` it leaves `row_parity.tsv` untouched.
`arclog_convert.row_parity` gives the details.
A solver's plan file under plan/ records the hash of the solver
file it was written from, and the runner and lib stamp of the run; where it
is missing or records another hash or stamp, the script first reruns
`scripts/run_dl.py determination-plan <stem>`.
A form the script cannot translate is written literally, under a
`;; TODO <kind>: ...` comment.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from pathlib import Path
from engine.program import Qualifier, RelationName, Variable
from arclog_convert.libmap import rename as libmap_rename
from arclog_convert.libmap.instances import Placement
from arclog_convert import OUT_ENV, paths, writable_out

from arclog_convert.forms import (
    MERGES,
    MERGES_UNMERGED,
    Todo,
    fold_or_lines,
    hoist_shared,
    renamed,
)
from arclog_convert.clauses import Site, site_columns
from arclog_convert.leaves import Converter, FACTS, Written
from arclog_convert.lib import Col, ColMismatch, LIB_DL, Lib, SIGNATURE
from arclog_convert.solver import Solver


PLAN_HASH = "solver file sha256: "


def solver_hash(stem: str) -> str:
    return hashlib.sha256((paths.SOLVERS / f"{stem}.dl").read_bytes()).hexdigest()


def stale_plans(stems: list[str]) -> list[str]:
    """The solvers whose plan file is missing, or records a hash other than
    their solver file's, or a runner and lib stamp other than the current
    one."""
    from cli.common import stamp
    lib_line = f"runner and lib: {stamp()}"
    out = []
    for stem in stems:
        p = paths.PLANS / f"{stem}.txt"
        lines = p.read_text().splitlines() if p.exists() else []
        if PLAN_HASH + solver_hash(stem) not in lines or lib_line not in lines:
            out.append(stem)
    return out


def write_plan(stem: str) -> str | None:
    """Run the determination plan of one solver and write its output, with
    the solver file's hash, to its plan file; None, or the error."""
    digest = solver_hash(stem)
    r = subprocess.run([sys.executable, str(paths.ROOT / "scripts" / "run_dl.py"), "determination-plan", stem],
                       cwd=paths.ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        lines = (r.stderr or r.stdout).strip().splitlines()
        return lines[-1] if lines else f"exit {r.returncode}"
    text = r.stdout + r.stderr
    paths.PLANS.mkdir(parents=True, exist_ok=True)
    (paths.PLANS / f"{stem}.txt").write_text(text + ("" if text.endswith("\n") else "\n") + PLAN_HASH + digest + "\n")
    return None


def refresh_plans(stems: list[str]) -> None:
    stale = stale_plans(stems)
    if not stale:
        return
    print(f"rerunning the determination plan of {len(stale)} solvers")
    with ThreadPoolExecutor(max_workers=8) as pool:
        for stem, err in zip(stale, pool.map(write_plan, stale)):
            if err is not None:
                print(f"  {stem}: the plan failed: {err}")


_LIBS: tuple[Lib, Lib] | None = None



_ARC_TOKEN = re.compile(r"[&$]?[A-Za-z_][\w]*(?:\.[\w]+)*")
_ALTS_CONCEPT = re.compile(r'\(ALTS \$\w+ "(?:[^"\\]|\\.)*" \$(\w+)')
"""The constructor an `ALTS` form gives as its concept alt."""


def _souffle_relation(c: "Converter", w: Written) -> dict:
    """The Souffle relation, or instance, `w`: the component path, its name
    there, and its name from the top level of the solver's program, null
    where no instance at the top level is of the scope's component."""
    path: str | None = w.relation
    if w.scope:
        at = [n for (sc, n), i in c.insts.items() if sc == () and i.component == w.scope[-1]]
        path = f"{at[0]}.{w.relation}" if len(w.scope) == 1 and len(at) == 1 else None
    return {"component": list(w.scope), "relation": w.relation, "path": path}


def _renamed_name(name: str, insts: dict[str, str]) -> str:
    """The arclog name `name` the converter writes, as the renames
    `convert_one` applies after it leave it: `renamed`, then
    `libmap_rename.rename` with `insts`."""
    return libmap_rename.rename(renamed(f"({name})"), insts)[1:-1]


def _relations_read(text: str) -> set[str]:
    """Each name the arclog or arcdata `text` reads as a relation or an
    instance: a name with `&` outside a quoted text, and the head of a
    form."""
    from arclog_convert.lint import L, Sym, read
    out: set[str] = set()

    def scan(xs: list) -> None:
        for x in xs:
            if not isinstance(x, L):
                continue
            for i, it in enumerate(x.items):
                if isinstance(it, Sym):
                    t = it.text.lstrip("^*")
                    if _ARC_TOKEN.fullmatch(t) and (t.startswith("&") or i == 0):
                        out.add(t)
            scan(x.items)
    scan(read(text))
    return out


def name_map(s: "Solver", insts: dict[str, str], arclog: str, arcdata: str) -> dict:
    """Each arclog relation name the written files read, with each Souffle
    relation it was written from, in the order the pass wrote them; each
    instance they read, with each Souffle instance; each `ALT` name, with the Souffle `Choice` constructor; and
    each arclog name with `&` the files read that the renames of this pass
    give no Souffle relation, under `unmapped`. Each name is the one the
    converter recorded as it wrote it (`Converter.wrote`), or a top-level
    lib relation it writes under its own name that the solver declares no
    relation of, under the renames
    `convert_one` applies after it (`_renamed_name`)."""
    c = s.c
    named = dict(c.written)
    for own in (*sorted(FACTS), *c.lib.top, *c.sig.top):
        if ((), own) not in c.rels:   # else the Souffle name is the solver's own relation
            named.setdefault(own, [Written((), own, False)])
    rels: dict[str, list[dict]] = {}
    instances: dict[str, list[dict]] = {}
    for arc, ws in named.items():
        for w in ws:
            got = (instances if w.instance else rels).setdefault(_renamed_name(arc, insts), [])
            if (r := _souffle_relation(c, w)) not in got:
                got.append(r)
    read = _relations_read(arclog + "\n" + arcdata)
    relations = {n: rels[n] for n in sorted(read) if n in rels}
    ctors = {f"${m}": m for m in sorted(set(re.findall(r"\(ALT \$(\w+)", arclog))
                                        | set(_ALTS_CONCEPT.findall(arclog)))}
    insts_read = {n: instances[n] for n in sorted(read) if n in instances}
    unmapped = sorted(n for n in read if n.startswith("&") and n not in relations
                      and n not in insts_read)
    return {"relations": relations, "instances": insts_read, "constructors": ctors,
            "unmapped": unmapped}


def column_map(s: "Solver", names: dict, insts: dict[str, str]) -> dict:
    """For each arclog relation of the name map `names` with one Souffle
    relation that has a path from the top level, or is declared in
    `Determine` (its path under the instance that `solver.determine.run_program`
    adds is `determine.<relation>`), one entry per column of the Souffle
    relation, in its order: the list of the kept leaves of that
    Souffle column that the arclog relation holds, each as
    `{"leaf": <path into the Souffle column's record>, "label": <the arclog
    column>, "field": <the field within the arclog column, or null>,
    "example": <whether the leaf is an Example leaf>}`; the list is empty
    where no arclog column holds a leaf of the Souffle column. The arclog
    columns stand for the Souffle relation's columns by the `Written.columns`
    of the relation of an expansion's shape (`Converter.made`); for a relation
    that lost `TiebreakResolution` columns, by the columns it kept; otherwise
    one to one. A relation whose arclog columns and Souffle columns differ in
    number and whose correspondence the converter does not hold gets no entry.
    The relation is resolved as a read sees it (`Converter.resolve`): from the
    top level by the Souffle relation's path, a relation of `Determine` with no
    path from within `Determine`, and a relation of an expansion's
    shape by its own name; the labels are those `site_columns` gives, the ones
    every read the converter writes of the relation names. `insts` are the
    instance renames `convert_one` applies to the names."""
    c = s.c
    out: dict[str, list[list[dict]]] = {}
    shaped: set[str] = set()
    for (scope, shape), w in c.made.items():
        if w is None or w.columns is None:
            continue
        *chain, rel = shape.split(".")
        name, cols, _, inst = c.resolve(RelationName(tuple(chain), rel), scope, {})
        arc = _renamed_name(name, insts)
        shaped.add(arc)
        width = c.souffle_arity(w.scope, w.relation)
        if cols is None or width is None or len(cols) != len(w.columns) \
                or names["relations"].get(arc) != [_souffle_relation(c, w)]:
            continue
        out[arc] = _souffle_columns(site_columns(c, cols, inst), w.columns, width)
    for arc, souffle in names["relations"].items():
        if arc in shaped or len(souffle) != 1:
            continue
        scope, relation, path = tuple(souffle[0]["component"]), souffle[0]["relation"], souffle[0]["path"]
        if path is not None:
            *chain, rel = path.split(".")
            _, cols, _, inst = c.resolve(RelationName(tuple(chain), rel), (), {})
        elif scope == ("Determine",):   # the instance a run adds (`solver.determine.run_program`) has no path in the solver's text
            *chain, rel = relation.split(".")
            _, cols, _, inst = c.resolve(RelationName(tuple(chain), rel), scope, {})
        else:
            continue
        width = c.souffle_arity(scope, relation)
        if cols is None or width is None:
            continue
        kept = tuple(j for j in range(width) if j not in c.dropped.get((scope, relation), ()))
        if len(kept) == len(cols):
            out[arc] = _souffle_columns(site_columns(c, cols, inst), kept, width)
    return out


def _souffle_columns(columns: list[list[Site]], placement: tuple[Placement, ...], width: int) -> list[list[dict]]:
    """The sites of the arclog columns `columns`, as the entries of the
    `width` columns of the Souffle relation they are placed in by
    `placement` (`Written.columns`): each site under the Souffle column that
    holds its leaf, with the leaf's path into that column."""
    out: list[list[dict]] = [[] for _ in range(width)]
    for sites, where in zip(columns, placement):
        for site in sites:
            at, path = where, tuple(site.leaf.path)
            if isinstance(where, tuple):   # a record term: its field holds the leaf
                at, path = where[path[0]], path[1:]
            if at is not None:
                out[at].append({"leaf": list(path), "label": site.label, "field": site.field,
                                "example": site.leaf.kind == "example"})
    return out


def _written_inline(s: "Solver", arclog: str) -> frozenset[str]:
    """Each relation of the solver declared `inline` that `arclog`, the pass's
    text, still writes as a `RULE` or `DET`, and whose clauses `terms.inlined`
    can inline: each has a body and a head of distinct variables. A relation
    the pass's merge removed is not in `arclog`, and one of another head
    stays as the pass wrote it."""
    c = s.c
    names = {r.name for r in c.prog.relations if Qualifier.INLINE in r.qualifiers}
    names = {n for n in names if n in c.unsafe or re.search(r"\((?:RULE|DET) &" + re.escape(n) + r"(?![\w-])", arclog)}

    def inlinable(n: str) -> bool:
        units = [u for u in c.prog.units if u.head.relation.name == n and not u.head.relation.instances]
        return n not in c.lib.top and any(u.body is not None for u in units) and all(
            u.body is None or (all(isinstance(a, Variable) for a in u.head.args)
                               and len({a.name for a in u.head.args}) == len(u.head.args))
            for u in units)
    return frozenset(n for n in names if inlinable(n))


def convert_one(stem: str) -> tuple[str, str | None, str | None, Counter, Counter, list[str], ColMismatch, str | None]:
    """One solver's arclog and arcdata, its TODO kinds, its merge counts and
    its parameters whose columns do not map onto their proposer's, or the
    error that stopped it: a pool worker's unit of work."""
    global _LIBS, fix_labels
    if _LIBS is None:
        from arclog_convert.lint import fix_labels
        lib, sig = Lib(LIB_DL), Lib(SIGNATURE)
        lib.extend(sig)
        _LIBS = lib, sig
    lib, sig = _LIBS
    MERGES.clear()
    MERGES_UNMERGED.clear()
    todo = Todo()
    try:
        s = Solver(stem, lib, sig, todo)
        arclog, arcdata = s.run()
        # an `inline` relation that the pass writes as an arclog relation is no
        # relation: its body stands at each call
        stuck = _written_inline(s, arclog)
        if stuck:
            MERGES.clear()
            MERGES_UNMERGED.clear()
            todo = Todo()
            s = Solver(stem, lib, sig, todo, stuck)
            arclog, arcdata = s.run()
        arclog = fold_or_lines(renamed(arclog))
        insts = libmap_rename.renamed_instances(libmap_rename.instances(arclog),
                                                libmap_rename.reads(arclog + arcdata))
        arclog = hoist_shared(fix_labels(libmap_rename.rename(arclog, insts)))
        arcdata = libmap_rename.rename(arcdata, insts)
        if paths.MACROS_ENV not in os.environ:
            names = name_map(s, insts, arclog, arcdata)
            columns = column_map(s, names, insts)
            for directory, data in ((paths.NAMES_DIR, names), (paths.COLUMNS_DIR, columns)):
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{stem}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    except Exception as e:  # noqa: BLE001
        return stem, None, None, Counter(), Counter(), [], {}, f"{type(e).__name__}: {e}"
    return stem, arclog, arcdata, todo.kinds, Counter(MERGES), list(MERGES_UNMERGED), s.c.col_mismatch, None


def main(argv: list[str]) -> int:
    global OUT_DIR, MACROS_DIR, PLANS, NAMES_DIR, COLUMNS_DIR
    import argparse
    parser = argparse.ArgumentParser(prog="python -m arclog_convert.convert")
    parser.add_argument("--out", type=Path, help="the directory to write under, in place of `arclog_convert.out`; required in a linked worktree unless `ARCLOG_OUT` is set")
    parser.add_argument("--no-train-replay", action="store_true", help="convert with no replay on the train pairs")
    parser.add_argument("--accept", action="store_true", help="rewrite the baseline lines of the solvers this run converted to its counts, and the row-parity baseline lines of those solvers unless --no-row-parity")
    parser.add_argument("--no-row-parity", action="store_true", help="convert with no comparison of the relations with Souffle's rows")
    parser.add_argument("stems", nargs="*", help="the solvers to convert; every solver where none is given")
    args = parser.parse_args(argv)
    if args.accept and args.no_train_replay:
        parser.error("--accept needs the train replay; drop --no-train-replay")
    if args.out is not None:
        # set before the pools start, so that their workers read it
        os.environ[OUT_ENV] = str(args.out.resolve())
        paths.OUT_DIR, paths.MACROS_DIR, paths.PLANS, paths.NAMES_DIR, paths.COLUMNS_DIR = paths.out_dirs()
    else:
        writable_out()
    stems = args.stems or sorted(p.stem for p in paths.SOLVERS.glob("*.dl"))
    refresh_plans(stems)
    print(f"{paths.OUT_DIR}:")
    converted = convert_into(stems, paths.OUT_DIR)
    # set before the second pool starts, so that its workers read it
    os.environ[paths.MACROS_ENV] = "1"
    print(f"{paths.MACROS_DIR}:")
    convert_into(stems, paths.MACROS_DIR)
    from arclog_convert import row_parity, train_replay
    status = 0 if args.no_train_replay else train_replay.replay(converted, paths.OUT_DIR.parent, args.accept)
    if args.no_row_parity:
        return status
    return row_parity.check(converted, paths.OUT_DIR.parent, args.accept) or status


def convert_into(stems: list[str], out: Path) -> list[str]:
    """Convert `stems` into `out` over a process pool, print the
    summary, and give the stems it converted."""
    from concurrent.futures import ProcessPoolExecutor
    out.mkdir(parents=True, exist_ok=True)
    total = Counter()
    per_kind_solvers = Counter()
    merges: Counter[str] = Counter()
    unmerged: list[str] = []
    mismatched: list[tuple[str, str, list[Col], list[Col]]] = []
    failed = []
    converted = []
    clean = 0
    workers = min(len(stems), os.cpu_count() or 4)
    if workers > 1:
        pool = ProcessPoolExecutor(workers)
        # the largest solvers first, so that no long one starts last
        order = sorted(stems, key=lambda t: -(paths.SOLVERS / f"{t}.dl").stat().st_size)
        results = pool.map(convert_one, order)
    else:
        pool, results = None, map(convert_one, stems)
    for stem, arclog, arcdata, kinds, m, um, mis, err in results:
        if err is not None:
            failed.append((stem, err))
            continue
        converted.append(stem)
        (out / f"{stem}.arclog").write_text(arclog)
        (out / f"{stem}.arcdata").write_text(arcdata)
        merges += m
        unmerged += um
        mismatched += [(stem, name, own, prop) for name, (own, prop) in mis.items()]
        total += kinds
        for k in kinds:
            per_kind_solvers[k] += 1
        if not kinds:
            clean += 1
    if pool is not None:
        pool.shutdown()
    print(f"converted {len(stems) - len(failed)} of {len(stems)}; {clean} with no TODO")
    print(f"merged {merges['relation']} relations and {merges['input']} inputs; "
          f"unmerged {merges['unmerged']} relations ({', '.join(sorted(set(unmerged)))}) "
          f"and {merges['input-unmerged']} inputs")
    if mismatched:
        print(f"{len(mismatched)} parameters keep their own columns, which do not map onto those of the proposer or the derivation their DET names:")
        for stem, name, own, prop in sorted(mismatched, key=lambda u: u[:2]):
            print(f"  {stem} {name}: ({', '.join(f'{c.name} {c.type}' for c in own)}) "
                  f"onto ({', '.join(f'{c.name} {c.type}' for c in prop)})")
    for k, n in total.most_common():
        print(f"  {k:20} {n:6} in {per_kind_solvers[k]} solvers")
    if failed:
        print(f"failed {len(failed)}:")
        for stem, err in failed[:30]:
            print(f"  {stem}: {err}")
        errs = Counter(e.split(":")[0] + ":" + e.split(":")[1][:60] for _, e in failed)
        for e, n in errs.most_common(10):
            print(f"  {n:4} {e}")

    return converted


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

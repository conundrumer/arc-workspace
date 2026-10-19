"""The rows of each Params relation a solver derives through `helpers`.

A clause of Params that reads a `ParamsHelpers` relation computes a
parameter's value from other parameters. Souffle runs the solver with no
input and prints those relations, and the rows are cached per solver under
`helper_rows/` of `arclog_convert.out`, keyed by the solver's and the lib's bytes.
"""

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRAMS = ROOT / "programs"
SOLVERS = PROGRAMS / "solvers"
sys.path.insert(0, str(ROOT / "src"))

from engine.engine import Limits, Tuples  # noqa: E402
from engine.program import AdtValue, RecordValue, RelationName  # noqa: E402
from souffle.engine import SouffleEngine  # noqa: E402
from arclog_convert import out  # noqa: E402

CACHE = out() / "helper_rows"

ENGINE = SouffleEngine()


def helper_rels(prog) -> list[str]:
    out = []
    for u in prog.units:
        if u.scope.components != ("Params",) or u.body is None or u.head.relation.instances:
            continue
        if any(getattr(getattr(l, "atom", None), "relation", None) is not None
               and l.atom.relation.instances == ("helpers",) for l in u.body):
            if u.head.relation.name not in out:
                out.append(u.head.relation.name)
    return out


def value_text(v) -> str:
    """A value in arcdata's spelling."""
    if isinstance(v, RecordValue):
        return "(" + " ".join(value_text(x) for x in v.fields) + ")"
    if isinstance(v, AdtValue):
        return "$" + v.constructor if not v.args else \
            "($" + v.constructor + " " + " ".join(value_text(x) for x in v.args) + ")"
    return str(v)


def stamp() -> str:
    h = hashlib.sha256()
    for f in [PROGRAMS / "lib.dl", *sorted((PROGRAMS / "lib").glob("*.dl"))]:
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def split_fields(line: str) -> list[str]:
    return line.rstrip("\n").split("\t")


def rows(stem: str, lib_stamp: str | None = None) -> dict[str, list[list[str]]]:
    text = (SOLVERS / f"{stem}.dl").read_text()
    key = hashlib.sha256((text + (lib_stamp or stamp())).encode()).hexdigest()[:16]
    cached = CACHE / f"{stem}.json"
    if cached.exists():
        got = json.loads(cached.read_text())
        if got.get("key") == key:
            return got["rows"]
    prog = ENGINE.parse_including(text, "lib.dl", PROGRAMS)
    if not hasattr(prog, "units"):
        raise RuntimeError(f"{stem}: parse failed: {prog}")
    rels = helper_rels(prog)
    result: dict[str, list[list[str]]] = {}
    if rels:
        names = [RelationName(("params",), r) for r in rels]
        got = ENGINE.run(prog, {}, names, Limits(600, 600))
        if not isinstance(got, Tuples):
            raise RuntimeError(f"{stem}: run failed: {str(got)[:400]}")
        for r, n in zip(rels, names):
            result[r] = [[value_text(v) for v in row] for row in sorted(got.relations[n], key=repr)]
    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"key": key, "rows": result}))
    return result


def main(argv: list[str]) -> None:
    stems = argv or sorted(p.stem for p in SOLVERS.glob("*.dl")
                           if "helpers." in p.read_text())
    s = stamp()
    def one(t):
        try:
            return rows(t, s)
        except RuntimeError as e:
            return str(e)
    with ThreadPoolExecutor(4) as ex:
        for stem, got in zip(stems, ex.map(one, stems)):
            print(stem, got if isinstance(got, str) else {k: len(v) for k, v in got.items()})


if __name__ == "__main__":
    main(sys.argv[1:])

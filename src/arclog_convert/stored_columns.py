"""The value columns of a `@store` relation that Souffle keys by columns
outside its value, and the `(STORED ...)` mark that states them in arclog
(`docs/arclog/arclog.md#the-alts-form`)."""

import hashlib
import json
import re

from solver.cases import cases
from solver.group_runs import StoredValues, case_groups
from solver.load import load
from solver.model import StoreBranch, choice_bases
from solver.restricted import restricted
from solver.stored_value import StoredValue, stored_value
from souffle import SouffleEngine

from arclog_convert import out
from arclog_convert.helper_rows import stamp


def cache_key(stem: str) -> str:
    """The digest of what the columns depend on: the solver's text, the
    lib (`helper_rows.stamp`), the task file, and the sources of the solver
    tool and the engine's Souffle layer."""
    from engine import checkout

    h = hashlib.sha256()
    h.update((checkout.solvers() / f"{stem}.dl").read_bytes())
    h.update(stamp().encode())
    h.update(checkout.sources_digest(["src/solver/*.py", "src/souffle/*.py", "src/engine/*.py"]).encode())
    task = checkout.ROOT / "data" / "tasks" / f"{stem[:8]}.json"
    h.update(task.read_bytes() if task.exists() else b"")
    return h.hexdigest()[:16]


def keyed_value_columns(stem: str) -> dict[str, tuple[tuple[int, ...], int]]:
    """For each `@store` line of the solver `stem`, by the relation as the
    line spells it (`StoreBranch.spelled`), the columns of its value and the
    relation's arity, where the stored value is keyed by columns outside the
    value that hold no case (`StoredValue.keyed_by_case` false). The value is
    the one `outcomes` computes for the cases that take the line's branch
    (`solver.group_runs.StoredValues`). It is cached under `stored_columns/`
    of the converter's output directory, by `cache_key`, so that a repeat
    conversion of an unchanged solver runs no Souffle. Raises `ValueError`
    where two case groups give one relation different value columns."""
    key = cache_key(stem)
    cached = out() / "stored_columns" / f"{stem}.json"
    if cached.exists():
        got = json.loads(cached.read_text())
        if got.get("key") == key:
            return {k: (tuple(cols), arity) for k, (cols, arity) in got["columns"].items()}
    found = _computed(stem)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"key": key, "columns": {k: [list(c), a] for k, (c, a) in found.items()}}))
    return found


def _computed(stem: str) -> dict[str, tuple[tuple[int, ...], int]]:
    """`keyed_value_columns`, computed by running the solver."""
    from cli.common import LIMITS

    engine = SouffleEngine()
    solver = load(stem, engine)
    if not solver.branches or solver.task is None or not solver.task.train:
        return {}
    found = cases(solver, engine, LIMITS)
    if not isinstance(found, tuple):
        return {}
    stored = StoredValues()
    out_: dict[str, tuple[tuple[int, ...], int]] = {}
    seen: dict[str, tuple[int, ...]] = {}
    for members in case_groups(solver, found):
        bases = tuple(choice_bases(members))
        held = restricted(engine, solver, bases)
        for b in members[0].branches:
            if not isinstance(b, StoreBranch):
                continue
            got = stored.get((bases, b.relation), lambda b=b: stored_value(engine, solver, held, b, bases, LIMITS))
            if not isinstance(got, StoredValue) or got.keyed_by_case:
                continue
            if b.spelled in seen and seen[b.spelled] != got.columns:
                raise ValueError(f"{stem}: `{b.spelled}` has the value columns {seen[b.spelled]} in one case group and {got.columns} in another")
            seen[b.spelled] = got.columns
            out_[b.spelled] = got.columns, got.arity
    return out_


def stored_mark(columns: tuple[int, ...], names: list[str], key_fields: list[str]) -> str:
    """The `(STORED ...)` mark for the value columns `columns` of a relation
    whose arclog columns are `names`, in Souffle's order: a bare column's
    name, and for the `key` column each field of the key record,
    `(:key <Field>)`, the fields being `key_fields`."""
    sites: list[str] = []
    for i in columns:
        if names[i] == "key":
            sites += [f"(:key {f})" for f in key_fields]
        else:
            sites.append(names[i])
    return f" (STORED {' '.join(sites)})"


def key_labels(init_lines: list[str]) -> list[str]:
    """The `^` labels of an `INIT` form's key body: the fields of its key record."""
    return sorted(set(re.findall(r"\^(\w+)", " ".join(init_lines))))

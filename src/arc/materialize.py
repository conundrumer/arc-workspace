"""Materialize: load upstream + apply patches → in-memory dict for serialization.

Materialize a task: load v1-preferred upstream, apply the canonical patch
(<id>.txt) if present, then apply every variant patch (<id>_<X>.txt) in
alphabetical order. The result reflects the highest variant level present
(else canonical).

Source records are listed canonical-first; non-canonical sources include a
`perm` mapping from that source's ordering back to canonical.

Each applied patch contributes one entry to a `patches` list on the resulting
dict, each carrying its level and any top-of-file metadata (`comment`,
`issue`, …) from that patch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .apply import apply_patch
from .patch import parse
from .task import Example
from .upstream import UpstreamSource, find_all, load_at

PATCHES_DIR = Path(__file__).resolve().parents[2] / "data" / "patches"
VARIANT_LABELS = ("A", "B", "C")


def materialize_default(task_id: str) -> dict[str, Any]:
    """Materialize the highest-consistency form of a task.

    The output dict carries a `patches` list (one entry per applied patch)
    plus a `variant` field naming the highest level applied when any was."""
    sources = find_all(task_id)
    if not sources:
        raise FileNotFoundError(f"task {task_id!r} not found in upstream")
    task = load_at(task_id, sources[0])

    patches: list[dict[str, Any]] = []

    canonical_path = PATCHES_DIR / f"{task_id}.txt"
    if canonical_path.exists():
        patch = parse(canonical_path.read_text())
        patches.append({"level": "canonical", **patch.metadata})
        task = apply_patch(task, patch)

    applied_variants: list[str] = []
    for label in VARIANT_LABELS:
        vpath = PATCHES_DIR / f"{task_id}_{label}.txt"
        if not vpath.exists():
            continue
        vpatch = parse(vpath.read_text())
        patches.append({"level": label, **vpatch.metadata})
        task = apply_patch(task, vpatch)
        applied_variants.append(label)

    file_dict: dict[str, Any] = {
        "id": task_id,
        "source": _build_source_records(task_id, sources),
    }
    if patches:
        file_dict["patches"] = patches
    if applied_variants:
        file_dict["variant"] = applied_variants[-1]
    file_dict["train"] = _examples_to_dicts(task.train)
    file_dict["test"] = _examples_to_dicts(task.test)
    return file_dict


def _examples_to_dicts(examples: list[Example]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, ex in enumerate(examples):
        d: dict[str, Any] = {"index": i, "input": ex.input, "output": ex.output}
        if ex.alt is not None:
            d["alt"] = {"kind": ex.alt.kind, "grid": ex.alt.grid}
        out.append(d)
    return out


def _build_source_records(task_id: str, sources: list[UpstreamSource]) -> list[dict[str, Any]]:
    canonical = load_at(task_id, sources[0])
    out: list[dict[str, Any]] = [
        {"dataset": sources[0].dataset, "split": sources[0].split}
    ]
    for src in sources[1:]:
        other = load_at(task_id, src)
        record: dict[str, Any] = {"dataset": src.dataset, "split": src.split}
        perm: dict[str, list[int]] = {}
        if (tp := _example_perm(other.train, canonical.train)) is not None:
            perm["train"] = tp
        if (ep := _example_perm(other.test, canonical.test)) is not None:
            perm["test"] = ep
        if perm:
            record["perm"] = perm
        out.append(record)
    return out


def _example_perm(other: list[Example], canonical: list[Example]) -> list[int] | None:
    """None for identity, and for set-mismatch where no permutation exists."""
    canonical_keys = [_ex_key(e) for e in canonical]
    other_keys = [_ex_key(e) for e in other]
    if other_keys == canonical_keys:
        return None
    if sorted(other_keys) != sorted(canonical_keys):
        return None
    return [canonical_keys.index(k) for k in other_keys]


def _ex_key(ex: Example) -> tuple:
    return (
        tuple(tuple(r) for r in ex.input),
        tuple(tuple(r) for r in ex.output),
    )

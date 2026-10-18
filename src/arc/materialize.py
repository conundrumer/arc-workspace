"""Materialize: load upstream + apply patches → in-memory dict for serialization.

Materialize a task: load v1-preferred upstream, apply the canonical patch
(<id>.arcpatch) if present, then apply every variant patch (<id>_<X>.arcpatch)
in alphabetical order. The result reflects the highest variant level present
(else canonical).

Source records are listed canonical-first; non-canonical sources include a
`perm` mapping from that source's ordering back to canonical.

Each applied patch contributes one entry to a `patches` list on the resulting
dict, each holding its level and any top-of-file metadata (`comment`,
`issue`, …) from that patch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .apply import apply_patch
from .patch import parse
from .task import PAIR_SECTIONS, Example, pair_json
from .upstream import UpstreamSource, find_all, load_at

PATCHES_DIR = Path(__file__).resolve().parents[2] / "data" / "patches"
VARIANT_LABELS = ("A", "B", "C")

# The keys of a task file, in the order `materialize_default` writes them:
# `DESCRIPTION_KEYS` describe the task, and each of `arc.task.PAIR_SECTIONS`
# holds the task's pairs of that name, each in its JSON form
# (`arc.task.pair_json`).
ID, SOURCE, PATCHES, VARIANT = "id", "source", "patches", "variant"
DESCRIPTION_KEYS = (ID, SOURCE, PATCHES, VARIANT)


def materialize_default(task_id: str) -> dict[str, Any]:
    """Materialize the highest-consistency form of a task.

    The output dict holds a `patches` list (one entry per applied patch)
    plus a `variant` field naming the highest level applied when any was."""
    sources = find_all(task_id)
    if not sources:
        raise FileNotFoundError(f"task {task_id!r} not found in upstream")
    task = load_at(task_id, sources[0])

    patches: list[dict[str, Any]] = []

    canonical_path = PATCHES_DIR / f"{task_id}.arcpatch"
    if canonical_path.exists():
        patch = parse(canonical_path.read_text())
        patches.append({"level": "canonical", **patch.metadata})
        task = apply_patch(task, patch)

    applied_variants: list[str] = []
    for label in VARIANT_LABELS:
        vpath = PATCHES_DIR / f"{task_id}_{label}.arcpatch"
        if not vpath.exists():
            continue
        vpatch = parse(vpath.read_text())
        patches.append({"level": label, **vpatch.metadata})
        task = apply_patch(task, vpatch)
        applied_variants.append(label)

    file_dict: dict[str, Any] = {
        ID: task_id,
        SOURCE: _build_source_records(task_id, sources),
    }
    if patches:
        file_dict[PATCHES] = patches
    if applied_variants:
        file_dict[VARIANT] = applied_variants[-1]
    for section in PAIR_SECTIONS:
        file_dict[section] = [pair_json(ex, i) for i, ex
                              in enumerate(getattr(task, section))]
    return file_dict


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


type _GridKey = tuple[tuple[int, ...], ...]
type _ExKey = tuple[_GridKey, _GridKey]


def _ex_key(ex: Example) -> _ExKey:
    return (
        tuple(tuple(r) for r in ex.input),
        tuple(tuple(r) for r in ex.output),
    )

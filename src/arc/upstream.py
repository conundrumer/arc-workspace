"""Load upstream ARC tasks from the pinned `data/upstream/` submodules.

Resolution order: ARC-AGI-1 (training, then evaluation), then ARC-AGI-2
(training, then evaluation). v1 ordering matches arcprize.org and wins
for shared tasks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .task import Example, Task

type DatasetT = Literal["arc-agi-1", "arc-agi-2"]
type SplitT = Literal["training", "evaluation"]

UPSTREAM_DIR = Path(__file__).resolve().parents[2] / "data" / "upstream"

_RESOLUTION: list[tuple[DatasetT, SplitT]] = [
    ("arc-agi-1", "training"),
    ("arc-agi-1", "evaluation"),
    ("arc-agi-2", "training"),
    ("arc-agi-2", "evaluation"),
]


@dataclass(frozen=True)
class UpstreamSource:
    dataset: DatasetT
    split: SplitT


def find(task_id: str) -> UpstreamSource | None:
    for dataset, split in _RESOLUTION:
        if _path(dataset, split, task_id).exists():
            return UpstreamSource(dataset, split)
    return None


def find_all(task_id: str) -> list[UpstreamSource]:
    """All sources where the task appears, in canonical resolution order."""
    return [
        UpstreamSource(dataset, split)
        for dataset, split in _RESOLUTION
        if _path(dataset, split, task_id).exists()
    ]


def load(task_id: str) -> tuple[Task, UpstreamSource]:
    src = find(task_id)
    if src is None:
        raise FileNotFoundError(f"task {task_id!r} not found in upstream")
    return load_at(task_id, src), src


def load_at(task_id: str, src: UpstreamSource) -> Task:
    return _load_json(_path(src.dataset, src.split, task_id))


def _path(dataset: DatasetT, split: SplitT, task_id: str) -> Path:
    return UPSTREAM_DIR / dataset / "data" / split / f"{task_id}.json"


def _load_json(path: Path) -> Task:
    data = json.loads(path.read_text())
    return Task(
        train=[Example(input=e["input"], output=e["output"]) for e in data["train"]],
        test=[Example(input=e["input"], output=e["output"]) for e in data["test"]],
    )

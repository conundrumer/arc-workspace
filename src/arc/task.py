"""Task data model — minimal in-memory representation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

type Grid = list[list[int]]
type AltKind = Literal["rule", "tiebreak"]

TASKS_DIR = Path(__file__).resolve().parents[2] / "data" / "tasks"


@dataclass
class Alt:
    kind: AltKind
    grid: Grid


@dataclass
class Example:
    input: Grid
    output: Grid
    # ARC scoring is pass@2, so at most one alternative valid output per example.
    alt: Alt | None = None


@dataclass
class Task:
    train: list[Example] = field(default_factory=list[Example])
    test: list[Example] = field(default_factory=list[Example])


def load(task_id: str) -> Task:
    """Load a materialized task from data/tasks/. Patches applied; upstream errors fixed."""
    path = TASKS_DIR / f"{task_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"no materialized task at {path}")
    data = json.loads(path.read_text())
    return Task(
        train=[Example(input=e["input"], output=e["output"]) for e in data["train"]],
        test=[Example(input=e["input"], output=e["output"]) for e in data["test"]],
    )

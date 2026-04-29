"""Task data model — minimal in-memory representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

type Grid = list[list[int]]
type AltKind = Literal["rule", "tiebreak"]


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
    train: list[Example] = field(default_factory=list)
    test: list[Example] = field(default_factory=list)

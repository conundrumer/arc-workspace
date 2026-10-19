"""The intermediates a slow section keeps, under
`.cache/corpus-survey/<section>/` of the main worktree, each keyed by what
it is computed from, so that a run computes again only those whose inputs
changed."""

import hashlib
import json
from collections.abc import Callable, Sequence
from functools import cache
from pathlib import Path
from typing import Any

from engine import checkout
from engine.memo import hash_file, read_or_make
from parity.snapshot import record_key


def kept_dir(section: str) -> Path:
    return checkout.caches() / "corpus-survey" / section


def files_key(files: Sequence[Path]) -> str:
    """The hash of each file of `files`, by its path as a line shows it
    (`checkout.shown`) and its bytes, a file that does not stand by its
    path alone."""
    h = hashlib.sha256()
    for p in files:
        hash_file(h, str(checkout.shown(p)), p.read_bytes() if p.is_file() else None)
    return h.hexdigest()


ROOT = checkout.ROOT


def tree_files() -> list[Path]:
    """Every file under `src/` and `engine/lib/`, sorted, leaving out
    `__pycache__`."""
    return sorted(p for top in ("src", "engine/lib") for p in (ROOT / top).rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts)


@cache
def tree_key() -> str:
    """The `files_key` of `tree_files()`, computed once per run."""
    return files_key(tree_files())


def solver_key(stem: str, files: Sequence[Path] = ()) -> dict[str, Any]:
    """What an intermediate of a run of the solver `stem` is computed
    from: what its snapshot record depends on (`parity.snapshot.record_key`),
    every file under `src/` and `engine/lib/` (`tree_key`), and `files`."""
    return {"solver": record_key(stem), "code": tree_key(), "files": files_key(files)}


def kept(section: str, key: dict[str, Any], make: Callable[[], Any]) -> Any:
    """The JSON value kept for `section` under `key`, else the one `make`
    gives, kept."""
    name = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
    return read_or_make(kept_dir(section) / f"{name}.json",
                        lambda data: json.loads(data),
                        lambda value: json.dumps(value).encode(),
                        lambda: (make(), True))

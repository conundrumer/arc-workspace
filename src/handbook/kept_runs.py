"""The runs of `scripts/context.py` in a tree of a commit, with that tree's
own code, and the outputs of those runs in kept trees
(`kept_trees.tree_at`), kept under `checkout.cache()`."""

from __future__ import annotations

import fcntl
import hashlib
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from engine.memo import read_or_make
from handbook.kept_trees import TREES, flocked

CONTEXT_SCRIPT = (checkout.scripts() / "context.py").relative_to(checkout.ROOT)
"""The command that prints a reader's context, from a checkout's root."""

RUNS = "reader-runs"
"""The directory under `checkout.cache()` that holds the kept outputs of
the runs in kept trees (`run_in`)."""


def run_in(tree: Path, commit: str, argv: list[str]) -> str:
    """The output of `scripts/context.py` with `argv`, run in `tree`, the
    tree of `commit`, with that tree's own code. Where `tree` is a kept
    tree (`kept_trees.tree_at`), the output is kept under `checkout.cache()` by the
    tree's commit and `argv`, since it never changes for that commit, and
    one run makes it however many ask for it at once; the checkout's output
    is not kept, since its files may differ from its `HEAD`."""
    if tree.parent != checkout.cache() / TREES:
        return _run(tree, commit, argv)
    return kept(RUNS, [tree.name, *argv], ".txt", bytes.decode, str.encode,
                lambda: (_run(tree, commit, argv), True))


def kept[V](directory: str, parts: Sequence[str], suffix: str,
            decode: Callable[[bytes], V | None], encode: Callable[[V], bytes],
            make: Callable[[], tuple[V, bool]]) -> V:
    """The value `read_or_make` gives of the file with `suffix` under
    `directory` in `checkout.cache()`, named by the sha256 of `parts`, under
    an exclusive lock on that name, so that of two calls with one key at
    once, the second waits for the first and reads what it kept."""
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode() + b"\0")
    key = checkout.cache() / directory / h.hexdigest()
    with flocked(key.with_suffix(".lock"), fcntl.LOCK_EX):
        return read_or_make(key.with_suffix(suffix), decode, encode, make)


def _run(tree: Path, commit: str, argv: list[str]) -> str:
    paths = [str(tree / "src"), os.environ.get("PYTHONPATH", "")]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in paths if p)}
    done = subprocess.run([sys.executable, str(tree / CONTEXT_SCRIPT), *argv],
                          cwd=tree, env=env, capture_output=True, text=True)
    if done.returncode != 0:
        failed = mctx("The run of `{command}` at {commit} failed.").format(
            command=" ".join(argv), commit=commit)
        raise SystemExit(failed + "\n" + done.stderr.strip())
    return done.stdout

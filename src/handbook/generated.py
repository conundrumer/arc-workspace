"""The generated files the renderer writes in the checkout, which git
ignores, and the manifest that lists them.

A command hands each file it generates to `write_generated`, or to
`regenerate`, as a `Rendering`. A rendering whose path stands under the checkout's root is a
generated file in the checkout. Before any is written, one
`git check-ignore` call over all of them and the manifest finds each that
git does not ignore, and where one is not ignored, nothing is written and
the command fails with `Unignored`. A path outside the checkout, such as
the gate's copy of the documents under its out dir, is written with no
check and no manifest entry. The module of the lib's wrappers is generated
and tracked, so it is written by `write_whole_text` alone, outside the
check.

The manifest opens with `MANIFEST_HEAD`, and gives each generated file
written in the checkout on a line of its own: the sha256 of the text
written, a space, and its path from the checkout's root. Each write adds
the files it writes, and keeps each listed file that still stands.

`regenerate` takes every rendering the sources give, and removes a listed
file only where git ignores it, no rendering has its path, and the file
still has the digest the manifest gives. A listed file it does not remove
is left in place, reported as `Left`, and dropped from the manifest. So:
- `AGENTS.md` and `.codex/config.toml`, which other tools read, are
  rendered by each run while their sources stand, and so are never stale.
- A hand edit, or another tool's write, at a listed path changes its
  digest, and the file stays.
- A manifest of another form, which does not open with `MANIFEST_HEAD`,
  lists nothing, so none of the files it names is removed.
- Two runs at once each write the manifest whole, so the entries of one
  can replace the other's. An entry lost that way leaves its file in place.
- A worktree has its own root, ignore rules and manifest, and the gate's
  copy stands outside the checkout.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath

from controlled_markdown import mctx
from engine import checkout
from engine.memo import write_whole
from handbook.paths import REPO_ROOT

MANIFEST_NAME = ".manifest"
MANIFEST_HEAD = "# sha256 path, of each generated file, from the checkout's root"


MANIFEST = PurePosixPath(
    checkout.agents().relative_to(checkout.ROOT).as_posix()) / MANIFEST_NAME
"""The manifest, from the checkout's root, beside the agent files."""


def manifest_path(root: Path = REPO_ROOT) -> Path:
    """The manifest of the checkout at `root`."""
    return root / MANIFEST


@dataclass(frozen=True)
class Rendering:
    """A generated file: where it is written, and its text."""

    path: Path
    text: str


class Unignored(SystemExit):
    """The generated files in the checkout that git does not ignore, of
    one command; the command writes none of its files."""

    def __init__(self, paths: list[PurePosixPath]) -> None:
        self.paths = paths
        super().__init__("\n".join(not_ignored_line(p) for p in paths))


def not_ignored_line(path: PurePosixPath) -> str:
    """The line that names one generated file git does not ignore."""
    return mctx("`{path}` is a generated file in the checkout, and no line "
                "of `.gitignore` ignores it.").format(path=path)


def write_whole_text(path: Path, text: str) -> Path:
    """Write a file, whole (`engine.memo.write_whole`): a reader that
    opens it while the write is in progress reads the old file or the new
    one. A file that already holds the text is left alone."""
    if path.exists() and path.read_text() == text:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    write_whole(path, text.encode())
    return path


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def in_checkout(path: Path, root: Path) -> PurePosixPath | None:
    """`path` from `root`, where it stands under it."""
    shown = checkout.shown(path, root)
    return None if shown.is_absolute() else PurePosixPath(shown.as_posix())


type Manifest = dict[PurePosixPath, str]
"""Each listed file, from the checkout's root, with its digest."""


def read_manifest(root: Path = REPO_ROOT) -> Manifest:
    """The entries of the manifest at `root`; none where it does not
    stand or does not open with `MANIFEST_HEAD`. A line that gives no digest and a path inside the checkout is
    a fault."""
    path = manifest_path(root)
    if not path.exists():
        return {}
    lines = path.read_text().splitlines()
    if lines[:1] != [MANIFEST_HEAD]:
        return {}
    out: Manifest = {}
    for line in lines[1:]:
        digest, sep, rel = line.partition(" ")
        if not sep or len(digest) != 64:
            raise _bad_line(path, line, "gives no digest and path")
        out[_entry(path, PurePosixPath(rel), line)] = digest
    return out


def _entry(manifest: Path, rel: PurePosixPath, line: str) -> PurePosixPath:
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise _bad_line(manifest, line, "names no path inside the checkout")
    return rel


def _bad_line(manifest: Path, line: str, what: str) -> SystemExit:
    return SystemExit(f"{checkout.shown(manifest)}: `{line}` {what}; remove "
                      "the manifest to start a new one")


def _write_manifest(root: Path, entries: Manifest) -> None:
    write_whole_text(manifest_path(root), "".join(
        [f"{MANIFEST_HEAD}\n",
         *(f"{entries[rel]} {rel}\n" for rel in sorted(entries))]))


def _ignored(root: Path, paths: list[PurePosixPath]) -> set[PurePosixPath]:
    """Of `paths`, from `root`, those git ignores, in one `git
    check-ignore` call. A tracked path is not ignored."""
    if not paths:
        return set()
    stdin = "".join(f"{p}\0" for p in paths)
    done = checkout.git(root, "check-ignore", "-z", "--stdin", stdin=stdin)
    # 0: some path is ignored; 1: none is.
    if done.returncode not in (0, 1):
        raise checkout.GitFailed(root, ["check-ignore", "-z", "--stdin"],
                                 done.stderr)
    return {PurePosixPath(p) for p in done.stdout.split("\0") if p}


class Kept(Enum):
    """Why a listed file no rendering has stays in place."""

    NOT_IGNORED = "git does not ignore it"
    EDITED = "it changed since it was written"


@dataclass(frozen=True)
class Left:
    """A listed file no rendering has, left in place."""

    path: Path
    why: Kept


@dataclass(frozen=True)
class Regenerated:
    """What `regenerate` did beyond the writes."""

    removed: list[Path]
    left: list[Left]


def write_generated(renderings: list[Rendering],
                    root: Path = REPO_ROOT) -> list[Path]:
    """Write each rendering, once git ignores each one in the checkout at
    `root`, list those in the manifest, and return the paths."""
    _write(renderings, root, stale=False)
    return [r.path for r in renderings]


def regenerate(renderings: list[Rendering],
               root: Path = REPO_ROOT) -> Regenerated:
    """`write_generated` over every rendering the sources give, then the
    removal of each listed file none of them has."""
    return _write(renderings, root, stale=True)


def _write(renderings: list[Rendering], root: Path,
           stale: bool) -> Regenerated:
    inside = {r.path: rel for r in renderings
              if (rel := in_checkout(r.path, root)) is not None}
    if not inside:
        for r in renderings:
            write_whole_text(r.path, r.text)
        return Regenerated([], [])
    listed = {rel: digest for rel, digest in read_manifest(root).items()
              if (root / rel).exists()}
    rendered = set(inside.values())
    gone = sorted(set(listed) - rendered) if stale else []
    ignored = _ignored(root, [*sorted(rendered), MANIFEST, *gone])
    unignored = sorted(p for p in [*rendered, MANIFEST] if p not in ignored)
    if unignored:
        raise Unignored(unignored)
    for r in renderings:
        write_whole_text(r.path, r.text)
    entries = {rel: digest for rel, digest in listed.items()
               if not stale or rel in rendered}
    entries |= {inside[r.path]: _digest(r.text.encode())
                for r in renderings if r.path in inside}
    removed: list[Path] = []
    left: list[Left] = []
    for rel in gone:
        path = root / rel
        if rel not in ignored:
            left.append(Left(path, Kept.NOT_IGNORED))
        elif _digest(path.read_bytes()) != listed[rel]:
            left.append(Left(path, Kept.EDITED))
        else:
            path.unlink(missing_ok=True)
            removed.append(path)
    _write_manifest(root, entries)
    return Regenerated(removed, left)

"""The review anchor of an editor: the time its work was first reviewed, kept
with a fingerprint of that work, so that each call of `operate.py review`
for work that has not changed reads the same time, whatever calls the
editor made between them.

The fingerprint of an editor's work is the bytes of its report file and the
content state of the change's worktree: `HEAD`, each path `git status`
lists there (ignored files are not listed), and the blob hash of each of
those paths that is a file. The anchor is a file `review-anchors/<agent
id>.json` of the session's scratch directory, which holds `at` and the
fingerprint."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from operations.state import Anchor


def git(worktree: Path, *args: str, stdin: bytes | None = None) -> bytes:
    """The output of `git -C worktree args`, or a `ValueError` that names
    the cause where git fails."""
    try:
        done = subprocess.run(["git", "-C", str(worktree), "--no-optional-locks", *args],
                              input=stdin, capture_output=True, check=False)
    except OSError as e:
        raise ValueError(f"git cannot run in {worktree}: {e}") from e
    if done.returncode != 0:
        raise ValueError(f"git {args[0]} fails in {worktree}: "
                         f"{done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def listed(status: bytes) -> list[str]:
    """The paths of the output of `git status --porcelain -z`, each rename
    or copy with both its paths."""
    fields = status.split(b"\0")
    paths: list[str] = []
    i = 0
    while i < len(fields) and fields[i]:
        code, path = fields[i][:2], fields[i][3:]
        paths.append(os.fsdecode(path))
        if b"R" in code or b"C" in code:
            i += 1
            paths.append(os.fsdecode(fields[i]))
        i += 1
    return paths


def fingerprint(worktree: Path, report: Path) -> str:
    """The fingerprint of the work of an editor whose report file is
    `report`, in `worktree`; a `ValueError` where the worktree or the
    report file cannot be read."""
    try:
        text = report.read_bytes()
    except OSError as e:
        raise ValueError(f"the report file {report} cannot be read: {e}") from e
    head = git(worktree, "rev-parse", "HEAD").strip()
    paths = sorted(set(listed(git(worktree, "status", "--porcelain", "-z",
                                  "--untracked-files=all"))))
    blobs: dict[str, str] = {}
    files = []
    for path in paths:
        full = worktree / path
        if full.is_symlink():
            blobs[path] = "link " + hashlib.sha256(os.fsencode(os.readlink(full))).hexdigest()
        elif full.is_file() and "\n" not in path:
            files.append(path)
        elif full.is_file():
            blobs[path] = hashlib.sha256(full.read_bytes()).hexdigest()
        else:
            blobs[path] = "none"
    if files:
        hashes = git(worktree, "hash-object", "--stdin-paths",
                     stdin="\n".join(files).encode()).decode().split()
        blobs.update(zip(files, hashes, strict=True))
    digest = hashlib.sha256()
    for part in (text, head, json.dumps(blobs, sort_keys=True).encode()):
        digest.update(hashlib.sha256(part).digest())
    return digest.hexdigest()


def anchor_file(scratch: Path, agent: str) -> Path:
    return scratch / "review-anchors" / f"{agent}.json"


def read_anchor(scratch: Path | None, agent: str | None) -> Anchor | None:
    """The anchor of the editor `agent`, or None where it has none."""
    if scratch is None or agent is None:
        return None
    try:
        value = json.loads(anchor_file(scratch, agent).read_text())
        return Anchor(float(value["at"]), str(value["fingerprint"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def anchored(scratch: Path, agent: str, current: str, now: float) -> float:
    """The `at` of the anchor of the editor `agent` where its fingerprint
    is `current`; otherwise write the anchor `now` and `current` give, and
    return `now`."""
    kept = read_anchor(scratch, agent)
    if kept is not None and kept.fingerprint == current:
        return kept.at
    target = anchor_file(scratch, agent)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps({"at": now, "fingerprint": current}))
    os.replace(temporary, target)
    return now

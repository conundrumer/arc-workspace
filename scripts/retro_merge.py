"""Take a worktree's whole change into the repo it came from. Deprecated.

    uv run python scripts/retro_merge.py <worktree> [--check]

The worktree's change against HEAD becomes one patch: the tracked edits and
the new files alike, everywhere outside `.scratch/` and what `.gitignore`
covers. `git apply --check` reads that patch in the target tree first. With
`--check` the script stops there and reports whether the patch applies.

Without `--check` the script copies the worktree's `.scratch/retro/diffs/`
files into the target tree, so a diff path written in the worktree still
resolves after the worktree is gone. It then applies the patch and removes
the worktree with `git worktree remove --force`. A patch the target tree
refuses leaves that tree and the worktree as they are.

The target tree is the main worktree of the repo the worktree belongs to.
`--into <path>` names another tree instead.

The script prints one JSON object:

    applied    whether the patch applies, under `--check`; whether it was
               applied, otherwise
    files      the repo-relative paths the patch covers
    conflict   what `git apply` reported when it refused; empty otherwise

Two applies on one tree can race, so a caller runs one merge at a time.

Exit status: 0 when the patch applies, 1 when it does not, 2 when the call
itself is malformed.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Where a retro agent writes its diffs, under the tree it worked in.
DIFF_DIR = Path(".scratch") / "retro" / "diffs"
# The paths the patch covers: everything the tree tracks, less the scratch
# directory. `--exclude-standard` drops what `.gitignore` covers, `.venv/`
# among it.
PATHSPEC = [".", ":(exclude).scratch"]
# Bytes of a refusal kept for the caller's report.
TAIL = 2000


def git(cwd: Path, *argv: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """One git command in `cwd`."""
    return subprocess.run(["git", *argv], cwd=cwd, input=stdin,
                          capture_output=True, text=True)


def main_tree(worktree: Path) -> Path:
    """The main worktree of the repo `worktree` belongs to."""
    done = git(worktree, "rev-parse", "--git-common-dir")
    if done.returncode != 0:
        raise RuntimeError(f"{worktree} is no git worktree: {done.stderr.strip()}")
    common = Path(done.stdout.strip())
    if not common.is_absolute():
        common = (worktree / common).resolve()
    return common.parent


def new_files(worktree: Path) -> list[str]:
    """The files the worktree holds that git does not track."""
    done = git(worktree, "ls-files", "--others", "--exclude-standard", "--", *PATHSPEC)
    if done.returncode != 0:
        raise RuntimeError(f"listing the new files of {worktree} failed: {done.stderr.strip()}")
    return [line for line in done.stdout.splitlines() if line]


def tracked_patch(worktree: Path) -> tuple[str, list[str]]:
    """The change to the tracked files against HEAD, and the paths it covers."""
    diff = git(worktree, "diff", "HEAD", "--binary", "--", *PATHSPEC)
    if diff.returncode != 0:
        raise RuntimeError(f"diffing {worktree} against HEAD failed: {diff.stderr.strip()}")
    names = git(worktree, "diff", "--name-only", "HEAD", "--", *PATHSPEC)
    return diff.stdout, [line for line in names.stdout.splitlines() if line]


def patch_text(worktree: Path) -> tuple[str, list[str]]:
    """The worktree's whole change as one patch, and the paths it covers. A
    new file carries no HEAD side, so it takes a diff against `/dev/null`."""
    patch, files = tracked_patch(worktree)
    for path in new_files(worktree):
        # git reports a difference with status 1, and a failure with 2.
        done = git(worktree, "diff", "--no-index", "--binary", "--", "/dev/null", path)
        if done.returncode > 1:
            raise RuntimeError(f"diffing the new file {path} failed: {done.stderr.strip()}")
        patch += done.stdout
        files.append(path)
    return patch, sorted(set(files))


def apply_patch(into: Path, patch: str, check: bool = False) -> str:
    """Apply the patch in `into`, or read it alone under `check`. The return
    is what git reported when it refused, and empty when it did not."""
    if not patch.strip():
        return ""
    argv = ["apply", "--whitespace=nowarn"] + (["--check"] if check else [])
    done = git(into, *argv, "-", stdin=patch)
    if done.returncode == 0:
        return ""
    said = (done.stderr + done.stdout).strip()
    return (said or f"git apply exited with {done.returncode}")[-TAIL:]


def copy_diffs(worktree: Path, into: Path) -> list[str]:
    """Copy the diff files the worktree holds into the target tree, so a path
    a fix reported still resolves there. The return is the paths copied."""
    source = worktree / DIFF_DIR
    if not source.is_dir():
        return []
    target = into / DIFF_DIR
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target / rel)
        copied.append(str(DIFF_DIR / rel))
    return copied


def remove_worktree(owner: Path, worktree: Path) -> str:
    """Remove the worktree from the repo that holds it. The return is what
    git reported when it refused, and empty when it did not."""
    done = git(owner, "worktree", "remove", "--force", str(worktree))
    return "" if done.returncode == 0 else (done.stderr + done.stdout).strip()[-TAIL:]


def merge(worktree: Path, into: Path | None = None, check: bool = False) -> dict[str, object]:
    """Take the worktree's change into `into`, the repo's main worktree when
    no other tree is named."""
    worktree = worktree.resolve()
    owner = main_tree(worktree)
    target = (into or owner).resolve()
    patch, files = patch_text(worktree)
    conflict = apply_patch(target, patch, check=True)
    if conflict or check:
        return {"applied": not conflict, "files": files, "conflict": conflict}
    copy_diffs(worktree, target)
    conflict = apply_patch(target, patch)
    if conflict:
        return {"applied": False, "files": files, "conflict": conflict}
    refused = remove_worktree(owner, worktree)
    if refused:
        print(f"retro_merge: the patch applied and {worktree} stays: {refused}", file=sys.stderr)
    return {"applied": True, "files": files, "conflict": ""}


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("worktree", type=Path, help="the worktree to take the change from")
    ap.add_argument("--check", action="store_true",
                    help="report whether the patch applies, and write nothing")
    ap.add_argument("--into", type=Path,
                    help="the tree to apply the patch to; the repo's main worktree when absent")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.worktree.is_dir():
        print(f"retro_merge: {args.worktree} is no directory", file=sys.stderr)
        return 2
    try:
        result = merge(args.worktree, args.into, args.check)
    except RuntimeError as exc:
        print(f"retro_merge: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["applied"] else 1


if __name__ == "__main__":
    sys.exit(main())

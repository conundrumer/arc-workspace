"""The kept `context --update` runs that the update texts of
`scripts/reader_commits.py` come from.

A `context --update` run that succeeds is kept under `checkout.cache()`,
keyed by its arguments, the held texts it reads, its tree's `HEAD`, and the
path and content of each file `git status` lists in that tree, so that a
later update with the same key, of any reader in any session, gives the
kept output in place of a run. Of two updates with one key at once, the
second waits for the first's run and gives what it kept. A file git
ignores is not in the key."""

import hashlib
import json
import subprocess
from pathlib import Path
from typing import NamedTuple

UPDATE_CACHE = "reader-updates"


class Run(NamedTuple):
    command: str
    returncode: int
    stdout: str
    stderr: str


def _status_digest(tree: Path) -> str:
    from engine import checkout
    from engine.memo import hash_files

    listed = checkout.git_out(tree, "status", "--porcelain=v1", "-z",
                              "--untracked-files=all", "--no-renames")
    h = hashlib.sha256()
    hash_files(h, ((name, tree / name)
                   for name in sorted(entry[3:] for entry in listed.split("\0") if entry)))
    return h.hexdigest()


def cached_run(tree: Path, after: str, args: list[str],
             held: tuple[str, str] | None = None) -> Run:
    """The `context --update` run with `args` in `tree`, whose `HEAD` is
    `after`, kept as the module docstring gives; with `held`, the texts the
    `--held` form reads from its two files."""
    import tempfile

    from engine import checkout
    from handbook.kept_runs import CONTEXT_SCRIPT, kept
    from handbook.reader_diffs import PROJECT_INSTRUCTIONS

    def made() -> tuple[Run, bool]:
        with tempfile.TemporaryDirectory() as tmp:
            files = [Path(tmp) / "context", Path(tmp) / PROJECT_INSTRUCTIONS]
            for file, text in zip(files, held or (), strict=False):
                file.write_text(text)
            argv = ["uv", "run", "python", str(CONTEXT_SCRIPT), "context", "--update",
                    *(["--held", *map(str, files)] if held else []), *args]
            done = subprocess.run(argv, cwd=tree, env=checkout.tree_env(),
                                  capture_output=True, text=True)
        run = Run(" ".join(argv), done.returncode, done.stdout, done.stderr)
        return run, run.returncode == 0

    parts = [after, *args, *(held or ()), "held" if held else "", _status_digest(tree)]
    return kept(UPDATE_CACHE, parts, ".json", lambda data: Run(*json.loads(data)),
                lambda run: json.dumps(run).encode(), made)

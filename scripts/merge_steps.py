"""The checks `merge_change.py` runs on the top of its stack, and the steps
it runs in the main tree after the fast-forward, run in the tree this
script is run in.

    uv run python scripts/merge_steps.py checks [--engine-passed <commit>] <base> [<gate-out>]
    uv run python scripts/merge_steps.py after [<gate-out>]

The `--help` of `merge_change.py` says which checks and steps these are,
when it runs each form, which copy of this script it runs, and what
`<base>` is. `<gate-out>` is accepted and unused: the `merge_change.py` on
`master` before the gate was removed passes it.

`checks` runs the checks concurrently. The engine checks run where the
changes touch a path under `engine/`. With `--engine-passed <commit>`, the
commit on which they last passed, they run again only where the `engine/`
tree of `<commit>` differs from that of the tree checked: equal trees build
and test the same, as no engine source or test reads a file outside
`engine/`.

The engine checks run in the kept tree, `merge-engine` under the `.cache/`
of the repository's main worktree: a detached worktree that each call moves
to the `HEAD` of the tree checked (`git checkout --detach --force` and
`git clean -fdq`, which leave `engine/target`), so that git rewrites only
the files the two commits differ in and cargo compiles again only the
crates they change. The call holds an exclusive lock on `merge-engine.lock`
beside it through the engine checks. The kept tree holds no submodule. The
environment of the cargo commands (`engine_env`) is the same at every merge:
no `VIRTUAL_ENV`, `CONDA_PREFIX` or `PYO3_*` variable, a `PATH` with no
`.venv/bin` entry, and `PYO3_PYTHON` the Python of the main tree's `.venv`,
as pyo3's build script reruns where a variable it reads changes. The
checks fail where the tree checked holds an `engine/` edit that its `HEAD`
lacks, before any cargo run.

The engine checks test and document the crates of the workspace that hold a
path the changes touch and the crates that depend on one of them, directly
or through others (`tested`), by `-p`; where a touched path under `engine/`
lies in no crate's directory (`Cargo.toml`, `Cargo.lock`, `lib/`), or those
crates are all of them, they take `--workspace`. This rests on the fact
that no crate's source, build script or test reads a file in the directory
of a crate it does not depend on. The reads of other directories are the
`include_str!` of `engine/lib/` in `arclog`, `engine/arclog-py/build.rs`,
which reads its own path dependencies and `engine/lib/`, and
`arclog-cli`'s `check_diff::checkout`, which no test calls.

Each line that shows a check's name as it starts, and each step line
(`engine.duration.STEP`) a check writes, goes on stderr as it comes, and
the output of each check that fails goes on stdout.

`after` runs the steps in order, stops at the first that fails, and prints
the stdout of each step it runs. For a step that fails, it then prints the
step's command and the last lines of its output.

Exit status: 0 where each check or step passes, 1 where one fails, 2 when
the call itself is malformed.
"""

import argparse
import contextlib
import fcntl
import json
import os
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

from engine import checkout
from handbook.kept_trees import flocked
from handbook.paths import scripts_importable

scripts_importable()

from change_checks import Check, changed_outside_work, failures, run_in, said  # noqa: E402
from operations.merging import CHECK_FAILED, CONTEXT_WRITE, DOCUMENT_CHECKS  # noqa: E402

DOCUMENT_PASS = ("scripts/document_pass.py",)
"""The command, after `uv run python`, that files a whole-document pass."""

ENGINE = "engine/"
"""The directory of the Cargo workspace."""

KEPT = "merge-engine"
"""The directory under the `.cache/` of the main worktree that holds the
kept tree (`kept_tree`)."""

ENGINE_EDITS = "the tree checked holds no edit to engine/ outside HEAD"
"""The name of the check that the tree checked holds no change to `engine/`
that its `HEAD` lacks."""


def selection(selected: tuple[str, ...] | None) -> tuple[str, ...]:
    """The arguments of a cargo command that choose its crates: the
    workspace where `selected` is None, else the crates of `selected`."""
    if selected is None:
        return ("--workspace",)
    return tuple(arg for member in selected for arg in ("-p", member))


def engine_check(selected: tuple[str, ...] | None) -> tuple[str, ...]:
    """The check that compiles every target of each crate of `selected`
    (`tested`) under `ENGINE`, from the crates already fetched, and runs
    every test of those crates, giving each test that fails."""
    return ("cargo", "test", "--manifest-path", f"{ENGINE}Cargo.toml", *selection(selected),
            "--offline", "--no-fail-fast")


def engine_doc_check(selected: tuple[str, ...] | None) -> tuple[str, ...]:
    """The check that builds the documentation of each crate of `selected`
    (`tested`) under `ENGINE`, from the crates already fetched, and fails
    on each rustdoc warning, such as a link from a public item's doc to a
    private item."""
    return ("env", "RUSTDOCFLAGS=-D warnings", "cargo", "doc", "--manifest-path",
            f"{ENGINE}Cargo.toml", *selection(selected), "--no-deps", "--offline")


def engine_runs(tree: Path, base: str, passed: str | None) -> bool:
    """Whether the engine checks run in `tree` for changes from the commit
    `base`: the changes touch a path under `ENGINE`, and, where `passed` is
    the commit on which they last passed, its `ENGINE` tree differs from
    that of `tree`'s `HEAD`."""
    if not any(p.startswith(ENGINE) for p in changed_outside_work(tree, base)):
        return False
    if passed is None:
        return True
    directory = ENGINE.rstrip("/")
    return (checkout.git_out(tree, "rev-parse", f"{passed}:{directory}")
            != checkout.git_out(tree, "rev-parse", f"HEAD:{directory}"))


@contextlib.contextmanager
def kept_tree(tree: Path) -> Iterator[Path]:
    """The kept tree, `KEPT` under the `.cache/` of the main worktree of
    `tree`'s repository, at `tree`'s `HEAD`, with its lock held for the
    block. It is a detached worktree of the repository, made where it does
    not stand, and otherwise moved to the commit, which rewrites only the
    files the two commits differ in, so that cargo rebuilds only the crates
    they change; `engine/target` stays, as git ignores it."""
    kept = checkout.main_worktree(tree) / ".cache" / KEPT
    head = checkout.git_out(tree, "rev-parse", "HEAD").strip()
    with flocked(kept.with_name(f"{KEPT}.lock"), fcntl.LOCK_EX):
        if (kept / ".git").exists():
            checkout.git_out(kept, "checkout", "--detach", "--force", head)
            checkout.git_out(kept, "clean", "-fdq")
        else:
            checkout.git_out(tree, "worktree", "prune")
            checkout.git_out(tree, "worktree", "add", "--detach", str(kept), head)
        yield kept


def engine_env() -> dict[str, str]:
    """The environment of the cargo commands, the same at every merge
    whatever tree or environment the call started from: no `VIRTUAL_ENV`,
    `CONDA_PREFIX` or `PYO3_*` variable, a `PATH` with no `.venv/bin`
    entry, and `PYO3_PYTHON` the Python of the main tree's `.venv`."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("VIRTUAL_ENV", "CONDA_PREFIX") and not k.startswith("PYO3_")}
    entries = [e for e in env["PATH"].split(os.pathsep)
               if Path(e).parts[-2:] != (".venv", "bin")]
    env["PATH"] = os.pathsep.join(entries)
    env["PYO3_PYTHON"] = str(checkout.main_worktree(checkout.ROOT) / ".venv" / "bin" / "python")
    return env


def members(kept: Path) -> tuple[dict[str, str], dict[str, set[str]]]:
    """The workspace of the kept tree `kept` from `cargo metadata`: the
    directory of each member, from the root of the tree, by name, and, by
    name, the members that depend on it over a path dependency of any
    kind."""
    done = subprocess.run(
        ["cargo", "metadata", "--manifest-path", f"{ENGINE}Cargo.toml", "--format-version", "1",
         "--no-deps", "--offline"], cwd=kept, env=engine_env(), capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"cargo metadata failed in {kept}: {done.stderr.strip()}")
    packages = {m["name"]: m for m in json.loads(done.stdout)["packages"]}
    root = kept.resolve()
    directories = {name: Path(m["manifest_path"]).parent.relative_to(root).as_posix()
                   for name, m in packages.items()}
    dependents: dict[str, set[str]] = {name: set() for name in packages}
    for name, m in packages.items():
        for dependency in m["dependencies"]:
            if dependency.get("path") is not None and dependency["name"] in packages:
                dependents[dependency["name"]].add(name)
    return directories, dependents


def tested(kept: Path, base: str) -> tuple[str, ...] | None:
    """The crates the engine checks test and document for changes from the
    commit `base`, in the kept tree `kept`: each member of the workspace
    whose directory holds a path the changes touch, and each member that
    depends on one of them, directly or through others, over normal, build
    and dev dependencies. None, for the whole workspace, where a touched
    path under `ENGINE` lies in no member's directory, or where those
    members are all of them."""
    directories, dependents = members(kept)
    reached: set[str] = set()
    for path in (p for p in changed_outside_work(kept, base) if p.startswith(ENGINE)):
        holding = [n for n, d in directories.items() if path.startswith(f"{d}/")]
        if not holding:
            return None
        reached.add(max(holding, key=lambda n: len(directories[n])))
    pending = list(reached)
    while pending:
        for name in dependents[pending.pop()] - reached:
            reached.add(name)
            pending.append(name)
    return None if reached == directories.keys() else tuple(sorted(reached))


def checks(tree: Path, base: str, engine_passed: str | None = None) -> list[str]:
    """Run in `tree` the checks of changes from the commit `base`: the
    output of each that fails. Where `engine_runs` holds for
    `engine_passed`, the compile and the tests of the engine
    (`engine_check`) and its documentation build (`engine_doc_check`) are
    among them, run in the kept tree (`kept_tree`) in `engine_env()`, for
    the crates `tested` gives, and a `tree` that holds an `engine/` edit
    outside its `HEAD` fails the check `ENGINE_EDITS`, with no cargo run."""
    engine = engine_runs(tree, base, engine_passed)
    common = list(map(Check, DOCUMENT_CHECKS))
    with contextlib.redirect_stdout(sys.stderr):
        if not engine:
            return failures(tree, common)
        if edits := [c.path for c in checkout.changed_paths(tree, "HEAD", ENGINE)]:
            return [CHECK_FAILED.format(s=ENGINE_EDITS) + "\n" + "\n".join(edits)]
        with kept_tree(tree) as kept:
            selected = tested(kept, base)
            env = engine_env()
            return failures(tree, [*common,
                                   *(Check(argv, cwd=kept, env=env)
                                     for argv in (engine_check(selected), engine_doc_check(selected)))])


def after(tree: Path) -> bool:
    """Run in `tree` the steps after the fast-forward, in order, up to the
    first that fails; whether each passes."""
    for argv in (CONTEXT_WRITE, DOCUMENT_PASS):
        shown = " ".join(argv)
        done = run_in(tree, ("uv", "run", "python", *argv))
        print(done.stdout, end="", flush=True)
        if done.returncode != 0:
            print(f"{shown}:\n{said(done)}", flush=True)
            return False
    return True


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    forms = ap.add_subparsers(dest="form", required=True)
    on_checks = forms.add_parser("checks", help="run the checks on the changes")
    on_checks.add_argument("--engine-passed", metavar="COMMIT",
                           help="the commit on which the engine checks last passed")
    on_checks.add_argument("base", help="the commit the changes stand on")
    on_checks.add_argument("gate_out", nargs="?", help="accepted and unused")
    on_after = forms.add_parser("after", help="run the steps after the fast-forward")
    on_after.add_argument("gate_out", nargs="?", help="accepted and unused")
    a = ap.parse_args(argv)
    tree = Path(checkout.git_out(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    if a.form == "after":
        return 0 if after(tree) else 1
    failed = checks(tree, a.base, a.engine_passed)
    print("\n".join(failed), end="\n" if failed else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

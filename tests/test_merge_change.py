"""What the forced removal of a merged worktree would lose, which the script
refuses before the commit and fails on before the removal: files inside
its submodules, and, before the commit alone, submodule
commits that only the worktree's own copies of the submodules' repositories
hold. Before the removal, the script also moves the files under its
`work/` to the main tree's, and fails on a file whose path there is
taken. A file the main tree holds untracked and a change holds a copy of keeps
its main-tree content where a pass edited it after the copy, which the
merge refuses, and where the fast-forward fails after its removal, which
writes it back; a copied file the change left as copied is in no
commit. The merge makes the readers' tree of the old `master` before the
fast-forward, and fast-forwards where that make fails. The checks run by
the command lines of the tree they check, by the main tree's copy of
`merge_steps.py` where the changes touch it, and refuse changes to `engine/`
where the engine does not compile."""

import os
import subprocess
import sys
from pathlib import Path

from types import SimpleNamespace

import pytest

from tests.conftest import script

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


@pytest.fixture(scope="module")
def merge_change():
    return script("merge_change")


@pytest.fixture(autouse=True)
def no_refresh_of_this_session(merge_change, tmp_path: Path,
                               monkeypatch: pytest.MonkeyPatch) -> None:
    """The refresh locks a merge takes stand under `tmp_path`, and for no
    session of the environment."""
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.setattr(sys.modules["refresh_locks"].checkout, "caches",
                        lambda: tmp_path / "caches")


def git(cwd: Path, *argv: str) -> str:
    done = subprocess.run(["git", "-c", "protocol.file.allow=always", *argv], cwd=cwd,
                          env=ENV, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def commit_file(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)


@pytest.fixture
def trees(tmp_path: Path, merge_change) -> tuple[Path, Path]:
    """A main tree with a submodule `s`, and a worktree on a branch of its
    own whose submodule the script has set up."""
    sub, main, worktree = tmp_path / "sub", tmp_path / "main", tmp_path / "worktree"
    for repo in (sub, main):
        repo.mkdir()
        git(repo, "init", "-q", "-b", "master")
        commit_file(repo, "a")
    git(main, "submodule", "add", "-q", str(sub), "s")
    git(main, "commit", "-q", "-m", "s")
    git(main, "worktree", "add", "-q", str(worktree), "-b", "change")
    main, worktree = main.resolve(), worktree.resolve()
    merge_change.set_up_submodules(worktree, main)
    return main, worktree


def test_untracked_file_in_submodule_is_refused(merge_change, trees):
    _, worktree = trees
    merge_change.refuse_dirty_submodules(worktree)
    (worktree / "s" / "new").write_text("new")
    with pytest.raises(merge_change.Refused, match="s/new"):
        merge_change.refuse_dirty_submodules(worktree)


def test_submodule_commit_the_main_tree_lacks_is_refused(merge_change, trees, tmp_path):
    main, worktree = trees
    commit_file(worktree / "s", "b")
    with pytest.raises(merge_change.Refused, match="lack"):
        merge_change.stage(worktree, main, tmp_path / "index", "HEAD")
    assert git(worktree, "diff", "--cached", "--name-only") == ""


def test_unlisted_gitlink_is_refused(merge_change, trees, tmp_path):
    main, worktree = trees
    nested = worktree / "nested"
    nested.mkdir()
    git(nested, "init", "-q", "-b", "master")
    commit_file(nested, "n")
    with pytest.raises(merge_change.Refused, match="does not list"):
        merge_change.stage(worktree, main, tmp_path / "index", "HEAD")
    assert git(worktree, "diff", "--cached", "--name-only") == ""


def test_change_refused_in_a_stack_reaches_master_through_no_other(
        merge_change, tmp_path, monkeypatch):
    """A change stacked on a refused one merges alone, without the refused
    change's commit beneath it."""
    sub, main = tmp_path / "sub", tmp_path / "main"
    first, second = tmp_path / "first", tmp_path / "second"
    for repo in (sub, main):
        repo.mkdir()
        git(repo, "init", "-q", "-b", "master")
        commit_file(repo, "a")
    git(main, "submodule", "add", "-q", str(sub), "s")
    git(main, "commit", "-q", "-m", "s")
    git(main, "worktree", "add", "-q", str(first), "-b", "first")
    git(main, "worktree", "add", "-q", str(second), "-b", "second")
    main, first, second = main.resolve(), first.resolve(), second.resolve()
    (first / "bad").write_text("bad")
    (second / "good").write_text("good")

    def check(tree: Path, main: Path, base: str, touched: set[str]) -> None:
        if (tree / "bad").exists():
            raise merge_change.Refused("bad")

    monkeypatch.setattr(merge_change, "check", check)
    monkeypatch.setattr(merge_change, "run_in",
                        lambda tree, argv: subprocess.CompletedProcess(argv, 0, "", ""))
    for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, ENV[k])
    assert not merge_change.merge([(first, "first"), (second, "second")])
    assert git(main, "ls-tree", "--name-only", "master").split() == [
        ".gitmodules", "a", "good", "s"]
    assert git(first, "status", "--porcelain").split() == ["??", "bad"]


def test_untracked_file_in_submodule_keeps_the_worktree(merge_change, trees):
    main, worktree = trees
    (worktree / "s" / "new").write_text("new")
    change = merge_change.Change(worktree, "change", frozenset(), "", None, "")
    with pytest.raises(merge_change.Failed, match="s/new"):
        merge_change.remove(main, change)
    assert (worktree / "s" / "new").exists()


def ignore_work(main: Path) -> None:
    with (main / ".git" / "info" / "exclude").open("a") as f:
        f.write("/work\n")


def test_work_files_move_to_the_main_tree_or_keep_the_worktree(merge_change, trees):
    main, worktree = trees
    ignore_work(main)
    for tree, name in ((main, "old"), (worktree, "old"), (worktree, "new")):
        (tree / "work" / "t").mkdir(parents=True, exist_ok=True)
        (tree / "work" / "t" / name).write_text(str(tree))
    change = merge_change.Change(worktree, "change", frozenset(), "", None, "")
    with pytest.raises(merge_change.Failed, match="work/t/old"):
        merge_change.remove(main, change)
    assert (main / "work" / "t" / "new").read_text() == str(worktree)
    assert (main / "work" / "t" / "old").read_text() == str(main)
    assert (worktree / "work" / "t" / "old").read_text() == str(worktree)
    (worktree / "work" / "t" / "old").unlink()
    merge_change.remove(main, change)
    assert not worktree.exists()


def test_work_is_never_staged(merge_change, trees, tmp_path):
    main, worktree = trees
    (main / "work").mkdir()
    (worktree / "work").symlink_to(main / "work")
    (worktree / "b").write_text("b")
    merge_change.stage(worktree, main, tmp_path / "index", "HEAD")
    assert git(worktree, "diff", "--cached", "--name-only").split() == ["b"]


def test_work_link_is_removed_alone(merge_change, trees):
    main, worktree = trees
    ignore_work(main)
    (main / "work").mkdir()
    (main / "work" / "kept").write_text("kept")
    (worktree / "work").symlink_to(main / "work")
    merge_change.remove(main, merge_change.Change(worktree, "change", frozenset(), "", None, ""))
    assert not worktree.exists()
    assert (main / "work" / "kept").read_text() == "kept"


@pytest.fixture
def carrying(trees, tmp_path, merge_change, monkeypatch):
    """The main tree of `trees` with the untracked file `p/u`, which the
    worktree holds a copy of, and the checks and the main tree's commands stubbed
    out."""
    main, worktree = trees
    (main / "p").mkdir()
    (main / "p" / "u").write_text("pass")
    ticket = tmp_path / "ticket.md"
    ticket.write_text("# t\n\n## Scope\n- `p/u`\n")
    script("change_worktree").copy_scope_untracked(main, worktree, SimpleNamespace(path=ticket))
    (worktree / "p" / "u").write_text("edited")
    monkeypatch.setattr(merge_change, "check", lambda *a: tmp_path)
    monkeypatch.setattr(merge_change, "run_in",
                        lambda tree, argv: subprocess.CompletedProcess(argv, 0, "", ""))
    for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, ENV[k])
    return main, worktree


def test_carried_file_edited_in_the_main_tree_is_refused(merge_change, carrying):
    main, worktree = carrying
    (main / "p" / "u").write_text("pass, edited")
    assert not merge_change.merge([(worktree, "m")])
    assert (main / "p" / "u").read_text() == "pass, edited"


def test_carried_file_left_as_copied_is_in_no_commit(merge_change, carrying):
    main, worktree = carrying
    (worktree / "p" / "u").write_text("pass")
    (worktree / "b").write_text("b")
    assert merge_change.merge([(worktree, "m")])
    assert git(main, "ls-files", "--", "p/u") == ""
    assert (main / "p" / "u").read_text() == "pass"


def test_carried_file_is_written_back_where_the_fast_forward_fails(
        merge_change, carrying, monkeypatch):
    main, worktree = carrying
    git_ = merge_change.checkout.git

    def failing(tree, *argv, **kw):
        if argv[:1] == ("merge",):
            return subprocess.CompletedProcess(argv, 1, "", "")
        return git_(tree, *argv, **kw)

    monkeypatch.setattr(merge_change.checkout, "git", failing)
    with pytest.raises(merge_change.Failed):
        merge_change.merge([(worktree, "m")])
    assert (main / "p" / "u").read_text() == "pass"


def test_the_tree_is_made_before_the_fast_forward_and_its_failure_merges(
        merge_change, carrying, monkeypatch):
    main, worktree = carrying
    steps: list[str] = []
    git_ = merge_change.checkout.git

    def run_in(tree, argv):
        steps.append(" ".join(argv))
        return subprocess.CompletedProcess(argv, 0 if "--keep-tree" not in argv else 1, "", "")

    def recorded(tree, *argv, **kw):
        if argv[:1] == ("merge",):
            steps.append("merge")
        return git_(tree, *argv, **kw)

    monkeypatch.setattr(merge_change, "run_in", run_in)
    monkeypatch.setattr(merge_change.checkout, "git", recorded)
    merge_change.merge([(worktree, "m")])
    keep = " ".join(("uv", "run", "python", *merge_change.TREE_KEEP))
    assert steps[:2] == [keep, "merge"]
    assert (main / "p" / "u").read_text() == "edited"


GATE = '''import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--since")
ap.add_argument("out")
ap.parse_args()
'''

STEPS = '''import subprocess, sys
assert sys.argv[1] == "checks" and len(sys.argv) == 4
done = subprocess.run([sys.executable, "scripts/gate.py", "--since", *sys.argv[2:]],
                      capture_output=True, text=True)
print(done.stderr, end="")
sys.exit(done.returncode and 1)
'''


def test_the_checks_run_the_command_lines_of_the_tree_checked(merge_change, trees):
    """A change whose gate takes `--since` in place of `--affected` passes
    the checks, which its own `merge_steps.py` runs; the main tree's passes
    `--affected`, which that gate refuses."""
    main, worktree = trees
    (worktree / "scripts").mkdir()
    (worktree / "scripts" / "gate.py").write_text(GATE)
    (worktree / "scripts" / "merge_steps.py").write_text(STEPS)
    base = git(worktree, "rev-parse", "HEAD").strip()
    merge_change.check(worktree, main, base, {"p"})
    (worktree / "scripts" / "merge_steps.py").write_text(
        STEPS.replace('"--since"', '"--affected"'))
    with pytest.raises(merge_change.Refused, match="unrecognized arguments: --affected"):
        merge_change.check(worktree, main, base, {"p"})



def test_a_change_to_merge_steps_is_checked_by_the_main_trees_copy(merge_change, trees):
    """A change whose `merge_steps.py` refuses the command line
    `merge_change.py` gives passes the checks, which the main tree's copy
    runs in the worktree."""
    main, worktree = trees
    (worktree / "scripts").mkdir()
    (worktree / "scripts" / "gate.py").write_text(GATE)
    (worktree / "scripts" / "merge_steps.py").write_text('print("refused")\nraise SystemExit(1)\n')
    (main / "scripts").mkdir()
    (main / "scripts" / "merge_steps.py").write_text(STEPS)
    base = git(worktree, "rev-parse", "HEAD").strip()
    merge_change.check(worktree, main, base, {"p", "scripts/merge_steps.py"})
    with pytest.raises(merge_change.Refused, match="refused"):
        merge_change.check(worktree, main, base, {"p"})


CRATE = """[package]
name = "e"
version = "0.0.0"
edition = "2021"
"""


def test_the_checks_refuse_an_engine_that_does_not_compile(trees, monkeypatch):
    """A change under `engine/` whose crate does not compile is refused; a
    change that touches no path under `engine/` is not, though the engine
    it stands on does not compile."""
    steps = script("merge_steps")
    monkeypatch.setattr(steps, "DOCUMENT_CHECKS", ())
    _, worktree = trees
    (worktree / "scripts").mkdir()
    (worktree / "scripts" / "gate.py").write_text("")
    (worktree / "engine" / "src").mkdir(parents=True)
    (worktree / "engine" / "Cargo.toml").write_text(CRATE)
    (worktree / "engine" / "src" / "lib.rs").write_text("pub fn f() -> u8 { \"\" }\n")
    base = git(worktree, "rev-parse", "HEAD").strip()
    failed = steps.checks(worktree, base, str(worktree / "out"))
    assert len(failed) == 1 and "mismatched types" in failed[0]
    git(worktree, "add", "-A")
    git(worktree, "commit", "-q", "-m", "e")
    base = git(worktree, "rev-parse", "HEAD").strip()
    commit_file(worktree, "p")
    assert steps.checks(worktree, base, str(worktree / "out")) == []

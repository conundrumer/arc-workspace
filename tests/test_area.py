"""The `References` list of `area.py`. A file it leaves out is an
interaction the analyst who reads it misses, in silence."""

import subprocess
from pathlib import Path

from tests.conftest import script

area = script("area")

FILES = {
    ".gitignore": "ignored/\n",
    "pkg/__init__.py": "",
    "pkg/target.py": "X = 1\n\n\ndef f():\n    return X\n",
    "takes.py": "from pkg.target import f\n\n\nf()\n",
    "reads.py": "import pkg.target\n\nprint(pkg.target.X)\n",
    "loads.py": "MODULE = 'pkg.target'\n",
    "doc.md": "# Doc\n\nSee [target](pkg/target.py).\n",
    "ignored/note.md": "pkg/target.py\n",
}


def git(root: Path, *argv: str) -> None:
    subprocess.run(["git", "-C", str(root), *argv], check=True, capture_output=True,
                   env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def test_references_give_each_kind_and_leave_out_copies_and_ignored_files(tmp_path):
    for path, text in FILES.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text)
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "tree")
    git(tmp_path, "worktree", "add", "-q", "--detach", ".claude/worktrees/copy")

    found = area.references(tmp_path, ["pkg/target.py"])

    assert {path for path, _ in found.rows} == {"takes.py", "reads.py", "loads.py", "doc.md"}
    takes = found.rows["takes.py", "pkg/target.py"]
    assert (takes.imports, takes.uses) == ([1], {"f": [4]})
    reads = found.rows["reads.py", "pkg/target.py"]
    assert (reads.imports, reads.uses) == ([1], {"X": [3]})
    assert found.rows["loads.py", "pkg/target.py"].loads == [1]
    assert found.rows["doc.md", "pkg/target.py"].names == [3]

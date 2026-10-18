"""The Controlled Markdown parser and formatter.

A parser of an external format that accepts wrong input fails silently, so the
cases under `controlled_markdown_cases/` are pinned here. Each case names its
expectation in its first line under any front matter, `+ expect: ok` or
`+ expect: error <rule>`.
"""

import re
import subprocess
from pathlib import Path

import pytest

from controlled_markdown import (
    ControlledMarkdownError,
    Registry,
    check_blocks,
    carry_errors,
    check_links,
    check_order,
    check_xrefs,
    handbook_sections,
    parse,
    render,
    round_trips,
    split_front,
    touched,
    write,
)
from controlled_markdown.__main__ import run_in_main, xrefs_documents

CASES = sorted((Path(__file__).parent / "controlled_markdown_cases").glob("*.md"))
EXPECT_RE = re.compile(r"^\+ expect: (ok|error (\S+))\s*$")

# The rules a render raises, not the parser. A case for one of these parses.
RENDER_RULES = {"include-missing", "include-cycle", "inline-missing",
                "inline-cycle", "id-repeat", "link-missing", "link-text"}


def expectation(text: str) -> tuple[str, str]:
    body = split_front(text, "case")[1].lstrip("\n")
    m = EXPECT_RE.match(body.split("\n", 1)[0])
    assert m is not None, ("a case's first line, under any front matter, must "
                           "be `+ expect: ...`")
    return ("ok", "") if m.group(1) == "ok" else ("error", m.group(2))


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_case(path):
    """A case parses as it expects, and an accepted case round trips."""
    text = path.read_text()
    kind, rule = expectation(text)
    if kind == "error" and rule not in RENDER_RULES:
        with pytest.raises(ControlledMarkdownError) as err:
            check_shape(parse(text, path.name))
        assert err.value.rule == rule
        return
    document = parse(text, path.name)
    check_shape(document)
    assert round_trips(document)
    canonical = write(document)
    assert write(parse(canonical, path.name)) == canonical
    if kind == "error":
        with pytest.raises(ControlledMarkdownError) as err:
            _render_case(path)
        assert err.value.rule == rule
        return
    _render_case(path)


def check_shape(document):
    """The rules a document keeps that the formatter does not settle."""
    check_order(document)
    check_blocks(document)
    for err in carry_errors(document):
        raise err


def _render_case(path):
    """A case rendered from its own directory, so an include by relative path
    resolves against the case file."""
    registry = Registry(path.parent)
    document = registry.load(path)
    check_links(document, path)
    render(document, registry)


MODULE = """import enum


class Filer(enum.Enum):
    ONE = "one"


@enum.unique
class Other(enum.Enum):
    TWO = "two"


def run():
    return 1
"""


GUIDE = """# Guide
- Read it.

## Making a change
- Write it.

### Detail
- Write it small.

## Other
- Keep it.
"""


def _tree(root: Path) -> None:
    _git(root, "init", "-q")
    (root / ".gitignore").write_text("tests/scratch/\n")
    (root / "scripts").mkdir()
    (root / "scripts" / "tool.py").write_text(MODULE)
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("")
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text(GUIDE)


def _rules(text: str, root: Path) -> list[str]:
    return [err.rule for err in check_xrefs(parse(text, "doc.md"), root)]


@pytest.mark.parametrize("line", [
    "- Run it.\n    + xref: scripts/tool.py:Filer.TWO",
    "- Run it.\n    + xref: scripts/tool.py:nothing",
    "- Run it.\n    + xref: docs/guide.md#absent",
    "- Run it.\n    + xref: scripts/tool.py#run",
    "- Run it.\n    + xref: docs/guide.md#",
    "- Run it.\n    + xref: scripts/tool.py:",
    "- Run `uv run python scripts/absent.py go`.",
    "- Run `uv run python -m absent`.",
    "- Read `src/absent.py`.",
])
def test_check_xrefs_refuses_what_the_tree_lacks(tmp_path, line):
    _tree(tmp_path)
    assert _rules(line, tmp_path) == ["xref-missing"]


@pytest.mark.parametrize("line", [
    "- Run it.\n    + xref: scripts/tool.py, scripts/tool.py:Filer.ONE, "
    "scripts/tool.py:run, scripts/tool.py:Other",
    "- Run it.\n    + xref: docs/guide.md, docs/guide.md#making-a-change, docs/guide.md#detail",
    "- Run `uv run python scripts/tool.py go --flag` and `uv run python -m pkg`.",
    "- Read `src/pkg/`, `scripts/*.py` and `src/<name>.py`.",
    "- Run `uv run python -c 'import absent'`.",
    "- Write under `tests/scratch/`.",
])
def test_check_xrefs_passes_what_resolves(tmp_path, line):
    _tree(tmp_path)
    assert _rules(line, tmp_path) == []


def _git(root: Path, *argv: str) -> str:
    return subprocess.run(["git", *argv], cwd=root, check=True, capture_output=True,
                          text=True, env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                                          "GIT_COMMITTER_NAME": "t",
                                          "GIT_COMMITTER_EMAIL": "t@t"}).stdout


def test_touched_lists_a_line_whose_definition_a_hunk_changes(tmp_path):
    _tree(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD").strip()
    path = tmp_path / "scripts" / "tool.py"
    path.write_text(MODULE.replace("return 1", "return 2"))
    document = parse("- Changed.\n    + xref: scripts/tool.py:run\n"
                     "- Kept.\n    + xref: scripts/tool.py:Filer.ONE\n", "doc.md")
    assert [(t.node.text, t.target) for t in touched([document], tmp_path, base)] == [
        ("Changed.", "scripts/tool.py:run")]


def test_touched_lists_a_line_whose_section_a_hunk_changes(tmp_path):
    _tree(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD").strip()
    path = tmp_path / "docs" / "guide.md"
    path.write_text(GUIDE.replace("Write it small.", "Write it short."))
    document = parse("- Section.\n    + xref: docs/guide.md#making-a-change\n"
                     "- Subsection.\n    + xref: docs/guide.md#detail\n"
                     "- Kept.\n    + xref: docs/guide.md#other\n"
                     "- Gone.\n    + xref: docs/guide.md#absent\n", "doc.md")
    assert [(t.node.text, t.target) for t in touched([document], tmp_path, base)] == [
        ("Section.", "docs/guide.md#making-a-change"),
        ("Subsection.", "docs/guide.md#detail")]


def test_touched_lists_no_section_whose_attribute_lines_alone_change(tmp_path):
    _tree(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD").strip()
    path = tmp_path / "docs" / "guide.md"
    path.write_text(GUIDE.replace("- Write it small.\n",
                                  "- Write it small.\n    + xref: scripts/tool.py:run\n"
                                  "    * comment: Asked for.\n"))
    assert path.read_text() != GUIDE
    document = parse("- Section.\n    + xref: docs/guide.md#making-a-change\n", "doc.md")
    assert touched([document], tmp_path, base) == []


def test_touched_lists_a_removed_target_and_no_target_absent_on_both_sides(tmp_path):
    _tree(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD").strip()
    path = tmp_path / "scripts" / "tool.py"
    path.write_text(MODULE.replace("def run():\n    return 1\n", ""))
    document = parse("- Removed.\n    + xref: scripts/tool.py:run\n"
                     "- Never.\n    + xref: scripts/tool.py:absent\n"
                     "- No file.\n    + xref: scripts/none.py:absent\n", "doc.md")
    assert [(t.node.text, t.target) for t in touched([document], tmp_path, base)] == [
        ("Removed.", "scripts/tool.py:run")]


def _linked(tmp_path: Path) -> tuple[Path, Path]:
    """A main tree with one commit, and a linked worktree of it."""
    main, linked = tmp_path / "main", tmp_path / "linked"
    main.mkdir()
    _git(main, "init", "-q")
    (main / "pyproject.toml").write_text('[tool.controlled_markdown]\npaths = ["docs"]\n')
    (main / "docs").mkdir()
    for name in ("kept", "ours"):
        (main / "docs" / f"{name}.md").write_text(f"- {name}.\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    _git(main, "worktree", "add", "-q", "--detach", str(linked))
    return main.resolve(), linked.resolve()


def test_xrefs_in_a_linked_worktree_reads_the_main_copy_of_each_document_it_leaves(tmp_path):
    main, linked = _linked(tmp_path)
    base = _git(linked, "rev-parse", "HEAD").strip()
    (main / "docs" / "kept.md").write_text("- kept, on master.\n")
    (linked / "docs" / "ours.md").write_text("- ours, changed.\n")
    (linked / "docs" / "added.md").write_text("- added.\n")
    assert xrefs_documents(linked, base) == [
        main / "docs" / "kept.md", linked / "docs" / "added.md", linked / "docs" / "ours.md"]


def test_xrefs_in_a_linked_worktree_reads_no_copy_of_a_document_its_diff_deletes(tmp_path):
    main, linked = _linked(tmp_path)
    base = _git(linked, "rev-parse", "HEAD").strip()
    (linked / "docs" / "ours.md").unlink()
    assert xrefs_documents(linked, base) == [main / "docs" / "kept.md"]


def test_xrefs_in_a_linked_worktree_reads_a_renamed_document_at_its_new_path(tmp_path):
    main, linked = _linked(tmp_path)
    base = _git(linked, "rev-parse", "HEAD").strip()
    _git(linked, "mv", "docs/ours.md", "docs/moved.md")
    assert xrefs_documents(linked, base) == [main / "docs" / "kept.md",
                                             linked / "docs" / "moved.md"]


def test_xrefs_in_the_main_tree_reads_its_own_documents(tmp_path):
    main, _ = _linked(tmp_path)
    base = _git(main, "rev-parse", "HEAD").strip()
    assert xrefs_documents(main, base) == [main / "docs" / "kept.md", main / "docs" / "ours.md"]


def test_xrefs_refuses_where_the_main_tree_has_no_module(tmp_path, capsys):
    _, linked = _linked(tmp_path)
    package = linked / "src" / "controlled_markdown"
    package.mkdir(parents=True)
    assert run_in_main(["xrefs", "HEAD"], package) == 2
    assert "the main tree has no `src/controlled_markdown`" in capsys.readouterr().err


def test_a_section_quote_spans_statements_past_their_attribute_lines(tmp_path):
    document = tmp_path / "doc.md"
    document.write_text("# Doc\n## Rule\n- Run the check.\n    + xref: scripts/tool.py:run\n"
                        "* comment: Asked for.\n- Read its output.\n")
    under = handbook_sections(document)["Rule"]
    assert under == ["Run the check. Read its output."]

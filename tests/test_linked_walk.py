"""The walk of links `contexts --diff` lists a reader's changed sections
by, from an agent's context and its checklist."""

from pathlib import Path

import handbook.reader_diffs as rd
from handbook.linked import LinkTarget, WalkStart, _Side, link_lines, linked_changes


def _side(root: Path, note: str) -> _Side:
    """A tree whose agent `a` has a checklist that links a section of a
    note no context links, with `note` as that section's text."""
    (root / "prompts" / "agents" / "a").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[tool.controlled_markdown]\npaths = ["prompts"]\n')
    (root / "prompts" / "agents" / "a" / "checklist.md").write_text(
        "# Step\n- Do it, as [Sec](prompts/note.md#sec) gives.\n")
    (root / "prompts" / "note.md").write_text(f"# Note\n\n## Sec\n- {note}\n")
    return _Side(root, str(root))


def test_a_section_only_a_checklist_links_is_listed(tmp_path: Path) -> None:
    then, now = _side(tmp_path / "then", "Old."), _side(tmp_path / "now", "New.")
    call = ("agent", ["a"])
    starts = rd._starts(then, now, "context\n", "context\n", call)
    changed = linked_changes(*starts, then, now)
    goals = {c.target for c in changed}
    assert LinkTarget(Path("prompts/note.md"), "sec") in goals
    lines = link_lines((link, WalkStart.CONTEXT)
                       for link in rd._leading(then, now, *starts, goals))
    assert "prompts/agents/a/checklist.md via context" in lines
    assert "prompts/note.md#sec via prompts/agents/a/checklist.md" in lines

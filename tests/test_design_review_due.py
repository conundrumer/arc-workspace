"""A change that builds code gets a design reviewer once after it leaves
`tickets/draft/`, and once more after a rebase conflict in a path that is
no document, once an editor has reported on that conflict."""

from pathlib import Path

from tests.conftest import script

LOG = ("## Log\n2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n"
       "2026-10-17T02:23:18Z open [ticket-reviewer ab225add95550521a]: reviewed\n"
       "2026-10-17T02:23:56Z assigned [operator aef519b953a4e20ed]: taking: no cost budget\n"
       "{conflict}")
CONFLICT = ("2026-10-17T03:00:00Z assigned [operator aef519b953a4e20ed]: "
            "conflict: the rebase onto `master` conflicts in {paths}\n")


def change(tmp_path: Path, conflict: str):
    path = tmp_path / "assigned" / "9-1_change_x_ticket-analyst.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nkind: change\neditors: code-editor\n---\n# x: y\n\n"
                    + LOG.format(conflict=conflict))
    script("file_ticket")
    return script("ticket_reads").held_ticket(path)


def editor(reported: float):
    from operations.roles import Role
    from operations.state import Agent, Report
    return Agent("a0000000000000001", "aef519b953a4e20ed", Role.CODE_EDITOR, "9-1", "", 0.0,
                 None, (Report(reported, "done"),), True)


def test_a_conflict_in_code_holds_the_review_until_an_editor_reports(tmp_path: Path) -> None:
    from operations.design_review import due_since
    t = change(tmp_path, CONFLICT.format(paths="src/operations/merging.py, README.md"))
    conflict = t.log[-1].time
    assert due_since(t, [editor(conflict - 1)]) is None
    assert due_since(t, [editor(conflict + 1)]) == conflict


def test_a_conflict_in_documents_alone_gives_no_second_review(tmp_path: Path) -> None:
    from operations.change_budget import left_draft
    from operations.design_review import due_since
    t = change(tmp_path, CONFLICT.format(paths="README.md"))
    assert due_since(t, [editor(t.log[-1].time - 1)]) == left_draft(t)

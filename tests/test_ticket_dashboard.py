"""The dashboard's page updates on a change of `fingerprint`: a log line
appended to a ticket file changes no directory's time, so a fingerprint
that misses it would leave the open page behind the tracker with no sign."""

from pathlib import Path

from tests.conftest import script


def test_a_log_line_appended_to_a_ticket_changes_the_fingerprint(tmp_path: Path, monkeypatch) -> None:
    module = script("ticket_dashboard")
    monkeypatch.setattr(module, "CODEX", module.CodexLimits(tmp_path))
    path = tmp_path / "new" / "9-1_bug_x_coordinator.md"
    path.parent.mkdir()
    path.write_text("---\nkind: bug\n---\n# x: y\n\n## Log\n2026-10-19T00:00:00Z new [coordinator]: filed\n")
    before = module.fingerprint(tmp_path)
    with path.open("a") as f:
        f.write("2026-10-19T00:01:00Z new [coordinator]: note\n")
    assert module.fingerprint(tmp_path) != before

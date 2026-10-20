"""Report acceptance refuses stale, amended and mismatched assignments."""

import hashlib
import os
from dataclasses import replace
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script
from operations.roles import Role

scripts_importable()
ticket = script("codex_ticket")
reports = script("codex_reports")


def prepared(tmp_path: Path):
    brief = tmp_path / "brief.md"
    brief.write_text("input")
    item = ticket.Assignment("11-2572", "a0123456789abcdef", "a1111111111111111",
                             Role.DESIGN_REVIEWER, 1, tmp_path, brief,
                             tmp_path / "scratch", tmp_path / "11-2572-0123456789ab-reply.txt",
                             hashlib.sha256(brief.read_bytes()).hexdigest())
    manifest = ticket.Store(tmp_path / "store").file(item)
    item.report.write_text("findings")
    # Force freshness without depending on file-system timestamp resolution.
    stamp = manifest.stat().st_mtime_ns
    os.utime(item.report, ns=(stamp + 1_000_000, stamp + 1_000_000))
    entries = [{"type": "user", "uuid": "input", "timestamp": "2020-01-01T00:00:00Z",
                "message": {"content": "input"}}]
    evidence = reports.Evidence(item.agent, item.revision, item.inputs_digest, entries)
    return item, manifest, evidence


@pytest.mark.parametrize("fault", ["wrong-path", "missing-file", "old-report", "changed-input",
                                    "wrong-revision", "wrong-agent", "no-evidence"])
def test_invalid_report_remains_invalid_on_retry(tmp_path: Path, fault: str):
    item, manifest, evidence = prepared(tmp_path)
    reply = str(item.report)
    if fault == "wrong-path":
        reply = str(tmp_path / "another.txt")
    elif fault == "missing-file":
        item.report.unlink()
    elif fault == "old-report":
        os.utime(item.report, ns=(1, 1))
    elif fault == "changed-input":
        item.brief.write_text("amended input")
    elif fault == "wrong-revision":
        evidence = replace(evidence, revision=2)
    elif fault == "wrong-agent":
        evidence = replace(evidence, agent="a2222222222222222")
    elif fault == "no-evidence":
        evidence = replace(evidence, entries=[])
    for _ in range(2):
        with pytest.raises((ticket.Refused, OSError)):
            reports.validate(manifest, reply, evidence, reports.Outcome.FINISHED)


def test_changed_report_invalidates_receipt(tmp_path: Path):
    item, manifest, evidence = prepared(tmp_path)
    receipt = reports.validate(manifest, str(item.report), evidence, reports.Outcome.FINISHED)
    item.report.write_text("different findings")
    os.utime(item.report, ns=(manifest.stat().st_mtime_ns + 1_000_000,) * 2)
    with pytest.raises(ticket.Refused):
        reports.validate(manifest, str(item.report), evidence, reports.Outcome.FINISHED, receipt)


def test_stopped_walk_does_not_approve(tmp_path: Path):
    item, manifest, evidence = prepared(tmp_path)
    item = replace(item, role=Role.CODE_EDITOR, revision=2)
    manifest = ticket.Store(tmp_path / "store").file(item)
    os.utime(item.report, ns=(manifest.stat().st_mtime_ns + 1_000_000,) * 2)
    entries = [*evidence.entries,
               {"type": "assistant", "message": {"content": [
                   {"type": "tool_use", "name": "Bash", "id": "stop",
                    "input": {"command": "uv run python scripts/step.py code-editor --stop copy-the-tree"}}]}},
               {"type": "user", "message": {"content": [
                   {"type": "tool_result", "tool_use_id": "stop", "content": "stopped"}]}}]
    with pytest.raises(ticket.Refused):
        reports.validate(manifest, str(item.report), replace(evidence, revision=2, entries=entries),
                         reports.Outcome.FINISHED)

"""A PreToolUse hook command that runs several checks denies a call with
the reason of each check that denies."""

import io
import json
import sys

import pytest

from tests.conftest import script


def test_a_denial_gives_the_reason_of_each_denying_check(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    entry = script("hook_entry")
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))

    def broken(_: dict[str, object]) -> str | None:
        raise ValueError("fails open")

    entry.run_pre_tool_use("test_hook", [lambda _: "first", lambda _: None, broken,
                                         lambda _: "second"])
    out = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"] == "first\nsecond"

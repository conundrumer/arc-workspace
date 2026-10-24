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


@pytest.mark.parametrize('denial', [None, 'denied'])
@pytest.mark.parametrize('failure', ['none', 'before', 'after'])
def test_advisory_and_update_fail_independently(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
        denial: str | None, failure: str) -> None:
    from contextlib import contextmanager
    entry = script('hook_entry')
    monkeypatch.setattr(sys, 'stdin', io.StringIO('{}'))
    recorded = []

    @contextmanager
    def update(_):
        if failure == 'before':
            raise ValueError('before')
        yield entry.Update('document', None)
        if failure == 'after':
            raise ValueError('after')
        recorded.append(True)

    def broken(_):
        raise ValueError('callback')

    entry.run_pre_tool_use('test', [lambda _: denial], update,
                           contexts=[lambda _: 'advice', broken, lambda _: 'more'])
    [output] = capsys.readouterr().out.splitlines()
    out = json.loads(output)['hookSpecificOutput']
    assert out['additionalContext'].splitlines() == (
        ['advice', 'more'] + ([] if failure == 'before' else ['document']))
    assert (out.get('permissionDecision') == 'deny') == (denial is not None)
    assert bool(recorded) == (failure == 'none')


def test_advisory_alone_allows(monkeypatch, capsys) -> None:
    entry = script('hook_entry')
    monkeypatch.setattr(sys, 'stdin', io.StringIO('{}'))
    entry.run_pre_tool_use('test', [], contexts=[lambda _: 'advice'])
    out = json.loads(capsys.readouterr().out)['hookSpecificOutput']
    assert out['additionalContext']
    assert 'permissionDecision' not in out

"""The trial switch and launch models required by the build brief."""

from pathlib import Path

import pytest

from engine import checkout
from handbook.paths import scripts_importable
from operations import codex_mode, trial_mode
from operations.roles import Model, Role, launch_parameters
from tests.conftest import script

scripts_importable()
actions = script("operate_actions")
operate = script("operate")


@pytest.fixture
def switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(actions, "main_tree", lambda: tmp_path)
    monkeypatch.setattr(checkout, "main_worktree", lambda _root: tmp_path)
    codex_mode.enabled.cache_clear()
    trial_mode.enabled.cache_clear()
    yield tmp_path
    codex_mode.enabled.cache_clear()
    trial_mode.enabled.cache_clear()


def test_switch(switch: Path, capsys):
    for args, expected in [([], "off"), (["on"], "on"), ([], "on"),
                           (["off"], "off"), ([], "off")]:
        assert operate.main(["trial", *args]) == 0
        assert capsys.readouterr().out.strip() == expected
        assert trial_mode.read(switch) == (expected == "on")
    assert not (switch / trial_mode.OVERRIDE).exists()
    assert operate.main(["trial", "yes"]) == 1
    assert operate.main(["trial", "on", "off"]) == 1
    assert not trial_mode.read(switch)


@pytest.mark.parametrize("text", ["", "yes", "on off"])
def test_switch_refuses_invalid_file(switch: Path, text: str):
    path = switch / trial_mode.OVERRIDE
    path.parent.mkdir()
    path.write_text(text)
    with pytest.raises(ValueError):
        trial_mode.read(switch)


@pytest.mark.parametrize("trial", [False, True])
@pytest.mark.parametrize("codex", [False, True])
@pytest.mark.parametrize("role, expected", [(Role.CODE_EDITOR, Model.OPUS),
                                          (Role.GATE, Model.SONNET),
                                          (Role.BATCH_PROFILE, None)])
@pytest.mark.parametrize("model", [None, Model.OPUS, Model.SONNET])
def test_launch(switch: Path, trial: bool, codex: bool, role: Role,
                expected: Model | None, model: Model | None):
    actions.set_trial(["on" if trial else "off"])
    actions.set_codex(["on" if codex else "off"])
    params = launch_parameters(role, "1-1", model, "brief")
    routed = codex and role is Role.CODE_EDITOR
    assert params.get("model") == (Model.HAIKU if trial or routed else model or expected)
    assert params["subagent_type"] == ("codex-launcher" if routed else role.agent_type)
    assert ("Codex mode:" in params["prompt"]) == routed


def test_command_holds_switch(switch: Path, capsys):
    actions.set_trial(["on"])
    first = launch_parameters(Role.BATCH_PROFILE, "1-1", None)
    actions.set_trial(["off"])
    assert launch_parameters(Role.BATCH_PROFILE, "1-1", None) == first
    assert operate.main(["trial"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "off"
    assert "model" not in launch_parameters(Role.BATCH_PROFILE, "1-1", None)

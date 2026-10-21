"""The switch and the launch fields it gives, as the build brief requires."""

from pathlib import Path

import pytest

from engine import checkout
from handbook.paths import scripts_importable
from operations import codex_mode
from operations.order import made
from operations.roles import PASSES, Model, Role, agent_type, launch_parameters, launched_model
from operations.printing import printed, printed_launches
from operations.steps import Launch
from tests.conftest import script
from tests.test_operator_take_up import operator_state

scripts_importable()
actions = script("operate_actions")


@pytest.fixture
def switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(actions, "main_tree", lambda: tmp_path)
    monkeypatch.setattr(checkout, "main_worktree", lambda _root: tmp_path)
    codex_mode.enabled.cache_clear()
    yield tmp_path
    codex_mode.enabled.cache_clear()


def test_switch(switch: Path, capsys):
    for args, expected in [([], "off"), (["on"], "on"), ([], "on"),
                           (["off"], "off"), ([], "off")]:
        assert actions.set_codex(args) == 0
        assert capsys.readouterr().out.strip() == expected
        assert codex_mode.read(switch) == (expected == "on")
    assert not (switch / codex_mode.OVERRIDE).exists()
    assert actions.set_codex(["yes"]) == 1
    assert not codex_mode.read(switch)


@pytest.mark.parametrize("text", ["", "yes", "on off"])
def test_switch_refuses_invalid_file(switch: Path, text: str):
    path = switch / codex_mode.OVERRIDE
    path.parent.mkdir()
    path.write_text(text)
    with pytest.raises(ValueError):
        codex_mode.read(switch)


def test_command_holds_switch(switch: Path):
    actions.set_codex(["on"])
    first = launch_parameters(Role.CODE_EDITOR, "1-1", None, "brief")
    actions.set_codex(["off"])
    assert launch_parameters(Role.CODE_EDITOR, "1-1", None, "brief") == first
    codex_mode.enabled.cache_clear()
    assert launch_parameters(Role.CODE_EDITOR, "1-1", None, "brief")["model"] != Model.HAIKU


@pytest.mark.parametrize("model", [None, *Model])
def test_operator_stays_on_claude_with_codex_on(switch: Path, model: Model | None):
    actions.set_codex(["on"])
    params = launch_parameters(Role.OPERATOR, "1-1", model, "brief")
    assert params["subagent_type"] == "operator"
    assert params["model"] == (model or Model.HAIKU)
    assert params["prompt"] == "brief"


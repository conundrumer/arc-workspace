"""The switch and the launch fields it gives, as the build brief requires."""

from pathlib import Path

import pytest

from engine import checkout
from handbook.paths import scripts_importable
from operations import codex_mode
from operations.order import made
from operations.roles import Model, Role, launch_parameters
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


@pytest.mark.parametrize("role", [Role.CODE_EDITOR, Role.CODE_REVIEWER, Role.DESIGN_REVIEWER,
                                 Role.LIB_REVIEWER, Role.DOC_EDITOR])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("model", [None, Model.SONNET])
def test_launch(switch: Path, role: Role, enabled: bool, model: Model | None):
    actions.set_codex(["on" if enabled else "off"])
    params = launch_parameters(role, "1-1", model, "brief")
    routed = enabled and role is not Role.DOC_EDITOR
    assert params["model"] == (Model.HAIKU if routed else model or role.model)
    assert params["subagent_type"] == ("codex-launcher" if routed else role.agent_type)
    assert params["description"] == f"op {role.value} 1-1"
    assert params["run_in_background"] == "true"
    if routed:
        effort = "high" if role is Role.CODE_EDITOR and model is None else "medium"
        assert params["prompt"] == f'brief\nCodex mode: role `{role.value}`, model `gpt-6.1-sol`, reasoning effort `{effort}`.'
    else:
        assert params["prompt"] == "brief"
    step = Launch(role, "1-1", "brief", model, occasion="test")
    state = made(operator_state(switch, "agent", ("agent",), ()), step)
    assert state.transcripts.calls[-1].input == params
    assert state.transcripts.agents[-1].brief == params["prompt"]
    output = printed(step, "agent", switch)
    launches = printed_launches(output)
    assert len(launches) == 1
    assert launches[0] is not None
    assert launches[0]["model"] == params["model"]
    assert launches[0]["subagent_type"] == params["subagent_type"]
    assert launches[0]["description"] == params["description"]
    assert ("Codex mode:" in launches[0]["prompt"]) == routed


def test_command_holds_switch(switch: Path):
    actions.set_codex(["on"])
    first = launch_parameters(Role.CODE_EDITOR, "1-1", None, "brief")
    actions.set_codex(["off"])
    assert launch_parameters(Role.CODE_EDITOR, "1-1", None, "brief") == first
    codex_mode.enabled.cache_clear()
    assert launch_parameters(Role.CODE_EDITOR, "1-1", None, "brief")["model"] != Model.HAIKU

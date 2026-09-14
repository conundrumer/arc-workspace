"""The retro's Codex runner: the files it lays out for a session, the schema
it hands the model, and the call it makes."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from dl.paths import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "retro_codex.py"

SCHEMA = {
    "type": "object",
    "properties": {
        "diffs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"file": {"type": "string"}, "path": {"type": "string"}},
                "required": ["file", "path"],
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["diffs"],
}


@pytest.fixture(scope="module")
def retro_codex():
    """The script, loaded from its path: `scripts/` is no package."""
    spec = importlib.util.spec_from_file_location("retro_codex", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["retro_codex"] = module
    spec.loader.exec_module(module)
    return module


def test_safe_folds_a_label_into_one_file_name(retro_codex):
    assert retro_codex.safe("fix:prose:1/3") == "fix-prose-1-3"


def test_strict_closes_every_object_and_requires_each_property(retro_codex):
    out = retro_codex.strict(SCHEMA)
    assert out["additionalProperties"] is False
    assert out["required"] == ["diffs", "notes"]
    item = out["properties"]["diffs"]["items"]
    assert item["additionalProperties"] is False
    assert item["required"] == ["file", "path"]


def test_prepare_writes_the_brief_and_the_schema_under_the_label(retro_codex, tmp_path: Path):
    brief, schema, out = retro_codex.prepare(tmp_path, "fix:prose:1/3", "the brief\n", SCHEMA)
    assert brief == tmp_path / retro_codex.BRIEF_DIR / "fix-prose-1-3.md"
    assert brief.read_text() == "the brief\n"
    assert schema == tmp_path / retro_codex.BRIEF_DIR / retro_codex.SCHEMA_NAME
    assert json.loads(schema.read_text())["additionalProperties"] is False
    assert out == tmp_path / retro_codex.OUT_DIR / "fix-prose-1-3.json"


def test_prepare_clears_the_final_message_a_previous_run_left(retro_codex, tmp_path: Path):
    stale = tmp_path / retro_codex.OUT_DIR / "unit.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}")
    _, _, out = retro_codex.prepare(tmp_path, "unit", "the brief\n", SCHEMA)
    assert out == stale
    assert not stale.exists()


def test_codex_argv_takes_the_brief_on_stdin_last(retro_codex, tmp_path: Path):
    argv = retro_codex.codex_argv(tmp_path, tmp_path / "s.json", tmp_path / "o.json")
    assert argv[:2] == ["codex", "exec"]
    assert argv[-1] == "-"
    assert argv[argv.index("-C") + 1] == str(tmp_path)
    assert argv[argv.index("--output-schema") + 1] == str(tmp_path / "s.json")
    assert argv[argv.index("-o") + 1] == str(tmp_path / "o.json")


def test_codex_argv_passes_the_model_and_the_effort_only_when_given(retro_codex, tmp_path: Path):
    bare = retro_codex.codex_argv(tmp_path, tmp_path / "s.json", tmp_path / "o.json")
    assert "--model" not in bare
    assert not [a for a in bare if "model_reasoning_effort" in a]
    given = retro_codex.codex_argv(tmp_path, tmp_path / "s.json", tmp_path / "o.json",
                                   model="gpt-5", effort="low")
    assert given[given.index("--model") + 1] == "gpt-5"
    assert 'model_reasoning_effort="low"' in given

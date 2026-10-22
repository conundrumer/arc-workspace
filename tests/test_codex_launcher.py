"""A launcher's role checks and Bash write refusals."""

import json
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from operations.roles import CODEX_AGENT_LINE, CODEX_LINE, PASSES, Role
from tests.conftest import script

scripts_importable()
reads = script("run_reads")
bash = script("codex_bash_hook")


def transcript(tmp_path: Path, first: str, kind: str = "codex-launcher") -> Path:
    path = tmp_path / "s" / "subagents" / "agent-a0000000000000001.jsonl"
    path.parent.mkdir(parents=True)
    path.with_suffix(".meta.json").write_text(json.dumps({"agentType": kind}))
    later = CODEX_LINE.format(role="lib-reviewer", model="gpt-6.1-sol", effort="medium")
    path.write_text("".join(json.dumps({"type": "user", "message": {"content": text}}) + "\n"
                            for text in (first, later)))
    return path


@pytest.mark.parametrize("role", [r for r in Role if r not in (*PASSES, Role.OPERATOR)])
def test_caller_role(tmp_path: Path, monkeypatch, role):
    path = transcript(tmp_path, "brief\n" + CODEX_LINE.format(
        role=role, model="gpt-6.1-sol", effort="high"))
    monkeypatch.setattr(reads, "caller_transcript", lambda _: path)
    assert reads.agent_type(path) == "codex-launcher"
    assert reads.caller_type("test", {}) == (path, role.agent_type)


@pytest.mark.parametrize("first", ["brief", *[CODEX_LINE.format(
    role=role, model="gpt-6.1-sol", effort="high") for role in ["unknown", *PASSES, Role.OPERATOR]]])
def test_missing_or_unsupported_role_is_refused(tmp_path: Path, first):
    with pytest.raises(ValueError):
        reads.role_type(transcript(tmp_path, first))


@pytest.mark.parametrize("kind", ["draft-analyst", "decision-analyst"])
def test_analyst_checks_use_the_selected_document(tmp_path: Path, kind: str):
    first = CODEX_LINE.format(role="ticket-analyst", model="gpt-6.1-sol", effort="high")
    first += "\n" + CODEX_AGENT_LINE.format(agent_type=kind)
    assert reads.role_type(transcript(tmp_path, first)) == kind


def test_a_different_roles_document_is_refused(tmp_path: Path):
    first = CODEX_LINE.format(role="code-editor", model="gpt-6.1-sol", effort="high")
    first += "\n" + CODEX_AGENT_LINE.format(agent_type="operator")
    with pytest.raises(ValueError):
        reads.role_type(transcript(tmp_path, first))


@pytest.mark.parametrize("command", [
    "python3 -c 'open(\"x\", \"w\")'", "python - <<'PY'\nprint('write')\nPY",
    "uv run python -c 'print(1)'", "uv run --project . python -c 'print(1)'",
    "if true; then python3 -c 'edit()'; fi", "python3 /tmp/edit.py",
    "sed -i '' s/a/b/ src/a.py", "perl -pi -e s/a/b/ src/a.py",
    "echo text | tee src/a.py", "echo text >src/a.py", "echo text >> src/a.py",
    "echo text 2>src/a.py", "cat <<'EOF' > src/a.py\ntext\nEOF",
    "cp /tmp/a src/a.py", "mv src/a.py /tmp/a", "rm -f src/a.py",
    "git apply /tmp/a.patch", "git commit -am edit", "git checkout -- src/a.py",
    "git -C {repo} reset --hard", "git add .", "git restore src/a.py", "git stash",
    "cd /tmp; echo text > {repo}/src/a.py",
    "echo text > {repo}/.claude/worktrees/other/src/a.py",
    "cd .claude/worktrees/other; cp /tmp/a src/a.py",
    "target={repo}/src/a.py; echo text > $target",
    "bash -c 'echo text > src/a.py'",
])
def test_bash_denies_writes(tmp_path: Path, command: str):
    root = tmp_path / "repo"
    assert bash.writes_repository(command.format(repo=root), root, root)


@pytest.mark.parametrize("command", [
    "uv run python scripts/step.py code-editor",
    "uv run python scripts/codex_agent.py code-editor /tmp/s /tmp/b gpt-6.1-sol high --cwd /tmp/w < /tmp/item",
    "timeout 180 uv run python -u scripts/operate.py review a1",
    "uv run python -m controlled_markdown check",
    "uv run --project . python scripts/step.py code-editor", "cat src/a.py", "git diff", "git log -1",
    "echo 'python3 -c code; git add .; > src/a.py'", "echo text > /tmp/reply.txt",
    "cp src/a.py /tmp/a", "mv /tmp/a /tmp/b", "rm /tmp/a", "echo text | tee /tmp/a",
    "cd /tmp; echo text > reply.txt", ": 'unattended-wait: codex'; sleep 1",
    "uv run python scripts/codex_agent.py code-editor /tmp/s /tmp/b gpt-6.1-sol high <<'EOF'\ngit add .\nEOF",
    "echo error >&2", "git log --grep add", "git -C /tmp log --grep commit",
    "sed -i s/a/b/ /tmp/a", "perl -pi -e s/a/b/ /tmp/a",
])
def test_bash_allows_commands(tmp_path: Path, command: str):
    root = tmp_path / "repo"
    assert not bash.writes_repository(command, root, root)


@pytest.mark.parametrize("kind,denied", [("codex-launcher", True), ("code-editor", False)])
def test_bash_caller_guard(tmp_path: Path, monkeypatch, kind, denied):
    from engine import checkout

    path = transcript(tmp_path, "brief", kind)
    monkeypatch.setattr(reads, "caller_transcript", lambda _: path)
    monkeypatch.setattr(checkout, "main_worktree", lambda _: tmp_path)
    assert bool(bash.check({"tool_name": "Bash", "cwd": str(tmp_path),
                            "tool_input": {"command": "python3 -c 'edit()'"}})) == denied


def test_a_launcher_cannot_skip_printed_review_launches(tmp_path: Path, monkeypatch):
    path = transcript(tmp_path, CODEX_LINE.format(
        role="code-editor", model="gpt-6.1-sol", effort="high"))
    monkeypatch.setattr(reads, "caller_transcript", lambda _: path)
    launch = script("printed_launch_hook")
    assert launch.check({"tool_name": "Agent", "agent_id": "a0000000000000001",
                         "tool_input": {"subagent_type": "codex-launcher"}}) is not None


def test_native_review_dispatch_requires_matching_validated_call(tmp_path: Path, monkeypatch, capsys):
    import hashlib
    from types import SimpleNamespace
    from operations.steps import Launch

    native_reads = script("codex_reads")
    ticket = script("codex_ticket")
    review = script("operate_review")
    hook = script("printed_launch_hook")
    reports = script("codex_reports")
    brief = tmp_path / "brief.txt"
    brief.write_text("editor input")
    assignment = ticket.Assignment("11-2967", "a0123456789abcdef", "a1111111111111111",
        Role.CODE_EDITOR, 1, tmp_path, brief, tmp_path / "editor", tmp_path / "report.txt",
        hashlib.sha256(brief.read_bytes()).hexdigest())
    store = ticket.Store(tmp_path / "store")
    manifest = store.file(assignment)
    token = store.reserve(assignment)
    store.accepted(assignment.agent, token, "native-editor", "turn")
    native = native_reads.Native(store.path, manifest, assignment, store.snapshot()["agents"][assignment.agent])
    monkeypatch.setattr(native_reads, "native_find", lambda _: native)
    monkeypatch.setattr(native_reads, "native_reviewing", lambda _: 1)
    monkeypatch.setattr(review, "find", lambda _: tmp_path / "operator")
    monkeypatch.setattr(reads, "agent_type", lambda _: Role.OPERATOR.agent_type)
    monkeypatch.setattr(review, "change_filed", lambda *_: None)
    monkeypatch.setattr(review, "read_state", lambda *_: (SimpleNamespace(scratch=tmp_path), None))
    step = Launch(Role.TICKET_ANALYST, "change:11-2967", "decide the finding", occasion="finding")
    monkeypatch.setattr(review.changes, "editor_step", lambda *_: step)
    monkeypatch.setattr(review, "read_again", lambda read: read)
    monkeypatch.setattr(review, "waited", lambda _, read, __: read(0))
    assert review.review(assignment.agent) == 0
    dispatch = json.loads(capsys.readouterr().out)
    assert json.loads((assignment.scratch / "codex-dispatch.json").read_text()) == dispatch
    call = dispatch["call"]["arguments"]
    assert call["subagent_type"] == "decision-analyst"
    undecided = []
    assert "decide the finding" in script("filed_texts").unfiled(call["prompt"], "dispatch", undecided)
    assert not undecided

    monkeypatch.setattr(reads, "agent_type", lambda _: "codex-launcher")
    monkeypatch.setattr(reads, "caller_transcript", lambda _: tmp_path / "launcher")
    monkeypatch.setattr(reads, "run_entries", lambda _: [])
    monkeypatch.setattr(native_reads, "calls", lambda _: [SimpleNamespace(scratch=assignment.scratch)])
    monkeypatch.setattr(native_reads, "native_receipt", lambda _: SimpleNamespace(outcome=reports.Outcome.NEEDS_OPERATOR))
    assert hook.check({"tool_name": "Agent", "tool_input": call}) is None
    visible = {key: value for key, value in call.items() if key != "run_in_background"}
    assert hook.check({"tool_name": "Agent", "tool_input": visible}) is None
    assert hook.check({"tool_name": "Agent", "tool_input": {**call, "prompt": "changed"}}) is not None
    monkeypatch.setattr(native_reads, "native_receipt", lambda _: None)
    assert hook.check({"tool_name": "Agent", "tool_input": call}) is not None


def test_joined_bash_denies_a_launcher_write(tmp_path: Path, monkeypatch, capsys):
    import io
    import sys
    from engine import checkout

    path = transcript(tmp_path, CODEX_LINE.format(
        role="code-editor", model="gpt-6.1-sol", effort="high"))
    monkeypatch.setattr(reads, "caller_transcript", lambda _: path)
    monkeypatch.setattr(checkout, "main_worktree", lambda _: tmp_path)
    monkeypatch.setattr(script("reader_delivery"), "reader_update", script("hook_entry").no_update)
    monkeypatch.setattr(sys, "argv", ["joined_hooks.py", "bash"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "tool_name": "Bash", "cwd": str(tmp_path),
        "tool_input": {"command": "python3 -c 'edit()'"}})))
    assert script("joined_hooks").main() == 0
    out = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"


@pytest.mark.parametrize("wording", ["old", "new", "prefix", "different", "wrong-role"])
def test_reviewer_recognition_uses_exact_worktree_command(tmp_path: Path, wording: str):
    from operations import briefs, doc_review
    from operations.roles import Role
    from operations.state import Agent

    worktree = tmp_path / "change"
    command = briefs.fingerprint_command(worktree)
    text = ("Before you write each final reply, run " + command
            + ", and end that reply with the line `Worktree: <what it printed>`.")
    if wording == "new":
        text = briefs.fingerprint_line(worktree)
    elif wording == "prefix":
        text = briefs.fingerprint_line(tmp_path / "change-other")
    elif wording == "different":
        text = briefs.fingerprint_line(tmp_path / "other")
    role = Role.CODE_REVIEWER if wording == "wrong-role" else Role.DOC_REVIEWER
    reviewer = Agent("reviewer", "operator", role, "change", text, 0, 0, None, (), False)
    expected = [reviewer] if wording in ("old", "new") else []
    assert doc_review.reviewers_of([reviewer], worktree) == expected

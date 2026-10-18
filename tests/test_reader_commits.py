"""The hooks that give a running reader the diff of its documents, run in
fresh processes as `.claude/settings.json` registers them. A lost update, an
update given twice, or a record that does not move gives no sign in use."""

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from engine import checkout
from engine.rwlock import HOLD_ENV
from tests.conftest import script

BEFORE = "9902f864930978d057225b591ef940510bfa6543"
OPERATOR_ID = "a0123456789abcdef"
GENERAL_ID = "afedcba9876543210"
KEPT_ENV = ("PATH", "HOME", HOLD_ENV)
"""The variables of the run's environment a hook is given. A variable of
the session, such as its reader, changes what a hook writes."""


def head() -> str:
    return checkout.git_out(checkout.ROOT, "rev-parse", "HEAD").strip()


def command(event: str, matcher: str | None = None, script: str = "") -> str:
    settings = json.loads((checkout.claude() / "settings.json").read_text())
    [cmd] = [h["command"] for m in settings["hooks"][event]
             if m.get("matcher") == matcher for h in m["hooks"] if script in h["command"]]
    return cmd


def ran(cmd: str, hook: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, shell=True, input=json.dumps(hook),
                          capture_output=True, text=True, check=True,
                          env={**{k: os.environ[k] for k in KEPT_ENV if k in os.environ},
                               checkout.CACHE_ENV: str(
                                   Path(hook["transcript_path"]).parent / "cache"),
                               "CLAUDE_PROJECT_DIR": str(checkout.ROOT),
                               "CLAUDE_CODE_ENTRYPOINT": "cli"})


def run(cmd: str, hook: dict[str, Any]) -> str:
    return ran(cmd, hook).stdout


def line(**fields: Any) -> str:
    return json.dumps(fields) + "\n"


def session(tmp: Path) -> Path:
    main = tmp / "S.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    main.write_text(line(parentUuid=None, type="user", uuid="u0", timestamp=now))
    subs = tmp / "S" / "subagents"
    subs.mkdir(parents=True)
    for aid, kind in [(OPERATOR_ID, "operator"), (GENERAL_ID, "general-purpose")]:
        (subs / f"agent-{aid}.jsonl").write_text(
            line(parentUuid=None, type="user", uuid=f"u{aid}", agentId=aid))
        (subs / f"agent-{aid}.meta.json").write_text(json.dumps({"agentType": kind}))
    return main


def record(main: Path, who: str) -> Path:
    """The record of `who`: the coordinator's in the session directory, a
    subagent's in the directory of the sessions."""
    where = main.with_suffix("") if who == "main" else main.parent
    return where / "reader-commits" / who


def delivered(main: Path, who: str = "main") -> Path:
    """The delivery file of `who`: its record's path with the suffix
    `reader_delivery.DELIVERED`."""
    return record(main, who).with_name(f"{who}.delivered")


def aged(path: Path, seconds: float) -> None:
    """Set the modification time of `path` to `seconds` ago, or ahead where
    negative, so that a check of its age needs no timing."""
    when = time.time() - seconds
    os.utime(path, (when, when))


def both(commit: str) -> str:
    return f"{commit}\n{commit}\n"


def call(main: Path, tool: str, inp: dict[str, Any],
         agent: str | None = None) -> dict[str, Any]:
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": inp,
            "tool_use_id": "t1", "transcript_path": str(main),
            "cwd": str(checkout.ROOT), **({"agent_id": agent} if agent else {})}


def session_start(main: Path) -> None:
    run(command("SessionStart"), {"hook_event_name": "SessionStart", "source": "compact",
                                  "transcript_path": str(main), "cwd": str(checkout.ROOT)})


def test_coordinator_gets_the_diff_once(tmp_path: Path) -> None:
    main = session(tmp_path)
    bash = command("PreToolUse", "Bash|Monitor")
    session_start(main)
    assert record(main, "main").read_text() == both(head())
    record(main, "main").write_text(both(BEFORE))
    session_start(main)
    assert record(main, "main").read_text() == both(BEFORE)
    out = json.loads(run(bash, call(main, "Bash", {"command": "ls"})))
    text = out["hookSpecificOutput"]["additionalContext"]
    assert f"context --update {BEFORE} {BEFORE} coordinator`" in text
    assert record(main, "main").read_text() == both(head())
    aged(delivered(main), 1)
    assert run(bash, call(main, "Bash", {"command": "ls"})) == ""


def test_subagents(tmp_path: Path) -> None:
    main = session(tmp_path)
    session_start(main)
    start = command("SubagentStart")
    for aid in (OPERATOR_ID, GENERAL_ID):
        run(start, {"hook_event_name": "SubagentStart", "agent_id": aid,
                    "transcript_path": str(main), "cwd": str(checkout.ROOT)})
        assert record(main, aid).read_text() == f"{head()}\n"
        record(main, aid).write_text(both(BEFORE))
    run(start, {"hook_event_name": "SubagentStart", "agent_id": OPERATOR_ID,
                "transcript_path": str(main), "cwd": str(checkout.ROOT)})
    assert record(main, OPERATOR_ID).read_text() == both(BEFORE)
    denied = call(main, "Bash", {"command": "ls", "timeout": 600000}, OPERATOR_ID)
    out = json.loads(run(command("PreToolUse", "Bash|Monitor"), denied))["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "context agent operator" in out["additionalContext"]
    assert record(main, OPERATOR_ID).read_text() == both(head())
    aged(delivered(main, OPERATOR_ID), 1)
    agent = command("PreToolUse", "Agent", "context_bound_hook")
    assert run(agent, call(main, "Agent", {"subagent_type": "operator"}, OPERATOR_ID)) == ""
    assert run(agent, call(main, "Agent", {"subagent_type": "operator"}, GENERAL_ID)) == ""
    assert record(main, GENERAL_ID).read_text() == both(head())


def transcript_of(main: Path, aid: str) -> Path:
    return main.with_suffix("") / "subagents" / f"agent-{aid}.jsonl"


def given(transcript: Path, context: str, project: str) -> None:
    """Append to `transcript` the attachments that hold the texts the
    harness gave its run."""
    with transcript.open("a") as f:
        f.write(line(type="attachment", attachment={"type": "instructions", "files": [
            {"path": str(checkout.ROOT / "CLAUDE.md"), "type": "Project", "content": project}]}))
        f.write(line(type="attachment", attachment={
            "type": "prompt_snapshot", "systemPrompt": [context]}))


def current() -> tuple[str, str]:
    """The operator's context and `CLAUDE.md` as `HEAD` gives them."""
    from handbook.agents import agent_prompt_text

    return (agent_prompt_text("operator"),
            (checkout.ROOT / "CLAUDE.md").read_text().rstrip("\n"))


def stale() -> tuple[str, str]:
    """Texts of the operator that differ from `current` by one line."""
    context, project = current()
    return context + "\n- A line that the tree no longer holds.", project


EARLIER_ID = "a1234567890abcdef"
"""An operator launched before `OPERATOR_ID`."""


def earlier_launch(main: Path, texts: tuple[str, str], aid: str = EARLIER_ID) -> Path:
    path = transcript_of(main, aid)
    path.write_text(line(parentUuid=None, type="user", uuid="ue", agentId=aid))
    given(path, *texts)
    meta = path.with_suffix(".meta.json")
    meta.write_text(json.dumps({"agentType": "operator"}))
    return meta


def subagent_start(main: Path, aid: str) -> subprocess.CompletedProcess[str]:
    return ran(command("SubagentStart"), {
        "hook_event_name": "SubagentStart", "agent_id": aid, "agent_type": "operator",
        "transcript_path": str(main), "cwd": str(checkout.ROOT)})


def started_with(done: subprocess.CompletedProcess[str]) -> str:
    return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.fixture
def digest(monkeypatch: pytest.MonkeyPatch) -> Any:
    """`reader_commits.texts_digest`."""
    monkeypatch.syspath_prepend(str(checkout.scripts()))
    return script("reader_commits").texts_digest


HELD_HEAD = "runs from the texts you were given at your launch"


def test_start_diff_from_an_earlier_launch_of_the_type(tmp_path: Path, digest: Any) -> None:
    main = session(tmp_path)
    earlier_launch(main, stale())
    text = started_with(subagent_start(main, OPERATOR_ID))
    assert text.startswith(f"Your agent id is {OPERATOR_ID}.\n\n")
    assert HELD_HEAD in text and "A line that the tree no longer holds." in text
    assert record(main, OPERATOR_ID).read_text() == f"{head()}\n{digest(stale())}\n"
    given(transcript_of(main, OPERATOR_ID), *stale())
    read = command("PreToolUse", "^(?!(Bash|Monitor|Agent)$).*", "reader_update_hook")
    hook = call(main, "Read", {"file_path": str(checkout.ROOT / "CLAUDE.md")}, OPERATOR_ID)
    assert run(read, hook) == ""
    assert record(main, OPERATOR_ID).read_text() == both(head())


def test_held_texts_other_than_the_predicted_ones(tmp_path: Path, digest: Any) -> None:
    main = session(tmp_path)
    earlier_launch(main, current())
    assert started_with(subagent_start(main, OPERATOR_ID)) == f"Your agent id is {OPERATOR_ID}."
    assert record(main, OPERATOR_ID).read_text() == f"{head()}\n{digest(current())}\n"
    given(transcript_of(main, OPERATOR_ID), *stale())
    bash = command("PreToolUse", "Bash|Monitor")
    out = json.loads(run(bash, call(main, "Bash", {"command": "ls"}, OPERATOR_ID)))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert HELD_HEAD in out["hookSpecificOutput"]["additionalContext"]
    assert record(main, OPERATOR_ID).read_text() == both(head())


def test_no_earlier_launch_and_a_failed_prediction(tmp_path: Path) -> None:
    main = session(tmp_path)
    assert started_with(subagent_start(main, OPERATOR_ID)) == f"Your agent id is {OPERATOR_ID}."
    assert record(main, OPERATOR_ID).read_text() == f"{head()}\n"
    earlier_launch(main, stale())
    unknown = "a1111111111111111"
    done = ran(command("SubagentStart"), {
        "hook_event_name": "SubagentStart", "agent_id": unknown,
        "transcript_path": str(main), "cwd": str(checkout.ROOT)})
    assert started_with(done) == f"Your agent id is {unknown}."
    assert "gave no start diff" in done.stderr
    assert record(main, unknown).read_text() == f"{head()}\n"


def test_merge_after_a_prediction_that_holds(tmp_path: Path, digest: Any) -> None:
    main = session(tmp_path)
    given(transcript_of(main, OPERATOR_ID), *current())
    record(main, OPERATOR_ID).parent.mkdir(parents=True, exist_ok=True)
    record(main, OPERATOR_ID).write_text(f"{BEFORE}\n{digest(current())}\n")
    bash = command("PreToolUse", "Bash|Monitor")
    out = json.loads(run(bash, call(main, "Bash", {"command": "ls"}, OPERATOR_ID)))
    assert f"context --update {BEFORE} {BEFORE} agent operator`" in \
        out["hookSpecificOutput"]["additionalContext"]
    assert record(main, OPERATOR_ID).read_text() == both(head())


def test_subagent_first_update_from_held_texts(tmp_path: Path) -> None:
    main = session(tmp_path)
    bash = command("PreToolUse", "Bash|Monitor")
    transcript = transcript_of(main, OPERATOR_ID)
    record(main, OPERATOR_ID).parent.mkdir(parents=True, exist_ok=True)
    record(main, OPERATOR_ID).write_text(f"{head()}\n")
    ls = call(main, "Bash", {"command": "ls"}, OPERATOR_ID)
    assert "holds no context" in ran(bash, ls).stderr
    assert record(main, OPERATOR_ID).read_text() == f"{head()}\n"
    given(transcript, *current())
    assert run(bash, ls) == ""
    assert record(main, OPERATOR_ID).read_text() == both(head())


GIVES_UPDATE = ("pending_wait_hook", "context_bound_hook", "reader_update_hook")
"""The PreToolUse hooks that give the caller its update."""


def stub_uv(tmp: Path, body: str) -> Path:
    """The directory of a `uv` to put first on the path, that runs the shell
    text `body`."""
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    (bin_dir / "uv").write_text(f"#!/bin/sh\n{body}\n")
    (bin_dir / "uv").chmod(0o755)
    return bin_dir


def test_fast_path_reads_the_record_of_record_path(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(checkout.scripts()))
    record_path = script("reader_commits").record_path
    delivery_path = script("reader_delivery").delivery_path

    main = session(tmp_path)
    started = tmp_path / "started"
    monkeypatch.setenv("PATH", f"{stub_uv(tmp_path, f'touch {started}')}:{os.environ['PATH']}")
    for hook in [after_call(main, "PostToolUse"), after_call(main, "PostToolUse", OPERATOR_ID),
                 prompt(main)]:
        cmd = command(hook["hook_event_name"])
        path = record_path(hook)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(both(head()))
        assert run(cmd, hook) == ""
        assert not started.exists()
        delivery_path(hook).touch()
        run(cmd, hook)
        assert started.exists()
        started.unlink()
        delivery_path(hook).unlink()
        path.write_text(both(BEFORE))
        run(cmd, hook)
        assert started.exists()
        started.unlink()


def after_call(main: Path, event: str, agent: str | None = None) -> dict[str, Any]:
    return {**call(main, "Bash", {"command": "ls"}, agent), "hook_event_name": event,
            "tool_response": {"stdout": ""}}


def prompt(main: Path) -> dict[str, Any]:
    return {"hook_event_name": "UserPromptSubmit", "prompt": "hi",
            "transcript_path": str(main), "cwd": str(checkout.ROOT)}


def test_update_after_a_call_and_with_a_prompt(tmp_path: Path) -> None:
    main = session(tmp_path)
    bash = command("PreToolUse", "Bash|Monitor")
    record(main, "main").parent.mkdir(parents=True)
    for hook, cmd in [(after_call(main, "PostToolUse"), command("PostToolUse")),
                      (after_call(main, "PostToolUseFailure"), command("PostToolUseFailure")),
                      (prompt(main), command("UserPromptSubmit"))]:
        record(main, "main").write_text(both(BEFORE))
        out = json.loads(run(cmd, hook))["hookSpecificOutput"]
        assert out.keys() == {"hookEventName", "additionalContext"}
        assert out["hookEventName"] == hook["hook_event_name"]
        assert f"context --update {BEFORE} {BEFORE} coordinator`" in out["additionalContext"]
        assert record(main, "main").read_text() == both(head())
        assert delivered(main).exists() == (hook["hook_event_name"] != "UserPromptSubmit")
        if delivered(main).exists():
            aged(delivered(main), 1)
        assert run(bash, call(main, "Bash", {"command": "ls"})) == ""
        assert not delivered(main).exists()


def test_call_within_the_bound_after_a_delivery_is_denied(tmp_path: Path) -> None:
    main = session(tmp_path)
    bash = command("PreToolUse", "Bash|Monitor")
    record(main, "main").parent.mkdir(parents=True)
    record(main, "main").write_text(both(BEFORE))
    run(command("PostToolUse"), after_call(main, "PostToolUse"))
    aged(delivered(main), -60)
    out = json.loads(run(bash, call(main, "Bash", {"command": "ls"})))["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"]
    assert "additionalContext" not in out
    assert record(main, "main").read_text() == both(head())
    assert delivered(main).stat().st_mtime < time.time() + 30


def test_a_call_whose_command_starts_within_the_bound_is_denied(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The age is read at the start of the hook's command, so a call whose
    command started within the bound is denied where `uv run` starts its
    entry past it. The stub `uv` sets the delivery half the bound before the
    `HOOK_STARTED` it is given, then sleeps past the bound, so that no start
    latency of the command decides the outcome."""
    monkeypatch.syspath_prepend(str(checkout.scripts()))
    bound = script("reader_delivery").DELIVERY_BOUND
    main = session(tmp_path)
    record(main, "main").parent.mkdir(parents=True)
    record(main, "main").write_text(both(head()))
    set_delivery = (f'[ -n "$HOOK_STARTED" ] && perl -MTime::HiRes=utime -e '
                    f"'$t = $ENV{{HOOK_STARTED}} - {bound / 2}; utime $t, $t, $ARGV[0]' "
                    f"{delivered(main)}")
    slow = stub_uv(tmp_path, f'{set_delivery}\nsleep {bound * 2}\n'
                             f'exec {shutil.which("uv")} "$@"')
    monkeypatch.setenv("PATH", f"{slow}:{os.environ['PATH']}")
    for cmd, tool in [(command("PreToolUse", "Bash|Monitor"), "Bash"),
                      (command("PreToolUse", "Agent", "context_bound_hook"), "Agent"),
                      (command("PreToolUse", "^(?!(Bash|Monitor|Agent)$).*",
                               "reader_update_hook"), "Read")]:
        delivered(main).touch()
        out = json.loads(run(cmd, call(main, tool, {})))["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny", tool


def test_an_update_at_pre_tool_use_records_its_delivery(tmp_path: Path) -> None:
    main = session(tmp_path)
    bash = command("PreToolUse", "Bash|Monitor")
    record(main, "main").parent.mkdir(parents=True)
    record(main, "main").write_text(both(BEFORE))
    out = json.loads(run(bash, call(main, "Bash", {"command": "ls"})))["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny" and out["additionalContext"]
    assert delivered(main).exists()


def matches(matcher: str | None, tool: str) -> bool:
    """Whether a hook's `matcher` covers `tool`, as Claude Code reads it: an
    exact name or names joined by `|`, and otherwise a regular expression."""
    if matcher in (None, "", "*"):
        return True
    if re.fullmatch(r"[\w|]+", matcher):
        return tool in matcher.split("|")
    return re.search(matcher, tool) is not None


def test_one_pre_tool_use_update_on_each_tool() -> None:
    settings = json.loads((checkout.claude() / "settings.json").read_text())
    for tool in ["Bash", "Monitor", "Agent", "Read", "Edit", "Write", "SendMessage",
                 "SubagentHandback", "Grep", "TaskStop"]:
        giving = [h["command"] for m in settings["hooks"]["PreToolUse"]
                  if matches(m.get("matcher"), tool) for h in m["hooks"]
                  if any(name in h["command"] for name in GIVES_UPDATE)]
        assert len(giving) == 1, (tool, giving)


def test_pre_tool_use_form_on_other_tools(tmp_path: Path) -> None:
    main = session(tmp_path)
    read = command("PreToolUse", "^(?!(Bash|Monitor|Agent)$).*", "reader_update_hook")
    record(main, "main").parent.mkdir(parents=True)
    record(main, "main").write_text(both(BEFORE))
    hook = call(main, "Read", {"file_path": str(checkout.ROOT / "CLAUDE.md")})
    out = json.loads(run(read, hook))["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert f"context --update {BEFORE} {BEFORE} coordinator`" in out["additionalContext"]
    assert record(main, "main").read_text() == both(head())
    aged(delivered(main), 1)
    assert run(read, hook) == ""


def test_an_agent_id_of_another_form_gets_its_record_and_start_diff(tmp_path: Path) -> None:
    main = session(tmp_path)
    earlier_launch(main, stale())
    odd = "agent-of-another-form"
    done = subagent_start(main, odd)
    assert "gave no agent id" in done.stderr
    text = started_with(done)
    assert "Your agent id is" not in text and HELD_HEAD in text
    assert record(main, odd).read_text().startswith(f"{head()}\n")


def test_the_latest_created_transcript_of_the_type_is_the_prediction(tmp_path: Path) -> None:
    """The harness rewrites the `.meta.json` of a subagent that finishes, so
    an earlier launch's may be newer than a later launch's."""
    main = session(tmp_path)
    first = earlier_launch(main, stale(), "a2234567890abcdef")
    earlier_launch(main, current())
    first.write_text(first.read_text())
    assert started_with(subagent_start(main, OPERATOR_ID)) == f"Your agent id is {OPERATOR_ID}."

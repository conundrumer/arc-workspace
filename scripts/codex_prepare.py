"""Native assignment construction and launch input rendering."""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from engine import checkout
from codex_ticket import (Assignment, Phase, Refused, Store, allocate, bound, reconcile, write_atomically)


def prepare(scratch: Path, parameters: dict[str, Any], home: Path,
            previous: str | None = None) -> dict[str, Any]:
    """File and reserve a printed launch before returning native tool arguments."""
    from codex_agent import opening, role_instructions
    from codex_ticket import NATIVE_IDENTITY, NATIVE_PARENT, NATIVE_FINDINGS
    from codex_reports import digest
    from filed_texts import brief_report_file, unfiled
    from operations.roles import CLAUDE_TYPES, CODEX_LAUNCHER, Model, agent_type, described, native_parameters

    binding, store = bound(scratch)
    state = store.snapshot()
    parent = state["agents"][binding.agent]
    if parent["phase"] == Phase.RESERVED and (scratch / "codex-session").exists():
        reconcile(scratch, binding.agent, (scratch / "codex-session").read_text().strip(), home)
        state = store.snapshot()
        parent = state["agents"][binding.agent]
    owner = Assignment.read(store.manifest(binding.agent, parent["revision"]))
    description = described(parameters["description"])
    if description is None:
        raise Refused("launch has no operations role and subject")
    if agent_type(description.role, description.subject) in CLAUDE_TYPES:
        dispatch = {"outcome": "needs-operator", "call": {"tool": "Agent", "arguments": parameters}}
        (scratch / "codex-dispatch.json").write_text(json.dumps(dispatch) + "\n")
        return dispatch
    override = (Model(parameters["model"]) if "model" in parameters
                and parameters.get("subagent_type") != CODEX_LAUNCHER else None)
    model, effort = native_parameters(description.role, description.subject, override)
    undecided: list[str] = []
    text = unfiled(parameters["prompt"], "native assignment", undecided)
    if undecided:
        raise Refused("; ".join(undecided))
    report = brief_report_file(text)
    if report is None:
        raise Refused("native launch requires a filed report path")
    predecessor = None
    if previous is not None and state["agents"][previous]["root_turn"] != parent["root_turn"]:
        predecessor, previous = previous, None
        prior = Assignment.read(store.manifest(predecessor, state["agents"][predecessor]["revision"]))
        text += "\n\n" + NATIVE_FINDINGS.format(predecessor=predecessor) + "\n" + prior.report.read_text()
    agent = previous or allocate(store.path)
    revision = state["agents"][agent]["revision"] + 1 if previous else 1
    directory = store.path / "inputs"
    directory.mkdir(exist_ok=True)
    brief = directory / f"{agent}-{revision}.txt"
    with brief.open("x") as output:
        output.write(text)
    assignment = Assignment(binding.ticket, binding.operator, agent, description.role,
        revision, owner.worktree, brief, store.path / "scratch" / agent, report.resolve(),
        digest(brief.read_bytes()), predecessor=predecessor, subject=description.subject,
        agent_type=agent_type(description.role, description.subject))
    from dataclasses import replace
    assignment = replace(assignment, model=model, effort=effort)
    manifest = store.manifest(assignment.agent, assignment.revision)
    context = role_instructions(checkout.main_worktree(owner.worktree), home, description.role.value, assignment.actual_type)
    identity = NATIVE_IDENTITY.format(agent=agent, scratch=assignment.scratch, manifest=manifest)
    kind = assignment.actual_type
    role = store.role_file(kind)
    declared = role.exists()
    roled = state["agents"][agent].get("role", False) if previous else declared
    if declared:
        write_atomically(role, "developer_instructions = " + json.dumps(context) + "\n")
    message = "\n\n".join([*([] if roled else [context]), identity,
        NATIVE_PARENT.format(parent=parent.get("runtime") or parent["native"]), text,
        opening(kind)])
    launch = {"task_name": agent, "fork_turns": "none", "model": model,
              "reasoning_effort": effort, "message": message}
    if declared and not previous:
        launch["agent_type"] = kind
    if previous:
        launch = {"target": state["agents"][agent].get("runtime") or state["agents"][agent]["native"], "message": message}
    store.file(assignment)
    token = store.reserve(assignment, binding.agent, roled)
    if previous:
        from codex_delivery import message as prepare_message
        prepared = prepare_message(scratch, agent, {'message': message})
        launch = prepared['call']
    return {"assignment": str(manifest), "token": token, "call": launch,
            "tool": "followup_task" if previous else "spawn_agent"}



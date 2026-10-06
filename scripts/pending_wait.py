"""The wait check of the PreToolUse hook: a timed wait whose text gives, by
agent id, an agent pending to the caller, as `profile_runs.py --pending`
gives the agents pending to a run.

A hook input inside a subagent gives the subagent's agent id, and one that
gives none is main's where the main transcript holds the call."""

from pathlib import Path
from typing import Any

from agent_launches import pending_agents
from command_labels import runs_sleep
from controlled_markdown import mctx
from file_ticket import AGENT_ID
from run_reads import blocks, session_agents, session_of
from transcripts import main_transcript, read_entries


def check(hook: dict[str, Any], notes: list[str]) -> str | None:
    """The reason to deny the call `hook` gives, where it waits on an agent
    pending to its caller. A case the check cannot judge goes to
    `notes`."""
    tool, inp = hook["tool_name"], hook["tool_input"]
    if tool == "Bash":
        text = inp["command"]
        if not runs_sleep(text):
            return None
    elif tool == "Monitor":
        text = f"{inp['command']}\n{inp['description']}"
    else:
        raise ValueError(f"the hook is registered on Bash and Monitor, and "
                         f"the input gives tool `{tool}`")
    named = set(AGENT_ID.findall(text))
    if not named:
        return None
    session = session_of(Path(hook["transcript_path"]))
    caller = hook.get("agent_id")
    if caller:
        path = session_agents(session).get(caller)
        if path is None:
            raise ValueError(f"no transcript of agent {caller} under {session}")
    else:
        path = main_transcript(session)
        call = hook["tool_use_id"]
        if not any(b.get("id") == call for e in read_entries(path)
                   for b in blocks(e, "tool_use")):
            notes.append(f"allowed: the hook input gives no agent id, and the "
                         f"main transcript {path} does not hold call {call}, "
                         "so the caller is unknown")
            return None
    undecided: list[str] = []
    waited = [a for a in pending_agents(path, undecided) if a in named]
    notes += [f"undecided: {line}" for line in undecided]
    if not waited:
        return None
    return mctx(
        "Blocked: this call waits on {agents}, which you launched and which "
        "has not reported since its launch or its last resume, by you or by "
        "another agent, so end your turn now, and the harness re-invokes you "
        "when it reports."
    ).format(agents=", ".join(waited))


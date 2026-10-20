"""Ticket-owned Codex identities and nonqueued control admission.

Bindings live in the session scratch directory. Each scratch directory has a
pointer to its ticket store. All mutations use that store's nonblocking lock;
accepted or interrupted turns remain unresolved until actual completion evidence
is reconciled. Enrollment stays disabled until the ticket's live probes pass.
"""

import fcntl
import json
import re
import secrets
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from collections.abc import Iterator

from controlled_markdown import mctx
from operations.roles import AGENT_ID, Role

ENABLED = False
BINDING = "codex-ticket.json"
ROLES = frozenset({Role.CODE_EDITOR, Role.ITEM_CHECKER, Role.DESIGN_REVIEWER})

CONTROL_ROUTE = mctx("Enrolled Codex ticket {ticket}, owning operator {operator}. "
                     "See [Codex](prompts/agents/notes/coordinator.md#codex).")


class Refused(ValueError):
    """The ticket cannot admit the requested mutation."""


class Phase(StrEnum):
    RESERVED = "reserved"
    RUNNING = "running"
    INTERRUPTING = "interrupting"
    ENDED = "ended"


class Terminal(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class Binding:
    ticket: str
    operator: str
    store: Path
    agent: str

    @classmethod
    def read(cls, scratch: Path) -> "Binding | None":
        path = scratch / BINDING
        if not path.exists():
            return None
        value = json.loads(path.read_text())
        binding = cls(value["ticket"], value["operator"], Path(value["store"]), value["agent"])
        if not binding.store.is_absolute() or not re.fullmatch(AGENT_ID, binding.agent):
            raise Refused("invalid Codex ticket binding")
        return binding

    def correction(self) -> str:
        return CONTROL_ROUTE.format(ticket=self.ticket, operator=self.operator)


@dataclass(frozen=True)
class Assignment:
    ticket: str
    operator: str
    agent: str
    role: Role
    revision: int
    worktree: Path
    brief: Path
    scratch: Path
    report: Path
    inputs_digest: str
    predecessor: str | None = None

    def document(self) -> dict[str, Any]:
        return {k: str(v) if isinstance(v, Path) else v for k, v in asdict(self).items()}

    @classmethod
    def read(cls, path: Path) -> "Assignment":
        value = json.loads(path.read_text())
        value["role"] = Role(value["role"])
        for key in ("worktree", "brief", "scratch", "report"):
            value[key] = Path(value[key])
            if not value[key].is_absolute():
                raise Refused(f"assignment {key} must be absolute")
        out = cls(**value)
        if (out.role not in ROLES or out.revision < 1
                or not re.fullmatch(AGENT_ID, out.agent)
                or not re.fullmatch(r"[0-9a-f]{64}", out.inputs_digest)):
            raise Refused("invalid native assignment")
        return out


class Store:
    def __init__(self, path: Path):
        self.path = path.resolve()

    @contextmanager
    def locked(self) -> Iterator[dict[str, Any]]:
        """Lock admission and updates; callers release this before daemon waits."""
        self.path.mkdir(parents=True, exist_ok=True)
        with (self.path / "lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Refused("ticket control is busy; input was not queued") from exc
            try:
                path = self.path / "state.json"
                state = json.loads(path.read_text()) if path.exists() else {"agents": {}}
                yield state
                temporary = self.path / "state.tmp"
                temporary.write_text(json.dumps(state, sort_keys=True) + "\n")
                temporary.replace(path)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def file(self, assignment: Assignment) -> Path:
        """File an immutable assignment and its scratch pointer under the lock."""
        with self.locked() as state:
            if state.get("ticket", assignment.ticket) != assignment.ticket:
                raise Refused("store belongs to another ticket")
            if state.get("operator", assignment.operator) != assignment.operator:
                raise Refused("store belongs to another operator")
            directory = self.path / "assignments"
            directory.mkdir(exist_ok=True)
            path = directory / f"{assignment.agent}-{assignment.revision}.json"
            with path.open("x") as output:
                output.write(json.dumps(assignment.document(), sort_keys=True) + "\n")
            assignment.scratch.mkdir(parents=True, exist_ok=True)
            binding = assignment.scratch / BINDING
            value = {"ticket": assignment.ticket, "operator": assignment.operator,
                     "agent": assignment.agent, "store": str(self.path)}
            if binding.exists() and json.loads(binding.read_text()) != value:
                path.unlink()
                raise Refused("scratch belongs to another ticket identity")
            binding.write_text(json.dumps(value) + "\n")
            state.update(ticket=assignment.ticket, operator=assignment.operator)
            return path

    def reserve(self, assignment: Assignment, parent: str | None = None) -> str:
        """Reserve a turn before transport submission, without holding a wait lock."""
        with self.locked() as state:
            filed = Assignment.read(self.path / "assignments" / f"{assignment.agent}-{assignment.revision}.json")
            if filed != assignment or state["ticket"] != assignment.ticket or state["operator"] != assignment.operator:
                raise Refused("submission does not match its filed assignment")
            agents = state["agents"]
            if parent is None:
                if any(a["phase"] != Phase.ENDED for a in agents.values()):
                    raise Refused("ticket has live or unresolved turns; input was not queued")
                root = state.get("root")
                if root is not None and root != assignment.agent:
                    raise Refused("ticket already owns a different root")
                state["root"] = assignment.agent
                state["interrupted"] = False
            else:
                if state.get("interrupted"):
                    raise Refused("root interruption has started; no child may launch")
                if parent not in agents or agents[parent]["phase"] != Phase.RUNNING:
                    raise Refused("native parent is not running in this ticket")
            old = agents.get(assignment.agent)
            if old is not None and old["phase"] != Phase.ENDED:
                raise Refused("assignment already has an unresolved turn")
            if old is not None and assignment.revision <= old["revision"]:
                raise Refused("resume requires a new assignment revision")
            if parent is not None and old is not None and old["root_turn"] != agents[parent]["root_turn"]:
                raise Refused("an old child requires a fresh checker identity after root resume")
            token = secrets.token_hex(16)
            agents[assignment.agent] = {"phase": Phase.RESERVED, "token": token,
                "revision": assignment.revision, "parent": parent,
                "root_turn": token if parent is None else agents[parent]["root_turn"],
                "native": old["native"] if old is not None else None,
                "turn": None, "validated": False}
            return token

    def accepted(self, agent: str, token: str, native: str, turn: str):
        with self.locked() as state:
            item = state["agents"][agent]
            if item["token"] != token or item["phase"] not in (Phase.RESERVED, Phase.INTERRUPTING):
                raise Refused("acceptance does not match the unresolved submission")
            if any(aid != agent and other["native"] == native for aid, other in state["agents"].items()):
                raise Refused("native identity already belongs to another assignment")
            previous = item.get("native")
            if previous is not None and previous != native:
                raise Refused("accepted root identity changed")
            item.update(native=native, turn=turn)
            if item["phase"] != Phase.INTERRUPTING:
                item["phase"] = Phase.RUNNING

    def interrupting(self, agent: str) -> tuple[str, str] | None:
        """Invalidate first, then let the caller send the interrupt outside the lock."""
        with self.locked() as state:
            item = state["agents"][agent]
            if agent == state["root"]:
                state["interrupted"] = True
            if item["phase"] == Phase.ENDED:
                return None
            item.update(phase=Phase.INTERRUPTING, validated=False)
            selected = ((item["native"], item["turn"])
                        if item["native"] is not None and item["turn"] is not None else None)
        if selected is None:
            raise Refused("submission is unresolved; reconcile its accepted turn before interruption")
        return selected

    def ended(self, agent: str, turn: str, status: str):
        """Reconcile only a terminal event for the saved turn; repetition is harmless."""
        try:
            terminal = Terminal(status)
        except ValueError as exc:
            raise Refused("event does not establish a terminal turn") from exc
        with self.locked() as state:
            item = state["agents"][agent]
            if item["turn"] != turn:
                raise Refused("completion belongs to another turn")
            if item["phase"] == Phase.ENDED:
                if item["status"] != terminal:
                    raise Refused("terminal evidence contradicts the recorded completion")
                return
            interrupted = item["phase"] == Phase.INTERRUPTING or state.get("interrupted")
            item.update(phase=Phase.ENDED, status=terminal,
                        validated=item["validated"] if not interrupted and terminal is Terminal.COMPLETED else False)

    def target(self, sender: str, target: str) -> str:
        """Resolve only an identity within the sender's current native tree."""
        with self.locked() as state:
            agents = state["agents"]
            if sender not in agents or agents[sender]["phase"] != Phase.RUNNING:
                raise Refused("sender is not running in this ticket")
            matches = [a for aid, a in agents.items() if aid == target or a["native"] == target]
            if (len(matches) != 1 or matches[0]["native"] is None
                    or matches[0]["root_turn"] != agents[sender]["root_turn"]):
                raise Refused("target is outside this ticket's native tree")
            return matches[0]["native"]


def allocate(session_scratch: Path) -> str:
    """Reserve a collision-checked operations identity apart from native UUIDs."""
    directory = session_scratch / "codex-identities"
    directory.mkdir(parents=True, exist_ok=True)
    while True:
        agent = "a" + secrets.token_hex(8)
        try:
            (directory / agent).mkdir()
        except FileExistsError:
            continue
        return agent


def legacy_guard(scratch: Path) -> Binding | None:
    binding = Binding.read(scratch)
    if binding is not None:
        raise Refused("legacy mutation refused for " + binding.correction())
    return None


def interrupt(scratch: Path, transport: Any) -> bool:
    binding = Binding.read(scratch)
    if binding is None:
        return False
    store = Store(binding.store)
    selected = store.interrupting(binding.agent)
    if selected is None:
        return True
    thread, turn = selected
    client = transport()
    try:
        client.call("turn/interrupt", {"threadId": thread, "turnId": turn})
    finally:
        client.close()
    return True

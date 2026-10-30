"""Ticket-owned Codex identities and nonqueued control admission.

    uv run python scripts/codex_ticket.py prepare <scratch> <parameters-json> [--previous <agent>]
    uv run python scripts/codex_ticket.py reconcile <scratch> <agent> <native-thread>
    uv run python scripts/codex_ticket.py accept <scratch> <agent> --outcome <outcome>
    uv run python scripts/codex_ticket.py target <scratch> <agent>
    uv run python scripts/codex_ticket.py dispatch <scratch> [--call <call-json>]
    uv run python scripts/codex_ticket.py message <scratch> <agent> <message-json>
    uv run python scripts/codex_ticket.py received <scratch> <delivery>

Prepare files and reserves a launch, then returns its native tool arguments.
Reconcile requires accepted rollout evidence, and settles the unresolved
descendants of its agent first. Accept validates the report of a
terminal turn; outcome is finished or needs-operator. Target resolves a native
recipient. Dispatch records input needed from the owning operator. Message
prepares a native message to a running agent and prints its call and the
reconcile command to run after it. Received acknowledges a delivery id that the
running recipient took.

Bindings live in the session scratch directory. Each scratch directory has a
pointer to its ticket store. All mutations use that store's nonblocking lock;
accepted or interrupted turns remain unresolved until actual completion evidence
is reconciled, which the next reconcile of the turn or of an ancestor does, and a
root resume does before it reserves.
"""

import fcntl
import json
import re
import secrets
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from collections.abc import Iterator

from controlled_markdown import mctx
from engine import checkout
from operations.roles import AGENT_ID, CODEX_ROLES, ReasoningEffort, Role

BINDING = "codex-ticket.json"
ROLES = frozenset(CODEX_ROLES)

CONTROL_ROUTE = mctx("Enrolled Codex ticket {ticket}, owning operator {operator}. "
                     "See [Codex](prompts/agents/notes/ops.md#codex).")


class Refused(ValueError):
    """The ticket cannot admit the requested mutation."""


class Phase(StrEnum):
    RESERVED = "reserved"
    RUNNING = "running"
    INTERRUPTING = "interrupting"
    ENDED = "ended"


from operations.attempts import Terminal


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
    subject: str | None = None
    agent_type: str | None = None
    model: str | None = None
    effort: ReasoningEffort | None = None

    @property
    def seat(self):
        from operations.roles import Described
        return Described(self.role, self.subject or self.ticket)

    @property
    def actual_type(self) -> str:
        return self.agent_type or self.role.agent_type

    def document(self) -> dict[str, Any]:
        return {k: str(v) if isinstance(v, Path) else v for k, v in asdict(self).items()}

    @classmethod
    def read(cls, path: Path) -> "Assignment":
        value = json.loads(path.read_text())
        value["role"] = Role(value["role"])
        if value.get("effort") is not None:
            value["effort"] = ReasoningEffort(value["effort"])
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

    def snapshot(self) -> dict[str, Any]:
        return json.loads((self.path / "state.json").read_text())

    def manifest(self, agent: str, revision: int) -> Path:
        return self.path / "assignments" / f"{agent}-{revision}.json"

    def refused(self, agent: str, token: str):
        """Release only a submission the caller proved was never accepted."""
        with self.locked() as state:
            item = state["agents"][agent]
            if item["phase"] != Phase.RESERVED or item["token"] != token:
                raise Refused("refusal does not match an unaccepted reservation")
            item.update(phase=Phase.ENDED, status=Terminal.FAILED, refused=True)

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
            from codex_attempts import committed
            committed(self, state)

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

    def role_file(self, kind: str) -> Path:
        """The config file of the Codex agent role `kind` in this store."""
        return self.path / "roles" / f"{kind}.toml"

    def reserve(self, assignment: Assignment, parent: str | None = None, role: bool = False,
                reservation: str | None = None) -> str:
        from contextlib import nullcontext
        import time
        from attempt_record import Record, backfill, seat_lock
        from operations.attempts import Launched, Transport, Refused as SubmissionRefused
        from operations.roles import Described

        record = Record()
        seat = assignment.seat
        token = reservation or secrets.token_hex(16)
        at = time.time()
        old = self.snapshot()['agents'].get(assignment.agent)
        launched = old.get('launched', old['reserved']) if old else at
        existing = next((e for e in record.events([assignment.agent])
                         if isinstance(e, Launched) and e.agent == assignment.agent), None)
        launch = existing or Launched(source='native-launch:' + assignment.agent, at=launched,
            agent=assignment.agent, seat=seat, parent=parent or assignment.operator,
            agent_type=assignment.actual_type, transport=Transport.NATIVE,
            scratch=str(assignment.scratch))
        with (nullcontext() if reservation else seat_lock(seat, record)):
            if reservation is None:
                backfill(record, record.path.parent.parent, Path.home(), seat,
                         change=assignment.ticket)
                record.admission(seat, assignment.agent, token, assignment.revision, at, launch, assignment.ticket)
            else:
                held = [e for e in record.events([assignment.agent])
                        if getattr(e, 'reservation', None) == token]
                if not held:
                    raise Refused('missing durable submission reservation')
                at = held[0].at
            try:
                return self._reserve(assignment, parent, role, token, at, launched)
            except Exception:
                from attempt_record import observe
                observe(lambda: record.append(SubmissionRefused(source='refused:' + token,
                    at=at, agent=assignment.agent, reservation=token)))
                raise

    def _reserve(self, assignment: Assignment, parent: str | None, role: bool,
                 token: str, at: float, launched: float) -> str:
        """Reserve a turn before transport submission, without holding a wait lock."""
        with self.locked() as state:
            filed = Assignment.read(self.path / "assignments" / f"{assignment.agent}-{assignment.revision}.json")
            if filed != assignment or state["ticket"] != assignment.ticket or state["operator"] != assignment.operator:
                raise Refused("submission does not match its filed assignment")
            agents = state["agents"]
            if parent is None:
                unresolved = ", ".join(f"{aid} {a['phase']}" for aid, a in agents.items()
                                       if a["phase"] != Phase.ENDED)
                if unresolved:
                    raise Refused(f"ticket has live or unresolved turns ({unresolved}); input was not queued")
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
            if old is not None:
                state.setdefault("history", []).append({"agent": assignment.agent, **old})
            agents[assignment.agent] = {"phase": Phase.RESERVED, "token": token,
                "revision": assignment.revision, "parent": parent,
                "root_turn": token if parent is None else agents[parent]["root_turn"],
                "native": old["native"] if old is not None else None,
                "runtime": old.get("runtime") if old is not None else None,
                "turn": None, "validated": False,
                "role": old.get("role", False) if old is not None else role}
            import time
            agents[assignment.agent]["reserved"] = at
            agents[assignment.agent]["launched"] = launched
            return token

    def receipt(self, agent: str, turn: str, receipt: dict[str, Any]):
        """Publish a validator receipt only for an uninterrupted terminal turn."""
        with self.locked() as state:
            item = state["agents"][agent]
            if (item["phase"] != Phase.ENDED or item["turn"] != turn
                    or item["status"] != Terminal.COMPLETED or state.get("interrupted")
                    or receipt["revision"] != item["revision"]):
                raise Refused("receipt has no current completed turn")
            if any(other["phase"] != Phase.ENDED for aid, other in state["agents"].items()
                   if other["parent"] == agent or (agent == state["root"] and aid != agent)):
                raise Refused("assignment has live or unresolved descendants")
            if receipt["outcome"] == "finished" and any(
                    (not other["validated"] or other.get("receipt", {}).get("outcome") != "finished")
                    and not other.get("refused")
                    for aid, other in state["agents"].items()
                    if aid != agent and other["root_turn"] == item["root_turn"]
                    and (agent == state["root"] or other["parent"] == agent)):
                raise Refused("finished assignment has descendants without validated results")
            item.update(validated=True, receipt=receipt)

    def accepted(self, agent: str, token: str, native: str, turn: str, runtime: str | None = None):
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
            if runtime is not None:
                item["runtime"] = runtime
                if item["parent"] is not None and runtime.startswith("/"):
                    agents = state["agents"]
                    agents[item["parent"]]["runtime"] = runtime.rsplit("/", 1)[0]
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
            if terminal is Terminal.COMPLETED and any(
                    other["phase"] != Phase.ENDED
                    and (other["parent"] == agent or (agent == state["root"] and aid != agent))
                    for aid, other in state["agents"].items()):
                raise Refused("assignment has live or unresolved descendants")
            interrupted = item["phase"] == Phase.INTERRUPTING or state.get("interrupted")
            item.update(phase=Phase.ENDED, status=terminal,
                        validated=item["validated"] if not interrupted and terminal is Terminal.COMPLETED else False)

    def target(self, sender: str, target: str) -> str:
        """Resolve only an identity within the sender's current native tree."""
        with self.locked() as state:
            agents = state["agents"]
            if sender not in agents or agents[sender]["phase"] != Phase.RUNNING:
                raise Refused("sender is not running in this ticket")
            matches = [a for aid, a in agents.items()
                       if aid == target or a["native"] == target or a.get("runtime") == target]
            if (len(matches) != 1 or matches[0]["native"] is None
                    or matches[0]["root_turn"] != agents[sender]["root_turn"]):
                raise Refused("target is outside this ticket's native tree")
            return matches[0].get("runtime") or matches[0]["native"]


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
    state = store.snapshot()
    selected_agents = {binding.agent}
    while added := {aid for aid, item in state["agents"].items()
                    if item["parent"] in selected_agents} - selected_agents:
        selected_agents.update(added)
    pending = []
    failures = []
    for aid in sorted(selected_agents, key=lambda aid: aid != binding.agent):
        try:
            if (selected := store.interrupting(aid)) is not None:
                pending.append(selected)
        except Refused as exc:
            failures.append(str(exc))
    if pending:
        client = transport()
        try:
            for thread, turn in pending:
                client.call("turn/interrupt", {"threadId": thread, "turnId": turn})
        finally:
            client.close()
    if failures:
        raise Refused("; ".join(failures))
    return True


def bound(scratch: Path) -> tuple[Binding, Store]:
    binding = Binding.read(scratch)
    if binding is None:
        raise Refused("scratch has no native assignment")
    return binding, Store(binding.store)


def register(store: Path, session_scratch: Path, root: str):
    directory = session_scratch / "codex-stores"
    directory.mkdir(parents=True, exist_ok=True)
    pointer = directory / f"{root}.json"
    value = {"store": str(store.resolve())}
    if pointer.exists() and json.loads(pointer.read_text()) != value:
        raise Refused("root is already registered in another native store")
    temporary = pointer.with_suffix(".tmp")
    temporary.write_text(json.dumps(value) + "\n")
    temporary.replace(pointer)


def child_types() -> list[str]:
    """The agent types of a Codex child: those outside `CLAUDE_TYPES`."""
    from operations.roles import ANALYST_TYPES, CLAUDE_TYPES, CODEX_ROLES

    return sorted({*(r.agent_type for r in CODEX_ROLES), *ANALYST_TYPES.values()} - CLAUDE_TYPES)


def role_declarations(store: Store) -> dict[str, str]:
    """The `agents.<type>` config of each Codex child type's role whose file
    `store` holds."""
    return {key: value for kind in child_types() if store.role_file(kind).exists()
            for key, value in (
        (f"agents.{kind}.description", kind),
        (f"agents.{kind}.config_file", str(store.role_file(kind))))}


def write_atomically(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, suffix=".tmp", delete=False) as output:
        output.write(text)
    Path(output.name).replace(path)


def declare_roles(store: Store) -> None:
    """Write a stub file for each child type's role that has none, so that a
    thread started now loads the declaration."""
    for kind in child_types():
        if not store.role_file(kind).exists():
            write_atomically(store.role_file(kind), f"name = {json.dumps(kind)}\n")


def prepare(scratch: Path, parameters: dict[str, Any], home: Path,
            previous: str | None = None) -> dict[str, Any]:
    from codex_prepare import prepare as prepare_native

    return prepare_native(scratch, parameters, home, previous)


NATIVE_IDENTITY = mctx("Your operations agent id is `{agent}`. Your native assignment is "
                       "`{manifest}` and your scratch directory is `{scratch}`.")
NATIVE_PARENT = mctx("Your native parent's id is `{parent}`.")
NATIVE_FINDINGS = mctx("Previous report from `{predecessor}`:")


def reconcile(scratch: Path, agent: str, native: str, home: Path) -> dict[str, Any]:
    from codex_reconcile import reconcile as reconcile_evidence

    return reconcile_evidence(scratch, agent, native, home)


def accept(scratch: Path, agent: str, home: Path, outcome: str) -> dict[str, Any]:
    """Accept a report from current terminal execution through the shared validator."""
    from codex_reads import native_execution
    from codex_reports import Evidence, Outcome, validate

    _, store = bound(scratch)
    item = store.snapshot()["agents"][agent]
    if item["native"] is None:
        raise Refused("submission has no accepted native identity")
    item = reconcile(scratch, agent, item["native"], home)
    if item["phase"] != Phase.ENDED or item["status"] != Terminal.COMPLETED:
        raise Refused("report has no completed execution")
    manifest = store.manifest(agent, item["revision"])
    assignment = Assignment.read(manifest)
    entries, reply = native_execution(assignment, item, home)
    receipt = validate(manifest, reply, Evidence(agent, assignment.revision,
                       assignment.inputs_digest, entries), Outcome(outcome))
    value = {key: str(value) if isinstance(value, Path) else value
             for key, value in asdict(receipt).items()}
    store.receipt(agent, item["turn"], value)
    if receipt.outcome == Outcome.NEEDS_OPERATOR:
        dispatch = assignment.scratch / "codex-dispatch.json"
        return {**value, "dispatch": json.loads(dispatch.read_text()) if dispatch.exists()
                else {"outcome": "needs-operator"}}
    return value


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    send = commands.add_parser("message")
    send.add_argument("scratch", type=Path)
    send.add_argument("agent")
    send.add_argument("parameters", type=Path)
    receive = commands.add_parser("received")
    receive.add_argument("scratch", type=Path)
    receive.add_argument("delivery")
    launch = commands.add_parser("prepare")
    launch.add_argument("scratch", type=Path)
    launch.add_argument("parameters", type=Path)
    launch.add_argument("--previous")
    sync = commands.add_parser("reconcile")
    sync.add_argument("scratch", type=Path)
    sync.add_argument("agent")
    sync.add_argument("native")
    result = commands.add_parser("accept")
    result.add_argument("scratch", type=Path)
    result.add_argument("agent")
    result.add_argument("--outcome", choices=("finished", "needs-operator"), required=True)
    target = commands.add_parser("target")
    target.add_argument("scratch", type=Path)
    target.add_argument("agent")
    dispatch = commands.add_parser("dispatch")
    dispatch.add_argument("scratch", type=Path)
    dispatch.add_argument("--call", type=Path)
    args = parser.parse_args()
    main_tree = checkout.main_worktree(checkout.ROOT)
    if checkout.ROOT != main_tree:
        print(f"codex_ticket: run in the main tree {main_tree}", file=sys.stderr)
        return 2
    try:
        if args.action == "message":
            from codex_delivery import message
            out = message(args.scratch, args.agent, json.loads(args.parameters.read_text()))
        elif args.action == "received":
            from codex_delivery import received
            out = received(args.scratch, args.delivery, Path.home())
        elif args.action == "prepare":
            out = prepare(args.scratch, json.loads(args.parameters.read_text()), Path.home(), args.previous)
        elif args.action == "reconcile":
            out = reconcile(args.scratch, args.agent, args.native, Path.home())
        elif args.action == "accept":
            out = accept(args.scratch, args.agent, Path.home(), args.outcome)
        elif args.action == "target":
            binding, store = bound(args.scratch)
            out = {"native": store.target(binding.agent, args.agent)}
        else:
            binding, store = bound(args.scratch)
            if store.snapshot()["agents"][binding.agent]["phase"] != Phase.RUNNING:
                raise Refused("dispatch requires a running assignment")
            out = {"outcome": "needs-operator"}
            if args.call is not None:
                out["call"] = json.loads(args.call.read_text())
            (args.scratch / "codex-dispatch.json").write_text(json.dumps(out) + "\n")
        print(json.dumps(out))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"codex_ticket: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

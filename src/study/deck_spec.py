"""The spec of a concept-decision card: one task, the question of which
model is its concept, and the options, the models under consideration,
each a solver's case whose output stands for it. A deck is the page of the
cards made at once:

    uv run python scripts/concept_deck.py <name> <spec>.json ...

A spec is a JSON object:

    {"task": "20a9e565",
     "question": "By what rule does the series grow on into the window?",
     "options": [
       {"name": "Stages", "text": "One sentence on the model.",
        "case": "concept"},
       {"name": "Slots", "text": "One sentence on the model.",
        "case": "concept", "root": ".claude/worktrees/agent-a925"},
       {"name": "Demonstration", "text": "One sentence on the model.",
        "case": "$Demonstration", "root": ".claude/worktrees/agent-a925"}],
     "witnesses": "programs/witnesses/20a9e565.wit.json",
     "witness_ids": ["stray-marker", "two-figures"]}

`options` are numbered in the order given; the model the solver has today
goes first, so the first answer keeps it.
Each names the case that gives its output, as the witness file writes a
name, and the checkout whose solver and lib run it, a path from the root
of the checkout the command runs in or absolute, that checkout where it
gives none. `witnesses` is the file whose entries the card draws, from
that root or absolute, which stands under `programs/witnesses/` of the
checkout whose solver's `@witness` lines hold its verdicts; without it,
the task's witness file in the first option's checkout. `witness_ids`
picks entries of that file, in the order given; without it, every entry in
file order that reassigns nothing and is no `@derive` or `@store` branch's
witness, since those test a parameterization and not the concept."""

import json
from dataclasses import dataclass
from pathlib import Path

from engine import checkout
from study.card_spec import from_root


@dataclass(frozen=True)
class Option:
    """One model under consideration: a short name, the column head; one
    sentence, the option's text; the case that gives its output; and the
    checkout whose solver and lib run that case."""

    name: str
    text: str
    case: str
    root: Path


@dataclass(frozen=True)
class CardSpec:
    """One card: the task, its question, its options in order, the witness
    file whose entries it draws and the entries drawn, each None where the
    spec gives none."""

    task_id: str
    question: str
    options: tuple[Option, ...]
    witness_file: Path | None
    witness_ids: tuple[str, ...] | None


def load_spec(path: Path) -> CardSpec:
    """The card spec in the JSON file at `path`. A file off the form the
    module docstring gives is a `ValueError` naming the file and the
    part."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: not JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the spec is a JSON object")
    spec: dict[str, object] = data

    def text(key: str, where: dict[str, object], at: str) -> str:
        value = where.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path}: {at}`{key}` is a non-empty string")
        return value.strip()

    for key in spec:
        if key not in _KEYS:
            raise ValueError(f"{path}: `{key}` is no field of a spec")
    options_raw = spec.get("options")
    if not isinstance(options_raw, list) or len(options_raw) < 2:
        raise ValueError(f"{path}: `options` lists two options or more")
    options: list[Option] = []
    for i, raw in enumerate(options_raw):
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: option {i + 1} is an object")
        option: dict[str, object] = raw
        for key in option:
            if key not in _OPTION_KEYS:
                raise ValueError(
                    f"{path}: option {i + 1}: `{key}` is no field of an option")
        at = f"option {i + 1}: "
        root = option.get("root")
        if root is not None and not isinstance(root, str):
            raise ValueError(f"{path}: {at}`root` is a path")
        options.append(Option(
            text("name", option, at), text("text", option, at),
            text("case", option, at),
            from_root(root) if root else checkout.ROOT))
    witnesses = spec.get("witnesses")
    if witnesses is not None and not isinstance(witnesses, str):
        raise ValueError(f"{path}: `witnesses` is a path")
    ids = spec.get("witness_ids")
    if ids is not None and not (isinstance(ids, list) and ids and all(
            isinstance(w, str) for w in ids)):
        raise ValueError(f"{path}: `witness_ids` lists witness ids")
    return CardSpec(
        text("task", spec, ""), text("question", spec, ""), tuple(options),
        from_root(witnesses) if witnesses else None,
        tuple(ids) if ids else None)


_KEYS = ("task", "question", "options", "witnesses", "witness_ids")
_OPTION_KEYS = ("name", "text", "case", "root")

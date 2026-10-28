"""Generate engine/lib/study-meanings.json from definition doc comments.

Run with --check to reject a stale catalogue without writing it. Registry
items have ;;; prose or a single ;;; @doc <repo-path>#<declaration> link.
Links read the existing /// doc of a Souffle or Rust declaration, or the
;;; doc of an arclog proposer. The registry's named context blocks supply
the shared text. This reads documentation anchors, not s-expression bodies;
the engine registry reader remains responsible for validating those bodies.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path("engine/lib/registry.sexpr")
OUTPUT = Path("engine/lib/study-meanings.json")
ITEM = re.compile(r"^\((relation|macro|component|fact|proposer) (\w+)\b")
CONTEXTS = ("general_contract", "proposer_context")


@dataclass(frozen=True)
class Doc:
    path: Path
    start: int
    end: int
    text: str


def preceding(path: Path, lines: list[str], at: int, mark: str) -> Doc:
    """The contiguous item doc immediately before a declaration or its attributes."""
    end = at
    while at and lines[at - 1].startswith("#["):
        at -= 1
    end = at
    while at and (lines[at - 1] == mark or lines[at - 1].startswith(mark + " ")):
        at -= 1
    if at == end:
        raise ValueError(f"{path}:{end + 1}: missing item documentation")
    prose = "\n".join(line[len(mark):].removeprefix(" ") for line in lines[at:end])
    if not prose.strip():
        raise ValueError(f"{path}:{at + 1}: empty item documentation")
    return Doc(path, at + 1, end, prose)


def linked(root: Path, target: str) -> Doc:
    path_text, sep, name = target.partition("#")
    path = Path(path_text)
    if not sep or not name or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"invalid documentation anchor: {target}")
    lines = (root / path).read_text().splitlines()
    patterns = {
        ".dl": rf"\.(?:decl|comp) {re.escape(name)}\b",
        ".rs": rf"pub struct {re.escape(name)}\b",
        ".arclog": rf"\(proposer {re.escape(name)}\b",
    }
    if path.suffix not in patterns:
        raise ValueError(f"unsupported documentation source: {target}")
    pattern = re.compile(patterns[path.suffix])
    matches = [i for i, line in enumerate(lines) if pattern.match(line)]
    if len(matches) != 1:
        raise ValueError(f"{target}: expected one declaration, found {len(matches)}")
    return preceding(path, lines, matches[0], ";;;" if path.suffix == ".arclog" else "///")


def summary(text: str) -> str:
    """The opening paragraph, stopping before the port list of an item."""
    lines: list[str] = []
    for line in text.splitlines():
        if not line.strip() or (lines and line.lstrip().startswith("- ")):
            break
        lines.append(line.strip())
    return " ".join(lines).removeprefix("- ")


def catalogue(root: Path = ROOT) -> dict[str, object]:
    lines = (root / REGISTRY).read_text().splitlines()
    contexts: dict[str, str] = {}
    entries: dict[str, object] = {}
    for i, line in enumerate(lines):
        if line in {";;; @" + field for field in CONTEXTS}:
            field = line.removeprefix(";;; @")
            if field in contexts:
                raise ValueError(f"duplicate context: {field}")
            end = i + 1
            while end < len(lines) and lines[end] != ";;; @end":
                if lines[end] != ";;;" and not lines[end].startswith(";;; "):
                    raise ValueError(f"{REGISTRY}:{end + 1}: unclosed context")
                end += 1
            if end == len(lines):
                raise ValueError(f"unclosed context: {field}")
            contexts[field] = "\n".join(x[3:].removeprefix(" ") for x in lines[i + 1:end])
            if not contexts[field].strip():
                raise ValueError(f"empty context: {field}")
        match = ITEM.match(line)
        if match is None:
            continue
        kind, name = match.groups()
        key = ("fact:" if kind == "fact" else "lib:") + name
        if key in entries:
            raise ValueError(f"duplicate registry identity: {key}")
        doc = preceding(REGISTRY, lines, i, ";;;")
        if doc.text.startswith("@doc "):
            if "\n" in doc.text:
                raise ValueError(f"{key}: a doc link must stand alone")
            doc = linked(root, doc.text.removeprefix("@doc "))
        elif doc.text.startswith("@"):
            raise ValueError(f"{key}: unknown documentation directive: {doc.text}")
        entries[key] = {
            "status": "authored_contract",
            "summary": summary(doc.text),
            "contract_markdown": doc.text,
            "source": {"document": doc.path.as_posix(), "start_line": doc.start, "end_line": doc.end},
            "section": {"relation": "Relations", "macro": "Relations", "component": "Components",
                        "proposer": "Proposers", "fact": "Facts"}[kind],
        }
    if set(contexts) != set(CONTEXTS):
        raise ValueError(f"missing contexts: {set(CONTEXTS) - contexts.keys()}")
    if not entries:
        raise ValueError("registry has no documented items")
    return {
        "schema": "arclog-study-meanings-v1",
        "source": "generated by scripts/generate_study_meanings.py from engine/lib/registry.sexpr and its @doc definition comments",
        **contexts,
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        rendered = json.dumps(catalogue(), ensure_ascii=False, indent=2) + "\n"
        path = ROOT / OUTPUT
        if args.check:
            if not path.exists() or path.read_text() != rendered:
                parser.exit(1, f"{OUTPUT} is stale; run uv run python scripts/generate_study_meanings.py\n")
        else:
            path.write_text(rendered)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

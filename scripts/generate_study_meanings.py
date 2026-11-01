"""Generate engine/lib/study-meanings.json, docs/arclog/lib.md and
docs/arclog/lib-rare.md from the registry.

Run with --check to reject a stale output without writing it. A registry
`type`, `fact` or `component` item has ;;; prose. A `relation`, `macro` or
`proposer` item may have none: its JSON entry has an empty `summary` and
`contract_markdown` and no line range in `source`, and its entry in the
markdown is its signature alone. A ;;; block that is present is non-empty. A ;;; block
whose first line is ";;; @rare" marks a rare item. That line is a directive:
it is not prose, so an item with that line alone has no prose. The rare items
stand in docs/arclog/lib-rare.md, under the same section headings as in
docs/arclog/lib.md, which leaves them out. The registry's named context
blocks supply the shared text, and they stand in docs/arclog/lib.md alone. The JSON reads
documentation anchors only. The markdown also reads each item's `columns`,
`modes`, `type-parameters`, `inputs` and `outputs` forms, and the kind of a
component, which it shows on the entry head of a construction; the engine registry reader remains responsible for validating
those forms, including that a macro's declared column types and modes are the
ones the engine derives from its definition. In a component entry, a prose
bullet that has the form "`<port>`: <text>" for one port of the component moves
onto that port's line.
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
LIBRARY = Path("docs/arclog/lib.md")
RARE_LIBRARY = Path("docs/arclog/lib-rare.md")
RARE = ";;; @rare"
PROSE_OPTIONAL = ("relation", "macro", "proposer")
ITEM = re.compile(r"^\((relation|macro|component|fact|proposer|type) (\w+)\b")
CONTEXTS = ("general_contract", "proposer_context")
SECTIONS = {"type": "Types", "fact": "Facts", "relation": "Relations", "macro": "Relations",
            "component": "Components", "proposer": "Proposers"}
PORT_FORMS = ("default", "copies", "frames")
PORT_BULLET = re.compile(r"`([^`]+)`: (.*)")

type Form = str | list[Form]


@dataclass(frozen=True)
class Doc:
    path: Path
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Item:
    kind: str
    name: str
    key: str
    doc: Doc
    form: list[Form]
    rare: bool = False


def preceding(lines: list[str], at: int, optional: bool = False) -> tuple[Doc, bool]:
    """The contiguous ;;; item doc immediately before the item at line `at`,
    and whether its first line is the `@rare` directive, which is not prose.
    Where there is no prose and `optional` is set, the doc is empty."""
    end = at
    while at and (lines[at - 1] == ";;;" or lines[at - 1].startswith(";;; ")):
        at -= 1
    rare = at < end and lines[at] == RARE
    if rare:
        at += 1
    if at == end:
        if optional:
            return Doc(REGISTRY, end + 1, end, ""), rare
        if rare:
            raise ValueError(f"{REGISTRY}:{end + 1}: empty item documentation")
        raise ValueError(f"{REGISTRY}:{end + 1}: missing item documentation")
    prose = "\n".join(line[3:].removeprefix(" ") for line in lines[at:end])
    if not prose.strip():
        raise ValueError(f"{REGISTRY}:{at + 1}: empty item documentation")
    return Doc(REGISTRY, at + 1, end, prose), rare


def summary(text: str) -> str:
    """The opening paragraph, stopping before the port list of an item."""
    lines: list[str] = []
    for line in text.splitlines():
        if not line.strip() or (lines and line.lstrip().startswith("- ")):
            break
        lines.append(line.strip())
    return " ".join(lines).removeprefix("- ")


def forms(lines: list[str]) -> dict[int, list[Form]]:
    """Each top-level form of the registry, by the index of its first line."""
    found: dict[int, list[Form]] = {}
    stack: list[list[Form]] = []
    start = 0
    for index, line in enumerate(lines):
        for token in re.findall(r"[()]|[^\s()]+", line.split(";", 1)[0]):
            if token == "(":
                if not stack:
                    start = index
                stack.append([])
            elif token == ")":
                if not stack:
                    raise ValueError(f"{REGISTRY}:{index + 1}: unbalanced parenthesis")
                done = stack.pop()
                if stack:
                    stack[-1].append(done)
                else:
                    found[start] = done
            elif stack:
                stack[-1].append(token)
            else:
                raise ValueError(f"{REGISTRY}:{index + 1}: an atom outside a form")
    if stack:
        raise ValueError(f"{REGISTRY}: unclosed form")
    return found


def read_registry(root: Path = ROOT) -> tuple[dict[str, str], list[Item]]:
    """The named contexts and the documented items of the registry, in file order."""
    lines = (root / REGISTRY).read_text().splitlines()
    parsed = forms(lines)
    contexts: dict[str, str] = {}
    items: list[Item] = []
    seen: set[str] = set()
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
        key = {"fact": "fact:", "type": "type:"}.get(kind, "lib:") + name
        if key in seen:
            raise ValueError(f"duplicate registry identity: {key}")
        seen.add(key)
        doc, rare = preceding(lines, i, kind in PROSE_OPTIONAL)
        if any(re.match(r"@doc\b", line) for line in doc.text.splitlines()):
            raise ValueError(f"{key}: a ;;; @doc link is not supported; write the prose")
        if doc.text.startswith("@"):
            raise ValueError(f"{key}: unknown documentation directive: {doc.text}")
        items.append(Item(kind, name, key, doc, parsed[i], rare))
    if set(contexts) != set(CONTEXTS):
        raise ValueError(f"missing contexts: {set(CONTEXTS) - contexts.keys()}")
    if not items:
        raise ValueError("registry has no documented items")
    return contexts, items


def catalogue(root: Path = ROOT) -> dict[str, object]:
    contexts, items = read_registry(root)
    entries: dict[str, object] = {}
    for item in items:
        source: dict[str, object] = {"document": item.doc.path.as_posix()}
        if item.doc.text:
            source |= {"start_line": item.doc.start, "end_line": item.doc.end}
        entries[item.key] = {
            "status": "authored_contract",
            "summary": summary(item.doc.text),
            "contract_markdown": item.doc.text,
            "source": source,
            "section": SECTIONS[item.kind],
        }
    return {
        "schema": "arclog-study-meanings-v1",
        "source": "generated by scripts/generate_study_meanings.py from engine/lib/registry.sexpr",
        **contexts,
        "entries": entries,
    }


def heads(form: list[Form], head: str) -> list[Form] | None:
    """The items after `head` of the first sub-form headed by it."""
    for sub in form:
        if isinstance(sub, list) and sub and sub[0] == head:
            return sub[1:]
    return None


def type_text(ty: Form) -> str:
    if isinstance(ty, list):
        return " ".join(type_text(part) for part in ty[1:])
    return "Pose" if ty == "shared-pose" else ty


def column_text(column: Form) -> str:
    """A column `(Name type)` or a macro's `(Name Label type)` as `Name: type`,
    and a bare label as itself."""
    if isinstance(column, str):
        return column
    return f"{column[0]}: {type_text(column[-1])}"


def signature(name: str, columns: list[Form]) -> str:
    return f"`{name}({', '.join(column_text(column) for column in columns)})`"


def needs_text(form: list[Form]) -> str:
    modes = heads(form, "modes")
    if not modes:
        return ""
    return "needs " + ", or ".join(" ".join(str(c) for c in mode) for mode in modes
                                   if isinstance(mode, list))


def port_columns(port: list[Form]) -> list[Form]:
    return [c for c in port[1:] if isinstance(c, list) and c and c[0] not in PORT_FORMS]


def port_line(direction: str, port: list[Form]) -> str:
    columns = port_columns(port)
    marks = []
    if direction == "in" and not any(c[-1] == "Key" for c in columns):
        marks.append("shared")
    if "from-key" in port:
        marks.append("from the key")
    if "reads-outputs" in port:
        marks.append("may read the outputs")
    default = heads(port, "default")
    if default is not None:
        rows = [row[0] for row in default if isinstance(row, list) and len(row) == 1
                and isinstance(row[0], str)]
        marks.append("default " + ", ".join(rows) if len(rows) == len(default) else "default rows")
    return f"{direction} {signature(str(port[0]), columns)}" + "".join(f", {m}" for m in marks)


def parameter_text(parameter: Form) -> str:
    if isinstance(parameter, list):
        return f"{parameter[0]} under {type_text(parameter[1])}"
    return parameter


def prose_lines(text: str) -> tuple[str, list[tuple[int, str]]]:
    """The opening paragraph of `text`, then each later paragraph and bullet as
    (nesting level, text), where a bullet's text has its marker removed."""
    blocks: list[tuple[int, str, bool]] = []
    previous_blank = True
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            previous_blank = True
            continue
        if line.startswith("- "):
            blocks.append(((len(raw) - len(raw.lstrip())) // 2, line[2:], True))
        elif blocks and not previous_blank:
            level, last, bullet = blocks[-1]
            blocks[-1] = (level, f"{last} {line}", bullet)
        else:
            blocks.append((0, line, False))
        previous_blank = False
    opening = ""
    if blocks and not blocks[0][2]:
        opening = blocks[0][1]
        blocks = blocks[1:]
    return opening, [(level, body) for level, body, _ in blocks]


def bullets(head: str, prose: str, ports: list[tuple[str, str]], depth: int = 0) -> list[str]:
    """An entry: its head line with the opening paragraph of its prose, a line
    for each of the `ports` (name, line) the registry declares, then the rest
    of the prose. A top-level prose bullet "`<port>`: <text>" that names one of
    the ports goes on that port's line, with the bullets nested under it. Any
    other bullet stays after the port lines."""
    opening, rest = prose_lines(prose)
    names = [name for name, _ in ports]
    glosses: dict[str, tuple[str, list[tuple[int, str]]]] = {}
    others: list[tuple[int, str]] = []
    current: list[tuple[int, str]] = others
    for level, body in rest:
        match = PORT_BULLET.fullmatch(body) if level == 0 else None
        if match and names.count(match[1]) == 1 and match[1] not in glosses:
            current = glosses.setdefault(match[1], (match[2], []))[1]
        else:
            if level == 0:
                current = others
            current.append((level, body))
    indent = "    " * depth
    lines = [f"{indent}- {head}: {opening}" if head and opening else f"{indent}- {head or opening}"]
    for name, line in ports:
        text, nested = glosses.get(name, ("", []))
        lines.append(f"{indent}    - {line}: {text}" if text else f"{indent}    - {line}")
        lines += [f"{indent}    {'    ' * level}- {body}" for level, body in nested]
    lines += [f"{indent}    {'    ' * level}- {body}" for level, body in others]
    return lines


def paragraphs(text: str) -> list[str]:
    return [" ".join(p.split()) for p in text.split("\n\n") if p.strip()]


def entry(item: Item) -> list[str]:
    form = item.form
    prose = item.doc.text
    if item.kind == "type":
        return bullets(f"`{item.name}`", prose, [])
    if item.kind == "fact":
        columns = heads(form, "columns") or []
        return bullets(signature(item.name, columns), prose, [])
    if item.kind in ("relation", "macro"):
        columns = heads(form, "columns") or []
        head = signature(item.name, columns)
        needs = needs_text(form)
        return bullets(f"{head}, {needs}" if needs else head, prose, [])
    if item.kind == "component":
        ports = []
        parameters = heads(form, "type-parameters")
        head = f"**{item.name}**"
        if parameters:
            head += "<" + ", ".join(parameter_text(p) for p in parameters) + ">"
        if form[2] == "construction":
            head += " (construction)"
        for direction, group in (("in", "inputs"), ("out", "outputs")):
            ports += [(str(port[0]), port_line(direction, port)) for port in heads(form, group) or []
                      if isinstance(port, list)]
        return bullets(head, prose, ports)
    columns = heads(form, "columns") or []
    names = [column if isinstance(column, str) else column[0] for column in columns]
    return bullets(signature(item.name, names), prose, [])


def library(root: Path = ROOT) -> str:
    """The text of docs/arclog/lib.md: the items that are not rare."""
    contexts, items = read_registry(root)
    out = [*generated_comment(), "", "# The arclog lib"]
    out += [f"- {p}" for p in paragraphs(contexts["general_contract"])]
    for section in dict.fromkeys(SECTIONS.values()):
        out += ["", f"## {section}"]
        if section == "Proposers":
            out += [f"- {p}" for p in paragraphs(contexts["proposer_context"])]
        for item in items:
            if SECTIONS[item.kind] == section and not item.rare:
                out += entry(item)
    return "\n".join(out) + "\n"


def rare_library(root: Path = ROOT) -> str:
    """The text of docs/arclog/lib-rare.md: the rare items, in the sections that have one."""
    _, items = read_registry(root)
    out = [*generated_comment(), "", "# The arclog lib: rare items"]
    for section in dict.fromkeys(SECTIONS.values()):
        rare = [item for item in items if SECTIONS[item.kind] == section and item.rare]
        if rare:
            out += ["", f"## {section}"]
            for item in rare:
                out += entry(item)
    return "\n".join(out) + "\n"


def generated_comment() -> list[str]:
    return [
        "* comment: when editing this doc",
        "    - Generated by `scripts/generate_study_meanings.py` from `engine/lib/registry.sexpr`. "
        "Edit the registry's `;;;` prose, then run that script.",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        outputs = {
            OUTPUT: json.dumps(catalogue(), ensure_ascii=False, indent=2) + "\n",
            LIBRARY: library(),
            RARE_LIBRARY: rare_library(),
        }
        for name, rendered in outputs.items():
            path = ROOT / name
            if args.check:
                if not path.exists() or path.read_text() != rendered:
                    parser.exit(1, f"{name} is stale; run uv run python scripts/generate_study_meanings.py\n")
            else:
                path.write_text(rendered)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

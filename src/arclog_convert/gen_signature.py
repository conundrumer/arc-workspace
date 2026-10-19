"""Write `arclog_convert.signature` from the present lib: its constants,
types, public components and public relations, with no clause, each `// @input`
read as `// @extensional`.

    uv run python -m arclog_convert.gen_signature
"""
import re
from pathlib import Path

from arclog_convert import signature

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "programs" / "lib.dl"
OUT = signature()

HEADER = """\
// The interface of the lib the converter emits: each constant, type,
// public component and public relation, with no clause. A relation marked
// `// @extensional` is one the caller supplies, and a component's
// extensional relations stand in the order the converter emits its inputs.
"""


def lines(path: Path):
    for line in path.read_text().splitlines():
        m = re.match(r'#include "(.+)"', line)
        if m:
            yield from lines(path.parent / m[1])
        else:
            yield line


def main() -> None:
    out: list[str] = [HEADER]
    it = iter(lines(LIB))
    for line in it:
        s = line.strip()
        if s.startswith("#define") or (s.startswith(".type") and not s.startswith(".type _")):
            out.append(line)
        elif s.startswith(".comp _"):
            indent = line[:len(line) - len(line.lstrip())]
            while next(it) != indent + "}":
                pass
        elif s.startswith(".comp"):
            out += ["", line]
        elif line == "}":
            out.append(line)
        elif s.startswith(".decl") and not s.startswith(".decl _"):
            decl = [line]
            while decl[-1].count("(") - decl[-1].count(")") + sum(d.count("(") - d.count(")") for d in decl[:-1]) > 0:
                decl.append(next(it))
            out += [d.replace("@input", "@extensional") for d in decl]
    OUT.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()

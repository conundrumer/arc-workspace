"""The reader of arclog, arcdata and arcscene text into S-expressions (`Sym`,
`Str`, `L`, `read`), and the walks over them: `walk`, `leaves` and `flat`."""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class Sym:
    text: str
    line: int
    pos: int = -1
    bare: bool = False   # a site or a record's field elided to its label


@dataclass
class Str:
    text: str
    line: int


@dataclass
class L:
    items: list
    line: int
    start: int = -1
    end: int = -1

    @property
    def head(self):
        return self.items[0].text if self.items and isinstance(self.items[0], Sym) else None


def read(text: str) -> list:
    toks = re.finditer(r'"(?:[^"\\]|\\.)*"|;;[^\n]*|[()]|[^\s()";]+|\n', text)
    stack: list[L] = [L([], 0)]
    line = 1
    for m in toks:
        t = m.group()
        if t == "\n":
            line += 1
        elif t.startswith(";;"):
            continue
        elif t == "(":
            stack.append(L([], line, m.start()))
        elif t == ")":
            done = stack.pop()
            done.end = m.end()
            stack[-1].items.append(done)
        elif t.startswith('"'):
            stack[-1].items.append(Str(t, line))
            line += t.count("\n")
        else:
            stack[-1].items.append(Sym(t, line, m.start()))
    if len(stack) != 1:
        raise SyntaxError("unbalanced parens")
    return stack[0].items


def walk(t) -> Iterator:
    """`t` and each node under it, each before the nodes under it, in order of the text."""
    pending = [t]
    while pending:
        node = pending.pop()
        yield node
        if isinstance(node, L):
            pending.extend(reversed(node.items))


def leaves(t):
    if isinstance(t, Sym):
        return [t]
    if isinstance(t, L):
        return [x for i in t.items[1:] for x in leaves(i)]
    return []


def flat(x) -> str:
    if isinstance(x, L):
        return "(" + " ".join(flat(i) for i in x.items) + ")"
    return x.text

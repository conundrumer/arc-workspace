"""The gold union graph of one task as forms that can be written: each graph function (a line of graph-prods-SET.jsonl, named by its `ident`) with the tree of its text in a case program, the graph table each reference uses, and the Name of each head.

A graph function is one identity of the union. Its text is a line of a case program in union-keys-SET.jsonl, with that program's labels. The first case line whose reads, resolved to graph tables, equal the function's `reads` is the one taken.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
import collections, hashlib, json, re
from dataclasses import dataclass, field
from pathlib import Path

from canon_text import Tree, given_tables, parse, with_fields

HEAD = re.compile(r'\((\w+) &([A-Za-z_][\w]*)')
NAME = re.compile(r'&([A-Za-z_]\w*)((?:\.\w+)*)')
TASK = re.compile(rb'^\{"task": "([^"]*)"')


class LineIndex:
    """The lines of a jsonl file by task, as byte ranges: one pass over the file, so a task's lines are read without loading the file. The file stays open, so
    the ranges stay valid when a writer replaces the file by a rename while it is read."""

    def __init__(self, path: Path):
        self.path = path
        self.at: dict[str, list[tuple[int, int, int]]] = collections.defaultdict(list)
        pos = 0
        self.f = open(path, 'rb')
        for n, line in enumerate(self.f):
            m = TASK.match(line)
            if m:
                self.at[m[1].decode()].append((pos, len(line), n))
            pos += len(line)

    def tasks(self) -> list[str]:
        return sorted(self.at)

    def lines(self, task: str) -> list[bytes]:
        out = []
        for pos, size, _ in self.at.get(task, []):
            self.f.seek(pos)
            out.append(self.f.read(size))
        return out


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def idents(lines: list[str]) -> list[tuple[str, str, str, str]]:
    """(label, kind, identity, line) of each form: the identity is the text with each read replaced by the identity of the form it reads, labels dropped (gold_union.forms_of)."""
    known: dict[str, str] = {}
    out = []
    for x in lines:
        m = HEAD.match(x)
        if not m:
            continue
        body = x[m.end():]
        text = m[1] + NAME.sub(lambda n: '{%s}%s' % (known[n[1]], n[2]) if n[1] in known else '&_' + n[2], body)
        known[m[2]] = sha(' '.join(text.split()))
        out.append((m[2], m[1], known[m[2]], x))
    return out


def name(key: int, out: str) -> str:
    return '%d.%s' % (key, out) if out else str(key)


@dataclass
class Form:
    ident: str
    kind: str
    depth: int | None
    reads: tuple[str, ...]
    heads: tuple[tuple[str, str], ...]  # (graph table, Name)
    line: str  # the form's line in its case program, as written
    tree: list[Tree]
    refs: dict[str, str]  # a reference of the tree, such as `&r2.tile`, to the graph table it uses
    givens: tuple[str, ...]
    consistent: bool
    read_idents: dict[str, str]  # a reference of the tree to the identity of the form it names in its case program
    cols: dict[str, str]  # a RULE's or DET's column field `:V` to the field it came from; an INIT's key field to `key#i`


@dataclass
class TaskGraph:
    task: str
    forms: dict[str, Form] = field(default_factory=dict)
    shadows: dict[str, Form] = field(default_factory=dict)  # a case line whose identity is no production of the graph: the same union key as a production, written with other names; it is read by other forms, never written as a member
    entries: dict[str, list[tuple[str, str]]] = field(default_factory=dict)  # graph table -> the (QueryHash, Name) of the tables that it holds
    unresolved: int = 0

    def form(self, ident: str) -> Form | None:
        return self.forms.get(ident) or self.shadows.get(ident)


def load(task: str, prods: list[bytes], tables: list[bytes], keys: list[bytes]) -> TaskGraph:
    p = {r['ident']: r for r in map(json.loads, prods)}
    members: dict[str, str] = {}
    of_table: dict[str, list[str]] = {}
    entries: dict[str, list[tuple[str, str]]] = {}
    for r in map(json.loads, tables):
        of_table[r['table']] = r['members']
        entries[r['table']] = [(h, n) for h, n in r.get('tables', [])]
        for m in r['members']:
            members[m] = r['table']
    graph = TaskGraph(task, entries=entries)
    for line in map(json.loads, keys):
        ls = [x for x in line['text'].splitlines() if x.strip() and not x.startswith('(OUT')]
        if len(ls) != len(line['keys']):
            continue
        forms = idents(ls)
        trees, origin = None, {}
        label = {f[0]: (k, f[1]) for f, k in zip(forms, line['keys'])}
        ident_of = {f[0]: f[2] for f in forms}
        for (lab, kind, ident, text), key in zip(forms, line['keys']):
            have = graph.forms.get(ident) or graph.shadows.get(ident)
            if key is None or (have is not None and have.consistent):
                continue
            if trees is None:
                trees, origin = with_fields(ls)
            tree = trees[ls.index(text)]
            refs: dict[str, str] = {}
            miss = 0
            for tok in _tokens(tree):
                if tok.startswith('&') and tok[1:].split('.')[0] in label and tok[1:].split('.')[0] != lab:
                    rk, rkind = label[tok[1:].split('.')[0]]
                    rest = tok.partition('.')[2]
                    nm = name(rk, rest.split('.')[0] if rkind == 'INIT' else '')
                    if nm in members:
                        refs[tok] = members[nm]
                    else:
                        # an input port of an INIT (such as `&r7.member`) is no member of any table; the form reads it through a table of the INIT's outputs, one of the form's `reads`
                        near = sorted({members[m] for m in members if m.partition('.')[0] == str(rk)} & (set(p[ident]['reads']) if ident in p else set(members.values()))) if rkind == 'INIT' else []
                        if near:
                            refs[tok] = near[0]
                        else:
                            miss += 1
            read_idents = {t: ident_of[t[1:].split('.')[0]] for t in refs}
            cols = dict(origin.get(lab, {})) if kind != 'INIT' else key_columns(text)
            if ident in p:
                graph.unresolved += miss
                r = p[ident]
                heads = tuple((h, _head_name(of_table.get(h, []), key)) for h in r['heads'])
                graph.forms[ident] = Form(ident, r['kind'], r['depth'], tuple(r['reads']), heads, text, tree, refs, tuple(given_tables(tree)), set(refs.values()) == set(r['reads']), read_idents, cols)
            else:
                heads = tuple(sorted((members[m], m.partition('.')[2]) for m in members if m.partition('.')[0] == str(key)))
                graph.shadows[ident] = Form(ident, kind, None, tuple(sorted(set(refs.values()))), heads, text, tree, refs, tuple(given_tables(tree)), miss == 0, read_idents, cols)
    for ident, r in p.items():
        if ident not in graph.forms:
            graph.unresolved += 1
    return graph


def key_columns(line: str) -> dict[str, str]:
    """An INIT's output columns that its key group names: {field `:V`: `key#i`}, i the place of the field's `^` mark in the key group."""
    tree = parse(line)[0]
    got: dict[str, str] = {}
    assert isinstance(tree, list)
    for c in tree[3:]:
        if isinstance(c, list) and c and c[0] == 'key' and len(c) > 1 and isinstance(c[1], list):
            for a in c[1]:
                for x in a[1:] if isinstance(a, list) else []:
                    if isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and isinstance(x[1], str) and x[1].startswith('^'):
                        got.setdefault(x[0], 'key#%d' % len(got))
    return got


def _head_name(ms: list[str], key: int) -> str:
    for m in ms:
        if m == str(key):
            return ''
        if m.startswith('%d.' % key):
            return m[len(str(key)) + 1:]
    return ''


def _tokens(t: Tree):
    if isinstance(t, str):
        yield t
    else:
        for x in t:
            yield from _tokens(x)

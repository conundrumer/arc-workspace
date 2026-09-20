"""Circular determinations: determined parameters that derive from each
other's stored values.

A determination relation derives a Params parameter from the examples, and the
determination check compares the result against the stored value. The
comparison is worth something only when the derivation does not consume what it
is being compared to.

Reading another determined parameter's stored value is allowed. That parameter
carries its own determination relation, which the same check verifies, so the
value read is one the check has confirmed — provided the chain of such reads
bottoms out. It bottoms out exactly when the reads form no cycle.

So the property is acyclicity, over a graph whose nodes are the determined
parameters and whose edges run from a parameter to each determined parameter
whose stored value its derivation reaches. A parameter reading its own value is
the one-node case: the check compares the value against itself. A two-node cycle
passes both checks together for any jointly consistent pair of values, and
longer cycles the same way.
"""

import re

from dl.dlparse import Index, parse
from dl.source import determined_params

PARAMS_INIT_RE = re.compile(r"\.init\s+(\w+)\s*=\s*Params\b")

# Pseudo-comps: the Params instance's values, and names from lib or outside
# every comp. Both sort outside the file's comp names, which are identifiers.
# Every sentence this module prints, keyed by the part it heads. A slot,
# `{name}`, is filled by the render.
MESSAGES = {
    "cycle": "circular determination: ",
    "step": "{param} reads params.{reads} ({comp} line {lineno})",
}

PARAMS = "\0params"
OUTER = "\0outer"

type Node = tuple[str, str]
type Graph = dict[Node, set[tuple[Node, int]]]

# One step of a cycle: the parameter, and where its derivation reads the next
# parameter's stored value.
type Step = tuple[str, str, int]


def param_reads(source: str) -> dict[str, dict[str, tuple[str, int]]]:
    """Parameter -> determined parameter whose stored value it reads ->
    (comp, line of the read)."""
    determined = determined_params(source)
    m = PARAMS_INIT_RE.search(source)
    if not determined or not m:
        return {}
    graph = _graph(source, m.group(1))
    reads = {}
    for param in sorted(determined):
        hits = {
            other: hit
            for other in sorted(determined)
            if (hit := _first_reach(graph, ("Determine", param), (PARAMS, other)))
        }
        if hits:
            reads[param] = hits
    return reads


def determine_cycles(source: str) -> list[list[Step]]:
    """Cycles in the determined parameters' reads of each other's stored values.

    Each cycle is a list of steps, the last reading the first step's parameter.
    Cycles that share a parameter report once: one is enough to act on, and the
    rest of the group follows from the same edges.
    """
    reads = param_reads(source)
    cycles, covered = [], set()
    for start in sorted(reads):
        if start in covered:
            continue
        path = _find_cycle(reads, start)
        if path is None:
            continue
        covered.update(path)
        cycles.append([
            (param, *reads[param][path[(i + 1) % len(path)]])
            for i, param in enumerate(path)
        ])
    return cycles


def _find_cycle(
    reads: dict[str, dict[str, tuple[str, int]]], start: str
) -> list[str] | None:
    """A path of parameters leading from `start` back to `start`; None if none does."""
    def walk(path: list[str]) -> list[str] | None:
        for nxt in sorted(reads.get(path[-1], ())):
            if nxt == start:
                return path
            if nxt not in path and (found := walk(path + [nxt])):
                return found
        return None

    return walk([start])


def _graph(source: str, cname: str) -> Graph:
    """Rule dependencies over the comps Determine reaches, head -> {(body, line)}.

    A local comp resolves precisely: its instance's atoms become nodes of the
    comp itself, so the instantiator's rules and the comp's own rules join up.
    A lib comp is opaque, so all of one instance's atoms collapse to a single
    node — every output of the instance then depends on every input to it.

    Rules outside a comp stay out: a determination relation derives from `ex_in`
    / `ex_out` and the comps Determine instantiates, not from the program.
    """
    ix = Index(parse(source))
    local = set(ix.program.comps())
    decls = {c: set(ix.decls.get(c, {})) for c in local}
    insts = {
        c: {i.inst: i.comp for i in ix.inits.get(c, {}).values()} for c in local
    }
    by_rule: dict[int, list] = {}
    for r in ix.refs:
        by_rule.setdefault(r.rule, []).append(r)

    graph: Graph = {}
    seen: set[str] = set()
    work = ["Determine"] if "Determine" in local else []
    while work:
        comp = work.pop()
        if comp in seen:
            continue
        seen.add(comp)
        work += [t for t in insts[comp].values() if t in local]
        for idx, info in enumerate(ix.rules):
            if info.scope != comp:
                continue
            head = info.rule.head
            src = _node(comp, _last_qual(head.qual), head.name,
                        cname, local, decls, insts)
            for r in by_rule.get(idx, ()):
                if r.role == "head":
                    continue
                a = r.atom
                dst = _node(comp, _last_qual(a.qual), a.name,
                            cname, local, decls, insts)
                graph.setdefault(src, set()).add((dst, a.line))
    return graph


def _last_qual(qual: str | None) -> str | None:
    """The instance an atom reads directly: the last hop of a dotted path."""
    return qual.split(".")[-1] if qual else None


def _node(
    comp: str,
    qual: str | None,
    name: str,
    cname: str,
    local: set[str],
    decls: dict[str, set[str]],
    insts: dict[str, dict[str, str]],
) -> Node:
    """The graph node an atom denotes, read inside comp `comp`."""
    if qual is None:
        return (comp, name) if name in decls[comp] else (OUTER, name)
    if qual == cname:
        return (PARAMS, name)
    target = insts[comp].get(qual)
    if target in local:
        return (target, name)
    return (comp, qual)


def _first_reach(graph: Graph, start: Node, target: Node) -> tuple[str, int] | None:
    """(comp, line) of the first edge into `target` from `start`; None if unreached."""
    seen = {start}
    work = [start]
    while work:
        node = work.pop()
        for dst, lineno in graph.get(node, ()):
            if dst == target:
                return (node[0], lineno)
            if dst not in seen:
                seen.add(dst)
                work.append(dst)
    return None


def render_cycles(cycles: list[list[Step]]) -> list[str]:
    return [
        MESSAGES["cycle"] + ", ".join(
            MESSAGES["step"].format(
                param=param, reads=cycle[(i + 1) % len(cycle)][0],
                comp=comp, lineno=lineno)
            for i, (param, comp, lineno) in enumerate(cycle)
        )
        for cycle in cycles
    ]

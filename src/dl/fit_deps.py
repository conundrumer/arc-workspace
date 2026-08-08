"""Circular fits: fitted slots that derive from each other's stored fills.

A Fit relation derives a Consts slot from the examples, and the fit check
compares the result against the stored fill. The comparison is worth something
only when the derivation does not consume what it is being compared to.

Reading another fitted slot's stored fill is allowed. That slot carries its own
Fit relation, which the same check verifies, so the value read is one the check
has confirmed — provided the chain of such reads bottoms out. It bottoms out
exactly when the reads form no cycle.

So the property is acyclicity, over a graph whose nodes are the fitted slots
and whose edges run from a slot to each fitted slot whose stored fill its
derivation reaches. A slot reading its own fill is the one-node case: the check
compares the fill against itself. A two-node cycle passes both checks together
for any jointly consistent pair of fills, and longer cycles the same way.
"""

import re

from dl.dlparse import Index, parse
from dl.source import fit_slots

CONSTS_INIT_RE = re.compile(r"\.init\s+(\w+)\s*=\s*Consts\b")

# Pseudo-comps: the Consts instance's fills, and names from lib or outside
# every comp. Both sort outside the file's comp names, which are identifiers.
CONSTS = "\0consts"
OUTER = "\0outer"

type Node = tuple[str, str]
type Graph = dict[Node, set[tuple[Node, int]]]

# One step of a cycle: the slot, and where its derivation reads the next
# slot's stored fill.
type Step = tuple[str, str, int]


def slot_reads(source: str) -> dict[str, dict[str, tuple[str, int]]]:
    """Slot -> fitted slot whose stored fill it reads -> (comp, line of the read)."""
    fitted = fit_slots(source)
    m = CONSTS_INIT_RE.search(source)
    if not fitted or not m:
        return {}
    graph = _graph(source, m.group(1))
    reads = {}
    for slot in sorted(fitted):
        hits = {
            other: hit
            for other in sorted(fitted)
            if (hit := _first_reach(graph, ("Fit", slot), (CONSTS, other)))
        }
        if hits:
            reads[slot] = hits
    return reads


def fit_cycles(source: str) -> list[list[Step]]:
    """Cycles in the fitted slots' reads of each other's stored fills.

    Each cycle is a list of steps, the last reading the first step's slot.
    Cycles that share a slot report once: one is enough to act on, and the
    rest of the group follows from the same edges.
    """
    reads = slot_reads(source)
    cycles, covered = [], set()
    for start in sorted(reads):
        if start in covered:
            continue
        path = _find_cycle(reads, start)
        if path is None:
            continue
        covered.update(path)
        cycles.append([
            (slot, *reads[slot][path[(i + 1) % len(path)]])
            for i, slot in enumerate(path)
        ])
    return cycles


def _find_cycle(
    reads: dict[str, dict[str, tuple[str, int]]], start: str
) -> list[str] | None:
    """A path of slots leading from `start` back to `start`; None if none does."""
    def walk(path: list[str]) -> list[str] | None:
        for nxt in sorted(reads.get(path[-1], ())):
            if nxt == start:
                return path
            if nxt not in path and (found := walk(path + [nxt])):
                return found
        return None

    return walk([start])


def _graph(source: str, cname: str) -> Graph:
    """Rule dependencies over the comps Fit reaches, head -> {(body, line)}.

    A local comp resolves precisely: its instance's atoms become nodes of the
    comp itself, so the instantiator's rules and the comp's own rules join up.
    A lib comp is opaque, so all of one instance's atoms collapse to a single
    node — every output of the instance then depends on every input to it.

    Rules outside a comp stay out: a Fit relation derives from `ex_in` / `ex_out`
    and the comps Fit instantiates, not from the body.
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
    work = ["Fit"] if "Fit" in local else []
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
        return (CONSTS, name)
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
        "circular fit: " + ", ".join(
            f"{slot} reads c.{cycle[(i + 1) % len(cycle)][0]} ({comp} line {lineno})"
            for i, (slot, comp, lineno) in enumerate(cycle)
        )
        for cycle in cycles
    ]

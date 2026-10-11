"""The cycles of a directed graph: its strongly connected components that
hold an edge."""

from collections.abc import Callable, Hashable, Iterable, Iterator


def cyclic_components[N: Hashable](
        nodes: Iterable[N], successors: Callable[[N], Iterable[N]]
) -> list[list[N]]:
    """The strongly connected components (Tarjan) of the graph that
    `successors` gives over `nodes` and the nodes they reach, each one
    that holds an edge: of more than one node, or of one node with an
    edge to itself. The walk starts at each of `nodes` in turn and follows
    successors in the order `successors` gives them; the components stand
    in the order it closes them, each in the order it leaves the path."""
    index: dict[N, int] = {}
    low: dict[N, int] = {}
    on: set[N] = set()
    path: list[N] = []
    out: list[list[N]] = []
    for root in nodes:
        if root in index:
            continue
        # The walk is a stack of nodes, each with its successors left to
        # follow, since a graph deeper than Python's recursion limit
        # stands in a large program.
        index[root] = low[root] = len(index)
        path.append(root)
        on.add(root)
        stack: list[tuple[N, Iterator[N]]] = [(root, iter(successors(root)))]
        while stack:
            v, rest = stack[-1]
            entered = False
            for w in rest:
                if w not in index:
                    index[w] = low[w] = len(index)
                    path.append(w)
                    on.add(w)
                    stack.append((w, iter(successors(w))))
                    entered = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if entered:
                continue
            stack.pop()
            if stack:
                u = stack[-1][0]
                low[u] = min(low[u], low[v])
            if low[v] != index[v]:
                continue
            comp: list[N] = []
            while True:
                w = path.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in successors(v):
                out.append(comp)
    return out

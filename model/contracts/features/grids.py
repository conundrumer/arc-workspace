"""Model input layer: what the features read of the grids of an example.

A grid is a labeling of the cells of a frame. The features read a label only through equality, so a labeling of any equality type can stand where the colors of a grid stand. Labeling holds what
they read of one labeling; Example holds what they read of the input and the train output together.
"""
from collections import Counter
from functools import cached_property

MOSTLY = 0.9  # the proportion of the cells it compares that a translation must keep for it to be a period of a grid with noise
CELL_ROLES = ('on the boundary of their component', 'at a corner of the box of their component', 'at the center of the box of their component',
              'at a tip of their component', 'in a component of one cell', 'on a full line of one color', 'on the grid edge', 'at a grid corner',
              'of the background next to the foreground', 'of the background enclosed by the foreground', 'at a crossing of two lines',
              "that break the grid's periods", 'of the background between the foreground on a line')

def F():
    import features
    return features


def bounding_interval(S):
    """(first row, last row, first column, last column) of a nonempty set of cells."""
    return min(u[0] for u in S), max(u[0] for u in S), min(u[1] for u in S), max(u[1] for u in S)


class Labeling:
    """A grid. A component is an 8-connected set of cells of one label; the background is the one most frequent label, where one label is; the foreground is the other cells."""

    def __init__(self, array):
        self.array = array
        self.H, self.W = len(array), len(array[0])
        self._inside, self._label_roles = {}, {}

    @cached_property
    def cells(self):
        return {(r, k) for r in range(self.H) for k in range(self.W)}

    @cached_property
    def counts(self):
        return Counter(u for row in self.array for u in row)

    @cached_property
    def labels(self):
        return set(self.counts)

    @cached_property
    def by_label(self):
        """{label: its cells}."""
        out = {}
        for u in self.cells:
            out.setdefault(self.array[u[0]][u[1]], set()).add(u)
        return out

    @cached_property
    def background(self):
        tops = [k for k, q in self.counts.items() if q == max(self.counts.values())]
        return tops[0] if len(tops) == 1 else None

    @cached_property
    def foreground(self):
        return None if self.background is None else {(r, k) for r, row in enumerate(self.array) for k, u in enumerate(row) if u != self.background}

    @cached_property
    def foreground_components(self):
        return F().components(self.foreground) if self.foreground else []

    @cached_property
    def foreground_box(self):
        return bounding_interval(self.foreground) if self.foreground else None

    @cached_property
    def as_tuple(self):
        return tuple(tuple(u) for u in self.array)

    @cached_property
    def positions(self):
        """{label: its cells, as a list in row order}."""
        out = {}
        for r, row in enumerate(self.array):
            for k, u in enumerate(row):
                out.setdefault(u, []).append((r, k))
        return out

    @cached_property
    def components_by_label(self):
        return {x: [frozenset(p) for p in F().components(q)] for x, q in self.by_label.items()}

    @cached_property
    def component_of(self):
        return {u: p for ps in self.components_by_label.values() for p in ps for u in p}

    @cached_property
    def full_rows(self):
        return {r for r in range(self.H) if len(set(self.array[r])) == 1}

    @cached_property
    def full_cols(self):
        return {k for k in range(self.W) if len({row[k] for row in self.array}) == 1}

    def walk_in(self, free):
        """The cells of free that no walk of four steps through free reaches from the grid's edge."""
        seen = {c for c in free if c[0] in (0, self.H - 1) or c[1] in (0, self.W - 1)}
        todo = list(seen)
        while todo:
            r, k = todo.pop()
            for y in ((r + 1, k), (r - 1, k), (r, k + 1), (r, k - 1)):
                if y in free and y not in seen:
                    seen.add(y)
                    todo.append(y)
        return free - seen

    def inside(self, x):
        if x not in self._inside:
            self._inside[x] = self.walk_in(self.cells - self.by_label[x])
        return self._inside[x]

    def label_roles(self, x):
        held = self._label_roles.get(x)
        if held is None:
            S, ps = self.by_label[x], self.components_by_label[x]
            rs, ks = [c[0] for c in S], [c[1] for c in S]
            fg_sizes = [len(p) for y, qs in self.components_by_label.items() if y != self.background for p in qs]
            held = {'that fill whole lines': all(r in self.full_rows or k in self.full_cols for r, k in S), 'that are single cells': all(len(p) == 1 for p in ps),
                    'of one component': len(ps) == 1, 'that touch every edge': min(rs) == 0 and max(rs) == self.H - 1 and min(ks) == 0 and max(ks) == self.W - 1,
                    'that touch no edge': min(rs) > 0 and max(rs) < self.H - 1 and min(ks) > 0 and max(ks) < self.W - 1, 'that enclose another color': bool(self.inside(x)),
                    'enclosed by another color': any(S <= self.inside(y) for y in self.by_label if y != x), 'that fill their boxes': all(F().fills_box(p) for p in ps),
                    'of the largest foreground component': x != self.background and bool(fg_sizes) and any(len(p) == max(fg_sizes) for p in ps),
                    'with the most components': len(ps) == max(len(qs) for qs in self.components_by_label.values()), 'with a symmetric cell set': F().symmetry_count(S) > 1}
            self._label_roles[x] = held
        return held

    @cached_property
    def cell_roles(self):
        """{role: its cells}."""
        if True:
            out = {r: set() for r in CELL_ROLES}
            boxes = {}
            for c in self.cells:
                r, k = c
                p = self.component_of[c]
                box = boxes.get(p)
                if box is None:
                    box = boxes[p] = (min(x[0] for x in p), max(x[0] for x in p), min(x[1] for x in p), max(x[1] for x in p))
                if any(y not in p for y in ((r + 1, k), (r - 1, k), (r, k + 1), (r, k - 1))):
                    out['on the boundary of their component'].add(c)
                if r in box[:2] and k in box[2:]:
                    out['at a corner of the box of their component'].add(c)
                if 2 * r == box[0] + box[1] and 2 * k == box[2] + box[3]:
                    out['at the center of the box of their component'].add(c)
                near = sum((r + a, k + b) in p for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0))
                if near == 1 and len(p) > 1:
                    out['at a tip of their component'].add(c)
                if len(p) == 1:
                    out['in a component of one cell'].add(c)
                if r in self.full_rows or k in self.full_cols:
                    out['on a full line of one color'].add(c)
                if r in (0, self.H - 1) or k in (0, self.W - 1):
                    out['on the grid edge'].add(c)
                if r in (0, self.H - 1) and k in (0, self.W - 1):
                    out['at a grid corner'].add(c)
                if self.foreground is not None and c not in self.foreground and any((r + a, k + b) in self.foreground for a in (-1, 0, 1) for b in (-1, 0, 1)):
                    out['of the background next to the foreground'].add(c)
            if self.foreground is not None:
                out['of the background enclosed by the foreground'] = self.walk_in(self.cells - self.foreground)
                out['at a crossing of two lines'] = self.crossings()
                out['of the background between the foreground on a line'] = self.between()
            out["that break the grid's periods"] = self.breaks()
            return out

    def crossings(self):
        """The cells where a row and a column cross that the foreground holds three quarters of."""
        rows = [r for r in range(self.H) if 4 * sum((r, k) in self.foreground for k in range(self.W)) >= 3 * self.W]
        cols = [k for k in range(self.W) if 4 * sum((r, k) in self.foreground for r in range(self.H)) >= 3 * self.H]
        return {(r, k) for r in rows for k in cols}

    def between(self):
        """The cells of the background with a foreground cell on each side along their row or their column."""
        out = set()
        for line, at in ((range(self.H), lambda a, b: (a, b)), (range(self.W), lambda a, b: (b, a))):
            across = self.W if at(0, 1) == (0, 1) else self.H
            for a in line:
                held = [b for b in range(across) if at(a, b) in self.foreground]
                out |= {at(a, b) for b in range(held[0] + 1, held[-1]) if at(a, b) not in self.foreground} if held else set()
        return out

    def breaks(self):
        """The cells off the most frequent color of their class, where a class is the cells that the grid's least period along each axis takes onto one another.
        A grid whose classes share one most frequent color has no such cells, since the period then only says that the grid is mostly one color."""
        pr, pk = least_move(self.array), least_move(list(zip(*self.array)))
        classes = {}
        for r, k in self.cells:
            classes.setdefault((r % pr if pr else r, k % pk if pk else k), Counter())[self.array[r][k]] += 1
        tops = {x for cnt in classes.values() for x, q in cnt.items() if q == max(cnt.values())}
        if len(tops) < 2:
            return set()
        return {(r, k) for r, k in self.cells if (cnt := classes[(r % pr if pr else r, k % pk if pk else k)])[self.array[r][k]] < max(cnt.values())}

    @cached_property
    def foreground_component_sets(self):
        return [frozenset(p) for p in self.foreground_components]

    @cached_property
    def line_labels(self):
        """The labels on each row, column and diagonal."""
        rows, cols, down, up = {}, {}, {}, {}
        for r, k in self.cells:
            x = self.array[r][k]
            rows.setdefault(r, set()).add(x)
            cols.setdefault(k, set()).add(x)
            down.setdefault(r - k, set()).add(x)
            up.setdefault(r + k, set()).add(x)
        return rows, cols, down, up

    def nearest_colors(self, cells):
        """The colors of the foreground cells outside cells that the fewest steps along rows and columns reach from them."""
        seen, layer = set(cells), list(cells)
        while layer:
            ahead, hit = [], set()
            for r, k in layer:
                for y in ((r + 1, k), (r - 1, k), (r, k + 1), (r, k - 1)):
                    if y in self.cells and y not in seen:
                        seen.add(y)
                        ahead.append(y)
                        if y in self.foreground:
                            hit.add(self.array[y[0]][y[1]])
            if hit:
                return hit
            layer = ahead
        return set()

    @cached_property
    def component_set(self):
        return {p for ps in self.components_by_label.values() for p in ps}

    @cached_property
    def component_boxes(self):
        return {bounding_interval(p) for p in self.component_set}

    @cached_property
    def input_measures(self):
        if True:
            parts = self.foreground_components
            out = {'the longer side of the input': {max(self.H, self.W)}, 'the shorter side of the input': {min(self.H, self.W)},
                            'the input color count': {len(self.counts)}, 'the count of some input color': set(self.counts.values()),
                            'the input full line count': {len(self.full_rows) + len(self.full_cols)}, 'the input one-color component count': {sum(len(p) for p in self.components_by_label.values())}}
            if self.foreground is not None:
                out.update({'the input foreground count': {len(self.foreground)}, 'the input foreground component count': {len(parts)},
                                     'the largest input foreground component': {max((len(p) for p in parts), default=0)}})
            return out


def least_move(lines):
    """The least move along a list of equal lines, at most half their number, that keeps at least MOSTLY of the cells it compares; 0 where none does."""
    n = len(lines)
    for p in range(1, n // 2 + 1):
        if sum(x == y for a, b in zip(lines, lines[p:]) for x, y in zip(a, b)) >= MOSTLY * (n - p) * len(lines[0]):
            return p
    return 0


_relabeled = {}


def relabeled(array, label):
    """The grid with each cell's color replaced by a label of the given equivalence type of its component: its shape, up to translation or up to D4, the component itself, or its size."""
    key = (id(array), label)
    held = _relabeled.get(key)
    if held is None or held[0] is not array:
        if len(_relabeled) > 32:
            _relabeled.clear()
        G = labeling(array)
        forms = {}

        def form(p):
            if p not in forms:
                forms[p] = F().normalized(p) if label == 'shape' else F().canon(p) if label == 'shape up to D4' else p if label == 'component' else len(p)
            return forms[p]
        held = _relabeled[key] = (array, [[form(G.component_of[(r, k)]) for k in range(G.W)] for r in range(G.H)])
    return held[1]


_held = {}


def labeling(array):
    held = _held.get(id(array))
    if held is None or held.array is not array:
        if len(_held) > 16:
            _held.clear()
        held = _held[id(array)] = Labeling(array)
    return held


class Example:
    """The input and the train output of an example."""

    def __init__(self, gi, go):
        self.gi, self.go = gi, go
        self.input, self.output = labeling(gi), labeling(go)
        self.same = (self.input.H, self.input.W) == (self.output.H, self.output.W)

    @cached_property
    def changed(self):
        return {u for u in self.output.cells if self.gi[u[0]][u[1]] != self.go[u[0]][u[1]]} if self.same else set()

    @cached_property
    def changed_box(self):
        return bounding_interval(self.changed) if self.changed else None

    @cached_property
    def added_labels(self):
        return self.output.labels - self.input.labels

    @cached_property
    def dropped_labels(self):
        return self.input.labels - self.output.labels

    @cached_property
    def changed_from(self):
        return {self.gi[r][k] for r, k in self.changed}

    @cached_property
    def changed_to(self):
        return {self.go[r][k] for r, k in self.changed}

    @cached_property
    def measures(self):
        """The numbers of the output and of the changed cells that a feature compares a value with. A number that the example does not have is left out."""
        G = self.output
        out = {'the output area': G.H * G.W, 'the longer side of the output': max(G.H, G.W), 'the shorter side of the output': min(G.H, G.W), 'the output color count': len(G.counts)}
        if G.foreground is not None:
            out['the output foreground count'] = len(G.foreground)
            out['the output foreground component count'] = len(G.foreground_components)
        if self.changed:
            out['the changed cell count'] = len(self.changed)
            out['the changed component count'] = F().comps(self.changed)
        return out

    @cached_property
    def paths(self):
        return {}


_last = None


def example(gi, go):
    global _last
    if _last is None or _last.gi is not gi or _last.go is not go:
        _last = Example(gi, go)
    return _last

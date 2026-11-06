#!/usr/bin/env python
"""The written templates' sizes when each named part counts 1, what enumeration over the parts
reaches at each size, and how many shapes that enumeration has.

  python model/feature_eval/template_parts.py results/template-shapes.tsv.zst

A part is a pattern over a term. It counts 1, with the relations that fill its holes counted
as usual, and a subexpression that appears twice counts once. A root of `ratio` over two
relations counts neither aggregate. A comparison of two counts is read as their `ratio`, and a
relation of two sets as its claims, the largest of which sets the size.
"""
import collections
import csv
import sys
from itertools import combinations

from common import open_text
from template_shapes import (BACKGROUND, CHANGED, COMPONENTS, COMPONENT_BOX, FOREGROUND, FOREGROUND_PARTS, FULL_LINES, INPUT_BACKGROUND, INPUT_FOREGROUND, INPUT_BOX, CHANGED_BOX, FOREGROUND_BOX, LINES,
                             LEAST_COLOR, MEASURES, MOST_COLOR, ON_FULL_LINE, PER_COLOR, ROLE_TEXTS, SAME_COLOR_NEIGHBOR, DROPPED, ADDED, COLOR_BOX, OUTPUT_EXTENTS, CHANGED_COMPONENTS, FOREGROUND_COMPONENTS, node_text, operator_children, parse)

CONSTANTS = {
    'changed cells': [CHANGED],
    'background': [BACKGROUND, f'(component Singleton (member {BACKGROUND} () (Col)) value)', INPUT_BACKGROUND],
    'foreground': [FOREGROUND, INPUT_FOREGROUND],
    'background cells': [f'(join output {BACKGROUND} (Col Col))'],
    'components': [COMPONENTS],
    'foreground components': [FOREGROUND_PARTS],
    'part labels': [FOREGROUND_COMPONENTS, CHANGED_COMPONENTS],
    'component boxes': [COMPONENT_BOX],
    'color counts': [PER_COLOR, PER_COLOR.replace('output', 'input')],
    'extreme colors': [LEAST_COLOR, MOST_COLOR],
    'same-color neighbors': [SAME_COLOR_NEIGHBOR],
    'full lines': [FULL_LINES],
    'grid lines': [LINES],
    'color boxes': [COLOR_BOX],
    'whole-set boxes': [INPUT_BOX, CHANGED_BOX, FOREGROUND_BOX],
    'colors dropped or added': [DROPPED, ADDED],
    'output extents': [OUTPUT_EXTENTS],
    'a measure of the output': [text for text, _ in MEASURES.values()],
    'a cell or color role': ROLE_TEXTS + [ON_FULL_LINE],
}
CONSTANT_OF = {node_text(parse(text)): name for name, texts in CONSTANTS.items() for text in texts}
GRIDS = ('input', 'output')


def is_list(node, head=None):
    return isinstance(node, list) and (head is None or (node and node[0] == head))


def binding(node, name):
    for item in node[2:-1]:
        if is_list(item) and item[0] == name:
            return item
    return None


def lib_join_of(node, name):
    return is_list(node, 'lib-join') and node[2] == name


def match_part(node):
    """(part name, the relations that fill its holes), or None."""
    if not is_list(node):
        return None
    text = node_text(node)
    if text in CONSTANT_OF:
        return CONSTANT_OF[text], []
    head = node[0]
    if head == 'lib-join' and node[2] == 'relative' and is_list(node[1], 'join'):
        rel, box = node[1][1], node[1][2]
        if is_list(box, 'component') and box[1] == 'BoundingBox':
            return 'cells relative to their box', [rel]
    if head == 'all' and is_list(node[2], 'component') and node[2][1] == 'Singleton' and node[2][-1] == 'value':
        member = binding(node[2], 'member')
        if member is not None and node_text(member[1]) == node_text(node[1]):
            return 'determines', [node[1]]
    if head == 'component':
        name, port = node[1], node[-1]
        if name == 'Order' and port in ('maximal', 'minimal'):
            member, score = binding(node, 'member'), binding(node, 'score')
            if member and score and node_text(member[1]) == node_text(score[1]):
                return 'extreme by a score', [member[1]]
        if name == 'Inclusion' and port == 'equal':
            pattern, observed = binding(node, 'pattern'), binding(node, 'observed')
            if pattern and observed:
                return 'equal sets', [pattern[1], observed[1]]
        if name == 'Agreement':
            source, target = binding(node, 'source'), binding(node, 'target')
            if source and target:
                return 'symmetries of a set' if node_text(source[1]) == node_text(target[1]) else 'agreement under D4', [source[1], target[1]]
        if name == 'Occurrences':
            shape = binding(node, 'shape')
            if shape:
                return 'occurrences in the output', [shape[1]]
        if name == 'Connectivity':
            nodes = binding(node, 'node')
            if nodes:
                return 'connected pieces', [nodes[1]]
        if name == 'Cardinality' and binding(node, 'domain'):
            return 'count with a domain', [binding(node, 'member')[1], binding(node, 'domain')[1]]
        if name == 'CellDistance':
            source = binding(node, 'source')
            if source:
                return 'distance from a set', [source[1]]
    # A set's cells on a grid, and the colors under them.
    if head == 'project' and is_list(node[1], 'join') and node[1][2] in GRIDS and len(node) == 3:
        pairs = node[1][3:]
        if len(pairs) == 1 and pairs[0][1] == 'P':
            if node[2] == pairs[0][0]:
                return 'cells on a grid', [node[1][1]]
            if node[2].startswith('Col'):
                return 'colors under cells', [node[1][1]]
    if head == 'project' and is_list(node[1], 'join') and node[1][2] in GRIDS and len(node) == 3:
        pairs = node[1][3:]
        if len(pairs) == 1 and pairs[0][1] == 'Col' and node[2] == pairs[0][0]:
            return 'colors on a grid', [node[1][1]]
    # A relation's rows by whether their cell changes.
    if head == 'select' and is_list(node[1], 'join') and is_list(node[1][1], 'join') and node[1][2] == 'output' and node[1][1][2] == 'input' and node[3] == '!=':
        return 'rows whose cell changes', [node[1][1][1]]
    if head in ('join', 'antijoin') and is_list(node[1], 'join') and node[1][2] == 'input' and node[2] == 'output' and len(node) == 5 and node[4] == ['Col', 'Col']:
        return 'rows whose cell stays' if head == 'join' else 'rows whose cell changes', [node[1][1]]
    # The cells around a set.
    if head == 'antijoin' and lib_join_of(node[1], 'neighbor') and node_text(node[1][1]) == node_text(node[2]):
        return 'cells around a set', [node[2]]
    if head == 'join' and lib_join_of(node[1], 'neighbor') and node[2] in GRIDS:
        return 'neighbor colors', [node[1][1]]
    if head == 'lib-join' and node[2] == 'apply' and is_list(node[1], 'join') and node[1][2] == 'd4_elem':
        return 'images under D4', [node[1][1]]
    # Two relations' rows that share a line.
    if head == 'join' and lib_join_of(node[1], 'split') and lib_join_of(node[2], 'split'):
        return 'on a shared line', [node[1][1], node[2][1]]
    if head == 'join' and lib_join_of(node[1], 'corner_dist') and lib_join_of(node[2], 'corner_dist'):
        return 'on a shared diagonal', [node[1][1], node[2][1]]
    # A set's rows with the cells inside its boxes.
    if head == 'lib-join' and node[2] == 'inside' and is_list(node[1], 'join'):
        return 'cells inside boxes', [node[1][1], node[1][2]]
    return None


def count_inside(node, seen, used):
    if not is_list(node):
        return 0
    text = node_text(node)
    if text in seen:
        return 0
    seen.add(text)
    part = match_part(node)
    if part is not None:
        used[part[0]] += 1
        return 1 + sum(count_inside(child, seen, used) for child in part[1])
    own, children = operator_children(node)
    return own + sum(count_inside(child, seen, used) for child in children)


def size_in_parts(terms, how):
    """A root's size in parts, by how its value reads its terms."""
    used = collections.Counter()
    nodes = [parse(term) for term in terms]
    if how == 'claims':
        return max(count_inside(node, set(), used) for node in nodes), used
    if how == 'compare':
        # Two tests over one join of two counts: the ratio of the two relations.
        product = nodes[0][1]
        seen = set()
        total = 0
        for side in product[1:3]:
            inner = side
            if is_list(side, 'component') and side[1] == 'Cardinality':
                inner = binding(side, 'member')[1]
            total += count_inside(inner, seen, used)
        return total, used
    seen = set()
    return sum(count_inside(node, seen, used) for node in nodes), used


def how_of(terms):
    nodes = [parse(term) for term in terms]
    first = nodes[0]
    if len(nodes) == 2 and is_list(first, 'select') and is_list(nodes[1], 'select') and is_list(first[1], 'join') and node_text(first[1]) == node_text(nodes[1][1]) and len(first[1]) == 3:
        return 'compare'
    if len(nodes) >= 3 and sum(is_list(node, 'antijoin') for node in nodes) >= 2:
        return 'claims'
    return 'root'


# ---- how many shapes enumeration over the parts has, on one schema

NUMBER = {'Nat', 'Int', 'N'}
PLACE = {'Position'}
ORDERED = NUMBER


def count_shapes(schema, largest, keep_lib=True, max_columns=7):
    """Counts of relation terms by size in parts, per column-type state. A column of the schema is a hole of one binding."""
    leaves = [tuple(sorted(schema)), ('Color', 'Position')]
    constant_states = [('Color', 'Color', 'Position'), ('Color',), ('Color', 'Position'), ('Color', 'Position'), ('Color', 'Ident', 'Position'), ('Ident', 'Position'), ('Ident',), ('Box', 'Color', 'Ident'), ('Color', 'Nat'), ('Color',), ('Color', 'Dir8', 'Position'), ('Axis', 'Box', 'Color'), ('Axis', 'Box', 'Box', 'Color', 'Position'), ('Box', 'Color'), ('Box',), ('Color',), ('Axis', 'Nat'), ('Nat',), ('Position',), ('Color',)]
    by_size = [collections.Counter() for _ in range(largest + 1)]
    for state in leaves:
        by_size[0][state] += 1
    by_size[0][('Color', 'Position')] += 1  # the two grids
    roles = 24
    for state in constant_states:
        by_size[1][tuple(sorted(state))] += 1
    by_size[1][('Position',)] += roles

    def unary(state):
        """(new state, how many terms) of each operator or part over a relation."""
        n = len(state)
        out = []
        for k in range(1, min(3, n) + 1):
            for chosen in set(combinations(state, k)):
                ways = 1
                for t in set(chosen):
                    a, b = state.count(t), chosen.count(t)
                    for i in range(b):
                        ways = ways * (a - i) // (i + 1)
                out.append((tuple(sorted(chosen)), ways))
        for t in set(state):
            a = state.count(t)
            if a >= 2:
                pairs = a * (a - 1) // 2
                rest = list(state)
                rest.remove(t)
                out.append((tuple(sorted(rest)), pairs))
                out.append((state, pairs * (5 if t in NUMBER else 1)))
            if t in NUMBER or t in ('Box', 'Position'):
                rest = list(state)
                rest.remove(t)
                out.append((tuple(sorted(rest)), a))
                out.append((state, a * (5 if t in NUMBER else 1)))
        positions = state.count('Position')
        if positions:
            out.append((('Position',), positions * 2))  # cells on a grid
            out.append((('Color',), positions * 2))  # colors under cells
            out.append((tuple(sorted(state + ('Position',))), positions))  # cells around a set
            out.append((tuple(sorted(state + ('Color', 'Position'))), positions * 2))  # neighbor colors
            out.append((tuple(sorted(state + ('Box',))), positions * max(1, 2 ** min(n - 1, 2))))  # cells relative to their box
            out.append((('Ident', 'Position'), positions * max(1, 2 ** min(n - 1, 2))))  # connected pieces
            out.append((('Nat', 'Position'), positions))  # distance from a set
            out.append((('Box', 'D4', 'Ident') if n > 1 else ('Box', 'D4'), positions))  # occurrences in the output
            if keep_lib:
                out.append((tuple(sorted(state + ('Axis', 'Box', 'Box'))), positions))  # split
                out.append((tuple(sorted(state + ('DiagDir', 'Nat'))), positions))  # corner_dist
                out.append((tuple(sorted(state + ('Dir', 'Nat'))), positions))  # margin
            out.append((tuple(sorted(state + ('Color',))), positions * 2))  # the join with a grid
        keys = [c for k in range(1, min(2, n) + 1) for c in combinations(range(n), k)]
        for key in set(tuple(sorted(state[i] for i in c)) for c in keys):
            ways = sum(1 for c in keys if tuple(sorted(state[i] for i in c)) == key)
            fields = n - len(key)
            if fields > 0:
                out.append(((), ways * fields))  # determines
                out.append((tuple(sorted(key + ('Color',))), ways * fields))  # a key's one value
                out.append((tuple(sorted(key + ('Nat',))), ways))  # a key's count
                out.append((tuple(sorted(key + ('Color',))), ways * fields))  # extreme by a score
        return out

    def binary(left, right):
        """(new state, how many terms) of each binary operator over two relations."""
        out = []
        pairs = [(i, j) for i, a in enumerate(left) for j, b in enumerate(right) if a == b or {a, b} <= {'Position', 'Box'}]
        one = len(pairs)
        two = sum(1 for a, b in combinations(pairs, 2) if a[0] != b[0] and a[1] != b[1])
        for count, matched in ((one, 1), (two, 2)):
            if count == 0:
                continue
            # Each binding drops `matched` of the right's columns: read as an average state.
            rest = list(right)
            taken = [pairs[0][1]] if matched == 1 else [pairs[0][1], next((b[1] for b in pairs if b[0] != pairs[0][0] and b[1] != pairs[0][1]), pairs[0][1])]
            for at in sorted(set(taken), reverse=True):
                rest.pop(at)
            state = tuple(sorted(left + tuple(rest)))
            if len(state) <= max_columns:
                out.append((state, count))
            out.append((left, count * 2))  # semijoin, antijoin
            out.append(((), count))  # all
            for t in set(left):
                out.append(((t,), count * left.count(t)))  # all with an outer column
        return out

    for size in range(1, largest + 1):
        for state, count in list(by_size[size - 1].items()):
            for new, ways in unary(state):
                if len(new) <= max_columns:
                    by_size[size][new] += count * ways
        for a in range(0, size):
            b = size - 1 - a
            for left, lc in by_size[a].items():
                for right, rc in by_size[b].items():
                    for new, ways in binary(left, right):
                        by_size[size][new] += lc * rc * ways
    return [sum(c.values()) for c in by_size]


def main():
    rows = list(csv.DictReader(open_text(sys.argv[1]), delimiter='\t'))
    if len(sys.argv) > 2:
        out = {}
        for row in rows:
            if row['expression']:
                terms = row['expression'].split(' ; ')
                out[row['template'].replace('key.C', 'C')] = min(size_in_parts(terms, how_of(terms))[0], out.get(row['template'].replace('key.C', 'C'), 99))
        import json
        open(sys.argv[2], 'w').write(json.dumps(out))
    ranked = sorted((r for r in rows if r['rank'] and r['expression']), key=lambda r: int(r['rank']))
    parts_count = collections.Counter()
    sizes = {}
    for row in ranked:
        terms = row['expression'].split(' ; ')
        size, used = size_in_parts(terms, how_of(terms))
        sizes[row['template']] = (size, used)
        parts_count.update(used.keys())
    print('parts, by the count of templates that use each:')
    for name, count in parts_count.most_common():
        print(f'  {count:>4} {name}')
    print('top 30: rank, distinct, in parts, kind, parts used')
    for row in ranked[:30]:
        size, used = sizes[row['template']]
        print(f"  {row['rank']:>3} {row['size distinct']:>3} -> {size:>2}  {row['template'][:58]:<58} {', '.join(sorted(used))}")
    counts = collections.Counter(size for size, _ in sizes.values())
    total = len(sizes)
    held = 0
    print('reach by size in parts:')
    for size in sorted(counts):
        held += counts[size]
        print(f'  {size:>2}: {counts[size]:>4}  cumulative {held}/{total}')
    print('shapes by size in parts, per schema: relation terms at sizes 0, 1, 2, 3')
    for schema in (('Color', 'Position'), ('Color', 'Ident', 'Position'), ('Nat', 'Position'), ('Axis', 'Box', 'Position')):
        print(f'  {schema}: {count_shapes(schema, 3)}; without lib-joins {count_shapes(schema, 3, False)}')
    print('misses at 3 parts, in rank order: rank, size, kind')
    for row in ranked:
        size, used = sizes[row['template']]
        if size > 3 and not row['template'].startswith('key.'):
            print(f"  {row['rank']:>3} {size:>2} {row['template'][:80]}")


if __name__ == '__main__':
    main()

#!/usr/bin/env python
"""The written templates' sizes when each named part counts 1.

  python model/feature_eval/template_parts.py results/template-shapes.tsv

A part is a pattern over a term. It counts 1, with the relations that fill its holes counted
as usual, and a subexpression that appears twice counts once.
"""
import collections
import csv
import sys

from template_shapes import (BACKGROUND, CHANGED, COMPONENTS, COMPONENT_BOX, FOREGROUND, FOREGROUND_PARTS, INPUT_BACKGROUND, INPUT_FOREGROUND, LINES,
                             FULL_LINES, ON_FULL_LINE, PER_COLOR, SAME_COLOR_NEIGHBOR, node_text, operator_children, parse)

CONSTANTS = {
    'changed cells': [CHANGED],
    'background': [BACKGROUND, f'(component Singleton (member {BACKGROUND} () (Col)) value)', INPUT_BACKGROUND],
    'foreground': [FOREGROUND, INPUT_FOREGROUND, f'(join output {BACKGROUND} (Col Col))'],
    'components': [COMPONENTS],
    'foreground components': [FOREGROUND_PARTS],
    'component boxes': [COMPONENT_BOX],
    'color counts': [PER_COLOR, PER_COLOR.replace('output', 'input')],
    'same-color neighbors': [SAME_COLOR_NEIGHBOR],
    'full lines': [FULL_LINES],
    'cells on a full line': [ON_FULL_LINE],
    'grid lines': [LINES],
}
CONSTANT_OF = {node_text(parse(text)): name for name, texts in CONSTANTS.items() for text in texts}


def is_list(node, head=None):
    return isinstance(node, list) and (head is None or (node and node[0] == head))


def binding(node, name):
    """The binding of an input in a component, or None."""
    for item in node[2:-1]:
        if is_list(item) and item[0] == name:
            return item
    return None


def match_part(node):
    """(part name, the relations that fill its holes), or None."""
    if not is_list(node):
        return None
    text = node_text(node)
    if text in CONSTANT_OF:
        return CONSTANT_OF[text], []
    head = node[0]
    # A set's cells relative to its box.
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
    # A set's cells with their neighbors' colors.
    if head == 'join' and is_list(node[1], 'lib-join') and node[1][2] == 'neighbor' and node[2] in ('input', 'output'):
        return 'neighbor colors', [node[1][1]]
    # The images of placed cells under D4.
    if head == 'lib-join' and node[2] == 'apply' and is_list(node[1], 'join') and node[1][2] == 'd4_elem':
        return 'images under D4', [node[1][1]]
    return None


def size_in_parts(terms):
    seen = set()
    used = collections.Counter()

    def walk(node):
        if not is_list(node):
            return 0
        text = node_text(node)
        if text in seen:
            return 0
        seen.add(text)
        part = match_part(node)
        if part is not None:
            used[part[0]] += 1
            return 1 + sum(walk(child) for child in part[1])
        own, children = operator_children(node)
        return own + sum(walk(child) for child in children)

    return sum(walk(parse(term)) for term in terms), used


def main():
    rows = list(csv.DictReader(open(sys.argv[1]), delimiter='\t'))
    ranked = sorted((r for r in rows if r['rank'] and r['expression']), key=lambda r: int(r['rank']))
    parts_count = collections.Counter()
    sizes = {}
    for row in ranked:
        terms = row['expression'].split(' ; ')
        # A share reads the terms of its fraction, and the rest read their one root.
        size, used = size_in_parts(terms)
        sizes[row['template']] = (size, used)
        parts_count.update(used.keys())
    print('parts, by the count of templates that use each:')
    for name, count in parts_count.most_common():
        print(f'  {count:>4} {name}')
    print('top 30:')
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
    print('kinds past 3 parts:')
    for row in ranked:
        size, used = sizes[row['template']]
        if size > 3:
            print(f"  {row['rank']:>3} {size:>2} {row['template'][:80]}")


if __name__ == '__main__':
    main()

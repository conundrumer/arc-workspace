#!/usr/bin/env python
"""Points with the target's atoms in a random valid order, to read what the written order leaves in the label.

  python features_ps_shuffle.py pool      writes points-held-pool-shuffled.jsonl from points-held-pool.jsonl
  python features_ps_shuffle.py census    writes points-census-shuffled.jsonl from the census's forms, parents scope, gold-v3-helper-forms-a036da074 base view

A form with an OR, an ALL or a nested atom is left out, as is a form of one atom. In the new order, an atom with no label in common with those before waits while another has one, and NOT and comparison atoms wait until each label they read is bound. A label keeps a star at its first positive atom in the new order, where its first positive atom in gold's order had one. The order is a draw seeded by the task and form, and it is the same for each scope of a form. The walk's `bad` and `dead` say whether it took the order.
"""
import json
import re
import sys
import zlib

import numpy as np

ME = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37/'
sys.path.insert(0, ME)
import features_perrel_keys as K  # noqa: E402

CENSUS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-relation-pick-read-heldout431-census/forms_all.json'
POINTS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/points-base.json'
LAB = re.compile(r'\(:[\w.]+ (\*?)([A-Za-z_]\w*)\)')
NAMEFIRST = re.compile(r'^\((?:NOT \()?([^\s()]+)')


def split(text):
    """(head text, atoms) of a RULE form, or None for a form this script leaves out."""
    m = re.match(r'\(RULE (&\w+) ', text)
    if m is None or not text.endswith(')'):
        return None
    body, atoms, depth, st = text[m.end():-1], [], 0, 0
    for i, c in enumerate(body):
        if c == '(':
            if depth == 0:
                st = i
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                atoms.append(body[st:i + 1])
    if len(atoms) < 2 or any(a.startswith(('(OR', '(ALL', '(IF')) for a in atoms):
        return None
    for a in atoms:
        x = a[5:-1] if a.startswith('(NOT ') else a
        if '((' in x or x.count('(') != x.count('(:') + 1:
            return None
    return text[:m.end()], atoms


def labels(a):
    if a.startswith(('(<', '(!=', '(=', '(>')):
        return set(re.findall(r'[A-Z]\w*', a))
    return {y for _x, y in LAB.findall(a)}


def order(text, seed):
    got = split(text)
    if got is None:
        return None
    head, atoms = got
    rng = np.random.RandomState(seed)
    pos = [not a.startswith(('(NOT', '(<', '(!=', '(=', '(>')) for a in atoms]
    star, seen = {}, set()
    for a, p in zip(atoms, pos):
        if p:
            for s, y in LAB.findall(a):
                if y not in seen:
                    seen.add(y)
                    star[y] = bool(s)
    left = list(range(len(atoms)))
    rng.shuffle(left)
    bound, new = set(), []
    while left:
        ok = [i for i in left if pos[i] and (not bound or labels(atoms[i]) & bound)]
        ok += [i for i in left if not pos[i] and (labels(atoms[i]) & seen) <= bound]
        i = ok[0] if ok else next((j for j in left if pos[j]), left[0])
        left.remove(i)
        if pos[i]:
            a = re.sub(r'(\(:[\w.]+ )\*', r'\1', atoms[i])

            def mark(m, b=bound):
                y = m[2]
                if y not in b and star.get(y):
                    b.add(y)
                    return m[1] + '*' + y + ')'
                b.add(y)
                return m[0]
            a = re.sub(r'(\(:[\w.]+ )([A-Za-z_]\w*)\)', mark, a)
            new.append(a)
        else:
            new.append(atoms[i])
    if new == atoms:
        return text, False
    return head + ' '.join(new) + ')', True


def main():
    mode = sys.argv[1]
    if mode.startswith('fit-'):
        rows = [json.loads(x) for x in open(ME + 'points-%s.jsonl' % mode)]
    elif mode == 'pool':
        rows = [json.loads(x) for x in open(ME + 'points-held-pool.jsonl')]
    else:
        gold = {x['task']: [y for y in x['gold_sexp'].splitlines() if y.strip()] for x in json.load(open(POINTS))}
        rows = []
        for r in json.load(open(CENSUS)):
            t, g = r[4], r[5]
            ls = gold[t]
            rows.append(dict(arm='census', task=t, form=g, stratum='census', scope=[ls[i] for i in K.parents(ls, g)], target=ls[g], line=len(rows)))
    n = out = same = 0
    name = ME + ('points-held-pool-shuffled.jsonl' if mode == 'pool' else 'points-census-shuffled.jsonl' if mode == 'census' else 'points-%s-shuffled.jsonl' % mode)
    with open(name, 'w') as f:
        for p in rows:
            got = order(p['target'], zlib.crc32(('shuffle %s %d' % (p['task'], p['form'])).encode()))
            if got is None:
                out += 1
                continue
            p['target'], moved = got
            p['stratum'] = 'moved' if moved else 'unmoved'
            same += not moved
            n += 1
            f.write(json.dumps(p) + '\n')
    print(mode, 'points', n, 'left out', out, 'same order as written', same)


main()

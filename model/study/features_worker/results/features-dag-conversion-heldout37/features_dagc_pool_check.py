#!/usr/bin/env python
"""Item 18 check: the visit form counts of this conversion's pool point files against the source's (features-relation-pick-per-relation-pool-scope-heldout37). No engine.

  python -I features_dagc_pool_check.py        writes pool-check.txt

A RULE point is matched by (arm, task, form index in the pass1 gold, visit second). Counts compared: visit_forms (forms of the visit), pool_forms (forms of the scope), and the strata. The points differ in scope text (DAG order) and `line`, so those are not compared.
Fit points: counts of points by kind and stratum against the source's fit-train and fit-test files (both are the same 1,011-task corpus view only in part: the conversion's fit points are the three kinds, the source's the RULE forms).
"""
import collections
import json
import os

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
SRC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37/'


def load(path):
    return [json.loads(x) for x in open(path)]


def groups(ps, rule):
    d = collections.defaultdict(list)
    for p in ps:
        if rule and p['kind'] != 'RULE':
            continue
        d[(p['arm'], p['task'], p['form'])].append(p)
    return d


def compare(name, mine, theirs, lines):
    """The visits of a form and arm: a group is (arm, task, form index). The count of visits in a group, the strata, the visit form counts and the visit seconds are compared as multisets."""
    a, b = groups(mine, True), groups(theirs, False)
    both = sorted(set(a) & set(b))
    f = lambda g: collections.Counter(len(v) for v in g.values())
    eq = collections.Counter()
    for k in both:
        for field in ('stratum', 'visit_forms', 'pool_forms', 'visit_second'):
            eq[field] += sorted(x.get(field) for x in a[k]) == sorted(x.get(field) for x in b[k])
        eq['count'] += len(a[k]) == len(b[k])
    sa = collections.Counter(p['stratum'] for v in a.values() for p in v)
    sb = collections.Counter(p['stratum'] for v in b.values() for p in v)
    va = collections.Counter(p['visit_forms'] for v in a.values() for p in v)
    vb = collections.Counter(p['visit_forms'] for v in b.values() for p in v)
    lines.append('%s: groups (arm, task, form) here %d (RULE points %d of %d), source %d; in both %d; visits per group here %s, source %s; groups with the same visit count %d, same strata %d, same visit_forms %d, same pool_forms %d, same visit seconds %d' % (
        name, len(a), sum(len(v) for v in a.values()), len(mine), len(b), len(both), dict(f(a)), dict(f(b)), eq['count'], eq['stratum'], eq['visit_forms'], eq['pool_forms'], eq['visit_second']))
    lines.append('  strata here %s, source %s; mean visit_forms here %.2f, source %.2f' % (dict(sa), dict(sb), sum(k * v for k, v in va.items()) / max(sum(va.values()), 1), sum(k * v for k, v in vb.items()) / max(sum(vb.values()), 1)))
    return len(set(a) ^ set(b)) + (len(both) - eq['count'])


def main():
    lines = []
    bad = 0
    bad += compare('held-pool', load(ME + 'points-held-pool.jsonl'), load(SRC + 'points-held-pool.jsonl'), lines)
    bad += compare('held-wide', load(ME + 'points-held-wide.jsonl'), load(SRC + 'points-held-wide-pool.jsonl'), lines)
    for name, mine, theirs in (('fit-pool-train', 'points-fit-pool-train-0of1.jsonl', 'points-fit-train.jsonl'), ('fit-pool-test', 'points-fit-pool-test-0of1.jsonl', 'points-fit-test.jsonl')):
        a, b = load(ME + mine), load(SRC + theirs)
        lines.append('%s: this conversion %d points (%s), source %d points (%s); tasks here %d, source %d, in both %d' % (name, len(a), dict(collections.Counter(p['kind'] for p in a)), len(b), 'RULE only',
                                                                                                                        len({p['task'] for p in a}), len({p['task'] for p in b}), len({p['task'] for p in a} & {p['task'] for p in b})))
        rule_a = {(p['task'], p['form']) for p in a if p['kind'] == 'RULE'}
        rule_b = {(p['task'], p['form']) for p in b}
        lines.append('  RULE forms here %d, source %d, in both %d' % (len(rule_a), len(rule_b), len(rule_a & rule_b)))
    open(ME + 'pool-check.txt', 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print('points that differ: %d' % bad)


if __name__ == '__main__':
    main()

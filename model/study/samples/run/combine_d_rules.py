#!/usr/bin/env python
"""combine_d_rules.py DIR OUT.json [--min-n-derived N] [--min-n-zero N]: sums the lines of DIR/*.jsonl.zst that derive_d_rules.py wrote and derives the parameters of the D parts
(lookahead_legal.py); OUT.json is the file that env WRITER_TRAIN_STATS names. Prints, per gate, the strict form's count of train gold violations and the parameter.
Runs with the repo's runtime-kaggle-py313 venv python (zstandard)."""
import argparse, collections, glob, json
import zstandard

ap = argparse.ArgumentParser()
ap.add_argument('dir'); ap.add_argument('out')
ap.add_argument('--min-n-derived', type=int, default=5, help='port bodies over a non-empty scope that a component needs before DerivedPort holds it to reading a derived relation')
ap.add_argument('--min-n-zero', type=int, default=1, help='values at a (relation, column) that ZeroBinder needs before it removes a kind')
a = ap.parse_args()

S = collections.Counter()
Mx = collections.defaultdict(int)
sets = collections.defaultdict(set)
ex = collections.defaultdict(list)
tasks = set()
for f in sorted(glob.glob(a.dir + '/*.jsonl.zst')):
    with open(f, 'rb') as fh:
        text = zstandard.ZstdDecompressor().stream_reader(fh, read_across_frames=True).read().decode()
    for line in text.splitlines():
        r = json.loads(line)
        if r['task'] in tasks:
            continue
        tasks.add(r['task'])
        S.update(r['sums'])
        for k, v in r['maxes'].items():
            Mx[k] = max(Mx[k], v)
        for k, v in r['sets'].items():
            sets[k] |= set(v)
        for k, v in r['examples'].items():
            if len(ex[k]) < 4:
                ex[k].extend([dict(task=r['task'], **e) for e in v[:1]])


def n(key):
    return S.get(key, 0)


def pre(prefix):
    return {k[len(prefix):]: v for k, v in S.items() if k.startswith(prefix)}


out, report = {}, {}
report['tasks'] = len(tasks)
report['targets'] = n('targets')
report['gold outside the engine mask'] = n('gold outside the engine mask')
report['walk errors'] = {k: v for k, v in S.items() if k.startswith('walk error')}

# Kinds
out['kinds'] = {k: sorted(sets.get(k, ())) for k in ('proposers', 'comps', 'comp_ports')}

# StopEmpty, StopOneAtom: facts only
report['StopEmpty'] = dict(gold_removed=n('stop|StopEmpty|gold_removed'), ends=n('stop|ends|RULE') + n('stop|ends|DET'), strict_form_holds=n('stop|StopEmpty|gold_removed') == 0)
report['StopOneAtom'] = dict(gold_removed=n('stop|StopOneAtom|gold_removed'), ends=n('stop|ends|RULE') + n('stop|ends|DET'), strict_form_holds=n('stop|StopOneAtom|gold_removed') == 0)

# UnjoinedAtom
enforce = {}
for cls in ('top', 'or', 'all'):
    enforce[cls] = n('flc|%s|floating' % cls) == 0
out['unjoined'] = dict(enforce=enforce)
report['UnjoinedAtom'] = {cls: dict(required_atoms=n('flc|%s|required' % cls), floating=n('flc|%s|floating' % cls)) for cls in ('top', 'or', 'all')}
rq = [(k, v) for k, v in S.items() if k.startswith('unj|') and '|req1|' in k]
tot = sum(v for _, v in rq)
no_join = sum(v for k, v in rq if '|js0|' in k)
report['UnjoinedAtom']['strict_form'] = dict(required_atoms=tot, reading_no_label_at_a_site=no_join)

# DerivedPort
comps = collections.defaultdict(lambda: [0, 0])  # comp -> [no, yes] over a non-empty scope
for k, v in S.items():
    if k.startswith('port|comp|') and '|scope1|derived|' in k:
        c, y = k[len('port|comp|'):].split('|scope1|derived|')
        comps[c][int(y)] += v
holds = [c for c, (no, yes) in comps.items() if no == 0 and yes >= a.min_n_derived]
total_no = sum(no for no, _ in comps.values())
out['derived_port'] = dict(comps=None if total_no == 0 else sorted(holds), min_n=a.min_n_derived)
report['DerivedPort'] = dict(strict_form_violations=total_no, port_bodies_scope_nonempty=sum(sum(x) for x in comps.values()), port_bodies_scope_empty=n('port|derived|scope0|0') + n('port|derived|scope0|1'),
                             components_held=sorted(holds), by_component={c: dict(without=no, with_=yes) for c, (no, yes) in sorted(comps.items())})

# UnreadPortEnd, UnreadPortHead
out['unread_port'] = dict(max_end=Mx['port|unread_pre'], max_head=max(1, Mx['port|unread_post']))
report['UnreadPort'] = dict(strict_form_max=1, observed_max_at_body_end=Mx['port|unread_pre'], observed_max_after_head=Mx['port|unread_post'],
                            histogram_at_body_end=pre('port|unread_pre|'), histogram_after_head=pre('port|unread_post|'))

# OrNesting, AllNesting
out['or_nesting'] = dict(max_depth=max(2, Mx['or|depth']), second_in_branch=n('or|nested|second_in_branch') > 0, continue_first=True,
                         continue_notfirst=n('or|after_nested|notfirst|continue') > 0, in_all=n('or|in_all') > 0)
report['OrNesting'] = dict(ors=n('or|total'), nested=n('or|nested'), observed_depth=Mx['or|depth'], second_in_branch=n('or|nested|second_in_branch'),
                           after_nested={k: v for k, v in S.items() if k.startswith('or|after_nested|')}, or_in_all=n('or|in_all'),
                           strict_form_holds=Mx['or|depth'] <= 2 and n('or|nested|second_in_branch') == 0 and n('or|after_nested|notfirst|continue') == 0 and n('or|in_all') == 0)
out['all'] = dict(guard_read=n('allg|made1|reads0') == 0, in_all=(n('all|in_all') + n('or|in_all')) > 0)
report['AllGuardRead'] = dict(alls=n('all|total'), conclusions_with_guard_labels=n('allg|made1|reads0') + n('allg|made1|reads1'), conclusions_reading_none=n('allg|made1|reads0'),
                              conclusion_atoms=pre('all|conclusion_atoms|'))
report['AllNesting'] = dict(all_in_all=n('all|in_all'), all_in_or=n('all|in_or'), or_in_all=n('or|in_all'))

# OrBranchClose
out['or_close'] = dict(missing_max=Mx['orb|missing'], unread_max=Mx['orb|unread'])
report['OrBranchClose'] = dict(later_branch_closes=n('orb|closes'), strict_form_missing_violations=n('orb|closes') - n('orb|missing|0'), strict_form_unread_violations=n('orb|closes') - n('orb|unread|0'),
                               observed_missing_max=Mx['orb|missing'], observed_unread_max=Mx['orb|unread'], key_body_closes_not_measured=n('orb|key_body_closes'))

# RigidDetPlain
classes = ('not', 'eq', 'cmp_other', 'input', 'or', 'all', 'dup_rel')
out['rigid_det'] = dict(refuse=[c for c in classes if n('rd|' + c) == 0])
report['RigidDetPlain'] = dict(atoms=n('rd|atoms'), tokens_by_class={c: n('rd|' + c) for c in classes}, other_fact_relations=n('rd|fact_other'), refuse=out['rigid_det']['refuse'])

# ZeroBinder
table = collections.defaultdict(dict)
for k, v in S.items():
    if k.startswith('zb|'):
        _, rel, col, kind = k.split('|')
        table['%s|%s' % (rel, col)][kind] = v
out['zero_binder'] = dict(min_n=a.min_n_zero, table=table)
report['ZeroBinder'] = dict(relation_columns=len(table), by_min_n={m: sum(1 for c in table.values() if sum(c.values()) >= m) for m in (1, 3, 10)},
                            fresh_zero=sum(1 for c in table.values() if sum(c.values()) >= a.min_n_zero and not c.get('fresh')),
                            join_zero=sum(1 for c in table.values() if sum(c.values()) >= a.min_n_zero and not c.get('join')),
                            zero_zero=sum(1 for c in table.values() if sum(c.values()) >= a.min_n_zero and not c.get('zero')))

out['report'] = report
out['examples'] = ex
with open(a.out, 'w') as f:
    json.dump(out, f, indent=0)
print(json.dumps({k: v for k, v in report.items()}, indent=1))

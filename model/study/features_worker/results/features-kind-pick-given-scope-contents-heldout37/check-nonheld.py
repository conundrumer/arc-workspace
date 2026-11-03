"""Sanity counts on non-held rows only: column types, form kinds, head names, how often each fact takes each value."""
import collections
import csv
import os
H = os.path.dirname(os.path.abspath(__file__)) + '/'
ty = collections.Counter()
kd = collections.Counter()
hd = collections.Counter()
key = collections.Counter()
for r in csv.DictReader(open(H + 'gold-form-rows.tsv'), delimiter='\t'):
    if r['split'] != 'nonheld':
        continue
    kd[r['kind']] += 1
    hd[r['head']] += 1
    key[r['kind'], r['key']] += 1
    for t in r['cols'].split(','):
        ty[t] += 1
print('forms by kind', kd)
print('key by kind', key)
print('types', ty.most_common(40))
print('heads', hd.most_common(30))
val = collections.defaultdict(collections.Counter)
n = 0
for r in csv.DictReader(open(H + 'gold-scope-rows.tsv'), delimiter='\t'):
    if r['split'] != 'nonheld' or r['rule'] != 'picks6':
        continue
    n += 1
    for k in ('last', 'cols', 'key', 'ident', 'stage', 'size'):
        val[k][r[k]] += 1
print(n)
for k, v in val.items():
    print(k, v.most_common(10))

"""Writes frozen.json: for each target and tier, the situation keys that select() picked on fit rows alone, from the last dev_read row of the target and tier."""
import json

import next_form_facts as F

keys = {}
for x in open(F.R + 'dev-read.jsonl'):
    r = json.loads(x)
    keys.setdefault(r['target'], {})[r['tier']] = [k.split('*') for k in r['keys']]
miss = [(t, x) for t in keys for x in ('need', 'foundset', 'need+foundset') if x not in keys[t]]
assert not miss, miss
# Nested tiers, so that a tier reads what the keys of a family add: need+foundset is the union of the keys of need and of foundset.
for t, d in keys.items():
    d['need+foundset'] = d['foundset'] + [k for k in d['need'] if k not in d['foundset']]
json.dump(dict(keys=keys), open(F.R + 'frozen.json', 'w'), indent=1)
print({t: {x: len(v) for x, v in d.items()} for t, d in keys.items()})

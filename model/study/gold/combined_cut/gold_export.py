"""Writes the gold that agents and the repo read: work/lm/data-study/gold/gold-export/concept/<stem>.arclog (the converter's concept file in gen-v3), work/lm/data-study/gold/gold-export/flat/<stem>.arclog (the text of view-final) and programs/gold/manifest.json. A rerun rewrites them all; a stem gone from view-final loses its files.

  python3 gold_export.py
"""
import gzip, hashlib, json, os, shutil
R = '/Users/davidlu/code/arc-workspace/'
D = R + 'work/lm/data-study/gold/'
VIEW = D + 'gold-v3-combined-cut/view-final/'
GEN = D + 'gen-v3-11f6a212c/corpus/gen/'
HAND = D + 'gold-v3-cover-forms-a036da074/round-out/hand-rewrites.jsonl'
OUT = R + 'work/lm/data-study/gold/gold-export/'

hand = {}
for l in open(HAND):
    r = json.loads(l)
    if r['taken'] is True:
        hand[r['stem']] = r['source']
new = OUT[:-1] + '.new/'
shutil.rmtree(new, ignore_errors=True)
os.makedirs(new + 'concept')
os.makedirs(new + 'flat')
stems = {}
for t in sorted(os.listdir(VIEW)):
    p = VIEW + t + '/pairs.jsonl.gz'
    if not os.path.exists(p):
        continue
    with gzip.open(p, 'rt') as f:
        first = json.loads(f.readline())
    flat = '\n'.join(x for x in first['gold_sexp'].splitlines() if x.strip()) + '\n'
    open(new + 'flat/%s.arclog' % t, 'w').write(flat)
    row = dict(flat_sha=hashlib.sha256(flat.encode()).hexdigest()[:16])
    if os.path.exists(GEN + t + '.arclog'):
        concept = open(GEN + t + '.arclog').read()
        open(new + 'concept/%s.arclog' % t, 'w').write(concept)
        row['concept_sha'] = hashlib.sha256(concept.encode()).hexdigest()[:16]
    if first.get('approximated'):
        row['approximated'] = True
    if t in hand:
        row['whole_program_rewrite'] = hand[t]
    stems[t] = row
json.dump(dict(flat='the gold text of each stem: the cheapest known right program, one form a line', concept='the converter\'s output for the solver of the same name in programs/solvers; flat text comes from it through the gold stages', approximated='the solver has @approximated; consumers leave the stem out by default', whole_program_rewrite='the flat text started from a whole program written outside the converter (kind: gold-v3-kind-forms-a036da074, or: gold-or-rewrite-heldout7)', stems=stems), open(new + 'manifest.json', 'w'), indent=1)
shutil.rmtree(OUT, ignore_errors=True)
os.rename(new, OUT)
print(len(stems), 'stems,', sum('concept_sha' in r for r in stems.values()), 'with a concept file,', len(hand), 'rewrites,', sum(r.get('approximated', False) for r in stems.values()), 'approximated')

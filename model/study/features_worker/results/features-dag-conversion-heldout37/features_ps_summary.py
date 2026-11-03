#!/usr/bin/env python
"""summary.md and summary.json from the read and compare files of this record. It runs no model and adds no held read.

  python features_ps_summary.py
"""
import glob
import json
import os

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
OLD = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-models-heldout37/'


def read(tag):
    return json.load(open(ME + 'read-%s.json' % tag))


def line(tag, name):
    r = {x['name']: x for x in read(tag)['table']}.get(name)
    return None if r is None else r


def cell(tag, name='Gold alive'):
    r = line(tag, name)
    if r is None:
        return 'no picks'
    return '%+.2f (%+.2f to %+.2f)' % (r['saved'], r['lo'], r['hi'])


MODELS = [
    ('Primary as fit on parents rows, reads written order', 'asfit-final-hyb-noorder'),
    ('Refit on parents rows, no lexical order', 'final-orderfree'),
    ('Refit on pool rows and parents rows, no lexical order', 'final-orderfree-union'),
    ('The same without facts of a form\'s text', 'final-orderfree-union-notext'),
]
CONTROLS = [
    ('Control of the primary as fit', 'asfit-control-hyb-noorder'),
    ('Control of the refit on parents rows', 'control-orderfree'),
    ('Control of the refit on pool rows', 'control-orderfree-union'),
]
out = ['# Relation pick, per-relation models on pool scopes: summary', '', 'Each number is generated from `read-*.json` and `compare.jsonl`. Saved bits are against the steered prior on the same rows, with 95% task intervals. Gold is `gold-v3-extended-cut/view-pass1` on pool rows and `gold-v3-helper-forms-a036da074` base view on census rows.', '']
out += ['## Saved bits per gold-alive pick', '', '| Model | Pool rows, 920 picks, 32 tasks | Same forms, parents scope, 248 picks | Wide pool rows, oracle context with junk, 4,726 picks | Wide parents, 2,434 picks | Census parents, 1,761 picks |', '|---|---|---|---|---|---|']
for n, t in MODELS:
    c = []
    for d in ('held-pool', 'held-parents', 'held-wide-pool', 'held-wide-parents', 'held'):
        p = ME + 'read-%s-on-%s.json' % (t, d)
        c.append(cell('%s-on-%s' % (t, d)) if os.path.exists(p) else 'not read')
    out.append('| %s | %s |' % (n, ' | '.join(c)))
for n, t in CONTROLS:
    out.append('| %s | %s | not read | not read | not read | not read |' % (n, cell('%s-on-held-pool' % t)))
out += ['', '## Random atom order, gold-alive picks', '', '| Model | Pool rows in random order, 566 picks, 26 tasks | Census forms in random order, 640 picks, 36 tasks |', '|---|---|---|']
for n, t in (('Refit on pool rows, random order fit rows', 'final-orderfree-shuffled'), ('Control of that refit', 'control-orderfree-shuffled'), ('Refit on pool rows and parents rows, written order fit rows', 'final-orderfree-union'), ('Refit on parents rows, written order fit rows', 'final-orderfree'), ('Primary as fit, reads written order', 'asfit-final-hyb-noorder')):
    c = []
    for d in ('held-pool-shuffled', 'census-shuffled'):
        c.append(cell('%s-on-%s' % (t, d)) if os.path.exists(ME + 'read-%s-on-%s.json' % (t, d)) else 'not read')
    out.append('| %s | %s |' % (n, ' | '.join(c)))
out += ['', '## By class and position on pool rows, gold-alive picks', '', '| Picks read | Picks | Prior bits | Primary as fit, reads written order | Refit on parents rows | Refit on pool rows | Census parents read: primary as fit | Census parents read: refit on parents rows |', '|---|---|---|---|---|---|---|---|']
for r in read('final-orderfree-union-on-held-pool')['table']:
    if r['name'] == 'All' or ', ' in r['name']:
        continue
    out.append('| %s | %d | %.2f | %s | %s | %s | %s | %s |' % (r['name'], r['picks'], r['prior_bits'], cell('asfit-final-hyb-noorder-on-held-pool', r['name']), cell('final-orderfree-on-held-pool', r['name']), cell('final-orderfree-union-on-held-pool', r['name']), cell('asfit-final-hyb-noorder-on-held', r['name']), cell('final-orderfree-on-held', r['name'])))
out += ['', 'Each model\'s full table, with class by position, is in `table-*.md`. The parents read of the first record, at all picks of the census, is in its `table-final-hyb-noorder.md`. This table reads gold-alive picks.', '']
out += ['## Keys, per form and cost', '']
for n, t in (('Refit on pool rows, pool rows', 'final-orderfree-union-on-held-pool'), ('Primary as fit, pool rows', 'asfit-final-hyb-noorder-on-held-pool'), ('Refit on pool rows, wide pool rows', 'final-orderfree-union-on-held-wide-pool'), ('Random order refit, random order pool rows', 'final-orderfree-shuffled-on-held-pool-shuffled')):
    r = read(t)
    f = r['per_form']
    out.append('- %s: keys past 1 bit net %s, %.1f%% of picks. Per walk, saved %+.2f (%+.2f to %+.2f); at 25 bits or more, %+.2f (%+.2f to %+.2f) on %d walks. Under 25: %d to %d of %d, %d taken under, %d pushed over.' % (n, [(k, round(v, 2), c) for k, v, c in r['keys_pass_net']], 100 * r['share_picks_pass_net'], *f['saved_all'], *f['saved_over25'], f['over25'], f['under25_now'], f['under25_model'], f['walks'], f['taken_under'], f['pushed_over']))
for p in sorted(glob.glob(ME + 'cost-*.json')):
    c = json.load(open(p))
    out.append('- Cost, %s on %s: %.2f ms per pick in a batch, %.0f ms alone, %.0f options per pick; content facts %.0f ms per pick.' % (c['model'], c['data'], c['batch_ms_per_pick'], c['alone_ms_per_pick'], c['options_per_pick'], c['content_cpu_ms_per_pick']))
out += ['', '## Compare lines', '']
for x in open(ME + 'compare.jsonl'):
    d = json.loads(x)
    if d['kind'] == 'strata':
        for k, v in d['strata'].items():
            out.append('- %s, stratum %s: %+.2f (%+.2f to %+.2f), %d picks, %d forms, %d tasks.' % (d['tag'], k, *v['saved'], v['picks'], v['forms'], v['tasks']))
    elif d['kind'] == 'pair':
        out.append('- %s minus %s, %d forms: %+.2f (%+.2f to %+.2f).' % (d['a'], d['b'], d['forms'], *d['a_minus_b']))
    else:
        out.append('- Order, %s, %s forms, %d: random %+.2f (%+.2f to %+.2f), written %+.2f (%+.2f to %+.2f), difference %+.2f (%+.2f to %+.2f).' % (d['label'], d['which'], d['forms'], *d['saved_random_order'], *d['saved_written_order'], *d['random_minus_written']))
out += ['', '## Held reads', '', 'One line per read, in `reads.log`.', '']
open(ME + 'summary.md', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))

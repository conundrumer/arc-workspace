"""Prints a read's tables: tables.py SPLIT. Writes read-<split>.md. Every number comes from read-<split>.json and pool-gap-<split>.json."""
import json
import sys

import next_form_facts as F


def iv(x):
    return '%+.2f (%+.2f to %+.2f)' % (x[0], x[1], x[2]) if x else ''


split = sys.argv[1]
d = json.load(open(F.R + 'read-%s.json' % split))
g = json.load(open(F.R + 'pool-gap-%s.json' % split))
o = []
o.append('# Read on %s: %d forms of %d tasks, %d with census bits, %d at 25 bits or more. %d model reads.' % (split, d['forms'], d['tasks'], d['forms_with_bits'], d['forms_25'], d['model_reads']))
o.append('')
o.append('## Target entropy, bits per form or read')
o.append('')
o.append('| Target | Forms | Fit marginal | Census paid | Tier | Model | Top-1 | Top-5 | Saved, all forms | Saved, 25 bits or more |')
o.append('|---|---|---|---|---|---|---|---|---|---|')
for name, r in d['targets'].items():
    if 'tiers' not in r or name.startswith('reads'):
        continue
    for tier, t in r['tiers'].items():
        s = t.get('vs_census') or t['vs_marginal']
        o.append('| %s | %d | %.3f | %s | %s | %.3f | %.3f | %.3f | %s | %s |' % (name, r['forms'], t['marginal'], t.get('census_paid', ''), tier, t['model'], t['top1'], t['top5'], iv(s['all']), iv(s['at25'])))
    if 'control' in r:
        o.append('| %s | | | | shuffled | | | | %s | %s |' % (name, iv(r['control']['all']), iv(r['control']['at25'])))
o.append('')
o.append('Saved is against the census part for the two component rows and against the fit marginal for the rest.')
o.append('')
o.append('## Read sets')
o.append('')
o.append('| Target | Reads | Tier | Marginal per read | Model per read | Top-1 | Top-5 | Bag saved per form, 25 bits or more | Gamma | Paid on relation picks | Tilt saved, all forms | Tilt saved, 25 bits or more |')
o.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
for name, r in d['targets'].items():
    if name.startswith('reads'):
        for tier, t in r['tiers'].items():
            o.append('| %s | %d | %s | %.3f | %.3f | %.3f | %.3f | %s | %s | %.2f | %s | %s |' % (name, r['reads'], tier, t['marginal_per_read'], t['model_per_read'], t['top1'], t['top5'], iv(t['bag_vs_marginal']['at25']), t['gamma'], t['paid_rel_picks'], iv(t['tilt_vs_census']['all']), iv(t['tilt_vs_census']['at25'])))
o.append('')
o.append('## Component and relation picks on one census walk')
o.append('')
o.append('| Tier | Saved, all forms | Saved, 25 bits or more | Forms over 25 | Taken under 25 | Tasks under 25, before | After |')
o.append('|---|---|---|---|---|---|---|')
for tier, t in d['t1_census_unit'].items():
    if tier != 'control_tilt':
        o.append('| %s | %s | %s | %d | %d | %d | %d |' % (tier, iv(t['saved']['all']), iv(t['saved']['at25']), t['forms_over'], t['forms_taken_under'], t['tasks_under_before'], t['tasks_under_after']))
c = d['t1_census_unit']['control_tilt']
o.append('| shuffled, tilt only | %s | %s | | | | |' % (iv(c['all']), iv(c['at25'])))
o.append('')
o.append('## Share of the saving at forms of 25 bits or more')
o.append('')
for k, v in d['shares'].items():
    o.append('- %s: need facts alone %.3f, found set alone %.3f, both %.3f; need facts add %s of both.' % (k, v['need'], v['found'], v['need_and_found'], v['share_need_added']))
o.append('')
o.append('## Pool gap: log2 of gold\'s marginal over the pool\'s share, in the kind')
o.append('')
for k, v in g['targets'].items():
    o.append('- %s: all forms %s, 25 bits or more %s.' % (k, iv(v['all']), iv(v['at25'])))
o.append('')
o.append('## Cost per state and rows by gold source')
o.append('')
o.append('- %s' % json.dumps(d['cost']))
o.append('- T1 saved at 25 bits or more, need and found set, by source of the text: %s' % json.dumps(d['by_source']))
text = '\n'.join(o) + '\n'
open(F.R + 'read-%s.md' % split, 'w').write(text)
print(text)

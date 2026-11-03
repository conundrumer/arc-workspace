"""read-held.md from read-held.json and read-candidate-held.json. It runs no model."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(HERE + '/read-held.json'))
c = json.load(open(HERE + '/read-candidate-held.json'))
L = []
L.append('# Held read: %d forms of %d tasks, %d with census bits, %d at 25 bits or more, %d primary edges. %d content model reads and %d candidate model reads.\n' % (d['forms'], d['tasks'], d['forms_with_bits'], d['forms_25'], d['primary'], d['model_reads'], c['reads']))


def iv(x):
    return '%+.2f (%+.2f to %+.2f)' % tuple(x[:3]) if x else ''


L.append('## Target by depth, tier full, bits per primary edge, against the marginal on fit tasks\n')
L.append('| Target | Depth | Rows | Baseline bits | Conditional bits | Top-1 | Top-5 |\n|---|---|---|---|---|---|---|')
for name in ('comp INIT', 'comp DET', 'reads INIT', 'reads RULE DET', 'kind', 'cols', 'geom', 'rel'):
    t = d['targets'][name]['tiers']['full']
    for k, v in sorted(t['by_depth'].items()):
        L.append('| %s | %s | %d | %.3f | %.3f | %.3f | %.3f |' % (name, k + ('+' if k == '4' else ''), v[0], v[1], v[2], v[3], v[4]))
L.append('\n`reads` rows are per token read, so a form counts once per token. The `comp` baseline equals the census part within .01 on all rows.\n')
L.append('## Target by tier, all depths\n')
L.append('| Target | Rows | Marginal | out | body | body+cols, full | open | Control saved, all | Saved full, all forms | Saved full, 25 bits or more |\n|---|---|---|---|---|---|---|---|---|---|')
for name in ('comp INIT', 'comp DET', 'kind', 'cols', 'geom', 'rel'):
    t = d['targets'][name]
    x = t['tiers']
    a = x['full'].get('vs_census') or x['full']['vs_marginal']
    L.append('| %s | %d | %.3f | %.3f | %.3f | %.3f | %.3f | %s | %s | %s |' % (name, t['forms'], x['full']['marginal'], x['out']['model'], x['body']['model'], x['full']['model'], x['open']['model'], iv(t['control']['all']), iv(a['all']), iv(a['at25'])))
L.append('\n## Component and relation picks on one census walk, primary number\n')
L.append('| Tier | Saved, all forms | Saved, 25 bits or more | Forms over 25 | Taken under 25 | Tasks under 25, before | After |\n|---|---|---|---|---|---|---|')
J = d['census_unit']
for t in ('out', 'body', 'body+cols', 'full', 'open', 'control'):
    x = J[t]
    L.append('| %s | %s | %s | %d | %d | %d | %d |' % (t, iv(x['saved']['all']), iv(x['saved']['at25']), x['forms_over'], x['forms_taken_under'], x['tasks_under_before'], x['tasks_under_after']))
L.append('\n`body+cols` and `full` hold the same keys. `control` is the relation tilt only, with labels shuffled.\n')
L.append('## Tier full by depth and by kind, saved bits\n')
L.append('| Slice | All forms | Forms | 25 bits or more | Forms |\n|---|---|---|---|---|')
for k in (1, 2, 3, 4):
    x = J['full']['depth %d' % k]
    L.append('| depth %d%s | %s | %d | %s | %s |' % (k, '+' if k == 4 else '', iv(x['all']), x['all'][3], iv(x['at25']), x['at25'][3] if x['at25'] else 0))
for k, x in J['full']['by kind'].items():
    L.append('| %s | %s | %d | %s | %s |' % (k, iv(x['all']), x['all'][3], iv(x['at25']), x['at25'][3] if x['at25'] else 0))
L.append('\n## Relation tilt alone\n')
L.append('| Target | Tier | Gamma | Paid on relation picks | Saved, all forms | Saved, 25 bits or more |\n|---|---|---|---|---|---|')
for name in ('reads RULE DET', 'reads INIT'):
    for tier, x in d['targets'][name]['tiers'].items():
        L.append('| %s | %s | %s | %.2f | %s | %s |' % (name, tier, x['gamma'], x['paid_rel_picks'], iv(x['tilt']['all']), iv(x['tilt']['at25'])))
L.append('\n## Which table: bits to name the read table among the candidates\n')
L.append('| Arm | Edges | Candidates, mean | Uniform | Model | Top-1 | Top-5 | Saved |\n|---|---|---|---|---|---|---|---|')
for a, x in c['arms'].items():
    L.append('| %s | %d | %.1f | %.3f | %.3f | %.3f | %.3f | %s |' % (a, x['edges'], x['cands_mean'], x['uniform'], x['model'], x['top1'], x['top5'], iv(x['saved'])))
L.append('\n| Arm | Depth | Edges | Uniform | Model | Top-1 | Top-5 |\n|---|---|---|---|---|---|---|')
for a, x in c['arms'].items():
    for k, v in sorted(x['by_depth'].items()):
        L.append('| %s | %s | %d | %.3f | %.3f | %.3f | %.3f |' % (a, k, v[0], v[1], v[2], v[3], v[4]))
L.append('\n## Candidate tilt on the census walk\n')
L.append('The tilt moves weight among derived options only, at picks where gold reads a derived relation. It acts at the reader, not at the read form.\n')
L.append('| Arm | Gamma | Saved, all forms | Saved, 25 bits or more | Taken under 25 |\n|---|---|---|---|---|')
for a, x in c['tilt'].items():
    L.append('| %s | %s | %s | %s | %s |' % (a, x['gamma'], iv(x['all']), iv(x['at25']), x.get('forms_taken_under')))
L.append('\n## Cost\n')
L.append('- ' + json.dumps(c['cost']))
open(HERE + '/read-held.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))

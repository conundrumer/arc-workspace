#!/usr/bin/env python
"""Tables of the final reads, from read-*.json. Writes summary.md and summary.json."""
import json
import os
import sys

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-order-free-per-relation-heldout37')
import features_ofree_lib as L  # noqa: E402

CL = ('derived', 'lib', 'fact', 'macro', 'NOT', 'comparison')


def rd(n):
    return json.load(open(L.ME + 'read-%s.json' % n))


def ci(x):
    return '%+.3f (%+.3f to %+.3f)' % tuple(x)


def passing(r):
    out = [k for k in r['keys_table'] if (k['tasks'] >= 8 or k['rows'] >= 50) and k['net'] >= 1]
    return out


def main():
    out = []
    names = [('rule-dag', 'Primary: other atoms as a set, their count, join structure'), ('rule-dag-control', 'Primary on shuffled labels'), ('rule-scope', 'Scope only, no atom of the body'), ('rule-set', 'Other atoms as a set and their count'), ('rule-open', 'Primary plus open labels and unread forms'), ('rule-order', 'Primary plus written order'), ('rule-subset', 'A random subset of the other atoms'), ('rule-prefix', 'Atoms written before, as a set'), ('rule-prefix-order', 'Atoms written before, plus index and last head')]
    R = {n: rd(n) for n, _ in names}
    out.append('# Read on the 37 held tasks\n\nRULE atoms, bits saved per left-out atom against the marginal among the options.\n')
    out.append('| Model | Atoms | Baseline bits | Saved | Keys passing net 1 bit |\n|---|---|---|---|---|')
    for n, t in names:
        a = R[n]['atoms']['all']
        p = passing(R[n])
        out.append('| %s | %d | %.3f | %s | %d |' % (t, a['n'], a['base'], ci(a['saved']), len(p)))
    out.append('\nBy class, primary and the same with order:\n')
    out.append('| Class | Atoms | Baseline | Saved, primary | Saved, with order | Saved, scope only |\n|---|---|---|---|---|---|')
    for c in CL:
        a, b, s = R['rule-dag']['atoms'].get(c), R['rule-order']['atoms'].get(c), R['rule-scope']['atoms'].get(c)
        out.append('| %s | %d | %.3f | %s | %s | %s |' % (c, a['n'], a['base'], ci(a['saved']), ci(b['saved']), ci(s['saved'])))
    a = R['rule-dag']['inside_not']['all']
    out.append('\nThe relation inside a NOT, a further pick not counted above: %d picks, baseline %.3f, saved %s.\n' % (a['n'], a['base'], ci(a['saved'])))
    g0, g1, g2 = R['rule-dag']['atoms']['all']['saved'][0], R['rule-order']['atoms']['all']['saved'][0], R['rule-scope']['atoms']['all']['saved'][0]
    p0, p1, p2 = R['rule-subset']['atoms']['all']['saved'][0], R['rule-prefix']['atoms']['all']['saved'][0], R['rule-prefix-order']['atoms']['all']['saved'][0]
    out.append('Written order, on the same rows:\n')
    out.append('- All other atoms: %.3f with no order, %.3f with it. Order adds %.3f, %.0f%% of the larger gain.' % (g0, g1, g1 - g0, 100 * (g1 - g0) / g1))
    out.append('- Same context sizes: %.3f for a random subset, %.3f for the atoms written before, %.3f with index and last head. Order adds %.3f, %.0f%% of the larger gain.' % (p0, p1, p2, p2 - p0, 100 * (p2 - p0) / p2))
    out.append('\nBody over scope, primary: %.3f.\n' % (g0 - g2))
    for g, ctl in (('init-dag', 'init-dag-control'), ('det-dag', 'det-dag-control')):
        r, c = rd(g), rd(ctl)
        a = r['atoms']['all']
        sc = rd(g.split('-')[0] + '-scope')['atoms']['all']
        out.append('## %s\n\n%d atoms on %d tasks, baseline %.3f, saved %s, scope and slot facts alone %s, control %s. Keys passing net 1 bit: %s.\n' % (g.split('-')[0].upper(), a['n'], a['tasks'], a['base'], ci(a['saved']), ci(sc['saved']), ci(c['atoms']['all']['saved']), ', '.join(k['key'] for k in passing(r)) or 'none'))
        if 'key_place' in r:
            out.append('Key bodies: %d atoms, baseline %.3f, saved %s. Port bodies: %d atoms, baseline %.3f, saved %s.\n' % (r['key_place']['n'], r['key_place']['base'], ci(r['key_place']['saved']), r['port_place']['n'], r['port_place']['base'], ci(r['port_place']['saved'])))
        out.append('| Class | Atoms | Baseline | Saved |\n|---|---|---|---|')
        for x in CL:
            b = r['atoms'].get(x)
            if b:
                out.append('| %s | %d | %.3f | %s |' % (x, b['n'], b['base'], ci(b['saved'])))
        out.append('')
    r = R['rule-dag']
    n = r['atoms']['all']['n']
    p = passing(r)
    out.append('## Keys of the primary that pass 1 bit net\n\nA key is read where it has 8 held tasks or 50 held atoms. %d keys are read. %d atoms of %d have a passing key as their label, a share of %.3f.\n' % (sum(1 for k in r['keys_table'] if k['tasks'] >= 8 or k['rows'] >= 50), sum(k['rows'] for k in p), n, sum(k['rows'] for k in p) / n))
    out.append('| Key | Atoms | Tasks | Saved at label | Net per label | Net 95% | Net total bits |\n|---|---|---|---|---|---|---|')
    for k in sorted(p, key=lambda k: -k['net_total']):
        out.append('| %s | %d | %d | %+.2f | %+.2f | %+.2f to %+.2f | %+.1f |' % (k['key'], k['rows'], k['tasks'], k['saved_at_label'], k['net'], k['net_lo'], k['net_hi'], k['net_total']))
    c = rd('rule-dag-control')
    out.append('\nThe control passes %d keys: %s.\n' % (len(passing(c)), ', '.join(k['key'] for k in passing(c)) or 'none'))
    txt = '\n'.join(out) + '\n'
    open(L.ME + 'summary.md', 'w').write(txt)
    print(txt)


if __name__ == '__main__':
    main()

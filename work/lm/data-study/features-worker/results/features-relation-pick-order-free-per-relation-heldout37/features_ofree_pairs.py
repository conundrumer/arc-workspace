#!/usr/bin/env python
"""What carries the keys of the primary: pairs and sets as rates a person can check. Writes pairs.md.

"Rate" is labels at the key over the baseline's mass there. Over 1 means the marginal gives the key too little. Held rows are counted once here, a line in the ledger.
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_ofree_lib as L  # noqa: E402

NAMED = [('compose', 'perp'), ('perp', 'compose'), ('neighbor', 'dir8_elem'), ('dir8_elem', 'neighbor'), ('inside', 'BoundingBox.box'), ('BoundingBox.box', 'inside')]


def words(f):
    fam, _, v = f.partition(':')
    w = {'in': '`%s` is another atom', 'neg': '`%s` is under NOT in the body', 'near': '`%s` is elsewhere in the body', 'sc': '`%s` is in the scope', 'scr': 'a scope form reads `%s`', 'inb': 'an atom reads a form that reads `%s`', 'col': 'an atom names column `%s`', 'join': 'two atoms share a label: `%s`', 'under': 'the atom sits under %s', 'size': 'at least %s other atoms', 'scf': '%s is in the scope'}.get(fam)
    return w % v if w else f


class Masses:
    """Each row's baseline share of a key, and whether the label is at it."""

    def __init__(self, D, base):
        self.D = D
        lo = base.fill(D)
        ll = base.loglib[D.neg.astype(int)].copy()
        ll[D.mask_ops] = -np.inf
        self.ql = np.exp(ll)
        self.qo = np.exp(lo)
        self.tot = self.ql.sum(1) + np.bincount(D.orow, self.qo, D.n)
        self.toks = np.array([o['tok'] for o in D.oinfo])

    def key(self, k):
        D = self.D
        y = D.keys == k
        if k in D.lix:
            return y, self.ql[:, D.lix[k]] / self.tot
        return y, np.bincount(D.orow, self.qo * (self.toks == k), D.n) / self.tot


def rate(y, q, m):
    return float(y[m].sum() / max(q[m].sum(), 1e-9))


def written_share(recs, a, b):
    """Of RULE rows with label a and b among the other atoms: rows, and the share with b written before a."""
    n = w = 0
    for rc in recs:
        for r in rc['rows']:
            if r['place'] != 'RULE' or r['key'] != a or 'not' in r['under']:
                continue
            ix = [i for i, c in enumerate(r['ctx']) if c['t'] == b and c['w'] == 'in']
            if ix:
                n += 1
                w += any(i in r['written']['before'] for i in ix)
    return n, w / max(n, 1)


def main():
    t0 = time.time()
    recs = L.load('fit')
    libs = L.lib_vocab(recs)
    D = L.Data(recs, 'RULE', libs, 'dag')
    base = L.Baseline(D, np.arange(D.n))
    hrecs = L.load('held')
    Dh = L.Data(hrecs, 'RULE', libs, 'dag', like=D)
    if not any(json.loads(x)['name'] == 'pairs-table' for x in open(L.ME + 'held-reads.jsonl')):
        with open(L.ME + 'held-reads.jsonl', 'a') as f:
            f.write(json.dumps(dict(name='pairs-table', group='RULE', arm='rates of named pairs and keys', tier='', lam=0, control=False, time=time.strftime('%Y-%m-%dT%H:%M:%S'))) + '\n')
    M, Mh = Masses(D, base), Masses(Dh, base)
    z = np.load(L.ME + 'models/rule-dag.npz')
    names = z['names'].tolist()
    fsel, facts = z['fsel'], z['facts'].tolist()
    nk, nf = len(names), len(fsel)
    W = z['theta'][:nk * nf].reshape(nk, nf)
    top, toph = ~D.neg, ~Dh.neg
    Fc = D.F.tocsc()
    Fh = Dh.F.tocsc()
    fid = D.fv  # a fact's id is per process, since a fact set has no fixed order: look a fact up by name

    def col(Fm, n):
        j = fid.get(n)
        if j is None or j >= Fm.shape[1]:
            return np.zeros(Fm.shape[0], bool)
        return np.asarray(Fm[:, j].todense()).ravel() > 0

    out = ['# Pairs and sets that carry the keys\n', 'Rates are labels at the key over the marginal\'s mass there, on RULE atoms. "Fit" is the fit tasks, "held" the 37 held tasks. A pair stands as a set where the first rate is over 1 and over the second, in both directions. "Written before" is the share of rows holding both where the second relation is written before the left-out one.\n']
    out.append('| Left out | Other atom | Fit: rows with it, labels | Fit rate with it | Fit rate without | Held: rows with it, labels | Held rate with it | Held rate without | Written before, fit |\n|---|---|---|---|---|---|---|---|---|')
    for a, b in NAMED:
        y, q = M.key(a)
        yh, qh = Mh.key(a)
        f = col(Fc, 'in:' + b) & top
        fh = col(Fh, 'in:' + b) & toph
        n, w = written_share(recs, a, b)
        out.append('| `%s` | `%s` | %d, %d | %.2f | %.2f | %d, %d | %.2f | %.2f | %.2f of %d |' % (a, b, f.sum(), y[f].sum(), rate(y, q, f), rate(y, q, top & ~f), fh.sum(), yh[fh].sum(), rate(yh, qh, fh), rate(yh, qh, toph & ~fh), w, n))
    out.append('')
    r = json.load(open(L.ME + 'read-rule-dag.json'))
    keep = [k for k in r['keys_table'] if (k['tasks'] >= 8 or k['rows'] >= 50) and k['net'] >= 1]
    fnames = [facts[j] for j in fsel.tolist()]
    for k in sorted(keep, key=lambda k: -k['net_total']):
        name = k['key']
        c = names.index('L:' + name) if 'L:' + name in names else names.index('T:' + name) if 'T:' + name in names else None
        if c is None:
            continue
        y, q = M.key(name)
        yh, qh = Mh.key(name)
        o = np.argsort(-W[c])
        rows = []
        for j in o.tolist():
            n = fnames[j]
            if W[c, j] <= 0 or n.split(':')[0] in ('place',):
                continue
            f = col(Fc, n) & top
            if y[f].sum() < 8:
                continue
            fh = col(Fh, n) & toph
            rows.append('| raises | %s | %d | %.2f | %.2f | %d | %.2f |' % (words(n), y[f].sum(), rate(y, q, f), rate(y, q, top & ~f), yh[fh].sum(), rate(yh, qh, fh) if fh.any() else float('nan')))
            if len(rows) == 5:
                break
        low = 0
        for j in o[::-1].tolist():
            n = fnames[j]
            if W[c, j] >= 0:
                continue
            f = col(Fc, n) & top
            if q[f].sum() < 8:
                continue
            fh = col(Fh, n) & toph
            rows.append('| lowers | %s | %d | %.2f | %.2f | %d | %.2f |' % (words(n), y[f].sum(), rate(y, q, f), rate(y, q, top & ~f), yh[fh].sum(), rate(yh, qh, fh) if fh.any() else float('nan')))
            low += 1
            if low == 2:
                break
        out.append('## `%s`\n\nHeld: %d atoms on %d tasks, net %+.2f per label (%+.2f to %+.2f).\n' % (name, k['rows'], k['tasks'], k['net'], k['net_lo'], k['net_hi']))
        out.append('| Direction | Fact | Fit labels with it | Fit rate with it | Fit rate without | Held labels with it | Held rate with it |\n|---|---|---|---|---|---|---|')
        out += rows
        out.append('')
    open(L.ME + 'pairs.md', 'w').write('\n'.join(out))
    print('\n'.join(out))
    print('%.0f s' % (time.time() - t0))


if __name__ == '__main__':
    main()

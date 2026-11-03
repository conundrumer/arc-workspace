#!/usr/bin/env python
"""Arrays of the relation picks of a walk, with the keys of each option. Rebuilds the rank read's rows with its own matrix and its cross-fit swap, and adds keys and facts.

  python features_perrel_data.py [--crossfit] NAME SCOPE WALK_FILE...     writes scratch/data-NAME.npz

SCOPE is before or parents: the context of the walk, which sets the map from a token to its form. A key and a fact read only what the search has at the pick: the text of the scope forms, the prefix, the options. `gold` holds gold's index for the fit and the tables alone.
"""
import collections
import json
import os
import re
import sys
import time

import numpy as np

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-models-heldout37')
import features_perrel_keys as K  # noqa: E402
import features_perrel_ports as PT  # noqa: E402
import features_rel_data as FD  # noqa: E402

ME = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-models-heldout37/'  # the data folder
OUT = ME + 'scratch/'
TYPES = FD.TYPES
COLS = 5
FORM = ('recency', 'recency_frac', 'form_atoms', 'form_not', 'form_or', 'kept_reads')  # form facts of a derived option, and the count of scope forms that read the option's relation
ATOMH = re.compile(r'\((&r\d+(?:\.\w+)?|[a-z_]\w*) \(:')


class Vocab:
    def __init__(self):
        self.ix = {}

    def __call__(self, s):
        return self.ix.setdefault(s, len(self.ix))

    def list(self):
        return sorted(self.ix, key=self.ix.get)


def registry_ports():
    """{(component, index): output's name}, in the registry's order of outputs."""
    txt = re.sub(r';[^\n]*', '', open('/Users/davidlu/code/arc-workspace/engine/lib/registry.sexpr', encoding='utf8').read())
    out = {}
    for m in re.finditer(r'\(component (\w+)', txt):
        i = txt.find('(outputs', m.end())
        nxt = txt.find('(component ', m.end())
        if i < 0 or (nxt > 0 and i > nxt):
            continue
        depth, j, names = 0, i, []
        while True:
            c = txt[j]
            if c == '(':
                depth += 1
                if depth == 2:
                    names.append(re.match(r'\(([\w]+)', txt[j:])[1])
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        for n, x in enumerate(names):
            out[m[1], n] = x
    return out


class Keys:
    """The keys of a pick's options and prefix, for one task's forms."""

    def __init__(self, sections, ports):
        self.sections, self.ports = sections, ports
        self.cache = {}

    def lib(self, name, kind):
        if kind in ('NOT', 'CMP'):
            return 'op', 'op:' + name, 'op:' + name
        s = self.sections.get(name)
        if kind == 'fact relation':
            return 'facts', 'fact:' + name, name
        if s is None:
            s = 'macro' if kind == 'relation macro' else 'lib-other'
        return 'lib-' + s, 'lib:' + name, name

    def derived(self, f, sl, tok):
        t = int(tok[2:])
        if t not in sl:
            return 'derived-unknown', 'derived-unknown', 'derived-unknown'
        L, j = sl[t]
        return f.key(L, j, self.ports)

    def text_head(self, f, h):
        """The relation key of a head in a form's written text, where &rN is the written name."""
        if not h.startswith('&'):
            return h
        base, _, port = h.partition('.')
        L = f.head.get(base)
        if L is None:
            return 'derived-unknown'
        kind, _h, comp = f.info[L]
        if kind in ('INIT', 'RIGID_DET'):
            return comp + '.' + (port if kind == 'INIT' else 'r')
        return f.key(L, 0, self.ports)[2]

    def head(self, f, sl, text):
        """The relation key of a prefix atom's head."""
        m = FD.HEAD.match(text)
        if m is None:
            return None
        h = m[1]
        if not h.startswith('&'):
            return h
        base, _, port = h.partition('.')
        t = int(base[2:])
        if t not in sl:
            return 'derived-unknown'
        L, j = sl[t]
        kind, _h, comp = f.info[L]
        if kind in ('INIT', 'RIGID_DET'):
            return comp + '.' + (port if kind == 'INIT' else 'r')
        return f.key(L, j, self.ports)[2]


def main():
    swap = None
    if sys.argv[1] == '--crossfit':
        sys.argv.pop(1)
        swap = FD.Swap()
    name, mode, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
    held = {x['task']: x['gold_sexp'] for x in json.load(open(PT.HELD))} if name.startswith('held') else None
    keys = Keys(K.lib_sections(), registry_ports())
    fam, comp, rel, heads = Vocab(), Vocab(), Vocab(), Vocab()
    S, Co, X, starts, gold, fi, ci, ri, last = [], [], [], [0], [], [], [], [], []
    ph_p, ph_k, sc_p, sc_k, scnt = [], [], [], [], []
    meta = {k: [] for k in ('task', 'line', 'ord', 'phase', 'k', 'gold_kind', 'own', 'gold_dead', 'q_bits', 'orf', 'nopts', 'where')}
    forms, buf, F, scopeinfo = [], [], {}, {}
    t0 = time.time()
    for d in FD.records(paths):
        if d['rec'] != 'form':
            buf.append(d)
            continue
        forms.append({k: d[k] for k in ('task', 'line', 'natoms', 'total', 'bad', 'dead', 'error', 'cpu', 'content_cpu', 'picks', 'aligned', 'orf')})
        if d['error'] or d['dead'] or d['bad'] or not d['aligned']:  # a valid form, as the census counts one
            buf = []
            continue
        for p in buf:
            task = p['task']
            if task not in F:
                F[task] = K.Forms(PT.gold_lines(task, held))
            f = F[task]
            kept = K.parents(f.lines, p['line']) if mode == 'parents' else list(range(p['line']))
            sl, _n = f.slots(kept)
            fkey = (task, p['line'])
            if fkey not in scopeinfo:
                rd = collections.Counter()
                for L in kept:
                    for h in set(ATOMH.findall(f.lines[L])):
                        rd[keys.text_head(f, h)] += 1
                fl = [L for L in kept if L in f.num]
                scopeinfo[fkey] = (rd, {L: i for i, L in enumerate(fl)}, len(fl), [f.key(L, 0, keys.ports)[1] for L in fl[-2:]])
            rd, order, nf, prevs = scopeinfo[fkey]
            if swap is not None:
                swap.apply(p)
            a, b, tok, la = FD.matrix(p)
            n = len(a)
            pid = len(gold)
            S.append(a), Co.append(b), starts.append(starts[-1] + n)
            g = p['gold_idx']
            gold.append(-1 if g is None else g)
            seen = set()
            scope = p['scope']
            cnt = {t: scope.count(t) for t in set(scope)}
            x = np.full((n, COLS), -1.0, np.float32)
            x2 = np.full((n, len(FORM)), -1.0, np.float32)
            for j, (o, r) in enumerate(zip(p['opts'], p['rowopts'])):
                nm, kd = o[0], o[1]
                k3 = keys.derived(f, sl, nm) if kd == 'relation' else keys.lib(nm, kd)
                fi.append(fam(k3[0])), ci.append(comp(k3[1])), ri.append(rel(k3[2]))
                x2[j, 5] = rd.get(k3[2], 0)
                if kd == 'relation':
                    t_ = int(nm[2:])
                    if t_ in sl:
                        L = sl[t_][0]
                        back = nf - 1 - order[L]
                        tx = f.lines[L]
                        x2[j, :5] = back, back / max(nf - 1, 1), len(ATOMH.findall(tx)), '(NOT' in tx, '(OR' in tx
                    if k3[1] not in seen:
                        seen.add(k3[1])
                        sc_p.append(pid), sc_k.append(heads('scope:' + k3[1]))
                for c, t in enumerate((r.get('types') or [])[:COLS]):
                    x[j, c] = cnt.get(t, 0)
            X.append(np.hstack([x, x2]))
            for i_, h_ in enumerate(reversed(prevs)):
                sc_p.append(pid), sc_k.append(heads('prevform%d:%s' % (i_ + 1, h_)))
            for h_ in rd:
                sc_p.append(pid), sc_k.append(heads('scopereads:' + h_))
            hs = [keys.head(f, sl, a_) for a_ in p.get('prefix') or []]
            hs = [h for h in hs if h]
            for h in set(hs):
                ph_p.append(pid), ph_k.append(heads('prefix:' + h))
            last.append(heads('last:' + (hs[-1] if hs else 'none')))
            scnt.append([cnt.get(t, 0) for t in TYPES])
            for k, v in dict(task=task, line=p['line'], ord=p['ord'], phase=p['phase'], k=p['k'], gold_kind=p['gold_kind'], own=p['own'], gold_dead=bool(g is None or p['opts'][g][3]), q_bits=p['q_bits'], orf=p['orf'], nopts=n, where=p.get('where') or '').items():
                meta[k].append(v)
        buf = []
        if len(forms) % 500 == 0:
            print('%d forms %d picks %.0fs' % (len(forms), len(gold), time.time() - t0), flush=True)
    np.savez(OUT + 'data-%s.npz' % name, S=np.vstack(S), C=np.vstack(Co).astype(np.float32), X=np.vstack(X), starts=np.array(starts), gold=np.array(gold), fam=np.array(fi, np.int32), comp=np.array(ci, np.int32), rel=np.array(ri, np.int32), last=np.array(last, np.int32),
             ph_p=np.array(ph_p, np.int32), ph_k=np.array(ph_k, np.int32), sc_p=np.array(sc_p, np.int32), sc_k=np.array(sc_k, np.int32), scnt=np.array(scnt, np.float32),
             v_fam=np.array(fam.list()), v_comp=np.array(comp.list()), v_rel=np.array(rel.list()), v_heads=np.array(heads.list()), forms=np.array(json.dumps(forms)), **{'m_' + k: np.array(v) for k, v in meta.items()})
    print(name, len(gold), 'picks', starts[-1], 'option rows', len(forms), 'forms, %.0fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()

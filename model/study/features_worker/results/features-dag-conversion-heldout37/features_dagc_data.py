#!/usr/bin/env python
"""Arrays of the relation picks of the walks of a part, in the schema of features_ps_data.py, for the DAG conversion (item 8).

  features_dagc_env.sh 1 features_dagc_data.py NAME POINTS WALKS... [--kinds RULE] [--seconds S] [--assemble-only]    writes scratch/data-NAME.npz
  features_dagc_env.sh 1 features_dagc_data.py --bits NAME POINTS WALKS...                                                writes scratch/bits-NAME.npz: the mean live (or any steer) bits of each pick key

WALKS are walks/PART-STEERS-KofN.jsonl.zst files (globs allowed). The script streams each file, skips the walks that a chunk already holds, and reads whatever frames exist now (a frame that the walker has not finished is ignored). A rerun resumes:
the chunks of finished work stand in scratch/chunks-NAME/, one per (file, range of walks), and the arrays are assembled from all chunks at the end.

What it does, against features_ps_data.py:
  - FD.matrix keeps the columns of ALLOWED_COLUMNS alone (features_dagc_matrix.py), with `dsize` and `d_depth` where `k` and `ord` stood. FORM drops `recency`, `recency_frac`, `kept_reads`. No `prevform*`, `scopereads:*` or `last` array.
  - A derived option's key comes from its `D:<content key>.<port>` name: the form of the scope with that content key, and the key of features_dagc_keys.py (the rarest head of its body, in place of the first atom).
  - `prefix:` tokens come from D (the heads of the atoms of the sorted `downset`). The tokens of pick_facts at tier `dag` (features_dagc_facts) join them. `scope:` tokens stay.
  - Picks with equal pick keys (part, task, form, scope_id, phase, atom, downset id) become one pick. Its weight `w` is its count of walks over the point's count of finished walks. A point is one form on one scope.
  - check_columns and check_tokens run before the file is written, and the file has a `checked` field. The fit refuses a file without it.
  - A pick whose key meets different options or weights in two walks keeps the first. The count of such keys is in `conflicts`.
"""
import argparse
import collections
import glob
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import zstandard

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')
import features_dag_order as D  # noqa: E402
import features_dagc_facts as F  # noqa: E402
import features_dagc_keys as K  # noqa: E402
import features_dagc_lib as L  # noqa: E402
import features_dagc_matrix as M  # noqa: E402
import features_dagc_walk as W  # noqa: E402
import features_ofree_text as T  # noqa: E402

ME = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37/'  # the data folder
OUT = ME + 'scratch/'
REL_KINDS = ('lib relation', 'relation macro', 'fact relation', 'relation')


def pkey_of(part, d):
    down = D.short('|'.join(d['downset']), 12)
    s = '|'.join((part, d['task'], d['form'], d['scope_id'], d['phase'], d['atom'], down))
    return int.from_bytes(hashlib.sha1(s.encode()).digest()[:8], 'big', signed=True)


def gid_of(point_line):
    return int(point_line)


def walk_frames(path, skip=0):
    """(pick rows, form row) of each finished walk of a zst file, after `skip` walks. A frame cut short by a running writer ends the stream."""
    if not os.path.exists(path):
        return
    n, buf = 0, []
    with open(path, 'rb') as f:
        try:
            for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
                if not line.endswith('\n'):
                    return
                if line.startswith('{"rec": "form"'):
                    n += 1
                    if n > skip:
                        yield buf, json.loads(line)
                    buf = []
                elif n >= skip:
                    buf.append(line)
        except zstandard.ZstdError:
            return


class Vocab:
    def __init__(self):
        self.ix = {}

    def __call__(self, s):
        return self.ix.setdefault(s, len(self.ix))

    def list(self):
        return sorted(self.ix, key=self.ix.get)


class Ctx:
    """The caches of one process: scope keys, programs, grid facts, orders."""

    def __init__(self, points_path, part):
        self.pts = {}
        for x in open(points_path):
            p = json.loads(x)
            self.pts[p['line']] = p
        self.part = part
        source = W.PARTS[part][0] if part in W.PARTS else 'held'
        self.orders = W.load_orders(source)
        self.reg = T.Registry()
        self.sections, self.ports = K.lib_sections(), M.registry_ports()
        self.grid = json.load(open(OUT + 'grid-facts.json'))
        self.gnames = json.load(open(OUT + 'grid-facts-names.json'))
        self.scopes = {}
        self.comp = {}

    def scope(self, p):
        k = (p['task'], hash(tuple(sorted(p['scope']))))  # not scope_id: two points whose scopes differ in the names of equal forms share a scope_id
        got = self.scopes.get(k)
        if got is None:
            if len(self.scopes) > 64:
                self.scopes.clear()
            sk = K.ScopeKeys(p['scope'], self.sections, self.ports)
            prog = F.program_of(p['scope'], self.reg)
            got = self.scopes[k] = (sk, prog, F.scope_record(prog), {})
        return got

    def component(self, p):
        r = self.orders.get((p['task'], p['line_id']))
        if r is None or p['kind'] != 'INIT':
            return ''
        return D.parse(r['orders'][0])[2]


def pick_dict(d, p, comp, prog):
    """The pick of features_dagc_facts.pick_facts from a row: its place and under from the atom's path alone (never its text), the atoms of D with `in` or `near`, and the mode depth."""
    path = d['atom'].split('|', 1)[0]
    root = path.split('/')[0]
    kind = p['kind']
    port = ''
    if root.startswith('port:'):
        port = '%s.%s' % (comp, root[5:]) if comp else root[5:]
    place = kind if root == 'top' else 'key' if root == 'key' else 'port' if root.startswith('port:') else root
    under = sorted(({'or'} if '/or' in path else set()) | ({'all'} if '/all' in path else set()) | ({'not'} if d['phase'] == 'root2' else set()))
    atoms = []
    for i in d['downset']:
        pa, txt = i.split('|', 1)
        atoms.append((D.parse(K.rn(txt)), 'in' if pa == path else 'near'))
    return dict(place=place, comp=comp, port=port, under=under, atoms=atoms, d_depth=d['d_depth'])


def option_keys(d, sk):
    out = []
    for o in d['opts']:
        out.append(sk.derived(o[0]) if o[1] == 'relation' else sk.lib(o[0], o[1]))
    return out


def build_pick(d, p, cx, vocabs):
    sk, prog, rec, tokcache = cx.scope(p)
    keys = option_keys(d, sk)
    S, Cm, X, scnt = M.matrix(d, sk, keys, 'scope' in d)
    task = d['task']
    g = d['gold_idx']
    seen, sc = set(), []
    for o, k3 in zip(d['opts'], keys):
        if o[1] == 'relation' and k3[1] not in seen:
            seen.add(k3[1])
            sc.append('scope:' + k3[1])
    down = [x.split('|', 1)[1] for x in d['downset']]
    hs = [sk.atom_head(K.rn(t)) for t in down]
    ph = {'prefix:' + h for h in hs if h}
    pk = pick_dict(d, p, cx.component(p), prog)
    pk['ctx'] = F.ctx_of(pk['atoms'], prog)
    ph |= F.pick_facts(pk, prog, 'dag', rec)
    toks = [r['tok'] if o[1] != 'relation' else '&D' for o, r in zip(d['opts'], d['rowopts'])]
    gk = d['opts'][g][1] if g is not None else 'none'
    return dict(S=S, C=Cm, X=X, scnt=scnt, keys=keys, sc=sc, ph=sorted(ph), toks=toks, gold=-1 if g is None else g,
                meta=dict(task=task, dsize=d['dsize'], phase=d['phase'], d_depth=d['d_depth'], gold_kind=gk, own=bool(g is not None and d['opts'][g][4] and gk in REL_KINDS), gold_dead=bool(g is None or d['opts'][g][3]), q_bits=d['q_bits'],
                          nopts=len(d['opts']), place=d['place'], form=d['form'], kind=d['kind'], line_id=d['line_id'], scope_id=d['scope_id']),
                sig=hash(tuple((o[0], round(o[2], 5), o[3]) for o in d['opts'])), sig_w=hash(tuple((o[0], round(o[2], 5)) for o in d['opts'])))


def process(path, skip, cx, kinds, part, seconds, t0):
    """Chunk of the walks of `path` after the first `skip`. Returns (chunk dict, walks read)."""
    picks, order, groups, forms, conflicts = {}, [], collections.Counter(), [], collections.Counter()
    nread = 0
    for rows, fm in walk_frames(path, skip):
        if seconds and time.time() - t0 > seconds:
            break
        nread += 1
        forms.append({k: fm.get(k) for k in ('task', 'point', 'line_id', 'kind', 'form', 'order_idx', 'ok', 'drop', 'total', 'parts', 'seconds', 'scope_id', 'nscope')})
        if not fm['ok']:
            continue
        p = cx.pts[fm['point']]
        gid = gid_of(fm['point'])
        groups[gid] += 1
        if fm['kind'] not in kinds:
            continue
        seen = set()
        for line in rows:
            d = json.loads(line)
            pk = pkey_of(part, d)
            if pk in seen:
                continue  # a key twice in one walk: an atom takes one pick per phase
            seen.add(pk)
            pk = (pk, gid)  # equal forms on equal scope ids share a key; each point still weighs on its own walks
            if pk in picks:
                e = picks[pk]
                e['cnt'] += 1
                if e['sig'] != hash(tuple((o[0], round(o[2], 5), o[3]) for o in d['opts'])):
                    conflicts['dead_only' if e['sig_w'] == hash(tuple((o[0], round(o[2], 5)) for o in d['opts'])) else 'weights'] += 1
                continue
            e = build_pick(d, p, cx, None)
            e.update(cnt=1, gid=gid, pk=pk[0])
            picks[pk] = e
            order.append(pk)
    return dict(picks=[picks[k] for k in order], groups=dict(groups), forms=forms, conflicts=dict(conflicts), nread=nread)


def save_chunk(path, ch):
    P = ch['picks']
    vo = {k: Vocab() for k in ('fam', 'comp', 'rel', 'tok', 'tokens')}
    fi, ci, ri, ti, ph_p, ph_k, sc_p, sc_k = [], [], [], [], [], [], [], []
    for i, e in enumerate(P):
        for k3, t in zip(e['keys'], e['toks']):
            fi.append(vo['fam'](k3[0])), ci.append(vo['comp'](k3[1])), ri.append(vo['rel'](k3[2])), ti.append(vo['tok'](t))
        for h in e['ph']:
            ph_p.append(i), ph_k.append(vo['tokens'](h))
        for h in e['sc']:
            sc_p.append(i), sc_k.append(vo['tokens'](h))
    meta = collections.defaultdict(list)
    for e in P:
        for k, v in e['meta'].items():
            meta[k].append(v)
    n = len(P)
    z = dict(S=np.vstack([e['S'] for e in P]) if n else np.zeros((0, len(M.STRUCT)), np.float32), C=np.vstack([e['C'] for e in P]) if n else np.zeros((0, len(M.CONTENT)), np.float32),
             X=np.vstack([e['X'] for e in P]) if n else np.zeros((0, len(M.XCOLS)), np.float32), scnt=np.array([e['scnt'] for e in P], np.float32).reshape(n, len(M.TYPES)),
             nopts=np.array([len(e['keys']) for e in P], np.int64), gold=np.array([e['gold'] for e in P], np.int64), cnt=np.array([e['cnt'] for e in P], np.int64), gid=np.array([e['gid'] for e in P], np.int64),
             pk=np.array([e['pk'] for e in P], np.int64), fam=np.array(fi, np.int32), comp=np.array(ci, np.int32), rel=np.array(ri, np.int32), tok=np.array(ti, np.int32),
             ph_p=np.array(ph_p, np.int32), ph_k=np.array(ph_k, np.int32), sc_p=np.array(sc_p, np.int32), sc_k=np.array(sc_k, np.int32),
             v_fam=np.array(vo['fam'].list()), v_comp=np.array(vo['comp'].list()), v_rel=np.array(vo['rel'].list()), v_tok=np.array(vo['tok'].list()), v_tokens=np.array(vo['tokens'].list()),
             groups=np.array(json.dumps(ch['groups'])), forms=np.array(json.dumps(ch['forms'])), conflicts=np.array(json.dumps(ch['conflicts'])), **{'m_' + k: np.array(v) for k, v in meta.items()})
    np.savez(path, **z)


def assemble(name, chunk_paths, kinds):
    """data-NAME.npz from the chunks. Picks with the same key across chunks merge (counts add)."""
    t0 = time.time()
    V = {k: Vocab() for k in ('fam', 'comp', 'rel', 'tok', 'tokens')}
    A = collections.defaultdict(list)
    meta = collections.defaultdict(list)
    starts, seen, groups, forms, conflicts = [0], {}, collections.Counter(), [], collections.Counter()
    ph_p, ph_k, sc_p, sc_k = [], [], [], []
    npick = 0
    for cp in chunk_paths:
        z = np.load(cp, allow_pickle=False)
        groups.update({int(k): v for k, v in json.loads(str(z['groups'])).items()})
        forms += json.loads(str(z['forms']))
        conflicts.update(json.loads(str(z['conflicts'])))
        m = {k: {s: V[k](s) for s in z['v_' + k].tolist()} for k in V}
        mp = {k: np.array([V[k](s) for s in z['v_' + k].tolist()], np.int32) for k in V}
        st = np.concatenate([[0], np.cumsum(z['nopts'])])
        pks = list(zip(z['pk'].tolist(), z['gid'].tolist()))
        keep = []
        for i, k in enumerate(pks):
            if k in seen:
                A['_cnt_extra'].append((seen[k], int(z['cnt'][i])))
            else:
                seen[k] = len(seen)
                keep.append(i)
        if not keep:
            continue
        keep = np.array(keep)
        rowsel = np.concatenate([np.arange(st[i], st[i + 1]) for i in keep])
        base = len(starts) - 1
        newid = {int(i): base + j for j, i in enumerate(keep.tolist())}
        for key in ('S', 'C', 'X'):
            A[key].append(z[key][rowsel])
        for key, vk in (('fam', 'fam'), ('comp', 'comp'), ('rel', 'rel'), ('tok', 'tok')):
            A[key].append(mp[vk][z[key][rowsel]])
        A['scnt'].append(z['scnt'][keep])
        A['gold'].append(z['gold'][keep])
        A['cnt'].append(z['cnt'][keep])
        A['gid'].append(z['gid'][keep])
        A['pk'].append(z['pk'][keep])
        for j in keep.tolist():
            starts.append(starts[-1] + int(z['nopts'][j]))
        for pk_, kk_, tgt in ((z['ph_p'], z['ph_k'], (ph_p, ph_k)), (z['sc_p'], z['sc_k'], (sc_p, sc_k))):
            sel = np.isin(pk_, keep)
            tgt[0].append(np.array([newid[int(i)] for i in pk_[sel]], np.int32))
            tgt[1].append(mp['tokens'][kk_[sel]])
        for k in z.files:
            if k.startswith('m_'):
                meta[k[2:]].append(z[k][keep])
    if not A['S']:
        raise SystemExit('no picks yet in %d chunks' % len(chunk_paths))
    cnt = np.concatenate(A['cnt']).copy()
    for pos, c in A['_cnt_extra']:
        cnt[pos] += c
    gid = np.concatenate(A['gid'])
    nok = np.array([groups[int(g)] for g in gid.tolist()], np.float64)
    w = (cnt / np.maximum(nok, 1)).astype(np.float32)
    meta_c = {k: np.concatenate(v) for k, v in meta.items()}
    meta_c['line'] = gid
    meta_c['w'] = w
    names = M.names(json.load(open(OUT + 'grid-facts-names.json')))
    toks_v = V['tokens'].list()
    F.check_tokens(toks_v)
    z = dict(S=np.vstack(A['S']), C=np.vstack(A['C']), X=np.vstack(A['X']), starts=np.array(starts), gold=np.concatenate(A['gold']), w=w, cnt=cnt, nwalks=nok.astype(np.int32), pkey=np.concatenate(A['pk']),
             fam=np.concatenate(A['fam']), comp=np.concatenate(A['comp']), rel=np.concatenate(A['rel']), tok=np.concatenate(A['tok']),
             ph_p=np.concatenate(ph_p), ph_k=np.concatenate(ph_k), sc_p=np.concatenate(sc_p), sc_k=np.concatenate(sc_k), scnt=np.vstack(A['scnt']),
             v_fam=np.array(V['fam'].list()), v_comp=np.array(V['comp'].list()), v_rel=np.array(V['rel'].list()), v_tok=np.array(V['tok'].list()), v_heads=np.array(toks_v),
             forms=np.array(json.dumps(forms)), names=np.array(names), grid_names=np.array(json.load(open(OUT + 'grid-facts-names.json'))), conflicts=np.array(json.dumps(dict(conflicts))),
             checked=np.array(json.dumps(dict(columns=len(names), tokens=len(toks_v), module='features_dagc_facts', scope_in_rows=False))), kinds=np.array(sorted(kinds)),
             **{'m_' + k: v for k, v in meta_c.items()})
    np.savez(OUT + 'data-%s.npz' % name, **z)
    print('%s: %d picks (%.1f weight-picks), %d option rows, %d walks in %d points, conflicts %s, %.0fs' % (name, len(w), float(w.sum()), len(z['S']), int(cnt.sum()), len(groups), dict(conflicts), time.time() - t0), flush=True)


def bits_only(name, points_path, paths):
    """Mean q_bits per pick key over the walks that reach it, for the live read of a part."""
    part = None
    acc = {}
    for path in paths:
        for rows, fm in walk_frames(path):
            if not fm['ok']:
                continue
            part = fm['part']
            seen = set()
            for line in rows:
                d = json.loads(line)
                pk = pkey_of(part, d)
                if pk in seen:
                    continue
                seen.add(pk)
                a = acc.setdefault(pk, [0.0, 0])
                a[0] += d['q_bits']
                a[1] += 1
    ks = np.array(sorted(acc), np.int64)
    np.savez(OUT + 'bits-%s.npz' % name, pkey=ks, bits=np.array([acc[k][0] / acc[k][1] for k in ks.tolist()]), cnt=np.array([acc[k][1] for k in ks.tolist()], np.int64))
    print('%s: %d pick keys' % (name, len(ks)), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bits', action='store_true')
    ap.add_argument('--kinds', default='RULE')
    ap.add_argument('--seconds', type=float, default=None)
    ap.add_argument('--assemble-only', action='store_true')
    ap.add_argument('name')
    ap.add_argument('points')
    ap.add_argument('walks', nargs='+')
    a = ap.parse_args()
    paths = [x for p in a.walks for x in sorted(glob.glob(p))]
    if a.bits:
        return bits_only(a.name, a.points, paths)
    kinds = set(a.kinds.split(','))
    cdir = Path(OUT) / ('chunks-%s' % a.name)
    cdir.mkdir(parents=True, exist_ok=True)
    idx_path = cdir / 'index.json'
    idx = json.load(open(idx_path)) if idx_path.exists() else {}
    t0 = time.time()
    if not a.assemble_only:
        cx = None
        for path in paths:
            part = os.path.basename(path).split('-off-')[0].split('-live-')[0]
            done = idx.get(path, 0)
            if cx is None:
                cx = Ctx(a.points, part)
            ch = process(path, done, cx, kinds, part, a.seconds, t0)
            if ch['nread']:
                cp = cdir / ('%s.%d-%d.npz' % (os.path.basename(path), done, done + ch['nread']))
                save_chunk(cp, ch)
                idx[path] = done + ch['nread']
                json.dump(idx, open(idx_path, 'w'))
            print('%s: %d new walks (%d held), %.0fs' % (os.path.basename(path), ch['nread'], done, time.time() - t0), flush=True)
            if a.seconds and time.time() - t0 > a.seconds:
                print('stopped: budget spent; rerun to resume', flush=True)
                break
    assemble(a.name, sorted(str(x) for x in cdir.glob('*.npz')), kinds)


if __name__ == '__main__':
    main()

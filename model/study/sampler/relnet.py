"""relnet: a learned correction to P's relation pick at each atom start of the arclog clause sampler.

score(option) = a * logp_P(option) + f(context, option); a softmax over the row's options.  `score_options(row)` returns
f' = score - logp_P for each option, so a steer multiplies option i's weight by exp(f'[i]).

Train (streams; prints rate and ETA):
  relnet.py --train runR_dev runR2_dev --test runR_holdout --out relnet.pt [--baselines]
Any number of --train dirs; a dir that lacks relrows.jsonl.zst is skipped.  Holdout is never read for training.
Use as a library:  from relnet import score_options;  f = score_options(row)

A row is a relrows row (k, phase, scope, prefix, options with p) plus
  point_group: {'point_group', 'depth', 'd_out'}   (in relrows already)
  head: {'tok': '&r9', 'name': '&wall_cell'}       (the relation of the clause being drawn; the training loader gets it
                                                    from `clause` and names.json; the sampler has it as prog_names)
"""
import argparse
import collections
import json
import math
import os
import random
import re
import sys
import time
import zlib

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths as P  # noqa: E402
sys.path.append(P.CODE)
from judge3.framed_jsonl import iter_json  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RELFIT = os.path.join(HERE, 'relfit.py')
LN2 = math.log(2)
GROUPS = ['DET', 'RULE depth 1', 'RULE depth 2', 'RULE depth 3+', 'INIT port', 'output']
S, T, TS, NP, PS = 4, 6, 12, 16, 12  # name subtokens, types per option, scope types, prefix relations, prefix name subtokens
NSUB = 2048  # subtoken hash buckets
NREL, NTY, NCOL = 256, 64, 256
USE_RECENCY = False  # slot distance is not DAG distance; the NN does not read it
REC = 14  # recency buckets 0..REC-2, REC-1 = not derived
LOGP_FLOOR = math.log(1e-7)
ATOM_REL = re.compile(r'\((?:NOT \()?([^\s():][^\s()]*)')
FRESH = re.compile(r'\(:(\w+) \*(\w+)\)')
SLOT = re.compile(r'&r(\d+)')


def subtokens(name):
    """The first S pieces of a program name: '&line_color.member' -> ['line', 'color', 'member'] (hashed to 1..NSUB-1; 0 pads)."""
    parts = [p for p in re.split(r'[&._\s]+', name or '') if p and not re.fullmatch(r'r?\d+', p)]
    return [2 + zlib.crc32(p.encode()) % (NSUB - 2) for p in parts[:S]]


def norm_type(t):
    return str(t).split('(')[0]


class Vocab:
    """Growing id tables for the closed sets (lib relations and ops, types, column names); id 0 pads, 1 is unknown.
    Past the table size an id is 1."""

    def __init__(self):
        self.d = {'rel': {}, 'ty': {}, 'col': {}}
        self.cap = {'rel': NREL, 'ty': NTY, 'col': NCOL}

    def id(self, table, s):
        d = self.d[table]
        i = d.get(s)
        if i is None:
            i = len(d) + 2 if len(d) + 2 < self.cap[table] else 1
            if i != 1:
                d[s] = i
        return i


class SigTable:
    """One id per distinct option signature (kind, relation or name, types, columns): static option features."""

    def __init__(self, vocab):
        self.v, self.ids, self.rows, self.arr = vocab, {}, [], None
        self.rows.append((0, 0, [0] * S, [0] * T, [0] * T, 0))  # id 0 pads

    def id(self, o):
        kind = o['kind']
        key = (kind, o['tok'] if kind != 'derived' else o['name'], tuple(map(str, o.get('types') or ())) if kind == 'derived' else 0)
        i = self.ids.get(key)
        if i is None:
            v = self.v
            ty = [v.id('ty', norm_type(t)) for t in (o.get('types') or [])][:T]
            col = [v.id('col', c) for c in (o.get('columns') or [])][:T]
            n = len(o.get('types') or [])
            if kind == 'derived':
                row = (1, 0, (subtokens(o['name']) + [0] * S)[:S], ty + [0] * (T - len(ty)), [0] * T, n)
            else:
                row = (0 if kind == 'lib' else 2, v.id('rel', o['tok']), [0] * S, ty + [0] * (T - len(ty)),
                       col + [0] * (T - len(col)), n)
            i = self.ids[key] = len(self.rows)
            self.rows.append(row)
            self.arr = None
        return i

    def arrays(self):
        if self.arr is None:
            self.arr = dict(kind=np.array([r[0] for r in self.rows], np.int64), rel=np.array([r[1] for r in self.rows], np.int64),
                            sub=np.array([r[2] for r in self.rows], np.int64), ty=np.array([r[3] for r in self.rows], np.int64),
                            col=np.array([r[4] for r in self.rows], np.int64), n=np.array([r[5] for r in self.rows], np.int64))
        return self.arr


def pad(xs, n):
    xs = list(xs)[:n]
    return xs + [0] * (n - len(xs))


def encode_row(r, V, tab, head=None):
    """A row's arrays, or None where gold is not among its options.  `head` overrides r['head']."""
    opts = r['options']
    toks = [o['tok'] for o in opts]
    gold = r.get('gold')
    if gold is not None and gold not in toks:
        return None
    pg = r.get('point_group') or {}
    slots = [int(m.group(1)) if o['kind'] == 'derived' and (m := SLOT.match(o['tok'])) else -1 for o in opts]
    top = max(slots) if max(slots, default=-1) >= 0 else 0
    head = head or r.get('head') or {}
    hm = SLOT.match(head.get('tok') or '') or re.match(r'\(\w+ &r(\d+)', r.get('clause') or '')
    hslot = int(hm.group(1)) if hm else top + 1
    hname = head.get('name') or ''
    byname = {o['tok']: o for o in opts}
    prefix = r.get('prefix') or []
    prel, pslot, psub = [], [], []
    for a in prefix:
        for m in ATOM_REL.finditer(a):
            s = m.group(1)
            if s.startswith('&r'):
                sm = SLOT.match(s)
                if sm:
                    pslot.append(int(sm.group(1)))
                    od = byname.get('&r' + sm.group(1))
                    if od:
                        psub += subtokens(od['name'])
            else:
                prel.append(V.id('rel', s))
    last_rel, last_slot, last_ty, last_sub = 0, -1, [], []
    if prefix:
        m = ATOM_REL.match(prefix[-1])
        if m:
            s = m.group(1)
            if s.startswith('&r') and SLOT.match(s):
                last_slot = int(SLOT.match(s).group(1))
                od = byname.get('&r' + str(last_slot))
                if od:
                    last_sub = subtokens(od['name'])
                    last_ty = [V.id('ty', norm_type(t)) for t in od.get('types') or []]
            else:
                last_rel = V.id('rel', s)
                od = byname.get(s)
                if od and od.get('columns') and od.get('types'):
                    ct = dict(zip(od['columns'], od['types']))
                    last_ty = [V.id('ty', norm_type(ct[c])) for c, _ in FRESH.findall(prefix[-1]) if c in ct]
    scope = [V.id('ty', norm_type(t)) for t in r.get('scope') or []]
    nder = sum(s >= 0 for s in slots)
    e = dict(
        k=min(r['k'], 6), grp=GROUPS.index(pg.get('point_group')) + 1 if pg.get('point_group') in GROUPS else 0,
        depth=min(int(pg.get('depth') or 0), 9), dout=min(int(pg.get('d_out') or 0), 6), phase=int(r.get('phase') == 'root2'),
        nder=min(nder // 3, 9), nprefix=min(len(prefix), 9),
        scope=np.array(pad(scope, TS), np.int64), prel=np.array(pad(prel, NP), np.int64),
        pslot=np.array(pad([s + 1 for s in pslot], NP), np.int64), psub=np.array(pad(psub, PS), np.int64),
        last_rel=last_rel, last_slot=last_slot + 1, last_ty=np.array(pad(last_ty, T), np.int64),
        last_sub=np.array(pad(last_sub, S), np.int64), head_sub=np.array(pad(subtokens(hname), S), np.int64),
        hslot=hslot, top=top,
        sig=np.array([tab.id(o) for o in opts], np.int64), slot=np.array([s + 1 for s in slots], np.int64),
        logp=np.array([max(math.log(max(o['p'], 1e-12)), LOGP_FLOOR) for o in opts], np.float32),
        gold=toks.index(gold) if gold is not None else -1)
    return e


FIXED = ['k', 'grp', 'depth', 'dout', 'phase', 'nder', 'nprefix', 'scope', 'prel', 'pslot', 'psub', 'last_rel', 'last_slot',
         'last_ty', 'last_sub', 'head_sub', 'hslot', 'top', 'gold']
OPTF = ['sig', 'slot', 'logp']


def stack(encs):
    """Encoded rows -> batch arrays (options padded to the longest row)."""
    out = {f: np.array([e[f] for e in encs]) for f in FIXED}
    O = max(len(e['sig']) for e in encs)
    n = len(encs)
    out['sig'] = np.zeros((n, O), np.int64)
    out['slot'] = np.zeros((n, O), np.int64)
    out['logp'] = np.zeros((n, O), np.float32)
    out['mask'] = np.zeros((n, O), bool)
    for i, e in enumerate(encs):
        m = len(e['sig'])
        out['sig'][i, :m], out['slot'][i, :m], out['logp'][i, :m], out['mask'][i, :m] = e['sig'], e['slot'], e['logp'], True
    return out


class Net(nn.Module):
    def __init__(self, E=16, H=32, hid=64, drop=0.2):
        super().__init__()
        self.cfg = dict(E=E, H=H, hid=hid, drop=drop)
        self.rel, self.sub, self.ty, self.col = nn.Embedding(NREL, E), nn.Embedding(NSUB, E), nn.Embedding(NTY, E), nn.Embedding(NCOL, E)
        self.kind, self.arity = nn.Embedding(3, E), nn.Embedding(T + 1, E)
        self.ke, self.ge, self.de, self.oe, self.pe, self.ne, self.npe = (
            nn.Embedding(7, E), nn.Embedding(len(GROUPS) + 1, E), nn.Embedding(10, E), nn.Embedding(7, E), nn.Embedding(2, E),
            nn.Embedding(10, E), nn.Embedding(10, E))
        self.rech, self.rect = nn.Embedding(REC, E), nn.Embedding(REC, E)
        self.opt_lin = nn.Linear(6 * E, H)
        self.ctx_lin = nn.Linear(13 * E, H)  # 7 scalar embeddings + 6 bags
        self.nd = 17
        self.mlp = nn.Sequential(nn.Linear(3 * H + self.nd + 2 * E, hid), nn.GELU(), nn.Dropout(drop), nn.Linear(hid, hid // 2), nn.GELU(),
                                 nn.Linear(hid // 2, 1))
        self.drop = nn.Dropout(drop)
        self.a = nn.Parameter(torch.ones(1))
        self.register_buffer('sub_ok', torch.ones(NSUB, dtype=torch.bool))  # False: a bucket too rare in training, read as unknown
        for emb in (self.rel, self.sub, self.ty, self.col, self.kind, self.arity, self.ke, self.ge, self.de, self.oe, self.pe, self.ne,
                    self.npe, self.rech, self.rect):
            nn.init.normal_(emb.weight, std=0.1)
        nn.init.zeros_(self.mlp[-1].weight)
        nn.init.zeros_(self.mlp[-1].bias)

    def bag(self, emb, ids, rare=False):
        """Mean embedding over the nonzero ids (the last dim)."""
        if rare:
            ids = torch.where(self.sub_ok[ids], ids, torch.ones_like(ids)) * (ids > 0)
        m = (ids > 0).float()
        return (emb(ids) * m[..., None]).sum(-2) / m.sum(-1, keepdim=True).clamp(min=1)

    def forward(self, b, sg):
        """b: batch tensors; sg: signature tensors.  Returns (scores, f') both (B, O) with masked options at -inf / 0."""
        sig = b['sig']
        kind, rel, sub, ty, col, n = (sg[x][sig] for x in ('kind', 'rel', 'sub', 'ty', 'col', 'n'))
        slot, logp, mask = b['slot'], b['logp'], b['mask']
        o = self.opt_lin(self.drop(torch.cat([self.rel(rel), self.bag(self.sub, sub, True), self.bag(self.ty, ty), self.bag(self.col, col),
                                              self.kind(kind), self.arity(n.clamp(max=T))], -1)))
        sc, hs = b['scope'], b['head_sub']
        c = self.ctx_lin(self.drop(torch.cat([
            self.ke(b['k']), self.ge(b['grp']), self.de(b['depth']), self.oe(b['dout']), self.pe(b['phase']), self.ne(b['nder']),
            self.npe(b['nprefix']), self.bag(self.rel, b['prel']), self.bag(self.sub, b['psub'], True), self.bag(self.ty, sc),
            self.rel(b['last_rel']) + self.bag(self.sub, b['last_sub'], True), self.bag(self.ty, b['last_ty']),
            self.bag(self.sub, hs, True)], -1)))
        c = c[:, None, :].expand_as(o)
        # dynamic features
        tym = (ty > 0)[..., None]
        hit_sc = ((ty[..., None] == sc[:, None, None, :]) & tym & (sc > 0)[:, None, None, :]).any(-1).float().sum(-1)
        hit_last = ((ty[..., None] == b['last_ty'][:, None, None, :]) & tym & (b['last_ty'] > 0)[:, None, None, :]).any(-1).float().sum(-1)
        nt = n.clamp(max=T).float()
        pr = b['prel'][:, None, :]
        in_rel = ((rel[..., None] == pr) & (rel > 1)[..., None]).float().sum(-1)
        in_slot = ((slot[..., None] == b['pslot'][:, None, :]) & (slot > 0)[..., None]).float().sum(-1)
        inpre = in_rel + in_slot
        islast = ((rel == b['last_rel'][:, None]) & (rel > 1)).float() + ((slot == b['last_slot'][:, None]) & (slot > 0)).float()
        subm = (sub > 0)[..., None]
        ov_head = ((sub[..., None] == hs[:, None, None, :]) & subm & (hs > 0)[:, None, None, :]).any(-1).float().sum(-1)
        sib = ((sub[..., 0] == hs[:, None, 0]) & (sub[..., 0] > 0)).float()
        ov_pre = ((sub[..., None] == b['psub'][:, None, None, :]) & subm & (b['psub'] > 0)[:, None, None, :]).any(-1).float().sum(-1)
        ov_last = ((sub[..., None] == b['last_sub'][:, None, None, :]) & subm & (b['last_sub'] > 0)[:, None, None, :]).any(-1).float().sum(-1)
        isd = (kind == 1).float()
        lp = logp.masked_fill(~mask, -1e9)
        rel_lp = logp - lp.max(-1, keepdim=True).values
        k1 = (b['k'] == 1).float()[:, None].expand_as(logp)
        dyn = torch.stack([hit_sc / 3, hit_sc / nt.clamp(min=1), ((nt > 0) & (hit_sc == 0)).float(), ((nt > 0) & (hit_sc == nt)).float(),
                           hit_last / 3, (hit_last > 0).float(), inpre.clamp(max=3) / 3, islast.clamp(max=1), ov_head / 2, sib,
                           ov_pre / 3, ov_last / 2, logp / 10, rel_lp / 10, (kind == 2).float(), k1, isd], -1)
        has = (slot > 0) & USE_RECENCY
        rh = torch.where(has, (b['hslot'][:, None] - (slot - 1)).clamp(0, REC - 2), torch.full_like(slot, REC - 1))
        rt = torch.where(has, (b['top'][:, None] - (slot - 1)).clamp(0, REC - 2), torch.full_like(slot, REC - 1))
        x = torch.cat([c, o, c * o, dyn, self.rech(rh), self.rect(rt)], -1)
        f = self.mlp(x).squeeze(-1)
        score = self.a * logp + f
        fprime = (score - logp).masked_fill(~mask, 0.0)
        return score.masked_fill(~mask, -1e9), fprime


def to_t(b):
    return {k: torch.from_numpy(np.ascontiguousarray(v)) for k, v in b.items()}


def sig_t(tab):
    return {k: torch.from_numpy(v) for k, v in tab.arrays().items()}


def row_bits(model, enc, tab, bs=256, p_only=False):
    """Bits of gold under the model (or under P alone) for each encoded row."""
    out = []
    sg = sig_t(tab)
    model.eval()
    with torch.no_grad():
        for i in range(0, len(enc), bs):
            b = to_t(stack(enc[i:i + bs]))
            sc = b['logp'].masked_fill(~b['mask'], -1e9) if p_only else model(b, sg)[0]
            lsm = sc - torch.logsumexp(sc, -1, keepdim=True)
            out.append((-lsm.gather(1, b['gold'][:, None])[:, 0] / LN2).numpy())
    return np.concatenate(out)


# ---- loading ----

def n_lines(path):
    ip = path + '.idx.jsonl'
    try:
        with open(ip) as f:
            next(f)
            return sum(json.loads(l)['line_count'] for l in f if l.endswith('\n'))
    except (OSError, StopIteration, ValueError):
        return None


def head_of(r, names):
    m = re.match(r'\(\w+ (&r\d+)', r.get('clause') or '')
    if not m:
        return None
    tok = m.group(1)
    nm = (names.get('%s|%s|%s' % (r['task'], r['case'], json.dumps(r['point']))) or {}).get(tok, '')
    return {'tok': tok, 'name': nm}


def load_dirs(dirs, V, tab, label, keep=None, max_rows=0):
    """Stream the rows of each dir; encode them.  Returns (encs, meta); meta rows: task, group, kind of gold, k, clause key.
    keep: a function row -> bool (a raw row is passed to it when it is encoded; used by the baseline reservoir)."""
    encs, meta = [], []
    skipped = collections.Counter()
    t0, done = time.time(), 0
    for d in dirs:
        path = os.path.join(d, 'relrows.jsonl.zst')
        if not os.path.exists(path):
            print('%s: %s missing, skipped' % (label, path), flush=True)
            continue
        npath = os.path.join(d, 'names.json')
        names = json.load(open(npath)) if os.path.exists(npath) else {}
        total = n_lines(path)
        # points.jsonl.zst has the group where a row lacks it
        for r in iter_json(path):
            done += 1
            if max_rows and done > max_rows:
                break
            e = encode_row(r, V, tab, head_of(r, names))
            if e is None:
                skipped['gold not in options'] += 1
                continue
            gk = next(o['kind'] for o in r['options'] if o['tok'] == r['gold'])
            encs.append(e)
            meta.append(dict(task=r['task'], grp=(r.get('point_group') or {}).get('point_group'), kind=gk, k=r['k'],
                             clause='%s|%s|%s' % (r['task'], r['case'], json.dumps(r['point'])), depth=(r.get('point_group') or {}).get('depth')))
            if keep is not None:
                keep(r, len(encs) - 1)
            if done % 2000 == 0:
                el = time.time() - t0
                rate = done / el
                eta = (total - done) / rate if total else float('nan')
                print('%s %s: %d rows, %.0f rows/s%s' % (label, os.path.basename(d.rstrip('/')), done, rate,
                                                        ', eta %.0fs' % eta if total and total > done else ''), flush=True)
        names = None
    print('%s: %d rows encoded in %.0fs; skipped %s' % (label, len(encs), time.time() - t0, dict(skipped)), flush=True)
    return encs, meta


# ---- training ----

def split_tasks(meta, frac=0.15):
    return np.array([zlib.crc32(m['task'].encode()) % 100 < frac * 100 for m in meta])


def train(encs, meta, tab, args):
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    isval = split_tasks(meta)
    tr, va = [i for i in range(len(encs)) if not isval[i]], [i for i in range(len(encs)) if isval[i]]
    print('train rows %d (%d tasks), val rows %d (%d tasks)' % (
        len(tr), len({meta[i]['task'] for i in tr}), len(va), len({meta[i]['task'] for i in va})), flush=True)
    model = Net(E=args.E, H=args.H, hid=args.hid, drop=args.drop)
    # a name subtoken is known when train options of at least 3 tasks carry it
    sigtasks = collections.defaultdict(set)
    for i in tr:
        for s in set(encs[i]['sig'].tolist()):
            sigtasks[s].add(meta[i]['task'])
    subtasks = collections.defaultdict(set)
    for s, ts in sigtasks.items():
        for u in tab.rows[s][2]:
            if u:
                subtasks[u] |= ts
    ok = torch.zeros(NSUB, dtype=torch.bool)
    for u, ts in subtasks.items():
        ok[u] = len(ts) >= args.min_tasks
    ok[0] = ok[1] = True
    model.sub_ok.copy_(ok)
    print('params %d; known subtokens %d of %d' % (sum(p.numel() for p in model.parameters()), int(ok.sum()), len(subtasks)), flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.wd)
    sg = sig_t(tab)
    best, best_state, bad = 1e9, None, 0
    P_val = row_bits(model, [encs[i] for i in va], tab, p_only=True).mean() if va else float('nan')
    print('val P alone: %.3f bits per pick' % P_val, flush=True)
    t_start = time.time()
    for ep in range(1, args.epochs + 1):
        model.train()
        order = rng.permutation(tr)
        t0, tot, cnt = time.time(), 0.0, 0
        nb = (len(order) + args.bs - 1) // args.bs
        for bi in range(nb):
            idx = order[bi * args.bs:(bi + 1) * args.bs]
            b = to_t(stack([encs[i] for i in idx]))
            sc = model(b, sg)[0]
            loss = F.cross_entropy(sc, b['gold'])
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            tot += loss.item() * len(idx)
            cnt += len(idx)
            if bi % 100 == 99:
                el = time.time() - t0
                print('  ep %d batch %d/%d  %.0f rows/s  loss %.3f bits' % (ep, bi + 1, nb, cnt / el, tot / cnt / LN2), end='\r', flush=True)
        vb = row_bits(model, [encs[i] for i in va], tab).mean() if va else tot / cnt / LN2
        el = time.time() - t0
        eta = (args.epochs - ep) * (time.time() - t_start) / ep
        print('ep %d/%d: train %.3f, val %.3f (P %.3f) bits per pick; %.0f rows/s, epoch %.0fs, eta %.0fs%s' % (
            ep, args.epochs, tot / cnt / LN2, vb, P_val, cnt / el, el, eta, ' *' if vb < best else ''), flush=True)
        if vb < best - 1e-4:
            best, bad = vb, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= args.patience:
                print('early stop', flush=True)
                break
    model.load_state_dict(best_state)
    return model, best


# ---- reports ----

def kbucket(k):
    return '1' if k == 1 else '2' if k == 2 else '3+'


def table(meta, cols, title):
    """cols: {name: bits array}; prints mean bits per pick by gold kind, k, group and depth 3+ x kind."""
    names = list(cols)
    print('\n%s' % title)
    print('%-28s %5s ' % ('subset', 'n') + ' '.join('%10s' % n for n in names))

    def line(label, sel):
        sel = np.array(sel)
        if sel.sum() == 0:
            return
        print('%-28s %5d ' % (label, sel.sum()) + ' '.join('%10.2f' % cols[n][sel].mean() for n in names))
    line('all', [True] * len(meta))
    for kd in ('lib', 'derived', 'op'):
        line('gold ' + kd, [m['kind'] == kd for m in meta])
    for kb in ('1', '2', '3+'):
        line('k ' + kb, [kbucket(m['k']) == kb for m in meta])
    for g in GROUPS:
        line('group ' + g, [m['grp'] == g for m in meta])
    for kd in ('lib', 'derived', 'op'):
        line('RULE depth 3+, gold ' + kd, [m['grp'] == 'RULE depth 3+' and m['kind'] == kd for m in meta])
    for kb in ('1', '2', '3+'):
        line('RULE depth 3+, k ' + kb, [m['grp'] == 'RULE depth 3+' and kbucket(m['k']) == kb for m in meta])
    # per clause at RULE depth 3+: the sum of the picks
    cl = collections.defaultdict(lambda: collections.defaultdict(float))
    for i, m in enumerate(meta):
        if m['grp'] == 'RULE depth 3+':
            for n in names:
                cl[m['clause']][n] += cols[n][i]
    if cl:
        print('RULE depth 3+ clauses: %d, mean bits per clause (sum over its picks): ' % len(cl) + ', '.join(
            '%s %.1f' % (n, np.mean([v[n] for v in cl.values()])) for n in names))
        base = names[0]
        for n in names[1:]:
            print('  mean bits saved per clause vs %s, %s: %.2f' % (base, n, np.mean([v[base] - v[n] for v in cl.values()])))


# ---- baselines (relfit) ----

def relfit_ns(use_b):
    src = open(RELFIT).read()
    src = src[:src.index('train, test = load(')]
    saved = sys.argv
    sys.argv = ['relfit'] + (['--b'] if use_b else [])
    ns = {'__name__': 'relfit_ns', '__file__': RELFIT}
    try:
        exec(compile(src, RELFIT, 'exec'), ns)
    finally:
        sys.argv = saved
    return ns


def fit_logit(Xs, gold, mask, l2=1e-3):
    """Conditional logit by L-BFGS from w = e_0 (P alone); Xs (N, O, F)."""
    w = torch.zeros(Xs.shape[-1])
    w[0] = 1.0
    w.requires_grad_(True)
    opt = torch.optim.LBFGS([w], lr=1.0, max_iter=100, line_search_fn='strong_wolfe')

    def closure():
        opt.zero_grad()
        s = (Xs @ w).masked_fill(~mask, -1e9)
        loss = F.cross_entropy(s, gold) + 0.5 * l2 * (w ** 2).sum()
        loss.backward()
        return loss
    opt.step(closure)
    return w.detach()


def pad_feats(feats, golds):
    O = max(f.shape[0] for f in feats)
    X = np.zeros((len(feats), O, feats[0].shape[1]), np.float32)
    mask = np.zeros((len(feats), O), bool)
    for i, f in enumerate(feats):
        X[i, :len(f)] = f
        mask[i, :len(f)] = True
    return torch.from_numpy(X), torch.tensor(golds), torch.from_numpy(mask)


# ---- runtime ----

_RT = {}


def save_model(model, V, tab, path, best, args):
    torch.save(dict(state=model.state_dict(), cfg=model.cfg, vocab={k: v for k, v in V.d.items()},
                    sigs=tab.rows, sig_ids=tab.ids, consts=dict(S=S, T=T, TS=TS, NP=NP, PS=PS, NSUB=NSUB, NREL=NREL, NTY=NTY, NCOL=NCOL, REC=REC),
                    val_bits=best, train_args=vars(args)), path)


def load_model(path=None):
    path = path or os.path.join(HERE, 'relnet.pt')
    ck = torch.load(path, weights_only=False)
    V = Vocab()
    V.d = ck['vocab']
    tab = SigTable(V)
    tab.rows = ck['sigs']
    tab.ids = ck['sig_ids']
    model = Net(**ck['cfg'])
    model.load_state_dict(ck['state'])
    model.eval()
    return model, V, tab


def score_options(row, path=None):
    """f' for each option of `row` (a relrows row, plus point_group and head; see the module doc): the log of the factor by
    which a steer multiplies the option's weight.  Options whose P share is 0 get a floor log p."""
    if 'm' not in _RT:
        _RT['m'] = load_model(path)
    model, V, tab = _RT['m']
    e = encode_row(dict(row, gold=None), V, tab)
    b = to_t(stack([e]))
    with torch.no_grad():
        return model(b, sig_t(tab))[1][0, :len(row['options'])].tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train', nargs='+', default=[HERE + '/runR_dev', HERE + '/runR2_dev'])
    ap.add_argument('--test', default=HERE + '/runR_holdout')
    ap.add_argument('--out', default=HERE + '/relnet.pt')
    ap.add_argument('--baselines', action='store_true', help='also fit relfit (structural and --b) on a reservoir of train rows')
    ap.add_argument('--base-rows', type=int, default=6000)
    ap.add_argument('--epochs', type=int, default=40)
    ap.add_argument('--patience', type=int, default=6)
    ap.add_argument('--bs', type=int, default=64)
    ap.add_argument('--lr', type=float, default=2e-3)
    ap.add_argument('--wd', type=float, default=1e-2)
    ap.add_argument('--drop', type=float, default=0.2)
    ap.add_argument('--E', type=int, default=16)
    ap.add_argument('--H', type=int, default=32)
    ap.add_argument('--hid', type=int, default=64)
    ap.add_argument('--min-tasks', type=int, default=3)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--threads', type=int, default=2)
    ap.add_argument('--max-rows', type=int, default=0, help='per dir, for a quick run')
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    random.seed(args.seed)
    V = Vocab()
    tab = SigTable(V)
    reservoir = {}  # row index -> {'s': struct features, 'b': b features}
    seen = [0]
    nsx = relfit_ns(False) if args.baselines else None
    nbx = relfit_ns(True) if args.baselines else None
    rr = random.Random(args.seed)

    def keep_train(r, idx):
        if not args.baselines:
            return
        seen[0] += 1
        if len(reservoir) >= args.base_rows:
            if rr.randrange(seen[0]) >= args.base_rows:
                return
            del reservoir[rr.choice(list(reservoir))]
        toks = [o['tok'] for o in r['options']]
        reservoir[idx] = (nsx['features'](r).astype(np.float32), nbx['features'](r).astype(np.float32), toks.index(r['gold']))

    encs, meta = load_dirs(args.train, V, tab, 'train', keep_train, args.max_rows)
    test_feats = []

    def keep_test(r, idx):
        if args.baselines:
            toks = [o['tok'] for o in r['options']]
            test_feats.append((nsx['features'](r).astype(np.float32), nbx['features'](r).astype(np.float32), toks.index(r['gold'])))
    tenc, tmeta = load_dirs([args.test], V, tab, 'test', keep_test, args.max_rows)
    model, best = train(encs, meta, tab, args)
    save_model(model, V, tab, args.out, best, args)
    print('saved', args.out, flush=True)
    cols = {'P': row_bits(model, tenc, tab, p_only=True)}
    if args.baselines:
        for nm, j in (('relfit', 0), ('relfit+b', 1)):
            ids = sorted(reservoir)
            X, g, m = pad_feats([reservoir[i][j] for i in ids], [reservoir[i][2] for i in ids])
            w = fit_logit(X, g, m)
            Xt, gt, mt = pad_feats([f[j] for f in test_feats], [f[2] for f in test_feats])
            s = (Xt @ w).masked_fill(~mt, -1e9)
            cols[nm] = (-(s - torch.logsumexp(s, -1, keepdim=True)).gather(1, gt[:, None])[:, 0] / LN2).numpy()
            print('%s fit on %d train rows' % (nm, len(ids)), flush=True)
    cols['relnet'] = row_bits(model, tenc, tab)
    table(tmeta, cols, 'TEST (%s): mean bits per gold pick' % args.test)
    vmeta = [meta[i] for i in np.nonzero(split_tasks(meta))[0]]
    table(vmeta, {'P': row_bits(model, [encs[i] for i in np.nonzero(split_tasks(meta))[0]], tab, p_only=True),
                  'relnet': row_bits(model, [encs[i] for i in np.nonzero(split_tasks(meta))[0]], tab)}, 'VAL (held-out tasks of train)')


if __name__ == '__main__':
    main()

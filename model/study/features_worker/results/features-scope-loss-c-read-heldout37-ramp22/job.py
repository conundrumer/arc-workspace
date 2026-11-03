"""Scope loss, class C: the proposal's chance of the gold clause under the recorded scope (S), gold's form over gold's ancestors (R), and the gold form's dag bits (DB).

  bash env.sh job.py [--shard I/N] [--budget S] [--arms refit_s0,refit_s1] [--all-slots] [--out FILE] [--only task:g,task:g] [--cap N] [--nowalk] [--recheck N] [--covered [--covered-any-kind]]

Streams one JSON line per form to forms.<I>of<N>.jsonl (forms-<arms>.<I>of<N>.jsonl with --arms) as soon as the form is done, and skips the forms already in that file.
A task stays in one shard (zlib.crc32(task) % N). With --budget the job stops after the form in progress once S seconds pass. It exits 75 when the peak RSS passes 3 GiB after a
form (run it again). A form that raises gets a row with status `error`, so a rerun does not loop on it.
--covered reads the covered gold forms (class `covered` in scope-loss/forms.tsv) instead of the C forms, and writes forms-covered.<I>of<N>.jsonl. A form's opening is the one that opened the
covering visit (`cover_check.o_v` of the scope-loss cache); its scope is that opening's recorded scope, got as for a C form. A form whose covering visit drew another kind than the gold kind gets
status `covering visit of another kind` (walked with --covered-any-kind), one with no covering opening gets `no covering opening`.
--recheck N walks again, for the first N measured rows of the shard file with an exact order sum and 2 or more orders, S on the last order's text (check 7) and S on the same
target (check 8); it writes checks.<I>of<N>.jsonl.
"""
import argparse
import bisect
import collections
import copy
import csv
import hashlib
import itertools
import json
import os
import re
import resource
import sys
import time
import zlib

T0 = time.time()
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
ENGINE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path'
RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943'
OLD = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad'
TOOLS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools'
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ARMS = ['bundle_s0', 'bundle_s1']
RSS_LIMIT = 3 * 2 ** 30
DB_OK = ('exact', 'one', 'bound')

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--shard', default='0/1')
ap.add_argument('--budget', type=float, default=None)
ap.add_argument('--arms', default=None, help='the refit arms to read instead of the bundle arms, for example refit_s0,refit_s1')
ap.add_argument('--all-slots', action='store_true')
ap.add_argument('--out', default=None)
ap.add_argument('--only', default=None, help='task:g,task:g  forms to run (test)')
ap.add_argument('--cap', type=int, default=None, help='stop after this many forms in this run (test)')
ap.add_argument('--nowalk', action='store_true', help='map and table check only (test)')
ap.add_argument('--recheck', type=int, default=None)
ap.add_argument('--covered', action='store_true', help='the covered gold forms under the scope of the opening that covered them (the control for class C)')
ap.add_argument('--covered-any-kind', action='store_true', help='with --covered: also walk the forms whose covering visit drew another kind than the gold kind')
ARGS = ap.parse_args()
SHARD_I, SHARD_N = (int(x) for x in ARGS.shard.split('/'))
ARMS = ARGS.arms.split(',') if ARGS.arms else DEFAULT_ARMS
TAG = ('forms' if not ARGS.covered else 'forms-covered') if not ARGS.arms else ('forms-' if not ARGS.covered else 'forms-covered-') + '+'.join(ARMS)
OUT = ARGS.out or '%s/%s.%dof%d.jsonl' % (HERE, TAG, SHARD_I, SHARD_N)

os.environ.update(P_DAG='1', ORDER_FREE='tie,key', ARCLOG_IDENT_SOURCE='value', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', ONE_REPAIR='30', CHOOSE_LIFT='0', PYTHONDONTWRITEBYTECODE='1')
os.environ.pop('STEER_COVER', None)
os.environ.pop('KEY_IDENT', None)
sys.dont_write_bytecode = True
sys.path[:0] = [KIT + '/model/study/sampler', ENGINE, TOOLS]
import live  # noqa: E402
import or_q  # noqa: E402
import superdag as D  # noqa: E402
import form_orders as O  # noqa: E402
import sampler_paths  # noqa: E402
import search_node_score_parity as P  # noqa: E402

NAME = re.compile(r'&[rf]\d+(?:\.\w+)?')
PROP = re.compile(r'^\(DET (&\S+) ([A-Za-z_]\w*)\)$')
sampler = live.Sampler(KIT + '/models-tk')
pe = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + '/points-eval.json'))}
DBITS = json.load(open(OLD + '/frontier/bits.json'))


# ---------------------------------------------------------------- items

def build_items():
    """[(arm, task, g, source, class-row)] of this shard: the C forms of ARMS and, for the bundle arms, the frontier's one-read proposal forms."""
    rows = list(csv.DictReader(open(RUN + '/scope-loss/forms.tsv'), delimiter='\t'))
    index = {(x['arm'], x['task'], int(x['g'])): x for x in rows}
    cset = {k for k, x in index.items() if x['class'] == ('covered' if ARGS.covered else 'C') and x['arm'] in ARMS}
    fset = set()
    if not ARGS.arms and not ARGS.covered:
        for x in csv.DictReader(open(RUN + '/frontier/ready.tsv'), delimiter='\t'):
            if x['nreads'] == '1' and x['bk_primary'] == 'proposal':
                fset.add(('bundle_s' + x['seed'], x['task'], int(x['g'])))
    keys = sorted(cset | fset, key=lambda k: (k[1], k[0], k[2]))
    out = []
    for k in keys:
        src = 'covered' if ARGS.covered else 'both' if k in cset and k in fset else 'C' if k in cset else 'frontier'
        out.append((*k, src, index.get(k)))
    return out


# ---------------------------------------------------------------- relations and the map

def col_sigs(tb):
    spans, at = [], 0
    for w in tb['widths']:
        spans.append((at, at + w))
        at += w
    entries = [(tuple(ex), rows) for ex, _, rows, _, _ in tb['entries']]
    return [(str(t), hash(tuple(sorted((ex, hash(frozenset(r[a:b] for r in rows))) for ex, rows in entries)))) for t, (a, b) in zip(tb['types'], spans)]


def relations(texts, sess, d):
    """{(text head, j or None): dict(slot, form, key, labels, sigs)} of the relation tables of the texts replayed."""
    run = D.Run(sampler.pri, sess, 0, time.monotonic() + 60, d, live.Limits())
    run.collect = []
    dec, pg = run.scope(texts)
    out = {}
    for i, ct in enumerate(run.collect):
        for s, j in D.relation_tables(ct):
            try:
                tb = D.S.parse_table(D.OneTable(ct, j))
            except Exception:  # noqa: BLE001  a table past the work cap, as gold_keys counts it
                continue
            nm = pg.names.get('&r%d' % s, '&r%d' % s)
            h, _, sub = nm.partition('.')
            out[(pg.written.get(h, h), int(sub) if sub else None)] = dict(slot=s, form=i, key=D.table_key(tb)[0], labels=list(tb['labels']), sigs=col_sigs(tb))
    return out


def port_map(gr, sr):
    """{gold label: scope label} by column signature, or None where the labels are not plain."""
    if '' in gr['labels'] or '' in sr['labels'] or len(set(gr['labels'])) < len(gr['labels']) or len(set(sr['labels'])) < len(sr['labels']):
        return None
    free = collections.defaultdict(list)
    for p, sg in enumerate(sr['sigs']):
        free[sg].append(p)
    out = {}
    for p, sg in enumerate(gr['sigs']):
        if not free[sg]:
            return None
        out[gr['labels'][p]] = sr['labels'][free[sg].pop(0)]
    return out


def rename(tree, ref, new, pm):
    """Renames the atoms of relation ref in tree: the relation to new, and each port :X to :pm[X]. Gives the count of record ports left as they are."""
    rec = 0
    if isinstance(tree, list):
        if tree and tree[0] == ref:
            tree[0] = new
            for p in tree[1:]:
                if isinstance(p, list) and p and p[0].startswith(':'):
                    if any(isinstance(y, list) for y in p[1:]):
                        rec += 1
                    elif pm is not None and p[0][1:] in pm:
                        p[0] = ':' + pm[p[0][1:]]
        for y in tree:
            rec += rename(y, ref, new, pm)
    return rec


def norm(text):
    """The text with the relation names and the binder marks left out."""
    return re.sub(r'[*^](?=[A-Za-z_])', '', re.sub(r'&[rf]\d+', '&', text))


def slots_of(sess, before, text, kind):
    V = sess.vocabulary
    toks = or_q.gold_rest(sess, before, text, kind)
    return [int(V.name(t)[2:]) for t in toks if re.fullmatch(r'&r\d+', V.name(t) or '')]


def learn_subs(texts, text_of, by_slot, sess):
    """{(component, j): {sub}}: the sub-names that the forms of texts write for the INIT relations they read, by the alignment of their refs with their relation tokens."""
    out = collections.defaultdict(set)
    for i, l in enumerate(texts):
        refs = [m for m in NAME.findall(l) if m != l.split()[1]]
        if not any('.' in r for r in refs):
            continue
        try:
            slots = slots_of(sess, texts[:i], l, l.split()[0][1:])
        except Exception:  # noqa: BLE001
            continue
        if len(slots) != len(refs):
            continue
        for r, s in zip(refs, slots):
            gk = by_slot.get(s)
            if '.' in r and gk is not None and gk[1] is not None and gk[0] in text_of and len(text_of[gk[0]].split()) > 2:
                out[(text_of[gk[0]].split()[2], gk[1])].add(r.partition('.')[2])
    return out


def reader_ports(gold_lines, bank_texts):
    """{proposer name: {port names}} that the atoms reading a (DET &x P) form write, in gold's lines and the bank's texts."""
    texts = list(gold_lines) + list(bank_texts)
    heads = {}
    for t in texts:
        m = PROP.match(t.strip())
        if m:
            heads[m.group(1)] = m.group(2)
    out = collections.defaultdict(set)

    def walk(x):
        if isinstance(x, list):
            if x and isinstance(x[0], str) and x[0] in heads:
                for p in x[1:]:
                    if isinstance(p, list) and p and isinstance(p[0], str) and p[0].startswith(':'):
                        out[heads[x[0]]].add(p[0][1:])
            for y in x:
                walk(y)
    for t in texts:
        if set(re.findall(r'&[rf]\d+', t)) & heads.keys():
            try:
                walk(O.parse(t)[0])
            except Exception:  # noqa: BLE001
                pass
    return out


# ---------------------------------------------------------------- one form

class Ctx:
    """What the forms of one (arm, task) share."""
    def __init__(self, arm, task):
        self.arm, self.task = arm, task
        self.lines = [l for l in pe[task].strip().split('\n') if not l.startswith('(OUT')]
        self.heads = [l.split()[1] for l in self.lines]
        self.sl = json.load(open('%s/scope-loss/cache/%s__%s.json' % (OLD, arm, task)))
        self.r1 = json.load(open('%s/r1-forms/cache/%s__%s.json' % (OLD, arm, task)))
        self.bank = P.load_bank('%s/out/%s/%s/work/%s.out.jsonl.bank' % (RUN, arm, task, task))
        self.pports = reader_ports(self.lines, [f.text for f in self.bank['forms'].values()])


CTX = {}


def ctx_of(arm, task):
    if CTX.get('key') != (arm, task):
        CTX.clear()
        CTX['key'] = (arm, task)
        CTX['ctx'] = Ctx(arm, task)
    return CTX['ctx']


def candidate_openings(c, g, cls):
    """[(slot_tries, i)] best first: for class C the rows held with the form's kind, for another class the rows held with another kind, with lost 0."""
    rows = next(x for x in c.sl['golds'] if x['g'] == g)['rows']
    ops = {o['i']: o for o in c.sl['ops']}
    pick = [x['i'] for x in rows if x['hk'] and ops[x['i']]['lost'] == 0] if cls == 'C' else [x['i'] for x in rows if x['held'] and not x['hk'] and ops[x['i']]['lost'] == 0]
    return sorted(((ops[i]['slot_tries'], i) for i in pick), key=lambda t: (-t[0], t[1])), ops


def covering_opening(c, g):
    """(status or None, cover_check, ops, [(slot_tries, i)]) of a covered form: the opening that opened the covering visit, from the cover_check of the scope-loss cache."""
    ck = next(x for x in c.sl['golds'] if x['g'] == g).get('cover_check') or {}
    ops = {o['i']: o for o in c.sl['ops']}
    if ck.get('visit') is None:
        return 'no covering visit', ck, ops, []
    if not ck.get('kind_ok') and not ARGS.covered_any_kind:
        return 'covering visit of another kind', ck, ops, []
    if ck.get('o_v') is None:
        return 'no covering opening', ck, ops, []
    return None, ck, ops, [(ops[ck['o_v']]['slot_tries'], ck['o_v'])]


def covering_visit(c, ck):
    return sorted(c.r1['visits'], key=lambda v: v['time'])[ck['visit']]


def scope_of(c, i):
    """(visit, fids, scope texts) of opening i: the first visit with resume false from the opening's time to the next opening's."""
    allops = sorted(c.r1['openings'], key=lambda o: o['time'])
    o = [x for x in allops if x['picks']][i]
    times = [x['time'] for x in allops]
    k = bisect.bisect_right(times, o['time'])
    nxt = times[k] if k < len(times) else float('inf')
    v = next(v for v in sorted(c.r1['visits'], key=lambda v: v['time']) if o['time'] <= v['time'] < nxt and not v['resume'])
    fs = c.bank['forms']
    fids = sorted(v['fids'], key=lambda f: (fs[f].depth, f))
    return v, fids, [fs[f].text for f in fids]


def build_target(c, g, kind, scope, sess, d):
    """The map of gold's reads to the scope, the target text and its table check. Gives a dict with status, how, target, table_check, gold_rels, absent."""
    lines = c.lines
    res = dict(how=[], absent=[])
    grel, srel = relations(lines, sess, d), relations(scope, sess, d)
    gtext, stext = {l.split()[1]: l for l in lines}, {l.split()[1]: l for l in scope}
    sidx = {l.split()[1]: n for n, l in enumerate(scope)}
    by_g, by_s = {v['slot']: k for k, v in grel.items()}, {v['slot']: k for k, v in srel.items()}
    subs = learn_subs(lines, gtext, by_g, sess)
    for k, v in learn_subs(scope, stext, by_s, sess).items():
        subs[k] |= v
    known = {k: next(iter(v)) for k, v in subs.items() if len(v) == 1}
    def rel_name(k):
        h, j = k
        return h if j is None else '%s.%s' % (h, known.get((gtext[h].split()[2] if len(gtext[h].split()) > 2 else '', j), j))
    res['gold_rels'] = [[rel_name(k), any(w['key'] == v['key'] for w in srel.values())] for k, v in grel.items() if v['form'] == g and k[0] in gtext]
    refs = [m for m in NAME.findall(lines[g]) if m != c.heads[g]]
    tree = O.parse(lines[g])[0]
    how, fails = res['how'], []
    try:
        toks = slots_of(sess, lines[:g], lines[g], kind)
    except Exception as e:  # noqa: BLE001
        toks = None
        how.append('gold tokens: %s' % repr(e)[:100])
    if toks is None or len(toks) != len(refs):
        res.update(status='refs and tokens differ', target=None)
        return res

    def labels_of(val, head, j, texts):
        lab = list(val['labels'])
        if j is None and len(lab) == 1 and lab[0] == '' and head in texts:
            m = PROP.match(texts[head].strip())
            ports = c.pports.get(m.group(2)) if m else None
            if ports and len(ports) == 1:
                lab = [next(iter(ports))]
        return lab

    recs = 0
    for ref in dict.fromkeys(refs):
        gk = by_g.get(toks[refs.index(ref)])
        if gk is None:
            fails.append('%s: no gold table' % ref)
            continue
        gr = grel[gk]
        sub = ref.partition('.')[2]
        cands = []
        for kk, val in srel.items():
            if val['key'] != gr['key']:
                continue
            h, j = kk
            if j is None:
                cands.append((1, sidx.get(h, 0), 0, kk, h))
            elif sub and gk[1] == j and h in stext and gk[0] in gtext and norm(stext[h]) == norm(gtext[gk[0]]):
                cands.append((0, sidx.get(h, 0), j, kk, '%s.%s' % (h, sub)))
            elif h in stext and len(stext[h].split()) > 2 and (stext[h].split()[2], j) in known:
                cands.append((2, sidx.get(h, 0), j, kk, '%s.%s' % (h, known[(stext[h].split()[2], j)])))
            else:
                cands.append((3, sidx.get(h, 0), j, kk, None))
        if not cands:
            fails.append('%s: not in scope' % ref)
            res['absent'].append(ref)
            continue
        why = []
        for cat, _, _, kk, new in sorted(cands, key=lambda t: t[:3]):
            if new is None:
                why.append('INIT relation %s.%s with no known sub-name' % kk)
                continue
            h, j = kk
            sr = srel[kk]
            glab, slab = labels_of(gr, gk[0], gk[1], gtext), labels_of(sr, h, j, stext)
            same = glab == slab
            pm = None if same else port_map(dict(gr, labels=glab), dict(sr, labels=slab))
            if not same and pm is None:
                why.append('ports not mapped %s %s' % (glab, slab))
                continue
            probe = copy.deepcopy(tree)
            nrec = rename(probe, ref, new, pm)
            if not same and nrec:
                why.append('record port with renamed labels %s %s' % (glab, slab))
                continue
            recs += rename(tree, ref, new, pm)
            how.append('%s -> %s %s' % (ref, new, 'same labels' if same else 'renamed %s' % pm))
            break
        else:
            fails.append('%s: %s' % (ref, ' / '.join(why)))
    how.extend(fails)
    if recs:
        how.append('record ports %d' % recs)
    target = O.unparse(tree)
    res['target'] = target
    if fails:
        res['status'] = 'read relation not in the scope' if res['absent'] else 'unmapped'
        return res
    try:
        target = or_q.sorted_fields(target, sess, scope)
        res['target'] = target
        trel = relations(scope + [target], sess, d)
        tkeys = sorted(str(val['key']) for val in trel.values() if val['form'] == len(scope))
        gkeys = sorted(str(val['key']) for val in grel.values() if val['form'] == g)
        res['table_check'] = tkeys == gkeys
        res['status'] = 'mapped' if tkeys == gkeys else 'table differs'
    except Exception as e:  # noqa: BLE001
        res.update(status='replay error', error=repr(e)[:200])
    return res


ORD_KEYS = ('orders', 'orders_exact', 'exact', 'walked', 'valid', 'refused', 'written', 'best', 'tight', 'only_written', 'stopped', 'draws', 'walked_bits', 'se_bits', 'ess', 'text_differs')


def compact(w):
    rec = {k: w.get(k) for k in ('total', 'parts', 'atoms', 'detail', 'bad', 'dead', 'left', 'fell_back')}
    rec['orders'] = {k: v for k, v in (w.get('orders') or {}).items() if k in ORD_KEYS}
    rec['valid'] = not (w.get('bad') or w.get('dead') or w.get('left'))
    return rec


def r_inputs(c, g, sess):
    forms = live.S.strata.sexprs('\n'.join(c.lines))
    idx = sorted(set(live.S.ancestor_order(forms, g)) | {g})
    sub = [c.lines[j] for j in idx]
    canon, _ = or_q.canonical_lines(sub, sess)
    k = idx.index(g)
    return or_q.canonical_scope(canon, k), canon[k]


def prepare(item, opening=None):
    """Everything to walk one form: (row, ctx dict) where row has the map's fields."""
    arm, task, g, src, frow = item
    c = ctx_of(arm, task)
    cls = frow['class']
    row = dict(arm=arm, seed=int(frow['seed']), task=task, g=g, kind=c.lines[g].split()[0][1:], source=src, nreads=int(frow['nreads']), cls=cls)
    kind = row['kind']
    cov = cls == 'covered'
    if cov:
        why, ck, ops, cand = covering_opening(c, g)
        row['cover_visit'] = ck.get('visit')
        row['cover_visit_kind'] = covering_visit(c, ck)['kind'] if ck.get('visit') is not None else None
        row['ready_before'] = ck.get('ready_before')
        row['held_o'] = ck.get('held_o')
        row['n_hk'] = len(cand)
        if why:
            row['status'] = why
            return row, None
    else:
        cand, ops = candidate_openings(c, g, cls)
        row['n_hk'] = len(cand)
    if not cand:
        row['status'] = 'no replayable scope'
        return row, None
    slot, i = cand[0] if opening is None else next(x for x in cand if x[1] == opening)
    v, fids, scope = scope_of(c, i)
    row.update(opening=i, slot_tries=slot, kind_match=(cls == 'C') if not cov else bool(ck.get('kind_ok')), visit_kind=v['kind'], kind_ok=(v['kind'] == kind) if cls in ('C', 'covered') else None, scope_fids=fids, scope_n=len(scope))
    if cov:
        row['lost'] = ops[i]['lost']
        if sorted(covering_visit(c, ck)['fids']) != sorted(fids):
            row['status'] = 'scope differs from the covering visit'
            return row, None
    sess, d, _ = D.session_of(task)
    bt = build_target(c, g, kind, scope, sess, d)
    row.update(how=bt['how'], status=bt['status'], target=bt.get('target'), table_check=bt.get('table_check'), gold_rels=bt.get('gold_rels'), absent=bt['absent'])
    if 'error' in bt:
        row['error'] = bt['error']
    db = DBITS.get(task, {}).get(str(g))
    row['DB'] = dict(bits=db[0] if db and db[1] in DB_OK else None, status=db[1] if db else 'absent')
    return row, dict(c=c, kind=kind, scope=scope, sess=sess, d=d, target=bt.get('target'), cand=cand, ops=ops, fids=fids)


def measure(item, row, x):
    arm, task, g = item[:3]
    c = x['c']
    S = or_q.walk(sampler, task, arm, [g, 0], x['scope'], x['target'], x['sess'], x['d'], x['kind'])
    row['S'] = compact(S)
    rscope, rtarget = r_inputs(c, g, x['sess'])
    R = or_q.walk(sampler, task, arm, [g, 1], rscope, rtarget, x['sess'], x['d'], x['kind'])
    row['R'] = compact(R)
    row['R_target'] = rtarget


def other_slots(item, row, x):
    """S on every other distinct held-with-kind scope of the form."""
    arm, task, g = item[:3]
    out, seen = [], {tuple(x['fids'])}
    for slot, i in x['cand'][1:]:
        r2, x2 = prepare(item, i)
        key = tuple(r2.get('scope_fids') or ())
        if key in seen:
            continue
        seen.add(key)
        e = dict(opening=i, slot_tries=slot, scope_n=r2.get('scope_n'), status=r2['status'], fids=r2.get('scope_fids'))
        if r2['status'] == 'mapped' and not ARGS.nowalk:
            e['S'] = compact(or_q.walk(sampler, task, arm, [g, 0], x2['scope'], x2['target'], x2['sess'], x2['d'], x2['kind']))
            e['S'].pop('atoms', None)
            e['S'].pop('detail', None)
        out.append(e)
    row['all_slots'] = out


def run_form(item):
    t1, c1 = time.time(), time.process_time()
    try:
        row, x = prepare(item)
        if x is not None and row['status'] == 'mapped':
            if not ARGS.nowalk:
                measure(item, row, x)
            if ARGS.all_slots:
                other_slots(item, row, x)
    except Exception as e:  # noqa: BLE001
        row = dict(arm=item[0], task=item[1], g=item[2], source=item[3], status='error', error='%s: %s' % (type(e).__name__, str(e)[:300]))
    row['cpu'] = round(time.process_time() - c1, 2)
    row['wall'] = round(time.time() - t1, 2)
    row['rss_gib'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 30, 3)  # bytes on macOS
    return row


# ---------------------------------------------------------------- manifest

def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def write_manifest():
    path = HERE + '/manifest.json'
    if os.path.exists(path):
        return
    base = KIT + '/model/study/sampler/'
    m = dict(kit=KIT, sampler_paths_REPO=str(sampler_paths.REPO), repo_is_kit=str(sampler_paths.REPO) == KIT,
             code_sha256={f: sha(base + f) for f in ('or_q.py', 'live.py', 'search.py', 'superdag.py', 'superdag_search.py', 'form_orders.py') if os.path.exists(base + f)},
             live_priors_sha256=sha(KIT + '/models-tk/live_priors.pkl'), engine=ENGINE, engine_so=ENGINE + '/arclog/arclog.abi3.so', engine_so_sha256=sha(ENGINE + '/arclog/arclog.abi3.so'),
             engine_note='the run used the wheel of commit e8c1b7882; the Mac build runtime-0a7d32160 differs from it only in engine/lib/study-meanings.json (git diff --stat 0a7d32160 e8c1b7882, outside work/, model/, prompts/, docs/, programs/, data/)',
             points_eval=KIT + '/points-eval.json', points_eval_sha256=sha(KIT + '/points-eval.json'),
             settings=dict(P_DAG='1', ORDER_FREE='tie,key', ARCLOG_IDENT_SOURCE='value', ONE_REPAIR='30', CHOOSE_LIFT='0', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1', STEER_COVER='unset', KEY_IDENT='unset'),
             priors='live.Sampler(KIT/models-tk), default steers', command='bash env.sh job.py --shard I/N ; bash env.sh read.py',
             rule='design.md: top 3 places share of the positive gap, task bootstrap (2000, default_rng(0)), 0.60 bar on the 2.5% point of T3, no gap under 1 bit median')
    json.dump(m, open(path, 'w'), indent=1)


# ---------------------------------------------------------------- main

def recheck():
    rows = [json.loads(l) for l in open(OUT)] if os.path.exists(OUT) else []
    chk_path = OUT.replace('forms', 'checks', 1) if ARGS.out is None else OUT + '.checks'
    done = {(json.loads(l)['arm'], json.loads(l)['task'], json.loads(l)['g']) for l in open(chk_path)} if os.path.exists(chk_path) else set()
    items = {(a, t, g): (a, t, g, s, f) for a, t, g, s, f in build_items()}
    todo = [r for r in rows if r.get('status') == 'mapped' and r.get('S') and r['S']['valid'] and r['S']['orders'].get('exact') and (r['S']['orders'].get('valid') or 0) >= 2 and (r['arm'], r['task'], r['g']) not in done]
    n = 0
    for r in todo[:ARGS.recheck]:
        item = items[(r['arm'], r['task'], r['g'])]
        row, x = prepare(item)
        form = O.Form(x['target'])
        last = form.text(list(itertools.islice(form.orders(), or_q.ORDER_CAP))[-1])
        w7 = or_q.walk(sampler, r['task'], r['arm'], [r['g'], 0], x['scope'], last, x['sess'], x['d'], x['kind'])
        w8 = or_q.walk(sampler, r['task'], r['arm'], [r['g'], 0], x['scope'], x['target'], x['sess'], x['d'], x['kind'])
        e = dict(arm=r['arm'], task=r['task'], g=r['g'], S=r['S']['total'], last_order_total=w7.get('total'), rerun_total=w8.get('total'),
                 c7_ok=abs((w7.get('total') or 1e9) - r['S']['total']) <= 0.01, c8_ok=w8.get('total') == r['S']['total'])
        open(chk_path, 'a').write(json.dumps(e) + '\n')
        print('recheck', e, flush=True)
        n += 1
    print('rechecked %d' % n)


def main():
    if ARGS.recheck is not None:
        return recheck()
    items = [it for it in build_items() if zlib.crc32(it[1].encode()) % SHARD_N == SHARD_I]
    if ARGS.only:
        want = {(x.split(':')[0], int(x.split(':')[1])) for x in ARGS.only.split(',')}
        items = [it for it in items if (it[1], it[2]) in want]
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            x = json.loads(l)
            done.add((x['arm'], x['task'], x['g']))
    todo = [it for it in items if it[:3] not in done]
    total, already = len(items), len(items) - len(todo)
    print('shard %d/%d: %d forms, %d done, %d todo -> %s' % (SHARD_I, SHARD_N, total, already, len(todo), OUT), flush=True)
    write_manifest()
    n = 0
    with open(OUT, 'a') as fh:
        for item in todo:
            if ARGS.budget is not None and time.time() - T0 > ARGS.budget:
                break
            if ARGS.cap is not None and n >= ARGS.cap:
                break
            row = run_form(item)
            fh.write(json.dumps(row, default=str) + '\n')
            fh.flush()
            n += 1
            el = time.time() - T0
            rate = n / el
            rem = len(todo) - n
            print('[%d/%d] %s %s g%d %s S=%s R=%s DB=%s %.1fs | %.2f forms/min, ETA %s' % (already + n, total, item[0], item[1], item[2], row['status'], (row.get('S') or {}).get('total'), (row.get('R') or {}).get('total'),
                  (row.get('DB') or {}).get('bits'), row['wall'], rate * 60, '%.0f s' % (rem / rate) if rem else 'done'), flush=True)
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > RSS_LIMIT:
                print('RSS passed 3 GiB: run it again', flush=True)
                sys.exit(75)
    left = len(todo) - n
    print('done %d todo %d' % (already + n, left), flush=True)


main()

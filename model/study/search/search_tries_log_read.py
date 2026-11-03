"""The read of the tries-log run: for each gold form of the 6 tasks, why a right clause is not in the pool at the end of the job. Standard library only.

  PY -I read.py [RUN_FOLDER] [--out DIR]     (default RUN_FOLDER: run/ beside this file; default DIR: this folder)
  GOLD=path/to/points-eval.json              (default: kit/points-eval.json beside this file)

RUN_FOLDER holds out/<arm>/<task>/work/<task>.out.jsonl.tries (and .cover, <task>.log) as pulled from the pod. Any other layout works too: an arm is the folder name
below out/, else the folder of the file. A task is the file name up to its first dot.

Writes read.out text to stdout, and form-rows.tsv, try-rows.tsv, dead-rows.tsv to DIR. Bits come from bits/<task>.json beside this file (bits6.sh), if there.

Words as in design.md:
  hit          a table of a try whose key equals a gold table's key (how k), or whose digest does, on a table that holds Ident (how d).
  covered      a gold form with a k hit on a try of outcome new or equal. A d hit alone is counted apart (class `digest hit alone`) and does not cover.
  holds        a pool form holds gold table (q, off) where a try of outcome new or equal gave a k hit on it with that pool form as holder.
  right visit  a visit of the form's kind whose scope (fids) holds each form that the gold form reads (right_port: each relation), by the rows before the visit.
"""
import collections
import glob
import hashlib
import json
import os
import platform
import re
import statistics
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD_PATH = os.environ.get('GOLD', HERE + '/kit/points-eval.json')
LN2 = 0.6931471805599453
QUESTION = ('ready', 'input', 'other-kind')
CLASSES = ['equal, other kind', 'failed beside a hit', 'digest hit alone', 'gold table unfinished', 'clause failed', 'clause stopped by a cap', 'dead with a hit', 'scored out', 'never proposed', 'no right tries', 'no right visit']
KINDS = ('RULE', 'DET', 'INIT')

# ---------------------------------------------------------------- clause_key of search.py, copied

TOKEN = re.compile(r'\(|\)|[^\s()]+')
NAME = re.compile(r'&[A-Za-z_0-9]+')
FNAME = re.compile(r'&f(\d+)')


def parse(text):
    stack = [[]]
    for t in TOKEN.findall(text):
        if t == '(':
            stack.append([])
        elif t == ')':
            top = stack.pop()
            stack[-1].append(top)
        else:
            stack[-1].append(t)
    return stack[0]


def flat(x):
    for y in x:
        if isinstance(y, list):
            yield from flat(y)
        else:
            yield y


def draw(x, color, mark=None):
    if isinstance(x, str):
        s = x.lstrip('*')
        if s in color:
            return '@' if s == mark else '#%d' % color[s]
        return x
    parts = [draw(y, color, mark) for y in x]
    if parts and all(isinstance(y, list) for y in x):
        parts.sort()
    elif len(x) > 1 and isinstance(x[0], str) and all(isinstance(y, list) for y in x[1:]):
        parts = parts[:1] + sorted(parts[1:])
    return '(' + ' '.join(parts) + ')'


def atoms_key(atoms):
    parsed = [x if isinstance(x, list) else (parse(x) or [[]])[0] for x in atoms]
    labels = {t[1:] for a in parsed for t in flat(a) if t.startswith('*') and len(t) > 1}
    color = dict.fromkeys(labels, 0)
    where = {l: [a for a in parsed if any(t.lstrip('*') == l for t in flat(a))] for l in labels}
    for _ in range(3):
        color = {l: zlib.crc32('\x1f'.join(sorted(draw(a, color, l) for a in where[l])).encode()) for l in labels}
    return tuple(sorted(draw(a, color) for a in parsed))


_KEYS = {}


def clause_key(text):
    k = _KEYS.get(text)
    if k is None:
        forms = parse(text)
        k = _KEYS[text] = () if not forms or not forms[0] else (forms[0][0],) + atoms_key(forms[0][2:])
    return k


# ---------------------------------------------------------------- gold

def load_gold():
    raw = open(GOLD_PATH, 'rb').read()
    sha = hashlib.sha256(raw).hexdigest()
    G = {}
    for r in json.loads(raw):
        lines = [l for l in r['gold_sexp'].strip().split('\n') if l.strip() and not l.startswith('(OUT')]
        names, kinds, ckey, reads = {}, [], [], []
        for i, line in enumerate(lines):
            found = NAME.findall(line)
            kinds.append(line[1:line.index(' ')])
            mapped = NAME.sub(lambda m: '&g%d' % names[m.group(0)] if m.group(0) in names else m.group(0), line).replace('^', '*')
            ckey.append(clause_key(mapped))
            reads.append({names[n] for n in found[1:] if n in names and n != found[0]})
            names[found[0]] = i
        G[r['task']] = dict(lines=lines, kinds=kinds, ckey=ckey, reads_name=reads)
    return G, sha


def load_bits(task):
    p = '%s/bits/%s.json' % (HERE, task)
    out = {}
    if os.path.exists(p):
        for r in json.load(open(p))['rows']:
            if r.get('skip'):
                continue
            b = r.get('parents') or r.get('before') or {}
            out[r['line']] = (b.get('total'), 1 if b.get('dead') else 0, 1 if b.get('bad') else 0)
    return out


# ---------------------------------------------------------------- one job

def msg_of(y):
    """(message kind, cap name) of a try's why: kind is 1..5 of ValueKind, `step`, `error`, `no table` or `other`."""
    if not y:
        return None, None
    if y == 'no table':
        return 'no table', None
    if y.startswith('error'):
        return 'error', None
    m = re.search(r'kind (\d)', y)
    if m:
        cap = None
        if m.group(1) == '3':
            c = re.search(r'stop (.*?), fault', y)
            cap = c.group(1)[:60] if c else '?'
        return m.group(1), cap
    if 'step gave' in y:
        return 'step', None
    return 'other', None


class Job:
    pass


def analyse(arm, task, path, G):
    gd = G[task]
    n_gold = len(gd['kinds'])
    kinds = gd['kinds']
    J = Job()
    J.arm, J.task, J.path = arm, task, path
    J.bad_lines = 0
    rows = []
    for l in open(path, errors='replace'):
        if not l.strip():
            continue
        try:
            rows.append(json.loads(l))
        except ValueError:
            J.bad_lines += 1
    J.rows = len(rows)
    gtab = {}  # (form, off) -> dict(digests=set, types, fails=list)
    reads_tok = None
    forms = {}  # fid -> (kind, text)
    f2q = {}  # fid -> least gold form whose table it holds
    held_form = collections.defaultdict(set)
    held_rel = collections.defaultdict(set)
    khold = collections.defaultdict(list)  # g -> [(off, holder kind, outcome)]
    ever_rel = set()
    first_k = {}  # g -> outcome of the first k hit
    new_seen = set()
    J.assert3 = []
    J.assert4 = []
    J.procs, J.visits = [], []
    J.tries = []
    buf = dict(T=[], B=[], D=[])
    new_total = 0
    pi = -1

    def flush(unfinished, r=None):
        nonlocal buf
        v = dict(pi=pi, unfinished=unfinished, T=buf['T'], B=buf['B'], D=buf['D'], right_f=set(), right_p=set(), fids=None, kind=None, v=None, tries=None, new=None, end=None, secs=None, bound=None, heap=None, stats={}, seen=None)
        if r:
            v.update(v=r['v'], kind=r['kind'], fids=set(r['fids']), tries=r['tries'], new=r['new'], end=r['end'], secs=r['secs'], bound=r['bound'], heap=r['heap'], stats=r['stats'], seen=r['seen'])
            for g in range(n_gold):
                if kinds[g] != v['kind']:
                    continue
                if all(not v['fids'].isdisjoint(held_form[q]) for q in reads_f.get(g, ())):
                    v['right_f'].add(g)
                if all(not v['fids'].isdisjoint(held_rel[x]) for x in reads_p.get(g, ())):
                    v['right_p'].add(g)
        for t in buf['T']:
            for g, lst in t['k'].items():
                for hk, hf, go in lst:
                    if hf is not None:
                        held_form[g].add(hf)
                        held_rel[(g, go)].add(hf)
        J.visits.append(v)
        buf = dict(T=[], B=[], D=[])

    reads_f = {g: set(gd['reads_name'][g]) for g in range(n_gold)}  # by name until a P row has the reads from tokens
    reads_p = {g: [] for g in range(n_gold)}
    for r in rows:
        k = r['r']
        if k == 'P':
            if buf['T'] or buf['B'] or buf['D']:
                flush(True)
            pi += 1
            n = r['forms']
            J.procs.append(dict(forms=n, new_before=new_total, gold_rows=len(r['gold']), time=r['time'], pfx=None, draws=r['draws']))
            for fid in [x for x in forms if x >= n]:
                del forms[fid]
            for fid in [x for x in f2q if x >= n]:
                del f2q[fid]
            for s in list(held_form.values()) + list(held_rel.values()):
                s.difference_update({x for x in s if x >= n})
            for x in r['gold']:
                e = gtab.setdefault((x['form'], x['off']), dict(digests=set(), types=None, fails=[]))
                if 'fail' in x:
                    e['fails'].append(x['fail'])
                else:
                    e['digests'].add(x['digest'])
                    e['types'] = x['types']
            rd = r.get('reads')
            if rd and 'error' not in rd and reads_tok is None:
                reads_tok = {int(a): sorted({tuple(y) for y in b}) for a, b in rd.items()}
                reads_f = {a: {y[0] for y in b} for a, b in reads_tok.items()}
                reads_p = {a: [tuple(y) for y in b] for a, b in reads_tok.items()}
        elif k == 'T':
            text = r['t']
            tk = text[1:text.index(' ')]
            o = r['o']
            hits = collections.defaultdict(list)
            dset = set()
            for off, got, how, hf, hk in r.get('h', ()):
                for g, go in got:
                    if how == 'k':
                        hits[g].append((hk, hf, go))
                    else:
                        dset.add(g)
            shapes = {g for s in r.get('s', ()) for g in s[1]}
            mapped = FNAME.sub(lambda m: '&g%d' % f2q[int(m.group(1))] if int(m.group(1)) in f2q else m.group(0), text)
            ck = clause_key(mapped)
            chit = {g for g in range(n_gold) if gd['ckey'][g] == ck}
            mk, cap = msg_of(r.get('y'))
            t = dict(pi=pi, v=r['v'], d=r['d'], o=o, tk=tk, q=r['q'], text=text, y=r.get('y'), mk=mk, cap=cap, k=dict(hits), dg=dset, s=shapes, c=chit, hx=bool(r.get('x')), raw=r.get('h', ()))
            buf['T'].append(t)
            J.tries.append(t)
            if o == 'new':
                forms[r['f']] = (tk, text)
                new_total += 1
            for g, lst in hits.items():
                for hk, hf, go in lst:
                    if hf is not None:
                        f2q[hf] = min(f2q.get(hf, g), g)
                    if o in ('new', 'equal'):
                        khold[g].append((go, hk, o))
                        ever_rel.add((g, go))
                if g not in first_k:
                    first_k[g] = o
                    if o != 'new':
                        J.assert4.append((g, o, text[:100]))
                if o == 'new':
                    new_seen.add(g)
                elif o == 'equal' and tk == kinds[g] and g not in new_seen and any(hk == tk for hk, _, _ in lst):
                    J.assert3.append((g, text[:100]))
        elif k == 'B':
            buf['B'].append(dict(g={x[0] for x in r['g']}, p=r['p'], k=r['k'], kind=r['kind'], how=r['how'], barred=r['b'], text=r['t']))
        elif k == 'D':
            buf['D'].append(dict(g={g for h in r.get('h', ()) if h[2] == 'k' for g, _ in h[1]}, y=r.get('y')))
        elif k == 'V':
            flush(False, r)
        elif k == 'C':
            if J.procs:
                J.procs[-1]['pfx'] = r.get('pfx')
    if buf['T'] or buf['B'] or buf['D']:
        flush(True)
    J.new_total = new_total
    J.gtab, J.khold, J.ever_rel = gtab, khold, ever_rel
    J.forms_n = new_total
    J.reads_tok = reads_tok
    J.reads_f, J.reads_p = reads_f, reads_p
    J.reads_name = gd['reads_name']
    J.n_gold = n_gold
    return J


def form_runs(J, G, bits):
    """One record per gold form of the job."""
    gd = G[J.task]
    kinds = gd['kinds']
    n = J.n_gold
    out = []
    covered = [bool(J.khold.get(g)) for g in range(n)]
    held_end = {g: {go for go, _, _ in J.khold.get(g, ())} for g in range(n)}
    tables = {g: sorted(off for (f, off) in J.gtab if f == g) for g in range(n)}
    finished = {g: [off for off in tables[g] if J.gtab[(g, off)]['digests']] for g in range(n)}
    rd = {g: set(J.reads_f.get(g, ())) for g in range(n)}
    rp = {g: list(J.reads_p.get(g, ())) for g in range(n)}

    def has_ident(g, off=None):
        offs = finished[g] if off is None else [off]
        return any('Ident' in str(t) for o in offs if (g, o) in J.gtab for t in (J.gtab[(g, o)]['types'] or ()))

    for g in range(n):
        kind = kinds[g]
        other = covered[g] and not any(hk == kind for _, hk, _ in J.khold[g])
        inp = not rd[g]
        ready = (not covered[g]) and bool(rd[g]) and all(covered[q] for q in rd[g])
        ready_port = (not covered[g]) and bool(rd[g]) and all(x in J.ever_rel for x in rp[g]) if J.reads_tok is not None else ready
        rident = 0
        for q in rd[g]:
            offs = [x[1] for x in rp[g] if x[0] == q]
            if offs:
                rident |= any(has_ident(q, o) for o in offs)
            else:
                rident |= has_ident(q)
        desc = 0
        for h in range(n):
            if g in rd[h] and not covered[h] and all(covered[q] for q in rd[h] if q != g):
                desc += 1
        b = bits.get(g, (None, 0, 0))
        r = dict(arm=J.arm, task=J.task, g=g, kind=kind, reads=sorted(rd[g]), ident=int(has_ident(g)), read_ident=int(bool(rident)), input=int(inp), ready=int(ready), ready_port=int(ready_port),
                 covered=int(covered[g]), tables_held=len(held_end[g]), tables=len(tables[g]), other_kind=int(other), unfinished=int(not finished[g]), desc=desc, bits=b[0], bits_dead=b[1], bits_bad=b[2],
                 text=gd['lines'][g].replace('\t', ' '))
        for lv, key in (('f', 'right_f'), ('p', 'right_p')):
            if other:
                st = 'other-kind'
            elif covered[g]:
                st = 'covered'
            elif inp:
                st = 'input'
            elif (ready if lv == 'f' else ready_port):
                st = 'ready'
            else:
                st = 'blocked'
            r['set_' + lv] = st
            r['scan_' + lv] = scan(J, g, kind, key, covered[g])
        r['class_f'] = classify(r, 'f')
        r['class_p'] = classify(r, 'p')
        out.append(r)
    return out


def scan(J, g, kind, key, cov):
    S = collections.Counter()
    S['caps'] = collections.Counter()
    S['gaps'] = []
    for v in J.visits:
        if v['unfinished'] or g not in v[key]:
            continue
        S['rv'] += 1
        for t in v['T']:
            S['rt'] += 1
            o = t['o']
            if o == 'none':
                S['none_' + str(t['mk'])] += 1
            else:
                S[o] += 1
            kh, dh, ch, sh = g in t['k'], g in t['dg'], g in t['c'], g in t['s']
            S['thit'] += kh or dh
            S['khit'] += kh
            S['dhit'] += dh
            S['chit'] += ch
            S['chit_nt'] += ch and not (kh or dh)
            S['shape'] += sh
            if kh and o == 'equal' and t['tk'] == kind and any(hk != kind for hk, _, _ in t['k'][g]):
                S['eq_other'] += 1
            if kh and o == 'none':
                S['failed_beside'] += 1
            if dh:
                S['dig'] += 1
            if ch and o == 'none':
                if t['mk'] in ('1', '3', 'no table'):
                    S['ccap'] += 1
                    S['caps'][t['cap'] or t['mk']] += 1
                else:
                    S['cfail'] += 1
        for b in v['B']:
            if g in b['g']:
                S['pre'] += 1
                S['gaps'].append((v, b))
        for d in v['D']:
            if g in d['g']:
                S['dead'] += 1
    return S


def classify(r, lv):
    st = r['set_' + lv]
    S = r['scan_' + lv]
    if st not in QUESTION:
        return '-' if st == 'covered' else 'blocked'
    if st == 'other-kind' and S['eq_other']:
        return 'equal, other kind'
    if S['failed_beside']:
        return 'failed beside a hit'
    if S['dig'] and not r['covered']:
        return 'digest hit alone'
    if r['unfinished']:
        return 'gold table unfinished'
    if S['cfail']:
        return 'clause failed'
    if S['ccap']:
        return 'clause stopped by a cap'
    if S['dead']:
        return 'dead with a hit'
    if S['pre'] and not S['thit']:
        return 'scored out'
    if S['rt']:
        return 'never proposed'
    if S['rv']:
        return 'no right tries'
    return 'no right visit'


# ---------------------------------------------------------------- output

def fmt(rows, cols, align=None):
    """A text table. rows: lists of cells."""
    cells = [[str(c) for c in cols]] + [[str(c) for c in r] for r in rows]
    w = [max(len(r[i]) for r in cells) for i in range(len(cols))]
    out = []
    for i, r in enumerate(cells):
        out.append('  '.join(c.ljust(w[j]) if j == 0 or not (c.replace('.', '', 1).lstrip('-').isdigit()) else c.rjust(w[j]) for j, c in enumerate(r)).rstrip())
        if i == 0:
            out.append('  '.join('-' * x for x in w))
    return '\n'.join(out)


def median(xs):
    return round(statistics.median(xs), 2) if xs else ''


def main():
    args = [a for a in sys.argv[1:]]
    outdir = HERE
    if '--out' in args:
        i = args.index('--out')
        outdir = args[i + 1]
        del args[i:i + 2]
    root = (args[0] if args else HERE + '/run').rstrip('/')
    os.makedirs(outdir, exist_ok=True)
    G, gold_sha = load_gold()
    files = sorted(glob.glob(root + '/**/*.tries', recursive=True))
    if not files:
        sys.exit('no .tries file under ' + root)
    man = {}
    for p in (root + '/manifest.json', HERE + '/manifest.json'):
        if os.path.exists(p):
            man = json.load(open(p))
            break
    jobs, runs = [], []
    for f in files:
        task = os.path.basename(f).split('.')[0]
        m = re.search(r'/out/([^/]+)/', f[len(root):])
        arm = m.group(1) if m else os.path.basename(os.path.dirname(f))
        if m is None and os.path.basename(os.path.dirname(f)) in ('work',):
            arm = os.path.basename(os.path.dirname(os.path.dirname(f)))
        if task not in G:
            print('skip (no gold)', f)
            continue
        J = analyse(arm, task, f, G)
        J.log = f.rsplit('.out.jsonl.tries', 1)[0] + '.log'
        J.cover = f[:-len('.tries')] + '.cover'
        jobs.append(J)
        runs += form_runs(J, G, load_bits(task))
    arms = sorted({J.arm for J in jobs})
    arm_groups = arms + (['both'] if len(arms) > 1 else [])
    tasks = sorted({J.task for J in jobs})
    wh = man.get('wheel_engine', {})
    wheels = ', '.join('%s %s' % (k, str(v.get('sha256', ''))[:8]) for k, v in wh.items()) if isinstance(wh, dict) and wh and all(isinstance(v, dict) for v in wh.values()) else 'wheels not in a manifest'
    budget = re.search(r'(\d+) s', man.get('budget', '') or '')
    header = 'gold %s sha256 %s, %d held-out tasks, seed 1, %s, models-current, pod CPU %s, arms %s, %s, read on the Mac, %s %s %s' % (
        (man.get('gold') or {}).get('name') or GOLD_PATH, gold_sha[:8], len(tasks), (budget.group(1) + ' s') if budget else 'budget not in a manifest',
        man.get('pod_cpu') or 'not recorded', '/'.join(arms), wheels, platform.system(), platform.release(), platform.machine())
    P = []

    def title(t):
        P.append('')
        P.append('## ' + t)
        P.append(header)
        P.append('')

    P.append('# tries-log read of %s' % root)
    P.append('%d job files; arms %s; tasks %s' % (len(jobs), arms, tasks))

    # ------------------------------------------------ checks
    title('Checks')
    chk = []
    for J in jobs:
        name = '%s/%s' % (J.arm, J.task)
        nT = len(J.tries)
        nV = sum(v['tries'] for v in J.visits if not v['unfinished'])
        nTf = sum(len(v['T']) for v in J.visits if not v['unfinished'])
        unfin = sum(len(v['T']) for v in J.visits if v['unfinished'])
        gen_ok = all(p['forms'] == p['new_before'] for p in J.procs)
        # P rows were merged by table, so a table with several digests changed between processes
        dig_bad = sum(1 for e in J.gtab.values() if len(e['digests']) > 1)
        log = open(J.log, errors='replace').read() if os.path.exists(J.log) else None
        gens = [int(m.group(1)) for m in re.finditer(r'^generation \d+: .*?(\d+) forms,', log, re.M)] if log else None
        tb = log.count('Traceback') if log is not None else 'no log'
        cover = [json.loads(l) for l in open(J.cover) if l.strip()] if os.path.exists(J.cover) else []
        cmiss = sum(1 for c in cover if not any(t['d'] == c['draw'] and c['gold'] in t['k'] for t in J.tries))
        pf = collections.Counter()
        for p in J.procs:
            pf.update(p['pfx'] or {})
        base_like = bool(pf)
        tok_diff = None
        if J.reads_tok is not None:
            tok_diff = sum(1 for g in range(J.n_gold) if set(J.reads_f.get(g, ())) != set(J.reads_name[g]))
        chk.append([name, J.rows, len(J.procs), J.procs[0]['gold_rows'] if J.procs else 0, nT, nV, nTf, unfin, 'yes' if gen_ok else 'NO',
                    (gens == [p['forms'] for p in J.procs]) if gens is not None else 'no log', dig_bad, tb, '%d/%d' % (cmiss, len(cover)),
                    ('%.3f' % (pf['same'] / max(1, pf['same'] + pf['other'])) if base_like else '-'), tok_diff if tok_diff is not None else 'no reads row',
                    len(J.assert3), len(J.assert4), J.bad_lines])
    P.append(fmt(chk, ['job', 'rows', 'procs', 'gold rows', 'T rows', 'V tries', 'T in done visits', 'T in cut visit', 'forms=new rows', 'forms=log gens', 'tables with 2+ digests', 'Traceback',
                       'cover lines with no T', 'pfx same share', 'reads tok!=name', 'assert3 fails', 'assert4 fails', 'bad lines']))
    P.append('')
    P.append('T in done visits must equal V tries. A job with prefix rows has a pfx share; evict has none ("-"). A forms=new rows of NO means a process died: read fid by the last process (this read prunes fid above P forms at a process start).')
    for J in jobs:
        for g, t in J.assert3[:3]:
            P.append('assert3 %s/%s form %d: %s' % (J.arm, J.task, g, t))
        for g, o, t in J.assert4[:3]:
            P.append('assert4 %s/%s form %d first k hit is %s: %s' % (J.arm, J.task, g, o, t))
    sup = sorted(glob.glob(root + '/**/supervisor.log', recursive=True))
    P.append('supervisor.log files %d, with Traceback %d' % (len(sup), sum('Traceback' in open(s, errors='replace').read() for s in sup)))
    miss = [(J.arm, J.task) for J in jobs if J.reads_tok is None]
    if miss:
        P.append('jobs whose P row has no reads (reads taken by name): %s' % miss)

    # ------------------------------------------------ outcome by form-run
    def groups(rs, lv):
        sets = list(QUESTION)
        for arm in arm_groups:
            ra = [r for r in rs if arm == 'both' or r['arm'] == arm]
            for st in sets + ['all']:
                rst = [r for r in ra if r['set_' + lv] in (QUESTION if st == 'all' else (st,))]
                for kd in KINDS + ('all',):
                    rk = [r for r in rst if kd == 'all' or r['kind'] == kd]
                    for idn in ('holds', 'none', 'all'):
                        rr = [r for r in rk if idn == 'all' or (r['ident'] == 1) == (idn == 'holds')]
                        if rr:
                            yield arm, st, kd, idn, rr

    for lv, nm in (('f', 'form level: ready, right_visits'), ('p', 'port level: ready_port, right_port')):
        title('Outcome by form-run, ' + nm)
        tab = []
        for arm, st, kd, idn, rr in groups(runs, lv):
            c = collections.Counter(r['class_' + lv] for r in rr)
            tab.append([arm, st, kd, idn, len(rr), len({(r['task'], r['g']) for r in rr})] + [c[x] for x in CLASSES])
        P.append(fmt(tab, ['arm', 'set', 'kind', 'Ident', 'form-runs', 'forms'] + CLASSES))

    # ------------------------------------------------ right tries by outcome
    title('Right tries by outcome, form level')
    tab = []
    for arm, st, kd, idn, rr in groups(runs, 'f'):
        S = collections.Counter()
        for r in rr:
            s = r['scan_f']
            for k in ('rv', 'rt', 'new', 'equal', 'none_1', 'none_2', 'none_3', 'none_4', 'none_5', 'none_no table', 'none_error', 'none_step', 'none_other', 'none_None', 'thit', 'chit', 'chit_nt', 'shape', 'pre'):
                S[k] += s[k]
        tab.append([arm, st, kd, idn, S['rv'], S['rt'], S['new'], S['equal'], S['none_1'], S['none_2'], S['none_3'], S['none_4'], S['none_5'], S['none_no table'], S['none_error'],
                    S['none_step'] + S['none_other'] + S['none_None'], S['thit'], S['chit'], S['chit_nt'], S['shape'], S['pre']])
    P.append(fmt(tab, ['arm', 'set', 'kind', 'Ident', 'right visits', 'right tries', 'new', 'equal', 'none k1', 'k2', 'k3', 'k4', 'k5', 'no table', 'error', 'none other', 'table hits', 'clause hits', 'clause no table',
                       'shape hits', 'prefix rows']))
    P.append('')
    P.append('Counts are summed over form-runs, so a try right for two forms counts twice. none k1..k5 is the ValueKind of the failed relation; "none other" holds step gave, table fault and unlisted.')

    # ------------------------------------------------ visits: right for a question form
    for J in jobs:
        qg = {r['g'] for r in runs if r['arm'] == J.arm and r['task'] == J.task and r['set_f'] in QUESTION}
        for v in J.visits:
            v['rq'] = bool(not v['unfinished'] and (v['right_f'] & qg))
    allv = [(J, v) for J in jobs for v in J.visits if not v['unfinished']]

    # ------------------------------------------------ dead paths
    dead = collections.defaultdict(lambda: collections.Counter())
    for J, v in allv:
        for k, n in v['stats'].items():
            if not k.startswith('dead:'):
                continue
            nk = re.sub(r'\d+', 'N', k)
            dead[nk]['all'] += n
            dead[nk]['all_' + v['kind']] += n
            if v['rq']:
                dead[nk]['right'] += n
                dead[nk]['right_' + v['kind']] += n
    title('Dead paths, by reason (top 25 by right visits; all in dead-rows.tsv)')
    dr = sorted(dead.items(), key=lambda kv: (-kv[1]['right'], -kv[1]['all'], kv[0]))
    P.append(fmt([[k, c['right'], c['all']] + [c['right_' + x] for x in KINDS] + [c['all_' + x] for x in KINDS] for k, c in dr[:25]],
                 ['reason', 'right visits', 'all visits'] + ['right ' + x for x in KINDS] + ['all ' + x for x in KINDS]))
    with open(outdir + '/dead-rows.tsv', 'w') as w:
        w.write('\t'.join(['reason', 'right_visits', 'all_visits'] + ['right_' + x for x in KINDS] + ['all_' + x for x in KINDS]) + '\n')
        for k, c in dr:
            w.write('\t'.join(str(x) for x in [k, c['right'], c['all']] + [c['right_' + y] for y in KINDS] + [c['all_' + y] for y in KINDS]) + '\n')

    # ------------------------------------------------ visit ends
    title('Visit ends, in right groups (a visit that is right for a question form) and in all visits')
    ends = collections.defaultdict(lambda: dict(rv=[], av=[]))
    for J, v in allv:
        e = ends[v['end']]
        e['av'].append(v)
        if v['rq']:
            e['rv'].append(v)
    P.append(fmt([[k, len(e['rv']), sum(x['tries'] for x in e['rv']), sum(1 for x in e['rv'] if not x['tries']), median([x['secs'] for x in e['rv']]),
                   len(e['av']), sum(x['tries'] for x in e['av']), sum(1 for x in e['av'] if not x['tries']), median([x['secs'] for x in e['av']])] for k, e in sorted(ends.items())],
                 ['end', 'right visits', 'tries', 'with 0 tries', 'median s', 'all visits', 'tries', 'with 0 tries', 'median s']))

    # ------------------------------------------------ failure messages
    title('Failure messages, by clause kind (full list)')
    fm = collections.defaultdict(collections.Counter)
    for J in jobs:
        for t in J.tries:
            if t['y']:
                fm[re.sub(r'\d+', 'N', t['y'])[:120]][t['tk']] += 1
    P.append(fmt([[k, sum(c.values())] + [c[x] for x in KINDS] for k, c in sorted(fm.items(), key=lambda kv: -sum(kv[1].values()))], ['message', 'tries'] + list(KINDS)))

    # ------------------------------------------------ sizes
    title('Sizes of a fix by class (both arms; the bar is 3 distinct forms on 2 tasks)')
    alltries = sum(len(J.tries) for J in jobs)
    tab = []
    for cl in CLASSES:
        rr = [r for r in runs if r['class_f'] == cl]
        forms = {(r['task'], r['g']) for r in rr}
        tasks_c = {r['task'] for r in rr}
        desc = sum(r['desc'] for r in {(r['task'], r['g']): r for r in rr}.values())
        bar = len(forms) >= 3 and len(tasks_c) >= 2
        bits = [r['bits'] for r in rr if r['bits'] is not None]
        tab.append([cl, len(rr), len(forms), len(tasks_c), 'yes' if bar else 'closed', desc, median(bits) if cl == 'never proposed' else '', sum(r['scan_f']['rt'] for r in rr) if cl == 'never proposed' else ''])
    P.append(fmt(tab, ['class', 'form-runs', 'distinct forms', 'tasks', 'bar', 'descendants', 'median bits (never proposed)', 'right tries (never proposed)']))
    P.append('')
    eqo = sum(1 for J in jobs for t in J.tries if t['o'] == 'equal' and any(hk != t['tk'] for hits in t['k'].values() for hk, _, _ in hits))
    fx = sum(1 for J in jobs for t in J.tries if t['hx'])
    fxh = sum(1 for J in jobs for t in J.tries if t['hx'] and (t['k'] or t['dg']))
    dtries = sum(1 for J in jobs for t in J.tries if t['dg'])
    P.append('Costs, over %d tries: equal with a gold-table holder of another kind %d (%.2f%%); tries with a failed relation %d, of them with a gold-table hit %d; tries with a d hit %d; D rows with a hit %d.' % (
        alltries, eqo, 100.0 * eqo / max(1, alltries), fx, fxh, dtries, sum(1 for J in jobs for v in J.visits for d in v['D'] if d['g'])))
    caps = collections.Counter()
    for r in runs:
        if r['class_f'] == 'clause stopped by a cap':
            caps.update(r['scan_f']['caps'])
    P.append('Caps named in clause stopped by a cap: %s' % dict(caps))
    gaps = []
    for r in runs:
        if r['class_f'] == 'scored out':
            last = {}
            J = next(j for j in jobs if j.arm == r['arm'] and j.task == r['task'])
            for v in J.visits:
                if not v['unfinished']:
                    last[(v['kind'], tuple(sorted(v['fids'])))] = v['bound']
            best = None
            for v, b in r['scan_f']['gaps']:
                lb = last.get((v['kind'], tuple(sorted(v['fids']))))
                if lb is not None:
                    gp = (lb - b['p']) / LN2
                    best = gp if best is None else min(best, gp)
            if best is not None:
                gaps.append(best)
    P.append('Scored out: gap in bits from the prefix path chance p to the slot last bound, least per form-run: %s' % sorted(round(x, 2) for x in gaps))

    # ------------------------------------------------ clause hits with no table hit
    title('Clause hits with no table hit (first 40)')
    n = 0
    for J in jobs:
        for t in J.tries:
            for g in sorted(t['c']):
                if g not in t['k'] and g not in t['dg']:
                    n += 1
                    if n <= 40:
                        P.append('%s/%s form %d outcome %s why %s: %s' % (J.arm, J.task, g, t['o'], t['y'], t['text'][:200]))
    P.append('total %d' % n)

    # ------------------------------------------------ prediction lines, measured
    title('Numbers for the prediction lines')
    q = [r for r in runs if r['set_f'] in QUESTION]
    cq = collections.Counter(r['class_f'] for r in q)
    P.append('form-runs: %d; question set (ready, input, other-kind): %d; by set %s' % (len(runs), len(q), dict(collections.Counter(r['set_f'] for r in runs))))
    P.append('question form-runs by class: %s' % dict(cq))
    if q:
        P.append('never proposed or no right tries or no right visit, share of question form-runs: %.3f; never proposed alone: %.3f' % ((cq['never proposed'] + cq['no right tries'] + cq['no right visit']) / len(q), cq['never proposed'] / len(q)))
    qi = [r for r in q if r['ident']]
    if qi:
        ci = collections.Counter(r['class_f'] for r in qi)
        P.append('Ident form-runs in the question set: %d; never proposed %.3f; digest hit alone %d; with a shape hit try %d (%.3f)' % (
            len(qi), ci['never proposed'] / len(qi), ci['digest hit alone'], sum(1 for r in qi if r['scan_f']['shape']), sum(1 for r in qi if r['scan_f']['shape']) / len(qi)))
    rd_ = [r for r in q if r['kind'] in ('RULE', 'DET')]
    if rd_:
        P.append('RULE and DET question form-runs: %d; with a body prefix row in a right group: %d (%.3f)' % (len(rd_), sum(1 for r in rd_ if r['scan_f']['pre']), sum(1 for r in rd_ if r['scan_f']['pre']) / len(rd_)))
    P.append('other-kind set form-runs: %d' % sum(1 for r in runs if r['set_f'] == 'other-kind'))
    P.append('forms with a d hit on a table of Ident and no k hit: %d' % sum(1 for r in runs if r['scan_f']['dhit'] and not r['covered']))

    print('\n'.join(P))

    # ------------------------------------------------ tsv
    cols = ['arm', 'task', 'form', 'kind', 'reads', 'ident', 'read_ident', 'input', 'ready', 'ready_port', 'covered', 'tables_held', 'tables', 'other_kind', 'class', 'class_port', 'right_visits', 'right_visits_port',
            'right_tries', 'table_hits', 'clause_hits', 'shape_hits', 'prefix_rows', 'bits', 'bits_dead', 'bits_bad', 'descendants', 'text']
    with open(outdir + '/form-rows.tsv', 'w') as w:
        w.write('\t'.join(cols) + '\n')
        for r in runs:
            s, sp = r['scan_f'], r['scan_p']
            w.write('\t'.join(str(x) for x in [r['arm'], r['task'], r['g'], r['kind'], ','.join(map(str, r['reads'])), r['ident'], r['read_ident'], r['input'], r['ready'], r['ready_port'], r['covered'],
                                               r['tables_held'], r['tables'], r['other_kind'], r['class_f'], r['class_p'], s['rv'], sp['rv'], s['rt'], s['thit'], s['chit'], s['shape'], s['pre'],
                                               '' if r['bits'] is None else round(r['bits'], 2), r['bits_dead'], r['bits_bad'], r['desc'], r['text']]) + '\n')
    with open(outdir + '/try-rows.tsv', 'w') as w:
        w.write('\t'.join(['arm', 'task', 'form', 'level', 'v', 'd', 'o', 'why', 'how', 'holder_kind', 'q', 'text']) + '\n')
        for J in jobs:
            for t in J.tries:
                base = [J.arm, J.task]
                tail = ['%d.%d' % (t['pi'], t['v']), t['d'], t['o'], (t['y'] or '').replace('\t', ' ')]
                for g, lst in sorted(t['k'].items()):
                    w.write('\t'.join(str(x) for x in base + [g, 'table'] + tail + ['k', lst[0][0], t['q'], t['text']]) + '\n')
                for g in sorted(t['dg']):
                    w.write('\t'.join(str(x) for x in base + [g, 'table'] + tail + ['d', '', t['q'], t['text']]) + '\n')
                for g in sorted(t['c']):
                    w.write('\t'.join(str(x) for x in base + [g, 'clause'] + tail + ['', '', t['q'], t['text']]) + '\n')


if __name__ == '__main__':
    main()

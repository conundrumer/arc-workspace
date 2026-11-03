"""The held map's rows: the facts of every visit's scope, each cover event's visit, and each gold form's exposure in the visits that hold its read forms. It follows build-rows.py of sampler-base-cost-read-heldout37. It streams, and a rerun skips finished runs.

Reads, per arm and task: .visits, .out.jsonl.cover and .out.jsonl.bank under sampler-pool-extended-text-pass1-600s/out-all37. Those paths are links into folders named out/.

  map-visit-rows.tsv     arm, task, visit, kind, resume, tries, missing (scope forms not in the bank), the facts of the scope
  map-cover-rows.tsv     arm, task, form, kind, draw, first, visit
  map-exposure-rows.tsv  arm, task, form, visit, n: tries in that visit up to the form's first cover, in visits that hold its read forms

With --test-replay, it reads only the replay-out folders of that record: their bank copies and .visits, with no covers. It writes replay-visit-rows.tsv.

It runs on the engine's python: a scope form's column types come from the engine's render, as on gold rows.
"""
import collections
import csv
import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/'
sys.path.insert(0, HERE)
sys.path.insert(1, BASE)
import arclog  # noqa: E402
import read_common as C  # noqa: E402
import scope_facts as F  # noqa: E402
CUT = 600.0
NEW = {x['task']: x['gold_sexp'] for x in json.load(open(C.K + 'points-eval.json'))}
ALIAS = {}
for l in open(BASE + 'gold-dups.jsonl'):
    q = json.loads(l)
    ALIAS[q['task']] = q
tasks = open(C.W + 'held/tasks.txt').read().split()


def gold_forms(t):
    lines = [l for l in NEW[t].strip().split('\n') if not l.startswith('(OUT')]
    head, reads = {}, []
    for i, x in enumerate(lines):
        names = re.findall(r'&r\d+', x)
        h = names[0]
        reads.append(sorted({head[m] for m in names[1:] if m in head and m != h}))
        head[h] = i
    q = ALIAS[t]
    nk = set(q['no_key'])
    out, unk = [], []
    for r in reads:
        got, u = set(), 0
        for m in r:
            if m not in nk:
                got.add(m)
            elif q['alias'][str(m)]:
                got |= set(q['alias'][str(m)])
            else:
                u = 1
        out.append(sorted(got))
        unk.append(u)
    return lines, out, unk


def render_cols(text):
    """{line number: set of column types} from the engine's render, as in build-gold-rows.py."""
    got = {}
    for e in json.loads(arclog.StudyProgram.from_sexp(text, arclog.DecodeSettings()).render_json())['definitions']['native_relations']:
        for w in e.get('column_witnesses') or ():
            x = (w.get('physical_type') or {}).get('type') or w.get('type')
            if x:
                got.setdefault(e['definition_path'][0], set()).add(x)
    return got


def form_dicts(st):
    """The bank's forms as scope_facts dicts: all of it is what the search has at the draw of a later form. A form's cols come at its first scope, from the render."""
    out = {}
    for fid, f in st['forms'].items():
        kind, head, key = F.parse_form(f.text)
        out[fid] = dict(i=fid, kind=f.kind, depth=f.depth, parents=list(f.parents), head=head, key=key, cols=None)
    return out


COUNTS = collections.Counter()


def fill_cols(fd, st, k):
    """Column types of the scope's forms from one render of the scope; where that fails, each form with its ancestors; where that fails, the table types of the form's nodes."""
    have = [f for f in k if f in fd]
    if all(fd[f]['cols'] is not None for f in have):
        return
    try:
        got = render_cols('\n'.join(st['forms'][f].text for f in have) + '\n(OUT (input ^P ^Col))')
        for n, f in enumerate(have):
            fd[f]['cols'] = got.get(n, set())
        COUNTS['scope renders'] += 1
        return
    except Exception:  # noqa: BLE001
        COUNTS['scope render failed'] += 1
    for f in have:
        if fd[f]['cols'] is not None:
            continue
        chain = sorted(F.closure(fd, [f]), key=lambda x: (fd[x]['depth'], x)) if all(x in fd for x in fd[f]['parents']) else [f]
        try:
            fd[f]['cols'] = render_cols('\n'.join(st['forms'][x].text for x in chain) + '\n(OUT (input ^P ^Col))').get(chain.index(f), set())
        except Exception:  # noqa: BLE001
            COUNTS['form render failed'] += 1
            cols = set()
            for n in getattr(st['forms'][f], 'nodes', ()) or ():
                cols |= set(st['nodes'][n].table_types)
            fd[f]['cols'] = cols


def scope_facts_of(fd, st, fids, cache):
    k = tuple(fids)
    if k not in cache:
        fill_cols(fd, st, k)
        S = [fd[f] for f in k if f in fd]
        cache[k] = F.facts(S), len(k) - len(S)
    return cache[k]


def one(arm, t, wr):
    d = '%s%s/%s' % (C.A, arm, t)
    base = float(open(d + '/start').read())
    work = d + '/work/'
    st = C.bank(glob.glob(work + '*.out.jsonl.bank')[0])
    fd = form_dicts(st)
    age = collections.defaultdict(set)
    for n in st['nodes'].values():
        age[n.age].add(n.form)
    visits = []
    for p in glob.glob(work + '*.visits'):
        for l in open(p):
            try:
                visits.append(json.loads(l))
            except ValueError:
                continue
    visits.sort(key=lambda v: v['time'])
    covs = []
    for p in glob.glob(work + '*.out.jsonl.cover'):
        for l in open(p):
            try:
                covs.append(json.loads(l))
            except ValueError:
                pass
    covs.sort(key=lambda c: c['time'])
    lines, reads, unknown = gold_forms(t)
    p2g = collections.defaultdict(set)
    for c in covs:
        for f in age.get(c['draw'], ()):
            p2g[f].add(c['gold'])
    cum, cache = 0, {}
    for j, v in enumerate(visits):
        v['j'] = j
        v['t'] = v['time'] - base
        v['d0'], v['d1'] = cum, cum + v['tries']
        cum += v['tries']
        v['held'] = set()
        for f in v['fids']:
            v['held'] |= p2g.get(f, set())
        q, miss = scope_facts_of(fd, st, v['fids'], cache)
        wr['visit'].writerow([arm, t, j, v['kind'], int(v['resume']), v['tries'], miss] + [q[x] for x in F.FACTS])
    vis600 = [v for v in visits if v['t'] <= CUT]
    first = {}
    for c in covs:
        if c['time'] - base <= CUT:
            cur = first.get(c['gold'])
            if cur is None or c['draw'] < cur['draw']:
                first[c['gold']] = c
    for c in covs:
        i = next((j for j, v in enumerate(visits) if v['time'] >= c['time'] - 1e-6), None)
        k = F.parse_form(lines[c['gold']])[0]
        wr['cover'].writerow([arm, t, c['gold'], k, c['draw'], int(first.get(c['gold']) is c), '' if i is None else i])
    for g in range(len(lines)):
        fc = first.get(g)
        r = set(reads[g])
        for v in vis600:
            n = v['tries']
            hit = fc is not None and v['d0'] < fc['draw'] <= v['d1']
            if hit:
                n = fc['draw'] - v['d0']
            if not unknown[g] and r <= v['held'] and n:
                wr['exposure'].writerow([arm, t, g, v['j'], n])
            if hit:
                break


HEAD = dict(visit=['arm', 'task', 'visit', 'kind', 'resume', 'tries', 'missing'] + list(F.FACTS), cover=['arm', 'task', 'form', 'kind', 'draw', 'first', 'visit'], exposure=['arm', 'task', 'form', 'visit', 'n'])


def test_replay():
    out = csv.writer(open(HERE + 'replay-visit-rows.tsv', 'w', newline=''), delimiter='\t')
    out.writerow(['task', 'kind', 'resume', 'tries', 'missing', 'scope_forms'] + list(F.FACTS))
    for d in sorted(glob.glob(BASE + 'replay-out/base_s0-*')):
        t = d.split('-')[-1]
        st = C.bank(d + '/bank')
        fd = form_dicts(st)
        cache = {}
        for l in open(d + '/out.jsonl.visits'):
            v = json.loads(l)
            q, miss = scope_facts_of(fd, st, v['fids'], cache)
            out.writerow([t, v['kind'], int(v['resume']), v['tries'], miss, len(v['fids'])] + [q[x] for x in F.FACTS])
    print(dict(COUNTS), flush=True)


class Rows(list):
    writerow = list.append


def main():
    if '--test-replay' in sys.argv:
        test_replay()
        return
    files = {k: HERE + 'map-%s-rows.tsv' % k for k in HEAD}
    done_path = HERE + 'map-done.txt'
    done = set(open(done_path).read().split('\n')) if os.path.exists(done_path) else set()
    new = not os.path.exists(files['visit'])
    if not new:  # a run killed before its log line may have left rows: keep only the rows of finished runs
        for p in files.values():
            with open(p) as f:
                keep = [l for i, l in enumerate(f) if i == 0 or ' '.join(l.split('\t')[:2]) in done]
            with open(p, 'w') as f:
                f.writelines(keep)
    fh = {k: open(p, 'a', newline='') for k, p in files.items()}
    wr = {k: csv.writer(f, delimiter='\t') for k, f in fh.items()}
    if new:
        for k in HEAD:
            wr[k].writerow(HEAD[k])
    todo = ['%s %s' % (a, t) for a in C.ARMS for t in tasks if '%s %s' % (a, t) not in done]
    t0, n = time.time(), 0
    log = open(done_path, 'a')
    for x in todo:
        arm, t = x.split()
        got = {k: Rows() for k in HEAD}  # a run's rows go to the files together, after the run
        one(arm, t, got)
        for k, f in fh.items():
            wr[k].writerows(got[k])
            f.flush()
        log.write(x + '\n')
        log.flush()
        n += 1
        rate = n / (time.time() - t0)
        print('%d of %d runs, %.2f runs per s, eta %.0f s, %s' % (n, len(todo), rate, (len(todo) - n) / rate, dict(COUNTS)), flush=True)


main()

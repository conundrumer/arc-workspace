"""The exact bits of each residual INIT of form-set.jsonl in its rewritten program, by part, with one row per read of the form.

  census_env.sh init_residual_bits.py [--limit N]

Writes rows.jsonl in this folder: one row per form as soon as it is walked, flushed. A rerun skips the forms that have a row. It prints a rate and an ETA.

The program is built as form_try.py builds it: the census text with the trial's replace applied, then its normal form. The walk is or_q.walk over every form before the INIT, on a session of its own, as scripts/arclog_bits.py does in exact mode, with the census's priors and steers. Its record's `parts` are kept by the walk's own labels; read_rows.py groups them. GuidedRun is subclassed only to record, at each port and body, what the walk already holds: the rows stay those of or_q.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import time

os.environ['ARCLOG_THREADS'] = '1'
sys.path.insert(0, os.environ['SAMPLER_CODE'])
sys.path.insert(0, os.environ['ARC_ROOT'] + '/scripts')
import arclog  # noqa: E402
import arclog_bits as B  # noqa: E402
import live  # noqa: E402
import live_try  # noqa: E402
import or_q  # noqa: E402
import search_gold as G  # noqa: E402
from live import ANY_TYPE, M  # noqa: E402

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-init-residual-bits-split-74forms/'  # the data folder
ROOT = os.environ['ARC_ROOT']
ENGINE_SO = ROOT + '/work/lm/data-study/ast/run/runtime-ba0754492/py313-path/arclog/arclog.abi3.so'
SO_SHA256_16 = '4538e2630f39d751'  # census-bands-cheapest/manifest.json, wheel_engine
CODE = ('live.py', 'or_q.py', 'search.py', 'search_gold.py', 'live_try.py')
HEAD = re.compile(r'^\((\w+)\s+(&[A-Za-z_0-9]+)')
NAME = re.compile(r'&[A-Za-z_0-9]+')


def session(task):
    return arclog.Session(arclog.Task.from_json(open('%s/data/tasks/%s.json' % (ROOT, task)).read(), arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))


def stream(sess, text):
    i, m, _ = arclog.StudyProgram.from_sexp(text, sess.settings).decode_stream()
    return [int(x) for x in i], [int(bool(x)) for x in m]


def normal_lines(row):
    """The lines of the normal form of the rewritten program, as form_try.run has them."""
    ls = list(row['lines'])
    for i, new in sorted(row['replace'], key=lambda x: -x[0]):
        ls[i:i + 1] = new
    sess = session(row['task'])
    norm = arclog.StudyProgram.from_stream(sess, *stream(sess, '\n'.join(ls))).sexp()
    return [x for x in norm.splitlines() if x.strip()]


class CaptureRun(or_q.GuidedRun):
    """GuidedRun that keeps a list of the bodies that the walk enters."""
    last = None

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        CaptureRun.last = self
        self.bodies, self.now = [], None

    def port(self, pg, f, comp, name, cols, params, nlab, keys, fields, outside=False):
        self.now = dict(comp=comp, name=name, cols=[list(c) for c in cols], params=sorted(params), key_types=[t for t in keys.values()], outside=outside)
        try:
            return super().port(pg, f, comp, name, cols, params, nlab, keys, fields, outside)
        finally:
            self.now = None

    def body(self, pg, dr, dec, kind, nlab, need=(), keys=()):
        self.bodies.append(dict(place='port' if self.now else 'key', port=self.now and dict(self.now), need=[sorted(x) for x in need], start=len(self.rng.atoms)))
        return super().body(pg, dr, dec, kind, nlab, need, keys)


or_q.GuidedRun = CaptureRun


def forms_in(lines):
    """[(index, kind, head name, names that it reads)] of the lines that declare a relation."""
    out = []
    for i, x in enumerate(lines):
        m = HEAD.match(x)
        if m:
            out.append((i, m[1], m[2], {n for n in NAME.findall(x[m.end():])}))
    return out


def slot_form(pg, heads):
    """{relation name in an atom's text: head name of the form that declares it}."""
    out = {}
    for name, written in pg.names.items():
        base = written.split('.')[0]
        if base in heads:
            out[name] = base
    return out


def form_types(pg, heads):
    """{head name: [set of column types of one relation, for each relation of the form]}: its table's column types and its record fields' types. A relation with no table gives ANY_TYPE, as label_types has it."""
    out = {h: [] for h in heads}
    cm = pg.colmaps['RULE']
    for name, written in pg.names.items():
        h = written.split('.')[0]
        if h not in out:
            continue
        s = int(name[2:])
        ts = set(pg.decl_types.get(s, ())) - {'Example'}
        ts |= {t for t in cm.get(s, {}).values() if isinstance(t, str)}
        out[h].append(ts or {ANY_TYPE})
    return {h: v or [{ANY_TYPE}] for h, v in out.items()}


def fits(rels, need, key_types=()):
    """Whether one relation of a form meets every set of need, and holds a key type where there are key types."""
    return any(ANY_TYPE in ts or (all(set(x) & ts for x in need) and (not key_types or set(key_types) & ts)) for ts in rels)


def fits_any(rels, need):
    """Whether one relation of a form meets one set of need, or need is empty."""
    return not need or any(ANY_TYPE in ts or any(set(x) & ts for x in need) for ts in rels)


def reads_of(q, run, scope):
    """One dict per atom of the walk's record, with the counts of item 4 for a read of an earlier form."""
    _, _, pg = run.scoped
    forms = forms_in(scope)
    heads = [h for _, _, h, _ in forms]
    of = slot_form(pg, set(heads))
    types = form_types(pg, heads)
    read_by_later = set()
    for _, _, _, names in forms:
        read_by_later |= names
    unread_before = [h for h in heads if h not in read_by_later]
    seen = set()  # the forms that an earlier read of this INIT read
    rows = []
    bodies = run.bodies
    for n, ((ctx, text, bits), det) in enumerate(zip(q['atoms'], q['detail'])):
        b = next((x for x in reversed(bodies) if x['start'] <= n), None)
        size = (next((x['start'] for x in bodies if x['start'] > b['start']), len(q['atoms'])) - b['start']) if b else 0
        neg = text.startswith('(NOT')
        m = re.match(r'\((?:NOT \()?(\S+)', text)
        name = m[1] if m else None
        target = of.get(name)
        r = dict(n=n, ctx=ctx, text=text, bits=bits, cur=det['cur'], cats=B.split(det['cur'], bits or 0.0), joined=det['joined'], k=det['k'], neg=neg, relation=name, port=b and b['port'] and b['port']['name'], place=b and b['place'], outside=bool(b and b['port'] and b['port']['outside']), body_atoms=size, need=b and b['need'],
                 target_form=target, kind='form' if target else 'lib' if name and name.isidentifier() else 'op')
        if target:
            need = (b and b['need']) or []
            key_types = [t for t in ((b and b['port'] and b['port']['key_types']) or []) if t]
            fit_all = [h for h in heads if fits(types[h], need)]
            fit_any = [h for h in heads if fits_any(types[h], need)]
            fit_key = [h for h in heads if fits(types[h], need, key_types)]
            so_far = [h for h in unread_before if h not in seen]
            sets = dict(all=heads, unread_before=unread_before, unread_so_far=so_far, fit_head=fit_all, fit_head_any=fit_any, fit_head_key=fit_key)
            r['counts'] = {k: len(v) for k, v in sets.items()}
            r['log2'] = {k: round(math.log2(len(v)), 3) if v else None for k, v in sets.items()}
            r['target_in'] = {k: target in v for k, v in sets.items()}
            r['target_types'] = sorted({t for ts in types.get(target, ()) for t in ts})
            seen.add(target)
        rows.append(r)
    return rows


def code_hash():
    h = hashlib.sha256()
    for f in CODE:
        h.update(open(os.path.join(os.environ['SAMPLER_CODE'], f), 'rb').read())
    return h.hexdigest()[:12]


def done_keys(path):
    got = set()
    if os.path.exists(path):
        for line in open(path):
            try:
                got.add(json.loads(line)['key'])
            except json.JSONDecodeError:
                pass
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int)
    ap.add_argument('--out', default=HERE + 'rows.jsonl')
    a = ap.parse_args()
    so = hashlib.sha256(open(ENGINE_SO, 'rb').read()).hexdigest()
    if not so.startswith(SO_SHA256_16):
        sys.exit('arclog .so is %s; the census manifest has %s' % (so, SO_SHA256_16))
    code = code_hash()
    rows = [json.loads(x) for x in open(HERE + 'form-set.jsonl')]
    done = done_keys(a.out)
    todo = [r for r in rows if r['key'] not in done]
    print('%d forms, %d done, %d to do; models %s; code %s' % (len(rows), len(done), len(todo), G.MODELS, code), flush=True)
    t0 = time.time()
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    load = time.time() - t0
    print('load %.1f s' % load, flush=True)
    t0, spent = time.time(), 0
    with open(a.out, 'a') as out:
        for r in todo[:a.limit]:
            t1 = time.time()
            nl = normal_lines(r)
            i = r['index']
            if nl[i] != r['target']:
                row = dict(key=r['key'], task=r['task'], held=r['held'], error='the normal form at %d is not the trial row\'s text' % i)
            else:
                kind = 'INIT'
                sess, task_json, _ = live_try.session_of(r['task'])
                q = or_q.walk(sampler, r['task'], kind, [i, 0], nl[:i], nl[i], sess, task_json, kind)
                run = CaptureRun.last
                ok = not q.get('bad') and q.get('dead') is None and q.get('total') is not None and not q.get('left')
                row = dict(key=r['key'], task=r['task'], form=r['form'], held=r['held'], group=r['group'], step=r['step'], index=i, target=nl[i], code=code, component=nl[i].split()[2], census_bits=r['census_bits'], total=q['total'], diff=round(q['total'] - r['census_bits'], 3), ok=ok, bad=q['bad'], dead=q['dead'], left=q['left'], match=q.get('match'), fell_back=q['fell_back'],
                           parts=q['parts'], counts=q['counts'], cats=B.split(q['parts'], q['total']), bodies=run.bodies, reads=reads_of(q, run, nl[:i]), scope_forms=len(forms_in(nl[:i])), scope_lines=i, relation_slots=run.scoped[2].ndecl)
            row['seconds'] = round(time.time() - t1, 2)
            out.write(json.dumps(row) + '\n')
            out.flush()
            spent += 1
            rate = (time.time() - t0) / spent
            print('%s held=%s total %s census %s diff %s (%.1f s); %.2f s per form, %d left, ETA %.0f s' % (r['key'], r['held'], row.get('total'), row.get('census_bits'), row.get('diff'), row['seconds'], rate, len(todo) - spent, rate * (len(todo) - spent)), flush=True)


if __name__ == '__main__':
    main()

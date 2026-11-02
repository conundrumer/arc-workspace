#!/usr/bin/env python
"""The bits of each form and each atom of an arclog program, in the census walk of the sampler.

  uv run python scripts/arclog_bits.py PROGRAM.arclog TASK [--fast] [--parents] [--written] [--order-cap N] [--order-budget N] [--order-seconds S] [--models DIR] [--steer-cover LIST] [--json OUT] [-v]

PROGRAM.arclog has one form per line (the gold text of the corpus: `(INIT ...)`, `(DET ...)`, `(RULE ...)`, `(RIGID_DET ...)`, then an
optional `(OUT ...)`). A blank line and a line that starts with `;` are skipped. TASK is a task id under data/tasks/.

One row per form, and under it one row per atom. A row has the bits and their split into relation pick (`rel`), columns (`col`), values (`val`),
stops (`stop`) and what is left (`other`), and a form's row has its running total. The program total is the last line.
- rel: the relation pick of an atom, with the operator relations.
- col: the pick of a column, and of a function column.
- val: a label or another value, and the comparison operator.
- stop: the stop of an atom's column list, the stop of a body or of a branch, and whether a branch goes on.
- other: the rest. In a form's row that is the component, the OR coins, the join mix, a port's coins and a head's. In an atom's row it is its join mix.

A form that the walk can't draw shows `bad` (a choice to which the walk gives gold chance 0) or `dead` (a gate or a refusal that ends gold's path)
and the reason, not a number. A form that the walk draws with something its priors lack (`fell_back`) is marked `fb`, and the header says which keys.

Exact mode (the default) is or_q.walk, as work/lm/data-study/sampler/sampler-worker/front/frontier_q.py drives it: each form on a session of its own. A figure is
-log2 of the sum over the form's valid orders (see or_q.py: a form with more orders than `--order-cap` has an estimate from `--order-budget` walks, and a form takes at most
`--order-seconds`). The first column, `before`, has every written form before the form as its scope, in written order, so it reads the written form order and isn't DAG invariant.
`--parents` adds, per form, the bits when the scope is only the forms that it reads, directly or not, each in its canonical atom order (or_q.canonical_lines,
or_q.canonical_scope); that column is DAG invariant. `--written` gives the old figure, which equals a census row of the same text, code, models and STEER_COVER: the form's written order
only (or_q.walk_order), and both columns read the written forms in written order. `--fast` is a proxy for the bits of the written order, and loads no engine tables
(see scripts/arclog_bits_fast.py).

The engine is the Mac runtime of work/lm/data-study/ast/run/runtime-0a7d32160, run by the python of runtime-kaggle-py313 (`--runtime` for
another runtime that scripts/build_study_runtime.py built). This tool sets PYTHONPATH itself, and stops unless the installed
arclog.abi3.so is the one in the runtime's wheel.

Default models are those of work/synth-kaggle/kernel-bundle-00361067/dataset, the built bundle that work/synth-kaggle/kernel-next-bundle-inputs.md
calls current: `live_priors.pkl` (sha256 starts 5feaca170f02b72b), `relR4_o.pkl`, `choice5_o.pkl` and `tilt_v1.json`. That bundle runs with STEER_COVER
unset, which is this tool's default. A census with `init,branch` (rigid-census.sh) is `--steer-cover init,branch --models <its models dir>`.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.checkout import main_worktree  # noqa: E402

WORK = main_worktree(ROOT) / 'work'
RUN = WORK / 'lm/data-study/ast/run'
RUNTIME = RUN / 'runtime-0a7d32160'
ENGINE_PY = RUN / 'runtime-kaggle-py313/venv/bin/python'
BUNDLE = WORK / 'synth-kaggle/kernel-bundle-00361067'
MODELS = BUNDLE / 'dataset'
SAMPLER = Path(os.environ.get('SAMPLER_CODE', ROOT / 'model/study/sampler'))  # as frontier_q.py: the sampler code of another checkout
INNER = 'ARCLOG_BITS_INNER'
CATS = ('rel', 'col', 'val', 'stop', 'other')
NAME = re.compile(r'&[A-Za-z_0-9]+')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def engine_path(runtime):
    """The folder that holds the runtime's arclog package for the python of runtime-kaggle-py313, made on first use."""
    path = runtime / 'py313-path'
    if not (path / 'arclog').exists():
        path.mkdir(exist_ok=True)
        (path / 'arclog').symlink_to(next((runtime / 'venv/lib').glob('python*/site-packages/arclog')))
    return path


def check_engine(runtime):
    """The engine line for the header; stops the tool where the installed arclog.abi3.so is not the one in the runtime's wheel."""
    import zipfile
    ready = json.load(open(runtime / 'ready.json'))
    so = engine_path(runtime) / 'arclog/arclog.abi3.so'
    with zipfile.ZipFile(ready['wheel']) as wheel:
        name = next(n for n in wheel.namelist() if n.endswith('arclog.abi3.so'))
        want = hashlib.sha256(wheel.read(name)).hexdigest()
    if sha256(so) != want:
        sys.exit('arclog.abi3.so in %s is not the one in %s' % (so.resolve().parent, ready['wheel']))
    return 'arclog %s (%s)' % (ready['revision'][:9], runtime.name)


def read_program(path):
    return [x.strip() for x in Path(path).read_text().splitlines() if x.strip() and not x.lstrip().startswith(';')]


def parents(lines, i):
    """The indexes before i of the forms that line i reads, directly or not."""
    head = {}
    for j, x in enumerate(lines):
        m = NAME.search(x)
        if m:
            head[m[0]] = j
    got, todo = set(), [i]
    while todo:
        for n in NAME.findall(lines[todo.pop()]):
            j = head.get(n)
            if j is not None and j < i and j not in got:
                got.add(j)
                todo.append(j)
    return sorted(got)


def kind_of(line):
    return line.split()[0].lstrip('(')


def part_cat(key):
    """The column of the table that a key of a record's `parts` or of an atom's `cur` goes in."""
    sub = key.split('atom: ', 1)[1] if 'atom: ' in key else key
    if sub in ('relation', 'relation (op)'):
        return 'rel'
    if sub in ('column', 'fcol'):
        return 'col'
    if sub.startswith('value') or sub == 'op':
        return 'val'
    if sub == 'column stop' or 'stop' in sub or 'go on' in sub:
        return 'stop'
    return 'other'


def split(parts, total=None):
    out = dict.fromkeys(CATS, 0.0)
    for k, v in parts.items():
        out[part_cat(k)] += v
    if total is not None:
        out['other'] += total - sum(out.values())
    return out


def label(line, width=58):
    text = ' '.join(line.split())
    return text if len(text) <= width else text[:width - 1] + '~'


# ---------------------------------------------------------------- exact mode, in the engine's python

def exact(a, lines):
    sys.path.insert(0, str(SAMPLER))
    os.environ['STEER_COVER'] = a.steer_cover
    import live  # noqa: E402  # pyright: ignore[reportMissingImports]
    import live_try  # noqa: E402  # pyright: ignore[reportMissingImports]
    import or_q  # noqa: E402  # pyright: ignore[reportMissingImports]
    t0 = time.time()
    sampler = live.Sampler(str(a.models), tuple(live.STEERS))
    load = time.time() - t0
    t0 = time.time()
    rows = []
    forms = [j for j, x in enumerate(lines) if kind_of(x) != 'OUT']  # canonical_lines takes the forms with no OUT form
    canon = None
    if a.parents and not a.written:
        sess, _, _ = live_try.session_of(a.task)
        canon, _ = or_q.canonical_lines([lines[j] for j in forms], sess)
    for i, target in enumerate(lines):
        kind = kind_of(target)
        row: dict[str, Any] = dict(line=i, kind=kind, target=target)
        rows.append(row)
        if kind not in live.KIND_TOK:
            row['skip'] = True
            continue
        for scope, keep in (('before', lines[:i]), ('parents', None if not a.parents else [lines[j] for j in parents(lines, i)] if a.written or canon is None else or_q.canonical_scope(canon, forms.index(i)))):
            if keep is None:
                continue
            t1 = time.time()
            q: dict[str, Any]
            try:
                sess, task_json, _ = live_try.session_of(a.task)  # a session for each walk, as frontier_q.py: a session that earlier walks used gives other bits
                if a.written:
                    q = or_q.walk_order(sampler, a.task, kind, [len(keep), 0], keep, target, sess, task_json, kind)
                else:
                    q = or_q.walk(sampler, a.task, kind, [len(keep), 0], keep, target, sess, task_json, kind, a.order_cap, a.order_budget, a.order_seconds)
            except Exception as e:  # noqa: BLE001
                q = dict(error=repr(e)[:200])
            q['seconds'] = round(time.time() - t1, 2)
            if 'error' not in q:
                q['cats'] = split(q['parts'], q['total'])
                q['atom_rows'] = [(place, text, bits, split(det['cur'], bits)) for (place, text, bits), det in zip(q['atoms'], q['detail'])]
            row[scope] = q
    return dict(rows=rows, load_seconds=round(load, 2), walk_seconds=round(time.time() - t0, 2), steer_cover=sorted(live.S.STEER_COVER))


# ---------------------------------------------------------------- fast mode

def fast(a, lines):
    import arclog_bits_fast as F
    t0 = time.time()
    model = json.load(open(Path(__file__).with_name('arclog_bits_fast.json')))
    load = time.time() - t0
    refs = F.refs_of(lines)
    rows = []
    for i, target in enumerate(lines):
        kind = kind_of(target)
        row: dict[str, Any] = dict(line=i, kind=kind, target=target)
        rows.append(row)
        if kind not in ('RULE', 'DET', 'INIT'):
            row['skip'] = True
            row['why'] = 'not a form' if kind == 'OUT' else 'not modeled'
            continue
        for scope, keep in (('before', list(range(i))), ('parents', parents(lines, i) if a.parents else None)):
            if keep is None:
                continue
            t1 = time.time()
            form, atoms = F.predict(model, model['names'], target, len(keep), refs)
            total = sum(form.values())
            row[scope] = dict(total=total, cats=form, bad=[], dead=None, fell_back=[], seconds=round(time.time() - t1, 4),
                              atom_rows=[(place, text, sum(y.values()), y) for text, place, y in atoms])
    return dict(rows=rows, load_seconds=round(load, 2), walk_seconds=0, steer_cover=[], fast=True)


# ---------------------------------------------------------------- the table

def num(x, w=6):
    return '%*.1f' % (w, x)


def cells(d, w=6):
    return ' '.join(num(d[c], w) for c in CATS)


def verdict(q):
    if 'error' in q:
        return 'error', q['error']
    if q.get('dead'):
        return 'dead', q['dead']
    if q.get('bad'):
        return 'bad', '; '.join(q['bad'])
    return None, None


def show(a, res, header, program):
    out: list[str] = []
    out.append('%s  task %s  %s' % (program, a.task, header))
    fb = {}
    head = '%-3s %-9s %-58s %7s %s %7s%s' % ('#', 'kind', 'form / atom', 'bits', ' '.join('%6s' % c for c in CATS), 'running', '  parents' if a.parents else '')
    out.append(head)
    run, bad_n, secs = 0.0, 0, 0.0
    for r in res['rows']:
        if r.get('skip'):
            out.append('%-3d %-9s %-58s %7s' % (r['line'], r['kind'], label(r['target']), r.get('why', 'not a form')))
            continue
        q = r['before']
        secs += q['seconds']
        why, text = verdict(q)
        ptxt = ''
        if a.parents:
            pq = r['parents']
            pw, pt = verdict(pq)
            ptxt = '  %7s' % (pw or '%.1f' % pq['total'])
        if q.get('fell_back'):
            for k in q['fell_back']:
                fb.setdefault(k, []).append(r['line'])
        if why:
            bad_n += 1
            out.append('%-3d %-9s %-58s %7s%s' % (r['line'], r['kind'], label(r['target']), why, ptxt))
            out.append('      %s: %s' % (why, text if a.verbose else str(text)[:150]))
            continue
        run += q['total']
        d = q['cats']
        out.append('%-3d %-9s %-58s %7.1f %s %7.1f%s%s' % (r['line'], r['kind'], label(r['target']), q['total'], cells(d), run, ptxt, '  fb' if q.get('fell_back') else ''))
        o = q.get('orders')
        if o:
            out.append('      orders %s walked %d valid %d written %s, %s' % (round(o['orders']) if o['orders'] is not None else '?', o['walked'], o['valid'], '-' if o['written'] is None else '%.1f' % o['written'],
                                                                          'exact' if o['exact'] else 'estimate se %.2f' % o.get('se_bits', 0.0)))
        for place, text, bits, ad in q['atom_rows']:
            out.append('      %-6s %-55s %7.1f %s' % (place, label(text, 55), bits, cells(ad)))
    out.append('total %.1f bits over %d forms%s; %.1f s in the walks, %.1f s to load the models' % (
        run, sum(1 for r in res['rows'] if not r.get('skip')), ', %d without a figure' % bad_n if bad_n else '', secs, res['load_seconds']))
    if fb:
        out.append('fell_back: the priors lack %s' % '; '.join('%s (forms %s)' % (k, ','.join(map(str, v))) for k, v in sorted(fb.items())))
    return '\n'.join(out)


def inner(a):
    lines = read_program(a.program)
    res: dict[str, Any] = fast(a, lines) if a.fast else exact(a, lines)
    if a.json:
        json.dump(res, open(a.json, 'w'))
    if a.fast:
        header = 'fast (a proxy for the bits of the written order, no engine)'
    else:
        what = 'written order' if a.written else 'sum over orders'
        header = 'exact (%s)  models %s  STEER_COVER=%s; the bits column reads every written form before the form, in written order' % (what, a.models, ','.join(list(res['steer_cover'])) or 'unset')
        if a.parents:
            header += '; the parents column reads the forms it reads, ' + ('in written order' if a.written else 'each in canonical atom order')
    print(show(a, res, header, a.program))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('program')
    ap.add_argument('task')
    ap.add_argument('--fast', action='store_true', help='the proxy, with no engine')
    ap.add_argument('--parents', action='store_true', help='also the bits over the forms that the form reads, in canonical atom order')
    ap.add_argument('--written', action='store_true', help='the bits of the written order of each form, over the written forms: one order, as this tool read before it summed over orders')
    ap.add_argument('--order-cap', type=int, default=256, help='a form with at most this many orders has all of them walked')
    ap.add_argument('--order-budget', type=int, default=256, help='the walks of a form with more')
    ap.add_argument('--order-seconds', type=float, default=300, help='the seconds a form takes at most')
    ap.add_argument('--models', type=Path, default=MODELS, help='a folder with live_priors.pkl, relR4_o.pkl, choice5_o.pkl, tilt_v1.json (default: the dataset of kernel-bundle-00361067)')
    ap.add_argument('--steer-cover', default='', help='STEER_COVER of the walk (default: unset, as in kernel-bundle-00361067)')
    ap.add_argument('--runtime', type=Path, default=RUNTIME, help='a runtime folder that scripts/build_study_runtime.py built (default: runtime-0a7d32160)')
    ap.add_argument('--json', help='write the records here')
    ap.add_argument('-v', '--verbose', action='store_true', help='the whole reason of a bad or dead form')
    a = ap.parse_args()
    if not (ROOT / 'data/tasks' / (a.task + '.json')).exists():
        sys.exit('no task %s in data/tasks/' % a.task)
    if os.environ.get(INNER) or a.fast:
        return inner(a)
    note = check_engine(a.runtime)
    env = dict(os.environ, PYTHONPATH=str(engine_path(a.runtime)), RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', **{INNER: '1'})
    print(note, file=sys.stderr)
    sys.exit(subprocess.call([str(ENGINE_PY), '-u', os.path.abspath(__file__), *sys.argv[1:]], env=env))


if __name__ == '__main__':
    main()

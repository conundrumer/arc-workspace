#!/usr/bin/env python
"""The bits of gold's forms under the sampler's walk, summed over each form's valid orders (or_q.walk), one record per form.

  <runtime python> dag_bits.py OUT_DIR --gold SOURCE [--gold SOURCE ...] --gold-revision NAME --tasks FILE [--tasks FILE ...] --models DIR
      [--context parents|before] [--cap 256] [--budget 256] [--seconds 300] [--shard K/N] [--limit N] [--only TASK:LINE ...] [--reuse DIR]

SOURCE is a folder with `<stem>/pairs.jsonl.gz` (the first row's `gold_sexp`) or a JSON list of rows with `task` and `gold_sexp`; for each task the first
source that has it wins. FILE is a list of task ids, split by whitespace. A form is a line of the gold text that is not blank and does not start with
`(OUT`; `line` is its index in that list. A CHOOSE form has a record with `total` null and `skip` true.

Context `parents` (the default) is DAG invariant: the scope of a form is the forms that it reads, directly or not, each in its canonical atom order
(or_q.canonical_lines, or_q.canonical_scope), and the target stays the written text. A form's name is in the text that the sort of the scope reads, so slot numbers can depend on
helper names. Context `before` reads every written line before the form, in written order, and isn't DAG invariant.
Each record also has `other_context_written`: the bits of the written order of the form over every written line before it, where that walk is valid.

A shard writes OUT_DIR/orders-shardKofN.jsonl, a line per form, flushed after each. At start every orders-shard*.jsonl of OUT_DIR is read and the forms with a
record are skipped, so a run with another shard count resumes. `--reuse DIR` takes the record of a form from the records of DIR where the task, the target text and
the scope (`scope_sha`) are the same. In context `parents` the target is walked with the fields of its atoms in the column order of the relations they read (or_q.sorted_fields); the record's `target` is the written text, and `target_rendered` the text walked where it differs. Read the records, partial or whole, with dag_bits_read.py.
"""
import argparse
import datetime
import gc
import glob
import gzip
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live  # noqa: E402
import live_try  # noqa: E402
import or_q  # noqa: E402

COMPOUND = '(OR ', '(ALL ', '(IF '
MEASURES = ['Teacher-forced replay', 'Surprisal under the proposal distribution', 'DAG invariance']
COMPARED = 'priors.sha256', 'gold.revision', 'arm', 'budget'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def tasks_of(files):
    out = []
    for f in files:
        out.append((f, open(f).read().split()))
    return out


class Gold:
    """The gold text of a task from a list of sources: the first source that has the task wins."""

    def __init__(self, sources):
        self.sources, self.lists = sources, {}
        for s in sources:
            if os.path.isfile(s):
                self.lists[s] = {r['task']: r['gold_sexp'] for r in json.load(open(s))}

    def text(self, task):
        for s in self.sources:
            if s in self.lists:
                if task in self.lists[s]:
                    return self.lists[s][task], s
                continue
            path = os.path.join(s, task, 'pairs.jsonl.gz')
            if os.path.exists(path):
                with gzip.open(path, 'rt') as f:
                    return json.loads(f.readline())['gold_sexp'], s
        raise SystemExit('no gold text for task %s in %s' % (task, self.sources))

    def lines(self, task):
        text, source = self.text(task)
        return [x for x in text.splitlines() if x.strip() and not x.startswith('(OUT')], source


def records_of(out_dir):
    """The records of the orders-shard*.jsonl files of a folder; a line that doesn't parse (a broken last line) is left out."""
    out = []
    for path in sorted(glob.glob(os.path.join(out_dir, 'orders-shard*.jsonl'))):
        with open(path) as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def scope_sha(scope):
    return hashlib.sha256('\n'.join(scope).encode()).hexdigest()[:16]


def engine_info():
    """sha256 and so_sha256 of the engine under PYTHONPATH, as scripts/arclog_bits.py:check_engine reads them, and the commit in the runtime folder's name."""
    for entry in os.environ.get('PYTHONPATH', '').split(os.pathsep):
        so = Path(entry) / 'arclog/arclog.abi3.so'
        if so.exists():
            wheels = sorted((Path(entry).parent / 'wheels').glob('*.whl'))
            return dict(commit=Path(entry).parent.name.split('-')[-1], sha256=sha256(wheels[0]) if wheels else None, so_sha256=sha256(so.resolve()), machine='Mac')
    raise SystemExit('no arclog.abi3.so on PYTHONPATH')


def code_commit():
    here = os.path.dirname(os.path.abspath(__file__))
    commit = subprocess.run(['git', '-C', here, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', '-C', here, 'status', '--porcelain', '--', here], capture_output=True, text=True).stdout.strip())
    return commit, dirty


def dig(d, path):
    for k in path.split('.'):
        d = d[k]
    return d


def manifest_of(a, gold, task_files, counts, priors_sha):
    commit, dirty = code_commit()
    return dict(
        command=' '.join([sys.executable, *sys.argv]), commit=commit, code_dirty=dirty, started=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        task_set={f: dict(tasks=len(ts), forms=counts[f]) for f, ts in task_files},
        budget=dict(cap=a.cap, budget=a.budget, seconds=a.seconds), measures=MEASURES, arm=a.context, node_records='none',
        training_eligibility='not for fits that test on these tasks',
        gold=dict(sources=gold.sources, revision=a.gold_revision),
        priors=dict(models=str(a.models), sha256=priors_sha),
        steers=list(live.STEERS), steer_cover=sorted(live.S.STEER_COVER),
        wheel_engine=engine_info())


def write_manifest(path, m):
    """Writes the manifest once: the first shard to link the file wins, and the others read it."""
    tmp = '%s.%d.tmp' % (path, os.getpid())
    with open(tmp, 'x') as f:
        json.dump(m, f, indent=1)
    try:
        os.link(tmp, path)
    except FileExistsError:
        pass
    finally:
        os.unlink(tmp)
    return json.load(open(path))


def one(sampler, a, task, lines, source, canon, i, reuse):
    """The record of form i of the task's lines."""
    target = lines[i]
    kind = target.split()[0].lstrip('(')
    rec = dict(task=task, line=i, kind=kind, source=source, context=a.context, compound=any(w in target for w in COMPOUND))
    if kind not in live.KIND_TOK:
        return dict(rec, total=None, skip=True)
    t0 = time.time()
    scope = or_q.canonical_scope(canon[0], i) if a.context == 'parents' else lines[:i]
    rec.update(nscope=len(scope), scope_sha=scope_sha(scope))
    if a.context == 'parents':
        rec['canon_kept'] = canon[1]
    try:
        old = reuse.get((task, target, rec['scope_sha']))
        if old is not None:
            q = dict(old, line=i, source=source, context=a.context, reused=True)
            q.pop('seconds', None)
            rec = dict(q, **{k: v for k, v in rec.items() if k not in q})
        else:
            gc.collect()
            sess, task_json, _ = live_try.session_of(task)
            walked = or_q.sorted_fields(target, sess, scope) if a.context == 'parents' else target  # the target's fields in the column order of the relations it reads
            q = or_q.walk(sampler, task, kind, [len(scope), 0], scope, walked, sess, task_json, kind, a.cap, a.budget, a.seconds)
            rec.update(q, target=target)
            if walked != target:
                rec['target_rendered'] = walked
        rec['valid'] = not rec['bad'] and rec['dead'] is None
        rec['other_context_written'] = None
        try:
            sess, task_json, _ = live_try.session_of(task)
            w = or_q.walk_order(sampler, task, kind, [i, 0], lines[:i], target, sess, task_json, kind)
            rec['other_context_written'] = w['total'] if or_q.clean(w) else None
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        rec.update(total=None, valid=False, error=repr(e)[:300])
    rec['seconds'] = round(time.time() - t0, 2)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out_dir')
    ap.add_argument('--gold', action='append', required=True)
    ap.add_argument('--gold-revision', required=True)
    ap.add_argument('--tasks', action='append', required=True)
    ap.add_argument('--models', type=Path, required=True)
    ap.add_argument('--context', choices=('parents', 'before'), default='parents')
    ap.add_argument('--cap', type=int, default=or_q.ORDER_CAP)
    ap.add_argument('--budget', type=int, default=or_q.ORDER_BUDGET)
    ap.add_argument('--seconds', type=float, default=or_q.ORDER_SECONDS)
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--only', nargs='*', default=[])
    ap.add_argument('--reuse')
    a = ap.parse_args()
    k, n = (int(x) for x in a.shard.split('/'))
    gold = Gold(a.gold)
    task_files = tasks_of(a.tasks)
    forms, counts, seen = [], {}, set()  # forms: (task, line) over the tasks in file order
    texts = {}
    for f, ts in task_files:
        counts[f] = 0
        for t in ts:
            if t not in texts:
                texts[t] = gold.lines(t)
            counts[f] += len(texts[t][0])
            if t not in seen:
                seen.add(t)
                forms += [(t, i) for i in range(len(texts[t][0]))]
    priors_sha = sha256(a.models / 'live_priors.pkl')
    os.makedirs(a.out_dir, exist_ok=True)
    mine = manifest_of(a, gold, task_files, counts, priors_sha)
    have = write_manifest(os.path.join(a.out_dir, 'manifest.json'), mine)
    for key in COMPARED:
        if key == 'arm':
            same = have['arm'] == mine['arm']
        else:
            same = dig(have, key) == dig(mine, key)
        if not same:
            sys.exit('the manifest of %s has a different %s: %s, not %s' % (a.out_dir, key, dig(have, key), dig(mine, key)))
    done = {(r['task'], r['line']) for r in records_of(a.out_dir)}
    only = {(x.split(':')[0], int(x.split(':')[1])) for x in a.only}
    todo = [(j, t, i) for j, (t, i) in enumerate(forms) if j % n == k and (t, i) not in done and (not only or (t, i) in only)]
    if a.limit:
        todo = todo[:a.limit]
    reuse = {}
    if a.reuse:
        for r in records_of(a.reuse):
            if not r.get('skip') and 'error' not in r and r.get('scope_sha'):
                reuse[(r['task'], r['target'], r['scope_sha'])] = r
    print('shard %d/%d: %d forms to do of %d in the shard, %d done; %d reusable' % (k, n, len(todo), sum(1 for j in range(len(forms)) if j % n == k), len(done), len(reuse)), flush=True)
    sampler = live.Sampler(str(a.models), tuple(live.STEERS))
    path = os.path.join(a.out_dir, 'orders-shard%dof%d.jsonl' % (k, n))
    with open(path, 'ab+') as f:
        f.seek(0, 2)
        if f.tell():
            f.seek(-1, 2)
            if f.read(1) != b'\n':
                f.write(b'\n')
    canon, start = {}, time.time()
    with open(path, 'a') as out:
        for count, (j, task, i) in enumerate(todo, 1):
            lines, source = texts[task]
            if canon.get('task') != task:
                canon = dict(task=task, value=None)
            if canon['value'] is None and a.context == 'parents' and lines[i].split()[0].lstrip('(') in live.KIND_TOK:
                sess, _, _ = live_try.session_of(task)
                canon['value'] = or_q.canonical_lines(lines, sess)
                del sess
            rec = one(sampler, a, task, lines, source, canon['value'] if a.context == 'parents' else None, i, reuse)
            rec['target'] = lines[i]
            out.write(json.dumps(rec) + '\n')
            out.flush()
            el = time.time() - start
            o = rec.get('orders') or {}
            print('%s:%d %s total %s orders %s walked %s valid %s %.1fs%s  %d of %d, eta %.0fs' % (
                task, i, rec['kind'], rec.get('total'), o.get('orders'), o.get('walked'), o.get('valid'), rec.get('seconds', 0), '  ERROR ' + rec['error'] if 'error' in rec else '',
                count, len(todo), el / count * (len(todo) - count)), flush=True)


if __name__ == '__main__':
    main()

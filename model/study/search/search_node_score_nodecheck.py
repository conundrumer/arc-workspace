"""Checks the rows and scores that mt and depth jobs made at the node, against a rebuild from the node records.

  KIT_POLICY=<kit>/policy <engine python> -I search_node_score_nodecheck.py OUT [SCORES [MAX_NODES]]

OUT is the folder of the jobs, OUT/<arm>/<task>/ as run3600.sh writes it (OUT/out is used where it exists). A job of an arm that starts with mt or depth
is read with its dump.jsonl (NODE_SCORE_DUMP), its rec folder (ARC_RECORD), and its bank. SCORES is the folder of the node score files (default: scores
beside OUT). MAX_NODES (default 1000) is the most nodes of a job that the check reads: the first in node order.

For each dumped node that the bank holds:
  1. Read the node's record (table_types, x_rows, clause) and its bank form (kind, depth, reads).
  2. Compute the facts as features_node_rebuild.py does, with node_features(..., with_shape=True) for mt, and the form's three facts for depth.
  3. Compare the facts with the dumped row, NaN equal to NaN, after rounding to float32. Compare the reference score of the dumped row, t * the sum of the
     source model's predict calls, with the bank's score, bit for bit.
A job passes where it compares at least 300 nodes and no row or score differs. Where rows differ, the names of the facts that differ are counted.
The exit status is 1 where a job fails.
"""
import collections
import glob
import json
import math
import os
import pickle
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
KIT_POLICY = os.environ['KIT_POLICY']
sys.path.insert(0, KIT_POLICY)
sys.path.insert(0, KIT_POLICY + '/fe')
import features_node_feats as FE  # noqa: E402
import nodescore  # noqa: E402
import search_node_score_parity as PA  # noqa: E402

MIN_NODES, DEFAULT_MAX_NODES = 300, 1000
SHOWN_NAMES = 12


def zst_lines(path):
    """The text lines of a record file. A frame with no end, as a process that died leaves, gives the lines up to its last whole block."""
    import zstandard
    text = b''
    try:
        with open(path, 'rb') as f:
            reader = zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True)
            while True:
                block = reader.read(1 << 20)
                if not block:
                    break
                text += block
    except zstandard.ZstdError:
        pass
    return text.decode(errors='replace').split('\n')


def records_of(folder):
    """{token: record} of the record files of a job. A later record of the same token replaces an earlier one."""
    got = {}
    for path in sorted(glob.glob(folder + '/rec/*.nodes.jsonl*')):
        lines = zst_lines(path) if path.endswith('.zst') else open(path, errors='replace').read().split('\n')
        for line in lines:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            got[r['token']] = r
    return got


def same(a, b):
    """Two facts, each a float or None for NaN, equal with NaN equal to NaN."""
    return (a is None and b is None) or (a is not None and b is not None and a == b)


def f32(v):
    """A fact rounded to float32, as a float, or None where NaN."""
    x = float(np.float32(v))
    return None if math.isnan(x) else x


def check_job(arm, task, folder, scores, max_nodes):
    work = '%s/work/%s' % (folder, task)
    log = open(work + '.log', errors='replace').read()
    name = next((line.split('name=')[1].split()[0] for line in log.split('\n') if line.startswith('node score: ')), None)
    card, _, _ = nodescore.read_file('%s/%s.npz' % (scores, name))
    kind = card['features']
    names, t = card['names'], card['t']
    dump = {x['node']: x for x in PA.read_lines(folder + '/dump.jsonl')}
    records = records_of(folder)
    bank = PA.load_bank(work + '.out.jsonl.bank')
    score = bank['policy']['score']
    ctx = FE.TaskCtx(json.load(open(work + '.task.json')))
    nodes = [n for n in sorted(dump) if n in score and str(n) in records and n in bank['nodes']][:max_nodes]
    print('%s/%s: name %s features %s, dumped %d, in bank %d, with record %d, compared %d' % (
        arm, task, name, kind, len(dump), sum(n in score for n in dump), sum(n in score and str(n) in records for n in dump), len(nodes)))
    rows, differ_rows, by_name = [], 0, collections.Counter()
    for n in nodes:
        r, form = records[str(n)], bank['forms'][bank['nodes'][n].form]
        if kind == 'T':
            d = FE.node_features(r['table_types'], r['x_rows'], r['clause'], form.kind, form.depth, form.reads, ctx, with_shape=True)
        else:
            d = {'dp_form_depth': form.depth, 'dp_form_reads': form.reads, 'dp_kind': FE.KINDS.get(form.kind, 3)}
        want = [f32(d.get(k, float('nan'))) for k in names]
        got = dump[n]['x']
        bad = [k for k, a, b in zip(names, want, got) if not same(a, b)]
        differ_rows += bool(bad)
        by_name.update(bad)
        rows.append([float('nan') if v is None else v for v in got])
    differ_scores = 0
    if nodes:
        with open(card['source'], 'rb') as f:
            models, _ = pickle.load(f)
        x = np.array(rows, np.float32)
        ref = np.zeros(len(x))
        for m in models:
            ref += m.predict(x)
        ref = t * ref
        mine = np.array([score[n] for n in nodes])
        differ_scores = int((ref.view(np.uint64) != mine.view(np.uint64)).sum())
        dumped = np.array([dump[n]['score'] for n in nodes])
        print('  dumped score differs from the bank score: %d' % int((dumped.view(np.uint64) != mine.view(np.uint64)).sum()))
    ok = len(nodes) >= MIN_NODES and differ_rows == 0 and differ_scores == 0
    print('  %s: rows differ %d, scores differ %d, of %d nodes (at least %d needed)' % ('PASS' if ok else 'FAIL', differ_rows, differ_scores, len(nodes), MIN_NODES))
    if by_name:
        print('  facts that differ (name: nodes): %s' % ', '.join('%s: %d' % kv for kv in by_name.most_common(SHOWN_NAMES)))
    return ok


def main():
    out = sys.argv[1]
    kit = out if os.path.isdir(out + '/out') else os.path.dirname(out.rstrip('/'))
    scores = sys.argv[2] if len(sys.argv) > 2 else kit + '/scores'
    max_nodes = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_MAX_NODES
    jobs = [j for j in PA.job_folders(out) if j[0].startswith(('mt', 'depth'))]
    results = [check_job(arm, task, folder, scores, max_nodes) for arm, task, folder in jobs]
    print('jobs %d, failed %d' % (len(results), results.count(False)))
    sys.exit(1 if not all(results) or not results else 0)


if __name__ == '__main__':
    main()

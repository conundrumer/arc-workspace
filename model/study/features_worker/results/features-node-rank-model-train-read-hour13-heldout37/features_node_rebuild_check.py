"""Item 5 report for H and B: completeness, row check by run, and positives by session key against row hash and recorded covers.

  python -I features_node_rebuild_check.py SET [SECONDS] [ARM/TASK ...]      (SET: hour or base; plain Python, no engine)

For each run (default: every run of the SET that has a progress file; resumes through check-SET.jsonl, one line per run):
  complete: forms done = forms of the bank, and nodes written = nodes of the bank;
  row check counts (equal, ident, tied, other counts, no table);
  positives: nodes with a session key label, and gold forms with at least one such node;
  the same gold forms by row hash (pair of column types and example row hashes against gold-sig) and by recorded covers;
  reads with no table: gold forms that are read, with a read that no node holds, by session key and by row hash.
Then totals. Prints nothing from a held label beyond these counts.
"""
import collections, glob, json, os, sys, time
sys.dont_write_bytecode = True
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-rank-model-train-read-hour13-heldout37/'  # the data folder
sys.path.insert(0, HERE)
import numpy as np
import common2 as C2

C = C2.C
T0 = time.time()
SET = sys.argv[1]
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 and not '/' in sys.argv[2] else 25.0
only = [a for a in sys.argv[2:] if '/' in a]
S = C2.SETS[SET]
OUT = HERE + SET + '-rows/'
ck = HERE + 'check-%s.jsonl' % SET
done = {}
if os.path.exists(ck):
    for l in open(ck):
        r = json.loads(l)
        done[(r['arm'], r['task'])] = r
RC = ['equal', 'ident', 'tied', 'other counts', 'no table']


def one(arm, task):
    stem = task if SET == 'n600' else arm + '.' + task
    prog = json.load(open(OUT + stem + '.progress.json'))
    st = C.bank(C.run_dir(S['root'], arm, task) + 'work/' + task + '.out.jsonl.bank')
    nodes = st['nodes']
    complete = prog['next'] >= prog.get('forms', 1 << 60) and prog['forms'] == len(st['forms']) and prog['nodes'] == len(nodes)
    rec = dict(arm=arm, task=task, complete=bool(complete), forms_done=prog['next'], forms=len(st['forms']), nodes_written=prog['nodes'], nodes=len(nodes), rc=prog['rc'])
    g = json.load(open(OUT + stem + '.gold.json'))
    G = len(g['kinds'])
    zs = [np.load(p) for p in sorted(glob.glob(OUT + stem + '.part*.npz'))]
    meta = np.vstack([z['meta'] for z in zs])
    cols = {str(c): meta[:, i] for i, c in enumerate(zs[0]['meta_cols'])}
    golds = sum((json.loads(str(z['gold'][0])) for z in zs), [])
    sk = set(q for gs in golds for q in gs)
    rec['gold_forms'] = G
    rec['pos_nodes'] = int((cols['y'] == 1).sum())
    rec['pos_forms_session'] = len(sk)
    by_pair, by_form = C2.sig_table(SET, task)
    pairs = {json.dumps([sorted(n.table_types), n.examples]) for n in nodes.values()}
    rh = {q for q in range(G) if by_form.get(q) and (by_form[q] & pairs)}
    rec['pos_forms_rowhash'] = len(rh)
    rec['pos_nodes_rowhash'] = sum(1 for n in nodes.values() if json.dumps([sorted(n.table_types), n.examples]) in by_pair)
    rc = {x['gold'] for x in C.recorded_covers(S['root'], arm, task)}
    rec['pos_forms_recorded'] = len(rc)
    rec['both_session_rowhash'] = len(sk & rh)
    rec['session_only'] = len(sk - rh)
    rec['rowhash_only'] = len(rh - sk)
    rec['recorded_only_vs_session'] = len(rc - sk)
    reads = g['reads']
    rec['reads_no_table_session'] = sum(1 for h in range(G) if reads[h] and any(q not in sk for q in reads[h]))
    rec['reads_no_table_rowhash'] = sum(1 for h in range(G) if reads[h] and any(q not in rh for q in reads[h]))
    return rec


runs = []
for arm in S['arms']:
    for task in S['tasks']:
        if os.path.exists(OUT + (task if SET == 'n600' else arm + '.' + task) + '.progress.json') and (not only or '%s/%s' % (arm, task) in only):
            runs.append((arm, task))
fh = open(ck, 'a')
for arm, task in runs:
    if (arm, task) in done and done[(arm, task)]['complete']:
        continue
    if time.time() - T0 > SECONDS:
        print('stopped at the limit; rerun to resume', flush=True)
        break
    r = one(arm, task)
    done[(arm, task)] = r
    fh.write(json.dumps(r) + '\n')
    fh.flush()
tot = collections.Counter()
inc = []
for (arm, task), r in sorted(done.items()):
    if (arm, task) not in runs:
        continue
    print(arm, task, 'complete' if r['complete'] else 'INCOMPLETE %d/%d forms' % (r['forms_done'], r['forms']), 'nodes', r['nodes_written'], 'row check', r['rc'], '| positives: nodes', r['pos_nodes'], 'forms session', r['pos_forms_session'], 'row hash', r['pos_forms_rowhash'],
          'recorded', r['pos_forms_recorded'], '| reads with no table session', r['reads_no_table_session'], 'row hash', r['reads_no_table_rowhash'])
    if not r['complete']:
        inc.append((arm, task))
    for k, v in r.items():
        if isinstance(v, int) and not isinstance(v, bool):
            tot[k] += v
    for k, v in r['rc'].items():
        tot['rc:' + k] += v
print('runs', len(runs), 'complete', len(runs) - len(inc), 'incomplete', inc)
print('TOTAL', dict(tot))

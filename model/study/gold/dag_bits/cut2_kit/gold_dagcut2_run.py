"""Runs the stage `dagcut2` (gold_dagcut2_one.py: the DAG split cut, tool 2, version 2) on a shard of the stems. Each stem is one process group under 900 s and 8 GiB over the group, with no retry at a higher bound. The sampler loads once here, and each stem is a fork of this process. One row per stem, streamed. It has the design of gold_pod_run.py (caps, process-group count, reaping, resume), which it uses.

  <runtime python> gold_dagcut2_run.py TASKS.txt LINES.json WEIGHTS.json BASE-ROWS.json OUT.jsonl SHARD SHARDS

TASKS.txt, LINES.json and WEIGHTS.json are as in gold_pod_run.py. BASE-ROWS.json maps a stem to the pod row's figures of its start text (gold_dagcut2_kit.py): a stem with no entry gets a row with `skipped`. A restart skips a stem whose row is in OUT or in a rows-*.jsonl beside it, with the same key (stage, task, base_sha, cap, budget, margin).
Each row has the fields of gold_pod_run.py (`stage` is `dagcut2`, `wall`, `peak_gib`, `peak_procs`, `code`, `stage_code`) and `dag_code`, the hash of gold_dagcut2_one.py, gold_dag_cuts.py and gold_dag_orders.py.
Environment: as gold_dagcut2_one.py and gold_pod_run.py.
"""
import glob, hashlib, json, os, sys, warnings
sys.path.insert(0, os.environ['SAMPLER_CODE'])
import gold_pod_run as R
import gold_dagcut2_one as M

STAGE = 'dagcut2'
R.STAGES[STAGE] = M
here = os.path.dirname(os.path.abspath(__file__))
DAG_FILES = ('gold_dagcut2_one.py', 'gold_dag_cuts.py', 'gold_dag_orders.py')


def dag_hash():
    return hashlib.sha256(b''.join(open(os.path.join(here, f), 'rb').read() for f in DAG_FILES)).hexdigest()[:12]


def key_of(task, sha, cap=None, budget=None, margin=None):
    return (STAGE, task, sha, M.P.CAP if cap is None else cap, M.P.BUDGET if budget is None else budget, M.MARGIN if margin is None else margin)


def rows_done(out):
    """The stems done, as keys. A row cut short by a kill does not parse and counts as not done."""
    done = set()
    for p in {os.path.abspath(out)} | {os.path.abspath(x) for x in glob.glob(os.path.join(os.path.dirname(os.path.abspath(out)), 'rows-*.jsonl'))}:
        if os.path.exists(p):
            for l in open(p):
                try:
                    r = json.loads(l)
                    if r['stage'] == STAGE:
                        done.add(key_of(r['task'], r.get('base_sha'), r.get('cap'), r.get('budget'), r.get('margin')))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
    return done


def main():
    warnings.filterwarnings('ignore', 'This process .* is multi-threaded', DeprecationWarning)  # the stem's fork steps no thread of this process
    tasks, lines_path, weights_path, base_path, out, k, n = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]), int(sys.argv[7])
    R.check_wheel()
    R.subreaper()
    done = rows_done(out)
    text = json.load(open(lines_path))
    mine = R.assign(R.tiers_of(tasks), json.load(open(weights_path)), n)[k]
    M.load_sampler()
    M.BASE_ROWS.update(json.load(open(base_path)))
    R.end_line(out)
    code = dag_hash()
    with open(out, 'a') as f:
        for t in mine:
            lines = text.get(t)
            if not lines or key_of(t, M.sha(lines)) in done:
                continue
            row = R.run_stage(STAGE, t, lines, out)
            row.update(margin=M.MARGIN, dag_code=code)
            f.write(json.dumps(row) + '\n')
            f.flush()
            print(t, STAGE, row.get('error', ''), 'landed' if row.get('landed') else '', row.get('commit'), row.get('skipped') or '', row['wall'], row['peak_gib'], row['peak_procs'], flush=True)


if __name__ == '__main__':
    main()

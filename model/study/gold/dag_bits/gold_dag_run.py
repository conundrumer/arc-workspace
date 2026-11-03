"""Runs the DAG stages on a shard of the stems: `dag` (gold_dag_bits.py, tool 1) and later `dagcut` (gold_dagcut_one.py, tool 2). Each stage of each stem is one process group under 900 s and 8 GiB over the group, as in gold_combined_run.py, whose caps, process-group tools and tier assignment this file imports. The sampler loads once here, and each stage of a stem is a fork of this process. One row per stage per stem, streamed.

  <runtime python> gold_dag_run.py TASKS.txt LINES.json WEIGHTS.json OUT.jsonl SHARD SHARDS

TASKS.txt lists the stems in the order they run, with a blank line between tiers. A tier goes to the shards by stem weight, heaviest first, each stem to the shard with the least weight so far. WEIGHTS.json maps a stem to its weight (scratch/weights.py: each drawable form's order count, at most 120, plus 1, times 1 + its scope size; refit it from measured rows). LINES.json maps a stem to its forms.
A restart skips a stage whose row is in OUT or in a rows-*.jsonl beside it, with the same key (stage, task, base_sha, CAP, DELTA). A row cut short by a kill does not parse and counts as not done. A stem that was killed at a cap keeps its row, with `error` set, and does not run again at a higher bound.
Environment: DAG_STAGES, the stages to run (default `dag`). DAG_ORDER_CAP, DAG_DELTA, ORCUT_SO_SHA256 and ORCUT_KEPT_NODES go to the stages. Each row has `dag_code`, the hash of the DAG files that exist.
"""
import glob, hashlib, json, os, sys
import gold_combined_run as R
import gold_dag_bits
import gold_fork_reads as F
import gold_orcut_base as B

R.STAGES['dag'] = gold_dag_bits
try:
    import gold_dagcut_one
    R.STAGES['dagcut'] = gold_dagcut_one
except ImportError:
    pass
DAG_FILES = ('gold_dag_orders.py', 'gold_dag_bits.py', 'gold_dag_cuts.py', 'gold_dagcut_one.py')
here = os.path.dirname(os.path.abspath(__file__))


def dag_code():
    return hashlib.sha256(b''.join(open(os.path.join(here, f), 'rb').read() for f in DAG_FILES if os.path.exists(os.path.join(here, f)))).hexdigest()[:12]


def key_of(stage, task, sha):
    return (stage, task, sha, gold_dag_bits.CAP, float(gold_dag_bits.DELTA))


def rows_done(out):
    done = {}
    for p in {os.path.abspath(out)} | {os.path.abspath(x) for x in glob.glob(os.path.join(os.path.dirname(os.path.abspath(out)), 'rows-*.jsonl'))}:
        if os.path.exists(p):
            for l in open(p):
                try:
                    r = json.loads(l)
                    done[(r['stage'], r['task'], r['base_sha'], r['cap'], float(r['delta']))] = r.get('program')
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
    return done


def one(stage, t, lines, out):
    row = R.run_stage(stage, t, lines, out)
    row.update(base_sha=B.sha(lines), cap=gold_dag_bits.CAP, delta=float(gold_dag_bits.DELTA), dag_code=dag_code())
    return row


def main():
    tasks, lines_path, weights_path, out, k, n = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6])
    stages = os.environ.get('DAG_STAGES', 'dag').split()
    R.check_wheel()
    R.subreaper()
    done = rows_done(out)
    text = json.load(open(lines_path))
    mine = R.assign(R.tiers_of(tasks), json.load(open(weights_path)), n)[k]
    F.load_sampler()
    R.end_line(out)
    with open(out, 'a') as f:
        for t in mine:
            lines = text.get(t)
            if not lines:
                continue
            for stage in stages:
                if key_of(stage, t, B.sha(lines)) in done:
                    continue
                row = one(stage, t, lines, out)
                f.write(json.dumps(row) + '\n')
                f.flush()
                a = row.get('after') or {}
                print(t, stage, row.get('error', ''), row.get('worst', a.get('worst')), row.get('sum', a.get('sum')), row['wall'], row['peak_gib'], row['peak_procs'], flush=True)


if __name__ == '__main__':
    main()

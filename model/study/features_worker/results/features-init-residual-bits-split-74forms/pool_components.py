"""The components of the INIT nodes of the factored-priors pool run, per task of form-set.jsonl that the run holds. Stdlib and the zstd command.

  python3 pool_components.py

Writes pool-components.jsonl in this folder: one row per task and arm, flushed, with the count of nodes and of nodes per component. A rerun skips the rows it has. A node is a line of <task>.nodes.jsonl.zst, and its component is the name after the head in its `clause` where that starts `(INIT`.
"""
import collections
import json
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-pool-factored-priors-heldout35-600s-ship7/'
ARMS = 'factored_search', 'control_search'
INIT = re.compile(r'\(INIT \S+ (\w+)')


def main():
    tasks = sorted({json.loads(x)['task'] for x in open(HERE + 'form-set.jsonl')})
    out_path = HERE + 'pool-components.jsonl'
    done = set()
    if os.path.exists(out_path):
        done = {(r['task'], r['arm']) for r in map(json.loads, open(out_path))}
    t0 = time.time()
    with open(out_path, 'a') as out:
        for task in tasks:
            for arm in ARMS:
                path = '%s%s/%s.nodes.jsonl.zst' % (RUN, arm, task)
                if (task, arm) in done or not os.path.exists(path):
                    continue
                p = subprocess.Popen(['zstd', '-dc', path], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
                nodes, comps = 0, collections.Counter()
                for line in p.stdout:
                    nodes += 1
                    clause = json.loads(line).get('clause') or ''
                    for m in INIT.finditer(clause):
                        comps[m[1]] += 1
                p.wait()
                out.write(json.dumps(dict(task=task, arm=arm, nodes=nodes, init_nodes=sum(comps.values()), components=dict(comps))) + '\n')
                out.flush()
                print(task, arm, nodes, dict(comps), '%.1f s' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()

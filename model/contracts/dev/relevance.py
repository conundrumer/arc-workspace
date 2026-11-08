"""Dev labeling layer: the relevance of each table, from the near-miss worlds that judge_nearmiss.py writes. Not model input.

    python relevance.py OUT_DIR

The observer sees the train output, so a table's relevance is not information about the output: it is how well the table's claims about the
output single out the output among the outputs that plausible wrong readings of the rule give. A table's claims about the output are its
output features (those that read the train output), other than those of NOT_CLAIMS, with one value at every train example; the input grid's claims are its own such features.
A claim rules a near miss out where its value there differs from its value at every train example. A table's relevance is the share of the
near misses that its claims rule out, among those that the input grid's claims in GRID_CLAIMS do not rule out.

A table that reads the train outputs, directly, through a task parameter whose proposer reads them, or through other tables that do, has no
relevance judgment, since its claims about the output hold partly by its construction. A table with fewer than MIN_NEAR_MISSES near misses
left has none either.

Writes OUT_DIR/relevance.jsonl, one line per task; a restart skips the tasks written.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import analyze as A  # noqa: E402
import jsonl as J  # noqa: E402
import progress as PR  # noqa: E402
import roles as RO  # noqa: E402

MIN_NEAR_MISSES = 10
NOT_CLAIMS = tuple(x.strip() for x in RO.WITH_OUTPUT + PR.WITH_OUTPUT + PR.WITH_BOTH)  # a table's roles in the output and its count of claims hold one value by chance, and a near miss moves them
GRID_CLAIMS = (' vs the changed cells', ' Jaccard index with the changed cells', ' is the set of the colors the changed cells take', ' within the output colors', ' Jaccard index with the output cells',
               ' agrees with the output colors, proportion', ' has the output size', ' vs the output colors', ' vs the output foreground cells', ' is the output foreground box',
               ' vs the output foreground', ' vs the output cells of its colors', ' color counts agree with the output, proportion', ' vs the output foreground components')  # a fixed set, since a claim added here would take near misses from every table


def by_owner(feats):
    out = {}
    for k, v in feats.items():
        o, _, f = k.partition('|')
        if not f.endswith(' describe'):
            out.setdefault(o, {})[f] = v
    return out


def claims(dicts, owner):
    """{feature: value} of the owner's output features that hold one value at every dict."""
    keys = set.intersection(*[set(d) for d in dicts]) if dicts else set()
    return {k: dicts[0][k] for k in keys if A.is_output(owner + '|' + k) and not k.endswith(NOT_CLAIMS) and len({json.dumps(d[k]) for d in dicts}) == 1}


def task_rows(out_dir, task):
    recs = list(J.records(Path(out_dir) / (task + '.nearmiss.jsonl')))
    base = next((r for r in recs if r['id'] == 'base'), None)
    if base is None:
        return None
    own = base['examples']
    obs = {e: by_owner(w['features']) for e, w in own.items()}
    tables = sorted(set.intersection(*[set(o) for o in obs.values()]))
    readers = set(base['output_readers'])
    input_claims = {k: v for k, v in claims([w['base']['input'] for w in own.values()], 'input').items() if k.endswith(GRID_CLAIMS)}
    misses = [r for r in recs if r['id'].startswith('nearmiss.') and 'error' not in r]
    left = [r for r in misses if all(r['base']['input'].get(k, 'MISSING') == v for k, v in input_claims.items())]
    mobs = {r['id']: by_owner(r['features']) for r in left}
    rows = []
    for t in tables:
        if t.split('.')[0] in readers:
            rows.append(dict(t=t, status='reads the train outputs'))
            continue
        mine = claims([obs[e][t] for e in own], t)
        near = [r for r in left if t in mobs[r['id']]]
        rec = dict(t=t, claims=len(mine), near_misses=len(misses), left_by_the_input=len(near))
        if len(near) < MIN_NEAR_MISSES:
            rows.append(dict(rec, status='too few near misses'))
            continue
        ruled, by = 0, {}
        for r in near:
            broke = [k for k, v in mine.items() if mobs[r['id']][t].get(k, 'MISSING') != v]
            ruled += bool(broke)
            for k in broke:
                by[k] = by.get(k, 0) + 1
        rows.append(dict(rec, status='tested', relevance=ruled / len(near), ruling=sorted(by.items(), key=lambda kv: -kv[1])[:4]))
    return dict(task=task, tables=rows)


def main(out_dir):
    out = Path(out_dir) / 'relevance.jsonl'
    done = {json.loads(l)['task'] for l in out.read_text().splitlines()} if out.exists() else set()
    tasks = sorted({p.name.split('.')[0] for p in Path(out_dir).glob('*.nearmiss.jsonl*')} - done)
    t0 = time.time()
    with open(out, 'a') as f:
        for i, task in enumerate(tasks, 1):
            res = task_rows(out_dir, task)
            if res:
                f.write(json.dumps(res) + '\n')
                f.flush()
            print('%s [%d/%d, %.0f s]' % (task, i, len(tasks), time.time() - t0), flush=True)


if __name__ == '__main__':
    main(sys.argv[1])

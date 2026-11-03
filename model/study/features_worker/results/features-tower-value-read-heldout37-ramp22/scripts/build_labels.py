"""Labels, tower facts, shipped score, cover ids and exposure per node of each run. No engine replay: banks, cover lines and picks only.

  <engine python> build_labels.py read|fit|pass [--only TASK ...]    (pass: the ramp tasks of the arms bundle and pass of search-pass-r1; rows/pass/ARM_TASK_SEED)

Writes rows/<set>/<task>_<seed>.npz and rows/<set>/<task>_<seed>.json (events and counts). Skips runs with an npz. Streams: prints one line per run, a rate and an ETA.
Label (read set): a node is positive when a node of a cover line (held by the bank) has it as an ancestor through parents, or is it.
Label (fit set): the covering nodes are the nodes tagged with a gold form by the session key (n600-rows gold lists); N600 cover lines name no node.
Exposure (read set only; N600 has no .picks): scope calls = the picks lines the bank keeps (lineage), a call's scope = its picks and their ancestors.
"""
import bisect
import collections
import glob
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-tower-value-read-heldout37-ramp22/scripts')
import common as C


def fit_tags(task):
    """{node: [gold indices]} and the count of nodes the rows have no table for, from n600-rows."""
    tags, no_table, n = {}, 0, 0
    for p in sorted(glob.glob(C.N600_ROWS + task + '.part*.npz')):
        z = np.load(p, allow_pickle=False)
        meta = z['meta']
        gold = json.loads(str(z['gold'][0]))
        for i in range(len(meta)):
            n += 1
            if int(meta[i, 2]) == 4:
                no_table += 1
            if gold[i]:
                tags[int(meta[i, 0])] = gold[i]
    return tags, no_table, n


def run_one(group, seed, task, base, out_dir, stem_name=None):
    bank = C.load_bank(base + '.bank')
    nodes, forms = bank['nodes'], bank['forms']
    ids, anc, facts = C.tower(bank)
    score = bank['policy']['score']
    info = dict(task=task, seed=seed, group=group, nodes=len(ids), forms=len(forms))
    cov_time, cov_gold = {}, collections.defaultdict(list)
    first_nodes = set()
    if group == 'fit':
        tags, no_table, nrow = fit_tags(task)
        for n, g in tags.items():
            cov_gold[n] = g
            cov_time[n] = None
        first_nodes = set(tags)
        info.update(row_nodes=nrow, rows_no_table=no_table, covering_nodes=len(tags))
        events = []
    else:
        lineage = bank.get('lineage', [])
        lines = C.read_lines(base + '.cover')
        kept = [(e['proc'], e['nodes0'], e['nodes1']) for e in lineage]
        held = [x for x in lines if 'node' in x and x['node'] in nodes and any(x.get('proc') == pr and a <= x['node'] < b for pr, a, b in kept)]
        info.update(cover_lines=len(lines), cover_lines_held=len(held), cover_lines_dropped=len(lines) - len(held))
        by_gold = collections.defaultdict(list)
        for x in held:
            cov_gold[x['node']].append(x['gold'])
            cov_time[x['node']] = min(cov_time.get(x['node'], 1e30), x['time'])
            by_gold[x['gold']].append(x)
        events = []
        for g in sorted(by_gold):
            x = sorted(by_gold[g], key=lambda y: y['time'])[0]
            events.append(dict(gold=g, node=x['node'], time=x['time'], draw=x.get('draw')))
            first_nodes.add(x['node'])
        info.update(gold_covered=len(by_gold), events=len(events))
        info['gold_lines_dropped_only'] = sorted(set(x['gold'] for x in lines if 'gold' in x) - set(by_gold))

    def coverers_of(cset):
        co = collections.defaultdict(list)
        for c in cset:
            for x in anc[c] | {c}:
                co[x].append(c)
        return co

    co_all = coverers_of(set(cov_gold))
    co_first = coverers_of(first_nodes)
    for x, cs in co_all.items():
        assert all(c >= x for c in cs)
    n = len(ids)
    label = np.array([1 if x in co_all else 0 for x in ids], np.int8)
    label_first = np.array([1 if x in co_first else 0 for x in ids], np.int8)
    self_cover = np.array([1 if x in cov_gold else 0 for x in ids], np.int8)
    cover_ids = np.array([json.dumps(sorted(co_all.get(x, []))) for x in ids])
    fct = np.full(n, np.nan)
    if group != 'fit':
        for i, x in enumerate(ids):
            if x in co_all:
                fct[i] = min(cov_time[c] for c in co_all[x])
    # exposure
    exposure = np.full(n, np.nan)
    exp_before = np.full(n, np.nan)
    first_exp = np.full(n, np.nan)
    if group != 'fit':
        picks = C.read_lines(base + '.picks')
        by_proc = collections.defaultdict(list)
        for x in picks:
            by_proc[x['proc']].append(x)
        calls = []
        for e in bank.get('lineage', []):
            calls += sorted((x for x in by_proc.get(e['proc'], ()) if x['seq'] < e['picks1']), key=lambda x: x['seq'])
        times = collections.defaultdict(list)
        for x in calls:
            sc = set()
            for p in x['picks']:
                if p in nodes:
                    sc.add(p)
                    sc |= anc[p]
            for q in sc:
                times[q].append(x['time'])
        pos = {x: i for i, x in enumerate(ids)}
        for q, ts in times.items():
            ts.sort()
            i = pos[q]
            exposure[i] = len(ts)
            first_exp[i] = ts[0]
        exposure[np.isnan(exposure)] = 0
        for i, x in enumerate(ids):
            if exposure[i] == 0:
                exp_before[i] = 0
            elif x in co_all:
                exp_before[i] = bisect.bisect_right(times[x], fct[i])
            else:
                exp_before[i] = exposure[i]
        info.update(picks_lines_kept=len(calls), exposed_nodes=int((exposure > 0).sum()))
    cols = dict(node=np.array(ids), score=np.array([score.get(x, np.nan) for x in ids]), label=label, label_first=label_first, self_cover=self_cover, cover_ids=cover_ids,
                exposure=exposure, exposure_before_cover=exp_before, first_exposed_time=first_exp, first_cover_time=fct,
                node_depth=np.array([nodes[x].depth for x in ids]), form_depth=np.array([forms[nodes[x].form].depth for x in ids]))
    for k, v in facts.items():
        cols[k] = np.array([v[x] for x in ids])
    info.update(positives=int(label.sum()), positives_first=int(label_first.sum()), self_covers=int(self_cover.sum()))
    os.makedirs(out_dir, exist_ok=True)
    stem = '%s/%s' % (out_dir, stem_name or '%s_%s' % (task, seed))
    info['stem'] = stem_name or '%s_%s' % (task, seed)
    json.dump(dict(info=info, events=events), open(stem + '.json.tmp', 'w'))
    os.replace(stem + '.json.tmp', stem + '.json')
    np.savez_compressed(stem + '.tmp.npz', **cols)
    os.replace(stem + '.tmp.npz', stem + '.npz')
    return info


def main():
    which = sys.argv[1]
    only = set(sys.argv[3:]) if len(sys.argv) > 2 and sys.argv[2] == '--only' else None
    if which == 'pass':
        runs = [(g, s, t, b, '%s_%s_%s' % (arm, t, s)) for g, s, t, b, arm in C.pass_runs()]
    else:
        runs = [(g, s, t, b, '%s_%s' % (t, s)) for g, s, t, b in (C.read_runs() if which == 'read' else C.fit_runs())]
    out_dir = C.REC + '/rows/' + which
    todo = [r for r in runs if (only is None or r[2] in only) and not os.path.exists('%s/%s.npz' % (out_dir, r[4]))]
    t0 = time.time()
    for i, (group, seed, task, base, stem) in enumerate(todo):
        info = run_one(group, seed, task, base, out_dir, stem)
        el = time.time() - t0
        rate = (i + 1) / el
        print('%s %s %s nodes %d pos %d (first %d) self %d | %d/%d, %.2f runs/s, eta %.0f s' % (group, task, seed, info['nodes'], info['positives'], info['positives_first'],
              info['self_covers'], i + 1, len(todo), rate, (len(todo) - i - 1) / rate), flush=True)
        if time.time() - t0 > 22:
            print('stopping at the time budget; rerun to continue', flush=True)
            break


main()

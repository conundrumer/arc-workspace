"""Runs the exposure measure of search_joint_exposure.py on the jobs of one run, one job at a time, and prints the shares.

  <python> -I search_joint_exposure_check.py RUN_OUT_FOLDER CACHE.json ARM [ARM ...] [--budget SECONDS]

RUN_OUT_FOLDER  the folder that holds <arm>/<task>/work (for round 1: .../runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out).
ARM             a job name such as bundle_s0.
CACHE.json      the results so far. A job in it is not read again. The script reads jobs until BUDGET_SECONDS (default 15) have passed, so a long run is several calls.
It uses the 37 held-out tasks of refit-tasks.json and the gold of points-eval.json, both found in the kit folder beside this one (--kit) or in round 1's out-r1 folder.
Prints, for each arm and horizon, the openings, the share of openings with an exposed form (any, 1-read form, 2+-read form), and the jobs still to read.
"""
import json
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import search_node_score_parity as PA  # noqa: E402
import search_node_score_read as R  # noqa: E402
import search_joint_exposure as X  # noqa: E402

KIT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/refit/out-r1'


def main():
    args = sys.argv[1:]
    budget = 15.0
    if '--budget' in args:
        i = args.index('--budget')
        budget = float(args[i + 1])
        del args[i:i + 2]
    out, cache_path, arms = args[0], args[1], args[2:]
    tasks = json.load(open(KIT + '/refit-tasks.json'))['heldout37']
    gold = {x['task']: R.gold_info(x['gold_sexp']) for x in json.load(open(KIT + '/points-eval.json'))}
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    t0 = time.time()
    left = 0
    for arm in arms:
        for task in tasks:
            key = '%s/%s' % (arm, task)
            if key in cache:
                continue
            if time.time() - t0 > budget:
                left += 1
                continue
            folder = '%s/%s/%s' % (out, arm, task)
            work = '%s/work/%s' % (folder, task)
            bank = PA.load_bank(work + '.out.jsonl.bank')
            picks = PA.read_lines(work + '.out.jsonl.picks')
            cache[key] = X.exposure(picks, PA.read_lines(work + '.out.jsonl.cover'), bank['lineage'], gold[task]['reads'], X.start_of(folder, picks))
    tmp = cache_path + '.tmp'
    json.dump(cache, open(tmp, 'w'))
    os.replace(tmp, cache_path)
    print('jobs still to read: %d' % left)
    for arm in arms:
        rows = [cache['%s/%s' % (arm, t)] for t in tasks if '%s/%s' % (arm, t) in cache]
        for h in ('all', str(X.SECONDS)):
            tot = {}
            for r in rows:
                tot = X.add_counts(tot, r[h])
            if tot.get('openings'):
                print('%-10s %-3s tasks %2d openings %5d  any %.2f%%  1-read %.2f%%  2+-read %.2f%%' % (
                    arm, h, len(rows), tot['openings'], X.share(tot, 'any'), X.share(tot, 'reads1'), X.share(tot, 'reads2')))


main()

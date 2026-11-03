"""S, the gold clause's bits under the recorded scope (or_q.walk, summed over orders, as ../job.py walks it), with the relation steer as the kit
has it (off) and with the steer moving mass only within groups (on).

    bash ../env.sh split-steer/job2.py --set C|covered [--shard I/N] [--budget S] [--only TASK:G,...] [--skip TASK:G,...] [--b-unsteered]

The switch: at each atom start where the steer applies (sample2_col.py 2428-2430), the options split into D (KIND relation, rel_name
'declared') and B (all others, NOT among them). For each group G of two or more options, with r_o the factor rel_factors gives:
    ws'[o] = T_G * ws[o] * r_o / sum_{j in G} ws[j] * r_j,   T_G = sum_{j in G} ws[j] (ws before the steer multiply)
and alt the same with its own totals. A group of one option keeps its weight; an empty group is skipped. With --b-unsteered, B keeps ws.
It is a monkeypatch: rel_factors hands the kit factors of 1 and keeps its own, and GuidedDrawer.pick_complete regroups the weights.

The forms: rows of ../forms.<i>of2.jsonl (C) or ../forms-covered.<i>of2.jsonl (covered) with status mapped and S valid. One JSON line per form
to walks-<set>[-bu].<I>of<N>.jsonl, streamed; forms already there are skipped. A task stays in one shard (crc32 of the task).
"""
import json
import os
import sys
import time
import zlib

T0 = time.time()
REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'
HERE = REC + '/split-steer'
argv = sys.argv[1:]


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


SET = opt('--set')
assert SET in ('C', 'covered')
SHARD_I, SHARD_N = (int(x) for x in opt('--shard', '0/1').split('/'))
BUDGET = float(opt('--budget')) if opt('--budget') else None
ONLY = opt('--only')
SKIP = opt('--skip')
BU = '--b-unsteered' in argv
OUT = '%s/walks-%s%s.%dof%d.jsonl' % (HERE, SET, '-bu' if BU else '', SHARD_I, SHARD_N)

src = open(REC + '/job.py').read()
src = src[:src.rindex('\nmain()')]
sys.argv = ['job.py'] + (['--covered'] if SET == 'covered' else [])
ns = dict(__name__='jobmod', __file__=REC + '/job.py')
exec(compile(src, REC + '/job.py', 'exec'), ns)
or_q, live = ns['or_q'], ns['live']
S = live.S

SWITCH = dict(on=False, picks=0, regrouped=0)
_rf = S.Drawer.rel_factors


def rel_factors(self, fr, n, popts, k, scope_types, key, rel, joined, leaf):
    got = _rf(self, fr, n, popts, k, scope_types, key, rel, joined, leaf)
    if not SWITCH['on']:
        return got
    self._pend_rf = list(got)
    return [1.0] * len(got)


S.Drawer.rel_factors = rel_factors
_pc = or_q.GuidedDrawer.pick_complete


def regroup(ws, rf, groups, steer):
    out = list(ws)
    for G, on in zip(groups, steer):
        if len(G) < 2:
            continue
        if not on:
            continue
        T = sum(ws[i] for i in G)
        Z = sum(ws[i] * rf[i] for i in G)
        if Z <= 0:
            continue
        for i in G:
            out[i] = T * ws[i] * rf[i] / Z
    return out


def pick_complete(self, n, opts, weights, key, alt=None):
    rf = getattr(self, '_pend_rf', None)
    if rf is not None:
        self._pend_rf = None
        SWITCH['picks'] += 1
        assert n.phase in ('root', 'root2') and len(rf) == len(opts), (n.phase, len(rf), len(opts))
        D = [i for i, o in enumerate(opts) if self.fr.KIND[o] == 'relation' and self.rel_name(o) == 'declared']
        Ds = set(D)
        B = [i for i in range(len(opts)) if i not in Ds]
        steer = (True, not BU)
        if any(abs(x - 1.0) > 0 for x in rf):
            SWITCH['regrouped'] += 1
        weights = regroup(weights, rf, (D, B), steer)
        if alt is not None:
            alt = regroup(alt, rf, (D, B), steer)
    return _pc(self, n, opts, weights, key, alt)


or_q.GuidedDrawer.pick_complete = pick_complete
compact = ns['compact']


def walk_S(item, x):
    arm, task, g = item[:3]
    return compact(or_q.walk(ns['sampler'], task, arm, [g, 0], x['scope'], x['target'], x['sess'], x['d'], x['kind']))


def main():
    files = ['%s/%s.%dof2.jsonl' % (REC, 'forms' if SET == 'C' else 'forms-covered', i) for i in range(2)]
    rows = [json.loads(l) for f in files for l in open(f)]
    rec = {(r['arm'], r['task'], r['g']): r for r in rows if r.get('status') == 'mapped' and r.get('S') and r['S'].get('valid')}
    items = {it[:3]: it for it in ns['build_items']()}
    want = [k for k in sorted(rec, key=lambda k: (k[1], k[0], k[2])) if zlib.crc32(k[1].encode()) % SHARD_N == SHARD_I]
    if ONLY:
        sel = {(x.split(':')[0], int(x.split(':')[1])) for x in ONLY.split(',')}
        want = [k for k in want if (k[1], k[2]) in sel]
    if SKIP:
        sk = {(x.split(':')[0], int(x.split(':')[1])) for x in SKIP.split(',')}
        want = [k for k in want if (k[1], k[2]) not in sk]
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            y = json.loads(l)
            done.add((y['arm'], y['task'], y['g']))
    todo = [k for k in want if k not in done]
    print('set %s shard %d/%d: %d forms, %d done, %d todo -> %s' % (SET, SHARD_I, SHARD_N, len(want), len(want) - len(todo), len(todo), OUT), flush=True)
    n = 0
    for k in todo:
        if BUDGET is not None and time.time() - T0 > BUDGET:
            break
        t1 = time.time()
        r = rec[k]
        out = dict(arm=k[0], task=k[1], g=k[2], set=SET, b_unsteered=BU, S_rec=r['S']['total'], DB=(r.get('DB') or {}).get('bits'), DB_status=(r.get('DB') or {}).get('status'))
        try:
            row, x = ns['prepare'](items[k])
            assert row['status'] == 'mapped' and row['target'] == r['target'], (row['status'], row['target'], r['target'])
            SWITCH['on'] = False
            out['S_off'] = walk_S(items[k], x)
            SWITCH.update(on=True, picks=0, regrouped=0)
            out['S_on'] = walk_S(items[k], x)
            out['switch_picks'], out['switch_regrouped'] = SWITCH['picks'], SWITCH['regrouped']
            SWITCH['on'] = False
            out['status'] = 'ok'
        except Exception as e:  # noqa: BLE001
            SWITCH['on'] = False
            out.update(status='error', error='%s: %s' % (type(e).__name__, str(e)[:300]))
        out['wall'] = round(time.time() - t1, 2)
        with open(OUT, 'a') as fh:
            fh.write(json.dumps(out, default=str) + '\n')
        n += 1
        print('%s %s g%d %s rec %s off %s on %s %.1fs' % (k[0], k[1], k[2], out['status'], out['S_rec'], (out.get('S_off') or {}).get('total'), (out.get('S_on') or {}).get('total'), out['wall']), flush=True)
    print('done %d todo %d, %.1fs' % (len(want) - len(todo) + n, len(todo) - n, time.time() - T0), flush=True)


main()

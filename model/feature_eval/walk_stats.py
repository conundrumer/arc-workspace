#!/usr/bin/env python
"""Scene and Rule recognition from the walks that the encoder wrote, by class.

  uv run python model/feature_eval/walk_stats.py manifest scene|rule [--negatives N] [--first N]
  uv run python model/feature_eval/walk_stats.py stats scene|rule --size D [--negatives N]
  uv run python model/feature_eval/walk_stats.py watch scene|rule --size D [--negatives N] [--seconds S]

`manifest` writes the grids of each task and the file the encoder's `walk` reads. `stats` reads the
walks that exist, writes results/<test>/<task><suffix>.d<d>.json at the top size, and writes the curve
at results/<test>/curve<suffix>.json: per size, the mean over the tasks with a walk at the top size,
its 99% interval, on hard items, and paired with the first version's line. `watch` does that as each
walk appears, until none has appeared for S seconds.
"""
import argparse
import glob
import json
import os
import random
import time

import numpy as np

from common import RESULTS, auc_of, eval_tasks, write_json_atomic
import rule as rule_test
import scene as scene_test

TESTS = {'scene': 'scene-input', 'rule': 'rule-base'}
PAYLOAD = (1 << 62) - 1
FRACTIONS = (0.002, 0.01, 0.05, 0.2, 1.0)
NULL_DRAWS = 20


def directory(test):
    return RESULTS / TESTS[test] / FOLDER


FOLDER = 'walk2'


def run_tag():
    """The mark of a later run's files, so a partial run leaves the last whole one in place."""
    return '' if FOLDER == 'walk2' else f'.{FOLDER}'


def items_of(test, task, limit):
    """What to compare, per item: the places the claims come from, the true place, the other
    places, and the flag of each other place that survives where the test has one."""
    if test == 'scene':
        grids, input_places, negatives = scene_test.items_of(task, limit)
        out = []
        for h, true_place in enumerate(input_places):
            out.append(([place for k, place in enumerate(input_places) if k != h], true_place, negatives[h], None))
        return grids, out
    pairs, count, near = rule_test.items_of(task)
    out = []
    for h in range(count):
        out.append(([k for k in range(count) if k != h], h, [place for place, _ in near[h]], np.array([flag for _, flag in near[h]], dtype=bool)))
    return pairs, out


def extra_instances(test, task, limit, count=8):
    """The true instances of `count` other tasks, drawn with a seed of the task: the grids that give
    the null's claims, which a walk reads beside the task's own."""
    others = [other for other in eval_tasks(60) if other != task]
    chosen = random.Random(f'null/{task}').sample(others, min(count, len(others)))
    extras = {}
    for other in chosen:
        if test == 'scene':
            grids, input_places, _ = scene_test.items_of(other, 0)
            extras[other] = [grids[place] for place in input_places]
        else:
            pairs, instances, _ = rule_test.items_of(other)
            extras[other] = pairs[:instances]
    return extras


def null_auc(words, inverse, sizes, d, items, extras):
    """The AUC with the claims from another task, over `NULL_DRAWS` draws with a fixed seed. A unit
    is a distinct pair of a value vector over this task's instances and a claim."""
    if not extras:
        return None
    rng = random.Random(f'draws/{d}')
    keep = sizes <= d
    held = words[keep]
    classes = inverse[keep]
    per_draw = []
    tasks = sorted(extras)
    for _ in range(NULL_DRAWS):
        aucs = []
        for others, true_place, places, _ in items:
            if not len(places):
                continue
            places_of = extras[rng.choice(tasks)]
            leave = rng.randrange(len(places_of))
            claim_places = [place for at, place in enumerate(places_of) if at != leave]
            if not claim_places:
                continue
            first = held[:, claim_places[0]]
            mask = np.all(held[:, claim_places] == first[:, None], axis=1) & ((first & np.uint64(PAYLOAD)) != 0)
            if not mask.any():
                aucs.append(0.5)
                continue
            units, at = np.unique(np.stack([classes[mask].astype(np.uint64), first[mask]], axis=1), axis=0, return_index=True)
            rows = held[mask][at]
            claim = first[mask][at]
            v_true = float((rows[:, true_place] != claim).mean())
            v_other = (rows[:, places] != claim[:, None]).mean(axis=0)
            aucs.append(auc_of(v_true, v_other))
        if aucs:
            per_draw.append(float(np.mean(aucs)))
    return float(np.mean(per_draw)) if per_draw else None


def read_walk(prefix, size):
    meta = json.load(open(f'{prefix}.d{size}.json'))
    sizes = np.fromfile(f'{prefix}.d{size}.sizes', dtype=np.uint8)
    words = np.fromfile(f'{prefix}.d{size}.words', dtype=np.uint64).reshape(len(sizes), meta['grids'])
    order = np.fromfile(f'{prefix}.d{size}.order', dtype=np.uint32)
    return meta, sizes, words, order


def violations(words, others, true_place, places, claims='active'):
    """The share of the classes with one value at `others` whose value differs, at the true place
    and at `places`, and the number of claims. An active claim's value is not its root's default,
    a claim of absence's is, and neither is no value."""
    if len(others) == 0 or len(words) == 0:
        return 0.0, np.zeros(len(places)), 0
    first = words[:, others[0]]
    mask = np.all(words[:, others] == first[:, None], axis=1)
    if claims == 'active':
        mask &= (first & np.uint64(PAYLOAD)) != 0
    elif claims == 'absence':
        mask &= ((first & np.uint64(PAYLOAD)) == 0) & (first != 0)
    count = int(mask.sum())
    if count == 0:
        return 0.0, np.zeros(len(places)), 0
    held = words[mask]
    claim = first[mask]
    v_true = float((held[:, true_place] != claim).mean())
    v_other = (held[:, places] != claim[:, None]).mean(axis=0) if len(places) else np.zeros(0)
    return v_true, v_other, count


def coverage_of(words, sizes, order, meta, items, top, hard):
    """The statistics at each coverage that the walk reached: within each tier, with the tiers
    before it whole, each point the classes of a seeded random share of that tier's operators."""
    points = []
    start = 0
    for tier, count in zip(meta['tiers'], meta['tier_edges']):
        for fraction in FRACTIONS:
            cut = start + int(np.ceil(fraction * count))
            if count == 0 or cut > meta['top_done']:
                continue
            held = words[(sizes < top) | ((sizes == top) & (order < cut))]
            aucs, hards, survive = [], [], []
            for at, (others, true_place, places, flags) in enumerate(items):
                v_true, v_other, _ = violations(held, others, true_place, places)
                value = auc_of(v_true, v_other)
                if value is not None:
                    aucs.append(value)
                if len(places) and hard[at].any():
                    hards.append(auc_of(v_true, v_other[hard[at]]))
                if flags is not None and len(places) and flags.any():
                    survive.append(auc_of(v_true, v_other[flags]))
            points.append({
                'tier': tier, 'fraction': fraction, 'operators': cut, 'classes': len(held),
                'auc': float(np.mean(aucs)) if aucs else None,
                'auc_hard': float(np.mean(hards)) if hards else None,
                'auc_survive': float(np.mean(survive)) if survive else None,
            })
        start += count
    return points


def task_stats(test, task, prefix, top, limit):
    meta, sizes, every, order = read_walk(prefix, top)
    grids, items = items_of(test, task, limit)
    # The columns past the task's own hold the null's other tasks, whose classes split ones of
    # this task: the statistics count classes over the task's own instances.
    extras = {}
    extras_path = f'{prefix}.extras.json'
    if os.path.exists(extras_path):
        extras = json.load(open(extras_path))
    own = len(grids)
    words, first_at, inverse = np.unique(every[:, :own], axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
    # A class's size and order are those of its first root.
    earliest = np.full(len(words), len(sizes), dtype=np.int64)
    np.minimum.at(earliest, inverse, np.arange(len(sizes)))
    all_sizes, sizes = sizes, sizes[earliest]
    order = order[earliest]
    records = {}
    hard = {}
    for d in range(1, top + 1):
        held = words[sizes <= d]
        per_item = []
        for at, (others, true_place, places, flags) in enumerate(items):
            v_true, v_other, claims = violations(held, others, true_place, places)
            if d == 1:
                hard[at] = np.abs(v_other - v_true) < 1e-12
            absence_true, absence_other, absence_claims = violations(held, others, true_place, places, 'absence')
            all_true, all_other, _ = violations(held, others, true_place, places, 'all')
            record = {
                'claims': claims, 'claims_absence': absence_claims, 'others': len(places), 'v_true': v_true,
                'auc': auc_of(v_true, v_other),
                'auc_absence': auc_of(absence_true, absence_other),
                'auc_all': auc_of(all_true, all_other),
                'auc_hard': auc_of(v_true, v_other[hard[at]]) if len(places) and hard[at].any() else None,
                'hard': int(hard[at].sum()) if len(places) else 0,
                'false_rule_out': bool(v_true > 0),
                'rule_outs': float((v_other > 0).mean()) if len(places) else None,
            }
            if flags is not None and len(places):
                record['auc_survive'] = auc_of(v_true, v_other[flags])
                record['auc_other'] = auc_of(v_true, v_other[~flags])
                record['auc_survive_hard'] = auc_of(v_true, v_other[flags & hard[at]])
            per_item.append(record)
        keep = sizes <= d
        default = (words[keep] & np.uint64(PAYLOAD)) == 0
        stopped = words[keep] == 0
        covered = meta['top_done'] / meta['top_edges'] if meta.get('top_edges') else 1.0
        record = {
            'task': task, 'd': d, 'grids': int(words.shape[1]), 'classes': int(keep.sum()), 'classes_at_size': int((sizes == d).sum()), 'seconds': meta['seconds'],
            'bounded': covered < 1.0, 'covered': covered, 'top_edges': meta.get('top_edges'), 'top_done': meta.get('top_done'),
            'active_classes': float((~default & ~stopped).sum(axis=0).mean()),
            'null': null_auc(every, inverse, all_sizes, d, items, extras),
            'per_item': per_item,
        }
        for key in ('auc', 'auc_absence', 'auc_all', 'auc_hard', 'auc_survive', 'auc_other', 'auc_survive_hard'):
            values = [item[key] for item in per_item if item.get(key) is not None]
            record[key] = float(np.mean(values)) if values else None
        records[d] = record
    records[top]['coverage'] = coverage_of(words, sizes, order, meta, items, top, hard)
    records[top]['component_seconds'] = meta.get('component_seconds')
    return records


def bootstrap(values, seed=7, draws=2000):
    values = np.array(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (draws, len(values)))].mean(axis=1)
    return float(np.quantile(means, 0.005)), float(np.quantile(means, 0.995))


def reference_of(test):
    out = {}
    folder = 'reference-active' if glob.glob(str(RESULTS / 'reference-active/????????.json')) else 'reference-class'
    for path in glob.glob(str(RESULTS / f'{folder}/????????.json')):
        record = json.load(open(path))
        values = [item['auc_class'] for item in record[test] if item.get('auc_class') is not None]
        if values:
            out[record['task']] = float(np.mean(values))
    return out


def write_curve(test, top, limit, tasks):
    suffix = f'.n{limit}' if limit and test == 'scene' else ''
    reference = reference_of(test)
    curve = []
    for d in range(1, top + 1):
        aucs = [out[d]['auc'] for out in tasks.values() if out[d]['auc'] is not None]
        if not aucs:
            continue
        low, high = bootstrap(aucs)
        row = {'d': d, 'tasks': len(aucs), 'auc': float(np.mean(aucs)), 'interval_99': [low, high]}
        nulls = [out[d]['null'] for out in tasks.values() if out[d].get('null') is not None]
        if nulls:
            row['null'] = float(np.mean(nulls))
            row['null_tasks'] = len(nulls)
        hard = [out[d]['auc_hard'] for out in tasks.values() if out[d]['auc_hard'] is not None]
        if hard:
            row['auc_hard'] = float(np.mean(hard))
            row['hard_interval_99'] = list(bootstrap(hard))
            row['hard_tasks'] = len(hard)
        paired = [out[d]['auc'] - reference[task] for task, out in tasks.items() if task in reference and out[d]['auc'] is not None]
        if paired:
            row['first_version'] = float(np.mean([reference[task] for task in tasks if task in reference]))
            row['paired_difference'] = float(np.mean(paired))
            row['paired_interval_99'] = list(bootstrap(paired))
        for key in ('auc_absence', 'auc_all', 'auc_survive', 'auc_other', 'auc_survive_hard'):
            values = [out[d][key] for out in tasks.values() if out[d].get(key) is not None]
            if values:
                row[key] = float(np.mean(values))
        row['claims_mean'] = float(np.mean([item['claims'] for out in tasks.values() for item in out[d]['per_item']]))
        row['no_claim_share'] = float(np.mean([item['claims'] == 0 for out in tasks.values() for item in out[d]['per_item']]))
        row['classes_mean'] = float(np.mean([out[d]['classes'] for out in tasks.values()]))
        row['active_classes_mean'] = float(np.mean([out[d]['active_classes'] for out in tasks.values()]))
        row['seconds_mean'] = float(np.mean([out[d]['seconds'] for out in tasks.values()]))
        row['bounded_tasks'] = int(sum(out[d]['bounded'] for out in tasks.values()))
        row['covered_mean'] = float(np.mean([out[d]['covered'] for out in tasks.values()]))
        items = [item for out in tasks.values() for item in out[d]['per_item']]
        row['false_rule_out_rate'] = float(np.mean([item['false_rule_out'] for item in items]))
        row['rule_out_rate'] = float(np.mean([item['rule_outs'] for item in items if item['rule_outs'] is not None]))
        curve.append(row)
    left_out = [task for task in eval_tasks(60) if task not in tasks]
    coverage = {}
    for task, out in tasks.items():
        for point in out[top]['coverage']:
            coverage.setdefault((point['tier'], point['fraction']), []).append((task, point))
    rows = []
    for (tier, fraction), held in coverage.items():
        gains = [point['auc'] - tasks[task][1]['auc'] for task, point in held if point['auc'] is not None and tasks[task][1]['auc'] is not None]
        row = {
            'tier': tier, 'fraction': fraction, 'tasks': len(held),
            'auc': float(np.mean([point['auc'] for _, point in held if point['auc'] is not None])) if gains else None,
            'auc_at_size_1': float(np.mean([tasks[task][1]['auc'] for task, point in held if point['auc'] is not None and tasks[task][1]['auc'] is not None])) if gains else None,
            'gain_over_size_1': float(np.mean(gains)) if gains else None,
            'gain_interval_99': list(bootstrap(gains)) if len(gains) > 1 else None,
            'classes': float(np.mean([point['classes'] for _, point in held])),
        }
        hard = [point['auc_hard'] for _, point in held if point['auc_hard'] is not None]
        if hard:
            row['auc_hard'] = float(np.mean(hard))
            row['hard_tasks'] = len(hard)
        survive = [point['auc_survive'] for _, point in held if point['auc_survive'] is not None]
        if survive:
            row['auc_survive'] = float(np.mean(survive))
        rows.append(row)
    write_json_atomic(RESULTS / TESTS[test] / f'curve{suffix}{run_tag()}.json', {'test': test, 'top': top, 'bounded': True, 'statistic': 'shares of active classes', 'tasks': sorted(tasks), 'left_out': left_out, 'curve': curve, 'coverage': rows})
    return curve


def read_task(test, task, top, limit, suffix):
    """The statistics of `task`, where its walk ended, and each result written."""
    folder = directory(test)
    prefix = folder / f'{task}{suffix}'
    if not (folder / f'{task}{suffix}.d{top}.json').exists():
        return None
    out = task_stats(test, task, prefix, top, limit)
    for d, record in out.items():
        write_json_atomic(folder / f'{task}{suffix}.stats.d{d}.json', record)
    write_json_atomic(RESULTS / TESTS[test] / f'{task}{suffix}{run_tag()}.d{top}.json', out[top])
    return out


def stats(test, top, limit):
    suffix = f'.n{limit}' if limit and test == 'scene' else ''
    tasks = {}
    for task in eval_tasks(60):
        out = read_task(test, task, top, limit, suffix)
        if out is not None:
            tasks[task] = out
    for row in write_curve(test, top, limit, tasks):
        print(json.dumps(row))


def watch(test, top, limit, seconds):
    suffix = f'.n{limit}' if limit and test == 'scene' else ''
    folder = directory(test)
    tasks = {}
    seen = {}
    last = time.time()
    while time.time() - last < seconds:
        fresh = False
        for task in eval_tasks(60):
            path = folder / f'{task}{suffix}.d{top}.json'
            if not path.exists() or seen.get(task) == path.stat().st_mtime:
                continue
            seen[task] = path.stat().st_mtime
            out = read_task(test, task, top, limit, suffix)
            if out is not None:
                tasks[task] = out
                fresh = True
        if fresh:
            last = time.time()
            curve = write_curve(test, top, limit, tasks)
            print(json.dumps({'tasks': len(tasks), 'curve': [{key: row.get(key) for key in ('d', 'tasks', 'auc', 'auc_hard', 'paired_difference', 'classes_mean', 'covered_mean', 'bounded_tasks')} for row in curve]}), flush=True)
        else:
            time.sleep(15)


def manifest(test, limit, first, null_tasks):
    suffix = f'.n{limit}' if limit and test == 'scene' else ''
    folder = directory(test)
    folder.mkdir(parents=True, exist_ok=True)
    lines = []
    for task in eval_tasks(first):
        grids, _ = items_of(test, task, limit)
        grids = list(grids)
        if null_tasks:
            places = {}
            for other, instances in extra_instances(test, task, limit, null_tasks).items():
                places[other] = list(range(len(grids), len(grids) + len(instances)))
                grids.extend(instances)
            (folder / f'{task}{suffix}.extras.json').write_text(json.dumps(places))
        path = folder / f'{task}{suffix}.grids.json'
        path.write_text(json.dumps(grids))
        lines.append(f'{task}\t{path}\t{folder / (task + suffix)}')
    target = folder / f'manifest{suffix}.tsv'
    target.write_text('\n'.join(lines) + '\n')
    print(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['manifest', 'stats', 'watch'])
    parser.add_argument('test', choices=['scene', 'rule'])
    parser.add_argument('--size', type=int, default=2)
    parser.add_argument('--negatives', type=int, default=None)
    parser.add_argument('--first', type=int, default=60)
    parser.add_argument('--seconds', type=float, default=7200)
    parser.add_argument('--folder', default='walk2')
    parser.add_argument('--null-tasks', type=int, default=0, help='the other tasks whose true instances a walk reads, for the null')
    a = parser.parse_args()
    global FOLDER
    FOLDER = a.folder
    if a.command == 'manifest':
        manifest(a.test, a.negatives, a.first, a.null_tasks)
    elif a.command == 'watch':
        watch(a.test, a.size, a.negatives, a.seconds)
    else:
        stats(a.test, a.size, a.negatives)


if __name__ == '__main__':
    main()

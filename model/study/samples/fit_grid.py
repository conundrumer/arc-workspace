"""The choice of the fit's settings by held-out loss: a grid of LightGBM settings over one binned set of training instances.

    python3 fit_grid.py --points DIR --out DIR [--points-per-task N] [--seed S] [--threads N] [--drop-names ...] [--drop-prefixes ...]

The train tasks whose sha256 is 0 mod 10 are held out. The files are read and binned once, as fit_trees.py reads and bins them, and each setting of the grid is fit on that set with the
writer's objective (fit_trees.objective_of) until its held-out loss has not fallen for 50 rounds. Each fit's line goes to OUT/grid.jsonl as soon as it ends: the setting, its best round, the
held-out loss and top-1 at that round, the largest |leaf value| of its trees to that round, and its seconds. A rerun skips the settings that the file has. The settings move one at a time
from the base: the learning rate, LightGBM's max_delta_step (its cap on a leaf's step before the learning rate), min_sum_hessian_in_leaf and lambda_l2."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np

import fit_trees as F

BASE = dict(learning_rate=0.05, max_delta_step=0.0, min_sum_hessian_in_leaf=1e-3, lambda_l2=0.0)
GRID = [{}, dict(max_delta_step=20.0), dict(max_delta_step=50.0), dict(min_sum_hessian_in_leaf=1.0), dict(min_sum_hessian_in_leaf=10.0),
        dict(lambda_l2=10.0), dict(lambda_l2=100.0), dict(learning_rate=0.02), dict(learning_rate=0.1)]


def held_out(task: str) -> bool:
    return int(hashlib.sha256(task.encode()).hexdigest(), 16) % 10 == 0


def largest_leaf(booster: lgb.Booster, rounds: int) -> float:
    def walk(node: dict) -> float:
        if 'leaf_value' in node:
            return abs(float(node['leaf_value']))
        return max(walk(node['left_child']), walk(node['right_child']))
    return max((walk(t['tree_structure']) for t in booster.dump_model(num_iteration=rounds)['tree_info']), default=0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--points', type=Path, nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--points-per-task', type=int, default=0)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--threads', type=int, default=6)
    ap.add_argument('--max-rounds', type=int, default=3000)
    ap.add_argument('--drop-names', default='')
    ap.add_argument('--drop-prefixes', default='')
    a = ap.parse_args()
    F.DROP = tuple(x for x in a.drop_prefixes.split(',') if x)
    F.DROP_NAMES = frozenset(x for x in a.drop_names.split(',') if x)
    a.out.mkdir(parents=True, exist_ok=True)
    lines = a.out / 'grid.jsonl'
    done = {json.dumps(json.loads(x)['setting'], sort_keys=True) for x in lines.read_text().splitlines()} if lines.exists() else set()
    t0 = time.time()
    _, _, all_heads = F.split_files(a.points, set())
    dev_tasks = {t for t in all_heads if held_out(t)}
    train_files, dev_files, heads = F.split_files(a.points, dev_tasks)
    fields = F.feature_fields([heads[F.points_stem(p)] for p in (*train_files, *dev_files)])
    layout = F.layout_of(fields)
    train, train_rows, reader, _ = F.plan_rows(train_files, heads, layout, a.points_per_task, a.seed)
    safe = F.booster_names(layout.names)
    dev, _ = F.load(dev_files, heads, layout, a.points_per_task, a.seed)
    print(f'{len(train_files)} train and {len(dev_files)} held-out tasks; train {train.describe()["groups"]} points, held out {dev.describe()["groups"]}; read in {time.time() - t0:.0f} s', flush=True)
    fixed = dict(num_leaves=63, min_data_in_leaf=100, feature_fraction=0.8, seed=a.seed, num_threads=a.threads, verbosity=-1, metric='None', feature_pre_filter=False)
    train_set = F.SequenceDataset(train_rows, label=train.positive, feature_name=safe, params=dict(fixed, max_bin=255), free_raw_data=True)
    train_set.construct()
    reader.release()
    dev_set = lgb.Dataset(dev.matrix, label=dev.positive, reference=train_set, feature_name=safe, free_raw_data=False)
    print(f'binned in {time.time() - t0:.0f} s', flush=True)
    objective = F.objective_of(train)
    starts, sizes, positive = dev.starts, dev.sizes, dev.positive.astype(np.float64)

    def dev_loss(scores, _data):
        return 'dev_loss', float(F.group_terms(np.asarray(scores, np.float64), positive, starts, sizes).loss.mean()), False

    for change in GRID:
        setting = dict(BASE, **change)
        key = json.dumps(setting, sort_keys=True)
        if key in done:
            continue
        t1 = time.time()
        reporter = F.Reporter(0)
        booster = lgb.train(dict(fixed, **setting, objective=objective), train_set, num_boost_round=a.max_rounds, valid_sets=[dev_set], valid_names=['dev'], feval=dev_loss,
                            callbacks=[reporter, lgb.early_stopping(50, first_metric_only=True, verbose=False)])
        best = booster.best_iteration or booster.current_iteration()
        got = F.evaluate(np.asarray(booster.predict(dev.matrix, num_iteration=best, raw_score=True)), dev)
        line = dict(setting=setting, best_round=best, rounds_run=booster.current_iteration(), held_out_loss=round(got['mean_loss'], 6), held_out_top=round(got['top_is_positive'], 4),
                    largest_leaf=round(largest_leaf(booster, best), 4), seconds=round(time.time() - t1, 1))
        with lines.open('a') as f:
            f.write(json.dumps(line) + '\n')
        print(json.dumps(line), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

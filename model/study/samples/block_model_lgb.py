"""A LightGBM text model from the trees of `block-boost softmax`.

  python3 block_model_lgb.py --model-jsonl OUT/model.jsonl --store STORE --out MODEL.txt [--softmax-json FILE] [--rounds N]

OUT/model.jsonl has one tree on each line (block-boost's `tree_json`): for each split its column, threshold, default_left and nan_seen, and the children and values of the tree.
STORE is the folder that block_store.py wrote. MODEL.txt is a file for `lightgbm.Booster(model_file=...)`, with the kept column names (as LightGBM takes them) in the store's column order,
and the raw score of a row is the sum of the trees' leaf values, as the fit's own score is. Beside it:

  MODEL.txt.json    what fit_trees.py's report holds for serving: `plan`, `params`, `features` (`uses`, `booster_names`, `header`) and the sizes
  MODEL.uses.json   the list of the column names (`features.uses`), as the writer's tree distribution and lineage_check.py read it

A split of block-boost sends a value left where the value is at most the threshold. A null threshold (no finite bound) sends every number left. A NaN goes the way `default_left`
says where the column had a NaN in the fit (`nan_seen`, LightGBM's missing type NaN), and is read as 0 where it had none (missing type None).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

import fit_trees as FT

NO_THRESHOLD = 1e300  # a threshold that every number is at most
NAN_MISSING = 2  # LightGBM's decision type: bits 2-3 are the missing type (0 None, 1 Zero, 2 NaN), bit 1 is default_left


def number(x: float) -> str:
    return repr(float(x))


def numbers(xs) -> str:
    return ' '.join(number(x) for x in xs)


def tree_text(index: int, tree: dict[str, Any]) -> str:
    """The text of one tree, as Tree::ToString writes it, followed by the blank line that LightGBM writes after each tree."""
    leaves = len(tree['value'])
    splits = len(tree['column'])
    if splits != leaves - 1:
        raise ValueError(f'tree {index}: {splits} splits and {leaves} leaves')
    lines = [f'Tree={index}', f'num_leaves={leaves}', 'num_cat=0']
    if splits:
        for key in ('column', 'threshold', 'default_left', 'nan_seen', 'gain', 'left', 'right'):
            if len(tree[key]) != splits:
                raise ValueError(f'tree {index}: {key} has {len(tree[key])} entries for {splits} splits')
        decision = [(2 if dl else 0) | ((NAN_MISSING << 2) if seen else 0) for dl, seen in zip(tree['default_left'], tree['nan_seen'])]
        threshold = [NO_THRESHOLD if t is None else t for t in tree['threshold']]
        lines += [f"split_feature={' '.join(map(str, tree['column']))}", f"split_gain={numbers(tree['gain'])}", f'threshold={numbers(threshold)}',
                  f"decision_type={' '.join(map(str, decision))}", f"left_child={' '.join(map(str, tree['left']))}", f"right_child={' '.join(map(str, tree['right']))}"]
    lines.append(f"leaf_value={numbers(tree['value'])}")
    if splits:
        lines += [f"leaf_weight={' '.join('0' for _ in range(leaves))}", f"leaf_count={' '.join('0' for _ in range(leaves))}", f"internal_value={' '.join('0' for _ in range(splits))}",
                  f"internal_weight={' '.join('0' for _ in range(splits))}", f"internal_count={' '.join('0' for _ in range(splits))}"]
    lines += ['is_linear=0', 'shrinkage=1', '', '']
    return '\n'.join(lines) + '\n'


def model_text(trees: list[dict[str, Any]], booster_names: list[str]) -> str:
    texts = [tree_text(i, t) for i, t in enumerate(trees)]
    head = ['tree', 'version=v4', 'num_class=1', 'num_tree_per_iteration=1', 'label_index=0', f'max_feature_idx={len(booster_names) - 1}', f"feature_names={' '.join(booster_names)}",
            f"feature_infos={' '.join('none' for _ in booster_names)}", f"tree_sizes={' '.join(str(len(t.encode())) for t in texts)}", '']
    return '\n'.join(head) + '\n' + ''.join(texts) + 'end of trees\n\n' + 'parameters:\n[boosting: gbdt]\n[objective: custom]\nend of parameters\n\npandas_categorical:null\n'


def read_trees(path: Path, rounds: int | None) -> list[dict[str, Any]]:
    trees = []
    with open(path) as f:
        for line in f:
            if line.strip():
                trees.append(json.loads(line))
            if rounds is not None and len(trees) == rounds:
                break
    return trees


def kept_names(store: Path) -> tuple[list[str], dict[str, Any]]:
    """The store's names in the column order of the model: the kept columns, in the order that keep.i32 numbers them."""
    names = json.loads((store / 'names.json').read_text())
    features = json.loads((store / 'features.json').read_text())
    keep_file = store / 'keep.i32'
    if keep_file.exists():
        keep = np.fromfile(keep_file, '<i4')
        if len(keep) != len(names):
            raise SystemExit(f'{keep_file} has {len(keep)} entries for {len(names)} names')
        order = sorted((int(k), j) for j, k in enumerate(keep) if k >= 0)
        if [k for k, _ in order] != list(range(len(order))):
            raise SystemExit(f'{keep_file} does not number its kept columns 0, 1, 2, ...')
        names = [names[j] for _, j in order]
    return names, features


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('--model-jsonl', type=Path, required=True)
    ap.add_argument('--store', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True, help='the model file, such as .../model.txt')
    ap.add_argument('--softmax-json', type=Path, help='the JSON that `block-boost softmax` ran with: its parameters go in the report')
    ap.add_argument('--rounds', type=int, help='the first N trees only (default: all; the best round where result.json of a run with a dev set names one)')
    args = ap.parse_args()
    started = time.time()
    names, features = kept_names(args.store)
    booster = FT.booster_names(names)
    result: dict[str, Any] = {}
    result_file = args.model_jsonl.with_name('result.json')
    if result_file.exists():
        result = json.loads(result_file.read_text())
    rounds = args.rounds if args.rounds is not None else (result.get('best_round') or None)
    trees = read_trees(args.model_jsonl, rounds)
    if not trees:
        print(f'error: {args.model_jsonl} holds no tree', file=sys.stderr)
        return 2
    used = {c for t in trees for c in t['column']}
    if used and max(used) >= len(names):
        print(f'error: a tree splits on column {max(used)}, and the store keeps {len(names)} columns', file=sys.stderr)
        return 2
    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + '.partial')
    tmp.write_text(model_text(trees, booster))
    os.replace(tmp, out)
    uses_file = Path(os.path.splitext(out)[0] + '.uses.json')
    uses_file.write_text(json.dumps(names))

    run = json.loads(args.softmax_json.read_text()) if args.softmax_json else {}
    params = dict(num_leaves=run.get('num_leaves'), learning_rate=run.get('learning_rate'), min_data_in_leaf=run.get('min_data_in_leaf'), feature_fraction=run.get('fraction'),
                  seed=run.get('seed', 0), num_threads=run.get('threads'), verbosity=-1, metric='None', min_sum_hessian_in_leaf=run.get('min_sum_hessian'),
                  max_bin=json.loads((args.store / 'plan.json').read_text()).get('max_bin'), trainer='block-boost softmax',
                  objective='custom: -log(sum of softmax over the positive ids), per point', alpha=0.0)
    try:
        commit = FT.code_commit()
    except Exception:
        commit = None
    report = dict(model=str(out), plan=features.get('plan'), params=params, rounds_run=len(trees), best_round=len(trees), early_stopping_rounds=None, max_rounds=run.get('max_rounds'),
                  dev_loss_by_round=[], dev=None, dev_uniform=None, points_per_task=0, seed=run.get('seed', 0), dev_tasks_override=[], points_dir=features.get('points_dir'),
                  matrix=dict(train=features.get('matrix')), points_left_out=dict(train=features.get('points_left_out')), train_tasks=features.get('train_tasks'), dev_tasks=[],
                  features=dict(uses_from_header=True, uses=names, booster_names=booster, header=features.get('header')), wheels_alike=[],
                  out_of_scope=features.get('out_of_scope'), shapes=None, peak_rss_mib=round(result['rss_gib'] * 1024, 1) if 'rss_gib' in result else None,
                  seconds=result.get('seconds'), train_loss=result.get('train_loss'), code_commit=commit, softmax_json=str(args.softmax_json) if args.softmax_json else None,
                  model_jsonl=str(args.model_jsonl), store=str(args.store))
    Path(str(out) + '.json').write_text(json.dumps(report, indent=1))
    splits = sum(len(t['column']) for t in trees)
    print(f'wrote {out}: {len(trees)} trees, {splits} splits on {len(used)} of {len(names)} columns, {len(names)} feature names, {out.stat().st_size / (1 << 20):.2f} MiB, {time.time() - started:.1f} s')
    print(f'wrote {out}.json and {uses_file}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

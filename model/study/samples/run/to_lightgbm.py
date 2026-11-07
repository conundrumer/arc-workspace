#!/usr/bin/env python
"""to_lightgbm.py WORK OUT.txt [--rounds N] [--plan ordered]: a block-boost softmax fit as a LightGBM text model that the kit's tree_dist.py loads.

WORK holds fits/model.jsonl (the trees, streamed) and columns.json (each kept column's label). The model's features are the columns its trees split on, in their order in OUT.uses.json. OUT.txt.json records the plan. N: the first N trees (default all that are complete)."""
import argparse, json
from pathlib import Path


def trees(path, rounds):
    out = []
    for line in open(path):
        if not line.endswith('\n'):
            break
        out.append(json.loads(line))
        if rounds and len(out) >= rounds:
            break
    return out


def num(x):
    return repr(float(x))


def tree_text(i, t, feature_of, shrinkage):
    leaves = len(t['value'])
    lines = [f'Tree={i}', f'num_leaves={leaves}', 'num_cat=0']
    if leaves > 1:
        decision = [(2 if left else 0) | (8 if nan else 0) for left, nan in zip(t['default_left'], t['nan_seen'])]
        lines += ['split_feature=' + ' '.join(str(feature_of[c]) for c in t['column']),
                  'split_gain=' + ' '.join(num(x) for x in t.get('gain', [0.0] * (leaves - 1))),
                  'threshold=' + ' '.join(num(1.7976931348623157e308 if x is None else x) for x in t['threshold']),
                  'decision_type=' + ' '.join(map(str, decision)),
                  'left_child=' + ' '.join(map(str, t['left'])),
                  'right_child=' + ' '.join(map(str, t['right']))]
    lines += ['leaf_value=' + ' '.join(num(x) for x in t['value']), 'is_linear=0', f'shrinkage={shrinkage}', '', '']
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('work'); ap.add_argument('out'); ap.add_argument('--rounds', type=int, default=0); ap.add_argument('--plan', default='ordered'); ap.add_argument('--shrinkage', default='0.05')
    a = ap.parse_args()
    work, out = Path(a.work), Path(a.out)
    held = trees(work / 'fits' / 'model.jsonl', a.rounds)
    labels = json.loads((work / 'columns.json').read_text())
    used = sorted({c for t in held for c in t['column']})
    feature_of = {c: i for i, c in enumerate(used)}
    texts = [tree_text(i, t, feature_of, a.shrinkage) for i, t in enumerate(held)]
    head = ['tree', 'version=v4', 'num_class=1', 'num_tree_per_iteration=1', 'label_index=0', f'max_feature_idx={len(used) - 1}',
            'feature_names=' + ' '.join(f'f{i}' for i in range(len(used))), 'feature_infos=' + ' '.join('none' for _ in used),
            'tree_sizes=' + ' '.join(str(len(x.encode())) for x in texts), '', '']
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w') as f:
        f.write('\n'.join(head))
        for x in texts:
            f.write(x)
        f.write('end of trees\n\npandas_categorical:null\n')
    out.with_suffix('.uses.json').write_text(json.dumps([labels[c] for c in used]))
    Path(str(out) + '.json').write_text(json.dumps(dict(model=str(out), plan=a.plan, rounds=len(held), source=str(work))))
    print(len(held), 'trees,', len(used), 'features', flush=True)


if __name__ == '__main__':
    main()

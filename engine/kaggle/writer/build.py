#!/usr/bin/env python3
"""Builds a Kaggle bundle of the writer kit: dataset/ and kernel/ under OUT.

  build.py --kit KIT --overlay DIR --wheels W... --tree FILE --uses FILE --out OUT [--seconds S] [--pool P] [--env K=V ...]

code.bin holds the kit's model/study trees and engine/lib/registry.sexpr, with the files of --overlay (a folder that holds model/study/...) over them.
The dataset holds the wheels, the four model files of the kit's models-cf, policy_model.pkl, the kernel's supervisor.py (this folder), the tree with its feature list and its fit report, and run_config.json.
"""
import argparse, hashlib, json, pathlib, runpy, shutil, subprocess, sys, tarfile

HERE = pathlib.Path(__file__).resolve().parent
TREES = ['sampler', 'feat_exp', 'judge3', 'ast/run', 'policy']
MODELS = ['live_priors.pkl', 'relR4_o.pkl', 'choice5_o.pkl', 'tilt_v1.json']
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()  # noqa: E731


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', required=True)
    ap.add_argument('--overlay', nargs='*', default=[])
    ap.add_argument('--wheels', nargs='+', required=True)
    ap.add_argument('--tree', default='')
    ap.add_argument('--uses', default='')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=int, default=240)
    ap.add_argument('--tasks', type=int, default=46)
    ap.add_argument('--rss-limit-mib', type=int, default=600)
    ap.add_argument('--pool', default='search')
    ap.add_argument('--env', nargs='*', default=[])
    a = ap.parse_args()
    kit, out = pathlib.Path(a.kit), pathlib.Path(a.out)
    D, K = out / 'dataset', out / 'kernel'
    shutil.rmtree(D, ignore_errors=True)
    D.mkdir(parents=True)
    K.mkdir(parents=True, exist_ok=True)
    for w in a.wheels:
        shutil.copy(w, D)
    for m in MODELS:
        shutil.copy(kit / 'models-cf' / m, D / m)
    shutil.copy(kit / 'policy' / 'policy_model.pkl', D)
    shutil.copy(HERE / 'supervisor.py', D)
    shutil.copy(HERE / 'dataset-metadata.json', D)
    env = dict(e.split('=', 1) for e in a.env)
    if a.tree:
        shutil.copy(a.tree, D)
        shutil.copy(a.uses, D)
        report = pathlib.Path(a.tree + '.json')  # fit_trees.py's report: the worker reads the tree's writer plan from it (sampler/writer_plan.py)
        if report.exists():
            shutil.copy(report, D)
        elif 'ordered' not in pathlib.Path(a.tree).name and 'WRITER_PLAN' not in env:
            sys.exit('%s has no report %s and no plan in its name: give --env WRITER_PLAN=ordered|unordered' % (a.tree, report))
        env.setdefault('WRITER_TREE', '{data}/' + pathlib.Path(a.tree).name)
    json.dump(dict(seconds=a.seconds, tasks=a.tasks, rss_limit_mib=a.rss_limit_mib, pool=a.pool, env=env), open(D / 'run_config.json', 'w'))
    files = {}
    for t in TREES:
        for p in sorted((kit / 'model/study' / t).rglob('*.py')):
            if '__pycache__' not in p.parts:
                files['model/study/' + str(p.relative_to(kit / 'model/study'))] = p
    for name in ('policy.py', 'nodefeat.py', 'outfeat.py'):  # the policy code that goes with policy_model.pkl, as ARC_POLICY of the kit's runs
        files['model/study/policy/' + name] = kit / 'policy' / name
    for ov in map(pathlib.Path, a.overlay):  # a later overlay's file wins
        for p in sorted(ov.rglob('*.py')):
            if '__pycache__' not in p.parts and 'model/study/' in str(p):
                rel = str(p)[str(p).index('model/study/'):]
                files[rel] = p
    files['engine/lib/registry.sexpr'] = kit / 'engine/lib/registry.sexpr'
    with tarfile.open(D / 'code.bin', 'w') as t:
        for rel, p in sorted(files.items()):
            t.add(p, rel)
        sp = out / 'study_paths.py'
        sp.write_text(runpy.run_path(str(HERE / 'study_paths_text.py'))['STUDY_PATHS'])
        t.add(sp, 'model/study/study_paths.py')
    shutil.copy(HERE / 'kernel-metadata.json', K)
    subprocess.run([sys.executable, str(HERE / 'make_notebook.py'), str(K / 'notebook.ipynb')], check=True)
    m = dict(kit=str(kit), overlay=a.overlay, files={p.name: sha(p)[:16] for p in sorted(D.iterdir())}, notebook=sha(K / 'notebook.ipynb')[:16], run_config=json.load(open(D / 'run_config.json')),
             code_files=len(files) + 1)
    json.dump(m, open(out / 'manifest.json', 'w'), indent=1)
    print(json.dumps(m, indent=1))


if __name__ == '__main__':
    main()

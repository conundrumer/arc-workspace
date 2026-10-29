#!/usr/bin/env python3
"""Compact completed normal classifications atomically, without classifying."""
import argparse
import ast
import fcntl
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from study_paths import DATA_ROOT
import facts

LEGACY_CLASSIFIER = facts.LEGACY_CLASSIFIER
POLICY_AST = '6d86a7ec704a3d3af4fdfcb0a1001ddbf4b855a0ef44ac24f8bdd4e03417d1b8'
POLICY_NODES = {'repository_module', 'StoredSource', 'StoredRows', 'form_starts', 'PrefixRows', 'Context'}


def qualify(previous, current):
    """The storage rewrite preserves the exact classification AST and dependencies."""
    tree = ast.parse(Path(__file__).with_name('normal_policy.py').read_text())
    nodes = {n.name:ast.dump(n, include_attributes=False) for n in tree.body
             if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in POLICY_NODES}
    if facts.digest(nodes) != POLICY_AST:
        raise ValueError('classification extraction differs from reviewed predecessor')
    from normal_policy import dependency_identity
    old = dict(previous['logical_files'])
    new = dependency_identity(current)
    runtime = {name.removeprefix('runtime/'):new.pop(name) for name in list(new)
               if name.startswith('runtime/')}
    if old.pop('ast/run/mech2/classify_normal.py', None) != LEGACY_CLASSIFIER:
        raise ValueError('unreviewed normal producer; retain database unchanged')
    for name in ('ast/run/mech2/normal_policy.py', 'ast/run/mech2/classify_normal.py',
                 'ast/run/mech2/facts.py'):
        new.pop(name)
    if (old != new or previous['runtime'] != runtime or
            any(previous[k] != current[k] for k in
                ('constraint_set', 'normal_policy', 'numpy', 'pandas'))):
        raise ValueError('classification dependencies changed; retain database unchanged')


def compact(db, manifest):
    """Caller holds the normal producer's exclusive lock; one atomic transaction."""
    schema = db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
    if schema and schema[0] == facts.SCHEMA:
        return
    previous = json.loads(db.execute("SELECT value FROM metadata WHERE key='code_manifest'").fetchone()[0])
    qualify(previous, manifest)
    active = facts.digest(previous)
    code = facts.digest(manifest)
    # Read/validate all old facts before touching their tables. No base writes.
    gold = {}
    for point, normal, text in db.execute('SELECT point_id,normal,record_json FROM gold_points'):
        record = json.loads(text)
        identity = {k:record[k] for k in ('task', 'case', 'point', 'clause')}
        if facts.digest(identity) != point or normal != record['normal']:
            raise ValueError('invalid gold point identity or outcome')
        gold[point] = (record, None)
    accepted = {active}
    for prior, current in db.execute('SELECT code_sha256,current_code_sha256 FROM compatible_codes'):
        if current == active:
            original = db.execute('SELECT manifest_json FROM code_manifests WHERE code_sha256=?', (prior,)).fetchone()
            if original and facts.digest(json.loads(original[0])) == prior:
                accepted.add(prior)
    db.execute('BEGIN IMMEDIATE')
    try:
        for table in ('pairs', 'gold_points', 'metadata'):
            db.execute('ALTER TABLE ' + table + ' RENAME TO old_' + table)
        facts.initialize(db)
        db.execute('INSERT INTO producers VALUES (?,?)', (code, facts.canonical(manifest)))
        for done, row in enumerate(db.execute(
                'SELECT pair_id,source_sha256,base_result_sha256,code_sha256,result_sha256,normal,gold_point_id,record_json FROM old_pairs'), 1):
            pid, source, base, producer, result, normal, point, text = row
            record = json.loads(text)
            if (facts.digest(record) != result or producer not in accepted or
                    any(record[k] != expected for k, expected in
                        (('pair_id', pid), ('source_sha256', source), ('base_result_sha256', base),
                         ('code_sha256', producer), ('gold_point_id', point))) or
                    normal != record['mutant']['normal'] or
                    (producer != active and normal is None)):
                raise ValueError('invalid predecessor normal fact ' + pid)
            if point not in gold:
                raise ValueError('missing predecessor gold point ' + point)
            facts.insert(db, 'pairs', (pid, source, code, point), record['mutant'])
            old_gold, origin = gold[point]
            if origin is None and facts.classification(old_gold) == facts.classification(record['gold']):
                gold[point] = old_gold, (pid, source)
            if done % 5000 == 0:
                print(f'compacted={done}', flush=True)
        for point, (record, origin) in gold.items():
            if origin is None:
                raise ValueError('gold fact has no matching source pair ' + point)
            facts.insert(db, 'gold_points', (point, *origin, code), record)
        for table in ('old_pairs', 'old_gold_points', 'old_metadata', 'compatible_codes',
                      'code_manifests', 'gold_point_history'):
            db.execute('DROP TABLE IF EXISTS ' + table)
        db.commit()
    except BaseException:
        db.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DATA_ROOT / 'ast/run/mech2/normal.sqlite3')
    args = parser.parse_args()
    path = args.database.resolve()
    if path.parent != DATA_ROOT / 'ast/run/mech2':
        parser.error('normal output must stay under DATA_ROOT/ast/run/mech2')
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        db = sqlite3.connect(path)
        try:
            db.execute('PRAGMA synchronous=FULL')
            import normal_policy
            compact(db, normal_policy.policy_manifest())
            # Legacy aggregate output is superseded by the read-time join.
            path.with_name('summary.json').unlink(missing_ok=True)
        finally:
            db.close()
    print('normal facts compacted; classifications retained; base database untouched', flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Run one judge clause and write ordinary JSON data; no viewing commands."""
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import sys
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT
sys.path.insert(0, str(CODE_ROOT / 'judgetool'))
from dataset_format import FORMAT, result_packet, table_packet, write_json


def execute(args):
    pair = json.loads((args.pair / 'pair.json').read_text(encoding='utf-8'))
    if pair.get('format') != FORMAT or pair.get('kind') != 'pair':
        raise ValueError('not a judge-dataset-v1 pair')
    pair_id = pair['pair_id']
    # This lookup is private: no record/test paths appear in the public index.
    context = json.loads((DATA_ROOT / 'judgetool/dataset-contexts' / (pair_id + '.json')).read_text())
    from judge_tool import load_pair
    from evaluator import ReplayEvaluator, sha
    _, record, target = load_pair(context['source_pair'])
    if sha(record) != context['source_sha256']:
        raise ValueError('source record differs from exported dataset')
    train = importlib.import_module('evaluator_train')
    clause = args.clause_file.read_text(encoding='utf-8')
    ev = ReplayEvaluator(deadline=args.deadline)
    try:
        checked, acquired = train.evaluate_train_clause(
            ev, record, clause, dict(target, mode='alternative' if args.command == 'alternative' else 'recovery'),
            columns=args.columns, explore=args.command == 'run')
    finally:
        ev.close()
    private = DATA_ROOT / 'judgetool/dataset-runs' / (uuid.uuid4().hex + '.json')
    checked=dict(checked,tool_implementation={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),Path(__file__).with_name('dataset_format.py'),
                  CODE_ROOT/'judgetool/judge_tool.py')})
    write_json(private, checked)
    comparisons=[]
    for item in checked.get('comparisons',[]):
        if item['target_id']=='G':
            comparisons.append(item);continue
        reference=item.get('reference')
        if reference is not None:
            candidates=[t for t in context.get('targets',[]) if t['case']==reference['case']
                and all(str(t['native_selector'].get(k))==str(v)
                        for k,v in reference['native_selector'].items()
                        if k in ('form','point','relation','fact'))]
        else:
            candidates=[t for t in context.get('targets',[]) if t['legacy_target_id']==item['target_id']]
        if len(candidates)==1:
            comparisons.append(dict(item,target_id=candidates[0]['id']))
        else:
            # Do not assign a BODY comparison to a guessed same-named target.
            comparisons.append(dict(item,target_id=None,target_source=item['target_id']))
    checked=dict(checked,comparisons=comparisons)
    table_path = None
    if acquired is not None:
        packet = table_packet(acquired, table_id='result', source_name='&fix',
                              case=pair['case'], roles=['result'])
        table_path = 'table.json'
        write_json(args.output / table_path, packet)
    result = result_packet(checked, command=args.command, pair_id=pair_id, table_path=table_path)
    write_json(args.output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--deadline', type=float, default=30)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('run', 'check', 'alternative'):
        p = commands.add_parser(command)
        p.add_argument('--clause-file', type=Path, required=True)
        p.add_argument('--output', type=Path, required=True)
        p.add_argument('--columns', type=json.loads)
    args = parser.parse_args()
    if args.columns is not None and (not isinstance(args.columns, list) or
                                     any(not isinstance(c, str) for c in args.columns)):
        parser.error('--columns must be a JSON list of variable names')
    # An existing result directory could leave a stale table next to a refusal.
    if args.output.exists():
        parser.error('--output must be a new directory')
    try:
        result = execute(args)
    except Exception as error:
        # A startup/export failure is not a checked clause outcome. In
        # particular it must not masquerade as a TEST replay's "unknown".
        result = dict(format=FORMAT, kind='error', command=args.command, engine=None,
                      reason=f'{type(error).__name__}: {error}', table=None, comparisons=[])
        write_json(args.output / 'result.json', result)
    print(json.dumps(dict(result=str(args.output / 'result.json'), table=result.get('table'),
                          **({'outcome': result['outcome']} if 'outcome' in result else {})),
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

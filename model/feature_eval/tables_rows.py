#!/usr/bin/env python
"""One task's Candidate tables, read again from its stored mutants, with test rows and each Ident column's source.

  <runtime python> -u -I -B tables_rows.py OLD_ROOT NEW_ROOT TASK

It evaluates gold and each stored mutant once, and draws nothing. It keeps the tables' train rows under NEW_ROOT as zstd, and
prints to stdout the tables with their test rows too, with `prefix` and `state` as state_tables.py gives them, for the pipe of
`candidate-lists`. Test rows go nowhere else. An Ident is the digest of its members, so a value means one thing across gold's
run and a mutant's. On a fault it prints only the fault's type.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

os.environ['ARCLOG_IDENT_SOURCE'] = 'value'
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import read_json  # noqa: E402
from query_structure import DEFINING, parse_forms  # noqa: E402
from state_tables import parents_of  # noqa: E402
from tables_worker import REPO, TASKS, keep, read_table, split_of  # noqa: E402


def worker(old_root, new_root, task):
    import numpy as np
    import arclog
    started = time.time()
    split = split_of(task)
    if split not in ('train', 'dev'):
        raise ValueError('not a train or dev task')
    spec = importlib.util.spec_from_file_location('arclog_script', REPO / 'scripts/arclog.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    old = Path(old_root) / split
    stored = read_json(old / 'candidate-tables' / f'{task}.json')
    mutants = read_json(old / 'mutants' / f'{task}.json')
    settings = arclog.DecodeSettings()
    gold = arclog.StudyProgram.from_sexp(mutants['gold'], settings)
    task_json = json.loads((TASKS / (task + '.json')).read_text())
    evaluator = arclog.StudyTaskEvaluator(task, str(TASKS), settings)

    def tables_of(program):
        _, tables = evaluator.gold_tables(program, held_rows=True)
        return script.Tables(arclog, np, program, tables, task_json)

    gold_tables = tables_of(gold)
    gold_forms = parse_forms(mutants['gold'])
    defined = {}
    for at, form in enumerate(gold_forms):
        if form and form[0] in DEFINING and len(form) > 1:
            defined.setdefault(form[1], at)
    by_form = {query['form']: query for query in mutants['queries']}
    prefix = {}

    def with_parents(names):
        for name in names:
            if name not in prefix:
                prefix[name] = read_table(gold_tables, name, sources=True)[0]
        return [name for name in names if prefix[name] is not None]

    programs = 0
    items = []
    left_out = list(stored.get('left_out', []))
    for item in stored['items']:
        form, name = item['form'], item['table']
        gold_table, why = read_table(gold_tables, name, sources=True)
        if gold_table is None:
            left_out.append(dict(query=item['query'], table=name, why=why))
            continue
        kept = []
        for mutant in item['mutants']:
            record = by_form[form]['mutants'][mutant['mutant']]
            try:
                program = arclog.StudyProgram.from_sexp(record['text'], settings)
                table, why = read_table(tables_of(program), name, gold_table['assignment'], sources=True)
                programs += 1
            except Exception as error:
                left_out.append(dict(query=item['query'], table=name, mutant=mutant['mutant'], why='mutant: ' + type(error).__name__))
                continue
            if table is None:
                left_out.append(dict(query=item['query'], table=name, mutant=mutant['mutant'], why='mutant: ' + why))
                continue
            parents = with_parents(parents_of(parse_forms(record['text']), form, defined))
            kept.append(dict(mutant=mutant['mutant'], edit=mutant.get('edit'), extra=mutant.get('extra'), table=table, parents=parents, text=record['text']))
        if kept:
            items.append(dict(query=item['query'], form=form, table=name, gold=gold_table, parents=with_parents(parents_of(gold_forms, form, defined)), mutants=kept, text=mutants['gold']))
    reads_at = {at: parents_of(gold_forms, at, defined) for at in defined.values()}
    names = set(prefix) | {read for reads in reads_at.values() for read in reads} | {item['table'] for item in items}
    names |= {relation for relation, at in defined.items() if gold_forms[at][0] != 'INIT'}
    nodes = [dict(name=name, form=defined[name.split('.')[0]], reads=reads_at[defined[name.split('.')[0]]]) for name in sorted(names) if name.split('.')[0] in defined]
    head = {key: stored.get(key) for key in ('task', 'case', 'train', 'last_query', 'budget_cut')}
    prefix = {name: table for name, table in prefix.items() if table is not None}
    full = dict(head, test=len(task_json['test']), left_out=left_out, items=items, prefix=prefix, state=dict(nodes=nodes))

    def train_rows(table):
        keep_key = lambda held: {key: value for key, value in held.items() if key == 'task' or key.startswith('train/')}
        return {**table, 'rows': keep_key(table['rows']), 'models': keep_key(table['models'])}

    kept_items = [{**{key: value for key, value in item.items() if key != 'text'}, 'gold': train_rows(item['gold']), 'mutants': [{**{key: value for key, value in mutant.items() if key != 'text'}, 'table': train_rows(mutant['table'])} for mutant in item['mutants']]} for item in items]
    keep(Path(new_root) / split / 'candidate-tables' / f'{task}.json.zst', dict(head, left_out=left_out, items=kept_items, prefix={name: train_rows(table) for name, table in prefix.items()}, state=dict(nodes=nodes), seconds=round(time.time() - started, 2), programs=programs + 1))
    json.dump(full, sys.stdout)
    sys.stdout.flush()


if __name__ == '__main__':
    try:
        worker(*sys.argv[1:4])
    except Exception as error:
        print(type(error).__name__, file=sys.stderr)
        sys.exit(1)

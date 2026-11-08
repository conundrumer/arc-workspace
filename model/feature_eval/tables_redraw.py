#!/usr/bin/env python
"""Draws again the stored queries whose every draw reads as the same table, since their tables may stand at the level of the task.

  <runtime python> -u -I -B tables_redraw.py OLD_ROOT NEW_ROOT TASK

A table that the task reads once keeps its rows under the key `task`, so a comparison at the train pairs alone reads every mutant of it as equal to the ground
truth. For a query that has no kept mutant and all of whose draws read as the same table, this draws its specs again with the comparison at that key as well. Every
other query and item stays as OLD_ROOT holds it. NEW_ROOT gets the task's `mutants` and `candidate-tables` files with the new mutants and items, and a task that
gains nothing gets none. It prints one line of counts. No row is printed. On a fault it prints only the fault's type.
"""
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import read_json  # noqa: E402
from query_structure import Reader, parse_forms  # noqa: E402
from tables_worker import BUDGET, CORPUS, PER_QUERY, REPO, SEED, TASKS, keep, read_table, read_checked, split_of  # noqa: E402


def worker(old_root, new_root, task):
    import numpy as np
    import arclog
    split = split_of(task)
    if split not in ('train', 'dev'):
        raise ValueError('not a train or dev task')
    old = Path(old_root) / split
    stored_mutants = read_json(old / 'mutants' / f'{task}.json')
    stored_tables = read_json(old / 'candidate-tables' / f'{task}.json')
    lost = [query for query in stored_mutants['queries'] if not query['mutants'] and query['drawn'] and query['same_table'] == query['drawn']]
    if not lost:
        print(json.dumps(dict(task=task, queries=0, kept=0)))
        return
    spec = importlib.util.spec_from_file_location('arclog_script', REPO / 'scripts/arclog.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    data = CORPUS / (task + '.arcdata')
    cases = arclog.case_files(task, read_checked(CORPUS / (task + '.arclog')), read_checked(data) if data.exists() else '', str(CORPUS))
    case = [held for held in cases if held.concept][0]
    settings = arclog.DecodeSettings()
    gold = arclog.StudyProgram.from_sexp(case.arclog, settings)
    if case.arclog != stored_mutants['gold']:
        raise ValueError('the corpus has moved from the stored program')
    task_json = json.loads((TASKS / (task + '.json')).read_text())
    train = len(task_json['train'])
    evaluator = arclog.StudyTaskEvaluator(task, str(TASKS), settings)

    def tables_of(program):
        _, tables = evaluator.gold_tables(program, held_rows=True)
        return script.Tables(arclog, np, program, tables, task_json)

    def rows(tb, names):
        out = {}
        for name in names:
            if name in tb.names:
                for example, _, _, raw, _ in tb.entries(tb.names.index(name)):
                    out.setdefault((name, example), set()).update(repr(row) for row in raw)
        return out

    gold_tables = tables_of(gold)
    specs_of = {}
    for point in gold.points():
        form = point.clause_path[0]
        if any(query['form'] == form for query in lost):
            try:
                specs, _ = gold.draw_specs(point, 1, 5000, 0, operation='mixed', source_revision=SEED, task=task, case=case.case)
            except ValueError:
                continue
            specs_of.setdefault(form, []).extend(specs)
    gold_forms = parse_forms(case.arclog)
    rng = random.Random(f'{SEED}.{task}.task-level')
    started = time.time()
    new_items = []
    kept_count = 0
    keys = ['task'] + [f'train/{at}' for at in range(train)]

    def train_rows(table):
        held = lambda values: {key: value for key, value in values.items() if key == 'task' or key.startswith('train/')}
        return dict(rows=held(table['rows']), models=held(table['models']))

    def parents_of(forms, form, own):
        reader = Reader()
        reader.form(forms[form])
        return sorted({read for read in reader.reads if read in gold_tables.names and read not in own})

    for query in lost:
        form, names = query['form'], query['tables']
        specs = list(specs_of.get(form, []))
        rng.shuffle(specs)
        gold_rows = rows(gold_tables, names)
        kept, reads = [], []
        same = failed = 0
        for held in specs:
            if len(kept) == PER_QUERY or time.time() - started > BUDGET:
                break
            mutant = gold.construct(held)
            program = mutant.as_program()
            try:
                tables = tables_of(program)
                mutant_rows = rows(tables, names)
            except Exception:
                failed += 1
                continue
            if not any(mutant_rows.get((name, key)) != gold_rows.get((name, key)) for name in names for key in keys):
                same += 1
                continue
            edits = json.loads(mutant.identity_json).get('edits', [])
            kept.append(dict(edit=edits[0].get('kind') if edits else None, status='', text=mutant.sexp(), extra=False))
            golds = {name: read_table(gold_tables, name)[0] for name in names}
            reads.append({name: read_table(tables, name, golds[name]['assignment']) if golds[name] else (None, 'no table') for name in names})
        query.update(mutants=kept, same_table=same, failed=failed)
        kept_count += len(kept)
        for name in names:
            gold_table, why = read_table(gold_tables, name)
            if gold_table is None:
                stored_tables.setdefault('left_out', []).append(dict(query=query['name'], table=name, why=why))
                continue
            mutants = []
            for at, (record, held) in enumerate(zip(kept, reads)):
                table, why = held[name]
                if table is None:
                    stored_tables.setdefault('left_out', []).append(dict(query=query['name'], table=name, mutant=at, why='mutant: ' + why))
                elif train_rows(table) != train_rows(gold_table):
                    mutants.append(dict(mutant=at, edit=record['edit'], extra=False, table={**table, **train_rows(table)}, parents=parents_of(parse_forms(record['text']), form, names)))
            if mutants:
                new_items.append(dict(query=query['name'], form=form, table=name, gold={**gold_table, **train_rows(gold_table)}, mutants=mutants))
    if kept_count:
        stored_tables['items'] = sorted(stored_tables['items'] + new_items, key=lambda item: item['form'])
        keep(Path(new_root) / split / 'mutants' / f'{task}.json.zst', stored_mutants)
        keep(Path(new_root) / split / 'candidate-tables' / f'{task}.json.zst', stored_tables)
    print(json.dumps(dict(task=task, queries=len(lost), kept=kept_count, items=len(new_items), seconds=round(time.time() - started, 1))))


if __name__ == '__main__':
    try:
        worker(*sys.argv[1:4])
    except Exception as error:
        print(json.dumps(dict(task=sys.argv[3], fault=type(error).__name__)))
        sys.exit(1)

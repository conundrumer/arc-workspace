#!/usr/bin/env python
"""A task's gold queries against foreign queries at the same states, for the pipe of `all-lists`.

  <runtime python> -u -I -B tables_foreign.py pool OLD_ROOT POOL_DIR
  <runtime python> -u -I -B tables_foreign.py OLD_ROOT POOL_DIR NEW_ROOT TASK

`pool` writes each split's gold forms. Then, at up to STATES gold queries of the task, other than the one that `OUT` reads, it
draws forms from the gold programs of the task's split's other tasks, renames what each reads to tables of the state, and keeps
up to PER_STATE that hold all of these: the program type-checks, the table has rows at every train pair, no table of the
state has its rows, and no gold query of the task has them. It keeps each kept program under NEW_ROOT as `mutants`, in the form
tables_worker.py gives, with each candidate's `edit` saying whether its column types are gold's, and what the draw met under
NEW_ROOT/draws. It prints the tables with their test rows, which go nowhere else. On a fault it prints only the fault's type.

With FOREIGN_READS=gold in the environment, a draw is harder to tell from gold without table content: a form must read a table
of the state, a read goes to a table that gold's query reads wherever one has the columns or the port, and a table has an Example
column only where a table of gold's query has one.
"""
import importlib.util
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ['ARCLOG_IDENT_SOURCE'] = 'value'
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import read_json  # noqa: E402
from query_structure import DEFINING, parse_forms, relation_of  # noqa: E402
from state_tables import parents_of  # noqa: E402
from tables_worker import REPO, TASKS, keep, read_table, split_of  # noqa: E402

SEED = 'arc-foreign-queries-1'
STATES = 4
PER_STATE = 8
DRAWS = 300
PROGRAMS = 60
SECONDS = 40
OWN = '&foreign'
READS_LIKE_GOLD = os.environ.get('FOREIGN_READS') == 'gold'
NO_OUT = ['OUT', ['input', '^P', '^Col']]


def written(node):
    return node if isinstance(node, str) else '(' + ' '.join(written(part) for part in node) + ')'


def defining(form):
    return bool(form) and form[0] in DEFINING and len(form) > 1 and isinstance(form[1], str) and form[1].startswith('&')


def atoms_of(node):
    """Each list under a form whose head is a relation of a program."""
    if isinstance(node, list):
        if node and isinstance(node[0], str) and node[0].startswith('&'):
            yield node
        for part in node:
            yield from atoms_of(part)


def columns_read(atom):
    """The columns that an atom's sites name."""
    out = set()
    for site in atom[1:]:
        if isinstance(site, str):
            name = site.lstrip('*^')
            if name != '0':
                out.add(name)
        elif site and isinstance(site[0], str) and site[0].startswith(':'):
            out.add(site[0][1:])
    return out


def pool(old_root, pool_dir):
    for split in ('train', 'dev'):
        held = []
        for path in sorted((Path(old_root) / split / 'mutants').glob('*.json*')):
            task = path.name.split('.')[0]
            forms = parse_forms(read_json(path)['gold'])
            for form in forms:
                if defining(form):
                    held.append(dict(task=task, text=written(form)))
        keep(Path(pool_dir) / f'pool-{split}.json.zst', held)


def renamed(node, names):
    if isinstance(node, str):
        return names.get(node, node)
    return [renamed(part, names) for part in node]


def placed(form, members, rng, parents=()):
    """The form with its name made fresh and each table it reads a table of the state, or None where one has no place. A
    read goes to one of `parents` where one fits."""
    own = form[1]
    names = {own: OWN}
    needs = {}
    for atom in atoms_of(form):
        needs.setdefault(atom[0], set()).update(columns_read(atom))
    for token, columns in needs.items():
        if relation_of(token) == own:
            names[token] = OWN + token[len(own):]
            continue
        port = token[len(relation_of(token)):]
        if port:
            options = [name for name in members if name[len(relation_of(name)):] == port]
        else:
            options = [name for name, held in members.items() if relation_of(name) == name and columns <= held]
        if not options:
            return None
        names[token] = rng.choice([name for name in options if name in parents] or options)
    return renamed(form, names)


def worker(old_root, pool_dir, new_root, task):
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
    drawn_file = read_json(old / 'mutants' / f'{task}.json')
    settings = arclog.DecodeSettings()
    text = drawn_file['gold']
    gold = arclog.StudyProgram.from_sexp(text, settings)
    task_json = json.loads((TASKS / (task + '.json')).read_text())
    train = len(task_json['train'])
    evaluator = arclog.StudyTaskEvaluator(task, str(TASKS), settings)

    def tables_of(program):
        _, tables = evaluator.gold_tables(program, held_rows=True)
        return script.Tables(arclog, np, program, tables, task_json)

    def rows_key(table):
        """A table's content at the train pairs."""
        keep_key = lambda held: {key: value for key, value in held.items() if key == 'task' or key.startswith('train/')}
        return json.dumps([[ty.split('@')[0] for ty in table['types']], keep_key(table['rows']), keep_key(table['models'])], sort_keys=True)

    def has_rows(table):
        if 'task' in table['rows'] or 'task' in table['models']:
            return bool(table['rows'].get('task') or table['models'].get('task'))
        return all(table['rows'].get(f'train/{at}') or table['models'].get(f'train/{at}') for at in range(train))

    gold_tables = tables_of(gold)
    gold_forms = parse_forms(text)
    defined = {}
    for at, form in enumerate(gold_forms):
        if defining(form):
            defined.setdefault(form[1], at)
    known = {}
    for name in gold_tables.names:
        if name and relation_of(name) in defined and name not in known:
            table = read_table(gold_tables, name, sources=True)[0]
            if table is not None:
                known[name] = table
    all_gold = {rows_key(table) for table in known.values()}
    read_later = {read for at in defined.values() for read in parents_of(gold_forms, at, defined)}
    rng = random.Random(f'{SEED}.{task}')
    choices = sorted(at for relation, at in defined.items() if relation != stored.get('last_query') and any(relation_of(name) == relation for name in known))
    rng.shuffle(choices)
    choices = sorted(choices[:STATES])
    foreign = [held for held in read_json(Path(pool_dir) / f'pool-{split}.json') if held['task'] != task]
    prefix, items, queries, draws = {}, [], [], []

    def with_parents(names):
        for name in names:
            if name in known:
                prefix[name] = known[name]
        return [name for name in names if name in known]

    for form_at in choices:
        relation = gold_forms[form_at][1]
        ports = sorted(name for name in known if relation_of(name) == relation)
        read = [name for name in ports if name in read_later]
        ports = (read or ports)[:2]
        members = {}
        for name, table in known.items():
            if defined[relation_of(name)] < form_at:
                members[name] = set(table['columns'])
        state_keys = {rows_key(known[name]) for name in members}
        lines = [written(form) for form in gold_forms[:form_at]]
        drawn_rng = random.Random(f'{SEED}.{task}.{form_at}')
        counts = dict(form=form_at, drawn=0, no_place=0, refused=0, no_table=0, no_rows=0, in_state=0, in_gold=0, example_column=0, kept=0)
        gold_parents = parents_of(gold_forms, form_at, defined)
        gold_has_example = any('Example' in known[name]['types'] for name in ports)
        candidates = []
        begun = time.time()
        programs = 0
        for held in drawn_rng.sample(foreign, min(DRAWS, len(foreign))):
            if len(candidates) >= PER_STATE or programs >= PROGRAMS or time.time() - begun > SECONDS:
                break
            counts['drawn'] += 1
            form = placed(parse_forms(held['text'])[0], members, drawn_rng, gold_parents if READS_LIKE_GOLD else ())
            if form is None or (READS_LIKE_GOLD and gold_parents and not set(gold_parents) & set(atom[0] for atom in atoms_of(form))):
                counts['no_place'] += 1
                continue
            programs += 1
            own_text = written(form)
            whole = '\n'.join(lines + [own_text, written(NO_OUT)])
            try:
                tables = tables_of(arclog.StudyProgram.from_sexp(whole, settings))
            except Exception:
                counts['refused'] += 1
                continue
            own = sorted(name for name in tables.names if name and relation_of(name) == OWN)
            if not own:
                counts['no_table'] += 1
                continue
            table = read_table(tables, drawn_rng.choice(own), sources=True)[0]
            if table is None or table.get('too_large'):
                counts['no_table'] += 1
            elif not has_rows(table):
                counts['no_rows'] += 1
            elif rows_key(table) in state_keys:
                counts['in_state'] += 1
            elif rows_key(table) in all_gold:
                counts['in_gold'] += 1
            elif READS_LIKE_GOLD and 'Example' in table['types'] and not gold_has_example:
                counts['example_column'] += 1
            else:
                counts['kept'] += 1
                reads = sorted({read for read in parents_of(parse_forms(whole), form_at, defined) if read in known})
                candidates.append(dict(table=table, text=whole, parents=reads, source=held['task']))
        draws.append(counts)
        if not candidates:
            continue
        queries.append(dict(form=form_at, name=relation, tables=ports, kinds=[gold_forms[form_at][0]], drawn=counts['drawn'], same_table=0, failed=counts['refused'], mutants=[dict(edit='foreign', text=held['text'], extra=False, source=held['source']) for held in candidates]))
        for port in ports:
            gold_table = known[port]
            own_types = sorted(ty.split('@')[0] for ty in gold_table['types'])
            kept = []
            for at, held in enumerate(candidates):
                same = sorted(ty.split('@')[0] for ty in held['table']['types']) == own_types
                kept.append(dict(mutant=at, edit='same-types' if same else 'other-types', extra=False, table=held['table'], parents=with_parents(held['parents'])))
            items.append(dict(query=relation, form=form_at, table=port, gold=gold_table, parents=with_parents(parents_of(gold_forms, form_at, defined)), mutants=kept))
    reads_at = {at: parents_of(gold_forms, at, defined) for at in defined.values()}
    names = set(prefix) | {read for reads in reads_at.values() for read in reads} | {item['table'] for item in items}
    names |= {name for name, at in defined.items() if gold_forms[at][0] != 'INIT'}
    nodes = [dict(name=name, form=defined[relation_of(name)], reads=reads_at[defined[relation_of(name)]]) for name in sorted(names) if relation_of(name) in defined]
    head = dict(task=task, case=drawn_file['case'], train=train, last_query=stored.get('last_query'), budget_cut=False, left_out=[])
    keep(Path(new_root) / split / 'mutants' / f'{task}.json.zst', dict(task=task, case=drawn_file['case'], gold=text, gold_status='', budget_cut=False, queries=queries))
    keep(Path(new_root) / 'draws' / f'{task}.json.zst', dict(task=task, split=split, seconds=round(time.time() - started, 2), states=draws))
    json.dump(dict(head, test=len(task_json['test']), items=items, prefix=prefix, state=dict(nodes=nodes)), sys.stdout)
    sys.stdout.flush()


if __name__ == '__main__':
    try:
        if sys.argv[1] == 'pool':
            pool(sys.argv[2], sys.argv[3])
        else:
            worker(*sys.argv[1:5])
    except Exception as error:
        print(type(error).__name__, file=sys.stderr)
        sys.exit(1)

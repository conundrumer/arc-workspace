#!/usr/bin/env python
"""One task's stored Candidate tables with the tables its queries read, for the pipe of `candidate-lists`.

  state_tables.py TASK

It prints the task's tables file with three things added, and runs no engine:

- `prefix`: each table the stored items hold, by name, from each item's gold table and the tables its gold form reads.
- `parents`, on each item and each mutant: the names of the tables its own form reads.
- `state.nodes`: each table or relation of the gold program, with its form and the names it reads.

The stored tables hold train rows only.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_json  # noqa: E402
from query_structure import DEFINING, Reader, parse_forms, relation_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / 'work/feature-spec/results/all'


def reads_of(form):
    reader = Reader()
    reader.form(form)
    return reader.reads


def parents_of(forms, at, defined):
    """The names of the earlier relations and tables that a form reads."""
    own = forms[at][1] if len(forms[at]) > 1 else None
    return sorted({read for read in reads_of(forms[at]) if relation_of(read) != own and defined.get(relation_of(read), at) < at})


def tables_file(task):
    split = next(name for name in ('train', 'dev') if (ROOT / name / 'candidate-tables' / f'{task}.json.zst').exists())
    data = read_json(ROOT / split / 'candidate-tables' / f'{task}.json')
    mutants = read_json(ROOT / split / 'mutants' / f'{task}.json')
    gold_forms = parse_forms(mutants['gold'])
    defined = {}
    for at, form in enumerate(gold_forms):
        if form and form[0] in DEFINING and len(form) > 1:
            defined.setdefault(form[1], at)
    by_form = {query['form']: query for query in mutants['queries']}
    prefix = {}
    items = []
    for item in data['items']:
        form = item['form']
        prefix[item['table']] = item['gold']
        for name, table in item.get('reads', {}).items():
            prefix.setdefault(name, table)
        kept = []
        for mutant in item['mutants']:
            forms = parse_forms(by_form[form]['mutants'][mutant['mutant']]['text'])
            kept.append({**mutant, 'parents': parents_of(forms, form, defined)})
        rest = {key: value for key, value in item.items() if key != 'reads'}
        items.append({**rest, 'parents': parents_of(gold_forms, form, defined), 'mutants': kept})
    reads_at = {at: parents_of(gold_forms, at, defined) for at in defined.values()}
    names = set(prefix) | {read for reads in reads_at.values() for read in reads}
    names |= {relation for relation, at in defined.items() if gold_forms[at][0] != 'INIT'}
    nodes = [dict(name=name, form=defined[relation_of(name)], reads=reads_at[defined[relation_of(name)]]) for name in sorted(names) if relation_of(name) in defined]
    head = {key: value for key, value in data.items() if key != 'items'}
    return dict(head, test=0, items=items, prefix=prefix, state=dict(nodes=nodes))


if __name__ == '__main__':
    json.dump(tables_file(sys.argv[1]), sys.stdout)
    sys.stdout.flush()

#!/usr/bin/env python3
"""Export complete pair data through the shared evaluator's TRAIN surfaces."""
from copy import deepcopy
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT
sys.path.insert(0, str(CODE_ROOT / 'judgetool'))
from dataset_format import FORMAT, table_packet, table_summary, pair_packet, write_json
from nonrender_metadata import MetadataProducer


def grouped(packet):
    """Value-only transport to the canonical comparator; no equality here."""
    result = {}
    for entry in packet['entries']:
        key = (entry['assignment'], 1, entry['example_index'])
        rows = frozenset(tuple(tuple(cell['value']) for cell in row) for row in entry['rows'])
        result.setdefault(key, set()).add(rows)
    return dict(groups=result, required={tuple(k) for k in packet['required']},
                missing=[tuple(k) for k in packet['missing']])


def _case(ev, record, context, ntrain, ntest, cache):
    from evaluator import sha, read_json
    from evaluator_train import acquire_case_train, dependency_receipt
    if not Path(cache).resolve().is_relative_to(DATA_ROOT.resolve()):
        raise ValueError('case cache must stay under the study data root')
    kept = context.get('kept_assignments')
    if kept is None:
        kept = (context.get('reference') or {}).get('evaluation', {}).get('kept_assignments')
    if kept is None and context['name'] == record['case']:
        kept = record['evaluation']['kept_assignments']
    program = context.get('source_program')
    if program is None and context['name'] == record['case']:
        program = record['gold_sexp']
    catalogue = Path(context['catalogue_path'])
    identity = dict(task=record['task'], case=context['name'], program=program, kept=kept,
                    catalogue_sha256=hashlib.sha256(catalogue.read_bytes()).hexdigest(),
                    relation_source_names=context.get('relation_source_names'),
                    runtime=ev.receipt, adapter=dependency_receipt(), ntrain=ntrain, ntest=ntest)
    path = cache / (sha(identity) + '.json')
    if path.exists():
        return read_json(path), False
    print(f"case {context['name']}: fresh gold replay", file=sys.stderr, flush=True)
    case_context = dict(context, catalogue_path=context.get('catalogue_path'))
    value = acquire_case_train(ev, record, case_context, ntrain, ntest)
    # Cache failed/bounded acquisitions too: an exporter retry is explicit.
    write_json(path, value)
    return value, True


def export_pair(ev, source_pair, output, cache):
    from judge_tool import load_pair
    manifest, record, target = load_pair(source_pair)
    return export_target(ev, manifest['pair_id'], record, target, output, cache,
                         source=str(Path(source_pair).resolve()))


def export_target(ev, pair_id, record, target, output, cache, *, source,
                  private=DATA_ROOT / 'judgetool', features=None):
    """Write one pair directory from a source record and its target (adapter, ntrain, ntest).

    `source` names where the target came from; `private` receives the contexts
    and receipts that the judge clause commands read.

    `features` is a point directory. With it, the pair directory holds X, the
    mutant program and pair.json, and the point directory holds G, the available
    tables, train.json, the gold program and libraries.json, written by the
    first pair of the point. The other targets, the comparisons, the readers
    and the private files are not computed.
    """
    from evaluator import read_json, sha
    from tables import TargetStore
    from evaluator_train import acquire_train_point
    from case_collector import compare_target
    from definition_binding import definition_node
    adapter = target['adapter']
    destination = Path(output)
    if not destination.resolve().is_relative_to(DATA_ROOT.resolve()):
        raise ValueError('dataset output must stay under the study data root')
    if destination.exists():
        raise ValueError('dataset output must be a new directory: ' + str(output))
    # An interrupted acquisition never publishes a partial public pair.
    output = destination.with_name(destination.name + '.building')
    if output.exists():
        output.rename(output.with_name(output.name + '-' + str(time.time_ns())))
    shared = None  # the point directory under construction
    if features is not None and not (features / 'point.json').exists():
        shared = features.with_name(features.name + '.building-' + str(os.getpid()))
        shutil.rmtree(shared, ignore_errors=True)
    if adapter['input']['binding']['kind'] == 'Det':
        raise ValueError('DET pairs are not judged')
    store = TargetStore(ev.legacy, CODE_ROOT)
    producer = MetadataProducer(engine=ev.arclog,
        read_native=lambda ref, base: store.snapshot(ref, base)['_native_reader'],
        corpus=Path(adapter['source']['native_base']).parent, settings=ev.settings,
        case_inventory=adapter['all_case_targets'])
    point_export = producer._export(record['gold_sexp'], record)
    point_view = next(v for v in point_export['body_views'] if v['body_path'] == record['point'])
    point_name = producer.point_source_name(point_export, point_view)
    packets = {}; index = []; shared_index = []; comparisons = []; provenance = []; target_bindings = []
    def add(packet, table_id, name, case, roles, atom=None, **metadata):
        path = 'tables/' + table_id + '.json'
        public = table_packet(packet, table_id=table_id, source_name=name, case=case,
                              roles=roles, callable_atom=atom)
        public.update(metadata)
        where, listing = (shared, shared_index) if features is not None and table_id != 'X' else (output, index)
        write_json(where / path, public)
        listing.append(table_summary(public,path))
        packets[table_id] = packet
        return public
    x = acquire_train_point(ev, record, adapter, target['ntrain'], target['ntest'], side='mutant')
    add(x, 'X', point_name, record['case'], ['input'], adapter['input']['binding']['callable_template'], side='mutant')
    if features is None or shared:
        g = acquire_train_point(ev, record, adapter, target['ntrain'], target['ntest'], side='gold')
        add(g, 'G', point_name, record['case'], ['target'], side='gold')
    candidate = grouped(x)
    columns = [(f.get('field_name', f.get('name')), f['type']) for f in x['fields']]
    def comparison(packet, fields, ref):
        value = compare_target(candidate['groups'], columns, grouped(packet), fields, ref)
        # The public pair contains TRAIN evidence only. A comparator invoked
        # with no TEST keys must not advertise vacuous "test: equal" evidence.
        value.pop('test', None)
        value['scope'] = 'train'
        comparisons.append(dict(target_id=ref['target_id'], comparison=value))
    if features is None:
        comparison(g, g['fields'], dict(target_id='G', role='point'))
    main_export = None
    count = 0
    fresh_cases = {}
    facts = set()
    contexts = adapter['all_case_targets']['cases']
    for context in contexts:
        if features is not None and not shared and context['name'] != record['case']:
            continue  # the point directory exists: this pair needs only the export of its own case
        context = dict(context, catalogue_path=adapter['all_case_targets']['catalogue_path'])
        bundle, fresh_cases[context['name']] = _case(ev, record, context, target['ntrain'], target['ntest'], cache)
        if not bundle['native_table_inventory_complete']:
            # Preserve the real replay refusal/bound instead of presenting it
            # as a missing-table catalogue. Never publish an incomplete case.
            from tables import Incomplete
            observation=bundle.get('receipt',{}).get('observation',{})
            reasons=[g['reason'] for g in bundle.get('gaps',[])
                     if g.get('kind')=='replay' and g.get('reason')]
            error=Incomplete('fresh case replay incomplete: '+context['name']+'; '
                + ('; '.join(reasons) or observation.get('engine','native capture unavailable'))
                + '; artifact='+str(observation.get('artifact')))
            error.receipt=bundle.get('receipt')
            raise error
        export = bundle['export']; same = bundle['case'] == record['case']
        if same:
            main_export = export
        if features is not None and not same:
            # The tables of the cases before the pair's case number the tables after them.
            count += len(bundle['tables'])
            continue
        if features is not None and not shared:
            break
        provenance.append(bundle['receipt'])
        for item in bundle['tables']:
            meta = producer.case_table_metadata(export, item)
            eligible = not same
            if same:
                ts = {k: [v] for k, v in item['selector'].items()}
                eligible = producer.selectors['same_case_after'](
                    ts, 0, adapter['comparison_target']['binding'], export)
                if eligible is None:
                    raise ValueError('canonical same-case source order unavailable: ' + item['table_id'])
            allowed = False
            if same:
                allowed = item['selector']['fact'] in ('ex_input', 'ex_output')
                independent = adapter['availability']['independent_nodes']
                for definition in meta['definitions']:
                    if definition_node(export, definition) in independent:
                        allowed = True
            if not eligible and not allowed:
                continue
            roles = (['target'] if eligible else []) + (['available'] if allowed else [])
            table_id = 'T' + str(count); count += 1
            # Feature consumers require only canonically available tables.
            # Preserve target numbering without decoding later target rows.
            if features is not None and not allowed:
                continue
            if item['table'] is None:
                raise ValueError('fresh table unavailable: ' + str(item.get('reason')))
            fields = [dict(field, field_name=bound['display_name'])
                      for field, bound in zip(item['table']['fields'], meta['schema'])]
            if len(fields) != len(item['table']['fields']):
                raise ValueError('canonical metadata schema width differs')
            packet = dict(item['table'], fields=fields)
            atom = meta['callable_atom'] if allowed else None
            if features is None or allowed:
                add(packet, table_id, meta['source_name'], bundle['case'], roles, atom,
                    **{k: meta[k] for k in ('body_path', 'body_kind') if k in meta})
            if eligible and features is None:
                ref = dict(target_id=table_id, role='later' if same else 'other_case', case=bundle['case'])
                compared_fields = fields if same else [dict(f, field_name=None) for f in fields]
                comparison(packet, compared_fields, ref)
                target_bindings.append(dict(id=table_id,case=bundle['case'],
                    native_selector=item['selector'],
                    legacy_target_id=bundle['case']+': '+item['source_name']))
            if allowed and item['selector']['fact']:
                facts.add(item['selector']['fact'])
            if same and item['input'] is not None:
                inp = item['input']
                # Native fact input schema is retained; no own projection.
                add(inp, 'input', 'input', bundle['case'], ['available'],
                    producer.policy['Document'].callable_atom(
                        object(), [dict(f, display_name=f['name']) for f in inp['fields']], 'input'))
                facts.add('input')
        if features is not None and same:
            break  # the cases after the pair's case add no available table
    if (features is None or shared) and not {'input', 'ex_input', 'ex_output'} <= facts:
        raise ValueError('fresh dataset lacks required available input facts')
    if main_export is None:
        raise ValueError('pair case missing from fresh case catalogue')
    names = producer.policy['Names'](main_export)
    programs = {}
    for side in ('gold', 'mutant'):
        programs[side] = side + '.arclog'
        if features is not None and side == 'gold' and not shared:
            continue
        export = producer._export(record[side + '_sexp'], record if side == 'gold' else None)
        side_names = producer.policy['Names'](export) if side == 'gold' else names
        where = shared if features is not None and side == 'gold' else output
        (where / programs[side]).write_text(side_names.text(record[side + '_sexp']) + '\n')
    nodes = {tuple(n['path']): n for n in main_export['nodes']}
    change = dict(point=record['point'], kind=adapter['input']['binding']['kind'],
                  gold=names.text(nodes[tuple(record['point'])]['sexp']))
    mutant_export = producer._export(record['mutant_sexp'])
    mutant_nodes = {tuple(n['path']): n for n in mutant_export['nodes']}
    change['mutant'] = names.text(mutant_nodes[tuple(record['point'])]['sexp'])
    readers = {}
    for side, export in (() if features is not None else (('gold', main_export), ('mutant', mutant_export))):
        nodes = {tuple(n['path']): n for n in export['nodes']}
        variables = {(tuple(v['scope_path']),v['label_id']):v
                     for v in export['typed_sites']['variables']}
        readers[side] = []
        for reader in export['definitions']['readers']:
            path = reader['reader_path']
            arguments = []
            for a in export['typed_sites']['arguments']:
                if a['path'][:len(path)] != path:
                    continue
                variable = variables.get((tuple(a['scope_path']),a['label_id']))
                arguments.append(dict(site=names.text(nodes[tuple(a['site_path'])]['sexp']),
                    variable=None if variable is None else variable['label_spelling'],
                    type=a['column_type'], frame=a['frame'], literal=a['literal']))
            readers[side].append(dict(path=path, owner=reader.get('reader_owner_path'),
                atom=names.text(nodes[tuple(path)]['sexp']), arguments=arguments))
    if features is not None:
        if shared:
            task = read_json(adapter['source']['task_path'])
            write_json(shared / 'train.json', task['train'])
            write_json(shared / 'libraries.json', ev.registry_interfaces(record)['entries'])
            write_json(shared / 'point.json', dict(format=FORMAT, kind='features-point', task=record['task'],
                case=record['case'], point=record['point'], tables=shared_index,
                programs=dict(gold=programs['gold']), train='train.json', libraries='libraries.json'))
            try:
                shared.rename(features)
            except OSError:  # another process published the same point first
                shutil.rmtree(shared)
        write_json(output / 'pair.json', dict(format=FORMAT, kind='features-pair', pair_id=pair_id,
            task=record['task'], case=record['case'], change=change, tables=index,
            programs=dict(mutant=programs['mutant']), point=os.path.relpath(features, destination)))
        output.rename(destination)
        return dict(pair_id=pair_id, tables=len(index) + len(shared_index), output=str(destination),
                    fresh_cases=fresh_cases)
    task = read_json(adapter['source']['task_path'])
    write_json(output / 'train.json', task['train'])
    write_json(output / 'readers.json', readers)
    write_json(output / 'libraries.json', ev.registry_interfaces(record)['entries'])
    write_json(output / 'comparisons.json', comparisons)
    write_json(output / 'pair.json', pair_packet(pair_id=pair_id, task=record['task'], case=record['case'],
        change=change, tables=index, programs=programs, libraries='libraries.json'))
    write_json(private / 'dataset-contexts' / (pair_id + '.json'),
               dict(source_pair=source, source_sha256=sha(record),
                    targets=target_bindings))
    write_json(private / 'dataset-export-receipts' / (pair_id + '.json'),
               dict(source_sha256=sha(record), runtime=ev.receipt, cases=provenance,
                    implementation={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (Path(__file__), Path(__file__).with_name('dataset_format.py'),
                                  Path(__file__).with_name('nonrender_metadata.py'))}))
    output.rename(destination)
    return dict(pair_id=pair_id, tables=len(index), output=str(destination), fresh_cases=fresh_cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=DATA_ROOT / 'judgetool/dataset-case-cache')
    parser.add_argument('--deadline', type=float, default=30)
    args = parser.parse_args()
    from evaluator import ReplayEvaluator
    ev = ReplayEvaluator(deadline=args.deadline)
    start = time.monotonic()
    try:
        for i, pair in enumerate(args.pair):
            print(json.dumps(export_pair(ev, pair, args.output / pair.name, args.cache)), flush=True)
            elapsed = time.monotonic() - start
            print(f'{i+1}/{len(args.pair)} elapsed={elapsed:.1f}s ETA={elapsed/(i+1)*(len(args.pair)-i-1):.1f}s',
                  file=sys.stderr, flush=True)
    finally:
        ev.close()


if __name__ == '__main__':
    main()

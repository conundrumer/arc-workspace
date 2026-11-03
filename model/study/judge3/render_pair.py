#!/usr/bin/env python3
"""Render stored study pairs; never evaluate programs or call a judge.

Uses render2's pinned native reader, AST export, typed value printer, complete
row catalog and grid printer. Only StudyProgram metadata/registry APIs are used.
"""
from __future__ import annotations
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import collections
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
S = ROOT.parent
sys.path[:0] = [str(S / 'judge2/render2'), str(S / 'ast/run')]
from native import Native, require, reader_metadata
from native_storage import load_native
from structured import Programs
from values import Values
from render import RowCatalog
from grids import grid_lines, reference_panels
from next_revision.family_recovery import kept_entry_groups
from sites import frame_text
from assignments import Assignments
from components import attach_choice_extents
from column_paths import key as column_key
from headers import bind_body_schema
from body import project_entries
from column_paths import text as column_text
from catalog import matches as selector_matches, same_case_after, definition_after, fields as catalog_fields


# Read historical receipts through the real study paths after relocation.
DEFAULT_DOCUMENT_LIMIT = 300_000


def real_paths(text):
    # Normalize historical session receipts at the read boundary, including
    # references embedded in diagnostic strings. Never emit symlink paths.
    session = r'/private/tmp/claude-\d+/[^/]+/'
    text = re.sub(session + '320d8711-2e71-48f5-ab26-25e45b27e47b/scratchpad/relabel',
                  lambda _: str(DATA_ROOT/'ref/progsynth-relabel'), text)
    return re.sub(session + '64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad', lambda _: str(DATA_ROOT), text)


def compact(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic_text(path, text):
    path=Path(path); pending=path.with_name(path.name+'.next')
    pending.write_text(text); pending.replace(path)


def atomic_gzip(path, text):
    path=Path(path); pending=path.with_name(path.name+'.next')
    with gzip.open(pending,'wt') as stream: stream.write(text)
    pending.replace(path)


def admission_validation(reference, record):
    if reference is None:
        return dict(schema='mech-admission-validation-v1',status='unavailable',eligible=False,
                    receipt_authenticated=False,reason='no durable mechanical admission reference supplied')
    mech=S/'ast/run/mech'
    sys.path.insert(0,str(mech))
    try:
        from admission import load_admission
        result=load_admission(reference,record)
        require(result.get('schema')=='mech-admission-validation-v1','unsupported admission validation')
        return result
    except Exception as error:
        return dict(schema='mech-admission-validation-v1',status='unavailable',eligible=False,
                    receipt_authenticated=False,reason='mechanical admission validation unavailable: '+str(error))
    finally:
        sys.path.remove(str(mech))


def under(path, parent):
    return path[:len(parent)] == parent


class Names:
    """Exact-token substitution from authenticated native relation identities."""
    def __init__(self, export):
        self.tokens = {}
        self.sources = {}
        self.slots = {}
        for d in export['definitions']['native_relations']:
            if d.get('display_name'):
                self.sources[d['source_name']] = d['display_name']
        for item in export['relation_source_names']['relations']:
            identity = item['native_relation']
            display = item['display_name']
            self.slots[item['relation_slot']] = display
            if identity.get('kind') == 'declared':
                native = identity['name']
                token = '&r' + str(native['slot']) if native['kind'] == 'slot' else native['name']
                require(token.startswith('&'), 'native written relation lacks its exact source token')
            elif 'owner' in identity and set(identity['owner']) in ({'instance'}, {'rigid'}):
                owner_kind = next(iter(identity['owner']))
                instance = identity['owner'][owner_kind]
                source_instance = item['source_relation']['owner'][owner_kind]
                token = '&r' + str(instance['slot']) if 'slot' in instance else instance['name']
                require(token.startswith('&'), 'native written owner lacks its exact source token')
                previous = self.tokens.setdefault(token, source_instance['name'])
                require(previous == source_instance['name'], 'conflicting INIT owner source names')
                for part in identity['path']:
                    if set(part) == {'port'}:
                        token += '.' + part['port']
                    elif set(part) == {'part'} and set(part['part']) == {'slot'}:
                        token += '.r' + str(part['part']['slot'])
                    elif set(part) == {'part'} and set(part['part']) == {'name'}:
                        # Native OutputStep::Part(Written) writes the exact
                        # declared part name after removing its leading &.
                        # The display spelling still comes from the native
                        # authenticated source map, never from this suffix.
                        name = part['part']['name']
                        require(isinstance(name, str) and name.startswith('&') and len(name) > 1,
                                'native written RIGID part lacks its declared token')
                        token += '.' + name.lstrip('&')
                    elif part == {'pose': True}:
                        token += '.pose'
                    else:
                        raise ValueError('unsupported nested relation identity: ' + compact(part))
            else:
                raise ValueError('unsupported source relation identity: ' + compact(identity))
            previous = self.tokens.setdefault(token, display)
            require(previous == display, 'conflicting source relation tokens')
        require(len(self.tokens.values()) == len(set(self.tokens.values())), 'source relation spelling collision')
        self.pattern = re.compile(r'"(?:\\.|[^"\\])*"|&[^\s()]+')

    def text(self, text):
        def replace(m):
            token = m.group()
            if token.startswith(chr(34)):
                return token
            require(not re.match(r'&r\d+(?:\.|$)', token) or token in self.tokens,
                    'source relation name missing: ' + token)
            return self.tokens.get(token, token)
        return self.pattern.sub(replace, text)

    def source(self, source):
        require(source in self.sources, 'source relation identity missing: ' + source)
        return self.sources[source]


class Document:
    def __init__(self, record, base, task, engine, programs):
        self.r, self.base, self.engine = record, base, engine
        from legacy_body_metadata import LegacyBodyMetadata
        self.legacy_body_context = dict(resolver=LegacyBodyMetadata.configured(),
            programs=programs, base=base)
        # The input passed to the value printer has no test output field.
        self.task = dict(train=[dict(input=x['input'], output=x['output']) for x in task['train']],
                         test=[dict(input=x['input']) for x in task['test']])
        self.ntrain = len(self.task['train'])
        self.kept = record['evaluation']['kept_assignments']
        self.nkept = len(self.kept)
        require(self.nkept > 0, 'no kept assignments')
        self.gprogram, self.gexport, _ = programs.load(record['programs']['gold'], record)
        _, self.mexport, _ = programs.load(record['programs']['mutant'])
        self.names = Names(self.gexport)
        reserved = {'&X', '&fix'}
        source_tokens = set(self.names.tokens.values())
        raw_tokens = set(self.names.tokens)
        for export in (self.gexport, self.mexport):
            raw_tokens.update(token for token in self.names.pattern.findall(export['program_sexp'])
                              if token.startswith('&'))
        require(not reserved & (source_tokens | raw_tokens),
                'reserved recovery relation collision: ' + ', '.join(sorted(reserved & (source_tokens | raw_tokens))))
        self.gnodes = {tuple(n['path']): n for n in self.gexport['nodes']}
        self.mnodes = {tuple(n['path']): n for n in self.mexport['nodes']}
        body = [b for b in self.gexport['body_views'] if b['body_path'] == record['point']]
        require(len(body) == 1, 'changed body view missing or ambiguous')
        self.body = body[0]
        self.owner = self.body['owner_path']
        self.target_path = self.body['body_path']
        self.top = self.owner[0]
        self.readers = {}
        self.raw = {}
        for side in ('gold', 'mutant'):
            self.raw[side] = load_native(record['native'][side], base)
            self.readers[side] = Native(self.raw[side])
        self.full = Native(load_native(record['full_replay']['gold'], base))
        self.full_maps = record['full_replay']['evaluation']['gold_assignment_map']
        require(record['full_replay']['evaluation']['kept_assignments'] == self.kept,
                'full replay uses different held DET values')
        self.gaps = []
        self.blocks = []
        self.retained_objects = []  # keep Values' identity-based cache keys alive
        domains = dict(self.gexport['orientation_domains'])
        for ty, domain in self.mexport['orientation_domains'].items():
            require(ty not in domains or domains[ty] == domain, 'nominal orientation domain differs')
            domains[ty] = domain
        self.values = Values(dict(task_data=self.task, orientations=list(engine.orientation_names()),
                                  orientation_types=domains,
                                  column_names={}))
        self.catalog = RowCatalog()
        self.printed_schema_layouts = set()
        self.fact_definitions = {}
        self.row_namespace = record['case']
        self.target_catalog = None
        self.column_matches = []
        self.row_sections = []
        self.row_display_policy = 'budget'
        self.full_row_refs = set()
        self.document_limit = DEFAULT_DOCUMENT_LIMIT
        self.table_receipts = []
        self.body_bindings = {}
        self.available_definitions = []
        self.availability = self.dependency_scope()
        self.mechanical_receipt = None
        self.admission_reference = None
        self.admission_validation = admission_validation(None,record)
        self.source_context = None
        self.case_inventory = None

    def gap(self, message):
        if message not in self.gaps:
            self.gaps.append(message)

    def dependency_scope(self):
        definitions = self.gexport['definitions']
        graph = {n['node']: n for n in definitions['graph_nodes']}
        require(all(set(n['reads']) <= graph.keys() for n in graph.values()), 'resolver graph edge missing')
        owner = self.gnodes[tuple(self.owner)]
        if self.body['kind'].startswith('INIT'):
            instance = owner['data']['name']
            seeds = {i for i, n in graph.items() if n['definition'].get('instance') == instance
                     and (self.body['kind'] == 'INIT key' or
                          (n['definition']['kind'] == 'instance_input' and n['definition']['port'] == self.body['input_port']))}
            # A component that reads its own outputs has one native resolver
            # node for every input and output, rather than per-port nodes.
            seeds.update(i for i, n in graph.items()
                         if n['definition']['kind'] == 'recursive_instance'
                         and n['definition']['name'] == instance
                         and self.owner in n['forms'])
        elif owner['kind'] == 'choose':
            # CHOOSE is a native chosen definition, not a clause node. Bind
            # its exact declared identity and original owner form together.
            seeds = {i for i, n in graph.items() if self.owner in n['forms']
                     and n['definition']['kind'] == 'chosen'
                     and n['definition']['name'] == owner['data']['name']}
        else:
            seeds = {i for i, n in graph.items() if self.owner in n['forms']
                     and n['definition']['kind'] in ('clause', 'parameter', 'chosen', 'rigid_assembly')}
        require(seeds, 'target relation absent from resolver graph')
        def dependents(initial, fixed_cut=False):
            # fixed_cut: a DET (`parameter`) or CHOOSE (`chosen`) node holds one value for the task, so its
            # readers do not depend on the outputs it was chosen from
            selected = set(initial)
            while True:
                more = {i for i, n in graph.items()
                        if any(r in selected and not (fixed_cut and graph[r]['definition']['kind'] in ('parameter', 'chosen'))
                               for r in n['reads'])}
                if more <= selected:
                    return selected
                selected.update(more)
        excluded = dependents(seeds)
        output_seeds = {i for i, n in graph.items()
                        if n['definition'].get('relation') == {'fact': 'ExOutput'}}
        registry = {r['id']: r for r in definitions['registry']['entries']}
        def library_reads_output(identity):
            todo = [identity]; seen = set()
            while todo:
                current = todo.pop()
                if current in seen:
                    continue
                seen.add(current)
                require(current in registry, 'library dependency absent')
                for read in registry[current]['reads']:
                    if read.get('fact') == 'ExOutput':
                        return True
                    if 'lib' in read:
                        todo.append('lib:' + read['lib'])
            return False
        for r in definitions['readers']:
            resolved = r['resolution']
            if resolved['kind'] == 'library' and library_reads_output(resolved['id']):
                output_seeds.update(i for i, n in graph.items()
                                    if any(under(r['reader_path'], p) for p in n['forms']))
        return dict(graph_nodes=definitions['graph_nodes'], target_nodes=sorted(seeds),
                    dependent_nodes=sorted(excluded), independent_nodes=sorted(graph.keys() - excluded),
                    ex_output_dependent_nodes=sorted(dependents(output_seeds)),
                    ex_output_test_blocked_nodes=sorted(dependents(output_seeds, fixed_cut=True)),
                    ex_output_provenance='native resolver edges plus transitive resolved library fact reads; shared-owner library effects conservatively retained')

    def definition_node(self, definition):
        relation = definition['relation']
        matches = []
        for n in self.availability['graph_nodes']:
            d = n['definition']
            match = d.get('relation') == relation
            if relation.get('kind') == 'declared' and d['kind'] == 'chosen':
                match = (d['name'] == relation['name']
                         and definition['definition_path'] in n['forms'])
            if 'owner' in relation:
                owner = relation['owner']
                if 'instance' in owner:
                    native = owner['instance']
                    instance = (dict(kind='slot', slot=native['slot']) if 'slot' in native
                                else dict(kind='written', name=native['name']))
                    match = (d.get('instance') == instance and len(relation['path']) == 1
                             and d.get('port') == relation['path'][0].get('port'))
                    if d['kind'] == 'recursive_instance':
                        # Native recursive components map all written inputs
                        # and declared outputs to their one owner node.
                        match = (d['name'] == instance
                                 and definition['definition_path'] in n['forms']
                                 and len(relation['path']) == 1
                                 and set(relation['path'][0]) == {'port'})
                elif 'rigid' in owner:
                    native = owner['rigid']
                    rigid = (dict(kind='slot', slot=native['slot']) if 'slot' in native
                             else dict(kind='written', name=native['name']))
                    match = d['kind'] == 'rigid_assembly' and d['name'] == rigid
            if match:
                matches.append(n['node'])
        require(len(matches) == 1, 'callable relation lacks unique resolver node: ' + definition['source_name'])
        return matches[0]

    def _body_side(self, reader, body_side=None):
        sides=[name for name,actual in self.readers.items() if reader is actual]
        if body_side is None:
            require(len(sides)==1,'BODY reader requires explicit body_side when shared or outside point snapshots')
            body_side=sides[0]
        require(body_side in sides,'BODY reader differs from explicit body_side')
        return body_side

    def _legacy_body_binding(self, reader, table, schema, view, *, body_side=None):
        context = getattr(self, 'legacy_body_context', None)
        if context is None or context['resolver'] is None:
            return None
        sides = [side for side, actual in self.readers.items() if reader is actual]
        # A fresh/full-case payload has no source point acquisition receipt.
        if not sides:
            return None
        side=self._body_side(reader,body_side)
        program, export, _ = context['programs'].load(self.r['programs'][side],
            self.r if side == 'gold' else None,
            mutant_record=self.r if side == 'mutant' else None)
        from native_correspondence import certified_metadata_program
        program=certified_metadata_program(context['programs'].engine,program,export,
            context['programs'].settings)
        from legacy_body_metadata import recorded_metadata_context
        admission=recorded_metadata_context(context['programs'],self.r)
        return context['resolver'].bind(record=self.r, side=side, base=context['base'],
            reader=reader, table=table, schema=schema, program=program,
            export=export, body_path=view['body_path'],recorded_context=admission)

    def schema(self, reader, table, *, body=False, definition=None, body_side=None):
        schema = [dict(c) for c in reader.schema(table)]
        if body:
            side=self._body_side(reader,body_side)
            export = self.gexport if side == 'gold' else self.mexport
            views = [v for v in export['body_views'] if v['owner_path'] == self.owner
                     and v['body_path'] == self.body['body_path']
                     and v['kind'] == self.body['kind'] and v['input_port'] == self.body['input_port']
                     and v['native_table_selector']['form'] == reader.tables['form'][table]]
            require(len(views) == 1, 'target body binding is missing or ambiguous: ' + side)
            view = views[0]
            require(reader.tables['point'][table] == view['native_table_selector']['point'], 'body selector differs')
            binding=self._legacy_body_binding(reader,table,schema,view,body_side=side)
            for c in schema:
                c['native_source_label'] = c['source_label']
            bind_body_schema(dict(schema=schema), view,legacy_binding=binding)
            for c in schema:
                c['native_label_identity'] = dict(kind='implicit_unit' if c['type'] == 'Unit' else 'scoped_label',
                    label_id=None if c['type'] == 'Unit' else c['ast_label_id'],
                    label_spelling=c['label'], native_slot=c['slot'], native_source_label=c['native_source_label'],
                    owner_path=view['owner_path'], body_path=view['body_path'])
                if c['type'] != 'Unit':
                    variables = [v for v in export['typed_sites']['variables']
                                 if v['label_id'] == c['ast_label_id'] and v['scope_path'] == view['owner_path']]
                    require(len(variables) == 1, 'body label lacks exact lexical scope')
                    c['native_label_identity']['scope_path'] = variables[0]['scope_path']
                    c['native_label_identity']['source_label_spelling'] = variables[0]['label_spelling']
        is_port = definition is not None and 'owner' in definition['relation']
        names = []
        for c in schema:
            # RULE body labels are its exposed fields. INIT outputs use actual
            # port field names, never provenance labels (which can repeat).
            if definition is not None:
                witness = next(w for w in definition['column_witnesses'] if w['physical_column'] == c['index'])
                name = column_text(witness['row_path'], 'role')
            else:
                name = (c['label'] or c['name']) if body else c['name']
            names.append(name)
            c['display_name'] = name
            c['source_label'] = '@column:' + str(c['index'])
            self.values.f['column_names'][c['source_label']] = name
        require(len(names) == len(set(names)), 'duplicate callable field names: ' + ', '.join(names))
        return schema

    def callable_atom(self, schema, name, definition=None):
        """Format binding sites from exported row paths, including nested keys.

        Positional path members are positional arguments, never invented named
        sites such as :key.c0. Every leaf is included, so slots remain complete.
        """
        from native_correspondence import canonical_bound_field_type
        tree = {}
        native_paths = definition is not None and 'owner' in definition['relation']
        witnesses = {w['physical_column']: w for w in definition['column_witnesses']} if native_paths else {}
        for c in schema:
            if c.get('callable_row_path') is not None:
                path = column_key(c['callable_row_path'])
            elif native_paths:
                witness = witnesses[c['index']]
                require(witness.get('row_path') is not None, 'callable column path missing')
                require(witness['native_name'] == c['name'] and witness['type'] == canonical_bound_field_type(c),
                        'callable column witness differs from native table')
                path = column_key(witness['row_path'])
            else:
                path = (('written', c['display_name']),)
            cursor = tree
            for part in path:
                cursor = cursor.setdefault(part, {})
            require(not cursor, 'overlapping native column paths')
            cursor['value'] = '*V' + str(c['index'])
        def emit(children):
            if 'value' in children:
                require(len(children) == 1, 'column path is both scalar and record')
                return children['value']
            slots = sorted(part[1] for part in children if part[0] == 'slot')
            require(not slots or slots == list(range(len(slots))), 'sparse positional binding path')
            result = []
            items = sorted(children.items(), key=lambda x: x[0][1]) if slots else children.items()
            for part, subtree in items:
                kind, value = part
                content = emit(subtree)
                result.append('(:' + value + ' ' + content + ')' if kind == 'written' else content)
            return ' '.join(result)
        return '(' + name + (' ' + emit(tree) if tree else '') + ')'

    def target_projection(self, reader, schema, decoded, *, body_side=None):
        side=self._body_side(reader,body_side)
        export = self.gexport if side == 'gold' else self.mexport
        # A CHOOSE owner has multiple bodies with the same kind/port and
        # native point ordinal. Only the exact source body path identifies X.
        views = [v for v in export['body_views'] if v['body_path'] == self.body['body_path']
                 and v['owner_path'] == self.owner
                 and v['kind'] == self.body['kind'] and v['input_port'] == self.body['input_port']]
        require(len(views) == 1, 'exact target projection body is missing or ambiguous')
        view = views[0]
        by_label = {c['ast_label_id']: c for c in schema}
        selected = []
        if view['kind'] == 'INIT key':
            key = next(n for n in export['nodes'] if n['path'] == view['body_path'][:-1])
            require(key['kind'] == 'init_key', 'INIT key projection lacks exact key declaration')
            for field in key['data']['columns']:
                selected.append((by_label[field['label_id']], [field['name']],
                                 dict(role='key', label_id=field['label_id'])))
        elif view['kind'] == 'INIT input':
            key_columns = [c for c in view['input_port_columns'] if c['role'] == 'group_key']
            require(len(key_columns) <= 1, 'ambiguous INIT group key layout')
            key_fields = key_columns[0]['fields'] if key_columns else []
            require(len(key_fields) == len(view['group_key_label_ids']), 'INIT key field coverage differs')
            for label, field in zip(view['group_key_label_ids'], key_fields):
                selected.append((by_label[label], [dict(kind='written', name='key'), field],
                                 dict(role='group_key', label_id=label)))
            for p in sorted(view['input_port_projection'], key=lambda x: x['port_column']):
                if p['body_column'] is None:
                    require(p['type'] == 'Unit' and p['inserted_constant']['kind'] == 'unit',
                            'unknown inserted INIT input constant')
                    source = dict(type='Unit', frame='', name='', label='', slot=-1,
                                  native_label_identity=dict(kind='implicit_unit', label_id=None))
                else:
                    source = by_label[p['label_id']]
                path = [p['logical_port_column_name']] + ([p['field']] if p['field'] is not None else [])
                selected.append((source, path, dict(p, role='input_value')))
        else:
            selected = [(c, [dict(kind='written', name=c['display_name'])],
                         dict(role='body', label_id=c['ast_label_id'])) for c in schema]
        indices = [source.get('index') for source, _, _ in selected]
        projected = []
        for i, (source, path, projection) in enumerate(selected):
            projected.append(dict(source, index=i, source_body_column=source.get('index'),
                source_projection=projection, callable_row_path=path,
                display_name=column_text(path, 'role'), source_label='@column:' + str(i)))
        require(len({c['display_name'] for c in projected}) == len(projected), 'projected field collision')
        result = {}
        for e, entry in decoded.items():
            rows = project_entries(dict(entries=[dict(entry, choice=None)]), indices)[0]['rows']
            result[e] = dict(entry, rows=rows)
        return projected, result, view

    def visible(self, entry, schema):
        require(entry['example_kind'] != 2, 'attempt to render a test relation entry')
        example_columns = [c['index'] for c in schema if c['type'] == 'Example']
        rows = [row for row in entry['rows']
                if all(0 <= row[i]['value'][0] < self.ntrain for i in example_columns)]
        # Preserve whole typed native cells (values, frame sizes and status).
        unique = {compact(row): row for row in rows}
        return dict(entry, rows=[unique[k] for k in sorted(unique)])

    def entries(self, reader, table, maps, *, nkept=None):
        native = dict(reader.parts)
        groups, evidence = kept_entry_groups(native, table, maps, self.nkept if nkept is None else nkept, self.ntrain)
        decoded = {}
        for trains in groups:
            for ids in trains:
                for e in ids:
                    if e not in decoded:
                        decoded[e] = reader.entry(e, with_extents=True, projection_stop=False)
        return groups, decoded, evidence

    def rows(self, schema, entry, title):
        entry = self.visible(entry, schema)
        for c in schema:
            self.values.f['column_names'][c['source_label']] = c['display_name']
        table = dict(schema=[dict(c, presentation_namespace=self.row_namespace) for c in schema])
        self.retained_objects.extend((table, entry))
        order = [c['source_label'] for c in schema]
        self.blocks += [title + f'; complete visible row count={len(entry["rows"])}']
        layout_key = compact([self.row_namespace,[(c['display_name'],c['type'],c.get('frame','')) for c in schema]])
        if layout_key not in self.printed_schema_layouts:
            self.printed_schema_layouts.add(layout_key)
            self.blocks += ['Fields in physical order: ' + ('; '.join(
            c['display_name'] + ': ' + c['type'] + ((' in ' + c['frame']) if c['frame'] else '')
            for c in schema) or '(no columns)')]
        self.blocks += ['```text']
        fact_key = compact(dict(namespace=self.row_namespace, example=entry['example'],
            schema=[dict(type=c['type'], frame=c.get('frame','')) for c in schema], rows=entry['rows']))
        if fact_key in self.fact_definitions:
            lines = ['  All rows: '+self.fact_definitions[fact_key]+' (complete set defined above).']
        else:
            lines = self.catalog.lines(table, entry, order, self.values, allow_grid=False)
            self.fact_definitions[fact_key] = lines[0].strip().split()[0] if lines and 'rows, complete):' in lines[0] else lines[0].split(': ',1)[1].split()[0]
        ref = self.fact_definitions[fact_key]
        if self.row_display_policy == 'full':
            self.full_row_refs.add(ref)
        begin = len(self.blocks)
        self.blocks += lines
        # Only defining blocks can be sampled; later references retain the same
        # catalog identity and are relabelled if that definition becomes partial.
        if len(entry['rows']) > 1 and lines and 'rows, complete):' in lines[0]:
            ref = lines[0].strip().split()[0]
            self.row_sections.append(dict(begin=begin, end=len(self.blocks), table=table,
                entry=entry, order=order, values=self.values, ref=ref, title=title, total=len(entry['rows']), policy=self.row_display_policy))
        self.blocks += ['```', '']
        return entry

    def table(self, reader, table, maps, title, *, body=False, definition=None, show_rows=True, nkept=None, callable=True):
        schema = self.schema(reader, table, body=body, definition=definition)
        groups, decoded, evidence = self.entries(reader, table, maps, nkept=nkept)
        source_schema = copy.deepcopy(schema)
        if body:
            schema, decoded, view = self.target_projection(reader, schema, decoded)
        relation_name = '&X' if title == 'X' else definition.get('display_name') if definition else None
        atom = self.callable_atom(schema, relation_name, definition) if relation_name and callable else None
        if atom:
            self.blocks += [title + ' binding syntax: `' + atom + '`',
                'Bindings: ' + '; '.join('V' + str(c['index']) + '=' + c['display_name'] for c in schema), '']
        for a, items in enumerate(evidence):
            for item in items:
                e = item['native_entry']
                entry = decoded[e]
                if show_rows:
                    self.rows(schema, entry, f'{title}; assignment {a+1}; {entry["example"]}; native model {entry["model"]}')
        shown_entries = []
        for a, items in enumerate(evidence):
            for item in items:
                entry = self.visible(decoded[item['native_entry']], schema)
                shown_entries.append(dict(assignment=a, entry=entry['entry'],
                    example=entry['example'], example_kind=entry['example_kind'],
                    example_index=entry['example_index'], model=entry['model'], rows=entry['rows']))
        self.table_receipts.append(dict(title=title, table=table, callable_atom=atom, native_candidate_keys=reader.tables.get('keys', [[] for _ in reader.tables['width']])[table], selector={k: reader.tables[k][table]
            for k in ('form', 'point', 'relation', 'fact')}, entries=evidence,
            decoded_entries=shown_entries,
            fields=[dict(physical_index=c['index'], name=c['display_name'], type=c['type'], frame=c['frame'],
                native_name=c['name'], label=c['label'], native_slot=c['slot'],
                native_label_identity=c.get('native_label_identity'),
                row_path=(next(w['row_path'] for w in definition['column_witnesses'] if w['physical_column']==c['index'])
                          if definition else c.get('callable_row_path'))) for c in schema]))
        if body:
            side = 'gold' if reader is self.readers['gold'] else 'mutant'
            export = self.gexport if side == 'gold' else self.mexport
            fields = [dict(physical_index=c['index'], field_name=c['display_name'],
                native_name=c['name'], native_label_identity=c['native_label_identity'],
                type=c['type'], frame=c['frame'],
                callable_row_path=c['callable_row_path'], source_body_column=c['source_body_column'],
                source_projection=c['source_projection']) for c in schema]
            self.body_bindings[side] = dict(side=side, body_path=view['body_path'], owner_path=view['owner_path'],
                scope=view['scope'], kind=view['kind'], input_port=view['input_port'],
                native_ref=self.r['native'][side], native_table_index=table,
                native_selector=view['native_table_selector'],
                table_receipt_index=len(self.table_receipts)-1, table_receipt=self.table_receipts[-1],
                fields=fields, projected_schema=fields, projected_entries=shown_entries,
                source_body_schema=source_schema,
                target_kind='instance_input_relation' if view['kind'].startswith('INIT') else 'clause_body_relation',
                callable_template=self.callable_atom(schema, '&X') if side == 'mutant' else None,
                init_projection=copy.deepcopy(view['input_port_projection']),
                group_key_label_ids=view['group_key_label_ids'])
        return schema, groups, decoded

    def task_section(self):
        self.blocks += ['## Task', 'Coordinates are zero-based. Each grid row is printed on its own line.', '']
        for i, ex in enumerate(self.task['train'], 1):
            self.blocks += [f'train{i}', '```text', *reference_panels(ex), '```', '']
        for i, ex in enumerate(self.task['test'], 1):
            self.blocks += [f'test{i} input', '```text', *grid_lines(ex['input']), '```', '']

    def target_section(self):
        r = self.r
        self.blocks += ['# Judge document', f'Pair `{r["identity"].get("pair_id", "") or self.pair_id}`; task `{r["task"]}`; case `{r["case"]}`.', '',
            'Recover a target from X with one RULE or DET, checked across train and test inputs and compatible kept assignments; test target rows are not shown. '
            'Target columns come from X sites or a lib computation giving exactly one row per X row; other atoms restrict X rows. Qualifying unions need native contribution/nonredundancy proof; other-atom target bindings are partial sources. '
            'Counts and output fit alone do not decide whether information survives.', '',
            f'Target: {self.body["kind"]}; body at AST {".".join(map(str,self.target_path))}; {self.body["scope"]}.',
            'The recovery interface is `&X`, with exactly the fields shown for X. '
            '`&X` is a judge adapter handle. For INIT, it exposes the actual input/key projection, not full witnesses or component outputs. '
            'Gold G is the comparison target, never an available relation.', '',
            'Every kept gold DET is held at its complete saved value in both programs. '
            'A conditional continuation can therefore hide a damaged DET proposal; no DET admissibility is inferred here.', '',
            '## Change', 'Gold owning definition:', '```arclog', self.names.text(self.gnodes[tuple(self.owner)]['sexp']), '```',
            'Mutant owning definition:', '```arclog', self.names.text(self.mnodes[tuple(self.owner)]['sexp']), '```']
        for edit in r['identity']['edits']:
            node = self.gnodes.get(tuple(edit['at']))
            before = self.names.text(node['sexp']) if node else 'unavailable'
            self.blocks += [f'- AST {".".join(map(str,edit["at"]))}: {edit["kind"]}: `{before}`']
        self.blocks += ['', 'The table comparison measures the combined edit. No single-edit counterfactual is supplied.', '']
        if self.body['input_port']:
            self.blocks += ['INIT target: the actual keyed input relation obtained by this native projection, '
                'deduplicated as a relation. Fields use the port’s declared column names; body-only witnesses are excluded from G and X.']
            for p in self.body['input_port_projection']:
                n = p['logical_port_column_name']
                self.blocks += [f'- port {self.body["input_port"]}, field {compact(n)}: body '
                    f'column {p["body_column"]}, type {p["type"]}; '
                    f'constant={compact(p["inserted_constant"])}']
            self.blocks += ['Group key label IDs: ' + compact(self.body['group_key_label_ids']), '']

    def comparison(self):
        ev = self.r['evaluation']
        self.blocks += ['## G and X', 'Full row and comparison counts use complete projected train/task tables. Display aligns on stored native candidate keys; without a shared projected key, only G-only and X-only rows are displayed. '
            'G/X comparison rows are complete. R references point to row sets printed earlier. '
            'Model numbers on the two sides are independent; comparisons explicitly take their Cartesian product. '
            'The recovery must match the complete SET of model row SETS for every kept assignment/train input, '
            'with the tool’s name-else-type output-column correspondence; it must never pair models by equal indices. '
            'Missing rows describe a difference, not a proof of unrecoverability.', '']
        sides = {}
        for side, letter in (('gold', 'G'), ('mutant', 'X')):
            t = ev['table_indices'][side + '_kept']
            sides[side] = self.table(self.readers[side], t, ev[side + '_kept_assignment_map'], letter, body=True, show_rows=False)
        gs, gg, gd = sides['gold']
        ms, mg, md = sides['mutant']
        self.target_fields = dict(gold=[c['display_name'] for c in gs], mutant=[c['display_name'] for c in ms])
        self.blocks += ['G physical field order: ' + compact(self.target_fields['gold']),
                        'Suggested positional output labels (explicit --columns mapping): ' + compact(['V' + str(i) for i in range(len(gs))]), '']
        self.blocks += ['### Retained columns and exact differences', '']
        def stored_keys(side, schema):
            table = ev['table_indices'][side + '_kept']
            native = self.readers[side].tables.get('keys')
            if native is None:
                return []
            source_to_projected = {}
            for c in schema:
                if c['source_body_column'] is not None:
                    source_to_projected.setdefault(c['source_body_column'], c['index'])
            return [tuple(source_to_projected[i] for i in key) for key in native[table]
                    if all(i in source_to_projected for i in key)]
        gkeys = stored_keys('gold', gs); mkeys = stored_keys('mutant', ms)
        self.comparison_key_evidence = dict(gold=gkeys, mutant=mkeys,
            authority='stored native tables.keys only, projected through exact source body columns')

        # Align only authenticated labels, equal value types, and equal declared
        # frame identities. Never pair different schema columns by row content.
        comparable = [(c['display_name'], c['type'], c['frame']) for c in gs] == [
            (c['display_name'], c['type'], c['frame']) for c in ms]
        for a in range(self.nkept):
            for ex in range(self.ntrain):
                for ge in gg[a][ex]:
                    for me in mg[a][ex]:
                        gentry = self.visible(gd[ge], gs)
                        mentry = self.visible(md[me], ms)
                        # Task-wide rows retain Example; restrict summaries to
                        # this train before counting, never count held-out rows.
                        def per_train(entry, schema):
                            ei = [c['index'] for c in schema if c['type'] == 'Example']
                            return [row for row in entry['rows'] if all(row[i]['value'][0] == ex for i in ei)]
                        grow = per_train(gentry, gs); mrow = per_train(mentry, ms)
                        prefix = f'assignment {a+1}; train{ex+1}; G model {gentry["model"]}, X model {mentry["model"]}'
                        self.blocks += [prefix, f'Complete source counts: G={len(grow)} rows; X={len(mrow)} rows.']
                        if comparable:
                            gset = {compact(row): row for row in grow}
                            mset = {compact(row): row for row in mrow}
                            self.blocks += [f'Shared={len(gset.keys() & mset.keys())}; missing G={len(gset.keys()-mset.keys())}; '
                                f'extra X={len(mset.keys()-gset.keys())}. These are exact typed display-tuple counts including frame status and extents; tool equality also matches columns by name/else type, renames component ids and compares Position/Box margins.']
                            shared_keys = [key for key in gkeys if key in mkeys]
                            if shared_keys:
                                key = min(shared_keys, key=lambda k: (len(k), k))
                                self.blocks += ['Stored native candidate key: ' + ', '.join(gs[i]['display_name'] for i in key) + '.']
                                def keyed(rows):
                                    result = collections.defaultdict(list)
                                    for row in rows:
                                        result[compact([row[i] for i in key])].append(row)
                                    return result
                                ga, ma = keyed(grow), keyed(mrow)
                                common = ga.keys() & ma.keys()
                                conflicts = sum({compact(r) for r in ga[k]} != {compact(r) for r in ma[k]} for k in common)
                                self.blocks += [f'Complete key comparison: shared keys={len(common)}; conflicting keys={conflicts}; G-only keys={len(ga.keys()-ma.keys())}; X-only keys={len(ma.keys()-ga.keys())}.']
                                aligned_schema = [dict(c, index=i, source_label='@aligned:'+str(i), display_name=side+'.'+c['display_name'])
                                    for i, (side,c) in enumerate([('G',c) for c in gs]+[('X',c) for c in ms])]
                                aligned = [gr+mr for k in sorted(common) for gr in ga[k] for mr in ma[k]]
                                self.rows(aligned_schema, dict(gentry, rows=aligned), 'G/X rows aligned on stored key; '+prefix)
                                missing = [r for k in ga.keys()-ma.keys() for r in ga[k]]
                                extra = [r for k in ma.keys()-ga.keys() for r in ma[k]]
                            else:
                                self.blocks += ['No shared stored native candidate key survives the projection; no row pairing or inferred key.']
                                missing = [gset[k] for k in sorted(gset.keys()-mset.keys())]
                                extra = [mset[k] for k in sorted(mset.keys()-gset.keys())]
                            self.rows(gs, dict(gentry, rows=missing), 'Rows only in G; '+prefix)
                            self.rows(ms, dict(mentry, rows=extra), 'Rows only in X; '+prefix)
                        else:
                            self.blocks += ['Schemas differ; tuple subtraction and key alignment are undefined. All rows are side-exclusive in their respective typed schemas.', '']
                            self.rows(gs, dict(gentry, rows=grow), 'G schema-exclusive rows; '+prefix)
                            self.rows(ms, dict(mentry, rows=mrow), 'X schema-exclusive rows; '+prefix)
                        for i, c in enumerate(ms):
                            # The shared printer preserves cell/frame types.
                            vals = sorted({self.values.text(row[i], c, mentry['example']) for row in mrow})
                            gold_columns = [j for j, x in enumerate(gs) if x['display_name'] == c['display_name'] and x['type'] == c['type']]
                            text = f'X.{c["display_name"]}: '
                            if not vals:
                                text += 'empty domain'
                            elif len(vals) == 1:
                                text += 'constant ' + vals[0]
                            else:
                                text += f'{len(vals)} distinct values'
                            if len(gold_columns) == 1:
                                j = gold_columns[0]
                                gvals = {compact(row[j]['value']) for row in grow}
                                mvals = {compact(row[i]['value']) for row in mrow}
                                missing = [row[j] for row in grow if compact(row[j]['value']) in gvals-mvals]
                                texts = sorted({self.values.text(cell, gs[j], gentry['example']) for cell in missing})
                                text += '; gold-only native values: ' + (', '.join(texts) or '(none)')
                            self.blocks += [text]
                        for i, c in enumerate(ms):
                            for j in range(i):
                                d = ms[j]
                                if mrow and (c['type'] == d['type'] or {c['type'], d['type']} <= {'Box', 'Position'}):
                                    if all(row[i]['value'] == row[j]['value'] for row in mrow):
                                        self.blocks += [f'X.{c["display_name"]} repeats X.{d["display_name"]} in every row '
                                            '(native values; declared types/frames remain as shown).']
                        self.blocks += ['']

    def choices(self):
        self.blocks += ['## Complete kept DET assignments', 'These are controls, including DETs not read by the changed body.', '']
        choices, evidence = Assignments(self.engine).compiled(self.r, self.gprogram, self.gexport)
        report = copy.deepcopy(self.r['full_replay']['evaluation'])
        for choice in report.get('full_choice_extents', {}).get('choices', []):
            for det in choice['dets']:
                if det.get('status') in ('stopped', 'fault'):
                    original = compact(det)
                    det['reason'] = 'saved annotation ' + det['status'] + ': ' + original
                    det['status'] = 'unresolved'
        annotated = dict(structured=dict(kept_decoded=choices, components=dict(
            report=report)), kept_assignments=self.kept, pending=[])
        attach_choice_extents(annotated)
        for problem in annotated['pending']:
            self.gap(problem)
        for a, choice in enumerate(choices):
            for det in choice:
                schema = [dict(c, index=i, display_name=c['name'], source_label='@column:' + str(i))
                          for i, c in enumerate(det['schema'])]
                examples = det.get('extent_examples') or [dict(example='task', example_kind=0,
                    example_index=0, model=0, rows=det['rows'])]
                for entry in examples:
                    if entry['example_kind'] == 2:
                        continue
                    self.rows(schema, entry, f'assignment {a+1}; held {det["display_name"]}; '
                              f'{entry["example"]}; native model {entry["model"]}')

    def available(self):
        self.blocks += ['## Available tables for recovery',
            'Every gold table independent of G is available, including later definitions, DET relations and INIT ports. '
            'The native resolver graph excludes G and every direct or transitive dependent. '
            'Library predicates are callable operations, not stored available tables.', '',
            '`input` has fields P (Position) and Col (Color), exactly the input grids under Task, one relation per current example. '
            '`ex_input` has fields E (Example), P (Position), Col (Color): the same grids with an explicit example column. '
            '`ex_output` has fields E, P, Col: exactly the GIVEN train outputs under Task. '
            'These grid encodings specify every fact tuple; no test output tuple is supplied. '
            'Every recovery must equal its target on train and test inputs; the tool checks hidden target rows without showing them.', '']
        for d in self.gexport['definitions']['native_relations']:
            try:
                node = self.definition_node(d)
            except ValueError as error:
                self.gap(str(error))
                continue
            if node not in self.availability['independent_nodes']:
                continue
            offered = dict(definition=copy.deepcopy(d), graph_node=node,
                           ex_output_dependent=node in self.availability['ex_output_dependent_nodes'],
                           status='unavailable', table_receipt_index=None)
            self.available_definitions.append(offered)
            if not d.get('readable_in_checked_program'):
                offered['reason']='native export does not supply a callable source binding in this checked scope'
                self.gap('independent '+d.get('display_name',d['source_name'])+': callable source binding unavailable in native export')
                self.blocks += [d.get('display_name',d['source_name'])+': independent table, but its callable source binding is unavailable; never invent a port or clause name.', '']
                continue
            sel = d['native_selector']
            tables = [t for t in range(len(self.full.tables['width'])) if all(self.full.tables[k][t] == v for k, v in sel.items() if k in ('form','point','relation'))]
            name = d.get('display_name', d['source_name'])
            if len(tables) != 1:
                self.gap(f'available {name}: native selector {compact(sel)} has {len(tables)} stored tables (an alias/omitted port cannot be reconstructed from this snapshot)')
                self.blocks += [f'{name}: rows unavailable; see evidence gaps.', '']
                continue
            try:
                self.table(self.full, tables[0], self.full_maps, 'Available ' + name, definition=d)
                offered.update(status='complete', table_receipt_index=len(self.table_receipts)-1,
                               table_receipt=self.table_receipts[-1], native_ref=self.r['full_replay']['gold'])
                if offered['ex_output_dependent']:
                    self.blocks += [name + ': resolver/library evidence marks possible ex_output dependence; the native checker resolves whether hidden-test verification is required.', '']
            except (ValueError, KeyError, IndexError) as error:
                self.gap(f'available {name}: {type(error).__name__}: {error}')
                self.blocks += [f'{name}: rows unavailable; see evidence gaps.', '']

    def readers_and_program(self):
        self.blocks += ['## What the readers need',
            'Exact reader sites below show fields, bindings, joins, negation and guards. '
            'The complete owning clauses in the program provide their surrounding conditions and output projection.', '']
        ctx = self.gexport['definitions']
        # Resolver graph determines reads; no substring/name dependency guesses.
        reader_paths = {tuple(p[:1]) for n in self.availability['graph_nodes']
                        if n['node'] in self.availability['dependent_nodes']
                        and n['node'] not in self.availability['target_nodes']
                        for p in n['forms'] if p and p[:1] != self.owner}
        for path in sorted(reader_paths):
            if path in self.gnodes:
                self.blocks += ['```arclog', self.names.text(self.gnodes[path]['sexp']), '```']
        if not reader_paths:
            self.blocks += ['No downstream reader definition in the resolver graph.']
        self.blocks += ['', '### Typed literals at the change', '']
        for side, export in (('gold', self.gexport), ('mutant', self.mexport)):
            for arg in export['typed_sites']['arguments']:
                if under(arg['path'], self.owner) and arg.get('literal'):
                    self.blocks += [f'{side} AST {".".join(map(str,arg["path"]))}: {arg["literal"]["meaning"]}; {frame_text(arg["frame"])}']
        self.blocks += ['', '## Gold program', 'Source relation names are used throughout. '
            'Local variable spellings come from the engine writer; an authored variable-name map is not exported.', '```arclog']
        for n in self.gexport['nodes']:
            if len(n['path']) == 1:
                self.blocks += [('>> ' if n['path'] == self.owner else '   ') + self.names.text(n['sexp'])]
        self.blocks += ['```', '', '## Callable library meanings', '']
        ids = {r['resolution']['id'] for export in (self.gexport, self.mexport)
               for r in export['definitions']['readers'] if r['resolution']['kind'] == 'library'}
        registry = {e['id']: e for e in ctx['registry']['entries']}
        todo = list(ids)
        while todo:
            key = todo.pop()
            for read in registry[key]['reads']:
                child = 'lib:' + read['lib'] if 'lib' in read else None
                if child and child not in ids:
                    ids.add(child); todo.append(child)
        for key in sorted(ids):
            lib = registry[key]
            semantics = lib.get('semantics', {})
            self.blocks += [lib['name'] + ':', semantics.get('contract_markdown', 'Authored semantic contract unavailable.'), '']
            if semantics.get('status') != 'authored_contract':
                self.gap('library ' + key + ': authored semantic contract unavailable')
            self.blocks += ['```arclog', lib['declaration']['sexp']]
            if lib.get('arclog_implementation'):
                self.blocks += [lib['arclog_implementation']['sexp']]
            self.blocks += ['```', '']

    def column_correspondences(self):
        """Complete column-value families; no model pairing or semantic decoder."""
        self.blocks += ['## Values retained in another column or table',
            'These comparisons use every visible row, before sampling. Equal column domains do not establish row associations or a recovery. Different nominal types retain their identities; equal encodings are stated as encodings.', '']
        def signatures(receipt):
            fields = receipt['fields']; result = [collections.defaultdict(set) for _ in fields]
            example_columns = [i for i,c in enumerate(fields) if c['type']=='Example']
            nonempty = [False for _ in fields]
            for item in receipt['decoded_entries']:
                examples = range(self.ntrain) if item['example_kind']==0 else [item['example_index']]
                for ex in examples:
                    rows = [r for r in item['rows'] if all(r[i]['value'][0]==ex for i in example_columns)]
                    for i in range(len(fields)):
                        values = sorted({compact(r[i]['value']) for r in rows})
                        nonempty[i] |= bool(values)
                        result[i][(item['assignment'],ex)].add(compact(values))
            return [compact([(a,e,sorted(v)) for (a,e),v in sorted(column.items())]) if nonempty[i] else None
                    for i,column in enumerate(result)]
        x = next(r for r in self.table_receipts if r['title']=='X')
        xs = signatures(x)
        signature_cache = {id(t):signatures(t) for t in self.table_receipts if t['title']=='X' or t['title'].startswith('Available ')}
        for i, signature in enumerate(xs):
            if signature is None: continue
            matches = []
            for table in self.table_receipts:
                if table['title'] != 'X' and not table['title'].startswith('Available '): continue
                for j,other in enumerate(signature_cache[id(table)]):
                    if table is x and j>=i: continue
                    if signature==other:
                        source = 'X' if table is x else table['title'].removeprefix('Available ')
                        field = table['fields'][j]
                        matches.append(dict(relation=source, column=field['name'], type=field['type'], frame=field['frame']))
            if matches:
                field=x['fields'][i]
                self.column_matches.append(dict(x_column=field['name'], type=field['type'], matches=matches,
                    evidence='complete per-kept/train SETS of column-value model SETS; native encodings, not row-source proof'))
                self.blocks += ['X.'+field['name']+' ('+field['type']+') has the same complete per-kept/train column-value families as: '+
                    '; '.join(m['relation']+'.'+m['column']+' ('+m['type']+')' for m in matches)+'.']
        if not self.column_matches:
            self.blocks += ['No additional complete column-domain correspondence was found in the supplied visible X/available tables.']
        self.blocks += ['']

    def render_targets(self):
        """One stored catalog, used by document, tool and mechanical callers."""
        require(self.case_inventory is not None, 'case inventory missing')
        base = self.source_context['native_base']
        catalog = dict(schema='judge-target-catalog-v1', complete=False, targets=[], gaps=[],
            scope='G; strictly later tables of pair case; every table of every other case, without names',
            population_receipt={k:self.case_inventory[k] for k in ('catalogue_path','catalogue_sha256','catalogue_status')})
        self.target_catalog = catalog
        def gap(text):
            if text not in catalog['gaps']: catalog['gaps'].append(text)
            self.gap('Target catalog: '+text)
        binding=self.body_bindings['gold']
        point_tables=[t for t in range(len(self.full.tables['width'])) if selector_matches(self.full.tables,t,binding['native_selector'])]
        catalog['targets'].append(dict(target_id='G',case=self.r['case'],role='point',native_ref=self.r['full_replay']['gold'],
            native_selector=binding['native_selector'], native_base=base, kept_assignments=self.kept,
            assignment_map=self.full_maps, fields=binding['projected_schema'], binding=binding,
            native_table_index=point_tables[0] if len(point_tables)==1 else None,
            status='stored' if len(point_tables)==1 else 'acquire',
            acquisition=dict(helper='judgetool/checks.py:observe_gold', requires_saved_train_agreement=False,
                             source='full gold replay with projected observer and OUT; normal search then kept filter')))
        self.blocks += ['## Recovery targets',
            'G is the comparison above. The remaining targets are every table after the changed point in this case, and every table of every other case. Other-case names are ignored in comparison. Later tables of this case are complete while the document fits; large tables may be sampled to meet the limit, with complete row counts. Tables of other cases show at most 12 rows per kept/train/model entry, with complete row counts; use view-target with the target ID to see more. These are comparison-only targets, not additional available reads. Each case retains its own kept values and model contexts; ordinals are never zipped across cases.', '']
        for case in self.case_inventory['cases']:
            main = case['name']==self.r['case']; full=case['reference']
            if full is None:
                gap('case '+case['name']+': full replay reference missing'); continue
            evaluation=full['evaluation']; kept=evaluation.get('kept_assignments')
            if not kept:
                gap('case '+case['name']+': exact kept assignments missing'); continue
            try:
                reader=self.full if main else Native(load_native(full['gold'],Path(base)))
            except (ValueError,KeyError,OSError) as error:
                gap('case '+case['name']+': '+str(error)); continue
            export=self.gexport if main else None
            if not main and case.get('source_program') and case.get('source_record_data'):
                try:
                    _,export,_=self.programs.load(case['source_program'],case['source_record_data'])
                except (ValueError,KeyError) as error:
                    gap('case '+case['name']+': source metadata '+str(error))
            maps=evaluation.get('gold_assignment_map',[])
            definitions=export['definitions']['native_relations'] if export else []
            represented=set()
            old_namespace=self.row_namespace; old_values=self.values; old_policy=self.row_display_policy
            self.row_namespace=case['name']; self.row_display_policy='budget' if main else 'other_case'
            if not main:
                self.values=Values(dict(old_values.f, orientation_types=export['orientation_domains'] if export else {}, column_names={}))
            try:
                for table in range(len(reader.tables['width'])):
                    later=same_case_after(reader.tables,table,self.body,export) if main else True
                    if main and later is None:
                        gap('main-case table '+str(table)+': native source position unavailable'); continue
                    if not later: continue
                    ds=[d for d in definitions if selector_matches(reader.tables,table,d['native_selector'])]
                    definition=next((d for d in ds if d.get('column_witnesses')),None)
                    for d in ds: represented.add(compact(d['native_selector']))
                    target_id='T'+str(len(catalog['targets']))
                    fields=catalog_fields(reader,table,definition)
                    for field in fields:
                        if field['row_path'] is not None:field['field_name']=column_text(field['row_path'],'role')
                    item=dict(target_id=target_id,case=case['name'],role='later' if main else 'other_case',
                        native_ref=full['gold'],native_selector={k:reader.tables[k][table] for k in ('form','point','relation','fact')},
                        native_table_index=table,native_base=base,kept_assignments=kept,assignment_map=maps,
                        fields=fields,ignore_names=not main,status='stored',
                        definition=definition or {},source_record=case.get('source_record'))
                    catalog['targets'].append(item)
                    name=(definition.get('display_name') or definition['source_name']) if definition else 'native table '+str(table)
                    if reader.tables['point'][table]==2:
                        name=reader.tables['fact'][table]
                    if definition is None and export and reader.tables['point'][table]==1:
                        views=[v for v in export['body_views'] if selector_matches(reader.tables,table,v['native_table_selector'])]
                        if len(views)==1:
                            view=views[0]
                            owners=[n for n in export['nodes'] if n['path']==view['owner_path']]
                            if len(owners)==1:
                                owner=owners[0]; data=owner.get('data',{}); names=Names(export)
                                identity=data.get('defines',{}).get('name', data.get('name',{}))
                                slot=identity.get('slot') if isinstance(identity,dict) else None
                                source=names.tokens.get('&r'+str(slot)) if slot is not None else None
                                if source:
                                    name=source+' body at AST '+'.'.join(map(str,view['body_path']))
                    self.blocks += [f'### {target_id}; case {case["name"]}; {name}',
                        'Comparison only; '+('names ignored; other-case sample' if not main else 'after changed point; full counts')+'.',
                        'Schema in physical order: '+('; '.join(f["field_name"]+': '+f["type"]+((' in '+f["frame"]) if f["frame"] else '') for f in fields) or '(no columns)')+'.']
                    if reader.tables['point'][table]==2:
                        self.blocks += ['Facts are the input/GIVEN train grids under Task, with the declared Example/Position/Color fields. Test output facts are withheld.']
                        try:
                            schema=self.schema(reader,table,definition=definition)
                            _,decoded,evidence=self.entries(reader,table,maps,nkept=len(kept))
                            for a,items in enumerate(evidence):
                                for evidence_item in items:
                                    entry=self.visible(decoded[evidence_item['native_entry']],schema)
                                    self.blocks += [f'{target_id}; assignment {a+1}; {entry["example"]}; native model {entry["model"]}; complete visible row count={len(entry["rows"])}; rows under Task.']
                        except (ValueError,KeyError,IndexError) as error:
                            gap(target_id+': fact counts '+str(error))
                            self.blocks += ['Complete visible row count unavailable in this saved context.']
                        self.blocks += ['']
                        item['presentation']='task grids; no duplicated facts'; continue
                    existing=next((r for r in self.table_receipts if main and r['title'].startswith('Available ') and r['table']==table),None)
                    if existing is not None:
                        self.blocks += ['Complete visible rows already shown under '+existing['title']+'; reuse those rows with the same field order.', '']
                        item['table_receipt_index']=self.table_receipts.index(existing);continue
                    try:
                        self.table(reader,table,maps,target_id,definition=definition,nkept=len(kept),callable=False)
                        item['table_receipt_index']=len(self.table_receipts)-1
                    except (ValueError,KeyError,IndexError) as error:
                        item['presentation_status']='unavailable';gap(target_id+': visible context/field evidence '+str(error))
                        self.blocks += ['Rows unavailable in the saved compatible context; not an empty table.', '']
                if export:
                    for definition in definitions:
                        selector=definition['native_selector']
                        if compact(selector) in represented:continue
                        if main and not definition_after(definition,self.body,export):continue
                        # Aliases/ports are eligible even when storage omitted them.
                        if any(selector_matches(reader.tables,t,selector) for t in range(len(reader.tables['width']))):continue
                        target_id='T'+str(len(catalog['targets']))
                        catalog['targets'].append(dict(target_id=target_id,case=case['name'],role='later' if main else 'other_case',
                            native_ref=full['gold'],native_selector=selector,native_base=base,kept_assignments=kept,
                            assignment_map=maps,definition=definition,status='unavailable',ignore_names=not main))
                        name=definition.get('display_name',definition['source_name'])
                        witnesses=sorted(definition.get('column_witnesses',[]),key=lambda w:w['physical_column'])
                        self.blocks += [f'### {target_id}; case {case["name"]}; {name}',
                            'Comparison only; '+('names ignored; other-case sample' if not main else 'after changed point')+'.',
                            'Schema in physical order: '+('; '.join(column_text(w['row_path'],'role')+': '+w['type'] for w in witnesses) if witnesses else 'unavailable in saved source metadata')+'.',
                            'Complete row count and rows unavailable in the saved port/alias snapshot; request this target with view-target.', '']
                        gap(target_id+' '+case['name']+': omitted port/alias '+definition.get('display_name',definition['source_name']))
            finally:
                self.row_namespace=old_namespace; self.values=old_values; self.row_display_policy=old_policy
        if self.case_inventory['catalogue_status']!='authenticated_complete':
            gap('exported population/fault inventory is not yet authenticated complete')
        # Missing point test rows are lazily acquired by the one evaluator.
        # A stored inventory does not assert that acquisition or its check ran.
        catalog['complete']=not catalog['gaps']

    def policy_and_cases(self):
        require(self.case_inventory is not None, 'case inventory missing')
        admitted=self.admission_validation.get('eligible') is True and self.admission_validation.get('receipt_authenticated') is True
        if not admitted:
            self.gap('Judge admission '+self.admission_validation['status']+': '+self.admission_validation.get('reason','mechanical receipt does not admit this pair'))
        if self.body['kind'] == 'Det':
            self.gap('DET-kind pair is outside judge admission; retained only as a renderer qualification sample')
        self.blocks += ['## Admission and all-case targets',
            'Admission is determined only by the mechanical owner’s validated durable receipt. The judge admits only non-fitting mechanical-open, non-DET pairs where X holds every gold row and search did not cover the space. Missing receipts leave this as qualification evidence.',
            'Fits pairs are graded mechanically without a judge; lossy pairs receive Reject mechanically, and DET-kind pairs are not judged.',
            'Targets are G, tables of this case after the changed point, and every table of every other task case. Other-case tables are compared without names. Target names are explanatory handles, not equality identities or available reads.',
            'The exported case population and saved references below are an inventory. A corpus manifest or a table-map count does not prove all-case target coverage. Cross-case assignment ordinals and raw Ident namespaces must not be equated.', '']
        for case in self.case_inventory['cases']:
            if case['name'] == self.r['case']:
                state = 'main G and saved later table references; missing native evidence is listed below'
            elif case['reference'] is None:
                state = 'no saved full-kept reference located in the supplied inventory'
            else:
                state = f'saved full-kept reference; {len(case["reference"]["evaluation"].get("gold_assignment_map", []))} table maps recorded, not a completeness proof'
            self.blocks += ['- `' + case['name'] + '`: ' + state + '.']
        self.blocks += ['', 'Every table of every other case is eligible, with that case’s own kept/model contexts. There is no cross-case cutoff and no assignment ordinal zip. Target membership never grants a callable read.']
        point = self.body_bindings['gold']['native_selector']
        if not any(all(self.full.tables[k][t] == v for k,v in point.items() if k in ('form','point','relation'))
                   for t in range(len(self.full.tables['width']))):
            self.blocks += ['', 'This saved full-replay bundle has no point BODY table for target test rows. The tool can acquire it through full gold replay with a projected observer and OUT, using the shared INIT projection. Every target is acquired by fresh full gold replay of its own case; saved reference rows and completeness flags do not gate verification. Missing compatible kept context gives unknown. Component outputs are not substitutes.']
        self.blocks += ['', 'Clause execution uses full mutant replay with the inserted clause and OUT, followed by filtering entries for agreement with the kept assignment on every DET slot listed by each table. No submitted clause has been run or verified by this renderer; no kept entry means unknown.', '']

    def outputs(self):
        self.blocks += ['## Conditional train output fit',
            'Saved continuation under held gold DET values. This is a consequence, not the recovery criterion.', '']
        for output in self.r['evaluation'].get('outputs', []):
            a = output['assignment']
            for side in ('gold', 'mutant'):
                result = output.get(side, {})
                train = result.get('train') or []
                if not train:
                    self.blocks += [f'assignment {a+1}; {side}: {result.get("status", "unavailable")}']
                for tr in train:
                    ex = tr['example']
                    require(0 <= ex < self.ntrain, 'output train index outside train scope')
                    self.blocks += [f'assignment {a+1}; {side}; train{ex+1}: accepted-set fits={tr.get("fits")}; distinct grids={tr.get("distinct_output_grids")}']
                    for mi, model in enumerate(tr.get('models', [])):
                        # Explicit whitelist: never serialize the output object.
                        if model.get('grid_defined') is False:
                            state = 'no output grid: ' + str(model.get('reason', 'undefined'))
                        elif model.get('differing_cells') is not None:
                            state = str(model['differing_cells']) + ' cells differ from GIVEN'
                        else:
                            state = str(model.get('status', 'unavailable'))
                        self.blocks += [f'  native model {model.get("model", mi)}: {state}']
        self.blocks += ['']

    def adapter_contract(self):
        from native_correspondence import canonical_bound_field_type
        require(self.source_context is not None, 'source record/program binding missing')
        point_selector = self.body_bindings['gold']['native_selector']
        point_tables = [t for t in range(len(self.full.tables['width']))
            if all(self.full.tables[k][t] == v for k, v in point_selector.items() if k in ('form', 'point', 'relation'))]
        point_table = point_tables[0] if len(point_tables) == 1 else None
        projection_indices = [c['source_body_column'] for c in self.body_bindings['gold']['fields']]
        projection_bound = False
        if point_table is not None:
            full_schema = [dict(c) for c in self.full.schema(point_table)]
            try:
                binding=self._legacy_body_binding(self.full,point_table,full_schema,self.body)
                bind_body_schema(dict(schema=full_schema), self.body,legacy_binding=binding)
                projection_bound = all(index is None or (index < len(full_schema)
                    and full_schema[index]['ast_label_id'] == field['native_label_identity']['label_id']
                    and full_schema[index]['type'] == canonical_bound_field_type(field))
                    for index, field in zip(projection_indices, self.body_bindings['gold']['fields']))
            except (ValueError, KeyError, IndexError):
                projection_bound = False
        comparison_tables = [t for t in self.target_catalog['targets'] if t['role'] != 'point']
        contract = dict(schema='judge3-review-evidence-v3', review_only=True,
            reserved_relations=['&X', '&fix'], reserved_collision_policy='reject_source_or_native_token_collision',
            input=dict(handle='&X', side='mutant', binding=self.body_bindings['mutant'],
                       fields=self.body_bindings['mutant']['fields'],
                       callable_template=self.body_bindings['mutant']['callable_template']),
            comparison_target=dict(side='gold', callable=False, binding=self.body_bindings['gold'],
                full_replay_body=dict(native_ref=self.r['full_replay']['gold'],
                    native_selector=point_selector, native_table_index=point_table, assignment_map=self.full_maps,
                    status='stored' if point_table is not None and projection_bound else 'unavailable',
                    projection_indices=projection_indices, projection_schema_bound=projection_bound,
                    projection_helper='judge2/render2/body.py:project_entries',
                    scope='all train and test entries for checking; test rows never displayed')),
            comparison_keys=self.comparison_key_evidence,
            output=dict(relation='&fix', fields=self.body_bindings['gold']['fields'],
                        default_columns=['V' + str(i) for i in range(len(self.body_bindings['gold']['fields']))],
                        mapping='tool matches columns by name, else type; explicit ordered output labels may be supplied'),
            availability=dict(self.availability, definitions=self.available_definitions,
                              fact_relations=['input', 'ex_input', 'ex_output'], full_native_ref=self.r['full_replay']['gold']),
            admission=dict(self.admission_validation, reference=self.admission_reference,
                requires=['mechanical pass leaves pair open', 'X holds every main G row', 'search did not cover the space', 'pair is not DET-kind', 'pair does not fit'],
                authority='explicit authenticated native/mechanical receipt; not decoded-cell inference or P strata'),
            reader_projection=dict(status='unavailable',source_sha256=sha(compact(self.r).encode()),fields=[],
                reason='exact reader-visible G/X physical-field projection not supplied by a shared authenticated native mapper'),
            readers=dict(source_sha256=sha(compact(self.r).encode()),
                gold=self.gexport['definitions']['readers'],mutant=self.mexport['definitions']['readers'],
                gold_typed_sites=self.gexport['typed_sites'],mutant_typed_sites=self.mexport['typed_sites'],
                target_fields={side:self.body_bindings[side]['fields'] for side in ('gold','mutant')}),
            all_case_targets=self.case_inventory,
            target_catalog=self.target_catalog,
            column_correspondences=self.column_matches,
            kept_assignments=self.kept,
            source=self.source_context,
            programs=dict(gold=self.r['programs']['gold'], mutant=self.r['programs']['mutant']),
            relation_tokens=self.names.tokens,
            equality=dict(scope='for every compatible kept assignment and every train/test input',
                criterion='equality of complete SETS of model row SETS after the fixed output-field binding',
                model_alignment='none; model ordinals are independent, never zipped',
                task_scope='broadcast task-wide entries to each train; retain explicit Example fields',
                row_identity='tool equality: columns by name else type; component ids up to renaming; Position and Box by four margins; display differences retain typed cells and extent evidence',
                missing_evidence='reject; never invent rows, models, ports, aliases or frame evidence'),
            inlining=dict(mode='structural native AST transformation only; no textual substitution',
                lexical_identity='bind by exported owner/body/scope path and LabelId, never variable spelling alone',
                hygiene='alpha-rename every internal body/key variable to a fresh identity disjoint from the submitted clause and each other expansion',
                field_binding='connect each submitted &X site through its callable row path to its physical input field and native label identity; preserve joins, fresh uses and literals',
                key_scope='preserve enclosing INIT key bindings and exact lexical scope before projecting body fields; do not run component outputs as witnesses',
                branches='preserve OR/IF/NOT scopes and binding identity; canonical_or replaces later-branch re-made * labels with bare labels',
                det_scope='use the explicit full kept assignment; proposals and held values remain distinct',
                executable_clause='run submitted clause with documented canonical_or normalization; no other syntax repair'),
            recovery_space=dict(clause_kinds=['RULE', 'DET'], requires_x=True,
                source_rule='target columns come from X sites, or a lib computes exactly one row per X row from X columns; provenance required',
                other_atoms='restrict X rows; a target column bound at another non-lib atom is a partial source, not a recovery',
                library_relations='may restrict rows; computation of target columns must give exactly one row per X row; axis_elem/dir_elem expansion is not source-X recovery',
                union_rule='X-reading branches must contribute rows the target needs and X must not be redundant; native proof required',
                partial_source='verified target columns bound at another atom are recorded as partial source',
                outside_space='an X-free recomputation says nothing about X'),
            outcomes=['recovery verified', 'partial source verified', 'continuation passed', 'refused by the engine', 'did not verify', 'unknown'],
            judge_response='clauses with one or two evidence-based reasons each, or no clause found; no label or grade',
            execution_route='whole mutant replay with inserted clause and OUT, normal search; filter each table entry by agreement on every listed DET slot with gold kept assignment; no kept entry is unknown',
            coverage_authority='no search-negative or admission conclusion is inferred from a missing candidate or P strata',
            equality_authority='engine authenticates original native term identities; projected decoded cells are presentation evidence, not native identity authority',
            continuation_binding=dict(owner_path=self.owner, body_path=self.target_path,
                owner_native_data=self.gnodes[tuple(self.owner)]['data'],
                role='instance_input' if self.body['kind']=='INIT input' else 'instance_key' if self.body['kind']=='INIT key'
                     else 'det_proposal' if self.body['kind']=='Det' else 'clause_body',
                input_port=self.body['input_port'], input_port_columns=self.body['input_port_columns'],
                source_projection=self.body_bindings['gold']['fields'],
                key_declaration=(self.gnodes[tuple(self.target_path[:-1])]['data'] if self.body['kind']=='INIT key' else None),
                authentication='native derivation required; no inferred continuation proof',
                unavailable_policy='test unavailable if exact replacement/continuation mapping cannot be established'),
            test_requirement='every recovery equals gold target train and test rows at kept assignments; INIT uses the same projection; never display test rows',
            alternative=dict(requires_x=True, comparison_tables=comparison_tables,
                criterion='on every train input: table nonempty, unequal X and every available table; equality with any target is checked as recovery',
                equality_authority='native exact model-family comparator',
                recovery_match='check target match as a recovery including its test rows',
                missing_comparison_policy='unavailable'),
            integration_status='review evidence only; full replay execution route established; shared tool interface under construction, not an endpoint protocol')
        if self.mechanical_receipt is not None:
            contract['mechanical'] = self.mechanical_receipt
        return contract

    def render(self, pair_id):
        self.pair_id = pair_id
        self.target_section()
        syntax = ['## Clause syntax',
            'Use one `(RULE &fix ...)` or `(DET &fix ...)`. A site `(:Field *V)` binds V; `(:Field V)` joins an already bound variable. '
            'Recovery columns match target names, else types. An explicit ordered output-label list can select fields; scratch labels are projected away by that mapping. '
            '`NOT` binds nothing. Comparisons use bound variables. Order comparisons apply to numbers. '
            'Literal 0 is allowed at Number/Box/Position/Offset sites, or as the second constraint label when the first is Number or Box; never as Color. '
            'For a color test, join or antijoin with a named available color relation. '
            'Box zero means four zero margins, not an arbitrary top-left grid cell. '
            'In OR, introduce a variable with `*` in its first branch and use the bare name in subsequent branches. '
            'Binding templates below preserve nested sites and positional key fields. Replace V0, V1, etc. with your chosen variables.', '']
        self.row_display_policy = 'full'
        self.comparison()
        self.row_display_policy = 'budget'
        self.blocks += ['Mechanical redundant attribute: ' + (str(self.mechanical_receipt['redundant']).lower()
                        if self.mechanical_receipt is not None and 'redundant' in self.mechanical_receipt else 'not supplied'), '']
        try:
            self.choices()
        except (ValueError, KeyError, IndexError) as error:
            self.gap(f'complete held DET evidence: {type(error).__name__}: {error}')
        self.render_targets()
        self.readers_and_program()
        self.available()
        self.column_correspondences()
        self.policy_and_cases()
        self.blocks += syntax
        self.task_section()
        self.outputs()
        status = 'HELD' if self.gaps else 'COMPLETE'
        self.blocks += ['## Evidence status', status, *['- ' + g for g in self.gaps], '']
        self.blocks[2:2] = [f'Evidence status: {status}. See the evidence-status section for any gaps.', '']
        for section in self.row_sections:
            section['begin'] += 2; section['end'] += 2
        full_blocks = list(self.blocks)
        full_text = real_paths('\n'.join(full_blocks) + '\n')
        selected = {}
        sample_receipts = []
        def assemble():
            blocks = []; pos = 0
            for begin, (end, lines) in sorted(selected.items()):
                blocks.extend(full_blocks[pos:begin]); blocks.extend(lines); pos=end
            blocks.extend(full_blocks[pos:])
            text = real_paths('\n'.join(blocks) + '\n')
            for item in sample_receipts:
                text = text.replace('All rows: '+item['ref']+' (complete set defined above).',
                    'Rows: '+item['ref']+' (sample; full counts above; use the tool to see more).')
            notice = ('Display limit proposal: '+str(self.document_limit)+' UTF-8 bytes; '
                + ('other-case tables sampled; additional large tables sampled only as needed; G/X comparison complete; full row/comparison counts retained; query the tool to see more.' if selected else 'tables complete (common rows without a native key are omitted from the comparison as specified).'))
            text = text.replace('# Judge document\n', '# Judge document\n'+notice+'\n')
            size=0
            for _ in range(5):
                result=text+'\nDocument size: '+str(size)+' UTF-8 bytes.\n'
                new=len(result.encode())
                if new==size: return result
                size=new
            return result
        def sample(section, cap):
            sample_entry = dict(section['entry'], rows=section['entry']['rows'][:cap])
            self.retained_objects.append(sample_entry)
            values = section['values']
            for c in section['table']['schema']:
                values.f['column_names'][c['source_label']] = c['display_name']
            rows = values.rows(section['table'], sample_entry, section['order'])
            lines=['  '+section['ref']+f' ({section["total"]} rows total; first {cap} shown; {section["total"]-cap} omitted):',
                *['  '+line for line in values.layout(rows, section['order'], allow_grid=False)]]
            selected[section['begin']] = (section['end'], lines)
            sample_receipts[:] = [r for r in sample_receipts if r['ref']!=section['ref']]
            sample_receipts.append(dict(ref=section['ref'], title=section['title'], total=section['total'], shown=cap,
                omitted=section['total']-cap, policy=section['policy']))
        # Other-case displays are bounded independently of the document budget.
        # G/X comparison definitions stay complete,
        # even when their row sets are referenced by another presentation alias.
        for section in self.row_sections:
            if section['policy']=='other_case' and section['ref'] not in self.full_row_refs and section['total']>12:
                sample(section,12)
        text=assemble()
        for cap in (12, 1):
            for section in sorted(self.row_sections, key=lambda r: sum(len(x.encode()) for x in full_blocks[r['begin']:r['end']]), reverse=True):
                if len(text.encode()) <= self.document_limit:
                    break
                if section['ref'] in self.full_row_refs or section['total'] <= cap: continue
                sample(section,cap)
                text=assemble()

        display = dict(limit_bytes=self.document_limit, proposed=True, full_bytes=len(full_text.encode()),
            sampled=bool(selected), other_case_sample_limit=12, same_case_later='complete unless sampled for budget', comparison='complete', sampled_tables=sample_receipts, limit_met=len(text.encode())<=self.document_limit)

        sections = collections.Counter()
        section = 'opening'
        for line in text.splitlines(keepends=True):
            if line.startswith('## '):
                section = line.strip()[3:]
            sections[section] += len(line.encode())
        return text, dict(schema='judge3-document-v3', pair_id=pair_id, task=self.r['task'], case=self.r['case'],
                          status=status, gaps=self.gaps, display=display, sections_bytes=dict(sections), recovery_handle='&X', target_fields=self.target_fields,
                          adapter=self.adapter_contract(),
                          table_receipts=self.table_receipts, relation_tokens=self.names.tokens,
                          source_native=self.r['native'], source_full=self.r['full_replay']['gold'],
                          native_reader=reader_metadata())


def key(r):
    edits = r['edits'] if 'edits' in r else r['identity']['edits']
    return r['task'], r['case'], r['K'], r['operation'], compact(edits)


def dependencies(engine):
    import arclog.arclog as binary
    paths = [CODE_ROOT / 'study_paths.py', Path(__file__).resolve(), Path(binary.__file__).resolve()]
    paths += [S / 'judge2/render2' / name for name in (
        'native.py', 'structured.py', 'values.py', 'render.py', 'grids.py',
        'assignments.py', 'components.py', 'column_paths.py', 'sites.py', 'headers.py', 'body.py')]
    paths += [S / 'judge2/published_code.py']
    paths += [S / 'judge2/support' / name for name in ('tableview.py', 'views.py')]
    paths += [S / 'ast/run/native_storage.py', S / 'ast/run/next_revision/family_recovery.py',
              Path(reader_metadata()['source'])]
    paths += [ROOT/'brief-core.md', ROOT/'catalog.py', ROOT/'tool-usage.md']
    return {str(path.resolve()): sha(path.read_bytes()) for path in paths}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--document-limit', type=int, default=DEFAULT_DOCUMENT_LIMIT, help='proposed UTF-8 document budget; sample large displays only when exceeded')
    p.add_argument('--corpus', type=Path, required=True)
    p.add_argument('--selection', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--support-site', type=Path, help='site-packages supplying NumPy for shared tableview')
    p.add_argument('--admission-index', type=Path, help='explicit list of {pair_id, reference}; validation delegated to mech.admission.load_admission')
    p.add_argument('--mechanical-receipts', type=Path, help='explicit JSON list of pair_id/redundant boolean receipts; omitted attributes stay unknown')
    p.add_argument('--tasks', type=Path, default=MAIN_ROOT / 'data/tasks')
    a = p.parse_args()
    require(a.output.resolve().is_relative_to(DATA_ROOT / 'judge3'), 'output must stay inside owned judge3 directory')
    import arclog
    if a.support_site:
        sys.path.append(str(a.support_site.resolve()))
    # Resolve presentation dependencies before streaming large corpus files.
    from values import printer
    printer()
    selection = json.loads(real_paths(a.selection.read_text()))
    require(isinstance(selection, list), 'selection must be a list')
    by_task = collections.defaultdict(dict)
    for row in selection:
        require(key(row) not in by_task[row['task']], 'duplicate selection identity')
        by_task[row['task']][key(row)] = row['pair_id']
    a.output.mkdir(parents=True, exist_ok=True)
    brief = ((ROOT/'brief-core.md').read_text() + '\n' + (ROOT/'tool-usage.md').read_text()).replace('@STUDY_CODE_ROOT@', str(CODE_ROOT))
    (a.output/'judge-brief.md').write_text(brief)
    mechanical = {}
    if a.mechanical_receipts is not None:
        raw_receipts = a.mechanical_receipts.read_bytes()
        for receipt in json.loads(raw_receipts):
            require(('redundant' not in receipt or type(receipt['redundant']) is bool) and receipt['pair_id'] not in mechanical,
                    'invalid or duplicate mechanical receipt')
            mechanical[receipt['pair_id']] = dict(receipt=receipt,
                source_path=str(a.mechanical_receipts.resolve()), source_sha256=sha(raw_receipts))
            if 'redundant' in receipt:
                mechanical[receipt['pair_id']]['redundant'] = receipt['redundant']
    admission_index={}
    if a.admission_index is not None:
        for item in json.loads(real_paths(a.admission_index.read_text())):
            require(item['pair_id'] not in admission_index,'duplicate admission reference')
            admission_index[item['pair_id']]=item['reference']
    dependency_hashes = dependencies(arclog)
    version = sha(compact(dependency_hashes).encode())
    dependency_stats = {path: (Path(path).stat().st_size, Path(path).stat().st_mtime_ns) for path in dependency_hashes}
    programs = Programs(arclog)
    prior_path = DATA_ROOT / 'cross-case/missing.json'
    prior_raw = prior_path.read_bytes()
    prior_cases = {row['task']: row['found'] for row in json.loads(real_paths(prior_raw.decode()))}
    case_inventories = {}
    started = time.monotonic(); done = 0; counts = collections.Counter()
    report = a.output / 'render-report.jsonl'
    with report.open('w') as log:
        def emit(item):
            nonlocal done
            done += 1; counts[item['status']] += 1
            elapsed = time.monotonic() - started
            item.update(done=done, total=len(selection), elapsed=round(elapsed, 3), rate=round(done/max(elapsed, .001), 3))
            log.write(compact(item) + '\n'); log.flush()
            print(compact(item), file=sys.stderr, flush=True)
        for task, want in by_task.items():
            task_data = json.loads((a.tasks / (task + '.json')).read_text())
            base = a.corpus / task
            cached = a.output / 'records'
            cached.mkdir(exist_ok=True)
            def records():
                for wanted_id in list(want.values()):
                    path = cached / (wanted_id + '.json.gz')
                    if path.exists():
                        with gzip.open(path, 'rt') as stream:
                            yield stream.read(), path
                last_progress = time.monotonic()
                for filename in ('recoverable.jsonl.gz', 'pairs.jsonl.gz'):
                    source = base / filename
                    if not source.exists() or not want:
                        continue
                    scanned = 0
                    with gzip.open(source, 'rt') as incoming:
                        for line in incoming:
                            scanned += 1
                            if time.monotonic() - last_progress >= 10:
                                elapsed = time.monotonic() - started
                                print(compact(dict(event='scan', task=task, file=filename, scanned=scanned, done=done, total=len(selection), elapsed=round(elapsed, 1), rate=round(done/max(elapsed,.001),3))), file=sys.stderr, flush=True)
                                last_progress = time.monotonic()
                            yield line, source
                            if not want:
                                break
            for line, source in records():
                line = real_paths(line)
                marker = ',"relation_source_names":'
                head = line.partition(marker)[0]
                probe = json.loads(head + '}') if len(head) < len(line) else json.loads(line)
                identity = key(probe)
                if identity not in want:
                    continue
                record = json.loads(line)
                require(key(record) == identity, 'record header identity differs')
                pair_id = want.pop(identity)
                atomic_gzip(cached / (pair_id + '.json.gz'), line)
                directory = a.output / pair_id
                directory.mkdir(parents=True, exist_ok=True)
                for old in ('prompt.md', 'prompt.json', 'error.json'):
                    (directory / old).unlink(missing_ok=True)
                try:
                    program_paths = {}
                    for side in ('gold', 'mutant'):
                        program_path = directory / (side + '.arclog')
                        atomic_text(program_path,record['programs'][side])
                        program_paths[side] = dict(path=str(program_path.resolve()), sha256=sha(program_path.read_bytes()))
                    doc = Document(record, base, task_data, arclog, programs)
                    doc.document_limit = a.document_limit
                    doc.mechanical_receipt = mechanical.get(pair_id)
                    doc.admission_reference=admission_index.get(pair_id)
                    doc.admission_validation=admission_validation(doc.admission_reference,record)
                    if task not in case_inventories:
                        import numpy as np
                        task_manifest_path = base/'manifest.json'
                        task_manifest_raw = task_manifest_path.read_bytes()
                        task_manifest = json.loads(task_manifest_raw)
                        cases_path = Path(task_manifest['config']['export'])/'tasks'/task/'cases.npz'
                        with np.load(cases_path, allow_pickle=False) as population:
                            case_names = population['case'].tolist()
                        case_sources = {}
                        retained_path = base/'retained.jsonl'
                        if retained_path.exists():
                            with retained_path.open() as rows:
                                for raw in rows:
                                    row = json.loads(real_paths(raw)); case = row['case']
                                    full = row.get('full_replay'); ev = (full or {}).get('evaluation', {})
                                    if case in case_sources or not (full and ev.get('gold_collection',{}).get('materialization_complete') and ev.get('gold_status',{}).get('status')=='complete'):
                                        continue
                                    case_cache = a.output/'case-records'; case_cache.mkdir(exist_ok=True)
                                    normalized = real_paths(raw)
                                    path = case_cache/(task+'-'+sha(case.encode())+'.json.gz')
                                    atomic_gzip(path,normalized)
                                    case_sources[case] = dict(reference=full, source_record=dict(path=str(path.resolve()), sha256=sha(normalized.encode())),
                                        source_program=row['programs']['gold'], source_record_data=row)
                        case_inventories[task] = dict(
                            catalogue_path=str(cases_path), catalogue_sha256=sha(cases_path.read_bytes()),
                            catalogue_status='exported population recorded; native provenance/fault authentication pending',
                            corpus_manifest_path=str(task_manifest_path.resolve()), corpus_manifest_sha256=sha(task_manifest_raw),
                            corpus_case_limit=task_manifest['config'].get('case_limit'),
                            corpus_manifest_cases=task_manifest['cases'],
                            reference_inventory_path=str(prior_path), reference_inventory_sha256=sha(prior_raw),
                            comparison='names ignored; no cross-case assignment zip or shared Ident namespace assumption',
                            other_case_cutoff='none: every table of every other case is eligible',
                            cases=[dict(name=case, reference=case_sources.get(case,{}).get('reference',prior_cases.get(task, {}).get(case)),
                                        source_record=case_sources.get(case,{}).get('source_record'),
                                        source_program=case_sources.get(case,{}).get('source_program'),
                                        source_record_data=case_sources.get(case,{}).get('source_record_data'),
                                        target_eligibility='main_case_point_and_later' if case==record['case'] else 'every_table')
                                   for case in case_names])
                    doc.case_inventory = copy.deepcopy(case_inventories[task])
                    doc.programs = programs
                    for case in doc.case_inventory['cases']:
                        if case['name'] == record['case']:
                            case.update(reference=record['full_replay'], target_eligibility='main_case_point_and_later', source_program=record['programs']['gold'])
                        else:
                            case['target_eligibility']='every_table'
                    doc.source_context = dict(record_path=str((cached/(pair_id+'.json.gz')).resolve()),
                        record_encoding='gzip_json', record_sha256=sha(line.encode()),
                        native_base=str(base.resolve()), task_path=str((a.tasks/(task+'.json')).resolve()),
                        program_paths=program_paths, pair_directory=str(directory.resolve()),
                        kept_assignment_map=dict(gold=record['evaluation']['gold_kept_assignment_map'],
                                                 mutant=record['evaluation']['mutant_kept_assignment_map']))
                    document, manifest = doc.render(pair_id)
                    for case in manifest['adapter']['all_case_targets']['cases']:
                        case.pop('source_record_data',None)
                    require(all((Path(path).stat().st_size, Path(path).stat().st_mtime_ns) == signature
                                for path, signature in dependency_stats.items()), 'renderer dependency changed during rendering')
                    manifest.update(render_version=version, dependencies=dependency_hashes, source_file=str(source.resolve()),
                                    source_record_sha256=sha(line.encode()), corpus=str(a.corpus.resolve()),
                                    document_sha256=sha(document.encode()), bytes=len(document.encode()))
                    (directory / 'error.json').unlink(missing_ok=True)
                    atomic_text(directory / 'evidence.md',document)
                    # Held evidence remains inspectable, never a callable prompt.
                    if manifest['status'] == 'COMPLETE':
                        footer = '\n# Pair identity\n' + compact(dict(pair_id=pair_id, render_version=version)) + '\n'
                        invocation = ('Tool paths: PYTHON=' + sys.executable + '; TOOL=' + str(S/'judgetool/judge_tool.py')
                                      + '; PAIR_DIR=' + str(directory.resolve()) + '\n\n')
                        prompt = brief + '\n' + invocation + document + footer
                        (directory / 'prompt.md').write_text(prompt)
                        (directory / 'prompt.json').write_text(compact(dict(
                            schema='judge3-prompt-v1', pair_id=pair_id, render_version=version,
                                    sha256=sha(prompt.encode()), brief_sha256=sha(brief.encode()), file='prompt.md')) + '\n')
                    atomic_text(directory / 'manifest.json',json.dumps(manifest, indent=2) + '\n')
                    emit(dict(pair_id=pair_id, task=task, status=manifest['status'], bytes=manifest['bytes'], gaps=manifest['gaps'], display=manifest['display']))
                except Exception as error:
                    failure = dict(pair_id=pair_id, task=task, status='ERROR',
                                   error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
                    (directory / 'error.json').write_text(json.dumps(failure, indent=2) + '\n')
                    emit(failure)
            for pair_id in want.values():
                emit(dict(pair_id=pair_id, task=task, status='NOT_FOUND'))
        require(dependencies(arclog) == dependency_hashes, 'renderer dependency bytes changed during rendering')
        (a.output / 'summary.json').write_text(json.dumps(dict(total=len(selection), counts=dict(counts),
            render_version=version, elapsed=time.monotonic()-started), indent=2) + '\n')
    return 1 if counts['ERROR'] or counts['NOT_FOUND'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

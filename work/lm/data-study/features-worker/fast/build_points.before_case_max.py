#!/usr/bin/env python3
"""Stream the feature-store point directories of a converted gold corpus, with no mutant pairs.

For each task, in the order of --tasks, and for each case of that task, the builder writes one directory per
branch point (the points of the case's gold program: Rule, Det, INIT key, INIT input and CHOOSE clause) with the files
that `judge3/export_dataset.export_target` writes for the first pair of a point in features mode:

    <id>/point.json  train.json  libraries.json  gold.arclog  tables/<id>.json  (G and the available tables)

The case's program is the program that the case's token stream decodes to (`arclog.corpus_streams`, then
`StudyProgram.from_stream`), so that its clause indexes, and so the paths of its points, are those of the stream. The
cases of a task are the streams that `model/export.py` keeps: not a stream that gives no mask, and not a repeat of an
earlier stream, in the order of the case names. The Tn ids of a case count the original tables of the cases before it,
as `export_target` counts them.

Each directory is written to `<id>.building` and renamed when it is complete. A directory that exists is skipped, and so
is a task that has a record in `<cache>/done/`. A failure of one point, one case or one task is logged to
`<cache>/failures.jsonl` when its task ends, and at once to `<cache>/failures-live.jsonl`, and the run goes on. A task
whose first PREPARE_GIVE_UP cases all fail in preparation, before any point is built, skips its other cases, and a
later run tries them again. With --stall or --task-gib, a task that builds no point for --stall seconds, or whose worker
holds more than --task-gib GiB, is stopped and listed in `<cache>/set-aside.txt`, and such a run skips the tasks listed
there; a run without both options builds them. The builder writes only under the output root and its cache directory
(default `<output>.cache`: scratch directories of the workers, the done records and the failure log).

Run it with the python of a runtime with the current engine, for example

    work/lm/data-study/ast/run/runtime-b157cc37/venv/bin/python -B work/lm/data-study/feat-exp/study/build_points.py \\
        work/arclog-v2-4b3e64f15/out <points root> --tasks <file> --workers 4

`compare OLD NEW` compares the directories of the cases that both roots hold, file by file.
"""
import argparse
import collections
import hashlib
import json
import multiprocessing
import os
import queue
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[5]
STUDY = REPO / 'model/study'
KINDS = ('Rule', 'Det', 'INIT key', 'INIT input', 'CHOOSE clause')
MIN_FREE_GB = 5
PREPARE_GIVE_UP = 8  # the cases of a task often fail in preparation for one shared reason


# ---------------------------------------------------------------------------------------------------------- naming

def point_name(task, case, point, scheme='old'):
    """The directory name of a point. `old` is what `export_by_pair_id.point_directory` gives (and so what the old
    store holds); `stream` is `stream_export.point_id`."""
    if scheme == 'old':
        return task + '-' + hashlib.sha256(json.dumps([case, point]).encode()).hexdigest()[:12]
    return task + '-' + hashlib.sha256(json.dumps([task, case, point]).encode()).hexdigest()[:16]


def dumps(value):
    """The bytes of `dataset_format.write_json(compact=True)` for a value, without the final newline."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def write_bytes(path, data):
    with open(path, 'wb') as out:
        out.write(data)


def resolve_corpus(path):
    path = Path(path).resolve()
    return path / 'gen' if (path / 'gen').is_dir() else path


# ---------------------------------------------------------------------------------------------------------- the study stack

class Env:
    """One process's evaluator and the study stack's policy objects."""
    on_point = None  # called after each built point

    def __init__(self, cfg):
        self.cfg = cfg
        sys.dont_write_bytecode = True
        for p in (STUDY / 'judge3', STUDY, STUDY / 'ast/run', STUDY / 'judgetool'):
            sys.path.insert(0, str(p))
        import arclog
        from study_paths import CODE_ROOT, DATA_ROOT
        from evaluator import ReplayEvaluator, sha
        self.arclog, self.sha, self.CODE_ROOT, self.DATA_ROOT = arclog, sha, CODE_ROOT, DATA_ROOT
        # Every table replay writes an artifact of all its entries; the builder reads the native tables instead.
        original = ReplayEvaluator.replay_program

        def replay_program(self_, *args, **kwargs):
            kwargs.setdefault('artifact_mode', 'metadata')
            return original(self_, *args, **kwargs)
        ReplayEvaluator.replay_program = replay_program
        self.ev = ReplayEvaluator(config=cfg.run_json, deadline=cfg.deadline)
        self.scratch = Path(cfg.cache) / 'scratch' / str(os.getpid())
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.ev.artifacts = self.scratch
        from nonrender_metadata import MetadataProducer, _policy
        renderer, Programs, selectors, sources = _policy()
        self.renderer, self.selectors = renderer, selectors
        producer = MetadataProducer.__new__(MetadataProducer)
        producer.engine, producer.policy, producer.selectors, producer.sources = arclog, renderer, selectors, sources
        producer.programs = Programs.__new__(Programs)
        producer.programs.engine, producer.programs.settings = arclog, self.ev.settings
        producer.programs.cache, producer.programs.names = collections.OrderedDict(), collections.OrderedDict()
        producer.case_cache = {}
        self.producer = producer

    def clean_scratch(self):
        for p in self.scratch.iterdir():
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)


class GoldSession:
    """One native session for the gold of one case: FITS once, then the BODY of each point.

    This is `gold_body.capture` with the session kept across the points of the case."""

    def __init__(self, env, record, text):
        from native_correspondence import Correspondence
        from tables import full_kept_matches
        self.env, self.record = env, record
        self._cm = env.ev.fresh_session()
        self.iso = iso = self._cm.__enter__()
        arclog = iso.arclog
        self.native_ev = iso.task_evaluator(record['task'])
        self.program = arclog.StudyProgram.from_sexp(text, iso.settings)
        self.export = json.loads(arclog.study_program_export_json(self.program))
        self.source_program = self.program.decode_source()
        self.source_export = json.loads(arclog.study_program_export_json(self.source_program))
        self.bridged = json.loads(arclog.study_program_export_json(self.program, source_program=self.source_program))
        self.correspondence = Correspondence(self.bridged, program_sexp=self.export['program_sexp'],
                                             source_program_sexp=self.source_export['program_sexp'])
        self.source_correspondence = Correspondence(self.source_export, program_sexp=self.source_export['program_sexp'],
                                                    source_program_sexp=self.source_export['program_sexp'])
        self.self_correspondence = Correspondence(self.export, program_sexp=self.export['program_sexp'],
                                                  source_program_sexp=self.export['program_sexp'])
        evidence = json.loads(self.program.choice_evidence_json('[]'))
        if evidence.get('schema') != 'arclog-study-choices-v1' or evidence.get('complete') is not True:
            raise ValueError('original gold full DET schema unavailable')
        self.kept = json.loads(self.native_ev.gold_kept(program=self.program))
        self.choices = iso.validate_gold_observation(self.program, self.kept, record['task'])
        self.old_by_fresh = full_kept_matches(env.ev.legacy, self.choices, evidence['dets'], record)

    def close(self):
        self._cm.__exit__(None, None, None)

    def body(self, point):
        """The `gold_body.capture` yield for the BODY at `point`."""
        from evaluator import canonical, sha
        from tables import Incomplete
        from native_correspondence import AtomicPacked
        from gold_body import _held_entries
        iso, record = self.iso, self.record
        view = self.correspondence.body_from_source(point)
        source_view = self.source_correspondence.body(point)
        status, payload = self.native_ev.gold_body(self.program, view['body_path'], canonical(self.choices))
        report = json.loads(status)
        observed = iso.validate_gold_observation(self.program, report, record['task'],
                                                 schema='arclog-study-gold-body-v1')
        if (observed != self.choices or report.get('gold_observation_ref') != self.kept.get('gold_observation_ref')
                or report.get('gold_observation_cached') is not True):
            raise Incomplete('original BODY did not reuse the exact native gold observation')
        if (report.get('body_path') != view['body_path'] or report.get('owner_path') != view['owner_path']
                or report.get('body_status', {}).get('status') != 'complete'
                or report.get('body_coverage', {}).get('complete') is not True
                or report.get('body_table_packed') is not True):
            raise Incomplete('original gold BODY scope, coverage or packing incomplete')
        for example in report['body_coverage']['examples']:
            counts = example.get('model_counts')
            if (example.get('status', {}).get('status') != 'complete' or not isinstance(counts, list)
                    or len(counts) != len(self.choices) or any(type(c) is not int or c < 0 for c in counts)):
                raise Incomplete('original BODY model enumeration is incomplete')
        native = iso.legacy.native(payload)
        table = report['body_table']
        packed = AtomicPacked(report, native['_native_reader'], program_sexp=self.export['program_sexp'], side='gold')
        packed_table = packed.table(table, role='gold_body_kept')
        schema = json.loads(json.dumps(native['_native_reader'].schema(table)))
        if (len(schema) != len(view['columns']) or
                packed_table['cell_width'] != sum(c['physical_type']['cell_width'] for c in view['columns'])):
            raise Incomplete('original BODY physical width differs from native correspondence')
        for field in view['columns']:
            physical, descriptor = field['physical_column'], field['physical_type']
            if (type(physical) is not int or not 0 <= physical < len(schema)
                    or schema[physical]['type'] not in (descriptor['type'], descriptor['wire_type'])):
                raise Incomplete('original BODY packed physical type differs from native correspondence')
        held = _held_entries(native, table, report, self.old_by_fresh)
        return dict(ev=iso, native=native, table=table, view=view, source_view=source_view, schema=schema, packed=packed,
                    correspondence=self.correspondence, source_correspondence=self.source_correspondence,
                    held_entries=held, report=report, receipt={})


# ---------------------------------------------------------------------------------------------------------- one point

def make_context(env, record, export, view, gnodes, names):
    """A `Document` as `MetadataProducer.produce` makes it for the gold side alone (the mutant is the gold)."""
    doc = env.renderer['Document']
    ctx = doc.__new__(doc)
    ctx.legacy_body_context = None
    ctx.r = record
    ctx.gexport = ctx.mexport = export
    ctx.names = names
    ctx.gnodes = gnodes
    ctx.body = view
    ctx.owner = view['owner_path']
    ctx.values = SimpleNamespace(f={'column_names': {}})
    return ctx


def gold_table(env, case, ctx, record, ntrain, point_name_):
    """The public G packet of a point: `acquire_train_point(side='gold')` for the kinds but Det, and
    `acquire_det_train_point(side='gold')` with the certified reader-header union for Det. A Det whose BODY has
    no column takes the read columns from the DET relation's own table (`relation_gold_table`)."""
    import copy
    from evaluator_train import acquire_train_table
    from gold_body import projection, projection_fields
    from judge3.dataset_format import table_packet
    from tables import Incomplete
    session = case.session
    body = session.body(record['point'])
    reader, table = body['native']['_native_reader'], body['table']
    view = ctx.body
    ctx.readers = {'gold': reader}
    # The physical columns bind to the labels through the native correspondence, as the normalized-gold BODY does:
    # a name match of the native table's labels against the AST's would fail where the two spell a label alike.
    raw = body['packed'].body_schema(session.self_correspondence, table, body_path=view['body_path'])
    for field in raw:
        ctx.values.f['column_names'][field['source_label']] = field['display_name']
    if view['kind'] == 'Det' and not raw:
        relation = relation_gold_table(env, case, ctx, view, point_name_)
        if relation is not None:
            return relation
    if view['kind'] == 'Det':
        projected = det_projection(env, ctx, record, raw, view)
    else:
        present = {c['ast_label_id'] for c in raw}
        missing = [label for label in view['group_key_label_ids'] if label not in present]
        if missing:
            raise Incomplete(f'gold INIT input {view["body_path"]}: outer key LabelIds {missing} are absent from '
                             'the BODY; the complete correlated key+port tuple requires the evaluator INIT-context adapter')
        projected, _, _ = ctx.target_projection(reader, [dict(c, source_body_column=c['index'], callable_row_path=None)
                                                         for c in raw], {}, body_side='gold')
    fields = []
    for c in projected:
        field = dict(physical_index=c['index'], field_name=c['display_name'], native_name=c['name'],
                     native_label_identity=c['native_label_identity'], type=c['type'], frame=c['frame'],
                     callable_row_path=c['callable_row_path'], source_body_column=c['source_body_column'],
                     source_projection=c['source_projection'])
        for key in ('native_legacy_binding', 'native_type'):
            if key in c:
                field[key] = copy.deepcopy(c[key])
        fields.append(field)
    if view['kind'] == 'Det':
        for field in fields:
            if field['source_body_column'] is None:
                evidence = field.get('source_projection', {})
                unit = evidence.get('unit_projection_certificate', {})
                if (field['type'] != 'Unit' or unit.get('schema') != 'mech3-native-unit-projection-v1'
                        or evidence.get('native_header', {}).get('status') != 'declared_without_local_label'):
                    raise Incomplete('DET virtual Unit lacks its native header certificate')
                field['source_projection']['inserted_constant'] = dict(kind='unit', native_certificate=unit)
    binding = dict(side='gold', kind=view['kind'], body_path=view['body_path'], owner_path=view['owner_path'],
                   scope=view['scope'], projected_schema=fields)
    indices = projection(body, record, binding)
    fields = projection_fields(body, binding, indices)
    packet = acquire_train_table(body['ev'], body['native'], body['table'], record, ntrain=ntrain, fields=fields,
                                 projection=indices, held_entries=body['held_entries'], source=dict(side='gold'),
                                 copy_rows=False)
    if packet['missing']:
        raise Incomplete('original gold BODY lacks required kept TRAIN entries')
    public = table_packet(packet, table_id='G', source_name=point_name_, case=record['case'], roles=['target'],
                          callable_atom=None, copy_rows=False, sort_rows=True)
    public['side'] = 'gold'
    return public


def relation_gold_table(env, case, ctx, view, point_name_):
    """The G of a Det whose BODY has no column, such as `(DET &tile_d4 TileD4)`: its lib proposer gives its rows.
    The readers' header union, placed by `relation_field` at the physical columns of the DET relation, projects the
    case's own native table of that relation, with the kept assignments of the case. None where no reader names a
    column: the BODY's projection on no column is then the G."""
    from definition_binding import definition_node
    from evaluator_train import _projector
    from judge3.dataset_format import table_packet
    from mech3.reader_projection import side_readers, reader_header_union, relation_field, compatible
    from tables import Incomplete
    binding = dict(kind='Det', body_path=view['body_path'], owner_path=view['owner_path'], projected_schema=[])
    readers = side_readers(ctx.gexport, binding, view['body_path'], field=relation_field)
    columns = reader_header_union(list(readers.values()))
    if not columns:
        return None
    owner = next(n for n in ctx.gexport['nodes'] if n['path'] == view['owner_path'])
    definition, = [d for d in ctx.gexport['definitions']['native_relations'] if d['relation'] == owner['data']['defines']]
    node = definition_node(ctx.gexport, definition)
    found = [i for i in range(len(case.bundle['tables']))
             if any(definition_node(case.export, d) == node for d in case.meta(i)['definitions'])]
    if len(found) != 1:
        raise Incomplete('Det without BODY columns lacks one native table of its relation')
    packet = case.bundle['tables'][found[0]]['table']
    if packet is None or packet['missing']:
        raise Incomplete('native table of the Det relation lacks required kept TRAIN entries')
    witnesses = definition['column_witnesses']
    if ([w['physical_column'] for w in witnesses] != list(range(len(packet['fields'])))
            or not all(compatible(f['type'], w['type']) for f, w in zip(packet['fields'], witnesses))):
        raise Incomplete('native table of the Det relation differs from its native header layout')
    indices = [c['header_physical_column'] for c in columns]
    project = _projector()
    entries = [dict(e, rows=project(dict(entries=[dict(e, example=e['example_index'], choice=None)]), indices)[0]['rows'])
               for e in packet['entries']]
    fields = [dict(field_name=env.renderer['column_text'](c['row_path'], 'role'), type=c['type'],
                   frame=packet['fields'][c['header_physical_column']].get('frame', ''), callable_row_path=c['row_path'])
              for c in columns]
    public = table_packet(dict(packet, fields=fields, entries=entries), table_id='G', source_name=point_name_,
                          case=case.name, roles=['target'], callable_atom=None, copy_rows=False, sort_rows=True)
    public['side'] = 'gold'
    return public


def det_projection(env, ctx, record, raw, view):
    """The DET header union that the point's readers name (`mech3.det_receipt`), as `project_header_union` gives it."""
    import copy
    from mech3.reader_projection import side_readers, reader_header_union
    from det_metadata import project_header_union
    binding = dict(kind='Det', body_path=view['body_path'], owner_path=view['owner_path'],
                   source_body_schema=copy.deepcopy(raw),
                   projected_schema=[dict(c, source_body_column=c['index']) for c in raw])
    readers = side_readers(ctx.gexport, binding, view['body_path'])
    columns = reader_header_union(list(readers.values()))
    return project_header_union(raw, columns, body_path=view['body_path'], column_text=env.renderer['column_text'])


# ---------------------------------------------------------------------------------------------------------- one case

class Case:
    """The program of one case, its native sessions and its table inventory."""

    def __init__(self, env, task, name, ids, model, sess, ntrain, ntest, train_text, corpus, offset_of):
        self.env, self.task, self.name = env, task, name
        self.ntrain, self.ntest = ntrain, ntest
        arclog = env.arclog
        program = arclog.StudyProgram.from_stream(sess, ids, model)
        self.text = program.sexp()
        self.names = json.loads(program.relation_source_names_json(str(corpus), task, name))
        self.points = []
        seen = set()
        for p in program.points():
            path = list(p.body_path)
            if tuple(path) not in seen:
                seen.add(tuple(path))
                self.points.append((p.kind, path))
        self.offset_of = offset_of
        self.record = dict(task=task, case=name, point=[0], gold_sexp=self.text, mutant_sexp=self.text,
                           programs=dict(gold=self.text, mutant=self.text), relation_source_names=self.names,
                           audit=dict(outside_atoms_unchanged=True))
        self.session = None
        self.bundle = None
        self.templates = {}

    def prepare(self):
        """Gold's kept assignments, the case's tables and the gold session; raises where the case cannot give them."""
        from evaluator_train import acquire_case_train
        from tables import Incomplete
        env = self.env
        acquired = env.ev.acquire_gold_kept(self.record, case=self.name, program=self.text)
        if acquired['engine'] != 'ran':
            raise Incomplete('case own gold kept acquisition: ' + str(acquired['reason']))
        self.record['evaluation'] = dict(kept_assignments=acquired['kept_assignments'])
        context = dict(name=self.name, source_program=self.text, relation_source_names=self.names,
                       kept_assignments=acquired['kept_assignments'])
        self.bundle = acquire_case_train(env.ev, self.record, context, self.ntrain, self.ntest)
        if not self.bundle['native_table_inventory_complete']:
            observation = self.bundle.get('receipt', {}).get('observation', {})
            reasons = [g['reason'] for g in self.bundle.get('gaps', []) if g.get('kind') == 'replay' and g.get('reason')]
            raise Incomplete('fresh case replay incomplete: ' + self.name + '; '
                             + ('; '.join(reasons) or observation.get('engine', 'native capture unavailable')))
        self.export = self.bundle['export']
        self.gexport = env.producer.programs.load(self.text, self.record)[1]
        self.gnodes = {tuple(n['path']): n for n in self.gexport['nodes']}
        self.name_policy = env.renderer['Names'](self.gexport)
        self.base_count = self.offset_of(self)
        self.metas = {}
        self.session = GoldSession(env, self.record, self.text)

    def close(self):
        if self.session is not None:
            self.session.close()
            self.session = None
        # The task keeps every case, for the table counts of the cases after it; these are the large parts.
        self.bundle = self.export = self.gexport = self.gnodes = self.name_policy = self.feature_program = None
        self.metas, self.templates = {}, {}
        self.record.pop('evaluation', None)

    def meta(self, i):
        if i not in self.metas:
            try:
                self.metas[i] = (self.env.producer.case_table_metadata(self.export, self.bundle['tables'][i]), None)
            except Exception as error:
                self.metas[i] = (None, error)
        value, error = self.metas[i]
        if error is not None:
            raise error
        return value


def build_point(env, case, kind, point, dest, libraries, blobs, link, scheme):
    """Write the directory of one point to `dest.building` and rename it."""
    from definition_binding import definition_node
    from judge3.dataset_format import FORMAT, table_packet, table_summary
    from feature_payload import point_payload
    from tables import Incomplete
    producer, ev = env.producer, env.ev
    record = dict(case.record, point=point)
    views = [v for v in case.gexport['body_views'] if v['body_path'] == point]
    if len(views) != 1:
        raise ValueError('exact source body path unavailable or ambiguous')
    view = views[0]
    if view['kind'] != kind:
        raise ValueError(f'point kind {kind} differs from its body view kind {view["kind"]}')
    ctx = make_context(env, record, case.gexport, view, case.gnodes, case.name_policy)
    ctx.availability = ctx.dependency_scope()
    independent = set(ctx.availability['independent_nodes'])
    source_name = producer.point_source_name(case.gexport, view)
    tmp = dest.with_name(dest.name + '.building')
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / 'tables').mkdir(parents=True)

    def put(path, data):
        """Write bytes; the same bytes of the same task share one file."""
        if link:
            key = hashlib.sha1(data).hexdigest()
            blob = blobs / key
            if not blob.exists():
                write_bytes(blob, data)
            try:
                os.link(blob, path)
                return
            except OSError:
                pass
        write_bytes(path, data)

    index = []

    def add(public, path):
        index.append(table_summary(public, path))

    # G
    g = gold_table(env, case, ctx, record, case.ntrain, source_name)
    gpath = 'tables/G.json'
    put(tmp / gpath, (dumps(g) + '\n').encode())
    add(g, gpath)
    # the available tables
    count = case.base_count
    facts = set()
    binding = dict(body_path=view['body_path'], owner_path=view['owner_path'])
    for i, item in enumerate(case.bundle['tables']):
        meta = case.meta(i)
        ts = {k: [v] for k, v in item['selector'].items()}
        eligible = env.selectors['same_case_after'](ts, 0, binding, case.export)
        if eligible is None:
            raise ValueError('canonical same-case source order unavailable: ' + item['table_id'])
        allowed = item['selector']['fact'] in ('ex_input', 'ex_output')
        for definition in meta['definitions']:
            if definition_node(case.export, definition) in independent:
                allowed = True
        if not eligible and not allowed:
            continue
        roles = (['target'] if eligible else []) + (['available'] if allowed else [])
        table_id = 'T' + str(count)
        count += 1
        if not allowed:
            continue
        if item['table'] is None:
            raise ValueError('fresh table unavailable: ' + str(item.get('reason')))
        template = case.templates.get(i)
        if template is None:
            fields = [dict(field, field_name=bound['display_name'])
                      for field, bound in zip(item['table']['fields'], meta['schema'])]
            if len(fields) != len(item['table']['fields']):
                raise ValueError('canonical metadata schema width differs')
            packet = dict(item['table'], fields=fields)
            public = table_packet(packet, table_id='T?', source_name=meta['source_name'], case=case.name, roles=[],
                                  callable_atom=meta['callable_atom'], copy_rows=False, sort_rows=True)
            public.update({k: meta[k] for k in ('body_path', 'body_kind') if k in meta})
            rest = {k: v for k, v in public.items() if k not in ('format', 'kind', 'id', 'source_name', 'case', 'roles')}
            template = case.templates[i] = (public, dumps(rest)[1:])
        public, tail = template
        head = ('{"format":' + dumps(public['format']) + ',"kind":"table","id":' + dumps(table_id) + ',"source_name":'
                + dumps(public['source_name']) + ',"case":' + dumps(public['case']) + ',"roles":' + dumps(roles) + ',')
        path = 'tables/' + table_id + '.json'
        put(tmp / path, (head + tail + '\n').encode())
        add(dict(public, id=table_id, roles=roles), path)
        if item['selector']['fact']:
            facts.add(item['selector']['fact'])
        if item['input'] is not None:
            key = ('input', i)
            if key not in case.templates:
                inp = item['input']
                atom = env.renderer['Document'].callable_atom(
                    object(), [dict(f, display_name=f['name']) for f in inp['fields']], 'input')
                public = table_packet(inp, table_id='input', source_name='input', case=case.name, roles=['available'],
                                      callable_atom=atom, copy_rows=False, sort_rows=True)
                case.templates[key] = (public, (dumps(public) + '\n').encode())
            public, data = case.templates[key]
            put(tmp / 'tables/input.json', data)
            add(public, 'tables/input.json')
            facts.add('input')
    if not {'input', 'ex_input', 'ex_output'} <= facts:
        raise ValueError('fresh dataset lacks required available input facts')
    names = case.name_policy
    put(tmp / 'gold.arclog', (names.text(case.text) + '\n').encode())
    put(tmp / 'train.json', case.train_bytes)
    put(tmp / 'libraries.json', libraries)
    native = json.loads(env.arclog.study_feature_metadata_json(case.feature_program, point))
    native['x_nf4f_v1'] = None
    payload = {key: native[key] for key in ('types_frames_v1', 'canonical_clauses_v1', 'x_nf4f_v1')}
    info = dict(format=FORMAT, kind='features-point', task=case.task, case=case.name, point=point, tables=index,
                programs=dict(gold='gold.arclog'), train='train.json', libraries='libraries.json',
                **point_payload(payload))
    put(tmp / 'point.json', (dumps(info) + '\n').encode())
    tmp.rename(dest)


# ---------------------------------------------------------------------------------------------------------- one task

def read_task(cfg, task):
    path = Path(cfg.tasks_dir) / (task + '.json')
    return path, json.loads(path.read_text())


def catalogue(env, cfg, task, task_text):
    """[(case, ids, model)] as `model/export.py` keeps them, and [(case, reason)] of the streams it drops."""
    import numpy as np
    # --step-cap: the replay stops after that many model steps, and each later stream gets a mask fault (dropped below)
    cap = dict(step_cap=cfg.step_cap) if getattr(cfg, 'step_cap', 0) else {}
    streams, faults = env.arclog.corpus_streams(str(cfg.gen), all_cases=True, task_ids=[task], tasks=str(cfg.tasks_dir),
                                                **cap)
    dropped = [('', f) for f in faults]
    kept, seen = [], set()
    for s in streams:
        if s.mask_fault is not None:
            dropped.append((s.case, 'mask fault: ' + str(s.mask_fault)))
            continue
        ids = tuple(np.frombuffer(s.ids, np.uint32).tolist())
        model = tuple(np.frombuffer(s.model, np.uint8).astype(bool).tolist())
        if (ids, model) in seen:
            dropped.append((s.case, 'duplicate stream'))
            continue
        seen.add((ids, model))
        kept.append((s.case, list(ids), [int(m) for m in model]))
    kept.sort(key=lambda r: r[0])
    return kept, dropped


def build_task(env, cfg, task):
    """Build the missing points of one task. Returns the task's summary."""
    from evaluator import sha
    t0 = time.time()
    out = Path(cfg.out)
    summary = dict(task=task, built=0, skipped=0, failed=0, cases=0, errors=[], points=[], dropped_cases=[])

    def fail(error, n=1, **where):
        """Count n failed points, and log the error to the summary and to <cache>/failures-live.jsonl."""
        summary['failed'] += n
        e = dict(where, error=f'{type(error).__name__}: {error}', trace=traceback.format_exc(limit=6))
        summary['errors'].append(e)
        with open(Path(cfg.cache) / 'failures-live.jsonl', 'a') as live:
            live.write(json.dumps(dict(task=task, pid=os.getpid(), **e)) + '\n')
    if getattr(cfg, 'table_max_cells', 0):
        import evaluator_train
        evaluator_train.TRAIN_TABLE_MAX_CELLS = cfg.table_max_cells
    path, task_data = read_task(cfg, task)
    ntrain, ntest = len(task_data['train']), len(task_data['test'])
    train_bytes = (dumps(task_data['train']) + '\n').encode()
    cases, dropped = catalogue(env, cfg, task, task_data)
    summary['dropped_cases'] = dropped
    arclog = env.arclog
    bound = dict(session_bytes=cfg.session_mib << 20) if getattr(cfg, 'session_mib', 0) else {}
    sess = arclog.Session(arclog.Task.from_json(path.read_text(), arclog.World.Closed), **bound)
    blobs = Path(cfg.cache) / 'blobs' / (task + '.' + str(os.getpid()))
    shutil.rmtree(blobs, ignore_errors=True)
    blobs.mkdir(parents=True)
    # Case objects first (their points name the directories), then the table counts of the cases before each.
    built = []
    if not cases:
        # The checker refuses every case of the task: nothing to build, and a finished task does not change.
        summary['refused'] = dropped
    for name, ids, model in cases:
        try:
            built.append(Case(env, task, name, ids, model, sess, ntrain, ntest, None, cfg.gen, None))
        except Exception as error:
            fail(error, case=name)
    counts = {}
    prepare_failed = 0

    def table_count(case):
        """Original-table count of the cases before `case` in the catalogue, as export_target numbers the Tn."""
        from evaluator_train import dependency_receipt  # noqa: F401
        from export_dataset import _case_table_count
        total = 0
        for other in built:
            if other is case:
                return total
            if other.name not in counts:
                context = dict(name=other.name, source_program=other.text, relation_source_names=other.names)
                counts[other.name] = _case_table_count(env.ev, case.record, context)
            total += counts[other.name]
        return total

    for case in built:
        case.offset_of = table_count
        case.train_bytes = train_bytes
    try:
        for case in built:
            wanted = [(k, p) for k, p in case.points if k in cfg.kinds]
            if cfg.max_points:
                wanted = wanted[:cfg.max_points]
            todo = []
            for kind, point in wanted:
                dest = out / point_name(task, case.name, point, cfg.ids)
                if cfg.names is not None and dest.name not in cfg.names:
                    continue
                summary['points'].append([case.name, point, kind, dest.name])
                if dest.exists():
                    summary['skipped'] += 1
                else:
                    todo.append((kind, point, dest))
            if not todo:
                continue
            summary['cases'] += 1
            if prepare_failed >= PREPARE_GIVE_UP and not summary['built']:
                summary['failed'] += len(todo)
                continue
            try:
                case.prepare()
                case.feature_program = env.producer.programs.load(case.text, case.record)[0]
                libraries = (dumps(env.ev.registry_interfaces(case.record)['entries']) + '\n').encode()
            except Exception as error:
                fail(error, len(todo), case=case.name)
                prepare_failed += 1
                if prepare_failed == PREPARE_GIVE_UP and not summary['built']:
                    fail(RuntimeError(f'the first {PREPARE_GIVE_UP} cases failed in preparation; '
                                      'the other cases are skipped'), 0, case=case.name)
                case.close()
                env.clean_scratch()
                continue
            try:
                for kind, point, dest in todo:
                    try:
                        build_point(env, case, kind, point, dest, libraries, blobs, cfg.link, cfg.ids)
                        summary['built'] += 1
                        if env.on_point:
                            env.on_point()
                    except Exception as error:
                        shutil.rmtree(dest.with_name(dest.name + '.building'), ignore_errors=True)
                        fail(error, case=case.name, point=point, kind=kind)
            finally:
                case.close()
                env.clean_scratch()
    finally:
        shutil.rmtree(blobs, ignore_errors=True)
        env.ev.close()
    summary['seconds'] = round(time.time() - t0, 2)
    return summary


# ---------------------------------------------------------------------------------------------------------- the run

def worker(wid, cfg, tasks, results):
    os.environ['ARCLOG_THREADS'] = '1'
    try:
        env = Env(cfg)
    except BaseException:
        results.put(('dead', wid, None, traceback.format_exc()))
        return
    # The main process sets a task aside when it has built no point for --stall seconds
    env.on_point = (lambda: results.put(('point', wid, None, time.time()))) if getattr(cfg, 'stall', 0) else None
    done = 0
    while True:
        if cfg.recycle and done >= cfg.recycle:
            return  # exit code 0: the main process starts a fresh worker, which frees what this one holds
        task = tasks.get()
        if task is None:
            return
        done += 1
        results.put(('start', wid, task, time.time()))
        try:
            results.put(('done', wid, task, build_task(env, cfg, task)))
        except BaseException:
            results.put(('fail', wid, task, traceback.format_exc()))
            env.clean_scratch()


def eta(seconds):
    seconds = int(seconds)
    return f'{seconds // 3600}h{seconds % 3600 // 60:02d}m' if seconds >= 3600 else f'{seconds // 60}m{seconds % 60:02d}s'


def run(cfg):
    cache = Path(cfg.cache)
    for sub in ('done', 'scratch', 'blobs'):
        (cache / sub).mkdir(parents=True, exist_ok=True)
    Path(cfg.out).mkdir(parents=True, exist_ok=True)
    cfg.run_json = str(cache / 'run.json')
    Path(cfg.run_json).write_text(json.dumps(dict(tasks=str(Path(cfg.tasks_dir).resolve()), work_cap=1048576,
                                                  session_mib=getattr(cfg, 'session_mib', 0) or 512, deadline=1.0)))
    tasks = [t.strip() for t in Path(cfg.tasks).read_text().split() if t.strip()] if cfg.tasks else sorted(
        p.name[:-len('.arcdata')] for p in Path(cfg.gen).glob('*.arcdata'))
    for sub in ('scratch', 'blobs'):  # leftovers of a run that was killed
        shutil.rmtree(cache / sub, ignore_errors=True)
        (cache / sub).mkdir()
    absent = [t for t in tasks if not (Path(cfg.gen) / (t + '.arcdata')).exists()]
    aside_path = cache / 'set-aside.txt'
    aside = set(aside_path.read_text().split()) if (cfg.stall or cfg.task_gib) and aside_path.exists() else set()
    todo = [t for t in tasks if t not in absent and t not in aside and not (cache / 'done' / (t + '.json')).exists()]
    if aside:
        print(f'{len([t for t in tasks if t in aside])} tasks set aside in {aside_path} (skipped)', flush=True)
    print(f'{len(tasks)} tasks, {len(absent)} not in the corpus yet (skipped), {len(tasks) - len(absent) - len(todo)} done, '
          f'{len(todo)} to build; workers={cfg.workers}', flush=True)
    if not todo:
        return 0
    ctx = multiprocessing.get_context('spawn')
    taskq, results = ctx.Queue(), ctx.Queue()
    for t in todo:
        taskq.put(t)
    procs = {}

    def spawn(wid):
        procs[wid] = ctx.Process(target=worker, args=(wid, cfg, taskq, results), daemon=True)
        procs[wid].start()
    for wid in range(min(cfg.workers, len(todo))):
        spawn(wid)
    running, finished, started = {}, 0, time.time()
    progress, checked = {}, time.time()  # worker -> time of its task's start or last built point

    def worker_gib():
        """Memory of each worker as top reports it (resident plus compressed), in GiB."""
        pids = {p.pid: wid for wid, p in procs.items()}
        out = subprocess.run(['top', '-l', '1', '-stats', 'pid,mem'], capture_output=True, text=True).stdout
        gib = {}
        for line in out.splitlines():
            f = line.split()
            if len(f) == 2 and f[0].isdigit() and int(f[0]) in pids:
                m = f[1].rstrip('+-')
                unit = {'K': 2**-20, 'M': 2**-10, 'G': 1}.get(m[-1:], 2**-30)
                gib[pids[int(f[0])]] = float(m.rstrip('KMGB') or 0) * unit
        return gib

    def set_aside():
        """Stop each task that stalls or holds too much memory, list it in set-aside.txt, and give its worker a new
        process. Returns the number of tasks stopped."""
        gib = worker_gib() if cfg.task_gib else {}
        stopped = 0
        for wid, (task, _) in list(running.items()):
            idle = time.time() - progress.get(wid, time.time())
            if cfg.stall and idle > cfg.stall:
                why = f'no point built for {idle:.0f}s'
            elif cfg.task_gib and gib.get(wid, 0) > cfg.task_gib:
                why = f'worker holds {gib[wid]:.1f} GiB'
            else:
                continue
            procs[wid].terminate()
            procs[wid].join(timeout=30)
            running.pop(wid)
            with open(aside_path, 'a') as f:
                f.write(task + '\n')
            print(f'set aside {task}: {why}', flush=True)
            stopped += 1
            spawn(wid)
        return stopped
    totals = collections.Counter()
    failures = open(cache / 'failures.jsonl', 'a')
    last = time.time()
    seconds = []
    failed_tasks = 0
    while finished < len(todo):
        if (cfg.stall or cfg.task_gib) and time.time() - checked > 30:
            checked = time.time()
            finished += set_aside()
            if finished >= len(todo):
                break
        try:
            kind, wid, task, value = results.get(timeout=5)
        except queue.Empty:
            kind = None
        # The workers are checked at each message, not only when the queue is quiet: with --stall, points come so often
        # that a recycled worker would wait long for its new process
        for w, proc in list(procs.items()):
            if not proc.is_alive() and proc.exitcode == 0 and w not in running and finished < len(todo):
                spawn(w)  # a recycled worker
                continue
            if not proc.is_alive() and proc.exitcode not in (0, None):
                lost = running.pop(w, None)
                print(f'worker {w} died with {proc.exitcode} on {lost and lost[0]}', flush=True)
                if lost is not None:
                    failures.write(json.dumps(dict(task=lost[0], error=f'worker died with exit code {proc.exitcode}')) + '\n')
                    failures.flush()
                    finished += 1
                    failed_tasks += 1
                spawn(w)
        if time.time() - last > 60:
            last = time.time()
            busy = ' '.join(f'{t}:{int(time.time() - s)}s' for t, s in running.values())
            print(f'... {finished}/{len(todo)} tasks, running {busy}', flush=True)
        if kind is None:
            continue
        if kind == 'start':
            running[wid] = (task, value)
            progress[wid] = value
            continue
        if kind == 'point':
            progress[wid] = value
            continue
        if kind == 'dead':
            print(f'worker {wid} could not start:\n{value}', flush=True)
            return 1
        if running.get(wid, (None,))[0] != task:
            continue  # the result of a task that was set aside as it ended
        running.pop(wid, None)
        finished += 1
        if kind == 'fail':
            failed_tasks += 1
            failures.write(json.dumps(dict(task=task, error=value)) + '\n')
            print(f'FAILED {task}: {value.strip().splitlines()[-1]}', flush=True)
        else:
            totals.update(built=value['built'], skipped=value['skipped'], failed=value['failed'])
            for e in value['errors']:
                failures.write(json.dumps(dict(task=task, **e)) + '\n')
            # A task that the checker refuses is tried again at the next run: the engine decides it, not the corpus.
            if not value['errors'] and not value.get('refused'):
                (cache / 'done' / (task + '.json')).write_text(json.dumps(dict(
                    {k: v for k, v in value.items() if k not in ('errors',)})))
            seconds.append(value['seconds'])
            if value.get('refused'):
                print(f'{task} refused by the checker (no stream)', end=' ')
            print(f'{task} built={value["built"]} skipped={value["skipped"]} failed={value["failed"]} '
                  f'in {value["seconds"]:.1f}s', end=' ', flush=True)
        failures.flush()
        now = time.time() - started
        rate = finished / now
        print(f'| {finished}/{len(todo)} tasks, {rate * 60:.2f} tasks/min, points built={totals["built"]} '
              f'failed={totals["failed"]}, ETA {eta((len(todo) - finished) / rate)}', flush=True)
        free = shutil.disk_usage(cfg.out).free / 2**30
        if free < MIN_FREE_GB:
            print(f'stopped: {free:.1f} GB free', flush=True)
            for p in procs.values():
                p.terminate()
            return 2
    for _ in procs:
        taskq.put(None)
    for p in procs.values():
        p.join(timeout=30)
    shutil.rmtree(cache / 'scratch', ignore_errors=True)
    print(f'finished: {len(todo)} tasks in {eta(time.time() - started)}, points built={totals["built"]} '
          f'skipped={totals["skipped"]} failed={totals["failed"]}, task failures={failed_tasks}', flush=True)
    return 1 if failed_tasks or totals['failed'] else 0


# ---------------------------------------------------------------------------------------------------------- compare

def compare(old, new, names=None):
    """File-by-file comparison of the point directories that both roots hold (same names)."""
    old, new = Path(old), Path(new)
    rows = collections.Counter()
    differing = collections.defaultdict(list)
    shared = sorted(p.name for p in new.iterdir() if (p / 'point.json').exists() and (old / p.name / 'point.json').exists())
    for name in shared:
        a, b = old / name, new / name
        files = sorted({str(f.relative_to(a)) for f in a.rglob('*') if f.is_file()}
                       | {str(f.relative_to(b)) for f in b.rglob('*') if f.is_file()})
        for f in files:
            if not (a / f).exists():
                rows[f, 'only new'] += 1
                differing[f].append((name, 'only new'))
            elif not (b / f).exists():
                rows[f, 'only old'] += 1
                differing[f].append((name, 'only old'))
            elif (a / f).read_bytes() == (b / f).read_bytes():
                rows[f.split('/')[0] if f.startswith('tables/') and f != 'tables/G.json' else f, 'equal'] += 1
            else:
                rows[f.split('/')[0] if f.startswith('tables/') and f != 'tables/G.json' else f, 'differs'] += 1
                differing[f].append((name, 'differs'))
    print(len(shared), 'points in both')
    for (f, state), n in sorted(rows.items()):
        print(f'{f:24} {state:10} {n}')
    return differing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('corpus', help='the corpus directory: <gen>/<task>.arclog, or a directory that holds gen/')
    ap.add_argument('out', help='the points root')
    ap.add_argument('--tasks', help='file with one task id per line; the tasks are built in that order '
                                    '(default: every task of the corpus, sorted)')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--step-cap', type=int, default=0, metavar='N',
                    help="stop each task's stream replay after N model steps; the later cases are dropped (default: no cap)")
    ap.add_argument('--session-mib', type=int, default=0, metavar='N',
                    help="bound each task's sessions at N MiB of charged bytes (default: 512)")
    ap.add_argument('--table-max-cells', type=int, default=0, metavar='N',
                    help='the most cells of a train table the features read (default: 524288)')
    ap.add_argument('--stall', type=float, default=0, metavar='S',
                    help='set aside a task that builds no point for S seconds (default: no limit)')
    ap.add_argument('--task-gib', type=float, default=0, metavar='G',
                    help='set aside a task whose worker holds more than G GiB (default: no limit)')
    ap.add_argument('--recycle', type=int, default=0, metavar='N',
                    help='a worker exits after N tasks and a fresh one takes its place, which frees memory it holds')
    ap.add_argument('--cache', help='cache directory (default: <out>.cache)')
    ap.add_argument('--tasks-dir', default=str(REPO / 'data/tasks'))
    ap.add_argument('--kinds', default=','.join(KINDS), help='comma-separated point kinds (default: %(default)s)')
    ap.add_argument('--ids', choices=('old', 'stream'), default='old',
                    help="directory names: 'old' is task-sha256([case, point])[:12], what the old store holds; "
                         "'stream' is stream_export.point_id, task-sha256([task, case, point])[:16]")
    ap.add_argument('--no-link', dest='link', action='store_false',
                    help='write every file in full; by default the identical files of one task (libraries.json, '
                         'the available tables of a case) are hard links of one file')
    ap.add_argument('--deadline', type=float, default=30, help='seconds per native operation (the old exporter used 30)')
    ap.add_argument('--max-points', type=int, default=0, help='testing: at most this many points of each case')
    ap.add_argument('--names', metavar='FILE', help='testing: build only the points whose directory names the file '
                                                   'holds (one per line); the cases still decode in full')
    ap.add_argument('--compare', metavar='OLD', help='compare the directories of <out> with those of OLD and exit')
    cfg = ap.parse_args()
    if cfg.compare:
        compare(cfg.compare, cfg.out)
        return 0
    cfg.gen = resolve_corpus(cfg.corpus)
    cfg.out = str(Path(cfg.out).resolve())
    cfg.cache = str(Path(cfg.cache).resolve() if cfg.cache else Path(cfg.out + '.cache'))
    cfg.kinds = set(cfg.kinds.split(','))
    cfg.names = set(Path(cfg.names).read_text().split()) if cfg.names else None
    return run(cfg)


if __name__ == '__main__':
    sys.exit(main())

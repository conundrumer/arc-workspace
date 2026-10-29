"""Source-record metadata, without rendering, row decoding, evaluation or writes.

Call MetadataProducer(engine=..., read_native=..., corpus=...).produce(record).
read_native(reference, native_base) is the caller's EXISTING stored-native reader
factory; it must return an object exposing tables and schema(table). No entry()
method is used. No pinned renderer/native module is imported into its namespace.
"""
from __future__ import annotations
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import ast
import copy
from collections import OrderedDict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
STUDY = CODE_ROOT


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(value).hexdigest()


def _extract(path, *, functions=(), classes=(), methods=None, namespace=None):
    """Load exact trusted producer functions, not a second policy implementation."""
    raw = path.read_bytes()
    tree = ast.parse(raw, str(path)); selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in functions:
            selected.append(node)
        elif isinstance(node, ast.ClassDef):
            if node.name in classes:
                selected.append(node)
            elif methods and node.name in methods:
                node.body = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in methods[node.name]]
                selected.append(node)
    ns = dict(namespace or {})
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), ns)
    return ns, dict(path=str(path.resolve()), sha256=_sha(raw))


@lru_cache(maxsize=1)
def _policy():
    paths = STUDY/'judge2/render2'
    ns = dict(require=_require, json=json, re=re, copy=copy,
              compact=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
    columns, p1 = _extract(paths/'column_paths.py', functions=('key','text'), namespace=ns)
    ns.update(column_key=columns['key'], column_text=columns['text'])
    headers, p2 = _extract(paths/'headers.py', functions=('bind_body_schema',), namespace=ns)
    project, p3 = _extract(paths/'body.py', functions=('project_entries',), namespace=ns)
    ns.update(bind_body_schema=headers['bind_body_schema'], project_entries=project['project_entries'])
    renderer, p4 = _extract(ROOT/'render_pair.py', functions=('under','real_paths'), classes=('Names',),
        methods={'Document':('schema','target_projection','callable_atom','dependency_scope','definition_node')},
        namespace=dict(ns, S=STUDY, DATA_ROOT=DATA_ROOT, MAIN_ROOT=MAIN_ROOT))
    # dependency_scope uses the exact renderer under() helper.
    renderer['Document'].dependency_scope.__globals__['under'] = renderer['under']
    programs, p5 = _extract(paths/'structured.py', methods={'Programs':('source_names','load')}, namespace=dict(ns, MAIN_ROOT=MAIN_ROOT))
    selectors, p6 = _extract(ROOT/'catalog.py', functions=('matches','same_case_after','definition_after','fields'), namespace=ns)
    return renderer, programs['Programs'], selectors, [p1,p2,p3,p4,p5,p6]


class UnsupportedProjection(ValueError):
    """The exact public projection cannot be acquired through this provider."""


class MetadataProducer:
    """Reusable per-corpus producer. Native AST export only; never a replay.

    engine is the caller's existing arclog module. read_native uses the caller's
    reader/storage namespace. settings, if supplied, only configures AST decode.
    case_inventory may supply the existing catalogue structure instead of
    reading corpus manifest/cases.npz/retained.jsonl. It is never an authority
    for admission, row equality or replay completeness.
    """
    def __init__(self, *, engine, read_native, corpus, settings=None, case_inventory=None):
        self.engine, self.read_native = engine, read_native
        self.corpus = Path(corpus).resolve()
        self.inventory_provider = case_inventory
        renderer, Programs, self.selectors, self.sources = _policy()
        self.policy = renderer
        self.programs = Programs.__new__(Programs)
        self.programs.engine = engine
        self.programs.settings = settings
        self.programs.cache = OrderedDict()
        self.programs.names = OrderedDict()
        self.case_cache = {}

    def _export(self, text, record=None):
        return self.programs.load(text, record)[1]

    def _inventory(self, record):
        task = record['task']; base = self.corpus/task
        if task not in self.case_cache:
            if self.inventory_provider is not None:
                inv = self.inventory_provider(task) if callable(self.inventory_provider) else self.inventory_provider
                self.case_cache[task] = copy.deepcopy(inv)
            else:
                manifest_path = base/'manifest.json'
                raw = manifest_path.read_bytes(); manifest = json.loads(self.policy['real_paths'](raw.decode()))
                path = Path(manifest['config']['export'])/'tasks'/task/'cases.npz'
                # Existing exported catalogue reader, no new NPY decoder.
                import numpy as np
                with np.load(path, allow_pickle=False) as catalogue:
                    names = catalogue['case'].tolist()
                sources = {}; retained = base/'retained.jsonl'
                if retained.exists():
                    with retained.open() as stream:
                        for number, line in enumerate(stream, 1):
                            line = self.policy['real_paths'](line); source = json.loads(line)
                            name = source['case']; full = source.get('full_replay')
                            if name in sources:
                                continue
                            if full is None:
                                continue
                            sources[name] = dict(reference=full, source_program=source.get('programs',{}).get('gold',source.get('gold_sexp')),
                                source_record_data=source,
                                source_record=dict(path=str(retained.resolve()),encoding='jsonl',line=number,sha256=hashlib.sha256(line.encode()).hexdigest()))
                prior = DATA_ROOT/'cross-case/missing.json'; prior_cases = {}
                if prior.exists():
                    prior_cases = {r['task']:r['found'] for r in json.loads(self.policy['real_paths'](prior.read_text()))}.get(task,{})
                self.case_cache[task] = dict(catalogue_path=str(path.resolve()),catalogue_sha256=_sha(path.read_bytes()),
                    catalogue_status='exported population recorded; native provenance/fault authentication pending',
                    corpus_manifest_path=str(manifest_path.resolve()),corpus_manifest_sha256=_sha(raw),
                    corpus_case_limit=manifest['config'].get('case_limit'),corpus_manifest_cases=manifest['cases'],
                    comparison='names ignored; own kept contexts; no cross-case assignment zip or shared Ident namespace',
                    other_case_cutoff='none: every table of every other case is eligible',
                    cases=[dict(name=name,reference=sources.get(name,{}).get('reference',prior_cases.get(name)),
                                source_program=sources.get(name,{}).get('source_program'),
                                source_record=sources.get(name,{}).get('source_record'),
                                source_record_data=sources.get(name,{}).get('source_record_data')) for name in names])
        result = copy.deepcopy(self.case_cache[task])
        for case in result['cases']:
            main = case['name']==record['case']
            case['target_eligibility']='main_case_point_and_later' if main else 'every_table'
            if main:
                case.update(reference=record.get('full_replay'),source_program=record['programs']['gold'],source_record_data=record)
            ev=(case.get('reference') or {}).get('evaluation',{})
            case['kept_assignments']=ev.get('kept_assignments')
            case['gold_assignment_map']=ev.get('gold_assignment_map')
            case['native_base']=str(base)
        return result

    def raw_side_bindings(self, source_record, *, native_base=None):
        """Source-bound two-sided DET BODY metadata; no entries or projection.

        This supplies det_receipt's RAW input, not its selected public header
        union. The caller must certify reader transport before acquisition.
        """
        record=copy.deepcopy(source_record)
        if 'programs' not in record:
            record['programs']={side:record[side+'_sexp'] for side in ('gold','mutant')}
        base=Path(native_base).resolve() if native_base is not None else self.corpus/record['task']
        exports={side:self._export(record['programs'][side], record if side=='gold' else None)
                 for side in ('gold','mutant')}
        readers={side:self.read_native(record['native'][side],base)
                 for side in ('gold','mutant')}
        bindings={}
        for side in ('gold','mutant'):
            export=exports[side];reader=readers[side]
            views=[v for v in export['body_views'] if v['body_path']==record['point']]
            _require(len(views)==1 and views[0]['kind']=='Det',
                     'RAW DET supplier requires one exact DET BODY: '+side)
            view=views[0]
            _require(export['parts'].get('definitions_readers')=='complete',
                     'native reader inventory incomplete: '+side)
            indices=record['evaluation']['table_indices']
            candidates=[indices[k] for k in (side+'_kept',side+'_all') if k in indices]
            _require(bool(candidates),'source lacks exact native point index: '+side)
            table=candidates[0]
            _require(type(table) is int and 0<=table<len(reader.tables['form']),
                     'native point index outside table inventory: '+side)
            _require(self.selectors['matches'](reader.tables,table,view['native_table_selector']),
                     'native point selector differs: '+side)
            ctx=self.policy['Document'].__new__(self.policy['Document'])
            ctx.r=record;ctx.gexport=exports['gold'];ctx.mexport=exports['mutant']
            ctx.readers=readers;ctx.owner=view['owner_path'];ctx.body=view
            ctx.values=SimpleNamespace(f={'column_names':{}})
            raw=ctx.schema(reader,table,body=True)
            fields=[]
            for index,column in enumerate(raw):
                _require(column['index']==index,'RAW native physical order differs: '+side)
                identity=column['native_label_identity']
                if column['type']!='Unit':
                    _require(identity.get('kind')=='scoped_label' and
                             identity.get('scope_path')==view['owner_path'] and
                             identity.get('label_id')==column['ast_label_id'],
                             'RAW scalar lacks exact native lexical identity: '+side)
                fields.append(dict(physical_index=index,field_name=column['display_name'],
                    native_name=column['name'],native_label_identity=copy.deepcopy(identity),
                    type=column['type'],frame=column['frame'],source_body_column=index))
            bindings[side]=dict(side=side,kind='Det',body_path=view['body_path'],
                owner_path=view['owner_path'],scope=view['scope'],
                native_ref=copy.deepcopy(record['native'][side]),native_table_index=table,
                native_selector=copy.deepcopy(view['native_table_selector']),
                source_body_schema=raw,projected_schema=fields,fields=copy.deepcopy(fields),
                projection_kind='raw_identity',program_sha256=_sha(record['programs'][side]),
                export_sha256=_sha(export))
        return dict(schema='judge3-raw-side-bindings-v1',source_sha256=_sha(source_record),
            native_base=str(base),exports=exports,bindings=bindings,
            policies=copy.deepcopy(self.sources),
            authority='metadata only; no selected DET header, rows, acquisition or admission')

    def produce(self, source_record, *, native_base=None):
        """Return canonical side bindings, graph packet and own-case catalogue.

        Unsupported layouts raise ValueError; no guessed fields/Unit aliases.
        Empty projected_entries means NOT ACQUIRED, never an empty relation.
        The caller replays gold once per case and reuses stored X independently.
        """
        r=copy.deepcopy(source_record)
        if 'programs' not in r:
            r['programs']={side:r[side+'_sexp'] for side in ('gold','mutant')}
        base=Path(native_base).resolve() if native_base is not None else self.corpus/r['task']
        ctx=self.policy['Document'].__new__(self.policy['Document'])
        ctx.r=r;ctx.gexport=self._export(r['programs']['gold'],r);ctx.mexport=self._export(r['programs']['mutant'])
        ctx.names=self.policy['Names'](ctx.gexport)
        tokens=set(ctx.names.tokens)|set(ctx.names.tokens.values())
        for export in (ctx.gexport,ctx.mexport):
            tokens.update(t for t in ctx.names.pattern.findall(export['program_sexp']) if t.startswith('&'))
        _require(not tokens.intersection({'&X','&fix'}),'reserved recovery relation collision')
        ctx.gnodes={tuple(n['path']):n for n in ctx.gexport['nodes']}
        views=[v for v in ctx.gexport['body_views'] if v['body_path']==r['point']]
        _require(len(views)==1,'exact source body path unavailable or ambiguous')
        ctx.body=views[0];ctx.owner=ctx.body['owner_path']
        if ctx.body['kind']=='Det':
            raise UnsupportedProjection('DET reader-named compared-column projection unavailable; raw BODY fields are not a substitute')
        ctx.values=SimpleNamespace(f={'column_names':{}})
        ctx.readers={side:self.read_native(r['native'][side],base) for side in ('gold','mutant')}
        ctx.availability=ctx.dependency_scope()
        bindings={}
        for side,reader in ctx.readers.items():
            indexes=r['evaluation']['table_indices']
            candidates=[indexes[k] for k in (side+'_kept',side+'_all') if k in indexes]
            _require(bool(candidates),'source record lacks native point table index: '+side)
            table=candidates[0]
            raw=ctx.schema(reader,table,body=True)
            # Outer key variables are not necessarily outputs of the input
            # BODY. They must be acquired in the original correlated INIT
            # context, never joined to an independently evaluated key table.
            # In particular, None is reserved for a native inserted Unit; it
            # must not stand in for an absent, non-Unit key scalar.
            export=ctx.gexport if side=='gold' else ctx.mexport
            view=next(v for v in export['body_views'] if v['owner_path']==ctx.owner
                      and v['kind']==ctx.body['kind'] and v['input_port']==ctx.body['input_port'])
            present={c['ast_label_id'] for c in raw}
            missing=[label for label in view['group_key_label_ids'] if label not in present]
            if missing:
                raise UnsupportedProjection(
                    f'{side} INIT input {view["body_path"]}: outer key LabelIds {missing} '
                    'are absent from the stored BODY; the complete correlated '
                    'key+port tuple requires the evaluator INIT-context adapter')
            projected,_,view=ctx.target_projection(reader,raw,{})
            fields=[dict(physical_index=c['index'],field_name=c['display_name'],native_name=c['name'],
                native_label_identity=c['native_label_identity'],type=c['type'],frame=c['frame'],
                callable_row_path=c['callable_row_path'],source_body_column=c['source_body_column'],source_projection=c['source_projection']) for c in projected]
            bindings[side]=dict(side=side,body_path=view['body_path'],owner_path=view['owner_path'],scope=view['scope'],
                kind=view['kind'],input_port=view['input_port'],native_ref=r['native'][side],native_table_index=table,
                native_selector=view['native_table_selector'],source_body_schema=raw,projected_schema=fields,fields=fields,
                projected_entries=[],entries_status='not_acquired',
                callable_template=ctx.callable_atom(projected,'&X'),
                init_projection=copy.deepcopy(view['input_port_projection']),group_key_label_ids=view['group_key_label_ids'],
                input_port_columns=copy.deepcopy(view['input_port_columns']),owner_native_data=ctx.gnodes[tuple(ctx.owner)]['data'],
                key_declaration=(ctx.gnodes[tuple(view['body_path'][:-1])]['data'] if view['kind']=='INIT key' else None))
        gaps=[];definitions=[]
        for d in ctx.gexport['definitions']['native_relations']:
            try:
                node=ctx.definition_node(d)
            except ValueError as error:
                gaps.append(str(error));continue
            if node in ctx.availability['independent_nodes']:
                definitions.append(dict(definition=d,graph_node=node,status='metadata_only',ex_output_dependent=node in ctx.availability['ex_output_dependent_nodes']))
        inventory=self._inventory(r)
        own_kept=r['evaluation'].get('kept_assignments')
        for case in inventory['cases']:
            if case['name']==r['case']:
                case['kept_assignments']=own_kept
        return dict(schema='judge3-source-metadata-v1',status='metadata_only',programs=r['programs'],source_sha256=_sha(source_record),native_base=str(base),
            source=dict(native_base=str(base),source_sha256=_sha(source_record)),
            bindings=bindings,input=dict(handle='&X',side='mutant',binding=bindings['mutant'],fields=bindings['mutant']['fields'],callable_template=bindings['mutant']['callable_template']),
            comparison_target=dict(side='gold',callable=False,binding=bindings['gold'],
                full_replay_body=dict(native_ref=(r.get('full_replay') or {}).get('gold'),native_selector=bindings['gold']['native_selector'],
                    assignment_map=(r.get('full_replay') or {}).get('evaluation',{}).get('gold_assignment_map'),
                    projection_indices=[c['source_body_column'] for c in bindings['gold']['fields']],status='not_acquired')),
            availability=dict(ctx.availability,definitions=definitions,fact_relations=['input','ex_input','ex_output']),
            same_case=dict(body_view=ctx.body,definitions=ctx.gexport['definitions']['native_relations'],
                selectors_source=str((ROOT/'catalog.py').resolve()),gold_export=ctx.gexport),
            all_case_targets=inventory,kept_assignments=own_kept,relation_tokens=ctx.names.tokens,
            readers=dict(gold=ctx.gexport['definitions']['readers'],mutant=ctx.mexport['definitions']['readers'],
                gold_typed_sites=ctx.gexport['typed_sites'],mutant_typed_sites=ctx.mexport['typed_sites']),
            policies=self.sources,gaps=gaps,authority='metadata only; no admission, equality or replay-completeness claim')

    def callable_definition(self, definition, native_schema):
        """Bind an admitted source definition to a stored/fresh native schema.

        No native call, row access, graph selection or second layout policy.
        The caller supplies the definition admitted by availability.definitions;
        this formatting operation does not itself grant read availability.
        """
        _require(bool(definition.get('display_name')), 'definition lacks authenticated source display_name')
        ctx=self.policy['Document'].__new__(self.policy['Document'])
        ctx.values=SimpleNamespace(f={'column_names':{}})
        reader=SimpleNamespace(schema=lambda table: copy.deepcopy(native_schema))
        schema=ctx.schema(reader,0,definition=definition)
        atom=ctx.callable_atom(schema,definition['display_name'],definition)
        return dict(schema=schema,callable_atom=atom,source_name=definition['display_name'],
                    authority='caller-supplied resolver-admitted definition and native schema; no availability granted')

    def case_table_metadata(self, export, item):
        """Source names/schema for an evaluator-owned fresh original table.

        This is formatting only. The caller still uses dependency_scope and
        same_case_after for read/target eligibility. No rows or replay handles
        are accepted here, and native table indices are never transferred.
        """
        selector=item['selector']
        matches=self.selectors['matches']
        tables={k:[v] for k,v in selector.items()}
        reader=SimpleNamespace(schema=lambda _:copy.deepcopy(item['native_schema']),tables=tables)
        ctx=self.policy['Document'].__new__(self.policy['Document'])
        ctx.values=SimpleNamespace(f={'column_names':{}})
        names=self.policy['Names'](export)
        definitions=[d for d in export['definitions']['native_relations']
                     if matches(tables,0,d['native_selector'])]
        if selector['point']==1:
            views=[v for v in export['body_views'] if matches(tables,0,v['native_table_selector'])]
            _require(len(views)==1,'fresh BODY table has no unique canonical source view')
            view=views[0]
            ctx.body=view;ctx.owner=view['owner_path'];ctx.gexport=export
            ctx.readers={'gold':reader}
            schema=ctx.schema(reader,0,body=True)
            source=self.point_source_name(export,view)
            return dict(schema=schema,source_name=source,callable_atom=None,
                        body_path=view['body_path'],body_kind=view['kind'],definitions=[])
        if definitions:
            chosen=[d for d in definitions if d['display_name']==item['source_name']]
            _require(len(chosen)==1,'fresh table source alias is not uniquely authenticated')
            result=self.callable_definition(chosen[0],item['native_schema'])
            return dict(result,definitions=definitions)
        _require(bool(selector['fact']),'fresh non-BODY table has no exported source definition')
        schema=ctx.schema(reader,0)
        return dict(schema=schema,source_name=selector['fact'],
                    callable_atom=ctx.callable_atom(schema,selector['fact']),definitions=[])

    def point_source_name(self, export, view):
        """Exact declared source owner, with the native input port if present."""
        owner=next(n for n in export['nodes'] if n['path']==view['owner_path'])
        identity=owner['data'].get('name') or owner['data'].get('defines',{}).get('name')
        _require(identity is not None,'BODY owner has no exported declared source identity')
        token=('&r'+str(identity['slot']) if identity['kind']=='slot' else identity['name'])
        _require(token.startswith('&'),'BODY written source owner lacks its exact token')
        source=self.policy['Names'](export).text(token)
        if view['input_port'] is not None:source+='.'+view['input_port']
        return source

    def same_case_after(self, tables, index, metadata):
        """Exact existing selector; None remains unresolved, never an ordinal guess."""
        return self.selectors['same_case_after'](tables,index,metadata['same_case']['body_view'],metadata['same_case']['gold_export'])

    def definition_after(self, definition, metadata):
        return self.selectors['definition_after'](definition,metadata['same_case']['body_view'],metadata['same_case']['gold_export'])

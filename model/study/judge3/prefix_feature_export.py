#!/usr/bin/env python3
"""Offline publication of authenticated Prefix-U packets. Never imports arclog.

The input tree contains only independently checked prefix/candidate syntax and
TRAIN X/available values. G and acquisition/source reports stay label/private.
Tn are NEW context-local IDs in native packed available-table order; no legacy
kept-store numbering, model/Ident alignment or relation-name joins are inferred.
"""
import argparse
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_paths import DATA_ROOT
from judge3.paused_storage import read_json, write_gzip_json, sidecar
from judge3.dataset_format import write_json

LAYOUT = 'prefix-u-full-body-train-v1'
POLICY = 'native-prefix-parent-universe-v1'
FIXED_RUNTIME_REVISIONS = frozenset(('f642830734cca0d1003004d1ec07e2ac0b52b358',
    '5f01bf6beec9430bd7f47868da95a0f2fe8fad52'))
# Exact storage-only predecessor; its fixed-f642 input/policy checks are unchanged.
PREDECESSOR_IMPLEMENTATION = '26236cb536b828e27521eb79ce023d8cdcabb1712671a91e8fa4af898c6bdc25'
PREVIEW_LAYOUT = 'recorded-prefix-universe-preview-v1'


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def confined(path):
    path = Path(path).resolve()
    if not path.is_relative_to(DATA_ROOT.resolve()):
        raise ValueError('prefix publication path escapes DATA_ROOT')
    return path


class Evidence:
    """One pair's bounded-lifetime checked metadata; no global value retention."""
    def __init__(self):
        self.refs = []
        self.cache = {}

    def read(self, ref):
        if not isinstance(ref, dict) or not {'path', 'sha256'} <= ref.keys():
            raise ValueError('missing explicit evidence reference')
        path = confined(ref['path']); key = (str(path), ref['sha256'])
        if key in self.cache: return self.cache[key]
        if path.exists():
            if ('bytes' in ref and path.stat().st_size != ref['bytes']) or file_sha(path) != ref['sha256']:
                raise ValueError('prefix evidence file SHA/size differs: ' + str(path))
            if path.suffix == '.gz':
                checksum = sidecar(path)
                if not checksum.is_file(): raise ValueError('gzip evidence lacks original SHA sidecar')
                if ref.get('original_sha_ref'):
                    supplied = ref['original_sha_ref']
                    if confined(supplied['path']) != checksum: raise ValueError('gzip sidecar addresses another file')
                    self.read(supplied)
                value = read_json(path)
            else: value = read_json(path, expected_sha256=ref['sha256'])
        else:
            # Logical native report refs keep their original byte hash after
            # lossless conversion. The shared codec verifies the complete tail.
            confined(path.with_name(path.name + '.gz'))
            value = read_json(path, expected_sha256=ref['sha256'])
        self.refs.append(deepcopy(ref)); self.cache[key] = value
        return value


def reference(path):
    path = confined(path)
    result = dict(path=str(path), sha256=file_sha(path), bytes=path.stat().st_size)
    if path.suffix == '.gz': result['original_sha_ref'] = reference(sidecar(path))
    return result


def native_problem(acquisition, evidence):
    """Retain exact native status/reason; never turn a bound into a negative."""
    report = evidence.read(acquisition['report_ref']) if acquisition.get('report_ref') else {}
    return dict(status=acquisition.get('status'), reason=acquisition.get('reason'),
        native_status=report.get('status'), native_reason=report.get('reason'),
        native_available_status=report.get('available_status'))


def checked_acquisition(value, evidence, side):
    schema = value.get('schema')
    if schema not in ('evaluator-prefix-acquisition-v1', 'study-prefix-compact-acquisition-v1'):
        raise ValueError('unsupported prefix acquisition container')
    if schema == 'study-prefix-compact-acquisition-v1' and value.get('native_packet_schema') != 'evaluator-prefix-acquisition-v1':
        raise ValueError('compact container changed native packet schema')
    receipt = value['receipt']
    if (value.get('policy') != POLICY or value.get('side') != side or
            receipt.get('test_cells') is not False or receipt.get('gold_kept_used') is not False):
        raise ValueError('acquisition lacks native prefix-only TRAIN authority')
    opening = evidence.read(receipt['opening_ref'])
    report = evidence.read(value['report_ref'])
    packed = evidence.read(receipt['packed_acquisition_ref'])
    source = evidence.read(receipt['source_ref'])
    cov = opening.get('coverage', {})
    if (opening.get('schema') != 'arclog-study-prefix-universe-v1' or opening.get('status') != 'complete'
            or cov.get('enumeration_complete') is not True or cov.get('assignment_values_complete') is not True
            or cov.get('parent_count') != len(opening.get('parent_assignments', []))
            or [p.get('parent') for p in opening['parent_assignments']] != list(range(cov['parent_count']))
            or any(p.get('missing_parameters') != [] for p in opening['parent_assignments'])):
        raise ValueError('native common prefix opening incomplete')
    if (report.get('schema') != 'arclog-study-prefix-tables-v1' or report.get('side') != side
            or report.get('status') != 'complete' or report.get('complete') is not True
            or report.get('packing_complete') is not True or report.get('entry_parent_map_complete') is not True
            or report.get('universe_ref') != opening['universe_ref']
            or report.get('universe_coverage') != cov or report.get('body_path') != opening['body_path']
            or report.get('task') != opening['task'] or report.get('query_prefix', {}).get('status') != 'complete'):
        raise ValueError('native prefix query unavailable: ' + str(report.get('reason')))
    if (packed.get('schema') != 'evaluator-live-packed-acquisition-v1' or packed.get('side') != side
            or packed.get('report_sha256') != sha(report) or packed.get('runtime') != receipt.get('runtime')
            or packed.get('source_sha256') != receipt.get('source_sha256')
            or packed.get('program_sexp') != report['query_prefix']['program_sexp']
            or packed.get('packing_ref') != report['packed_correspondence']['packing_ref']
            or source.get('source_sha256') != receipt['source_sha256']
            or source.get('runtime') != receipt['runtime'] or source.get('policy') != POLICY
            or sha(source['source_record']) != source['source_sha256']):
        raise ValueError('persisted adapter evidence does not bind original atomic query')
    native = report['packed_correspondence']
    if native.get('ident_namespace') != opening.get('ident_namespace') or native.get('universe_ref') != opening['universe_ref']:
        raise ValueError('native namespace/universe differs')
    return opening, report, source


def unique(rows, key):
    out = {}
    for row in rows:
        k = row[key]
        if k in out: raise ValueError('duplicate native ' + key)
        out[k] = row
    return out


def checked_table(table, report, opening):
    if (table.get('schema') != 'evaluator-prefix-train-table-v1' or table.get('policy') != POLICY
            or table.get('complete') is not True or table.get('missing') != []):
        raise ValueError('required prefix table incomplete')
    role = 'prefix_body' if table['table'] == report['body_table'] else 'prefix_available'
    receipt = table['receipt']
    if (table.get('role') != role or receipt.get('universe_ref') != opening['universe_ref']
            or receipt.get('ident_namespace') != opening['ident_namespace']
            or receipt.get('test_cells') is not False or receipt.get('gold_kept_used') is not False):
        raise ValueError('table role/U/namespace authority differs')
    packed = unique(report['packed_correspondence']['tables'], 'table')[table['table']]
    if role not in packed['report_roles']: raise ValueError('native table role mismatch')
    fields = table['fields']; width = len(fields)
    if ([f['index'] for f in fields] != list(range(width))
            or [f['type'] for f in fields] != packed['physical_types']
            or [f['name'] for f in fields] != packed['physical_names']):
        raise ValueError('physical schema differs from actual native packed table')
    columns = (report['body_columns'] if role == 'prefix_body' else
        unique(report['available_schemas'], 'table')[table['table']]['columns'])
    columns = unique(columns, 'physical_column')
    if set(columns) != set(range(width)): raise ValueError('native column correspondence incomplete')
    for i, field in enumerate(fields):
        column = columns[i]
        descriptor = column['physical_type']
        if field['type'] not in (descriptor['type'], descriptor['wire_type']):
            raise ValueError('native column type descriptor differs')
        if role == 'prefix_body' and field.get('prefix_source_identity') != column:
            raise ValueError('BODY source correspondence differs')
    families = {}
    required = set()
    for family in table['families']:
        axis = (family['parent_assignment'], family['example_index'])
        if (axis in families or family['example_kind'] != 1 or family.get('complete') is not True
                or not 0 <= axis[0] < opening['coverage']['parent_count']):
            raise ValueError('duplicate/incomplete TRAIN parent family')
        families[axis] = family; required.add((axis[0], 1, axis[1]))
    if sorted(map(list, required)) != table['required']: raise ValueError('required TRAIN family axes differ')
    native_families = unique(report['table_coverage'], 'table')[table['table']]['examples']
    native_counts = {}
    for example in native_families:
        if example['example_kind'] == 2: continue
        if example.get('status',{}).get('status') != 'complete':
            raise ValueError('native example family stopped')
        for family in example['families']:
            native_counts[(example['example_kind'],example['example_index'],family['parent_assignment'])] = family
    for family in families.values():
        nf = native_counts[(family['native_example_kind'],family['native_example_index'],family['parent_assignment'])]
        if (nf.get('complete') is not True or nf.get('observed_entries') != nf.get('model_count')
                or family['model_count'] != nf['model_count']
                or family['undefined_models'] != nf['undefined_models']
                or family['native_empty_rows_models'] != nf['empty_rows_models']):
            raise ValueError('local family differs from native coverage')
    seen = {}; native_map = {r['entry']: r for r in unique(report['entry_parent_map'], 'table')[table['table']]['entries']}
    for entry in table['entries']:
        axis = (entry['parent_assignment'], entry['example_index']); model = entry['model']
        if (entry['example_kind'] != 1 or entry['assignment'] != axis[0] or axis not in families
                or type(model) is not int or not 0 <= model < families[axis]['model_count']
                or model in seen.setdefault(axis, set())):
            raise ValueError('entry lacks unique local TRAIN parent/model axis')
        seen[axis].add(model)
        native_entry = native_map[entry['native_entry']]
        if any(native_entry[k] != entry[k] for k in ('parent_assignment','model')) or (
                native_entry['example_kind'],native_entry['example_index']) != (
                entry['native_example_kind'],entry['native_example_index']):
            raise ValueError('entry differs from native parent map')
        rows = entry['rows']
        if entry['kind'] == 'undefined':
            if rows is not None: raise ValueError('Undefined was changed into rows')
            continue
        if entry['kind'] != 'rows' or not isinstance(rows, list): raise ValueError('unknown prefix model state')
        for row in rows:
            if len(row) != width: raise ValueError('typed row width differs')
            for i, cell in enumerate(row):
                if (not isinstance(cell, dict) or not isinstance(cell.get('value'), list)
                        or len(cell['value']) != columns[i]['physical_type']['cell_width']
                        or any(type(v) is not int or not -(2**31) <= v < 2**31 for v in cell['value'])):
                    raise ValueError('native typed cell shape differs')
    for axis, family in families.items():
        if seen.get(axis, set()) != set(range(family['model_count'])):
            raise ValueError('local model family incomplete')
    return dict(schema='prefix-feature-table-v1',row_universe=LAYOUT,
        fields=fields,entries=table['entries'],families=table['families'],required=table['required'],missing=[],
        complete=True,zero_parent_universe=table['zero_parent_universe'],
        model_namespace='local to this table/parent/TRAIN family; no ordinal cross-table join')



def valid_ref(ref):
    try:
        path=confined(ref['path'])
        return (path.is_file() and path.stat().st_size==ref['bytes']
            and file_sha(path)==ref['sha256']
            and ('original_sha_ref' not in ref or valid_ref(ref['original_sha_ref'])))
    except (OSError,KeyError,ValueError,TypeError):return False


def write_packet(path, value):
    write_gzip_json(path, value)
    return reference(path)




@lru_cache(maxsize=4)
def wheel_binaries(path, device, inode, size, mtime, ctime):
    """Stream each immutable wheel once; cache only its tiny binary hash set."""
    matches=[]
    with zipfile.ZipFile(path) as wheel:
        for name in wheel.namelist():
            if name.endswith(('.so','.pyd')):
                h=hashlib.sha256()
                with wheel.open(name) as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
                matches.append(h.hexdigest())
    return tuple(matches)


def ready_references(paths):
    if paths is None:return []
    if isinstance(paths,(str,Path)):paths=[paths]
    refs=[]
    for path in sorted({confined(p) for p in paths}):
        if read_json(path).get('revision') not in FIXED_RUNTIME_REVISIONS:
            raise ValueError('runtime ready revision is not explicitly accepted')
        refs.append(reference(path))
    return refs


def runtime_authority(receipt, ready_paths, *, preview):
    if preview:
        return dict(status='preview_only',runtime=receipt['runtime'],
            declared_full_prefix_coverage='unproven; old complete status is insufficient')
    refs=ready_references(ready_paths)
    if not refs:raise ValueError('publication requires explicit fixed native runtime ready.json refs')
    wanted=receipt['runtime']['runtime']['binary_sha256'];matches=[]
    for ref in refs:
        ready_path=Path(ref['path']);ready=read_json(ready_path)
        if ready.get('revision') not in FIXED_RUNTIME_REVISIONS:
            raise ValueError('runtime lacks an explicitly accepted declared-prior-DET universe revision')
        wheel=confined(ready['wheel']);st=wheel.stat()
        binaries=wheel_binaries(str(wheel),st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
        if wanted in binaries:
            matches.append(dict(status='fixed_native_runtime',ready=ref,
                revision=ready['revision'],native_binary_sha256=wanted))
    if len(matches)>1:
        # Equal binaries cannot silently select the first/default build. The
        # receipt's actual installed path can disambiguate its original build.
        installed=Path(receipt['runtime']['runtime']['binary']).resolve()
        matches=[r for r in matches if installed.is_relative_to(Path(r['ready']['path']).parent)]
    if len(matches)!=1:raise ValueError('packet native binary has no unique matching explicit runtime ready')
    return matches[0]



def publish(acquisition_ref, gold_ref, *, pair_id, point_id, output, result_ref=None, context_ref=None,
            runtime_ready=None, preview=False):
    """Publish one stored candidate, reusing immutable inputs; no native imports."""
    output = confined(output); evidence = Evidence()
    layout = PREVIEW_LAYOUT if preview else LAYOUT
    if preview: output = output/'preview-only'
    # Raw ref + join source key permits metadata-only resume before JSON loads.
    key = sha(dict(X=acquisition_ref,G=gold_ref,result=result_ref,context=context_ref,
                   layout=layout,ready=ready_references(runtime_ready),
                   implementation=file_sha(__file__)))
    index = output/'published-pairs'/(pair_id+'.json')
    if index.exists():
        old = read_json(index)
        files_valid=old.get('public_files') and all(valid_ref(r)
                for r in [*old['public_files'],old['label'],old['receipt']])
        if old.get('key') == key and files_valid:
            return dict(status='reused',pair_id=pair_id,key=key)
        # Preserve prior validated f642 publications. Only the small index is
        # advanced: same exact acquisition/G/context/result and original ready,
        # same layout, same semantic checks, exact predecessor source hash.
        ready_refs=ready_references(runtime_ready)
        authority=old.get('coverage_authority',{})
        original_ready=authority.get('ready')
        if files_valid and authority.get('revision') in FIXED_RUNTIME_REVISIONS and original_ready in ready_refs:
            predecessor=sha(dict(X=acquisition_ref,G=gold_ref,result=result_ref,context=context_ref,
                layout=layout,ready=original_ready,implementation=PREDECESSOR_IMPLEMENTATION))
            previous_list=old.get('runtime_readies')
            current_predecessor=(sha(dict(X=acquisition_ref,G=gold_ref,result=result_ref,context=context_ref,
                layout=layout,ready=previous_list,implementation=file_sha(__file__)))
                if isinstance(previous_list,list) else None)
            if old.get('key') in (predecessor,current_predecessor):
                storage_key=old.get('storage_key',old['key'])
                old.update(key=key,storage_key=storage_key,runtime_readies=ready_refs,
                    reuse_reason='exact publication inputs/implementation; runtime provider list only, no row changes')
                write_json(index,old,compact=True)
                return dict(status='reused',pair_id=pair_id,key=key,storage_key=storage_key)
    if result_ref:
        result = evidence.read(result_ref)
        if result.get('pair_id') != pair_id or result.get('point_id') != point_id:
            raise ValueError('discovery result belongs to another pair/point')
    else: result = None
    context = evidence.read(context_ref) if context_ref else None
    value = evidence.read(acquisition_ref); gold = evidence.read(gold_ref) if gold_ref else None
    opening, report, source = checked_acquisition(value,evidence,'mutant')
    authority=runtime_authority(value['receipt'],runtime_ready,preview=preview)
    if context:
        if context.get('storage') == 'legacy-complete-packets':
            if context.get('x') != acquisition_ref or context.get('gold') != gold_ref:
                raise ValueError('legacy context does not bind the exact saved X/G packets')
        elif (context.get('universe_ref') != opening['universe_ref']
                or context.get('ident_namespace') != opening['ident_namespace']):
            raise ValueError('context ref differs from candidate native universe')
    if result and value['receipt'].get('candidate_sha256') != result['source_sha256']:
        raise ValueError('candidate source digest differs from indexed source')
    tables = unique(value['tables'], 'table')
    if value.get('available_refs'):
        if context is None or value.get('context') != context_ref or context.get('gold') != gold_ref:
            raise ValueError('external available refs lack their SAME-context authority')
        for external in value['available_refs']:
            if (external.get('packet') != gold_ref or external.get('context') != context_ref
                    or external.get('packet_table') != external.get('table')
                    or external.get('certificate') != 'native available_cached + canonical adapter exact fingerprint'
                    or external.get('receipt',{}).get('reused_on_same_native_universe') is not True):
                raise ValueError('external available packet is not certified SAME-context cache reuse')
            table = unique(gold['tables'], 'table')[external['packet_table']]
            if table['table'] in tables or table['role'] != 'prefix_available':
                raise ValueError('duplicate/external nonavailable table')
            tables[table['table']] = table
    packed = report['packed_correspondence']['tables']
    admitted = [t['table'] for t in packed if 'prefix_available' in t['report_roles']]
    if set(tables) != set(admitted + [report['body_table']]):
        raise ValueError('candidate omits native available inventory or BODY')
    if gold is not None:
        if gold['receipt']['runtime']!=value['receipt']['runtime']:
            raise ValueError('X/G retain different native runtime contexts')
        # A G-only failure cannot suppress a usable X; complete G, when present,
        # must still bind this exact U/namespace. Its rows are written label-only.
        gold_open = evidence.read(gold['receipt']['opening_ref'])
        if (gold_open['universe_ref'],gold_open['ident_namespace']) != (opening['universe_ref'],opening['ident_namespace']):
            raise ValueError('G context differs; no cross-context/model/Ident join allowed')
    context_id = sha(dict(universe=opening['universe_ref'],namespace=opening['ident_namespace']))
    point_dir = output/'inputs'/'points'/point_id/context_id
    pair_dir = output/'inputs'/'pairs'/pair_id/key
    label_dir = output/'labels'/point_id/context_id
    private_dir = output/'private'/pair_id/key
    table_index = []; public_refs = []
    for ordinal, table_id in enumerate(admitted):
        packet = checked_table(tables[table_id],report,opening);packet['row_universe']=layout
        tn = 'T'+str(ordinal); target = point_dir/'tables'/(tn+'.json.gz')
        if target.exists():
            # Never overwrite a shared context with a different native table.
            existing = read_json(target)
            if sha(existing) != sha(packet): raise ValueError('shared context Tn packet differs')
            ref = reference(target)
        else: ref = write_packet(target,packet)
        public_refs.append(ref)
        witness = unique(report['available_schemas'],'table')[table_id]
        table_index.append(dict(id=tn,native_table=table_id,selector=unique(packed,'table')[table_id]['selector'],
            native_correspondence=witness,path='tables/'+tn+'.json.gz'))
    point_value = dict(format='prefix-features-point-v1',row_universe=layout,task=opening['task'],
        point=opening['body_path'],context=context_id,tables=table_index,
        prefix=opening['frontier'],parent_count=opening['coverage']['parent_count'],
        ident_namespace=opening['ident_namespace'],model_policy='local model families; never zip across tables',
        source='independently checked prefix only; G and suffix excluded')
    point_file = point_dir/'point.json.gz'
    if point_file.exists():
        if sha(read_json(point_file)) != sha(point_value): raise ValueError('context point metadata differs')
        public_refs.append(reference(point_file))
    else: public_refs.append(write_packet(point_file,point_value))
    x = checked_table(tables[report['body_table']],report,opening);x['row_universe']=layout
    public_refs.append(write_packet(pair_dir/'tables'/'X.json.gz',x))
    # Only the independently checked native query prefix is feature syntax.
    pair = dict(format='prefix-features-pair-v1',row_universe=layout,pair_id=pair_id,context=context_id,
        point=str(point_file.relative_to(output)),X='tables/X.json.gz',
        candidate=report['query_prefix'],labels='separate label-only tree; not feature input')
    public_refs.append(write_packet(pair_dir/'pair.json.gz',pair))
    label = dict(schema='prefix-feature-label-v1',role='label_only',status='unavailable',reason=None)
    if gold is not None:
        try:
            go, gr, _ = checked_acquisition(gold,evidence,'gold')
            body = unique(gold['tables'],'table')[gold['body_table']]
            g=checked_table(body,gr,go);g['row_universe']=layout
            if not preview:runtime_authority(gold['receipt'],runtime_ready,preview=False)
            label.update(status='complete',table=g)
        except (ValueError,KeyError,TypeError) as error:
            label.update(reason=str(error),native=native_problem(gold,evidence))
    label_path = label_dir/'G.json.gz'
    if label_path.exists():
        if sha(read_json(label_path)) != sha(label): raise ValueError('shared native G label differs')
        label_ref = reference(label_path)
    else: label_ref = write_packet(label_path,label)
    receipt = dict(schema='prefix-feature-publication-v1',key=key,pair_id=pair_id,point_id=point_id,
        row_universe=layout,coverage_authority=authority,context=context_id,source_sha256=value['receipt'].get('candidate_sha256'),
        acquisition_source=source['source_sha256'],runtime=value['receipt']['runtime'],
        native_universe=opening['universe_ref'],ident_namespace=opening['ident_namespace'],
        inputs=public_refs,label=label_ref,private_evidence=evidence.refs,
        Tn_contract='new context-local IDs in exact native packed available-table order; not legacy kept Tn',
        replay=False,gold_kept_used=False,feature_input_excludes=['G','full source programs','later forms','private reports'])
    receipt_ref = write_packet(private_dir/'receipt.json.gz',receipt)
    index_value = dict(schema='prefix-feature-index-v1',key=key,pair_id=pair_id,point_id=point_id,
        context=context_id,pair=public_refs[-1],public_files=public_refs,receipt=receipt_ref,
        label=label_ref,row_universe=layout,coverage_authority=authority,runtime_readies=ready_references(runtime_ready))
    index.parent.mkdir(parents=True,exist_ok=True);write_json(index,index_value,compact=True)
    return dict(status='published',pair_id=pair_id,key=key,label_status=label['status'])


def publish_discovery(path, output, *, runtime_ready=None, preview=False):
    evidence=Evidence(); discovery=evidence.read(reference(path)); result=evidence.read(discovery['result'])
    if result.get('status') != 'complete':
        detail=dict(status='unavailable',pair_id=result.get('pair_id'),reason=result.get('reason'))
        if result.get('acquisition'): detail['native']=native_problem(evidence.read(result['acquisition']),evidence)
        return detail
    context=evidence.read(result['context'])
    gold_ref=context['gold']
    return publish(result['acquisition'],gold_ref,pair_id=result['pair_id'],point_id=result['point_id'],
                   output=output,result_ref=discovery['result'],context_ref=result['context'],runtime_ready=runtime_ready,preview=preview)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store',type=Path,default=DATA_ROOT/'judgetool/prefix-full-v1')
    parser.add_argument('--output',type=Path,default=DATA_ROOT/'feat-exp/prefix-u-v1')
    parser.add_argument('--runtime-ready',type=Path,action='append',help='repeat for explicit fixed runtime ready.json refs; each packet selects its matching native binary')
    parser.add_argument('--preview',action='store_true',help='DEV readback only; old-U coverage remains unproven, output isolated')
    parser.add_argument('--pair-id',action='append',default=[])
    parser.add_argument('--dev',type=Path,help='one stored DEV point folder with gold/mutant packets and operation.json')
    args=parser.parse_args();output=confined(args.output);counts=Counter()
    if not args.preview and args.runtime_ready is None:parser.error('--runtime-ready is required; old complete results are not full-U proof')
    if args.dev:
        folder=confined(args.dev);operation=read_json(folder/'operation.json')
        def saved(name):
            path=folder/(name+'.json');path=path if path.exists() else path.with_name(path.name+'.gz')
            return reference(path)
        print(json.dumps(publish(saved('mutant'),saved('gold'),pair_id=operation['pair_id'],
            point_id=operation['point_id'],output=output,runtime_ready=args.runtime_ready,preview=args.preview)),flush=True)
        return 0
    files=([args.store/'published-pairs'/(p+'.json') for p in args.pair_id]
        if args.pair_id else sorted((args.store/'published-pairs').glob('*.json')))
    for path in files:
        operator=output/'operator'/(path.stem+'.json')
        resume_key=sha(dict(discovery=reference(path),implementation=file_sha(__file__),
            ready=ready_references(args.runtime_ready),preview=args.preview))
        if operator.exists():
            previous=read_json(operator)
            if previous.get('resume_key')==resume_key and previous.get('result',{}).get('status')=='unavailable':
                result=dict(previous['result'],stored=True);counts['stored_unavailable']+=1
                print(json.dumps(result),flush=True);continue
        try:result=publish_discovery(path,output,runtime_ready=args.runtime_ready,preview=args.preview)
        except (ValueError,KeyError,TypeError,OSError) as error:
            result=dict(status='unavailable',discovery=str(path),reason=f'{type(error).__name__}: {error}')
        if result['status']=='unavailable':
            write_json(operator,dict(resume_key=resume_key,result=result),compact=True)
        counts[result['status']]+=1
        print(json.dumps(result),flush=True)
    print(json.dumps(dict(summary=dict(counts))),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())

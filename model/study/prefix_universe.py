"""DEV adapter for one native, suffix-independent common prefix universe.

No kept matching, later-reader projection, Python assignment expansion or raw
snapshot coverage inference. Native scope/bounds remain authoritative. This is
not the historical whole-gold-kept packet/policy and is not a full-run driver.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import time

from study_paths import CODE_ROOT, DATA_ROOT
from native_correspondence import PrefixCorrespondence, Unavailable, source_program_record

POLICY='native-prefix-parent-universe-v1'


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        allow_nan=False,separators=(',',':')).encode()).hexdigest()


def _write(path,value):
    from judge3.dataset_format import write_json
    write_json(path,value,compact=True)
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return dict(path=str(path.resolve()),sha256=digest.hexdigest())


def dependency_receipt():
    from evaluator_train import det_dependency_receipt
    return dict(det_dependency_receipt(),**{str(Path(__file__).resolve()):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})


def _kind(value):
    if type(value) is not int or value not in (0,1,2):
        raise Unavailable('native prefix example kind is not the frozen numeric wire axis')
    return value


def _table(point,binding,table,packed_receipt,report_ref):
    """Decode only native-mapped TRAIN/TASK values; retain every model state."""
    from evaluator_train import _visibility
    from types import SimpleNamespace
    reader=binding.reader;mapping=binding.entries(table);coverage=binding.families(table)
    ntrain=point.ntrain;families=[];required=set();missing=[];expected={};seen_axes=set()
    native_axes=[]
    for example in coverage:
        kind=_kind(example['example_kind']);index=example['example_index']
        if kind==2:continue                 # before assignment or value access
        if type(index) is not int or (kind==0 and index!=0) or (kind==1 and not 0<=index<ntrain):
            raise Unavailable('prefix model family has invalid TRAIN/TASK axis')
        if (kind,index) in native_axes:raise Unavailable('duplicate native prefix example family')
        native_axes.append((kind,index))
        if example.get('status',{}).get('status')!='complete':raise Unavailable('prefix example family stopped')
        rows=example.get('families')
        if not isinstance(rows,list) or [r.get('parent_assignment') for r in rows]!=list(range(binding.parent_count)):
            raise Unavailable('prefix model family omits common parents')
        for family in rows:
            count=family.get('model_count');parent=family['parent_assignment']
            if (family.get('complete') is not True or type(count) is not int or count<0
                    or family.get('observed_entries')!=count):
                raise Unavailable('prefix local model enumeration incomplete')
            expected[(kind,index,parent)]=family
            for train in (range(ntrain) if kind==0 else [index]):
                axis=(parent,1,train)
                if axis in seen_axes:raise Unavailable('prefix TASK and TRAIN families overlap')
                seen_axes.add(axis);required.add(axis)
                families.append(dict(parent_assignment=parent,example_kind=1,example_index=train,
                    native_example_kind=kind,native_example_index=index,model_count=count,
                    undefined_models=family['undefined_models'],native_empty_rows_models=family['empty_rows_models'],
                    complete=True,model_namespace='local table/native-example family; no cross-family alignment'))
    if set(native_axes) not in ({(0,0)},{(1,i) for i in range(ntrain)}):
        raise Unavailable('prefix table lacks a complete TRAIN or TASK example domain')
    fields=binding.fields(table);entries=[];actual={key:[] for key in expected};zero_placeholders=[]
    for row in mapping:
        kind=_kind(row['example_kind'])
        if kind==2:continue                 # never decode TEST assignment/cells
        index=row['example_index'];parent=row['parent_assignment'];entry=row['entry']
        if parent is None:
            # The native complete zero universe may pack one NoEntries marker.
            if (binding.parent_count!=0 or int(reader.entries['kind'][entry])!=5
                    or any(reader.entries[k][entry] for k in ('fault','stop_bound','value_stop_bound'))):
                raise Unavailable('prefix placeholder is not an exhausted zero-parent family')
            zero_placeholders.append(entry);continue
        axis=(kind,index,parent)
        if axis not in expected:raise Unavailable('prefix entry lacks native parent/example family')
        actual[axis].append(entry)
        value_kind=int(reader.entries['kind'][entry]);model=row['model']
        if value_kind==2:
            if any(reader.entries[k][entry] for k in ('fault','stop_bound','value_stop_bound')):
                raise Unavailable('native Undefined model also has a fault/stop')
            reader.validate_assignment(entry)
            rows=None;value='undefined'
        elif value_kind==0:
            decoded=reader.entry(entry,with_extents=True,projection_stop=False)
            decoded=_visibility()(SimpleNamespace(ntrain=ntrain),decoded,reader.schema(table))
            rows=decoded['rows'];value='rows'
        else:
            raise Unavailable('native prefix required model lacks full Rows: entry='+str(entry)+' kind='+str(value_kind))
        for train in (range(ntrain) if kind==0 else [index]):
            entries.append(dict(parent_assignment=parent,assignment=parent,example_kind=1,example_index=train,
                model=model,kind=value,rows=rows,native_entry=entry,native_example_kind=kind,native_example_index=index))
    for axis,family in expected.items():
        observed=actual[axis];models=[int(reader.entries['model'][e]) for e in observed]
        if models!=list(range(family['model_count'])):raise Unavailable('native prefix model ordinals/coverage differ')
        if sum(int(reader.entries['kind'][e])==2 for e in observed)!=family['undefined_models']:
            raise Unavailable('native prefix Undefined model accounting differs')
        if sum(int(reader.entries['kind'][e])==0 and int(reader.entries['rows'][e])==0 for e in observed)!=family['empty_rows_models']:
            raise Unavailable('native prefix empty-Row accounting differs')
    return dict(schema='evaluator-prefix-train-table-v1',policy=POLICY,table=table,role=binding.role(table),
        source_name=binding.maps[table].get('source_name'),fields=fields,entries=entries,
        required=[list(a) for a in sorted(required)],missing=missing,families=families,
        zero_parent_universe=binding.parent_count==0,zero_parent_placeholders=zero_placeholders,
        complete=True,status='complete',receipt=dict(universe_ref=point.report['universe_ref'],
            ident_namespace=point.report['ident_namespace'],entry_parent_map='native actual packed entry_parent_map',
            report_ref=report_ref,packed_acquisition_ref=packed_receipt,source_sha256=point.source_sha256,
            task_broadcast='TRAIN entry axis only; physical Example cells retain native filtered values',
            model_namespace='local table/native-example family',test_cells=False,gold_kept_used=False))


class PrefixPoint:
    """One point, independent session, native U and cached available values.

    original_record is canonical stored source, never rewritten to a prefix.
    acquire(mutant_record=...) constructs a real native ValidMutant from this
    object's exact original gold handle. A caller can pass mutant= instead if
    it already owns a ValidMutant from point.program; arbitrary ASTs are refused
    by the native interface. No private gold-kept set is used for any selection.
    """
    def __init__(self,ev,original_record,*,max_assignments=None,artifacts=None):
        self.ev=ev;self.original_record=original_record;self.source_sha256=_sha(original_record)
        self.record=source_program_record(original_record)
        self.max_assignments=max_assignments
        if max_assignments is not None and (type(max_assignments) is not int or max_assignments<1):
            raise ValueError('max_assignments must be positive or omitted for the native session cap')
        self.artifacts=Path(artifacts or DATA_ROOT/'judgetool/prefix-universe'/_sha(dict(source=self.source_sha256,cap=max_assignments,runtime=ev.receipt)))
        if not self.artifacts.resolve().is_relative_to(DATA_ROOT.resolve()):raise ValueError('prefix artifacts must remain under DATA_ROOT')
        self.available={};self.sequence=0;self.universe=None;self._context=None;self._available_terminal=None

    def __enter__(self):
        from native_correspondence import stored_metadata_program
        self._context=self.ev.fresh_session();self.isolated=self._context.__enter__()
        try:
            self.native=self.isolated.task_evaluator(self.record['task'])
            session_cap=getattr(self.native,'assignment_cap',None)
            if type(session_cap) is not int or session_cap<1:
                raise Unavailable('runtime lacks authoritative session assignment_cap; build the cap-fixed prefix runtime')
            if self.max_assignments is not None and self.max_assignments!=session_cap:
                raise ValueError('max_assignments must equal the native session assignment cap '+str(session_cap)+'; omit the override')
            self.max_assignments=session_cap
            missing=[name for name in ('prefix_universe','prefix_tables','rehydrate_prefix_identity')
                if not callable(getattr(self.native,name,None))]
            if missing:
                raise Unavailable('runtime lacks prefix API '+', '.join(missing)+'; build the prefix-held admission runtime')
            self.program=stored_metadata_program(self.ev.arclog,self.record['programs']['gold'],self.isolated.settings)
            task_path=Path(self.isolated.cfg['tasks'])/(self.record['task']+'.json')
            task=json.loads(task_path.read_text());self.ntrain=len(task['train'])
            self.task_input_sha256=hashlib.sha256(task_path.read_bytes()).hexdigest()
            raw,self.universe=self.native.prefix_universe(self.program,self.record['point'],max_assignments=self.max_assignments)
            self.report=json.loads(raw)
            self.artifacts.mkdir(parents=True,exist_ok=True)
            self.opening_ref=_write(self.artifacts/'universe.json',self.report)
            self.source_ref=_write(self.artifacts/'source.json',dict(source_sha256=self.source_sha256,
                source_record=self.original_record,task_input_sha256=self.task_input_sha256,
                runtime=self.isolated.receipt,session_assignment_cap=session_cap,
                implementation=dependency_receipt(),policy=POLICY,private_only=True))
            return self
        except BaseException:
            self.close();raise

    def _opening_complete(self):
        coverage=self.report.get('coverage',{})
        return (self.report.get('schema')=='arclog-study-prefix-universe-v1'
            and self.report.get('source_program_sexp')==self.program.sexp()
            and self.report.get('body_path')==self.record['point']
            and self.report.get('task')==self.record['task']
            and self.report.get('status')=='complete'
            and coverage.get('enumeration_complete') is True and coverage.get('assignment_values_complete') is True)

    def acquire(self,mutant_record=None,*,mutant=None):
        if self.universe is None:raise ValueError('prefix point is not open')
        if mutant_record is not None and mutant is not None:raise ValueError('supply one actual candidate')
        if not self._opening_complete():
            return dict(schema='evaluator-prefix-acquisition-v1',policy=POLICY,
                status=self.report.get('status','unavailable') if self.report.get('status')!='complete' else 'unavailable',
                complete=False,reason=self.report.get('reason') or 'native prefix enumeration/parameter values incomplete',
                tables=[],body_table=None,report_ref=self.opening_ref,receipt=dict(opening_ref=self.opening_ref,source_ref=self.source_ref))
        if self._available_terminal is not None:
            return dict(schema='evaluator-prefix-acquisition-v1',policy=POLICY,
                side='mutant' if mutant_record is not None or mutant is not None else 'gold',
                status=self._available_terminal['status'],complete=False,
                reason='native available materialization is terminal on this universe; no repeated query',
                tables=[],body_table=None,report_ref=self._available_terminal['report_ref'],
                receipt=dict(opening_ref=self.opening_ref,source_ref=self.source_ref,
                    cached_available_terminal=self._available_terminal,skipped_native_query=True,
                    candidate_sha256=None if mutant_record is None else _sha(mutant_record)))
        from native_correspondence import rehydrate_prefix_mutation,stored_metadata_program
        candidate_sha=None;admission=None
        if mutant_record is not None:
            record=source_program_record(mutant_record)
            if any(record[k]!=self.record[k] for k in ('task','case','point')) or record['programs']['gold']!=self.record['programs']['gold']:
                raise ValueError('candidate belongs to another original point/source')
            stored=stored_metadata_program(self.ev.arclog,record['programs']['mutant'],self.isolated.settings)
            mutant,admission=rehydrate_prefix_mutation(self.native,self.universe,self.program,
                record['identity'],stored,self.report)
            candidate_sha=_sha(mutant_record)
        started=time.monotonic();side='mutant' if mutant is not None else 'gold'
        self.sequence+=1;folder=self.artifacts/('acquisition-'+str(self.sequence).zfill(5));folder.mkdir(parents=True,exist_ok=True)
        admission_ref=_write(folder/'prefix-admission.json',admission) if admission is not None else None
        native_started=time.monotonic()
        raw,payload=self.native.prefix_tables(self.universe,mutant=mutant,include_available=True)
        native_seconds=time.monotonic()-native_started
        report=json.loads(raw);report_ref=_write(folder/'report.json',report)
        if report.get('available_status',{}).get('status') in ('stopped','fault','unavailable'):
            self._available_terminal=dict(status=report['available_status']['status'],
                report_ref=report_ref,native_status=deepcopy(report['available_status']))
        receipt=dict(opening_ref=self.opening_ref,source_ref=self.source_ref,policy=POLICY,
            source_sha256=self.source_sha256,candidate_sha256=candidate_sha,runtime=self.isolated.receipt,
            raw_reuse=deepcopy(report.get('raw_reuse')),test_cells=False,gold_kept_used=False,
            native_seconds=native_seconds,native_timings=deepcopy(report.get('timings')),implementation=dependency_receipt())
        if admission_ref is not None:
            receipt['prefix_admission_ref']=admission_ref
            receipt['held_admission_scope']='actual native prefix-carried DETs only; not all gold DETs'
        result=dict(schema='evaluator-prefix-acquisition-v1',policy=POLICY,side=side,
            status=report.get('status','unavailable'),complete=False,reason=report.get('reason'),
            body_table=report.get('body_table'),tables=[],receipt=receipt,report_ref=report_ref)
        try:
            native=self.isolated.legacy.native(payload);reader=native['_native_reader']
            actual_program=mutant.sexp() if mutant is not None else self.program.sexp()
            binding=PrefixCorrespondence(self.report,report,reader,task=self.record['task'],source_program_sexp=actual_program,side=side)
            packed=binding.atomic.receipt(payload,report_sha256=_sha(report),source_sha256=self.source_sha256,runtime=self.isolated.receipt)
            packed_ref=_write(folder/'packed-acquisition.json',packed)
            receipt['packed_acquisition_ref']=packed_ref;receipt['universe_ref']=self.report['universe_ref']
            extraction=time.monotonic()
            for table in sorted(binding.maps):
                # The native cache explicitly certifies unchanged available
                # materialization on this same U. Still bind every returned
                # physical schema/map/coverage before reusing a typed packet.
                fingerprint=_sha(dict(fields=binding.fields(table),entries=binding.entries(table),families=binding.families(table),
                    universe=self.report['universe_ref'],namespace=self.report['ident_namespace']))
                cached=self.available.get(table)
                if binding.role(table)=='prefix_available' and report.get('available_cached') is True and cached is not None and cached[0]==fingerprint:
                    packet=dict(cached[1],receipt=dict(cached[1]['receipt'],reused_on_same_native_universe=True))
                else:
                    try:packet=_table(self,binding,table,packed_ref,report_ref)
                    except (ValueError,KeyError,IndexError,TypeError) as error:
                        packet=dict(schema='evaluator-prefix-train-table-v1',policy=POLICY,table=table,role=binding.role(table),
                            complete=False,status='unavailable',reason=str(error),error_type=type(error).__name__,entries=[],
                            native_coverage=deepcopy(binding.coverage[table]))
                    if packet['complete'] and binding.role(table)=='prefix_available':self.available[table]=(fingerprint,packet)
                result['tables'].append(packet)
            receipt['python_extraction_seconds']=time.monotonic()-extraction
            result['complete']=all(t['complete'] for t in result['tables'])
            result['status']='complete' if result['complete'] else 'unavailable'
            if not result['complete']:result['reason']='one or more native prefix tables lack complete typed TRAIN transport'
        except (ValueError,KeyError,IndexError,TypeError) as error:
            result['status']=report.get('status') if report.get('status') in ('stopped','fault','unavailable') else 'unavailable'
            result['reason']=str(error);result['error_type']=type(error).__name__
        receipt['total_seconds']=time.monotonic()-started
        receipt_ref=_write(folder/'receipt.json',receipt);result['receipt_ref']=receipt_ref
        return result

    def close(self):
        try:
            if self.universe is not None:self.universe.close()
        finally:
            self.universe=None
            if self._context is not None:
                context=self._context;self._context=None
                try:context.__exit__(None,None,None)
                finally:self.available.clear()
            else:self.available.clear()

    def __exit__(self,*_):
        self.close()

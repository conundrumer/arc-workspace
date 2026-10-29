"""Typed full kept DET rows decoded by the native engine, with source names."""
import gzip
import json
from collections import OrderedDict
from pathlib import Path
from native import Native, require


def full_gold_status(evaluation, *, scope=None):
    """Read the native gold status without rewriting either snapshot envelope."""
    require(isinstance(evaluation,dict),'full gold evaluation envelope missing')
    if scope == 'gold_full_kept':
        require(evaluation.get('scope')=='gold-only','full kept gold evaluation scope differs')
        require(not {'status','reason','form'}.intersection(evaluation),
                'scoped gold evaluation has ambiguous top-level status fields')
        status=evaluation.get('gold_status')
        require(isinstance(status,dict),'scoped native gold status missing')
    else:
        require(scope is None and evaluation.get('scope')!='gold-only',
                'unknown full gold evaluation scope')
        status=evaluation
    require(status.get('status') in ('complete','stopped','fault'),'unknown native full gold status')
    return status


class Assignments:
    def __init__(self, engine):
        self.engine=engine
        self.cache=OrderedDict()

    def schemas(self, record, source):
        reference=record.get('full_replay',{}).get('gold')
        if not reference:return None
        path=(source.parent/reference).resolve(); revision=(path.stat().st_size,path.stat().st_mtime_ns)
        scope=record.get('full_replay',{}).get('scope')
        key=(str(path),revision,scope)
        if key in self.cache:return self.cache[key]
        with gzip.open(path,'rt') as incoming:
            data=json.load(incoming)
        status=full_gold_status(data['evaluation'],scope=scope)
        require(status['status'] in ('complete','stopped'),'full gold native evaluation fault: '+str(status))
        native=Native(data['native']); ts=native.tables
        schemas={}
        for t in range(len(ts['width'])):
            for i,relation in enumerate(ts['det_relations'][t]):
                schema=dict(types=ts['det_types'][t][i],frames=ts['det_frames'][t][i],columns=ts['det_columns'][t][i])
                if relation in schemas:
                    require(schemas[relation]['types']==schema['types'],'DET has inconsistent native types')
                else:schemas[relation]=schema
        schemas=dict(relations=schemas,evaluation=data['evaluation'])
        self.cache[key]=schemas
        while len(self.cache)>8:self.cache.popitem(last=False)
        return schemas

    def decode(self, record, source, gold):
        if not hasattr(self.engine.StudyProgram,'decode_rows_json') or gold['parts'].get('definitions_readers')!='complete':
            return None
        snapshot=self.schemas(record,source)
        if snapshot is None:return None
        schemas=snapshot['relations']
        definitions={r['source_name']:r for r in gold['definitions']['native_relations']}
        nodes={tuple(n['path']):n for n in gold['nodes']}
        result=[]
        def flat(term):
            if term['kind']=='box':
                return [term['margins'][k] for k in ('top','bottom','left','right')]
            if term['kind']=='unit':return [0]
            if term['kind'] in ('orientation','ident'):
                n=term['encoding_u32'];return [n if n < 2**31 else n-2**32]
            return [term['value']]
        for choice in record['evaluation']['kept_assignments']:
            decoded=[]
            for det in choice:
                name=det['relation']
                require(name in schemas and name in definitions,'kept DET lacks native schema/definition')
                schema=schemas[name]; definition=definitions[name]
                terms=json.loads(self.engine.StudyProgram.decode_rows_json(schema['types'],det['rows']))
                rows=[]
                for row in terms:
                    rows.append([dict(value=flat(term)) for term in row])
                path=definition['definition_path']
                require(path is not None and tuple(path) in nodes,'kept DET has no source AST definition')
                decoded.append(dict(source_name=name,definition=nodes[tuple(path)]['sexp'],
                                    display_name=definition.get('display_name'),
                                    schema=[dict(type=ty,frame=fr,name=col) for ty,fr,col in zip(schema['types'],schema['frames'],schema['columns'])],
                                    rows=rows,terms=terms))
            result.append(decoded)
        return result

    def evidence(self, program, kept=()):
        """Read native schemas/dependencies; empty choices decode no held values."""
        evidence=json.loads(program.choice_evidence_json(json.dumps(kept)))
        require(evidence['schema']=='arclog-study-choices-v1' and evidence['complete'] is True,'compiled choice evidence incomplete')
        require(len(evidence['choices'])==len(kept),'compiled choice coverage differs')
        require(len({d['source_name'] for d in evidence['dets']})==len(evidence['dets']),'duplicate compiled DET identity')
        require(len({tuple(b['body_path']) for b in evidence['bodies']})==len(evidence['bodies']),'duplicate compiled body identity')
        return evidence

    def compiled(self, record, program, export):
        """Decode exact historical full choices with their native checked schemas."""
        evidence=self.evidence(program,record['evaluation']['kept_assignments'])
        schemas={d['source_name']:d for d in evidence['dets']}
        definitions={d['source_name']:d for d in export['definitions']['native_relations']}
        nodes={tuple(n['path']):n for n in export['nodes']}
        from column_paths import text as column
        choices=[]
        for index,choice in enumerate(evidence['choices']):
            require(choice['assignment']==index,'compiled choice numbering differs')
            result=[]
            expected={d['relation']:d['rows'] for d in record['evaluation']['kept_assignments'][index]}
            for det in choice['full_assignment']:
                source=det['source_name'];schema=schemas[source];definition=definitions[source]
                require(det['packed_rows']==expected[source],'choice binding changed held rows')
                require(schema['columns'] is not None and len(schema['columns'])==len(det['types']),'DET native column paths missing')
                path=tuple(definition['definition_path']);require(path in nodes,'DET source definition missing')
                result.append(dict(source_name=source,display_name=definition.get('display_name'),definition=nodes[path]['sexp'],
                    schema=[dict(type=ty,name=column(col),frame='') for ty,col in zip(det['types'],schema['columns'])],
                    rows=[[dict(value=term_cells(cell)) for cell in row] for row in det['rows']],terms=det['rows']))
            choices.append(result)
        return choices,evidence


def body_dependencies(evidence, body):
    """Use native compiled body reads, independently of any choice decoding."""
    matches=[b for b in evidence['bodies'] if b['body_path']==body]
    require(len(matches)==1,'compiled body dependency identity missing or ambiguous')
    names=matches[0]['source_names']
    require(len(set(names))==len(names),'duplicate compiled body DET read')
    require(set(names)<={d['source_name'] for d in evidence['dets']},'compiled body reads undefined DET')
    return set(names)


def term_cells(term):
    if term['kind']=='box':return [term['margins'][k] for k in ('top','bottom','left','right')]
    if term['kind']=='unit':return [0]
    if term['kind'] in ('orientation','ident'):
        n=term['encoding_u32'];return [n if n<2**31 else n-2**32]
    return [term['value']]


def check_held_schema(relation,types,structured,side):
    """Preserve gold decoding; verify native column identity and permitted widening."""
    evidence=structured.get('choice_evidence')
    require(evidence is not None,'compiled original DET column identities unavailable')
    gold=next(d for d in evidence['gold']['dets'] if d['source_name']==relation)
    native=next(d for d in evidence[side]['dets'] if d['source_name']==relation)
    require(gold['columns']==native['columns'],'held DET original column identities changed')
    source=gold['types'];target=native['types']
    require(types==target and len(source)==len(target),'native held DET schema differs from checked program')
    require(all(a==b or (side=='mutant' and (a,b)==('Offset','Box')) for a,b in zip(source,target)),
            'held DET schema is not a compatible widening of gold')

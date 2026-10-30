"""Read-only population membership dispatch; grade policy remains StudyReader's."""
import json
from pathlib import Path
import sqlite3
from run import digest


class PopulationReader:
    def __init__(self,*,paths):
        self.paths=dict(paths);self.path=Path(self.paths.pop('population')).resolve()
        self.db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        self.meta=dict(self.db.execute('SELECT key,value FROM metadata'));self.readers={}

    def close(self):
        for reader in self.readers.values():reader.close()
        self.db.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def _reader(self,new):
        from read_grades import StudyReader
        if new not in self.readers:
            paths=dict(self.paths)
            if new:
                root=self.path.parent
                paths.update(base=Path(self.meta['labels']),witness_tests=root/'witness-tests.sqlite3',normal=root/'normal.sqlite3',fit_split=root/'fits.sqlite3',lib_search=root/'lib.sqlite3',target_comparison=root/'targets.sqlite3',judge_outcomes=root/'judge.sqlite3')
                # Explicit per-population store overrides remain possible.
                paths.update(self.paths.get('population_passes',{}))
            else:paths['base']=Path(self.meta['base'])
            paths.pop('population_passes',None)
            self.readers[new]=StudyReader(paths=paths)
        return self.readers[new]

    def _read(self,pair,payload,*,source_record=None,include_grades=True):
        from population_consume import observation,read_source,intact,member_inputs
        member=json.loads(payload)
        if member_inputs(member)!=self.db.execute('SELECT input_sha256 FROM members WHERE pair_id=?',(pair,)).fetchone()[0]:
            return dict(pair_id=pair,status='open',valid=False,reason='membership integrity differs')
        facts={k:member[k] for k in ('task','case','point','clause','kind','K','operation')}
        result=dict(pair_id=pair,facts=facts,population=dict(database=str(self.path),table='members',pair_id=pair),status='open',valid=False,grade='Unknown',normal=None)
        loc=observation(self.db,pair)
        if not loc:
            attempt=self.db.execute('SELECT payload FROM attempts WHERE pair_id=?',(pair,)).fetchone()
            return result|dict(reason='observation missing',attempt=json.loads(attempt[0]) if attempt else None)
        result['source']=loc;result['source_sha256']=loc['source_sha256']
        # Query by input binding before loading a potentially large source row.
        for new,path in ((False,self.meta['base']),(True,self.meta['labels'])):
            if not Path(path).exists():continue
            reader=self._reader(new)
            row=reader.base.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()
            if row and intact((row[1],row[4],row[5]),loc['source_sha256']):
                joined=reader._pair(row,source_record,include_grades=include_grades)
                return joined|dict(population=result['population'])
        rec=read_source(loc) if source_record is None else source_record
        if digest(rec)!=loc['source_sha256']:return result|dict(reason='source changed')
        from corpus_index import filter_labels
        filters=filter_labels(rec)
        return result|dict(status='filtered' if filters['filter_class'] else 'open',valid=True,reason='stored filter facts; no mechanical result' if filters['filter_class'] else 'mechanical result missing',filters=filters)

    def read_pair(self,pair_id,*,source_record=None):
        row=self.db.execute('SELECT payload FROM members WHERE pair_id=?',(pair_id,)).fetchone()
        if not row:return dict(status='open',valid=False,pair_id=pair_id,reason='not a population member')
        return self._read(pair_id,row[0],source_record=source_record)

    def read_pairs(self,*,rowids=None,include_grades=True):
        wanted=None if rowids is None else set(rowids)
        for rowid,pair,payload in self.db.execute('SELECT rowid,pair_id,payload FROM members ORDER BY rowid'):
            if wanted is not None and rowid not in wanted:continue
            result=self._read(pair,payload,include_grades=include_grades)
            if result.get('status')!='pruned':yield result

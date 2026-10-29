"""Bounded original-corpus reads for rare filtered-pair empty-table checks.

Uses the canonical native storage/held-context reader. No replay or labels are
computed, and no X rows or joined records are written to another store.
"""
from collections import OrderedDict
import gzip
import json
from pathlib import Path
from run import digest


class SourceReader:
    def __init__(self,code_root):
        self.code_root=Path(code_root);self.streams=OrderedDict();self.tasks={};self.store=None

    def close(self):
        for stream,line,value in self.streams.values():stream.close()
        self.streams.clear()

    def record(self,base):
        source=base['source'];path=Path(source['corpus']).resolve()/base['task']/source['file'];wanted=source['line']
        item=self.streams.pop(path,None)
        if item is None or item[1]>wanted:
            if item:item[0].close()
            item=(gzip.open(path,'rt'),0,None)
        stream,line,value=item
        while line<wanted:
            raw=next(stream);line+=1
            if line==wanted:value=json.loads(raw)
        self.streams[path]=(stream,line,value)
        while len(self.streams)>16:self.streams.popitem(last=False)[1][0].close()
        if value is None or digest(value)!=base['source_sha256']:raise ValueError('original source input differs')
        return value

    def groups(self,base,record=None):
        record=self.record(base) if record is None else record
        if digest(record)!=base['source_sha256']:raise ValueError('original source input differs')
        import sys
        sys.path.insert(0,str(self.code_root/'judgetool'))
        from evaluator import legacy_helpers
        from tables import TargetStore,kept_groups
        if self.store is None:self.store=TargetStore(legacy_helpers(),self.code_root)
        corpus=Path(base['source']['corpus']).resolve();task=base['task']
        key=(str(corpus),task)
        if key not in self.tasks:
            cfg=json.loads((corpus/'run.json').read_text())
            data=json.loads((Path(cfg['tasks'])/(task+'.json')).read_text())
            self.tasks[key]=(len(data['train']),len(data['test']))
        ntrain,ntest=self.tasks[key]
        native=self.store.snapshot(record['native']['mutant'],corpus/task)
        table=record['evaluation']['table_indices']['mutant_kept']
        result=kept_groups(self.store.L,native,table,record,ntrain,ntest)
        # Empty rowsets are preserved by every set projection, including INIT
        # key/port projection; a present zero-column row is still one row.
        self.store.cache.clear()
        return result

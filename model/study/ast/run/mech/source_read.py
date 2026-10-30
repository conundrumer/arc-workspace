"""Bounded original-corpus reads for rare filtered-pair empty-table checks.

Uses the canonical native storage/held-context reader. No replay or labels are
computed, and no X rows or joined records are written to another store.
"""
from collections import OrderedDict
import json
from pathlib import Path
try:
    from .run import digest
    from . import source_bindings as bindings
except ImportError:
    from run import digest
    import source_bindings as bindings


class SourceReader:
    def __init__(self,code_root):
        self.code_root=Path(code_root);self.streams=OrderedDict();self.tasks={};self.store=None

    def close(self):
        for reader,stream,line,value in self.streams.values():stream.close();reader.close()
        self.streams.clear()

    def record(self,base):
        """Read a canonical source record, including synthesized samples.

        Required base keys: task, source_sha256, source={corpus,file,line}.
        The physical path is corpus/task/file; line is one-based. Shared
        JsonlReader supports framed zstd, plain JSONL and legacy gzip. New
        samples need no migration entry. Historical migrated rows resolve
        through the binding journal without changing their recorded hash.
        """
        entry=bindings.source_entry(base['source_sha256'])
        if entry is not None:
            source=entry['locator'];expected=entry['current_sha']
        else:
            source=base['source'];expected=base['source_sha256']
        path=Path(source['corpus']).resolve()/base['task']/source['file']
        if entry is None:
            if bindings.active() and bindings.legacy_path(path):raise ValueError('unbound old source: '+str(path))
        value=bindings._read_locator(dict(source,task=base['task']),self.streams)
        if value is None or digest(value)!=expected:raise ValueError('original source input differs')
        if entry is not None and base['source_sha256']==entry['old_sha'] and entry['old_sha']!=entry['current_sha']:
            value=bindings.reverse_patch(value,bindings.object_value(bindings.connection(),entry['patch_ref']))
            if digest(value)!=base['source_sha256']:raise ValueError('historical source receipt differs')
        return value

    def groups(self,base,record=None):
        record=self.record(base) if record is None else record
        if digest(record)!=base['source_sha256']:raise ValueError('original source input differs')
        if self.store is None:
            import sys
            sys.path.insert(0,str(self.code_root/'judgetool'))
            from evaluator import legacy_helpers
            from tables import TargetStore
            self.store=TargetStore(legacy_helpers(),self.code_root)
        from tables import kept_groups
        corpus=Path(base['source']['corpus']).resolve();task=base['task']
        key=(str(corpus),task)
        if key not in self.tasks:
            cfg=json.loads(bindings.relocated_file(corpus/'run.json').read_text())
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

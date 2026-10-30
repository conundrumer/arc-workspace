#!/usr/bin/env python3
"""Classify stored changed forms using writer's normal constraint set; no evaluation."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import ast
from collections import Counter, defaultdict
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time

os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
if CODE_ROOT.resolve()!=HERE.parents[2]:
    raise RuntimeError('study_paths was imported from a foreign study checkout')
STUDY = CODE_ROOT
RUN = CODE_ROOT / 'ast/run'


def repository_module(name, path):
    """Load exact repository source even if a dependency changes sys.path."""
    path=Path(path).resolve()
    existing=sys.modules.get(name)
    if existing is not None:
        if Path(existing.__file__).resolve()!=path:
            raise RuntimeError(f'{name} already loaded from retired/foreign source: {existing.__file__}')
        return existing
    # Only these retired source roots can shadow the repository modules.
    # Runtime virtualenv site-packages may also live under DATA_ROOT.
    retired = {DATA_ROOT.resolve(), (DATA_ROOT/'ast/run').resolve(),
               (DATA_ROOT/'ast/run/mech').resolve(),
               (DATA_ROOT/'ast/run/mech2').resolve()}
    sys.path[:]=[str(CODE_ROOT),str(RUN/'mech'),str(RUN),str(REPO_ROOT/'model')]+[
        p for p in sys.path if Path(p or '.').resolve() not in retired]
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    try:spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name,None)
        raise
    return module


repository_module('pinned',CODE_ROOT/'pinned.py')
runner=repository_module('run',RUN/'mech/run.py')
canonical,digest,pair_key=runner.canonical,runner.digest,runner.pair_key
storage=repository_module('native_storage',RUN/'native_storage.py')
native_reader=repository_module('native_tables',RUN/'native_tables.py')
native_width=native_reader.width
writer=repository_module('writer',CODE_ROOT/'writer.py')
repository_module('encoder',REPO_ROOT/'model/encoder.py')
repository_module('viability',CODE_ROOT/'viability.py')
detectors=repository_module('detectors',CODE_ROOT/'detectors.py')
import numpy as np
import pandas as pd

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def policy_manifest():
    """Only classification code, runtime and source dependencies; no reports."""
    import arclog
    paths = [Path(__file__), HERE / 'classify_normal.py', HERE / 'facts.py',
             Path(writer.__file__), Path(storage.__file__),
             RUN / 'native_tables.py', RUN / 'mech/run.py',
             Path(detectors.__file__), Path(detectors.E.__file__),
             STUDY / 'pinned.py', CODE_ROOT / 'viability.py',
             Path(writer.ROOT) / 'engine/lib/registry.sexpr',
             CODE_ROOT / 'study_paths.py']
    runtime_paths = [Path(arclog.__file__)] + list(Path(arclog.__file__).parent.glob('*.so'))
    return dict(constraint_set='normal', normal_policy='finite-domain-functional-libs-v1',
                files={str(p.resolve()):sha(p) for p in paths + runtime_paths},
                numpy=np.__version__, pandas=pd.__version__)


def dependency_identity(manifest):
    """Relocation-independent dependency names, derived from the source receipt."""
    files = {}
    for path, value in manifest['files'].items():
        if '/model/study/' in path:
            name = path.split('/model/study/', 1)[1]
        elif path.endswith('/model/encoder.py'):
            name = 'model/encoder.py'
        elif path.endswith('/engine/lib/registry.sexpr'):
            name = 'engine/lib/registry.sexpr'
        else:
            name = 'runtime/' + Path(path).name
        if name in files and files[name] != value:
            raise ValueError('ambiguous normal dependency ' + name)
        files[name] = value
    return files


class StoredSource:
    """TableSource's read interface over authenticated, already stored native buffers."""
    def __init__(self, raw, task, case):
        self.raw, self.bad = raw, set()
        self.parts = {part: {k: list(storage.view(raw, part, k)) for k in raw[part]}
                      for part in ('tables', 'entries', 'flows', 'assigned')}
        ts = self.parts['tables']
        # Native references address tables by their physical row index; the
        # parquet TableSource interface exposes that identity as a column.
        self.t = pd.DataFrame({**ts, 'table': np.arange(len(ts['relation']))})
        self.t_at = {(task, case): np.arange(len(self.t))}
        es = self.parts['entries']
        self.i = {**{k: np.array(es[k]) for k in
                     ('table', 'example_kind', 'example_index', 'kind', 'rows', 'offset')},
                  'entry': np.arange(len(es['table']))}
        self.i_at = {(task, case): np.arange(len(es['table']))}

    def flows(self):
        fs = self.parts['flows']
        ix = [i for i, kind in enumerate(fs['kind']) if kind == 0]
        out = {k: np.array([fs[k][i] for i in ix]) for k in
               ('table', 'column', 'source_table', 'source_relation', 'source_column', 'det', 'atom')}
        return out, {next(iter(self.t_at)): np.arange(len(ix))}

    def assignments(self, task, case):
        a = self.parts['assigned']; out = defaultdict(set)
        for e, det, rows, offset in zip(a['entry'], a['det'], a['rows'], a['offset']):
            out[e].add((det, rows, offset))
        return {e: frozenset(v) for e, v in out.items()}


class StoredRows(writer.CaseRows):
    """Keep writer's layout/projection/count policy; change only the buffer transport."""
    def __init__(self, *args):
        super().__init__(*args)
        self.optimistic = False
        self.unavailable = []
        self.probes = {}
        self.mapping_issues = {}
        self._uncertain = []
        # CaseRows.setup sets ok before constructing tabs/ents/flows. Finish it
        # before this object can enter Context.rows_cache, so an exception cannot
        # leave a seemingly initialized object available to the next pair.
        self.setup()

    def setup(self):
        super().setup()
        if not self.ok:
            return
        # Forced declarations can precede the end of an INIT. Its remaining
        # model-written SKIP/port tokens must not start the next form. Retain the
        # writer's parsing/mapping policy, supplying whole top-level form spans.
        ids, model = self.stream
        starts = form_starts(ids, model, self.names)
        self.forms, self.place = {}, {}
        for j, lo in enumerate(starts):
            hi = starts[j+1] if j+1 < len(starts) else len(ids)
            place = 0
            for pos in range(lo, hi):
                if not model[pos] and self.kinds[ids[pos]] == 'relation':
                    k = int(self.names[ids[pos]][2:])
                    self.forms[k], self.place[k] = ids[lo:hi], place
                    place += 1

    def rows(self, lay, entry):
        _, _, _, n, off, _ = entry
        return np.frombuffer(self.src.raw['values'], dtype='<i4', count=n * lay['width'],
                             offset=4 * off).reshape(n, lay['width'])

    def one_row(self, k, sites, head):
        key = (int(k), canonical(sites), head)
        if key not in self.probes:
            self._uncertain = []
            self._probing = True
            try:
                result = super().one_row(k, sites, head)
                reason = list(self._uncertain)
            finally:
                self._probing = False
            self.probes[key] = (bool(result), reason)
            if reason:
                self.unavailable.append(dict(relation=int(k), sites=sites, head=head, reasons=reason))
        result, reason = self.probes[key]
        if reason and not any(p['relation'] == int(k) and p['sites'] == sites and p['head'] == head
                              for p in self.unavailable):
            self.unavailable.append(dict(relation=int(k), sites=sites, head=head, reasons=reason))
        return True if self.optimistic and reason else result

    def layout(self, k):
        lay = super().layout(k)
        if lay is not None:
            # Parquet exports type spatial aliases as Box. Native snapshots keep
            # Position/Offset names, each backed by the same four raw margins.
            offset = 0; spans = []
            for ty in lay['types']:
                end = offset + native_width([ty]); spans.append((offset,end)); offset=end
            if offset != lay['width']:
                raise ValueError('native column widths differ from stored row width')
            lay['spans'] = spans
        if lay is None and getattr(self, '_probing', False):
            if k not in self.tabs:
                matches=self.src.t[(self.src.t['point']==0)&(self.src.t['relation']==k)]
                reason='native prefix relation absent' if len(matches)==0 else 'native prefix relation identity ambiguous'
            elif isinstance(self.tabs[k].fault,str):reason='native prefix relation faulted'
            elif k not in self.forms:reason='stored stream declaration absent'
            elif not self.ents.get(self.tabs[k].table):reason='native prefix relation entries absent'
            else:reason='stored relation layout unavailable'
            self._uncertain.append(reason)
        return lay

    def columns(self, *args):
        cols = super().columns(*args)
        k,column,_,head=args
        lay=self.lays.get(k)
        if lay is not None and lay.get('kind')=='body':
            if head in ('DET','INIT','CHOOSE','RIGID_DET') and lay['per_input']:
                column-=1
            # Body mappings are cached by CaseRows. Their transitive uncertainty
            # must survive cache hits just as their selected columns do.
            for reason in self.mapping_issues.get((k,column),()):
                if getattr(self,'_probing',False) and reason not in self._uncertain:
                    self._uncertain.append(reason)
        if cols is None and getattr(self, '_probing', False):
            if lay is not None:
                self._uncertain.append('column-to-native projection unavailable')
        return cols

    def body_groups(self,k,lay,column):
        parent=self._uncertain;probing=getattr(self,'_probing',False)
        self._uncertain=[];self._probing=True
        try:
            groups=super().body_groups(k,lay,column)
            issues=tuple(dict.fromkeys(self._uncertain))
        finally:
            self._uncertain=parent;self._probing=probing
        self.mapping_issues[k,column]=issues
        if probing:
            parent.extend(reason for reason in issues if reason not in parent)
        return groups

    def distinct(self, *args, **kwargs):
        result = super().distinct(*args, **kwargs)
        if result is None and getattr(self, '_probing', False):
            self._uncertain.append('stored entries incomplete for one-row check')
        return result


def form_starts(ids, model, names):
    return [i for i,(t,m) in enumerate(zip(ids,model)) if m and
            names[t] in ('RULE','DET','INIT','OUT','CHOOSE','RIGID_DET')]


class PrefixRows:
    """Use all available stored prefix snapshots; never infer missing rows."""
    def __init__(self, sources, issues):
        self.sources=sources;self.issues=issues
        self.optimistic=False;self.unavailable=[]

    def one_row(self,k,sites,head):
        reasons=[];answers=[];receipts=[]
        for source in self.sources:
            source.optimistic=False;source.unavailable=[]
            answer=source.one_row(k,sites,head)
            probe=source.probes[(int(k),canonical(sites),head)]
            lay=source.lays.get(k)
            receipts.append(dict(reference=source.source_receipt,
                table_present=k in source.tabs,layout_kind=lay.get('kind') if lay else None,
                entry_kinds=dict(Counter(str(e[2]) for e in lay['entries'])) if lay else {},
                reasons=probe[1]))
            # A definitive multi-row result at any observed input suffices to
            # disprove one-row. Only actual mapped/complete observations count.
            if not probe[1] and not answer:return False
            if answer:answers.append(True)
            reasons.extend(probe[1])
        if answers:return True
        detail=dict(relation=int(k),sites=sites,head=head,
                    sources=receipts,
                    reasons=sorted(set(reasons or self.issues or ['stored prefix snapshots absent'])))
        if detail not in self.unavailable:self.unavailable.append(detail)
        return self.optimistic


class Context:
    def __init__(self, corpus, task):
        self.task = task
        manifest = Path(corpus) / task / 'manifest.json'
        self.manifest = json.loads(manifest.read_text())
        self.export = Path(self.manifest['config']['export']).resolve()
        vp = self.export / 'vocab.json'
        vocab = json.loads(vp.read_text())
        self.vocab = writer.Vocab(vocab['names'], vocab['kinds'])
        # Shape needs registry domain metadata, though normal itself does not.
        self.receipt = dict(manifest=str(manifest), manifest_sha256=sha(manifest),
                            vocab=str(vp), vocab_sha256=sha(vp))
        self.stream_path = self.export / 'tasks' / task / 'cases.npz'
        z = np.load(self.stream_path, allow_pickle=False)
        self.streams = {}
        for i, case in enumerate(z['case'].tolist()):
            lo, hi = z['offsets'][i:i+2]
            self.streams[case] = (z['ids'][lo:hi].tolist(), z['model'][lo:hi].tolist())
        z.close()
        self.receipt.update(stream_file=str(self.stream_path), stream_sha256=sha(self.stream_path))
        self.rows_cache = {}

    def shape(self, ids, model, point):
        # A source point's first path index identifies its complete top-level
        # writer form. INIT's segments/key exemption are handled by Shape.
        starts = form_starts(ids,model,self.vocab.names)
        if not 0 <= point < len(starts):
            raise ValueError('changed form is absent from stored stream')
        lo = starts[point]; hi = starts[point+1] if point+1 < len(starts) else len(ids)
        s = writer.Shape(self.vocab)
        positions = [i for i in range(lo, hi) if model[i]]
        if not positions:
            raise ValueError('changed form has no model tokens')
        for j, pos in enumerate(positions):
            end = positions[j+1] if j+1 < len(positions) else hi
            s.feed(ids[pos], ids[pos+1:end])
        if s.head in writer.HEADED and not s.ended:
            raise ValueError('stored stream did not close writer form')
        return s, (lo, hi)

    def prefix_rows(self, record, base, gold):
        sources=[];issues=[];seen=set()
        for ref in (record.get('full_replay',{}).get('gold'),record.get('native',{}).get('gold')):
            if not ref or digest(ref) in seen:continue
            seen.add(digest(ref));key=(record['case'],digest(ref))
            try:
                if key not in self.rows_cache:
                    raw=storage.load_native(ref,base)
                    self.rows_cache[key]=StoredRows(StoredSource(raw,self.task,record['case']),
                        self.task,record['case'],*gold,self.vocab.names,self.vocab.kinds)
                    self.rows_cache[key].source_receipt=ref
                    if len(self.rows_cache)>8:self.rows_cache.pop(next(iter(self.rows_cache)))
                sources.append(self.rows_cache[key])
            except (OSError,ValueError,KeyError) as error:
                issues.append('stored native prefix unavailable: '+str(error))
        return PrefixRows(sources,issues)

    def classify(self, record, base):
        case = record['case']; point = record['point'][0]
        gold = self.streams[case]
        mutant = record['mutant_stream']
        # Stored token paths independently check the selected top-level index.
        if len(mutant['paths']) != len(mutant['ids']):
            raise ValueError('mutant token/path length differs')
        results = {}
        # Authenticate the shared prefix against the stored mutant stream. No
        # changed-form or downstream relation is used as its own prefix evidence.
        _, gold_span = self.shape(*gold, point)
        _, mutant_span = self.shape(mutant['ids'], mutant['model'], point)
        if (gold[0][:gold_span[0]] != mutant['ids'][:mutant_span[0]] or
                gold[1][:gold_span[0]] != mutant['model'][:mutant_span[0]]):
            raise ValueError('gold export and stored mutant have different prefixes')
        ref = record.get('full_replay', {}).get('gold')
        rows = None
        for name, (ids, model) in [('gold', gold), ('mutant', (mutant['ids'], mutant['model']))]:
            s, span = self.shape(ids, model, point)
            if name == 'mutant' and any(not p or p[0] != point for p in mutant['paths'][span[0]:span[1]]):
                raise ValueError('stream form boundary differs from stored native paths')
            if s.head not in writer.CONSTRAINT_SETS['normal']['normal form']:
                results[name] = dict(normal=True, writer_pass=True, applicable=False, head=s.head)
                continue
            s.rows=None
            structural_pass=bool(writer.passes(s,'normal form'))
            class UnknownRows:
                def one_row(self,*args):return True
            s.rows=UnknownRows()
            structural_possible=bool(writer.passes(s,'normal form'))
            row_independent=structural_pass or not structural_possible
            if row_independent:
                verdict=structural_pass;gaps=[]
            else:
                if rows is None:rows=self.prefix_rows(record,base,gold)
                rows.optimistic=False;rows.unavailable=[];s.rows=rows
                verdict=bool(writer.passes(s,'normal form'))
                gaps=list(rows.unavailable)
            # The writer fails closed when row evidence is missing. Preserve its
            # exact verdict and distinguish an actual failure from unavailable
            # evidence: if even optimistic one-row answers fail, failure is proved.
            optimistic = verdict
            if not verdict and not row_independent:
                if rows is not None:
                    rows.optimistic = True
                    try:
                        optimistic = bool(writer.passes(s, 'normal form'))
                    finally:
                        rows.optimistic = False
            normal = True if verdict else None if optimistic else False
            results[name] = dict(normal=normal, writer_pass=verdict, applicable=True, head=s.head,
                                 status='unavailable' if normal is None else 'classified',
                                 row_independent=row_independent,
                                 unavailable=gaps, token_span=list(span),
                                 stream_sha256=digest([ids, model]))
            if name=='gold' and normal is False:
                failed=defaultdict(list)
                for component in writer.components(s,{a['seg'] for a in s.atoms if a['args']}-{s.key_seg}):
                    prior_optimism=getattr(s.rows,'optimistic',None)
                    if prior_optimism is not None:s.rows.optimistic=True
                    try:possible=writer.one_row_component(s,component)
                    finally:
                        if prior_optimism is not None:s.rows.optimistic=prior_optimism
                    if not possible:
                        failed[component[0]['seg']].append([
                            dict(relation=self.vocab.names[a['rel']],negated=a['neg'],sites=a['sites'])
                            for a in component])
                results[name]['failure_segments']=[dict(segment=seg,non_one_row_components=components)
                    for seg,components in failed.items() if len(components)>1]
        return dict(**results, inputs=dict(**self.receipt, native_gold=ref,
                                          native_prefix_gold=record.get('native',{}).get('gold'),
                                          prefix_policy='unchanged earlier forms from stored full gold replay'))


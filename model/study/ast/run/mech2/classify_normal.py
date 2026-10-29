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
STUDY = HERE.parents[2]
RUN = HERE.parent
sys.path[:0] = [str(RUN / 'mech'), str(RUN), str(STUDY)]
from run import canonical, digest, pair_key
import native_storage as storage
from native_tables import width as native_width
import writer
import numpy as np
import pandas as pd

SCHEMA = 'stored-normal-form-v1'
# Completed results from this producer never reached CaseRows' broken setup:
# any such call raised before returning a verdict. The transport repair changes
# only those unavailable results. Other imported policy sources must match.
REPAIR_PREDECESSOR = '1b6b6ecef473ad460efdc407248c0cf1894824e89a80ecdbb19d537b75592309'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def policy_manifest():
    # Hash actual imported dependencies as well as the policy and adapter.
    import detectors
    paths = [Path(__file__), Path(writer.__file__), Path(storage.__file__),
             RUN / 'native_tables.py',
             RUN / 'mech/run.py', Path(detectors.__file__), Path(detectors.E.__file__),
             STUDY / 'pinned.py', Path(writer.ROOT) / 'engine/lib/registry.sexpr']
    paths += [CODE_ROOT / 'study_paths.py']
    logical = {str(p.relative_to(CODE_ROOT)) if p.is_relative_to(CODE_ROOT)
               else 'pinned/encoder.py' if p == Path(detectors.E.__file__)
               else 'engine/lib/registry.sexpr': sha(p) for p in paths}
    paths += [HERE / 'migration-compatibility.json']
    return dict(schema=SCHEMA, constraint_set='normal',logical_files=logical,
                files={str(p.resolve()): sha(p) for p in paths},
                numpy=np.__version__, pandas=pd.__version__)


def compatible_migration(previous, current):
    """Authenticate reviewed legacy policy or identical code at another checkout."""
    if previous.get('logical_files') == current['logical_files']:
        return True
    receipt = json.loads((HERE / 'migration-compatibility.json').read_text())
    if digest(previous) not in receipt['legacy_manifest_sha256']:
        return False
    entry = 'ast/run/mech2/classify_normal.py'
    dependencies = {p:h for p,h in current['logical_files'].items() if p != entry}
    tree = ast.parse(Path(__file__).read_text())
    policy = {node.name:ast.dump(node,include_attributes=False) for node in tree.body
              if isinstance(node,ast.ClassDef) and node.name in ('StoredSource','StoredRows','Context')}
    return (dependencies == receipt['migrated_dependencies']
            and digest(policy) == receipt['classification_ast_sha256']
            and all(previous[k] == current[k] for k in ('schema','constraint_set','numpy','pandas')))


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
        if cols is None and getattr(self, '_probing', False):
            lay=self.lays.get(args[0])
            if lay is not None:
                self._uncertain.append('column-to-native projection unavailable')
        return cols

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
        return dict(**results, inputs=dict(**self.receipt, native_gold=ref,
                                          native_prefix_gold=record.get('native',{}).get('gold'),
                                          prefix_policy='unchanged earlier forms from stored full gold replay'))


def unavailable_causes(db):
    """Exclusive groups of causes; each pair/point contributes once."""
    out={}
    for table,key,name in [('pairs','mutant','mutants'),('gold_points',None,'gold_points')]:
        counts=Counter()
        for text, in db.execute('SELECT record_json FROM '+table+' WHERE normal IS NULL'):
            record=json.loads(text);result=record[key] if key else record
            causes={reason for probe in result.get('unavailable',[]) for reason in probe.get('reasons',[])}
            if result.get('reason'):causes.add(result['reason'])
            for probe in result.get('unavailable',[]):
                if probe.get('reason'):causes.add(probe['reason'])
            counts[tuple(sorted(causes or {'diagnostic absent'}))]+=1
        out[name]=dict(total=sum(counts.values()),groups=[dict(causes=list(c),count=n) for c,n in sorted(counts.items())])
    return out


CAUSE_MEANINGS = {
    'native prefix relation absent':'No stored candidate snapshot contains the requested prefix relation.',
    'native prefix relation identity ambiguous':'Stored native relation identity does not select one table.',
    'native prefix relation faulted':'The native snapshot records a fault instead of usable relation rows.',
    'native prefix relation entries absent':'Table metadata exists without the input/model entries needed for row counts.',
    'stored entries incomplete for one-row check':'An entry is stopped/undefined or stores only a multi-row count; its distinct projection cannot be recovered from that count.',
    'column-to-native projection unavailable':'The existing writer mapper cannot establish the requested column projection. This is an unresolved adapter/metadata limitation, not a proof that the data cannot decide it.',
    'stored stream declaration absent':'A required declaration could not be matched in the stored stream; investigate the adapter or source integrity.',
}


def summarize(db, path, total):
    rows = db.execute('SELECT base_label, operation, K, normal, count(*) FROM pairs GROUP BY 1,2,3,4').fetchall()
    by = defaultdict(Counter)
    counts = Counter()
    for label, operation, k, normal, n in rows:
        status = 'unavailable' if normal is None else 'normal' if normal else 'non_normal'
        counts[status] += n
        for dimension, value in [('base_label', label), ('operation', operation), ('K', str(k))]:
            by[dimension, value][status] += n
    gold = Counter()
    for normal, n in db.execute('SELECT normal,count(*) FROM gold_points GROUP BY normal'):
        gold['unavailable' if normal is None else 'normal' if normal else 'non_normal'] += n
    failures = [dict(point_id=i, task=t, case=c, point=json.loads(p), clause=json.loads(cl))
                for i,t,c,p,cl in db.execute('SELECT point_id,task,case_name,point,clause FROM gold_points WHERE normal=0 ORDER BY task,case_name,point')]
    result = dict(schema=SCHEMA, base_total=total, classified=sum(counts.values()), mutants=dict(counts),
                  unavailable_causes=unavailable_causes(db),
                  unavailable_cause_meanings=CAUSE_MEANINGS,
                  by={dim: {v: dict(n) for (d,v),n in by.items() if d==dim}
                      for dim in ('base_label','operation','K')},
                  joint=[dict(base_label=l, operation=o, K=k, normal=n, count=c) for l,o,k,n,c in rows],
                  gold_points=dict(gold), failing_gold_points=failures,
                  coverage='Stored base pairs only. Corpus runtime/load omissions and deadline-limited mutants are absent.')
    previous=db.execute("SELECT value FROM metadata WHERE key='repair_input_unavailable'").fetchone()
    if previous:result['repair_input_unavailable_causes']=json.loads(previous[0])
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(result, indent=2)+'\n'); temp.replace(path)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output', type=Path, default=DATA_ROOT / 'ast/run/mech2/normal.sqlite3')
    ap.add_argument('--summary', type=Path, default=DATA_ROOT / 'ast/run/mech2/summary.json')
    ap.add_argument('--retry-unavailable', action='store_true',
                    help='retry only existing null mutant attributes; preserve classified rows')
    a = ap.parse_args()
    a.output = a.output.resolve()
    if a.output.parent != DATA_ROOT/'ast/run/mech2' or a.summary.resolve().parent != DATA_ROOT/'ast/run/mech2':
        ap.error('outputs must be in mech2')
    lock = a.output.with_suffix('.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    code = policy_manifest(); code_hash = digest(code)
    base = sqlite3.connect(a.base.resolve().as_uri()+'?mode=ro', uri=True)
    db = sqlite3.connect(a.output)
    db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS pairs(pair_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,
        base_result_sha256 TEXT NOT NULL,code_sha256 TEXT NOT NULL,result_sha256 TEXT NOT NULL,
        normal INTEGER, gold_point_id TEXT NOT NULL, base_label TEXT, operation TEXT,K INTEGER,record_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS gold_points(point_id TEXT PRIMARY KEY,task TEXT,case_name TEXT,
        point TEXT,clause TEXT,normal INTEGER,record_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS code_manifests(code_sha256 TEXT PRIMARY KEY,manifest_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS compatible_codes(code_sha256 TEXT PRIMARY KEY,current_code_sha256 TEXT NOT NULL,reason TEXT NOT NULL);
    ''')
    previous_code = db.execute("SELECT value FROM metadata WHERE key='code_manifest'").fetchone()
    accepted_codes = {code_hash}
    if previous_code:
        previous_manifest = json.loads(previous_code[0]); previous_hash = digest(previous_manifest)
        db.execute('INSERT OR IGNORE INTO code_manifests VALUES (?,?)', (previous_hash,previous_code[0]))
        prior_compat = {p for p, in db.execute('SELECT code_sha256 FROM compatible_codes WHERE current_code_sha256=?',(previous_hash,))}
        if compatible_migration(previous_manifest,code):
            accepted_codes.add(previous_hash)
            accepted_codes.update(prior_compat)
        elif previous_hash == REPAIR_PREDECESSOR:
            old_files = {p:h for p,h in previous_manifest['files'].items() if p != str(Path(__file__).resolve())}
            new_files = {p:h for p,h in code['files'].items() if p != str(Path(__file__).resolve())}
            if old_files != new_files or any(previous_manifest[k]!=code[k] for k in ('schema','constraint_set','numpy','pandas')):
                raise ValueError('repair compatibility requires unchanged writer and dependency receipts')
            accepted_codes.add(previous_hash)
        elif previous_hash == code_hash:
            accepted_codes.update(prior_compat)
        elif a.retry_unavailable:
            raise ValueError('unreviewed predecessor: cannot preserve classified rows')
    elif a.retry_unavailable:
        raise ValueError('--retry-unavailable requires an existing completed output')
    if previous_code and previous_hash not in accepted_codes:
        db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',
                   ('repair_input_unavailable',canonical(unavailable_causes(db))))
        db.execute('DELETE FROM gold_points')
    db.execute('INSERT OR REPLACE INTO code_manifests VALUES (?,?)',(code_hash,canonical(code)))
    for previous_hash in accepted_codes - {code_hash}:
        db.execute('INSERT OR REPLACE INTO compatible_codes VALUES (?,?,?)',
                   (previous_hash,code_hash,'Reviewed source migration or table identity/atomic setup repair; completed predecessor verdicts unchanged'))
    db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('code_manifest',canonical(code)))
    db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('schema',SCHEMA));db.commit()
    total = base.execute('SELECT count(*) FROM pairs').fetchone()[0]
    state = dict(done=0, skipped=0, phase='index', total=total)
    start = time.monotonic(); stop = threading.Event()
    def progress():
        elapsed = time.monotonic()-start; rate=state['done']/max(elapsed,.001)
        eta=(total-state['done'])/rate if rate else None
        print(f"done={state['done']}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s ETA={eta if eta is not None else 'unknown'}s skipped={state['skipped']} phase={state['phase']}",flush=True)
    def heartbeat():
        while not stop.wait(5): progress()
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    try:
        old={p:(s,b,c,h,n) for p,s,b,c,h,n in db.execute('SELECT pair_id,source_sha256,base_result_sha256,code_sha256,result_sha256,normal FROM pairs')}
        wanted=defaultdict(dict)
        for pid, source_hash, base_hash, text in base.execute('SELECT pair_id,source_sha256,result_sha256,record_json FROM pairs'):
            valid = (pid in old and old[pid][:2] == (source_hash,base_hash)
                     and old[pid][2] in accepted_codes)
            if valid:
                saved=db.execute('SELECT record_json FROM pairs WHERE pair_id=?',(pid,)).fetchone()[0]
                valid = digest(json.loads(saved))==old[pid][3]
                if valid and not (a.retry_unavailable and old[pid][4] is None):
                    state['done']+=1;state['skipped']+=1;continue
            if a.retry_unavailable and not valid:
                raise ValueError('retry requires a valid existing receipt for '+pid)
            rec=json.loads(text)
            if digest(rec)!=base_hash or rec['pair_id']!=pid or rec['source_sha256']!=source_hash:
                raise ValueError('invalid base row '+pid)
            source=rec['source'];corpus=Path(source['corpus']).resolve()
            path=corpus/rec['task']/source['file']
            # Preserve separate base aliases pointing to the same source line.
            wanted[str(path)].setdefault(source['line'],[]).append(dict(pair_id=pid,
                source_sha256=source_hash,base_result_sha256=base_hash,base_label=rec.get('label'),
                operation=rec.get('operation'),K=rec.get('K'),task=rec['task'],case=rec['case'],
                point=rec['point'],clause=rec['clause']))
        def write(item, result, source):
            point={k:item[k] for k in ('task','case','point','clause')};point_id=digest(point)
            record=dict(schema=SCHEMA,**item,code_sha256=code_hash,source=source,
                        gold_point_id=point_id,**result)
            normal=result['mutant']['normal']; gold=result['gold']
            db.execute('INSERT OR REPLACE INTO pairs VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (item['pair_id'],item['source_sha256'],item['base_result_sha256'],code_hash,digest(record),
                 normal,point_id,item['base_label'],item['operation'],item['K'],canonical(record)))
            previous=db.execute('SELECT record_json FROM gold_points WHERE point_id=?',(point_id,)).fetchone()
            gp=dict(**point,**gold)
            if previous:
                prev=json.loads(previous[0]); vals={v for v in (prev.get('normal'),gold['normal']) if v is not None}
                if len(vals)>1: raise ValueError('inconsistent stored gold verdict '+point_id)
                if prev.get('normal') is not None:gp=prev
            db.execute('INSERT OR REPLACE INTO gold_points VALUES (?,?,?,?,?,?,?)',
                (point_id,item['task'],item['case'],canonical(item['point']),canonical(item['clause']),gp['normal'],canonical(gp)))
            db.commit();state['done']+=1
        for file, lines in sorted(wanted.items()):
            path=Path(file); state['phase']=file
            context=None; remaining=set(lines)
            try:
                with gzip.open(path,'rt') as fh:
                    for line,text in enumerate(fh,1):
                        if line not in remaining:continue
                        source=json.loads(text);remaining.remove(line)
                        for item in lines[line]:
                            locator=dict(corpus=str(path.parent.parent),file=str(path),line=line)
                            try:
                                if digest(source)!=item['source_sha256'] or digest(pair_key(source))!=item['pair_id']:
                                    raise ValueError('source receipt differs')
                                if context is None:context=Context(path.parent.parent,item['task'])
                                result=context.classify(source,path.parent)
                            except Exception as error:
                                unknown=dict(normal=None,writer_pass=None,status='unavailable',reason=f'{type(error).__name__}: {error}')
                                result=dict(mutant=unknown,gold=unknown)
                            write(item,result,locator)
                        if not remaining:break
                if remaining:raise ValueError('source file ended before requested lines')
            except (OSError,EOFError,ValueError) as error:
                for line in sorted(remaining):
                    for item in lines[line]:
                        unknown=dict(normal=None,writer_pass=None,status='unavailable',reason=f'{type(error).__name__}: {error}')
                        write(item,dict(mutant=unknown,gold=unknown),dict(file=file,line=line))
        state['phase']='summary'
        summary=summarize(db,a.summary,total);progress()
        print(canonical(dict(mutants=summary['mutants'],gold_points=summary['gold_points'],summary=str(a.summary))),flush=True)
    finally:
        stop.set();thread.join();db.close();base.close()


if __name__=='__main__':main()

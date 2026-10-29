#!/usr/bin/env python3
"""Bounded Workflow scripts and authenticated clause submissions.

Adapted from DATA_ROOT/judge2/judge_workflows.py: same child Promise.all,
sequential parent, strict script byte cap, frozen routing/hash validation,
actual started/result journal proof, and preflight-before-publish ingestion.
The retired label/prompt-pool contract is replaced by ordinary pair files,
checked tool results and judge-submission-v1. This script launches no agent.
"""
import argparse
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile
import time
import uuid
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT,DATA_ROOT,MAIN_ROOT
if __package__:
    from .make_batches import save,data_path,calls
    from .result_records import load_checked_result
else:
    from make_batches import save,data_path,calls
    from result_records import load_checked_result

SCRIPT_BYTES=500_000


def digest(value):return hashlib.sha256(value).hexdigest()
def literal(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('\u2028','\\u2028').replace('\u2029','\\u2029')
def identity(path):
    path=data_path(path)
    return dict(path=path.relative_to(DATA_ROOT).as_posix(),sha256=digest(path.read_bytes()))
def resolve(relative):
    path=Path(relative)
    if path.is_absolute() or '..' in path.parts:raise ValueError('expected canonical DATA-relative path')
    result=data_path(DATA_ROOT/path)
    if result.relative_to(DATA_ROOT).as_posix()!=relative:raise ValueError('noncanonical DATA-relative path')
    return result

def read_identity(ref):
    path=resolve(ref['path']);raw=path.read_bytes()
    if digest(raw)!=ref['sha256']:raise ValueError('file identity differs: '+str(path))
    return json.loads(raw)


@contextmanager
def run_lock(directory):
    with (directory/'INGEST.lock').open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);yield


def reply_schema():
    return dict(type='object',additionalProperties=False,required=['pair_id','answer_path'],properties=dict(pair_id=dict(type='string'),answer_path=dict(type='string')))


def child_script(pairs):
    # Retain old bounded concurrency/stop behavior; no label or grade field.
    return ("export const meta = "+literal(dict(name='pair-judge-child',description='One Sonnet session per data pair'))+"\n"
        "const pairs = "+literal(pairs)+"\nconst schema = "+literal(reply_schema())+"\nlet stop = false\n"
        "const completed = await Promise.all(pairs.map(async pair => {\n"
        "  if (stop) return {pair_id: pair.pair_id, skipped: true}\n"
        "  try {\n"
        "    const reply = await agent(pair.prompt, {model: 'sonnet', agentType: 'general-purpose', label: pair.pair_id,\n"
        "      schema: {...schema, properties: {...schema.properties, pair_id: {type: 'string', const: pair.pair_id}, answer_path: {type: 'string', const: pair.answer_path}}}})\n"
        "    if (reply === null) stop = true\n"
        "    return {pair_id: pair.pair_id, reply}\n"
        "  } catch (error) { stop = true; return {pair_id: pair.pair_id, reply: null, error: String(error)} }\n"
        "}))\nreturn {replies: completed.filter(x => !x.skipped), skipped: completed.filter(x => x.skipped).map(x => x.pair_id)}\n").encode()


def parent_script(children):
    return ("export const meta = "+literal(dict(name='pair-judge-run',description='Run bounded pair-judge child scripts'))+"\n"
        "const children = "+literal(children)+"\nconst replies = [], skipped = []\nlet stop = false\n"
        "for (const child of children) {\n"
        "  if (stop) { skipped.push(...child.pair_ids); continue }\n"
        "  const result = await workflow({scriptPath: child.scriptPath})\n"
        "  replies.push(...result.replies); skipped.push(...result.skipped)\n"
        "  if (result.replies.some(x => x.reply === null)) stop = true\n"
        "}\nreturn {replies, skipped}\n").encode()


def script_literal(content,name):
    prefix='const '+name+' = '
    found=[line[len(prefix):] for line in content.decode().splitlines() if line.startswith(prefix)]
    if len(found)!=1:raise ValueError('script lacks one literal '+name)
    return json.loads(found[0])


def dataset_binding(directory):
    """Hash every supplied public file, no table-row decoding or admission."""
    index=json.loads((directory/'pair.json').read_text())
    if index.get('format')!='judge-dataset-v1' or index.get('kind')!='pair':raise ValueError('not a current pair dataset')
    if any(t.get('complete') is not True or t.get('missing') for t in index['tables']):raise ValueError('incomplete public tables')
    for table in index['tables']:
        path=(directory/table['path']).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError('public table file missing or outside pair directory')
    files=[]
    for path in sorted(directory.rglob('*')):
        if path.is_file():files.append(identity(path))
    context_path=DATA_ROOT/'judgetool/dataset-contexts'/(index['pair_id']+'.json')
    context=json.loads(context_path.read_text())
    manifest_path=Path(context['source_pair'])/'manifest.json';manifest=json.loads(manifest_path.read_text())
    if manifest['pair_id']!=index['pair_id']:raise ValueError('private/public pair identity differs')
    source=Path(manifest['adapter']['source']['record_path']).resolve();raw=source.read_bytes()
    record=json.loads(gzip.decompress(raw) if source.suffix=='.gz' else raw)
    source_sha=digest(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    if source_sha!=context['source_sha256']:raise ValueError('dataset source identity differs')
    return dict(pair_id=index['pair_id'],source_sha256=source_sha,pair_dir=str(directory),files=files,
                context=identity(context_path),source_manifest=identity(manifest_path),source_record=identity(source))


def prompt_text(work,pair):
    return f'''You are the pair judge. Read {work/'brief.md'} and work only the pair data in {pair['pair_dir']}. Use the brief, pair files, inline Python and the three clause commands. Do not read previous reviews, preparation files, private records or implementation source.

In each shell call source {work/'env.sh'}; work in {work}. Use ./judge run|check|alternative --clause-file FILE --output NEW_DIRECTORY [--columns JSON_LIST], choosing one command per invocation. The environment supplies PAIR_DIR, WORK_DIR, PYTHON and TOOL. Inspect selected JSON fields first; do not print every table or repeat directory listings. Load Python environment values through os.environ.

Find checked recoveries or alternatives, or report no clause found. Write {work/'answer.json'} as JSON with exactly schema="judge-answer-v1", pair_id="{pair['pair_id']}", and clauses (an array). Each clause item has exactly kind (recovery|alternative), clause_file (absolute path to the exact UTF-8 clause file checked), columns (the explicit output-label list passed, or null when omitted), result_path (absolute checked result.json path), and reasons (one or two evidence strings). Do not give a label, grade, outcome claim or completion flag. Empty clauses means no clause found; exploratory run results are not answers.

Return only pair_id and answer_path="{work/'answer.json'}" through the supplied structured reply. Do not repeat the answer artifact. The host derives outcomes from the stored checked results, not your reasons.
'''


def create(args):
    directory=data_path(args.output_dir);snapshot=args.tool_snapshot.resolve()
    if snapshot.parent!=MAIN_ROOT/'.claude/runs' or not re.fullmatch(r'[0-9a-f]{40}',snapshot.name):raise ValueError('--tool-snapshot must be MAIN_ROOT/.claude/runs/<40hex>')
    tool=snapshot/'model/study/judgetool/judge_tool.py'
    if not tool.is_file():raise ValueError('snapshot tool missing')
    python=Path(args.python).absolute()
    if not python.is_file():raise ValueError('runtime Python missing')
    if args.sessions_per_child<1:raise ValueError('sessions per child must be positive')
    if directory.exists():raise ValueError('run output must be new; never overwrite an active session')
    directory.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.'+directory.name+'.',dir=directory.parent))
    rows=[];group=[];children=[];scripts={};start=time.monotonic();run_id=uuid.uuid4().hex
    try:
        (stage/'sessions').mkdir()
        def write_child():
            content=child_script(group)
            if len(content)>=SCRIPT_BYTES:raise ValueError('child exceeds strict script byte limit')
            name=f'child-{len(children)+1:04d}.js';(stage/name).write_bytes(content);scripts[name]=digest(content)
            children.append(dict(scriptPath=str(directory/name),pair_ids=[x['pair_id'] for x in group]))
        for call in calls(args.calls):
            binding=dataset_binding(Path(call['pair_dir']));pid=binding['pair_id']
            work=directory/'sessions'/pid;dest=stage/'sessions'/pid;dest.mkdir()
            shutil.copyfile(args.brief,dest/'brief.md')
            env=dict(WORK_DIR=str(work),PAIR_DIR=binding['pair_dir'],PYTHON=str(python),TOOL=str(tool))
            (dest/'env.sh').write_text(''.join('export '+k+'='+shlex.quote(v)+'\n' for k,v in env.items())+'cd "$WORK_DIR"\n')
            (dest/'judge').write_text('#!/bin/zsh\nset -eu\nsource '+shlex.quote(str(work/'env.sh'))+'\nexec "$PYTHON" "$TOOL" --pair "$PAIR_DIR" "$@"\n');(dest/'judge').chmod(0o755)
            prompt=prompt_text(work,binding);(dest/'prompt.txt').write_text(prompt)
            item=dict(pair_id=pid,answer_path=str(work/'answer.json'),prompt=prompt)
            if len(child_script([item]))>=SCRIPT_BYTES:raise ValueError('single pair exceeds script size cap')
            if group and (len(group)>=args.sessions_per_child or len(child_script(group+[item]))>=SCRIPT_BYTES):write_child();group=[]
            group.append(item)
            rows.append(dict(binding,session_id=run_id+':'+pid,answer_path=item['answer_path'],work_dir=str(work),prompt_sha256=digest(prompt.encode()),
                session_files={name:digest((dest/name).read_bytes()) for name in ('brief.md','env.sh','judge','prompt.txt')}))
            print(f'prepared {len(rows)} elapsed={time.monotonic()-start:.1f}s pair={pid}',file=sys.stderr,flush=True)
        if not rows:raise ValueError('empty calls file')
        if group:write_child()
        content=parent_script(children)
        if len(content)>=SCRIPT_BYTES:raise ValueError('parent exceeds strict script size cap; split calls with make_batches')
        (stage/'parent.js').write_bytes(content);scripts['parent.js']=digest(content)
        manifest=dict(schema='pair-judge-workflow-v2',run_id=run_id,parent=str(directory/'parent.js'),pairs=rows,children=children,scripts=scripts,
            config=dict(model='sonnet',sessions_per_child=args.sessions_per_child,tool_snapshot=str(snapshot),tool_sha256=digest(tool.read_bytes()),python=str(python)),
            calls=identity(args.calls),producer=dict(path=str(Path(__file__).resolve()),sha256=digest(Path(__file__).read_bytes())))
        save(stage/'run.json',manifest);stage.rename(directory)
    finally:
        if stage.exists():shutil.rmtree(stage)
    print(json.dumps(dict(parent=str(directory/'parent.js'),pairs=len(rows),children=len(children))),flush=True)


def verify_run(directory):
    manifest=json.loads((directory/'run.json').read_text())
    if manifest.get('schema')!='pair-judge-workflow-v2' or manifest['parent']!=str(directory/'parent.js'):raise ValueError('unsupported/misrouted workflow run')
    if manifest['config']['model']!='sonnet':raise ValueError('workflow model differs')
    if 'parent.js' not in manifest['scripts'] or len(manifest['scripts'])<2:raise ValueError('parent/child scripts missing')
    snapshot=Path(manifest['config']['tool_snapshot'])
    if snapshot.parent!=MAIN_ROOT/'.claude/runs' or not re.fullmatch(r'[0-9a-f]{40}',snapshot.name):raise ValueError('invalid frozen tool snapshot')
    tool=snapshot/'model/study/judgetool/judge_tool.py'
    if digest(tool.read_bytes())!=manifest['config']['tool_sha256']:raise ValueError('snapshot tool changed')
    expected={p['pair_id']:p for p in manifest['pairs']}
    if len(expected)!=len(manifest['pairs']):raise ValueError('duplicate scheduled pair')
    groups=[]
    for name,sha in manifest['scripts'].items():
        path=directory/name
        if path.resolve().parent!=directory:raise ValueError('script path escapes run')
        content=path.read_bytes()
        if digest(content)!=sha or len(content)>=SCRIPT_BYTES:raise ValueError('script hash/size differs')
        if name=='parent.js':
            if script_literal(content,'children')!=manifest['children']:raise ValueError('parent routing differs')
        else:
            pairs=script_literal(content,'pairs')
            if script_literal(content,'schema')!=reply_schema() or len(pairs)>manifest['config']['sessions_per_child']:raise ValueError('child reply schema/concurrency differs')
            groups.append((str(path),[p['pair_id'] for p in pairs]))
            for p in pairs:
                row=expected[p['pair_id']]
                if p['answer_path']!=row['answer_path'] or digest(p['prompt'].encode())!=row['prompt_sha256']:raise ValueError('child prompt/answer routing differs')
    if set(groups_as_paths:=[g[0] for g in groups])!={x['scriptPath'] for x in manifest['children']} or len(groups_as_paths)!=len(set(groups_as_paths)):raise ValueError('child script set differs')
    routes=dict(groups)
    if any(routes[c['scriptPath']]!=c['pair_ids'] for c in manifest['children']):raise ValueError('child pair routing differs')
    if [p for c in manifest['children'] for p in c['pair_ids']]!=list(expected):raise ValueError('child order differs')
    for row in expected.values():
        public=data_path(row['pair_dir'])
        actual_files={data_path(p).relative_to(DATA_ROOT).as_posix() for p in public.rglob('*') if p.is_file()}
        if actual_files!={ref['path'] for ref in row['files']}:raise ValueError('frozen public file inventory changed')
        for ref in row['files']+[row['context'],row['source_manifest'],row['source_record']]:
            path=resolve(ref['path'])
            if digest(path.read_bytes())!=ref['sha256']:raise ValueError('frozen input changed: '+str(path))
        work=data_path(row['work_dir'])
        if work.parent!=directory/'sessions' or work.name!=row['pair_id']:raise ValueError('session directory routing differs')
        for name,sha in row['session_files'].items():
            if digest((work/name).read_bytes())!=sha:raise ValueError('launch file changed: '+name)
    return manifest,expected


def read_result(value):
    """Same observed outer Workflow envelope as the retired runner, no recursive search."""
    if not isinstance(value,dict):raise ValueError('unknown workflow result envelope')
    runner_fields={'summary','agentCount','logs','result'}
    if runner_fields<=set(value):
        if set(value)-runner_fields-{'workflowProgress','totalTokens','totalToolCalls'}:raise ValueError('unknown runner fields')
        if not isinstance(value['summary'],str) or type(value['agentCount']) is not int or not isinstance(value['logs'],list):raise ValueError('bad runner summary')
        value=value['result']
    if not isinstance(value,dict):raise ValueError('script result must be an object')
    if set(value)=={'children'} and isinstance(value['children'],list):
        blocks=[read_result(c) for c in value['children']]
        return dict(replies=[r for b in blocks for r in b['replies']],skipped=[r for b in blocks for r in b['skipped']])
    if set(value)!={'replies','skipped'} or not all(isinstance(value[k],list) for k in value):raise ValueError('unsupported script result')
    return value


def journal_proofs(paths,expected,directory):
    """Bind completed host replies to actual native started/result records."""
    result={}
    for path in paths:
        path=Path(path).resolve();raw=path.read_bytes();events=[json.loads(l) for l in raw.splitlines() if l.strip()]
        if not events or events[0]!={'type':'launched'}:raise ValueError('unsupported native workflow journal')
        starts={}
        for event in events[1:]:
            key=(event.get('key'),event.get('agentId'))
            if event.get('type')=='started':
                if not all(isinstance(v,str) and v for v in key):raise ValueError('native start lacks key/agent identity')
                if key in starts:raise ValueError('duplicate host start')
                starts[key]=event
            elif event.get('type')=='result':
                if key not in starts:raise ValueError('host result without matching start')
                started=starts[key];pid=started['label']
                if pid not in expected:continue
                if pid in result:raise ValueError('duplicate native completion for pair')
                frozen=directory/'host-receipts'/(digest(raw)+'.jsonl')
                result[pid]=dict(reply=event['result'],journal_bytes=raw,receipt=dict(
                    path=frozen.relative_to(DATA_ROOT).as_posix(),sha256=digest(raw),original_journal_path=str(path),workflow=path.parent.name,
                    agent_id=key[1],result_key=key[0],started_label=pid,started_phase=started.get('phase')))
            else:raise ValueError('unrecognized native journal event; do not infer completion')
    return result


def validate_answer(row,reply):
    if not isinstance(reply,dict) or set(reply)!={'pair_id','answer_path'} or reply['pair_id']!=row['pair_id'] or reply['answer_path']!=row['answer_path']:raise ValueError('reply does not match reserved pair/answer')
    answer_path=data_path(reply['answer_path']);answer_ref=identity(answer_path);answer=read_identity(answer_ref)
    if not isinstance(answer,dict) or set(answer)!={'schema','pair_id','clauses'} or answer['schema']!='judge-answer-v1' or answer['pair_id']!=row['pair_id'] or not isinstance(answer['clauses'],list):raise ValueError('invalid clause answer; labels/grades not accepted')
    selected=[];checked=[];envelopes=[];seen=set();work=Path(row['work_dir'])
    for clause in answer['clauses']:
        if not isinstance(clause,dict) or set(clause)!={'kind','clause_file','columns','result_path','reasons'} or clause['kind'] not in ('recovery','alternative'):raise ValueError('invalid selected clause')
        if not isinstance(clause['reasons'],list) or not 1<=len(clause['reasons'])<=2 or any(not isinstance(r,str) or not r.strip() for r in clause['reasons']):raise ValueError('clause needs one or two evidence reasons')
        columns=clause['columns']
        if columns is not None and (not isinstance(columns,list) or any(not isinstance(c,str) for c in columns)):raise ValueError('columns must be strings or null')
        if not Path(clause['result_path']).is_absolute() or not Path(clause['clause_file']).is_absolute():raise ValueError('clause/result paths must be absolute')
        result_path=data_path(clause['result_path']);clause_path=data_path(clause['clause_file'])
        if not result_path.is_relative_to(work) or not clause_path.is_relative_to(work):raise ValueError('clause/result must belong to this session')
        public=identity(result_path)
        if public['path'] in seen:raise ValueError('duplicate selected result')
        seen.add(public['path']);resolved=load_checked_result(result_path,expected_pair_id=row['pair_id'],expected_source_sha256=row['source_sha256'])
        if resolved.get('status')!='available':raise ValueError('checked result unavailable: '+resolved.get('reason',''))
        if (resolved['submitted_kind']!=clause['kind'] or resolved['operation']!=('check' if clause['kind']=='recovery' else 'alternative')
                or resolved['columns']!=columns or resolved['checked']['submitted_clause']!=clause_path.read_text()):raise ValueError('answer differs from actual checked clause/columns/kind')
        envelopes.append(resolved)
        selected.append(dict(public,submitted_kind=clause['kind'],outcome=resolved['checked']['outcome']))
        checked.append(dict(result=public,clause=identity(clause_path),identities=resolved['identities'],outcome=resolved['checked']['outcome']))
    return answer_ref,selected,checked,envelopes


def result_partition(expected,artifacts):
    """Validate the frozen host outputs; one parser for ingest and readers."""
    replies={};skipped=set()
    for ref in artifacts:
        result=read_result(read_identity(ref))
        for item in result['replies']:
            if not isinstance(item,dict) or set(item)-{'pair_id','reply','error'} or not {'pair_id','reply'}<=set(item):raise ValueError('bad reply envelope')
            pid=item['pair_id']
            if pid not in expected or pid in replies:raise ValueError('unknown/duplicate workflow reply')
            replies[pid]=item
        for pid in result['skipped']:
            if pid not in expected or pid in skipped:raise ValueError('unknown/duplicate skipped pair')
            skipped.add(pid)
    if set(replies)&skipped or set(replies)|skipped!=set(expected):raise ValueError('result disposition does not cover scheduled pairs exactly')
    return replies,skipped


def completed_submission(row,proof,artifacts,run_manifest):
    """The host's one completion boundary; no clause outcome is inferred."""
    answer,selected,checked,envelopes=validate_answer(row,proof['reply'])
    value=dict(schema='judge-submission-v1',pair_id=row['pair_id'],source_sha256=row['source_sha256'],session_id=row['session_id'],
        host_completion_status='completed',answer_artifact=answer,selected_results=selected,no_clause_found=not selected,
        termination_receipt=dict(proof['receipt'],run_manifest=run_manifest),workflow_results=artifacts,checked_results=checked)
    return value,envelopes


def load_submission(path,*,expected_pair_id=None,expected_source_sha256=None):
    """Read a completed host submission and its immutable evidence closure.

    Reuses the producer's routing, host partition, native journal, answer and
    checked-result validation. No locks, writes, native imports, replay or grade.
    Current producer/brief source bytes are not validity conditions.
    """
    try:
        path=Path(path)
        path=data_path(path) if path.is_absolute() else resolve(path.as_posix())
        submission=json.loads(path.read_text())
        fields={'schema','pair_id','source_sha256','session_id','host_completion_status',
                'answer_artifact','selected_results','no_clause_found','termination_receipt',
                'workflow_results','checked_results'}
        if not isinstance(submission,dict) or set(submission)!=fields or submission.get('schema')!='judge-submission-v1':raise ValueError('unsupported submission schema')
        if type(submission['no_clause_found']) is not bool:raise ValueError('no_clause_found must be boolean')
        if submission.get('host_completion_status')!='completed':raise ValueError('host did not complete this submission')
        pid=submission['pair_id'];term=submission['termination_receipt'];run_ref=term['run_manifest']
        if expected_pair_id is not None and pid!=expected_pair_id:raise ValueError('submission pair differs')
        if expected_source_sha256 is not None and submission['source_sha256']!=expected_source_sha256:raise ValueError('submission source differs')
        run_path=resolve(run_ref['path']);read_identity(run_ref)
        directory=run_path.parent
        if run_path.name!='run.json' or path!=directory/'submissions'/(pid+'.json'):raise ValueError('submission/run routing differs')
        manifest,expected=verify_run(directory)
        row=expected[pid]
        if row['source_sha256']!=submission['source_sha256'] or row['session_id']!=submission['session_id']:raise ValueError('submission source/session differs from run')
        artifacts=submission['workflow_results']
        replies,skipped=result_partition(expected,artifacts)
        if pid in skipped or replies[pid]['reply'] is None:raise ValueError('host result did not complete this pair')
        journal_ref={k:term[k] for k in ('path','sha256')}
        journal=resolve(journal_ref['path'])
        if identity(journal)!=journal_ref:raise ValueError('native journal identity differs')
        proofs=journal_proofs([journal],expected,directory);proof=proofs.get(pid)
        if proof is None or proof['reply']!=replies[pid]['reply']:raise ValueError('actual native host reply missing/different')
        for key in ('path','sha256','agent_id','result_key','started_label','started_phase'):
            if term[key]!=proof['receipt'][key]:raise ValueError('native termination '+key+' differs')
        # Original journal locators are historical metadata; the frozen copy
        # authenticates the same events even if the host cleans its directory.
        if term['workflow']!=Path(term['original_journal_path']).parent.name:raise ValueError('native journal locator differs')
        proof=dict(proof,receipt={k:v for k,v in term.items() if k!='run_manifest'})
        rebuilt,envelopes=completed_submission(row,proof,artifacts,run_ref)
        if rebuilt!=submission:raise ValueError('submission differs from authenticated answer/results')
        return dict(schema='judge-submission-resolution-v1',status='available',submission=submission,
            checked_results=envelopes,host_completion_authenticated=True,
            identities=dict(submission=identity(path),run_manifest=run_ref,termination=journal_ref,
                            workflow_results=artifacts,answer=submission['answer_artifact']))
    except (OSError,EOFError,ValueError,TypeError,KeyError,IndexError,AttributeError) as error:
        return dict(schema='judge-submission-resolution-v1',status='unavailable',
                    host_completion_authenticated=False,reason=f'{type(error).__name__}: {error}')


def ingest(args):
    directory=data_path(args.run);directory=directory.parent if directory.name=='run.json' else directory
    manifest,expected=verify_run(directory)
    with run_lock(directory):
        proofs=journal_proofs(args.journals,expected,directory)
        artifacts=[identity(data_path(path)) for path in args.results]
        replies,skipped=result_partition(expected,artifacts)
        pending=[];dispositions=[]
        for pid,row in expected.items():
            if pid in skipped:
                dispositions.append(dict(pair_id=pid,status='not_started',receipt='workflow script result'))
                continue
            item=replies[pid];proof=proofs.get(pid)
            if proof is None or proof['reply']!=item['reply']:raise ValueError('actual native host completion proof missing/different: '+pid)
            if item['reply'] is None:
                # Native null is skip or terminal error; never a completed empty answer.
                dispositions.append(dict(pair_id=pid,status='failed' if item.get('error') else 'interrupted',
                                         termination_receipt=proof['receipt']))
                continue
            value,_=completed_submission(row,proof,artifacts,identity(directory/'run.json'))
            pending.append((directory/'submissions'/(pid+'.json'),value))
        # Every answer/result preflight precedes any submission write.
        for path,value in pending:
            if path.exists() and json.loads(path.read_text())!=value:raise ValueError('conflicting immutable submission')
        for proof in proofs.values():
            target=resolve(proof['receipt']['path']);raw=proof['journal_bytes']
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and target.read_bytes()!=raw:raise ValueError('conflicting journal snapshot')
            if not target.exists():
                temporary=target.with_suffix('.next');temporary.write_bytes(raw);os.replace(temporary,target)
        save(directory/'dispositions.json',dict(schema='judge-workflow-dispositions-v1',items=dispositions))
        for path,value in pending:
            if not path.exists():save(path,value)
            print(json.dumps(dict(path=str(path),pair_id=value['pair_id'],status=value['host_completion_status'])),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);commands=p.add_subparsers(dest='command',required=True)
    c=commands.add_parser('create');c.add_argument('--calls',type=Path,required=True);c.add_argument('--output-dir',type=Path,required=True)
    c.add_argument('--tool-snapshot',type=Path,required=True);c.add_argument('--python',type=Path,required=True)
    c.add_argument('--brief',type=Path,default=Path(__file__).with_name('judge-brief.md'));c.add_argument('--sessions-per-child',type=int,default=3)
    i=commands.add_parser('ingest');i.add_argument('--run',type=Path,required=True);i.add_argument('--results',type=Path,nargs='+',required=True);i.add_argument('--journals',type=Path,nargs='+',required=True)
    a=p.parse_args();start=time.monotonic()
    try:create(a) if a.command=='create' else ingest(a)
    finally:print(f'[judge workflows] elapsed={time.monotonic()-start:.3f}s',file=sys.stderr,flush=True)


if __name__=='__main__':main()

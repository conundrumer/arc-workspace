#!/usr/bin/env python3
"""Write reading samples from rendered evidence; no program evaluation or tests."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import json
import os
import gzip
import shutil
import sys
import time
from pathlib import Path

import render_pair as current
from native import require
from headers import bind_body_schema
from assignments import Assignments
from components import attach_choice_extents
from definitions import context
from values import Values
from grids import reference_panels

ROOT = Path(__file__).resolve().parent
P = DATA_ROOT/'ref/progsynth-relabel'
SAMPLES = [
    ('01-rule', '3300bdd', 'RULE: direct G/X row comparison and available source-named tables.'),
    ('02-init', '63c82d', 'INIT: actual a/b/W input projection, separate from full witnesses and component outputs.'),
    ('03-det', 'a353bb', 'DET renderer example, explicitly outside judge admission: held contexts and proposal/held distinction.'),
    ('04-union', 'a7ef228', 'Union: X retains a large OR-derived relation; no automatic union contribution or nonredundancy claim.'),
    ('05-many-rows-lib', '94afe3', 'Many rows and lib recovery: 6,224 X tuples counted across kept contexts; inside/same_dist historical candidate.'),
    ('06-other-case-samples', 'd90628d', 'Other-case target samples with full counts and schemas; later same-case tables sampled only when needed; use view-target to inspect more.'),
]


def render2_stored_page(directory, output):
    """Adapt saved evidence to the existing render2 display, without replay."""
    import arclog
    # Display-only dependency: choose the actual current interpreter environment
    # rather than an unmigrated historical CURRENT receipt. No replay is called.
    os.environ.setdefault('JUDGE_WHEEL_ENV', str(Path(sys.prefix).resolve()))
    sys.path.insert(0, str(current.S/'judge2'))
    from render2.render import display
    m = json.loads((directory/'manifest.json').read_text())
    with gzip.open(m['adapter']['source']['record_path'], 'rt') as stream:
        record = json.load(stream)
    task = json.loads(Path(m['adapter']['source']['task_path']).read_text())
    doc = current.Document(record, m['adapter']['source']['native_base'], task, arclog, current.Programs(arclog))
    choices, choice_evidence = Assignments(arclog).compiled(record, doc.gprogram, doc.gexport)
    f = dict(version='render2 stored-evidence review', pair_id=m['pair_id'], task=record['task'],
        case=record['case'], kind=record['kind'], K=record['K'], operation=record['operation'],
        identity=record['identity'], programs=record['programs'], tables={}, kept_assignments=doc.kept,
        outputs=record['evaluation']['outputs'], orientations=doc.values.f['orientations'],
        orientation_types=doc.values.f['orientation_types'], task_data=doc.task, faults=[],
        pending=['Review display of stored rows only: production replay/audit not run',
                 'Computed component outputs, detailed OUT and DET admissibility not replayed'],
        column_names={}, fits_evidence=[], comparison_audit=[])
    views = {}
    for side in ('gold', 'mutant'):
        reader = doc.readers[side]
        export = doc.gexport if side == 'gold' else doc.mexport
        view = next(v for v in export['body_views'] if v['owner_path']==doc.owner and v['kind']==doc.body['kind'] and v['input_port']==doc.body['input_port'])
        views[side] = view
        t = record['evaluation']['table_indices'][side+'_kept']
        schema = [dict(c) for c in reader.schema(t)]
        f['column_names'].update(bind_body_schema(dict(schema=schema), view))
        _, decoded, evidence = doc.entries(reader, t, record['evaluation'][side+'_kept_assignment_map'])
        entries = []
        for a, items in enumerate(evidence):
            for item in items:
                e = dict(doc.visible(decoded[item['native_entry']], schema), choice=a+1)
                for det in e['assignment']:
                    det['display_name'] = doc.names.source(det['relation'])
                entries.append(e)
        f['tables'][side] = dict(schema=schema, entries=entries)
    changed = [dict(path=e['at'], before=doc.gnodes[tuple(e['at'])], deleted=e['kind']=='delete', after=None)
               for e in record['identity']['edits']]
    require(all(c['deleted'] for c in changed), 'selected baseline needs exact nondelete correspondence')
    f['structured'] = dict(gold=doc.gexport, mutant=doc.mexport, changes=changed,
        clause=doc.gnodes[tuple(record['clause'])], mutant_clause=doc.mnodes[tuple(record['clause'])],
        owner=doc.gnodes[tuple(doc.owner)], kept_decoded=choices, choice_evidence=dict(gold=choice_evidence,mutant=choice_evidence),
        contexts=dict(gold=context(doc.gexport,doc.owner,downstream_only=True),
                      mutant=context(doc.mexport,doc.owner,downstream_only=True)),
        sites={}, body_views=views, components=dict(report=record['full_replay']['evaluation']))
    attach_choice_extents(f)
    intro = ['# render2 page — same stored pair, offline display', '',
        'Generated by the existing render2 `display(full=True)` formatter from this exact stored calibration record. '
        'No program was reevaluated; this is not a previously published/AUDITED pool page. '
        'The page remains PENDING where execution/audit evidence was not attached. '
        'It preserves render2’s aliases, witness presentation and layout for comparison.', '', '## Task references', '']
    for i, ex in enumerate(doc.task['train'],1):
        intro += [f'train{i}', '```text', *reference_panels(ex), '```', '']
    raw = '\n'.join(intro) + '\n' + display(f, full=True, values=Values(f), include_task=True, compact_evidence=True)
    output.write_text(current.real_paths(raw))
    return dict(formatter=str((current.S/'judge2/render2/render.py').resolve()),
                formatter_sha256=current.sha((current.S/'judge2/render2/render.py').read_bytes()),
                mode='display(full=True), stored rows only, no evaluator/audit', pair_id=m['pair_id'],
                source_record_sha256=m['adapter']['source']['record_sha256'])


def main():
    sys.dont_write_bytecode = True
    sys.path.append(str(MAIN_ROOT/'.venv/lib/python3.12/site-packages'))
    review = DATA_ROOT/'judge3/review'
    review.mkdir(exist_ok=True)
    for name in ('06-repeated-values','06-sampled-large'):
        obsolete=review/name
        if obsolete.exists(): shutil.rmtree(obsolete)
    lines = ['# Judge document review set', '',
        'Six calibration pairs under the chosen display policy and the budget reported in size-proposal.md. G/X comparison rows are complete. Later same-case tables are complete when they fit, sampled otherwise with full counts. Other-case target tables are sampled with full row counts and schemas; the tool can show more. Other supporting tables are sampled only when needed. All row and comparison counts use complete tables. Open the files below; no commands are needed. '
        'Targets include every table of every other case. The brief gives the tool commands for viewing targets and checking clauses. '
        '',
        '- [Tool review v5](/Users/davidlu/code/arc-workspace/work/lm/data-study/judgetool/review-v5/index.md) — four actual sessions on this version, including target views, pagination, recoveries and continuation outcomes.',
        '- [Current execution route](current-route.md) — target viewing, full replay and the new pruned document version; prior recordings are preserved.',
        '- [Size proposal](size-proposal.md) — measured 55-pair sizes, proposed budget and sampling behavior.',
        '- [Judge brief](judge-brief.md) — whole judge brief: clauses and evidence-based reasons, six per-clause outcomes, exploratory runs, train-and-test checks, full replay and kept-entry filtering; no judge label or grade.', '']
    (review/'judge-brief.md').write_text((ROOT/'judge-brief.md').read_text().replace('@STUDY_CODE_ROOT@', str(CODE_ROOT)))
    receipt = []; started=time.monotonic()
    for number,(name,prefix,description) in enumerate(SAMPLES,1):
        directory = next((DATA_ROOT/'judge3/calibration2-v5').glob(prefix+'*'))
        m = json.loads((directory/'manifest.json').read_text()); target=review/name;target.mkdir(exist_ok=True)
        shutil.copyfile(directory/'evidence.md',target/'current.md')
        # A reader-facing snapshot is enough; raw source records/native test data are not copied.
        receipt.append(dict(sample=name,pair_id=m['pair_id'],task=m['task'],case=m['case'],
                            render_version=m['render_version'],file='current.md',sha256=m['document_sha256']))
        lines += [f'- [{name}/current.md]({name}/current.md) — {description} Task `{m["task"]}`, case `{m["case"]}`; {m["bytes"]:,} bytes; {"sampled displays" if m["display"]["sampled"] else "complete displays"}.']
        if number==1:
            (target/'p-evidence.md').write_text(current.real_paths((P/'calib2'/m['pair_id']/'evidence.md').read_text()))
            baseline=render2_stored_page(directory,target/'render2.md')
            (target/'comparison-provenance.json').write_text(json.dumps(baseline,indent=2)+'\n')
            lines += [f'- [{name}/comparison-provenance.json]({name}/comparison-provenance.json) — formatter hash, saved-record identity and explicit offline/PENDING comparison mode.',
                      f'- [{name}/render2.md]({name}/render2.md) — the same pair through render2’s unchanged full display formatter, using saved evidence only; PENDING, not a new audited/replayed production page.',
                      f'- [{name}/p-evidence.md]({name}/p-evidence.md) — P’s original evidence.md for that exact pair, historical content retained with paths relocated; its sampled rows and older rules are historical.']
        if name=='05-many-rows-lib':
            label=json.loads((P/'labels2'/(m['pair_id']+'.json')).read_text())
            native=next(json.loads(l) for l in (P/'engine-final.jsonl').read_text().splitlines() if json.loads(l).get('pair_id')==m['pair_id'])
            (target/'historical-lib-example.md').write_text('# Historical lib recovery example\n\n'
                'P recorded this inside/same_dist clause and an engine verification under its historical verifier. '
                'This is selection/provenance context for the review sample, not a current verification or a judge answer embedded in current.md. '
                'No clause was run here.\n\n```arclog\n'+label['recovery']+'\n```\n\n'
                +'P engine-final.jsonl: engine='+str(native.get('engine'))+', verified='+str(native.get('verified'))+'. '
                'The old verifier’s column/held-context rules are not a substitute for the final tool contract.\n')
            lines += [f'- [{name}/historical-lib-example.md]({name}/historical-lib-example.md) — P’s recorded lib-using clause and historical verification provenance, explicitly not reverified.']
        elapsed=time.monotonic()-started
        print(f'{number}/{len(SAMPLES)} elapsed={elapsed:.2f}s rate={number/max(elapsed,.001):.2f}/s {name}',flush=True)
    lines += ['', '- [provenance.json](provenance.json) — source identities for the copied review samples.', '']
    render_rows = [json.loads(line) for line in (DATA_ROOT/'judge3/calibration2-v5/render-report.jsonl').read_text().splitlines()]
    sizes = sorted(row['bytes'] for row in render_rows)
    full = sorted(row['display']['full_bytes'] for row in render_rows)
    sampled = sum(row['display']['sampled'] for row in render_rows)
    budget=render_rows[0]['display']['limit_bytes']
    (review/'size-proposal.md').write_text(
        '# Proposed document size limit\n\n'
        f'Propose **{budget:,} UTF-8 bytes per document**, excluding the shared brief. This is a review proposal, configurable with --document-limit. '
        'Every document must stay strictly below this limit. G/X comparison rows are protected; later same-case tables may be sampled to fit.\n\n'
        f'All {len(sizes)} calibration sources rendered. Before applying the chosen sampling policy, median document content is {full[len(full)//2]:,} bytes and the largest is {full[-1]:,}. '
        f'{len(sizes)-sampled} documents show every displayed table completely; {sampled} include sampled row sets, primarily other-case targets under the chosen display policy. '
        f'Final documents range from {sizes[0]:,} to {sizes[-1]:,} bytes; '+('all fit the proposed limit.' if all(r['display']['limit_met'] for r in render_rows) else 'some exceed the limit; see per-pair receipts.')+'\n\n'
        'The renderer computes complete comparisons first. G/X comparison definitions are protected from sampling. Later same-case tables are complete while the document fits, then large tables are sampled if needed. Other-case target definitions show at most 12 rows regardless of document size; additional large supporting displays are reduced only as needed. '
        'Each sampled definition prints its total count, first 12 rows (or one if needed to meet the budget) and omitted count; references to it say sample. Every target entry also prints its complete visible row count, source name and schema. '
        'Complete source-row, difference and native-key conflict counts are never computed from the sample. '
        'G/X align only on stored native candidate keys that survive projection; these 55 have no shared projected keys, so comparisons show side-exclusive rows.\n\n'
        'Use view-target to inspect more target rows, or exploratory clauses over available tables. Those runs are not answers; recovery verdicts require complete train-and-test checks. '
        'The stable tool CLI and final-answer format are in the judge brief. No test outputs, tests, evaluator runs or judge calls were used to render these samples.\n')
    (review/'index.md').write_text('\n'.join(lines))
    (review/'provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    main()

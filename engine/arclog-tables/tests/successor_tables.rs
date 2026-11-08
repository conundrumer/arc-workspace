//! A check of `successor_tables`, an in-progress feature of the query
//! writer: at each model token of a ramp program, for each token the mask
//! admits, the successor's tables equal those of the oracle, a fork of the
//! decode that steps the token and gives `step_tables` with `Points::All`:
//! the same tables at the same points, with the same TableHash at each
//! assignment, the same faults, column types, Ident sources and frames. Where
//! the token leaves the point of the body in progress as it was,
//! `step_tables` gives no table, and the oracle is the table of the fork's
//! body in progress (`body_now`).

use arclog::decode::Decoder;
use arclog::eval::join::Materializer;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::registry::Registry;
use arclog::session::{SessionBound, TaskSession, SESSION_BYTES};
use arclog::stream::{DecodeSettings, Token};
use arclog::study::StudyProgram;
use arclog::task::{read_judged_train_text, read_task_text};
use arclog_tables::columns::{step_case_columns_by_assignment_in, CaseColumns, StreamTables};
use arclog_tables::summary::{train_pairs, SummaryCache};
use arclog_tables::tables::successors::{successor_tables, SuccessorKind};
use arclog_tables::tables::{body_now, evidence_tables, mark_selected, step_tables, Point, Points, Table};

/// What the check compares of one row of the tables part of the export by
/// assignment: the point code, the conjuncts and the sites, the form, whether
/// the row has a TableHash and the hash, the fault, and the column types, Ident
/// sources and frames.
type Row = (u8, u32, u32, String, u8, u128, Option<String>, Vec<String>, Vec<String>, Vec<String>);

fn rows(columns: &CaseColumns) -> Vec<Row> {
    let t = &columns.tables;
    (0..t.point.len())
        .map(|at| (t.point[at], t.conjuncts[at], t.sites[at], t.form[at].clone(), t.hashed[at], t.hash[at], t.fault[at].clone(), t.column_types[at].clone(), t.column_ident_sources[at].clone(), t.column_frames[at].clone()))
        .collect()
}

/// The columns by assignment of `tables`, the tables of the step at `index`
/// of `decoder`, after the stream `before`, as `step_tables` of the Python
/// binding gives them, and the stream after them.
fn columns(decoder: &Decoder<'_>, evidence: &[Table], before: Option<&StreamTables>, index: usize, tables: Vec<Table>, summaries: &SummaryCache) -> (CaseColumns, StreamTables) {
    let limits = decoder.limits();
    let materializer = Materializer::new(decoder.evaluation_inputs().1, &limits);
    let queries = tables
        .iter()
        .map(|table| match table.point {
            Point::Relation => table.form.0.first().and_then(|top| decoder.query_hash(top.0 as usize)),
            Point::Body { .. } | Point::Evidence => None,
        })
        .collect();
    let train = train_pairs(decoder.evaluation_inputs().0);
    step_case_columns_by_assignment_in(&materializer, before, evidence, tables.into_iter().map(|table| (index, table)).collect(), &train, queries, false, summaries)
}

/// The mismatches between the successors and the oracle at each model token
/// of `program`, a program of the task of the JSON `task`, and the count of
/// the admitted tokens compared.
fn mismatches(task: &str, program: &str) -> (Vec<String>, usize) {
    let registry = Registry::get();
    let settings = DecodeSettings { table_work_cap: 1 << 21, rule_tests: false, ..DecodeSettings::synthesis() };
    let judged = read_judged_train_text(task).expect("the task's train pairs");
    let task = read_task_text(task).expect("the task");
    let session = TaskSession::new(SessionBound { bytes: SESSION_BYTES }, settings.caps);
    let constructions = arclog_constructions::shared().expect("the constructions");
    let train: std::sync::Arc<[PairCandidates<'_>]> = judged.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Open)).collect();
    let mut decoder = Decoder::new(&task, &session, registry, constructions, &settings).judging(train);
    let stream = StudyProgram::from_sexp(program, registry).expect("the program reads").decode_stream(registry, &settings).expect("the program's stream");
    let vocabulary = arclog::stream::Vocabulary::new(registry, &settings);
    let evidence = evidence_tables(&task, registry);
    let summaries = SummaryCache::default();
    let mut before: Option<StreamTables> = None;
    // The tables of the decode's last model step.
    let mut last: Vec<Table> = Vec::new();
    let mut found = Vec::new();
    let mut compared = 0;
    for (&id, &model) in stream.ids.iter().zip(&stream.model) {
        if model == 0 {
            continue;
        }
        let mask = decoder.admissible();
        let admitted: Vec<u32> = (0..vocabulary.len() as u32).filter(|&id| mask.contains(id)).collect();
        let tokens: Vec<Token> = admitted.iter().map(|&id| vocabulary.token(id).expect("an admitted id").clone()).collect();
        let index = decoder.trace().len();
        let earlier: Vec<&Table> = before.as_ref().map_or_else(Vec::new, StreamTables::tables);
        let held = match &last[..] {
            [table] if matches!(table.point, Point::Body { .. }) => Some(table.clone()),
            _ => None,
        };
        let successors = successor_tables(&decoder, &decoder.limits(), tokens.clone(), &earlier, held);
        let current = successors.current.as_ref().map(|table| rows(&columns(&decoder, &evidence, before.as_ref(), index, vec![table.clone()], &summaries).0));
        let each = successors.each;
        for ((&id, token), successor) in admitted.iter().zip(tokens).zip(&each) {
            compared += 1;
            let mut fork = decoder.fork();
            let oracle = fork.step(token).ok().map(|_| {
                let mut own = step_tables(&fork, Points::All, &earlier);
                mark_selected(&fork, own.iter_mut());
                // Where the step leaves the point of the body as it was, `step_tables` gives no table, and the oracle is the body table it makes at a point that differs.
                let finished = fork.program().value().forms.len() > fork.before().expect("a step").program().value().forms.len();
                if own.is_empty() && !finished {
                    own.extend(body_now(&fork, &earlier));
                }
                rows(&columns(&fork, &evidence, before.as_ref(), index, own, &summaries).0)
            });
            let mine = successor.as_ref().ok().map(|successor| match successor.kind {
                // The table of the body in progress, at the successor's point, which is the current one.
                SuccessorKind::Unchanged => current.clone().unwrap_or_default(),
                // A successor that names an earlier one gets that one's tables, as the binding gives them.
                _ => {
                    let tables = successor.same_as.and_then(|first| each[first].as_ref().ok()).map_or(&successor.tables, |first| &first.tables);
                    rows(&columns(&successor.decoder, &evidence, before.as_ref(), index, tables.clone(), &summaries).0)
                }
            });
            let equal = oracle == mine;
            if !equal {
                found.push(format!("token {index}, id {id} ({:?}): oracle {oracle:?}, successor {mine:?}", vocabulary.token(id)));
            }
        }
        decoder.step(vocabulary.token(id).expect("the program's id").clone()).expect("the decode takes the program's token");
        let mut own = step_tables(&decoder, Points::All, &earlier);
        mark_selected(&decoder, own.iter_mut());
        let (_, next) = columns(&decoder, &evidence, before.as_ref(), index, own.clone(), &summaries);
        before = Some(next);
        last = own;
    }
    (found, compared)
}

fn check(task: &str, program: &str) {
    let (found, compared) = mismatches(task, program);
    assert!(compared > 0, "no admitted token");
    assert!(found.is_empty(), "{} of {compared} tokens differ from the oracle; the first: {:#?}", found.len(), &found[..found.len().min(3)]);
}

/// The task 74dd1130, without its test output.
const D4_TASK: &str = r#"{"train": [
{"input": [[2,2,1],[1,5,1],[5,2,2]], "output": [[2,1,5],[2,5,2],[1,1,2]]},
{"input": [[2,2,5],[6,2,2],[5,5,5]], "output": [[2,6,5],[2,2,5],[5,2,5]]},
{"input": [[9,9,5],[5,5,8],[5,8,9]], "output": [[9,5,5],[9,5,8],[5,8,9]]},
{"input": [[2,6,6],[2,1,1],[2,6,2]], "output": [[2,2,2],[6,1,6],[6,1,2]]}],
"test": [{"input": [[9,3,4],[9,4,4],[9,3,4]]}]}"#;

#[test]
fn successors_of_a_program_with_a_det_equal_the_oracle() {
    check(D4_TASK, "(DET &r0 D4Domain)\n(RULE &r1 (input (:P *P) (:Col *Col)) (&r0 (:D *D)) (apply (:D D) (:P P) (:P_out *POut)))\n(OUT (input ^P ^Col))\n");
}

/// The task 8e2edd66, without its test output.
const TILING_TASK: &str = r#"{"train": [
{"input": [[9,9,0],[0,0,9],[0,9,0]], "output": [[0,0,0,0,0,0,0,0,9],[0,0,0,0,0,0,9,9,0],[0,0,0,0,0,0,9,0,9],[0,0,9,0,0,9,0,0,0],[9,9,0,9,9,0,0,0,0],[9,0,9,9,0,9,0,0,0],[0,0,9,0,0,0,0,0,9],[9,9,0,0,0,0,9,9,0],[9,0,9,0,0,0,9,0,9]]},
{"input": [[8,8,0],[0,8,8],[0,8,0]], "output": [[0,0,0,0,0,0,0,0,8],[0,0,0,0,0,0,8,0,0],[0,0,0,0,0,0,8,0,8],[0,0,8,0,0,0,0,0,0],[8,0,0,0,0,0,0,0,0],[8,0,8,0,0,0,0,0,0],[0,0,8,0,0,0,0,0,8],[8,0,0,0,0,0,8,0,0],[8,0,8,0,0,0,8,0,8]]},
{"input": [[7,0,7],[7,7,7],[0,7,0]], "output": [[0,0,0,0,7,0,0,0,0],[0,0,0,0,0,0,0,0,0],[0,0,0,7,0,7,0,0,0],[0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0],[0,7,0,0,0,0,0,7,0],[0,0,0,0,0,0,0,0,0],[7,0,7,0,0,0,7,0,7]]}],
"test": [{"input": [[1,1,0],[0,1,0],[1,0,1]]}]}"#;

#[test]
fn successors_of_a_program_with_init_port_bodies_equal_the_oracle() {
    check(
        TILING_TASK,
        "(INIT &r0 Tiling (outer ((:P P)) (input (:P *P) (:Col *Col))) (inner ((:P P2)) (input (:P *P2) (:Col *Col2))))\n\
         (DET &r4 SharedColor)\n\
         (RULE &r5 (input (:P *P) (:Col *Col)) (&r4 (:C Col)))\n\
         (INIT &r6 Tiling (outer ((:P P)) (&r5 (:P *P))) (inner ((:P P2)) (&r5 (:P *P2))))\n\
         (OUT (input ^P ^Col))\n",
    );
}

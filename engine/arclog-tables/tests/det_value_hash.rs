//! A check of the export by assignment, an in-progress feature of the query
//! writer. An assignment names the value of a `DET` by its value hash. The
//! readers of a `DET` read its columns by position, so two values that differ
//! only by the order of two columns of one type are different values, and
//! their value hashes differ. The TableHash of the `DET`'s table is the same
//! under that order.

use std::collections::BTreeSet;

use arclog::decode::Decoder;
use arclog::eval::join::Materializer;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::registry::Registry;
use arclog::session::{SessionBound, TaskSession, SESSION_BYTES};
use arclog::stream::DecodeSettings;
use arclog::study::StudyProgram;
use arclog::task::{read_judged_train_text, read_task_text};
use arclog_tables::columns::{step_case_columns_by_assignment_in, CaseColumns, StreamTables};
use arclog_tables::summary::{train_pairs, SummaryCache};
use arclog_tables::tables::{evidence_tables, mark_selected, step_tables, Point, Points, Table};

/// The task 74dd1130, without its test output.
const TASK: &str = r#"{"train": [
{"input": [[2,2,1],[1,5,1],[5,2,2]], "output": [[2,1,5],[2,5,2],[1,1,2]]},
{"input": [[2,2,5],[6,2,2],[5,5,5]], "output": [[2,6,5],[2,2,5],[5,2,5]]},
{"input": [[9,9,5],[5,5,8],[5,8,9]], "output": [[9,5,5],[9,5,8],[5,8,9]]},
{"input": [[2,6,6],[2,1,1],[2,6,2]], "output": [[2,2,2],[6,1,6],[6,1,2]]}],
"test": [{"input": [[9,3,4],[9,4,4],[9,3,4]]}]}"#;

/// A `DET` of two `Color` columns, and a table that reads both of its columns.
const PROGRAM: &str = "(DET &r0 ColorColorDomain)\n(RULE &r1 (input (:P *P) (:Col *Col)) (&r0 (:C_from Col) (:C_to *C2)))\n(OUT (input ^P ^Col))\n";

/// The columns by assignment of `tables`, the tables of the step at `index`
/// of `decoder`, after the stream `before`, and the stream after them.
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

/// The export by assignment of each model step of `program` on `task`.
fn exports(task: &str, program: &str) -> Vec<CaseColumns> {
    let registry = Registry::get();
    let settings = DecodeSettings { deadline: None, table_work_cap: 1 << 21, rule_tests: false, ..DecodeSettings::synthesis() };
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
    let mut found = Vec::new();
    for (&id, &model) in stream.ids.iter().zip(&stream.model) {
        if model == 0 {
            continue;
        }
        let index = decoder.trace().len();
        decoder.step(vocabulary.token(id).expect("the program's id").clone()).expect("the decode takes the program's token");
        let earlier: Vec<&Table> = before.as_ref().map_or_else(Vec::new, StreamTables::tables);
        let mut own = step_tables(&decoder, Points::All, &earlier);
        mark_selected(&decoder, own.iter_mut());
        let (export, next) = columns(&decoder, &evidence, before.as_ref(), index, own, &summaries);
        found.push(export);
        before = Some(next);
    }
    found
}

#[test]
fn det_values_that_differ_by_a_column_swap_have_different_value_hashes() {
    let exports = exports(TASK, PROGRAM);
    // The value hashes of the `DET`'s values, as its own table gives them.
    let mut own_values: BTreeSet<u128> = BTreeSet::new();
    for export in &exports {
        let (tables, assignments, entries) = (&export.tables, &export.assignments, &export.entries);
        // Each row of the `DET`'s own table, with the value hash that its assignment names the `DET` by.
        let own: Vec<(usize, u128)> = (0..assignments.table.len())
            .filter(|&at| assignments.has_det_query[at] == 1 && tables.has_query[assignments.table[at] as usize] == 1 && tables.query[assignments.table[at] as usize] == assignments.det_query[at])
            .map(|at| (assignments.table[at] as usize, assignments.value[at]))
            .collect();
        if own.is_empty() {
            continue;
        }
        assert!(own.len() >= 2, "the DET has {} values", own.len());
        let values: BTreeSet<u128> = own.iter().map(|&(_, value)| value).collect();
        assert_eq!(values.len(), own.len(), "{} values of the DET have {} value hashes", own.len(), values.len());
        for &(row, value) in &own {
            let hashes: Vec<u128> = (0..entries.table.len()).filter(|&entry| entries.table[entry] as usize == row && entries.hash[entry] != 0).map(|entry| entries.hash[entry]).collect();
            assert_eq!(hashes, vec![value], "the entry of the DET's own table at a value has the value's hash");
        }
        let table_hashes: BTreeSet<u128> = own.iter().map(|&(row, _)| tables.hash[row]).collect();
        assert!(table_hashes.len() < own.len(), "the TableHash of a value and of its column swap are equal, so {} values have fewer TableHashes than {}", own.len(), table_hashes.len());
        own_values.extend(values);
    }
    assert!(!own_values.is_empty(), "no export has the DET's own table");
    // Each value that a reader of the `DET` names is a value of the `DET`'s own table.
    let mut read = 0;
    for export in &exports {
        let (tables, assignments) = (&export.tables, &export.assignments);
        for at in 0..assignments.table.len() {
            let row = assignments.table[at] as usize;
            if assignments.has_det_query[at] == 1 && !(tables.has_query[row] == 1 && tables.query[row] == assignments.det_query[at]) {
                read += 1;
                assert!(own_values.contains(&assignments.value[at]), "a reader names a value hash that the DET's own table does not give");
            }
        }
    }
    assert!(read > 0, "no reader of the DET");
}

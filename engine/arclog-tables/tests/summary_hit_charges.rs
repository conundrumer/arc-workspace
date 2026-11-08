//! A table summary that a `SummaryCache` gives charges the request that takes
//! it what the summary's computation charged. So the counts and the gauges of
//! a request over a cache that holds the summaries of its tables equal those
//! of a request that computed them, which is what makes the gauges of a decode
//! that shares a session with an earlier decode equal those of a decode in a
//! session of its own.

use arclog::decode::Decoder;
use arclog::eval::join::Materializer;
use arclog::eval::{Cancellation, Gauge, Limits};
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::registry::Registry;
use arclog::session::{SessionBound, TaskSession, SESSION_BYTES};
use arclog::stream::DecodeSettings;
use arclog::study::StudyProgram;
use arclog::task::{read_judged_train_text, read_task_text};
use arclog_tables::columns::{step_case_columns_by_assignment_in, StreamTables};
use arclog_tables::summary::{train_pairs, SummaryCache};
use arclog_tables::tables::{evidence_tables, mark_selected, step_tables, Point, Points, Table};

/// A task of one train pair and one test input, each a row of two cells.
const TASK: &str = r#"{"train": [{"input": [[1, 2]], "output": [[1, 2]]}], "test": [{"input": [[1, 2]]}]}"#;

const PROGRAM: &str = "(RULE &output (input *P *Col))\n(OUT (&output ^P ^Col))\n";

/// The largest value and the hits of each gauge of `limits`' request, by the
/// gauge's name, other than the session's bytes, which hold what the session
/// held.
fn gauges(limits: &Limits) -> Vec<(&'static str, u64, u64)> {
    limits.request.gauges().each().iter().filter(|(gauge, ..)| *gauge != Gauge::SessionBytes).map(|(gauge, max, _, hits)| (gauge.name(), *max, *hits)).collect()
}

/// The export by assignment of `tables`, the tables of the step at `index`,
/// after the stream `before`, in a request of its own and through `cache`: the
/// gauges of that request and the stream after the step.
fn columns_under(decoder: &Decoder<'_>, evidence: &[Table], before: Option<&StreamTables>, index: usize, tables: &[Table], cache: &SummaryCache) -> (Vec<(&'static str, u64, u64)>, StreamTables) {
    let limits = Limits::new(None, Cancellation::default());
    let materializer = Materializer::new(decoder.evaluation_inputs().1, &limits);
    let queries = tables
        .iter()
        .map(|table| match table.point {
            Point::Relation => table.form.0.first().and_then(|top| decoder.query_hash(top.0 as usize)),
            Point::Body { .. } | Point::Evidence => None,
        })
        .collect();
    let train = train_pairs(decoder.evaluation_inputs().0);
    let (_, stream) = step_case_columns_by_assignment_in(&materializer, before, evidence, tables.iter().cloned().map(|table| (index, table)).collect(), &train, queries, true, cache);
    (gauges(&limits), stream)
}

#[test]
fn a_summary_from_the_cache_charges_what_its_computation_charged() {
    let registry = Registry::get();
    let settings = DecodeSettings { table_work_cap: 1 << 21, rule_tests: false, ..DecodeSettings::synthesis() };
    let judged = read_judged_train_text(TASK).expect("the task's train pairs");
    let task = read_task_text(TASK).expect("the task");
    let session = TaskSession::new(SessionBound { bytes: SESSION_BYTES }, settings.caps);
    let constructions = arclog_constructions::shared().expect("the constructions");
    let train: std::sync::Arc<[PairCandidates<'_>]> = judged.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Open)).collect();
    let mut decoder = Decoder::new(&task, &session, registry, constructions, &settings).judging(train);
    let stream = StudyProgram::from_sexp(PROGRAM, registry).expect("the program reads").decode_stream(registry, &settings).expect("the program's stream");
    let vocabulary = arclog::stream::Vocabulary::new(registry, &settings);
    let evidence = evidence_tables(&task, registry);
    let mut before: Option<StreamTables> = None;
    let (mut steps, mut charging) = (0, 0);
    for (&id, &model) in stream.ids.iter().zip(&stream.model) {
        if model == 0 {
            continue;
        }
        decoder.step(vocabulary.token(id).expect("the program's id").clone()).expect("the decode takes the program's token");
        let index = decoder.trace().len();
        let earlier: Vec<&Table> = before.as_ref().map_or_else(Vec::new, StreamTables::tables);
        let mut own = step_tables(&decoder, Points::All, &earlier);
        mark_selected(&decoder, own.iter_mut());
        // The first export computes the summaries into `cache`, and the second takes them from it.
        let cache = SummaryCache::default();
        let (computed, _) = columns_under(&decoder, &evidence, before.as_ref(), index, &own, &cache);
        let (taken, next) = columns_under(&decoder, &evidence, before.as_ref(), index, &own, &cache);
        assert_eq!(computed, taken, "the gauges of the export at the model step {steps}: computed, then taken from the cache");
        steps += 1;
        if computed.iter().any(|(name, max, _)| ["request_bytes", "assignment_bytes", "rows", "bindings"].contains(name) && *max > 0) {
            charging += 1;
        }
        before = Some(next);
    }
    assert!(steps > 0, "no model step");
    assert!(charging > 0, "no export charged bytes, rows or bindings, so the check compared no charge of a summary");
}

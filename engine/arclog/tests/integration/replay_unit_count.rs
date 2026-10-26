//! A solver replayed in k units gives every stream the result that one unit gives it, in at most k units, each stream settled once.

use super::panic_isolation::{ARCDATA, ARCLOG};
use arclog::decode::corpus::{read_task_files, replay_units, ReplayProgress, UnitSolver};
use arclog::decode::Decoder;
use arclog::eval::instance::Constructions;
use arclog::registry::Registry;
use arclog::stream::corpus::{solver_streams, token_ids, WantedCases};
use arclog::stream::{DecodeSettings, Vocabulary};
use std::num::NonZeroUsize;
use std::sync::atomic::{AtomicUsize, Ordering};

#[test]
fn k_units_give_each_stream_the_result_of_one_unit() {
    let dir = std::env::temp_dir().join(format!("arclog-unit-count-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("a temporary directory");
    let pair = r#"{"input": [[1, 2, 1]], "output": [[2, 2, 1]]}"#;
    std::fs::write(dir.join("tie.arclog"), ARCLOG).expect("the arclog file");
    std::fs::write(dir.join("tie.arcdata"), ARCDATA).expect("the arcdata file");
    std::fs::write(dir.join("tie.json"), format!(r#"{{"train": [{pair}], "test": [{pair}]}}"#)).expect("the task file");
    let registry = Registry::get();
    let settings = DecodeSettings::default();
    let vocabulary = Vocabulary::new(registry, &settings);
    let cases = solver_streams(&dir, "tie", WantedCases::Concept, &vocabulary).expect("the solver's streams");
    let (task, judged) = read_task_files(&dir, "tie").expect("the task reads");
    std::fs::remove_dir_all(&dir).ok();
    let whole = token_ids(&cases[0].stream.as_ref().expect("a stream").tokens, &vocabulary);
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");

    // Prefixes of one stream, so that each adds model steps to the running sum.
    let streams: Vec<_> = (1..=6).map(|part| whole[..whole.len() * part / 6].to_vec()).collect();
    let run = |units: Option<usize>| {
        let started = AtomicUsize::new(0);
        let settled = AtomicUsize::new(0);
        let progress = ReplayProgress::default();
        let solvers = [UnitSolver { task: &task, judged: &judged, streams: &streams, units: units.and_then(NonZeroUsize::new) }];
        let results = replay_units(
            &solvers,
            &constructions,
            &settings,
            false,
            units.unwrap_or(1),
            &progress,
            &|record: &mut Vec<usize>, _: &Decoder<'_>, stepped| record.push(stepped.index),
            &|_| {
                started.fetch_add(1, Ordering::SeqCst);
            },
            &|_, replay| replay.record,
            &|_| {
                settled.fetch_add(1, Ordering::SeqCst);
            },
            None,
        );
        assert_eq!(settled.load(Ordering::SeqCst), streams.len());
        assert_eq!(progress.done(), progress.total());
        (results.into_iter().next().expect("a result for the solver"), started.load(Ordering::SeqCst))
    };
    let (base, base_units) = run(None);
    assert_eq!(base_units, 1);
    assert_eq!(run(Some(1)), (base.clone(), 1));
    for k in [2, 3, 6] {
        let (results, units) = run(Some(k));
        assert!(1 < units && units <= k, "{units} units for {k}");
        assert_eq!(results, base);
    }
}

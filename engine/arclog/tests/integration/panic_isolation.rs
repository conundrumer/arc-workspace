//! A panic in one stream's replay faults that stream alone, and a computation
//! in flight that panics ends for the threads that wait on it.

use arclog::decode::corpus::{read_task_files, replay_units, ReplayProgress, UnitSolver};
use arclog::eval::instance::Constructions;
use arclog::eval::pool::InFlight;
use arclog::registry::Registry;
use arclog::stream::corpus::{solver_streams, token_ids, WantedCases};
use arclog::stream::{DecodeSettings, Vocabulary};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

pub(crate) const ARCLOG: &str = "\
;; tie

(DET &seed RarestColor)

(RULE &seed_cell
  (input *P *Col)
  (&seed (:C Col)))

(INIT &state Unfold
  (start ((:t P))
    (&seed_cell *P))
  (initial_untaken ((:item P))
    (input *P)
    (NOT (&seed_cell P)))
  (score ((:t P) (:item X) (:S K))
    (&seed_cell *P)
    (input (:P *X))
    (NOT (&seed_cell (:P X)))
    (= *K 0)))

(RULE &taken
  (&state.take (:item *P)))

(RULE &output
  (OR ((input *P *Col)
       (NOT (&taken P)))
      ((&taken P)
       (&seed (:C Col)))))
";

pub(crate) const ARCDATA: &str = "\
;; tie

(param &seed Color (2))
";


#[test]
fn a_panic_in_one_stream_faults_that_stream_alone() {
    let dir = std::env::temp_dir().join(format!("arclog-panic-isolation-{}", std::process::id()));
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

    // The short stream is a prefix of the whole one, so one unit holds both; only the whole stream steps past `cut`.
    let cut = whole.len() / 2;
    let streams = vec![whole.clone(), whole[..cut].to_vec()];
    let solvers = [UnitSolver { task: &task, judged: &judged, streams: &streams, units: None }];
    let (started, ended, settled) = (AtomicUsize::new(0), AtomicUsize::new(0), AtomicUsize::new(0));
    let progress = ReplayProgress::default();
    let results = replay_units(
        &solvers,
        &constructions,
        &settings,
        false,
        1,
        &progress,
        &|record: &mut Vec<usize>, _, stepped| {
            assert!(stepped.index < cut, "boom");
            record.push(stepped.index);
        },
        &|_| {
            started.fetch_add(1, Ordering::SeqCst);
        },
        &|_, replay| {
            ended.fetch_add(1, Ordering::SeqCst);
            replay.record
        },
        &|_| {
            settled.fetch_add(1, Ordering::SeqCst);
        },
        None,
    );
    let [results] = <[_; 1]>::try_from(results).expect("one solver");
    let [whole_result, short_result] = <[_; 2]>::try_from(results).expect("one result for each stream");
    let fault = whole_result.expect_err("the stream that panics gives a fault");
    assert!(fault.starts_with("the replay panicked: ") && fault.contains("boom"), "{fault}");
    let short = short_result.expect("the stream that does not panic gives its record");
    assert!(!short.is_empty() && short.iter().all(|&index| index < cut), "{short:?}");
    assert_eq!(started.load(Ordering::SeqCst), 1);
    assert_eq!(ended.load(Ordering::SeqCst), 1);
    assert_eq!(settled.load(Ordering::SeqCst), 2);
    assert_eq!(progress.done(), progress.total());
}

/// A waiter on a computation that panics asks again and computes the entry itself.
#[test]
fn a_waiter_computes_an_entry_whose_computation_panicked() {
    let table: InFlight<u32, u32> = InFlight::new();
    let computing = AtomicBool::new(false);
    std::thread::scope(|scope| {
        let first = scope.spawn(|| {
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                table.get_or_compute(7, || {
                    computing.store(true, Ordering::SeqCst);
                    std::thread::sleep(std::time::Duration::from_millis(100));
                    panic!("boom")
                })
            }))
        });
        while !computing.load(Ordering::SeqCst) {
            std::thread::yield_now();
        }
        let second = table.get_or_compute(7, || Some(70));
        assert!(first.join().expect("the thread ends").is_err());
        assert_eq!(second, Some(70));
    });
}

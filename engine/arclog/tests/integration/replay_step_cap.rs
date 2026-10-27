//! A replay of units under a step cap gives the streams of a solver within
//! the cap what it gives with no cap, and each later stream the cap's fault,
//! and settles each stream once.

use arclog::decode::corpus::{new_model_steps, ReplayProgress, read_task_files, replay_units, sorted_streams, UnitSolver};
use arclog::decode::replay::replay;
use arclog::decode::Decoder;
use arclog::eval::instance::Constructions;
use arclog::registry::Registry;
use arclog::stream::corpus::{solver_streams, token_ids, WantedCases};
use arclog::stream::{DecodeSettings, Emitter, Vocabulary};
use std::ops::ControlFlow;
use std::sync::atomic::{AtomicUsize, Ordering};

const ARCLOG: &str = "\
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

(OUT (&output ^P ^Col))
";

const ARCDATA: &str = "\
;; tie

(param &seed Color (2))
";


#[test]
fn a_step_cap_cuts_a_solvers_streams_at_the_stream_that_passes_it() {
    let dir = std::env::temp_dir().join(format!("arclog-step-cap-{}", std::process::id()));
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

    // A position where the model writes, and an id the mask refuses there: a second branch of the prefix tree.
    let session = arclog::decode::corpus::corpus_session();
    let train: std::sync::Arc<[_]> = judged.train.iter().map(|pair| arclog::judge::candidates::PairCandidates::of(pair, arclog::judge::candidates::Section::Train, arclog::judge::candidates::World::Closed)).collect();
    let tokens = |ids: &[(u32, Emitter)]| -> Vec<_> { ids.iter().map(|(id, emitter)| (vocabulary.token(*id).expect("a token").clone(), *emitter)).collect() };
    let (cut, refused) = (2..whole.len())
        .find_map(|cut| {
            if whole[cut].1 != Emitter::Model {
                return None;
            }
            let mut decoder = Decoder::new(&task, &session, registry, &constructions, &settings).judging(std::sync::Arc::clone(&train));
            let replayed = replay(&mut decoder, &tokens(&whole[..cut]), true, &mut |_, _| ControlFlow::Continue(())).ok()?;
            if !replayed.forced().is_empty() {
                return None;
            }
            let mask = decoder.admissible();
            (0..vocabulary.len() as u32).find(|id| !mask.contains(*id)).map(|id| (cut, id))
        })
        .expect("a position of the stream that refuses a token");
    let mut refusing = whole[..cut].to_vec();
    refusing.push((refused, Emitter::Model));
    let streams = vec![refusing, whole.clone(), whole[..cut].to_vec()];

    let order = sorted_streams(&streams);
    let steps = |kept: usize| {
        let mut last = None;
        order[..kept].iter().map(|&index| {
            let added = new_model_steps(last, &streams[index]);
            last = Some(streams[index].as_slice());
            added
        }).sum::<usize>()
    };
    let total = steps(order.len());
    let cap = steps(2);
    assert!(cap < total, "the third stream in order adds steps");

    let solvers = [UnitSolver { task: &task, judged: &judged, streams: &streams, units: None }];
    let run = |step_cap: Option<usize>| {
        let settled = AtomicUsize::new(0);
        let results = replay_units(
            &solvers,
            &constructions,
            &settings,
            false,
            1,
            &ReplayProgress::default(),
            &|record: &mut Vec<usize>, _: &Decoder<'_>, stepped| record.push(stepped.index),
            &|_| {},
            &|_, replay| replay.record,
            &|_| {
                settled.fetch_add(1, Ordering::SeqCst);
            },
            step_cap,
        );
        assert_eq!(settled.load(Ordering::SeqCst), streams.len());
        results.into_iter().next().expect("a result for the solver")
    };
    let uncapped = run(None);
    let capped = run(Some(cap));
    for (rank, &index) in order.iter().enumerate() {
        if rank < 2 {
            assert_eq!(capped[index], uncapped[index]);
        } else {
            let fault = capped[index].as_ref().expect_err("a stream past the cap gives a fault");
            assert!(fault.contains(&cap.to_string()) && fault.contains(&total.to_string()), "{fault}");
        }
    }
}

//! The replay of streams as a prefix tree gives, for each stream, the record
//! and the outcome that a replay of that stream from a new decoder gives.

use arclog::decode::corpus::{read_task_files, replay_prefix_tree, corpus_session, StreamReplay, sorted_streams, model_steps};
use arclog::decode::replay::replay;
use arclog::decode::{Decoder, TokenMask};
use arclog::eval::instance::Constructions;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::registry::Registry;
use arclog::stream::corpus::{solver_streams, token_ids, WantedCases};
use arclog::stream::{DecodeSettings, Emitter, Vocabulary};
use std::cell::Cell;
use std::ops::ControlFlow;
use std::sync::Arc;

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
";

const ARCDATA: &str = "\
;; tie

(param &seed Color (2))
";

type Record = Vec<(usize, TokenMask)>;

#[test]
fn a_prefix_tree_replay_gives_what_a_replay_from_a_new_decoder_gives() {
    let dir = std::env::temp_dir().join(format!("arclog-prefix-tree-{}", std::process::id()));
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
    let whole = token_ids(cases[0].stream.as_ref().expect("a stream"), &vocabulary);
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let record = |record: &mut Record, _: &Decoder<'_>, stepped: arclog::decode::replay::Stepped<'_>| record.push((stepped.index, stepped.mask.expect("the replay computes the mask").mask.clone()));

    let session = corpus_session();
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let fresh = || Decoder::new(&task, &session, registry, &constructions, &settings).judging(Arc::clone(&train));
    let tokens = |ids: &[(u32, Emitter)]| -> Vec<_> { ids.iter().map(|(id, emitter)| (vocabulary.token(*id).expect("a token").clone(), *emitter)).collect() };

    // A position where the model writes, with no token forced, and an id the mask refuses there.
    let (cut, refused) = (2..whole.len())
        .find_map(|cut| {
            if whole[cut].1 != Emitter::Model {
                return None;
            }
            let mut decoder = fresh();
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
    let mut refusing_longer = refusing.clone();
    refusing_longer.push(whole[cut]);
    let streams = vec![whole.clone(), refusing.clone(), whole[..cut].to_vec(), whole.clone(), refusing_longer, whole[..cut + 1].to_vec(), refusing];

    let tree = replay_prefix_tree(&task, &judged, &streams, &constructions, &settings, true, &record);
    assert_eq!(tree.len(), streams.len());
    for (stream, outcome) in streams.iter().zip(&tree) {
        let mut decoder = fresh();
        let mut recorded = Record::new();
        let result = replay(&mut decoder, &tokens(stream), true, &mut |decoder, stepped| {
            record(&mut recorded, decoder, stepped);
            ControlFlow::Continue(())
        });
        let alone = StreamReplay { fault: result.map_or_else(Some, |replayed| replayed.unfinished()), record: recorded };
        assert_eq!(*outcome, alone);
    }
    // The refused stream keeps the steps before its refused token.
    assert!(tree[1].fault.is_some(), "the refused stream fails: {:?}", tree[1]);
    assert!(!tree[1].record.is_empty(), "the refused stream keeps the record before its refused token");
    assert!(tree[0].fault.is_none(), "{:?}", tree[0].fault);

    // A replay with no mask records the same steps and ends the same way, refusal lines included.
    let indices = |record: &mut Vec<usize>, _: &Decoder<'_>, stepped: arclog::decode::replay::Stepped<'_>| {
        assert!(stepped.mask.is_none());
        record.push(stepped.index);
    };
    let unmasked = replay_prefix_tree(&task, &judged, &streams, &constructions, &settings, false, &indices);
    let masked_indices: Vec<StreamReplay<Vec<usize>>> = tree.iter().map(|outcome| StreamReplay { record: outcome.record.iter().map(|(index, _)| *index).collect(), fault: outcome.fault.clone() }).collect();
    assert_eq!(unmasked, masked_indices);

    let order = sorted_streams(&streams);
    let sorted: Vec<&[(u32, Emitter)]> = order.iter().map(|&index| streams[index].as_slice()).collect();
    let model = |stream: &[(u32, Emitter)]| stream.iter().filter(|(_, emitter)| *emitter == Emitter::Model).count();
    assert!(model_steps(&sorted) < streams.iter().map(|stream| model(stream)).sum::<usize>());
}

/// A stream that shares with the stream before it a shorter prefix than that stream shares with the one before it.
fn branches_below_an_earlier_branch(sorted: &[&[(u32, Emitter)]]) -> bool {
    let shared: Vec<usize> = sorted.windows(2).map(|pair| pair[0].iter().zip(pair[1]).take_while(|(x, y)| x == y).count()).collect();
    shared.windows(2).any(|pair| pair[1] < pair[0])
}

#[test]
fn a_prefix_tree_replay_steps_each_model_token_of_the_tree_once() {
    let dir = std::env::temp_dir().join(format!("arclog-prefix-steps-{}", std::process::id()));
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
    let whole = token_ids(cases[0].stream.as_ref().expect("a stream"), &vocabulary);
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");

    let session = corpus_session();
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let tokens = |ids: &[(u32, Emitter)]| -> Vec<_> { ids.iter().map(|(id, emitter)| (vocabulary.token(*id).expect("a token").clone(), *emitter)).collect() };

    // A position where the model writes with no token forced, with the ids the mask refuses there that sort before and after the whole stream's token.
    let refusing_at = |cut: usize| -> Option<(usize, Vec<u32>)> {
        if whole[cut].1 != Emitter::Model {
            return None;
        }
        let mut decoder = Decoder::new(&task, &session, registry, &constructions, &settings).judging(Arc::clone(&train));
        let replayed = replay(&mut decoder, &tokens(&whole[..cut]), true, &mut |_, _| ControlFlow::Continue(())).ok()?;
        if !replayed.forced().is_empty() {
            return None;
        }
        let mask = decoder.admissible();
        let refusing: Vec<u32> = (0..vocabulary.len() as u32).filter(|id| !mask.contains(*id)).collect();
        let refused: Vec<u32> = refusing.iter().copied().filter(|id| *id < whole[cut].0).take(1).chain(refusing.iter().copied().filter(|id| *id > whole[cut].0).take(1)).collect();
        (refused.len() == 2).then_some((cut, refused))
    };
    let first = (2..whole.len()).find_map(refusing_at).expect("a position of the stream refuses a token");
    let last = (2..whole.len()).rev().find_map(refusing_at).expect("a position of the stream refuses a token");
    assert!(first.0 < last.0, "two positions of the stream refuse a token");
    // Streams that each continue a prefix of the whole stream with a refused token, at two cuts.
    let mut streams = vec![whole.clone()];
    let mut expected: Vec<Vec<(u32, Emitter)>> = vec![whole.clone()];
    for (cut, refused) in [first, last] {
        expected.push(whole[..cut].to_vec());
        for id in refused {
            let mut stream = whole[..cut].to_vec();
            stream.push((id, Emitter::Model));
            streams.push(stream);
        }
    }
    let order = sorted_streams(&streams);
    let sorted: Vec<&[(u32, Emitter)]> = order.iter().map(|&index| streams[index].as_slice()).collect();
    assert!(branches_below_an_earlier_branch(&sorted), "the streams branch below an earlier branch");

    let calls = Cell::new(0usize);
    let record = |_: &mut (), _: &Decoder<'_>, _: arclog::decode::replay::Stepped<'_>| calls.set(calls.get() + 1);
    replay_prefix_tree(&task, &judged, &streams, &constructions, &settings, false, &record);
    // The refused tokens are never stepped, so the steps are those of the streams cut before them.
    let order = sorted_streams(&expected);
    let sorted: Vec<&[(u32, Emitter)]> = order.iter().map(|&index| expected[index].as_slice()).collect();
    assert_eq!(calls.get(), model_steps(&sorted));
}

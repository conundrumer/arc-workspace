//! The replay of streams as a prefix tree gives, for each stream, the record
//! and the outcome that a replay of that stream from a new decoder gives.

use arclog::decode::corpus::{read_task_files, replay_prefix_tree, corpus_session, sorted_streams, mask_computations};
use arclog::decode::replay::replay;
use arclog::decode::{Decoder, TokenMask};
use arclog::eval::instance::Constructions;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::registry::Registry;
use arclog::stream::corpus::{solver_streams, token_ids, WantedCases};
use arclog::stream::{DecodeSettings, Emitter, Vocabulary};
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
    let record = |record: &mut Record, _: &Decoder<'_>, stepped: arclog::decode::replay::Stepped<'_>| record.push((stepped.index, stepped.mask.clone()));

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
            let replayed = replay(&mut decoder, &tokens(&whole[..cut]), &mut |_, _| ControlFlow::Continue(())).ok()?;
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

    let tree = replay_prefix_tree(&task, &judged, &streams, &constructions, &record);
    assert_eq!(tree.len(), streams.len());
    for (stream, outcome) in streams.iter().zip(&tree) {
        let mut decoder = fresh();
        let mut recorded = Record::new();
        let alone = replay(&mut decoder, &tokens(stream), &mut |decoder, stepped| {
            record(&mut recorded, decoder, stepped);
            ControlFlow::Continue(())
        })
        .and_then(|replayed| replayed.unfinished().map_or(Ok(recorded), Err));
        assert_eq!(*outcome, alone);
    }
    assert!(tree[1].is_err(), "the refused stream fails: {:?}", tree[1]);
    assert!(tree[0].is_ok(), "{:?}", tree[0]);

    let order = sorted_streams(&streams);
    let sorted: Vec<&[(u32, Emitter)]> = order.iter().map(|&index| streams[index].as_slice()).collect();
    let model = |stream: &[(u32, Emitter)]| stream.iter().filter(|(_, emitter)| *emitter == Emitter::Model).count();
    assert!(mask_computations(&sorted) < streams.iter().map(|stream| model(stream)).sum::<usize>());
}

//! The corpus workload of `Decoder::admissible`: `check` compares its mask
//! with the mask of `Decoder::admissible_reference` (`Decoder::next` over every
//! token) at each state of the streams of a corpus's tasks, gold and forked
//! off the gold stream, and `bench` times `Decoder::admissible` at each gold
//! state. The binary builds with the feature `arclog/admissible-reference`.
//!
//! admissible_workload <bench|check> <corpus> <tasks> <task ids...>
use std::path::Path;
use std::sync::Arc;
use std::time::{Duration, Instant};

use arclog::decode::corpus::{corpus_session, read_task_files};
use arclog::decode::{Decoder, TokenMask};
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::registry::Registry;
use arclog::stream::corpus::{WantedCases, solver_streams};
use arclog::stream::{DecodeSettings, Emitter, Token, Vocabulary};

#[derive(Default)]
struct Counts {
    gold: usize,
    forks: usize,
    streams: usize,
    mask_time: Duration,
    times: Vec<f64>,
}

fn mask(decoder: &Decoder<'_>, mode: &str, counts: &mut Counts, gold: bool) -> TokenMask {
    // Forks hold no mask, as in the writer. Each measurement computes a new mask.
    let fresh = decoder.fork();
    let start = Instant::now();
    let actual = fresh.admissible();
    let elapsed = start.elapsed();
    if mode == "bench" {
        counts.mask_time += elapsed;
        counts.times.push(elapsed.as_secs_f64());
    }
    if mode == "check" {
        let expected = decoder.fork().admissible_reference();
        if actual != expected {
            let different: Vec<_> = (0..decoder.vocabulary().len() as u32).filter(|id| actual.contains(*id) != expected.contains(*id)).map(|id| (id, decoder.vocabulary().token(id), actual.contains(id), expected.contains(id))).collect();
            eprintln!("mask difference: {different:?}");
            if let Some((program, _)) = decoder.partial() {
                eprintln!("{}", arclog::write::write_synthesized(&program, Registry::get()));
            }
        }
        assert_eq!(
            actual,
            expected,
            "different mask after {} gold and {} fork states; trace {:?}",
            counts.gold,
            counts.forks,
            decoder.trace()
        );
    }
    if gold {
        counts.gold += 1;
    } else {
        counts.forks += 1;
    }
    actual
}

fn main() -> Result<(), String> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let [mode, corpus, tasks, ids @ ..] = args.as_slice() else {
        return Err("usage: admissible_workload <bench|check> <corpus> <tasks> <task ids...>".into());
    };
    assert!(["bench", "check"].contains(&mode.as_str()));
    assert!(!ids.is_empty(), "supply explicit task ids to bound the workload");
    let settings = DecodeSettings::corpus();
    let vocabulary = Vocabulary::new(Registry::get(), &settings);
    let constructions = arclog_constructions::shared()?;
    let mut counts = Counts::default();
    eprintln!("pid {}", std::process::id());
    for id in ids {
        let streams = solver_streams(Path::new(corpus), id, WantedCases::Concept, &vocabulary)?;
        let (task, judged) = read_task_files(Path::new(tasks), id)?;
        let session = corpus_session();
        let train: Arc<[_]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
        for case in streams.into_iter().filter(|case| !case.demonstrated) {
            let stream = case.stream?;
            let mut decoder = Decoder::new(&task, &session, Registry::get(), constructions, &settings).judging(train.clone());
            let mut forced = Vec::new();
            for (index, (token, emitter)) in stream.tokens.iter().enumerate() {
                if *emitter == Emitter::Engine {
                    assert_eq!(forced.remove(0), *token, "{id} at {index}");
                    continue;
                }
                assert!(forced.is_empty());
                let current = mask(&decoder, mode, &mut counts, true);
                let gold_id = vocabulary.id(token).unwrap();
                assert!(current.contains(gold_id), "{id} at {index}: {token:?}");
                if mode == "check" && counts.gold % 11 == 0 {
                    // Deterministic alternative choices and multi-token off-gold walks.
                    let choices: Vec<u32> = (0..vocabulary.len() as u32).filter(|id| current.contains(*id) && *id != gold_id).collect();
                    for seed in 0..2 {
                        if choices.is_empty() {
                            break;
                        }
                        let mut fork = decoder.fork();
                        let first = choices[(counts.gold * 17 + seed * 31) % choices.len()];
                        fork.step(vocabulary.token(first).unwrap().clone()).map_err(|e| format!("fork: {e:?}"))?;
                        for depth in 0..6 {
                            let found = mask(&fork, mode, &mut counts, false);
                            let choices: Vec<u32> = (0..vocabulary.len() as u32).filter(|id| found.contains(*id)).collect();
                            if choices.is_empty() {
                                break;
                            }
                            let next = choices[(counts.gold * 13 + seed * 23 + depth * 7) % choices.len()];
                            let next: Token = vocabulary.token(next).unwrap().clone();
                            fork.step(next).map_err(|e| format!("fork: {e:?}"))?;
                        }
                    }
                }
                forced = decoder.step(token.clone()).map_err(|e| format!("{id} at {index}: {e:?}"))?.forced.into();
            }
            assert!(forced.is_empty());
            // Includes the terminal state's empty mask after a consistent OUT.
            mask(&decoder, mode, &mut counts, true);
            counts.streams += 1;
            eprintln!("{id}: complete, {} gold / {} off-gold states", counts.gold, counts.forks);
        }
    }
    report(mode, counts)
}

fn report(mode: &str, mut counts: Counts) -> Result<(), String> {
    if counts.streams == 0 {
        return Err("the selected tasks contain no non-demonstrated concept streams".into());
    }
    println!("{} streams; {} gold states; {} off-gold states", counts.streams, counts.gold, counts.forks);
    if mode == "check" {
        println!("all masks bit-identical");
    }
    if mode == "bench" {
        counts.times.sort_by(f64::total_cmp);
        println!(
            "fresh admissible: mean {:.3} ms; median {:.3} ms; p99 {:.3} ms; total {:.3} s",
            counts.mask_time.as_secs_f64() * 1000.0 / counts.gold as f64,
            counts.times[counts.times.len() / 2] * 1000.0,
            counts.times[(counts.times.len() - 1) * 99 / 100] * 1000.0,
            counts.mask_time.as_secs_f64()
        );
    }
    Ok(())
}

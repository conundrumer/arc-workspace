//! The judge's comparison refuses wrong input, as
//! `docs/engine/cases.md#one-case` gives.

use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::judge::solves::{OutputSet, solves};
use arclog::task::{Alt, AltKind, Grid, JudgedPair};
use arclog::terms::Color;

fn grid(digit: u8) -> Grid {
    let color = Color::from_digit(digit).expect("a color");
    Grid::from_rows(Box::new([Box::new([color])])).expect("a grid")
}

#[test]
fn an_open_world_train_pair_whose_set_lacks_its_given_output_is_not_solved() {
    let pair = JudgedPair { output: grid(1), alt: None };
    let candidates = PairCandidates::of(&pair, Section::Train, World::Open);
    assert!(!solves(&OutputSet::Grids(Box::new([grid(2)])), &candidates));
}

#[test]
fn a_set_that_matches_no_candidate_is_not_solved() {
    let pair = JudgedPair { output: grid(1), alt: Some(Alt { kind: AltKind::Rule, grid: grid(2) }) };
    let candidates = PairCandidates::of(&pair, Section::Train, World::Closed);
    assert!(!solves(&OutputSet::Grids(Box::new([grid(1), grid(2)])), &candidates));
}

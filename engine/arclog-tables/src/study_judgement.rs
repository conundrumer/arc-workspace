//! Study FITS uses the same closed-world candidate sets as native decode.
//! Model-to-given equality remains independent diagnostic evidence.
use arclog::judge::candidates::{Candidates, PairCandidates, Section, World};
use arclog::judge::solves::{OutputSet, solves};
use arclog::task::{Grid, JudgedTask, Task};
use serde_json::{Value, json};

pub(super) struct TrainJudge<'a> {
    pub pairs: Vec<PairCandidates<'a>>,
}

impl<'a> TrainJudge<'a> {
    pub fn new(task: &Task, judged: &'a JudgedTask) -> Result<Self, String> {
        if task.train.len() != judged.train.len()
            || task.train.iter().zip(&judged.train).any(|(pair, judged)| pair.output != judged.output)
        {
            return Err("study judged train pairs differ from the evaluation task".into());
        }
        Ok(Self { pairs: judged.train.iter()
            .map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect() })
    }
}

#[derive(Default)]
pub(super) struct ModelSet {
    grids: Vec<Grid>,
    undefined: bool,
}

impl ModelSet {
    pub fn observe(&mut self, grid: Option<Grid>) {
        match grid {
            Some(grid) if !self.grids.contains(&grid) => self.grids.push(grid),
            Some(_) => {},
            None => self.undefined = true,
        }
    }

    pub fn finish(self, pair: &PairCandidates<'_>) -> Value {
        let count = self.grids.len();
        let defined = !self.undefined && count > 0;
        let set = if defined { OutputSet::Grids(self.grids.into_boxed_slice()) } else { OutputSet::Undefined };
        let sizes = match &pair.candidates {
            Candidates::Closed(candidates) => candidates.iter().map(|candidate| candidate.grids().len()).collect::<Vec<_>>(),
            Candidates::Open { .. } => unreachable!("study train judge constructs closed-world candidates"),
        };
        json!({"fits":solves(&set,pair),"fit_comparison":"native_closed_candidate_set",
            "distinct_output_grids":count,"output_set_defined":defined,"accepted_candidate_sizes":sizes})
    }
}

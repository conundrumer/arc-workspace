//! The report of the share of decodes and of runs that each bound stopped. It
//! reads traces and changes nothing in them.

use std::collections::BTreeMap;

use super::{DecodeTrace, RunTrace, Stop};

/// The share of traces that each bound stopped: each trace counts once, under
/// the first bound it records, and a trace that records none counts in
/// `total` alone.
#[derive(Clone, PartialEq, Eq, Debug, Default)]
pub struct StopShares {
    pub total: usize,
    pub stopped: BTreeMap<Stop, usize>,
}

impl StopShares {
    /// The share of the traces that `stop` stopped, `0` where there are none.
    pub fn share(&self, stop: Stop) -> f64 {
        match self.total {
            0 => 0.0,
            total => self.stopped.get(&stop).copied().unwrap_or(0) as f64 / total as f64,
        }
    }

    fn of(firsts: impl Iterator<Item = Option<Stop>>) -> StopShares {
        let mut shares = StopShares::default();
        for first in firsts {
            shares.total += 1;
            if let Some(stop) = first {
                *shares.stopped.entry(stop).or_default() += 1;
            }
        }
        shares
    }
}

/// The share of the decodes that each bound stopped. A decode is a candidate
/// program, and counts under the first bound its trace records.
pub fn stop_shares<'t>(decodes: impl IntoIterator<Item = &'t DecodeTrace>) -> StopShares {
    StopShares::of(decodes.into_iter().map(|trace| trace.records().into_iter().find_map(|record| record.stop)))
}

/// The share of the runs that each bound stopped, counted as
/// [`stop_shares`] counts decodes.
pub fn run_stop_shares<'t>(runs: impl IntoIterator<Item = &'t RunTrace>) -> StopShares {
    StopShares::of(runs.into_iter().map(|trace| trace.records().into_iter().find_map(|record| record.stop)))
}

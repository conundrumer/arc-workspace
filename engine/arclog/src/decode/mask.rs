//! The checks of a decode's prefix: the result of each check of
//! [`crate::check::checks`] on the program a state gives, by the checks'
//! prefix forms, and the resolution of that program, each kept in a cache
//! that every fork of a decode shares.

use std::sync::{Arc, Mutex};

use super::Refusal;
use crate::check::prefix::check_prefix;
use crate::check::{PrefixResult, SolverClauses};
use crate::hash::{StableHash, StableHashMap};
use crate::program::path::NodePath;
use crate::program::{Node, Program};
use crate::registry::Registry;
use crate::resolver::{resolve, ResolvedProgram, SolverScope};

/// The verdict of the checks on a prefix: none, or the refusal of the
/// first check that refuses it.
type Verdict = Option<Refusal>;

/// Entries by the canonical hash of their program, each with its program,
/// so that a match of hashes is settled by the programs' equality.
type Entries<K, V> = Mutex<StableHashMap<K, Vec<(Node<Program>, V)>>>;

/// The resolutions and the verdicts of the prefixes a decode and its forks
/// have checked.
#[derive(Default)]
pub(super) struct Cache {
    resolved: Entries<StableHash, Arc<ResolvedProgram>>,
    verdicts: Entries<(StableHash, Option<NodePath>), Verdict>,
}

impl Cache {
    /// The resolution of `program`, a synthesized program, whose names
    /// resolve within it.
    pub(super) fn resolved(&self, program: &Node<Program>, registry: &Registry) -> Arc<ResolvedProgram> {
        lookup(&self.resolved, program.canonical_hash(), program, || Arc::new(resolve(program, None, &SolverScope::default(), registry).value))
    }

    /// The verdict of the checks on the prefix whose partial form is the
    /// last form of `program`, open at `open`.
    pub(super) fn verdict(&self, program: &Node<Program>, open: Option<&NodePath>, registry: &Registry) -> Verdict {
        let key = (program.canonical_hash(), open.cloned());
        lookup(&self.verdicts, key, program, || {
            let resolved = self.resolved(program, registry);
            let clauses = SolverClauses::of_program((*resolved).clone());
            check_prefix(&resolved, &clauses, registry, open).into_iter().find_map(|(check, result)| match result {
                PrefixResult::Refuse(refusals) => Some(Refusal::Check { check, refusals }),
                PrefixResult::Undecided => None,
            })
        })
    }
}

/// The value of `entries` at `key` for `program`, made by `make` where the
/// cache holds none. Two threads that miss at once each make the value.
fn lookup<K: std::hash::Hash + Eq, V: Clone>(entries: &Entries<K, V>, key: K, program: &Node<Program>, make: impl FnOnce() -> V) -> V {
    let held = |entries: &Entries<K, V>, key: &K| {
        let entries = entries.lock().expect("no thread panics while it holds the cache");
        entries.get(key).and_then(|bucket| bucket.iter().find(|(held, _)| held == program).map(|(_, value)| value.clone()))
    };
    if let Some(value) = held(entries, &key) {
        return value;
    }
    let value = make();
    let mut entries = entries.lock().expect("no thread panics while it holds the cache");
    entries.entry(key).or_default().push((program.clone(), value.clone()));
    value
}

//! The search of one cluster: propagation to a fixpoint, and then a
//! depth-first search over the options still open, in index order, that
//! keeps an option before it excludes it and propagates after each choice.
//!
//! A node is one choice of the search, the keep or the exclusion of one open
//! option, and the search counts its nodes against the node cap.

use super::cluster::Cluster;
use super::NodeCapReached;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Choice {
    Keep,
    Exclude,
}

/// The choice made for an option, `None` while it is open.
type Mark = Option<Choice>;

/// The search of one cluster, which gives its models one at a time.
pub(super) struct Search<'a> {
    cluster: &'a Cluster,
    /// The states still to visit, each propagated to a fixpoint, the next
    /// to visit last.
    pending: Vec<Box<[Mark]>>,
    nodes: u64,
    node_cap: u64,
}

impl<'a> Search<'a> {
    pub(super) fn new(cluster: &'a Cluster, node_cap: u64) -> Self {
        let mut root = vec![None; cluster.options.len()].into_boxed_slice();
        let singletons = cluster.groups.iter().filter(|group| group.len() == 1).map(|group| (group[0], Choice::Keep)).collect();
        let pending = if propagate(cluster, &mut root, singletons) { vec![root] } else { Vec::new() };
        Search { cluster, pending, nodes: 0, node_cap }
    }

    /// The cluster's next model, as the local indexes of the options it
    /// keeps, or `None` once the search has visited every state.
    pub(super) fn next_model(&mut self) -> Result<Option<Box<[usize]>>, NodeCapReached> {
        while let Some(state) = self.pending.pop() {
            let Some(open) = state.iter().position(|&mark| mark == None) else {
                return Ok(Some((0..state.len()).filter(|&option| state[option] == Some(Choice::Keep)).collect()));
            };
            // The exclusion is pushed first, so the keep is visited first.
            for choice in [Choice::Exclude, Choice::Keep] {
                self.nodes += 1;
                if self.nodes > self.node_cap {
                    self.pending.clear();
                    return Err(NodeCapReached { cap: self.node_cap });
                }
                let mut child = state.clone();
                if propagate(self.cluster, &mut child, vec![(open, choice)]) {
                    self.pending.push(child);
                }
            }
        }
        Ok(None)
    }
}

/// Applies `choices` to `state` and propagates them to a fixpoint: a group with
/// one option left forces it, a kept option excludes the other options of
/// its groups and each option it forms a `never` pair with. Whether the state
/// has a model left, which it has not where an option takes both choices or a
/// group has no option left.
fn propagate(cluster: &Cluster, state: &mut [Mark], mut choices: Vec<(usize, Choice)>) -> bool {
    while let Some((option, choice)) = choices.pop() {
        match state[option] {
            None => state[option] = Some(choice),
            Some(current) if current == choice => continue,
            _ => return false,
        }
        match choice {
            Choice::Keep => {
                for &group in cluster.groups_of[option].iter() {
                    choices.extend(cluster.groups[group].iter().filter(|&&other| other != option).map(|&other| (other, Choice::Exclude)));
                }
                choices.extend(cluster.never_of[option].iter().map(|&other| (other, Choice::Exclude)));
            }
            Choice::Exclude => {
                for &group in cluster.groups_of[option].iter() {
                    let members = &cluster.groups[group];
                    if members.iter().any(|&member| state[member] == Some(Choice::Keep)) {
                        continue;
                    }
                    let mut open = members.iter().filter(|&&member| state[member] == None);
                    match (open.next(), open.next()) {
                        (None, _) => return false,
                        (Some(&last), None) => choices.push((last, Choice::Keep)),
                        _ => {}
                    }
                }
            }
        }
    }
    true
}

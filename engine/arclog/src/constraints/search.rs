//! The search of one cluster: propagation to a fixpoint, and then a
//! depth-first search that branches on a group with the fewest open options
//! (the first such group) and visits one child per open option, with that
//! option kept and propagated, in index order.
//!
//! A node is one child of the search, and the search counts its nodes
//! against the node cap.

use super::cluster::Cluster;
use super::NodeCapReached;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Choice {
    Keep,
    Exclude,
}

/// The open options of the group of `cluster` with the fewest open options,
/// the least group where several have as few, or `None` where no option of
/// `state` is open.
fn branch_group(cluster: &Cluster, state: &State) -> Option<Vec<usize>> {
    let (group, _) = state.groups.iter().enumerate().filter(|(_, group)| group.open > 0).min_by_key(|(_, group)| group.open)?;
    Some(cluster.groups[group].iter().copied().filter(|&option| state.marks[option].is_none()).collect())
}

/// The choice made for an option, `None` while it is open.
type Mark = Option<Choice>;

/// What a state holds of one group, kept up to date as options are marked.
#[derive(Clone, Copy)]
struct GroupState {
    /// Whether a member of the group is kept.
    kept: bool,
    /// The number of members of the group that are open.
    open: usize,
    /// The sum of the local indexes of the open members, which is the index
    /// of the open member where `open` is 1.
    open_index_sum: usize,
}

/// The choices made for the options of a cluster, and the state of each of
/// its groups.
#[derive(Clone)]
struct State {
    marks: Box<[Mark]>,
    groups: Box<[GroupState]>,
}

impl State {
    /// The state of `cluster` with every option open.
    fn open(cluster: &Cluster) -> Self {
        let groups = cluster
            .groups
            .iter()
            .map(|members| GroupState { kept: false, open: members.len(), open_index_sum: members.iter().sum() })
            .collect();
        State { marks: vec![None; cluster.options.len()].into_boxed_slice(), groups }
    }
}

/// The search of one cluster, which gives its models one at a time.
pub(super) struct Search<'a> {
    cluster: &'a Cluster,
    /// The states still to visit, each propagated to a fixpoint, the next
    /// to visit last.
    pending: Vec<State>,
    nodes: u64,
    node_cap: u64,
}

impl<'a> Search<'a> {
    pub(super) fn new(cluster: &'a Cluster, node_cap: u64) -> Self {
        let mut root = State::open(cluster);
        let singletons = cluster.groups.iter().filter(|group| group.len() == 1).map(|group| (group[0], Choice::Keep)).collect();
        let pending = if propagate(cluster, &mut root, singletons) { vec![root] } else { Vec::new() };
        Search { cluster, pending, nodes: 0, node_cap }
    }

    /// The nodes that the search has counted.
    pub(super) fn nodes(&self) -> u64 {
        self.nodes
    }

    /// The cluster's next model, as the local indexes of the options it
    /// keeps, or `None` once the search has visited every state.
    pub(super) fn next_model(&mut self) -> Result<Option<Box<[usize]>>, NodeCapReached> {
        while let Some(state) = self.pending.pop() {
            let Some(open) = branch_group(self.cluster, &state) else {
                return Ok(Some((0..state.marks.len()).filter(|&option| state.marks[option] == Some(Choice::Keep)).collect()));
            };
            // Every open option counts a node, so where they pass the node cap no child is propagated.
            if self.nodes + open.len() as u64 > self.node_cap {
                self.pending.clear();
                return Err(NodeCapReached { cap: self.node_cap });
            }
            // The children are pushed last first, so the first option is visited first.
            for &option in open.iter().rev() {
                self.nodes += 1;
                if self.nodes > self.node_cap {
                    self.pending.clear();
                    return Err(NodeCapReached { cap: self.node_cap });
                }
                let mut child = state.clone();
                if propagate(self.cluster, &mut child, vec![(option, Choice::Keep)]) {
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
fn propagate(cluster: &Cluster, state: &mut State, mut choices: Vec<(usize, Choice)>) -> bool {
    while let Some((option, choice)) = choices.pop() {
        match state.marks[option] {
            None => state.marks[option] = Some(choice),
            Some(current) if current == choice => continue,
            _ => return false,
        }
        for &group in cluster.groups_of[option].iter() {
            let group_state = &mut state.groups[group];
            group_state.open -= 1;
            group_state.open_index_sum -= option;
            match choice {
                Choice::Keep => {
                    group_state.kept = true;
                    choices.extend(cluster.groups[group].iter().filter(|&&other| other != option).map(|&other| (other, Choice::Exclude)));
                }
                Choice::Exclude if group_state.kept => {}
                Choice::Exclude => match group_state.open {
                    0 => return false,
                    1 => choices.push((group_state.open_index_sum, Choice::Keep)),
                    _ => {}
                },
            }
        }
        if choice == Choice::Keep {
            choices.extend(cluster.never_of[option].iter().map(|&other| (other, Choice::Exclude)));
        }
    }
    true
}

//! The constraint module: the models of one pick, as
//! `docs/engine/cases.md#the-constraint-module` gives them, one at a time.
//!
//! The module knows nothing of programs, relations or terms. Its input is a
//! [`Pick`]: a count of options, indexed in the canonical order their builder
//! gives them, its groups and its `never` pairs. Its output is [`Models`], an
//! iterator over the product of the models of the pick's clusters, each
//! cluster split off by the submodule `cluster` and solved by the submodule
//! `search`.

mod cluster;
mod search;

use cluster::Cluster;
use search::Search;

/// One option of a pick, by its index in the canonical order.
pub type OptionIndex = usize;

/// A model of a pick: the options it keeps, in ascending order.
pub type Model = Box<[OptionIndex]>;

/// One pick: its options, its groups, each a set of options of which a model
/// keeps exactly one, and its `never` pairs, two options that no model keeps
/// both of. A `never` pair of one option with itself constrains nothing.
#[derive(Clone, Debug)]
pub struct Pick {
    clusters: Box<[Cluster]>,
}

/// An input that is no pick.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum PickError {
    /// An option index of a group or a pair that is not below the count of
    /// options.
    OptionOutOfRange { option: OptionIndex, options: usize },
    EmptyGroup { group: usize },
    /// An option that a group gives more than once, so the group is no set.
    RepeatedInGroup { group: usize, option: OptionIndex },
    /// An option that stands in no group.
    NoGroup { option: OptionIndex },
}

/// A search that reached the node cap on one cluster: a stop at a bound.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct NodeCapReached {
    pub cap: u64,
}

impl Pick {
    pub fn new(options: usize, groups: &[Box<[OptionIndex]>], never: &[(OptionIndex, OptionIndex)]) -> Result<Self, PickError> {
        let in_range = |option: OptionIndex| {
            if option < options { Ok(option) } else { Err(PickError::OptionOutOfRange { option, options }) }
        };
        let mut grouped = vec![false; options];
        for (group, members) in groups.iter().enumerate() {
            if members.is_empty() {
                return Err(PickError::EmptyGroup { group });
            }
            let mut seen = std::collections::BTreeSet::new();
            for &option in members.iter() {
                in_range(option)?;
                if !seen.insert(option) {
                    return Err(PickError::RepeatedInGroup { group, option });
                }
                grouped[option] = true;
            }
        }
        for &(a, b) in never {
            in_range(a)?;
            in_range(b)?;
        }
        let never: Vec<_> = never.iter().copied().filter(|&(a, b)| a != b).collect();
        if let Some(option) = grouped.iter().position(|&grouped| !grouped) {
            return Err(PickError::NoGroup { option });
        }
        Ok(Pick { clusters: cluster::clusters(options, groups, &never) })
    }

    /// The pick's models, under a cap of `node_cap` search nodes per cluster.
    /// Where `first_only` is set, the iterator gives the first model alone.
    pub fn models(&self, node_cap: u64, first_only: bool) -> Models<'_> {
        Models {
            clusters: self.clusters.iter().map(|cluster| ClusterModels::new(cluster, node_cap)).collect(),
            positions: None,
            first_only,
            done: false,
        }
    }
}

/// The models of a pick, in the lexicographic order of the clusters' models,
/// the cluster of the least option the most significant. An item that is a
/// [`NodeCapReached`] is the last item.
pub struct Models<'a> {
    clusters: Vec<ClusterModels<'a>>,
    /// The index of each cluster's model in the last model given, `None`
    /// before the first.
    positions: Option<Vec<usize>>,
    first_only: bool,
    done: bool,
}

impl Iterator for Models<'_> {
    type Item = Result<Model, NodeCapReached>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.done {
            return None;
        }
        let first = self.positions.is_none();
        let positions = self.positions.get_or_insert_with(|| vec![0; self.clusters.len()]);
        let advanced = if first {
            self.clusters.iter_mut().try_for_each(|cluster| cluster.get(0).map(|_| ())).map(|()| true)
        } else if self.first_only {
            Ok(false)
        } else {
            advance(&mut self.clusters, positions)
        };
        match advanced {
            Ok(true) => Some(Ok(model(&self.clusters, positions))),
            Ok(false) => {
                self.done = true;
                None
            }
            Err(stop) => {
                self.done = true;
                Some(Err(stop))
            }
        }
    }
}

/// The model of the product at `positions`.
fn model(clusters: &[ClusterModels<'_>], positions: &[usize]) -> Model {
    let mut kept: Vec<OptionIndex> = clusters
        .iter()
        .zip(positions)
        .flat_map(|(cluster, &position)| cluster.found[position].iter().map(|&local| cluster.cluster.options[local]))
        .collect();
    kept.sort_unstable();
    kept.into()
}

/// Moves `positions` to the next model of the product: the last cluster that
/// has a next model takes it, and each cluster after it goes back to its
/// first.
fn advance(clusters: &mut [ClusterModels<'_>], positions: &mut [usize]) -> Result<bool, NodeCapReached> {
    for at in (0..clusters.len()).rev() {
        if clusters[at].get(positions[at] + 1)?.is_some() {
            positions[at] += 1;
            positions[at + 1..].fill(0);
            return Ok(true);
        }
    }
    Ok(false)
}

/// The models of one cluster found so far, each as the local indexes of the
/// options it keeps, and the search that finds the rest.
struct ClusterModels<'a> {
    cluster: &'a Cluster,
    search: Search<'a>,
    found: Vec<Box<[usize]>>,
    exhausted: bool,
}

impl<'a> ClusterModels<'a> {
    fn new(cluster: &'a Cluster, node_cap: u64) -> Self {
        ClusterModels { cluster, search: Search::new(cluster, node_cap), found: Vec::new(), exhausted: false }
    }

    /// The cluster's model at `index`, searching on until it is found.
    /// A cluster with no model has one model that keeps none of its options,
    /// so the product goes on over the other clusters.
    fn get(&mut self, index: usize) -> Result<Option<&[usize]>, NodeCapReached> {
        while self.found.len() <= index && !self.exhausted {
            match self.search.next_model()? {
                Some(model) => self.found.push(model),
                None => {
                    self.exhausted = true;
                    if self.found.is_empty() {
                        self.found.push(Box::new([]));
                    }
                }
            }
        }
        Ok(self.found.get(index).map(|model| &model[..]))
    }
}

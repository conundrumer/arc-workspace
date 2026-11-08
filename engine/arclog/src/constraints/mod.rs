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

use crate::product::Product;

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
            product: Product::new(self.clusters.iter().map(|cluster| ClusterModels::new(cluster, node_cap)).collect()),
            first_only,
            done: false,
        }
    }
}

/// The models of a pick, in the lexicographic order of the clusters' models,
/// the cluster of the least option the most significant. An item that is a
/// [`NodeCapReached`] is the last item.
pub struct Models<'a> {
    product: Product<ClusterModels<'a>>,
    first_only: bool,
    done: bool,
}

impl Models<'_> {
    /// The most search nodes that one cluster has counted so far, which the
    /// node cap bounds for each cluster.
    pub fn most_nodes(&self) -> u64 {
        self.product.factors().iter().map(|cluster| cluster.search.nodes()).max().unwrap_or(0)
    }
}

impl Iterator for Models<'_> {
    type Item = Result<Model, NodeCapReached>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.done {
            return None;
        }
        match self.product.next(|cluster, index| cluster.get(index).map(|model| model.is_some())) {
            Ok(Some(element)) => {
                self.done = self.first_only;
                Some(Ok(model(element)))
            }
            Ok(None) => {
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

/// The model of the product at an element, each cluster with the position
/// of its model.
fn model<'c, 'a: 'c>(element: impl Iterator<Item = (&'c ClusterModels<'a>, usize)>) -> Model {
    let mut kept: Vec<OptionIndex> = element
        .flat_map(|(cluster, position)| cluster.found[position].iter().map(|&local| cluster.cluster.options[local]))
        .collect();
    kept.sort_unstable();
    kept.into()
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

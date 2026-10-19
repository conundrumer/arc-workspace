//! The clusters of a pick: the connected components of the graph whose edges
//! join two options of one group or of one `never` pair, each with its
//! constraints over local option indexes.

use super::OptionIndex;

/// One cluster: its options in ascending order, and its groups and its
/// `never` pairs over local indexes, an option's local index being its place
/// in `options`.
#[derive(Clone, Debug)]
pub(super) struct Cluster {
    pub(super) options: Box<[OptionIndex]>,
    pub(super) groups: Box<[Box<[usize]>]>,
    /// The groups of each option.
    pub(super) groups_of: Box<[Box<[usize]>]>,
    /// The options each option forms a `never` pair with.
    pub(super) never_of: Box<[Box<[usize]>]>,
}

/// The clusters of a pick, in the order of their least option.
pub(super) fn clusters(options: usize, groups: &[Box<[OptionIndex]>], never: &[(OptionIndex, OptionIndex)]) -> Box<[Cluster]> {
    let mut components = DisjointSets::new(options);
    for group in groups {
        for &option in &group[1..] {
            components.union(group[0], option);
        }
    }
    for &(a, b) in never {
        components.union(a, b);
    }
    // The cluster of each root, numbered in the order of the least option,
    // and each option's cluster and local index.
    let mut cluster_of_root: Vec<Option<usize>> = vec![None; options];
    let mut cluster_of = vec![0; options];
    let mut local = vec![0; options];
    let mut members: Vec<Vec<OptionIndex>> = Vec::new();
    for option in 0..options {
        let root = components.find(option);
        let cluster = *cluster_of_root[root].get_or_insert_with(|| {
            members.push(Vec::new());
            members.len() - 1
        });
        cluster_of[option] = cluster;
        local[option] = members[cluster].len();
        members[cluster].push(option);
    }
    let mut cluster_groups: Vec<Vec<Box<[usize]>>> = vec![Vec::new(); members.len()];
    for group in groups {
        cluster_groups[cluster_of[group[0]]].push(group.iter().map(|&option| local[option]).collect());
    }
    let mut cluster_never: Vec<Vec<(usize, usize)>> = vec![Vec::new(); members.len()];
    for &(a, b) in never {
        cluster_never[cluster_of[a]].push((local[a], local[b]));
    }
    members
        .into_iter()
        .zip(cluster_groups)
        .zip(cluster_never)
        .map(|((options, groups), never)| {
            let mut groups_of = vec![Vec::new(); options.len()];
            for (group, members) in groups.iter().enumerate() {
                for &option in members.iter() {
                    groups_of[option].push(group);
                }
            }
            let mut never_of = vec![Vec::new(); options.len()];
            for (a, b) in never {
                never_of[a].push(b);
                never_of[b].push(a);
            }
            Cluster {
                options: options.into(),
                groups: groups.into(),
                groups_of: groups_of.into_iter().map(Into::into).collect(),
                never_of: never_of.into_iter().map(Into::into).collect(),
            }
        })
        .collect()
}

/// A union-find over option indexes, with path halving.
struct DisjointSets {
    parent: Vec<usize>,
}

impl DisjointSets {
    fn new(count: usize) -> Self {
        DisjointSets { parent: (0..count).collect() }
    }

    fn find(&mut self, mut item: usize) -> usize {
        while self.parent[item] != item {
            self.parent[item] = self.parent[self.parent[item]];
            item = self.parent[item];
        }
        item
    }

    fn union(&mut self, a: usize, b: usize) {
        let (a, b) = (self.find(a), self.find(b));
        self.parent[a.max(b)] = a.min(b);
    }
}

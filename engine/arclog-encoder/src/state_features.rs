//! What a state says of a candidate query over it: the numbers of the state's graph, and each table's
//! relation to the candidate. The contract's `State` holds these as functions of the state, and none of them
//! depends on the order in which a program writes its queries.

use std::collections::{BTreeSet, HashMap, HashSet};

/// A table or relation of a program, with its form and the names its form reads.
#[derive(Debug, Clone)]
pub struct Node {
    pub name: String,
    pub form: u64,
    pub reads: Vec<String>,
}

/// A program's graph, from the `state` of a tables file.
pub fn nodes_of(state: &serde_json::Value) -> Vec<Node> {
    state["nodes"].as_array().into_iter().flatten().filter_map(|node| {
        Some(Node {
            name: node["name"].as_str()?.to_string(),
            form: node["form"].as_u64()?,
            reads: node["reads"].as_array()?.iter().filter_map(|read| read.as_str().map(str::to_string)).collect(),
        })
    }).collect()
}

/// A table of a state as a candidate query stands to it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Relation {
    /// The candidate's form reads it.
    Parent,
    /// The candidate's form reads it through other queries.
    Ancestor,
    /// Neither.
    Other,
}

impl Relation {
    pub const ALL: [Relation; 3] = [Relation::Parent, Relation::Ancestor, Relation::Other];

    pub fn word(self) -> &'static str {
        match self {
            Relation::Parent => "parent",
            Relation::Ancestor => "ancestor",
            Relation::Other => "other",
        }
    }
}

/// The nodes earlier than a form, each with its relation to a candidate at that form that reads `parents`.
pub fn relations<'n>(nodes: &'n [Node], form: u64, parents: &[String]) -> Vec<(&'n Node, Relation)> {
    let by_name: HashMap<&str, &Node> = nodes.iter().filter(|node| node.form < form).map(|node| (node.name.as_str(), node)).collect();
    let direct: HashSet<&str> = parents.iter().map(String::as_str).collect();
    let mut reached: HashSet<&str> = HashSet::new();
    let mut stack: Vec<&str> = direct.iter().copied().collect();
    while let Some(name) = stack.pop() {
        if let Some(node) = by_name.get(name) {
            for read in &node.reads {
                if reached.insert(read.as_str()) {
                    stack.push(read.as_str());
                }
            }
        }
    }
    nodes.iter().filter(|node| node.form < form).map(|node| {
        let relation = if direct.contains(node.name.as_str()) {
            Relation::Parent
        } else if reached.contains(node.name.as_str()) {
            Relation::Ancestor
        } else {
            Relation::Other
        };
        (node, relation)
    }).collect()
}

/// The numbers of a state's graph at a candidate at `form` that reads `parents`. A number counts members:
/// a depth is 0 where a query reads no member, and 1 more than the deepest member it reads otherwise.
pub fn graph_numbers(nodes: &[Node], form: u64, parents: &[String]) -> Vec<(&'static str, f32)> {
    let mut members: Vec<&Node> = nodes.iter().filter(|node| node.form < form).collect();
    members.sort_by_key(|node| node.form);
    let mut depth: HashMap<&str, i32> = HashMap::new();
    for node in &members {
        let own = node.reads.iter().filter_map(|read| depth.get(read.as_str())).max().map_or(0, |deepest| deepest + 1);
        depth.insert(node.name.as_str(), own);
    }
    let deepest = depth.values().copied().max().unwrap_or(0);
    let used: HashSet<&str> = members.iter().flat_map(|node| node.reads.iter().map(String::as_str)).collect();
    let leaves: HashSet<&str> = members.iter().map(|node| node.name.as_str()).filter(|name| !used.contains(name)).collect();
    let read: BTreeSet<&str> = parents.iter().map(String::as_str).filter(|name| depth.contains_key(name)).collect();
    let own_depth = read.iter().map(|name| depth[name]).max().map_or(0, |most| most + 1);
    let gaps: Vec<i32> = read.iter().map(|name| deepest - depth[name]).collect();
    let related = relations(nodes, form, parents);
    let count_of = |wanted: Relation| related.iter().filter(|(_, relation)| *relation == wanted).count() as f32;
    let read_leaves = read.iter().filter(|name| leaves.contains(**name)).count();
    vec![
        ("members", members.len() as f32),
        ("parents", count_of(Relation::Parent)),
        ("ancestors", count_of(Relation::Ancestor)),
        ("others", count_of(Relation::Other)),
        ("depth", own_depth as f32),
        ("depth-below-deepest", (deepest - own_depth) as f32),
        ("deepest", f32::from(own_depth >= deepest)),
        ("roots", members.iter().filter(|node| !node.reads.iter().any(|read| depth.contains_key(read.as_str()))).count() as f32),
        ("leaves", leaves.len() as f32),
        ("leaves-read", read_leaves as f32),
        ("leaves-left", (leaves.len() - read_leaves) as f32),
        ("reads-deepest", gaps.iter().filter(|gap| **gap == 0).count() as f32),
        ("read-gap-least", gaps.iter().copied().min().unwrap_or(0) as f32),
        ("read-gap-greatest", gaps.iter().copied().max().unwrap_or(0) as f32),
    ]
}

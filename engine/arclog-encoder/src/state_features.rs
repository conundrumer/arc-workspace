//! What a state says of its tables and of a candidate query over it: the numbers of the state's graph, each
//! table's relation to another, and the values of two tables. The contract's `State` holds these as functions of the
//! state, and none of them depends on the order in which a program writes its queries.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

use crate::generate::{Generated, Generators, Walker};
use crate::lookup::{LookupMap, LookupSet};
use crate::query_vector::agrees;
use crate::run::{stored_tables, Host};
use crate::table_vector::{table_vector, two_tables_vector, Grids, TableVector};

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
    let by_name: LookupMap<&str, &Node> = nodes.iter().filter(|node| node.form < form).map(|node| (node.name.as_str(), node)).collect();
    let direct: LookupSet<&str> = parents.iter().map(String::as_str).collect();
    let mut reached: LookupSet<&str> = LookupSet::new();
    let mut stack: Vec<&str> = parents.iter().map(String::as_str).collect();
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
    let mut depth: LookupMap<&str, i32> = LookupMap::new();
    for node in &members {
        let own = node.reads.iter().filter_map(|read| depth.get(read.as_str())).max().map_or(0, |deepest| deepest + 1);
        depth.insert(node.name.as_str(), own);
    }
    let deepest = depth.max_of(|_, deepest| *deepest).unwrap_or(0);
    let used: LookupSet<&str> = members.iter().flat_map(|node| node.reads.iter().map(String::as_str)).collect();
    let leaves: LookupSet<&str> = members.iter().map(|node| node.name.as_str()).filter(|name| !used.contains(name)).collect();
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

/// A shape over several vectors: the least, the mean and the greatest of its mean over the examples, where a
/// vector with no value of the shape counts as 0.
pub fn pool(vectors: &[&TableVector]) -> Vec<(u64, f32, f32, f32)> {
    let mut held: LookupMap<u64, (f32, f32, f32, usize)> = LookupMap::new();
    for vector in vectors {
        for shape in 0..vector.shapes.len() {
            let (_, mean, _, count) = vector.over_examples(shape, false);
            if count == 0 {
                continue;
            }
            let mean = mean as f32;
            let entry = held.entry(vector.shapes[shape]).or_insert((f32::INFINITY, 0.0, f32::NEG_INFINITY, 0));
            entry.0 = entry.0.min(mean);
            entry.1 += mean;
            entry.2 = entry.2.max(mean);
            entry.3 += 1;
        }
    }
    let total = vectors.len();
    held.into_sorted_vec().into_iter().map(|(shape, (least, sum, most, seen))| {
        let least = if seen < total { least.min(0.0) } else { least };
        let most = if seen < total { most.max(0.0) } else { most };
        (shape, least, sum / total as f32, most)
    }).collect()
}

/// What a whole state says of each of its nodes: how deep it stands, and how many nodes it reads and read it.
pub fn member_numbers(nodes: &[Node]) -> BTreeMap<String, Vec<(&'static str, f32)>> {
    fn depth_of<'n>(name: &'n str, by_name: &LookupMap<&'n str, &'n Node>, memo: &mut LookupMap<&'n str, i32>) -> i32 {
        if let Some(found) = memo.get(name) {
            return *found;
        }
        let own = by_name.get(name).map_or(0, |node| node.reads.iter().filter(|read| by_name.contains_key(read.as_str())).map(|read| 1 + depth_of(read.as_str(), by_name, memo)).max().unwrap_or(0));
        memo.insert(name, own);
        own
    }
    let by_name: LookupMap<&str, &Node> = nodes.iter().map(|node| (node.name.as_str(), node)).collect();
    let mut memo = LookupMap::new();
    let depths: Vec<i32> = nodes.iter().map(|node| depth_of(node.name.as_str(), &by_name, &mut memo)).collect();
    let deepest = depths.iter().copied().max().unwrap_or(0);
    let mut out = BTreeMap::new();
    for (node, depth) in nodes.iter().zip(&depths) {
        let (ancestors, descendants) = closures(nodes, &node.name);
        let uses = nodes.iter().filter(|other| other.reads.contains(&node.name)).count();
        let reads = node.reads.iter().filter(|read| by_name.contains_key(read.as_str())).count();
        out.insert(node.name.clone(), vec![
            ("members", nodes.len() as f32),
            ("depth", *depth as f32),
            ("depth-below-deepest", (deepest - depth) as f32),
            ("deepest", f32::from(*depth == deepest)),
            ("leaf", f32::from(uses == 0)),
            ("root", f32::from(reads == 0)),
            ("uses", uses as f32),
            ("reads", reads as f32),
            ("ancestors", ancestors.len() as f32),
            ("descendants", descendants.len() as f32),
        ]);
    }
    out
}

/// The nodes that a node reads through any chain, and those that read it through any chain.
fn closures(nodes: &[Node], name: &str) -> (BTreeSet<String>, BTreeSet<String>) {
    let by_name: LookupMap<&str, &Node> = nodes.iter().map(|node| (node.name.as_str(), node)).collect();
    let mut ancestors = BTreeSet::new();
    let mut stack = vec![name.to_string()];
    while let Some(at) = stack.pop() {
        if let Some(node) = by_name.get(at.as_str()) {
            for read in node.reads.iter().filter(|read| by_name.contains_key(read.as_str())) {
                if ancestors.insert(read.clone()) {
                    stack.push(read.clone());
                }
            }
        }
    }
    let mut descendants = BTreeSet::new();
    let mut stack = vec![name.to_string()];
    while let Some(at) = stack.pop() {
        for node in nodes.iter().filter(|node| node.reads.contains(&at)) {
            if descendants.insert(node.name.clone()) {
                stack.push(node.name.clone());
            }
        }
    }
    (ancestors, descendants)
}

/// One member of a state at one assignment: its numbers, its values with each other table, and those values
/// pooled by the other table's relation to it. `used_by` pools the vectors of the tables that read it.
pub struct MemberVector {
    pub name: String,
    pub assignment: String,
    pub numbers: Vec<(&'static str, f32)>,
    pub edges: Vec<(String, &'static str, TableVector)>,
    pub pools: Vec<(&'static str, Vec<(u64, f32, f32, f32)>)>,
    pub used_by: Vec<(u64, f32, f32, f32)>,
}

/// Each member of a state at each assignment of its table. `d` is the size of the vectors that `used_by` pools.
pub fn state_vectors(host: &Host, grids: &Grids, families: &Generators, d: usize) -> Result<Vec<MemberVector>, String> {
    let facts = host.program_facts();
    let mut tables = BTreeMap::new();
    for (identity, spelled) in &facts.table_names {
        if let Ok(table) = stored_tables(host, spelled) {
            tables.insert(identity.clone(), table);
        }
    }
    let mut nodes: Vec<Node> = Vec::new();
    for (form, query) in facts.queries.iter().enumerate() {
        for computed in &query.computes {
            nodes.push(Node { name: computed.clone(), form: form as u64, reads: query.reads.iter().filter(|read| facts.table_names.contains_key(*read)).cloned().collect() });
        }
    }
    let numbers = member_numbers(&nodes);
    let examples = grids.inputs.len();
    let mut out = Vec::new();
    for (identity, own) in &tables {
        let (ancestors, descendants) = closures(&nodes, identity);
        let parents: BTreeSet<&String> = nodes.iter().filter(|node| node.name == *identity).flat_map(|node| node.reads.iter()).collect();
        let users: BTreeSet<&String> = nodes.iter().filter(|node| node.reads.contains(identity)).map(|node| &node.name).collect();
        let word_of = |other: &String| -> &'static str {
            if parents.contains(other) {
                "parent"
            } else if ancestors.contains(other) {
                "ancestor"
            } else if users.contains(other) {
                "child"
            } else if descendants.contains(other) {
                "descendant"
            } else {
                "other"
            }
        };
        for (assignment, table) in &own.at {
            let mut edges = Vec::new();
            let mut user_vectors = Vec::new();
            let mut same = 0.0;
            for (other, theirs) in &tables {
                if other == identity {
                    continue;
                }
                let Some((_, stored)) = theirs.at.iter().find(|(held, _)| agrees(held, assignment)) else { continue };
                if stored.content() == table.content() {
                    same += 1.0;
                }
                let family: Arc<Generated> = families.get_two_tables(table, stored);
                let mut walker = Walker::new(&family);
                edges.push((facts.table_names[other].clone(), word_of(other), two_tables_vector(&mut walker, table, stored, grids, examples, false)));
                if users.contains(other) {
                    let family: Arc<Generated> = families.get(stored, d.max(1));
                    let mut walker = Walker::new(&family);
                    user_vectors.push(table_vector(&mut walker, stored, grids, examples, false));
                }
            }
            let pools = ["parent", "ancestor", "child", "descendant", "other"].into_iter().filter_map(|word| {
                let held: Vec<&TableVector> = edges.iter().filter(|edge| edge.1 == word).map(|edge| &edge.2).collect();
                (!held.is_empty()).then(|| (word, pool(&held)))
            }).collect();
            let mut own_numbers = numbers.get(identity).cloned().unwrap_or_default();
            own_numbers.push(("same-table", same));
            let users_held: Vec<&TableVector> = user_vectors.iter().collect();
            out.push(MemberVector { name: facts.table_names[identity].clone(), assignment: format!("{assignment:?}"), numbers: own_numbers, edges, pools, used_by: pool(&users_held) });
        }
    }
    Ok(out)
}

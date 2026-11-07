//! What the bodies that the evaluator joins for a table say of each of its columns: the relation atoms that hold the column's variable, whether
//! two of them stand in one conjunction, how many alternatives an `OR` offers for it and whether they bind it from different sources, and
//! which pairs of columns one atom holds. The bodies are the IR of `arclog_tables::structure::relation_bodies`. Over several bodies, a count is
//! the greatest, and a flag holds where it holds in some body.

use std::collections::BTreeSet;

use serde_json::Value;

/// What a relation atom reads.
type Reads = (&'static str, String);

enum Node {
    Atom { reads: Reads, args: Vec<(String, Option<String>)> },
    Lib { relation: String, args: Vec<Option<String>>, computes: Vec<String> },
    Comparison { first: String, makes: bool },
    Or { exported: Vec<String>, branches: Vec<Body> },
    /// A `NOT` or an `ALL`, whose body no feature of a column here reads.
    Filter,
}

struct Body {
    /// The variable at each column of the table.
    columns: Vec<Option<String>>,
    nodes: Vec<Node>,
}

fn strings(value: &Value) -> Vec<String> {
    value.as_array().into_iter().flatten().filter_map(|item| item.as_str().map(str::to_string)).collect()
}

fn variable(value: &Value) -> Option<String> {
    value["v"].as_str().map(str::to_string)
}

fn clause(value: &Value) -> Vec<Node> {
    value["nodes"].as_array().into_iter().flatten().map(node).collect()
}

fn node(value: &Value) -> Node {
    match value["k"].as_str().unwrap_or("") {
        "atom" => {
            let read = &value["read"];
            let reads = if let Some(name) = read["fact"].as_str() {
                ("fact", name.to_string())
            } else if !read["key"].is_null() {
                ("key", String::new())
            } else if let Some(table) = read["table"].as_i64().filter(|table| *table >= 0) {
                ("table", table.to_string())
            } else {
                ("absent", String::new())
            };
            let args = value["args"].as_array().into_iter().flatten().map(|arg| (arg[0].as_str().unwrap_or("").to_string(), variable(&arg[1]))).collect();
            Node::Atom { reads, args }
        }
        "lib" => Node::Lib {
            relation: value["relation"].as_str().unwrap_or("").to_string(),
            args: value["args"].as_array().into_iter().flatten().map(|arg| variable(&arg[1])).collect(),
            computes: strings(&value["computes"]),
        },
        "cmp" => Node::Comparison { first: value["first"].as_str().unwrap_or("").to_string(), makes: value["binds_first"].as_bool().unwrap_or(false) },
        "or" => Node::Or { exported: strings(&value["exported"]), branches: value["branches"].as_array().into_iter().flatten().map(|branch| Body { columns: Vec::new(), nodes: clause(branch) }).collect() },
        _ => Node::Filter,
    }
}

/// The variables that an atom or a lib atom holds.
fn held<'n>(node: &'n Node) -> Vec<&'n str> {
    match node {
        Node::Atom { args, .. } => args.iter().filter_map(|(_, variable)| variable.as_deref()).collect(),
        Node::Lib { args, .. } => args.iter().filter_map(|variable| variable.as_deref()).collect(),
        _ => Vec::new(),
    }
}

/// `body` and the body of each branch of its `OR` nodes, at any depth.
fn conjunctions<'b>(body: &'b [Node], out: &mut Vec<&'b [Node]>) {
    out.push(body);
    for node in body {
        if let Node::Or { branches, .. } = node {
            for branch in branches {
                conjunctions(&branch.nodes, out);
            }
        }
    }
}

/// What binds `variable` in `nodes`: the relation an atom reads and its column, the lib relation that computes it, an equality that makes
/// it, and the same for the branches of an `OR` that exports it.
fn sources(nodes: &[Node], variable: &str, out: &mut BTreeSet<(Reads, Option<String>)>) {
    for node in nodes {
        match node {
            Node::Atom { reads, args } => out.extend(args.iter().filter(|(_, held)| held.as_deref() == Some(variable)).map(|(column, _)| (reads.clone(), Some(column.clone())))),
            Node::Lib { relation, computes, .. } if computes.iter().any(|computed| computed == variable) => {
                out.insert((("lib", relation.clone()), None));
            }
            Node::Comparison { first, makes: true } if first == variable => {
                out.insert((("equal", String::new()), None));
            }
            Node::Or { exported, branches } if exported.iter().any(|name| name == variable) => {
                for branch in branches {
                    sources(&branch.nodes, variable, out);
                }
            }
            _ => {}
        }
    }
}

/// What the bodies say of one column.
#[derive(Clone, Copy, Debug, Default)]
pub struct ColumnBody {
    pub relation_atoms: usize,
    pub joins: bool,
    pub alternatives: usize,
    pub alternatives_differ: bool,
}

/// What the bodies say of one table.
#[derive(Clone, Debug, Default)]
pub struct TableBody {
    pub reads_one_table_twice: bool,
    /// The pairs of columns, in each order, that one relation atom holds.
    pub shared: BTreeSet<(usize, usize)>,
}

fn column_body(body: &Body, variable: Option<&str>) -> ColumnBody {
    let mut out = ColumnBody::default();
    let Some(variable) = variable else { return out };
    out.relation_atoms = body.nodes.iter().filter(|node| matches!(node, Node::Atom { .. }) && held(node).contains(&variable)).count();
    let mut all = Vec::new();
    conjunctions(&body.nodes, &mut all);
    for nodes in all {
        if nodes.iter().filter(|node| matches!(node, Node::Atom { .. }) && held(node).contains(&variable)).count() >= 2 {
            out.joins = true;
        }
        for node in nodes {
            if let Node::Or { exported, branches } = node {
                if exported.iter().any(|name| name == variable) {
                    out.alternatives += branches.len();
                    let kinds: BTreeSet<BTreeSet<(Reads, Option<String>)>> = branches
                        .iter()
                        .map(|branch| {
                            let mut found = BTreeSet::new();
                            sources(&branch.nodes, variable, &mut found);
                            found
                        })
                        .collect();
                    if kinds.len() > 1 {
                        out.alternatives_differ = true;
                    }
                }
            }
        }
    }
    out
}

fn table_body(body: &Body) -> bool {
    let mut all = Vec::new();
    conjunctions(&body.nodes, &mut all);
    all.iter().any(|nodes| {
        let mut reads: Vec<&Reads> = Vec::new();
        for node in nodes.iter() {
            if let Node::Atom { reads: read, .. } = node {
                if read.0 == "table" || read.0 == "fact" {
                    reads.push(read);
                }
            }
        }
        reads.iter().any(|read| reads.iter().filter(|other| *other == read).count() >= 2)
    })
}

/// The column features and the table's, over `bodies`, the JSON bodies of a table whose columns have the identities `idents`. None where the
/// table has no body.
pub fn features(bodies: &[Value], idents: &[String]) -> Option<(Vec<ColumnBody>, TableBody)> {
    if bodies.is_empty() {
        return None;
    }
    let mut columns = vec![ColumnBody::default(); idents.len()];
    let mut table = TableBody::default();
    for given in bodies {
        let mut at: Vec<(&str, String)> = Vec::new();
        for pair in given["table_columns"].as_array().into_iter().flatten() {
            if let (Some(column), Some(variable)) = (pair[0].as_str(), pair[1].as_str()) {
                at.push((column, variable.to_string()));
            }
        }
        // The last variable listed for a column is the column's.
        let variable_of = |column: &String| at.iter().rev().find(|(own, _)| own == column).map(|(_, variable)| variable.clone());
        let body = Body { columns: idents.iter().map(variable_of).collect(), nodes: clause(&given["clause"]) };
        for (index, own) in columns.iter_mut().enumerate() {
            let found = column_body(&body, body.columns[index].as_deref());
            own.relation_atoms = own.relation_atoms.max(found.relation_atoms);
            own.joins |= found.joins;
            own.alternatives = own.alternatives.max(found.alternatives);
            own.alternatives_differ |= found.alternatives_differ;
        }
        table.reads_one_table_twice |= table_body(&body);
        for i in 0..idents.len() {
            for j in 0..idents.len() {
                let (Some(a), Some(b)) = (body.columns[i].as_deref(), body.columns[j].as_deref()) else { continue };
                if i != j && body.nodes.iter().any(|node| matches!(node, Node::Atom { .. }) && held(node).contains(&a) && held(node).contains(&b)) {
                    table.shared.insert((i, j));
                }
            }
        }
    }
    Some((columns, table))
}

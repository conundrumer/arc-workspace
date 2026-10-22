//! `ResolvedProgram::column_names` names each row position of a node's
//! relation by the column's name, and gives `None` for a node whose
//! columns are not known. The `<record>.<field>` names of a record's
//! fields are checked in the unit tests of `resolver/columns.rs`.

use arclog::layout::SourceFile;
use arclog::read::read_arclog;
use arclog::registry::Registry;
use arclog::resolver::{resolve, GraphNodeIndex, ResolvedProgram};

fn resolved(text: &str) -> ResolvedProgram {
    let read = read_arclog(text, SourceFile::Arclog).expect("the program reads");
    assert!(read.diagnostics.is_empty(), "{:?}", read.diagnostics);
    let (program, _) = read.value;
    let resolved = resolve(&program, None, &Default::default(), Registry::get());
    assert!(resolved.diagnostics.is_empty(), "{:?}", resolved.diagnostics);
    resolved.value
}

/// The column names of each node of `program`, in node order.
fn all_names(program: &ResolvedProgram) -> Vec<Option<Vec<String>>> {
    (0..program.graph.nodes.len() as u32).map(|node| program.column_names(GraphNodeIndex(node))).collect()
}

#[test]
fn a_relation_of_plain_columns_gives_their_names() {
    let program = resolved("(RULE &cell (input *P *Col))\n");
    assert!(all_names(&program).contains(&Some(vec!["P".to_owned(), "Col".to_owned()])));
}

#[test]
fn a_node_of_a_fact_has_no_names() {
    let program = resolved("(RULE &cell (input *P *Col))\n");
    assert_eq!(program.column_names(GraphNodeIndex(0)), None);
}

#[test]
fn a_node_past_the_graph_has_no_names() {
    let program = resolved("(RULE &cell (input *P *Col))\n");
    assert_eq!(program.column_names(GraphNodeIndex(1000)), None);
}

//! The graph relation of a named relation in a checked program: the lookup
//! of a relation by its name, and of `&output` in a case program.

use crate::check::CheckedProgram;
use crate::program::{DeclaredName, ProgramRelation, RelationName};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::types::GraphRelation;

/// The relation of `&output` in `program`, or `None` where it derives none.
pub fn output_relation(program: &CheckedProgram) -> Option<GraphRelation> {
    relation_of(program, &ProgramRelation::Declared(RelationName(DeclaredName::Written("&output".into()))))
}

/// The relation that a clause derives or a parameter stores as `name` in
/// `program`, or `None` where no clause or parameter gives it.
pub fn relation_of(program: &CheckedProgram, name: &ProgramRelation) -> Option<GraphRelation> {
    let node = program.program.graph.nodes.iter().position(|node| match &node.kind {
        DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => relation == name,
        _ => false,
    })?;
    Some(GraphRelation { node: GraphNodeIndex(node as u32), output: None })
}

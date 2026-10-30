//! The graph relation of a named relation in a checked program: the lookup
//! of a relation by its name, and of the `OUT` form's in a case program.

use crate::check::CheckedProgram;
use crate::program::{InstanceName, OutputOwner, OutputStep, PortName, ProgramRelation};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::types::GraphRelation;

/// The relation of the last `OUT` form of `program`, the program's output, or
/// `None` where it holds none.
pub fn output_relation(program: &CheckedProgram) -> Option<GraphRelation> {
    let nodes = program.program.graph.nodes.iter().enumerate();
    let (node, _) = nodes.filter_map(|(index, node)| match &node.kind {
        DependencyKind::Out(form) => Some((index, form)),
        _ => None,
    }).max_by(|(_, a), (_, b)| a.cmp(b))?;
    Some(GraphRelation { node: GraphNodeIndex(node as u32), output: None })
}

/// The relation that a clause derives, a parameter stores or a `ONE` mark chooses as `name` in
/// `program`, or an instance's output as `&<instance>.<port>`, or `None`
/// where none gives it.
pub fn relation_of(program: &CheckedProgram, name: &ProgramRelation) -> Option<GraphRelation> {
    let node = program.program.graph.nodes.iter().position(|node| match &node.kind {
        DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => relation == name,
        DependencyKind::Chosen(chosen) => matches!(name, ProgramRelation::Declared(declared) if declared == chosen),
        DependencyKind::InstanceOutput { instance, output } => {
            matches!(name, ProgramRelation::Output(of) if of.of == OutputOwner::Instance(instance.clone()) && *of.path == [OutputStep::Port(output.clone())])
        }
        _ => false,
    })?;
    Some(GraphRelation { node: GraphNodeIndex(node as u32), output: None })
}

/// The relation of the input `input` of the instance `instance` in `program`,
/// the rows its `INIT` form writes for it (or, where a `DET` of
/// `&<instance>.<input>` gives it, that `DET`'s), or `None` where the
/// instance has no such input.
pub fn input_relation(program: &CheckedProgram, instance: &InstanceName, input: &PortName) -> Option<GraphRelation> {
    for (index,node) in program.program.graph.nodes.iter().enumerate() {
        if matches!(&node.kind,DependencyKind::RecursiveInstance(own) if own==instance) {
            let relation=GraphRelation {node:GraphNodeIndex(index as u32),output:Some(std::sync::Arc::from([OutputStep::Port(input.clone())]))};
            let form=program.program.form_of(relation.node);
            let root=crate::program::path::NodeRef::Program(program.program.program.value());
            if let Some(crate::program::path::NodeRef::Instance(written))=crate::program::path::node_at(root,form) {
                if crate::program::written_inputs(written.key.as_ref(),&written.inputs).any(|own|own.name==*input) {return Some(relation);}
            }
        }
    }
    let node = program
        .program
        .graph
        .nodes
        .iter()
        .position(|node| matches!(&node.kind, DependencyKind::InstanceInput { instance: of, input: port } if of == instance && port == input))?;
    Some(GraphRelation { node: GraphNodeIndex(node as u32), output: None })
}

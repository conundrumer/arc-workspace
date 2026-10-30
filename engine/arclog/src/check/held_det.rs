//! Admission of gold parameter values into another checked program.
use super::CheckedProgram;
use crate::decode::held_dets;
use crate::program::ProgramRelation;
use crate::program::path::NodePath;
use crate::resolver::GraphNodeIndex;
use crate::types::GraphRelation;

/// A static interface failure. This checks the encoding carried by held rows;
/// proposal membership and ONE admissibility remain evaluation operations.
#[derive(Clone, Debug)]
pub struct HeldDetInterfaceError {
    pub relation: ProgramRelation,
    pub form: NodePath,
    pub reason: &'static str,
}

impl std::fmt::Display for HeldDetInterfaceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "held_det_interface:{}: {:?} at {:?}", self.reason, self.relation, self.form)
    }
}
impl std::error::Error for HeldDetInterfaceError {}
impl From<HeldDetInterfaceError> for crate::eval::RunFault {
    fn from(error: HeldDetInterfaceError) -> Self {
        Self {message: error.to_string().into(), form: error.form}
    }
}

impl CheckedProgram {
    /// Admit every assignable gold DET, including those the target does not
    /// read. Source types must fit the target types in the native lattice.
    pub fn check_held_det_interfaces(&self, target: &Self) -> Result<(), HeldDetInterfaceError> {
        let targets = held_dets(target);
        for det in held_dets(self) {
            self.held_det_nodes(target, &det.relation, Some(det.node),
                targets.iter().find(|d| d.relation == det.relation).map(|d| d.node))?;
        }
        Ok(())
    }

    /// Admit one carried relation by its original gold identity. A receipt's
    /// queried-program owner alone does not establish this source schema.
    pub fn check_held_det_interface(&self, target: &Self, relation: &ProgramRelation) -> Result<crate::judge::determination::Det, HeldDetInterfaceError> {
        let source = held_dets(self).iter().find(|d| &d.relation == relation).map(|d| d.node);
        let destination = held_dets(target).into_iter().find(|d| &d.relation == relation);
        self.held_det_nodes(target, relation, source, destination.as_ref().map(|d| d.node))?;
        Ok(destination.expect("the interface check requires a target DET"))
    }

    fn held_det_nodes(&self, target: &Self, relation: &ProgramRelation,
        source: Option<GraphNodeIndex>, destination: Option<GraphNodeIndex>) -> Result<(), HeldDetInterfaceError> {
        let form = destination.map(|n| target.program.form_of(n).clone())
            .or_else(|| source.map(|n| self.program.form_of(n).clone())).unwrap_or_default();
        let fail = |reason| HeldDetInterfaceError {relation: relation.clone(), form: form.clone(), reason};
        let source = source.ok_or_else(|| fail("missing_source"))?;
        let destination = destination.ok_or_else(|| fail("missing_target"))?;
        let source_paths = self.program.row_paths(source).ok_or_else(|| fail("schema_unavailable"))?;
        let target_paths = target.program.row_paths(destination).ok_or_else(|| fail("schema_unavailable"))?;
        if source_paths != target_paths { return Err(fail("column_identity")); }
        let gold = self.types.columns(&GraphRelation {node: source, output: None})
            .ok_or_else(|| fail("schema_unavailable"))?;
        let mutant = target.types.columns(&GraphRelation {node: destination, output: None})
            .ok_or_else(|| fail("schema_unavailable"))?;
        if gold.len() != mutant.len() { return Err(fail("arity")); }
        // Subtypes retain their encoding on widening, e.g. Offset -> Box.
        if !gold.iter().zip(mutant).all(|(g, m)| crate::registry::at_or_under(g, m)) {
            return Err(fail("type_narrowing"));
        }
        Ok(())
    }
}

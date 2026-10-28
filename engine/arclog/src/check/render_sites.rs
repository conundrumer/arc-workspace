//! Renderer access to the same inferred site types and grid rules as checks.
use super::frames::FormGrids;
use super::inference::{CaseInferences, Inference, ScopeBody, SiteReading};
use super::types::PoseOr;
use super::{CheckedProgram, SolverClauses};
use crate::mutation::path_json;
use crate::program::path::{NodePath, NodeRef};
use crate::program::*;
use crate::registry::Registry;
use crate::types::{ValueType, typed};
use serde_json::{Value, json};

pub fn export(checked: &CheckedProgram, registry: &Registry) -> Result<Value, String> {
    let clauses = SolverClauses::of_shared_program(std::sync::Arc::clone(&checked.program));
    let cases = CaseInferences::new(&clauses, registry);
    let inference = Inference::new(&checked.program, &cases);
    let mut arguments = Vec::new();
    let mut comparisons = Vec::new();
    fn frame(ty: &ValueType, label: Option<LabelId>, grids: &FormGrids<'_, '_>) -> Value {
        if !crate::registry::has_frame(ty) {
            return json!({"status":"not_applicable"});
        }
        match label {
            Some(label) => super::frames::render_grid_evidence(grids, label),
            None => {
                json!({"status":"contextual_reserved_zero","meaning":"zero margins in the relation's reference frame; no independently bound label frame"})
            }
        }
    }
    fn walk_site<'a>(
        site: &'a Site,
        at: &NodePath,
        atom: Option<&'a Atom>,
        column: &mut Vec<ColumnName>,
        inference: &Inference<'a>,
        reading: SiteReading<'_, 'a>,
        grids: &FormGrids<'_, 'a>,
        out: &mut Vec<Value>,
    ) -> Result<(), String> {
        column.push(site.column.clone());
        for (i, arg) in site.value.args.iter().enumerate() {
            let arg_at = at.child(i as u32);
            let (label, field) = match arg {
                SiteArg::Field(inner) => {
                    walk_site(inner, &arg_at, atom, column, inference, reading, grids, out)?;
                    continue;
                }
                SiteArg::Label(l) => (*l, None),
                SiteArg::NamedLabel { name, label } => (*label, Some(name)),
            };
            let mut path = column.clone();
            path.extend(field.cloned());
            let column_type = atom.and_then(|a| inference.site_type(reading, a, &path));
            let label_id = crate::types::use_label(label);
            let ty = match label_id {
                Some(l) => typed(reading.labels, l),
                None => column_type.clone(),
            }
            .ok_or_else(|| format!("no native inferred argument type at {arg_at:?}"))?;
            let zero = if label == LabelUse::Zero {
                Some(crate::study::render_terms::zero_meaning(&ty)?)
            } else {
                None
            };
            out.push(json!({"path":path_json(&arg_at),"site_path":path_json(at),"scope_path":path_json(reading.path),
                "label_id":label_id.map(|l|l.0),"resolved_type":format!("{ty:?}"),
                "column_type":column_type.map(|t|format!("{t:?}")),"frame":frame(&ty,label_id,grids),"literal":zero}));
        }
        column.pop();
        Ok(())
    }
    fn walk<'a>(
        node: NodeRef<'a>,
        at: &NodePath,
        inference: &Inference<'a>,
        reading: SiteReading<'_, 'a>,
        grids: &FormGrids<'_, 'a>,
        arguments: &mut Vec<Value>,
        comparisons: &mut Vec<Value>,
    ) -> Result<(), String> {
        if let Some(atom) = node.atom() {
            for (i, s) in atom.sites.iter().enumerate() {
                walk_site(
                    s,
                    &at.child(i as u32),
                    Some(atom),
                    &mut Vec::new(),
                    inference,
                    reading,
                    grids,
                    arguments,
                )?;
            }
            return Ok(());
        }
        if let NodeRef::InstanceInput(input) = node {
            for (i, s) in input.head.iter().enumerate() {
                walk_site(
                    s,
                    &at.child(i as u32),
                    None,
                    &mut Vec::new(),
                    inference,
                    reading,
                    grids,
                    arguments,
                )?;
            }
            return walk(
                NodeRef::Body(input.body.value()),
                &at.child(input.head.len() as u32),
                inference,
                reading,
                grids,
                arguments,
                comparisons,
            );
        }
        if let NodeRef::Conjunct(Conjunct::Constraint(c)) = node {
            let first = typed(reading.labels, c.first.label)
                .ok_or_else(|| format!("no first operand type at {at:?}"))?;
            let second = match c.second {
                Operand::Label(l) => {
                    let ty = typed(reading.labels, l.label)
                        .ok_or_else(|| format!("no second operand type at {at:?}"))?;
                    json!({"label_id":l.label.0,"resolved_type":format!("{ty:?}"),"frame":frame(&ty,Some(l.label),grids)})
                }
                Operand::Zero => {
                    json!({"resolved_type":format!("{first:?}"),"literal":crate::study::render_terms::zero_meaning(&first)?,"frame":frame(&first,None,grids)})
                }
            };
            comparisons.push(json!({"path":path_json(at),"scope_path":path_json(reading.path),"operator":format!("{:?}",c.op),
                "first":{"label_id":c.first.label.0,"resolved_type":format!("{first:?}"),"frame":frame(&first,Some(c.first.label),grids)},"second":second}));
        }
        for (i, child) in node.children().into_iter().enumerate() {
            walk(
                child,
                &at.child(i as u32),
                inference,
                reading,
                grids,
                arguments,
                comparisons,
            )?;
        }
        Ok(())
    }
    for (i, form) in checked.program.program.value().forms.iter().enumerate() {
        let at = NodePath::top(i as u32);
        let inferred = inference
            .infer(&at)
            .ok_or_else(|| format!("no native form inference at {at:?}"))?;
        let scope = ScopeBody::of(form, registry);
        let reading = inferred.reading(PoseOr::Given);
        let grids = FormGrids::new(&inference, reading, &scope);
        let reading = SiteReading {
            grids: Some(&grids),
            ..reading
        };
        walk(
            NodeRef::from(form),
            &at,
            &inference,
            reading,
            &grids,
            &mut arguments,
            &mut comparisons,
        )?;
    }
    Ok(json!({"arguments":arguments,"comparisons":comparisons,
        "frame_analysis":"native checker grid evidence; made/native table frames are a separate export part"}))
}

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
use std::collections::BTreeMap;

/// Native expected column type, distinct from the existing label's type.
/// None records a missing column type (for example an input-head declaration).
#[derive(Debug)]
pub(crate) struct SiteColumnType {
    pub scope_path: NodePath,
    pub ty: Option<ValueType>,
}

#[derive(Debug)]
pub(crate) struct TypedSiteExport {
    pub json: Value,
    pub columns: BTreeMap<NodePath, SiteColumnType>,
}

pub fn export(checked: &CheckedProgram, registry: &Registry) -> Result<Value, String> {
    Ok(export_typed(checked, registry)?.json)
}

pub(crate) fn export_typed(checked: &CheckedProgram, registry: &Registry) -> Result<TypedSiteExport, String> {
    let clauses = SolverClauses::of_shared_program(std::sync::Arc::clone(&checked.program));
    let cases = CaseInferences::new(&clauses, registry);
    let inference = Inference::new(&checked.program, &cases);
    let mut arguments = Vec::new();
    let mut comparisons = Vec::new();
    let mut variables = Vec::new();
    let mut scopes = Vec::new();
    let mut column_types = BTreeMap::new();
    let names = crate::write::label_names(&checked.program.program, registry);
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
        column_types: &mut BTreeMap<NodePath, SiteColumnType>,
    ) -> Result<(), String> {
        column.push(site.column.clone());
        for (i, arg) in site.value.args.iter().enumerate() {
            let arg_at = at.child(i as u32);
            let (label, field) = match arg {
                SiteArg::Field(inner) => {
                    walk_site(inner, &arg_at, atom, column, inference, reading, grids, out, column_types)?;
                    continue;
                }
                SiteArg::Label(l) => (*l, None),
                SiteArg::NamedLabel { name, label } => (*label, Some(name)),
            };
            let mut path = column.clone();
            path.extend(field.cloned());
            let column_type = atom.and_then(|a| inference.site_type(reading, a, &path));
            column_types.insert(arg_at.clone(), SiteColumnType {
                scope_path: reading.path.clone(), ty: column_type.clone(),
            });
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
        column_types: &mut BTreeMap<NodePath, SiteColumnType>,
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
                    column_types,
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
                    column_types,
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
                column_types,
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
                column_types,
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
        let first_argument = arguments.len();
        let first_comparison = comparisons.len();
        walk(
            NodeRef::from(form),
            &at,
            &inference,
            reading,
            &grids,
            &mut arguments,
            &mut comparisons,
            &mut column_types,
        )?;
        // Index original occurrences once per scope, rather than rescanning
        // every site and declaration for every variable.
        let mut occurrence_index = std::collections::BTreeMap::<u32,Vec<Value>>::new();
        for argument in &arguments[first_argument..] {
            if let Some(label) = argument["label_id"].as_u64() {
                occurrence_index.entry(label as u32).or_default()
                    .push(json!({"kind":"site_argument","path":argument["path"]}));
            }
        }
        for comparison in &comparisons[first_comparison..] {
            for operand in ["first","second"] {
                if let Some(label) = comparison[operand]["label_id"].as_u64() {
                    occurrence_index.entry(label as u32).or_default()
                        .push(json!({"kind":"comparison_operand","path":comparison["path"],"operand":operand}));
                }
            }
        }
        fn declarations(node: NodeRef<'_>, at: &NodePath, out: &mut std::collections::BTreeMap<u32,Vec<Value>>) {
            let columns = match node {
                NodeRef::Clause(c) => Some(&c.columns[..]),
                NodeRef::KeyClause(k) => Some(&k.key.columns[..]),
                NodeRef::Out(o) => Some(&o.key.columns[..]),
                _ => None,
            };
            if let Some(columns) = columns {
                for (i,column) in columns.iter().enumerate() {
                    out.entry(column.label.0).or_default()
                        .push(json!({"kind":"declaration_column","path":path_json(at),"column":i}));
                }
            }
            for (i,child) in node.children().into_iter().enumerate() {
                declarations(child,&at.child(i as u32),out);
            }
        }
        declarations(NodeRef::from(form),&at,&mut occurrence_index);
        let mut scope_labels = Vec::new();
        for (label, _) in reading.labels {
            let ty = typed(reading.labels, *label)
                .ok_or_else(||format!("no native inferred variable type at {at:?} label {label:?}"))?;
            let occurrences = occurrence_index.remove(&label.0).unwrap_or_default();
            if occurrences.is_empty() {
                return Err(format!("native inferred variable has no original occurrence at {at:?} label {label:?}"));
            }
            variables.push(json!({"scope_path":path_json(reading.path),"label_id":label.0,
                "label_spelling":names[i].iter().find(|(id,_)|id==label).map(|(_,name)|name.as_ref()),
                "resolved_type":format!("{ty:?}"),"frame":frame(&ty,Some(*label),&grids),"occurrences":occurrences}));
            scope_labels.push(label.0);
        }
        scopes.push(json!({"scope_path":path_json(reading.path),"label_ids":scope_labels,
            "argument_count":arguments.len()-first_argument,"comparison_count":comparisons.len()-first_comparison}));
    }
    Ok(TypedSiteExport { columns: column_types, json: json!({"arguments":arguments,"comparisons":comparisons,"variables":variables,"scopes":scopes,
        "variable_identity":"(scope_path,label_id); includes comparison-only and branch-local variables; occurrence paths are original AST paths",
        "frame_analysis":"native checker grid evidence; made/native table frames are a separate export part"}) })
}

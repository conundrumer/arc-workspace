//! Renderer access to the same inferred site types and grid rules as checks.
use super::frames::FormGrids;
use super::inference::{CaseInferences, Inference, ScopeBody, SiteReading};
use super::types::{demo_rule, form_at, rule_scope_forms, PoseOr};
use super::{CheckedProgram, SolverClauses};
use crate::mutation::path_json;
use crate::program::path::{node_at, NodePath, NodeRef};
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

/// Presentation names for an exact checked prefix; inference is performed only
/// on `checked`. Callers bind each form/LabelId to that prefix, never by name.
/// Unused names do not add variables: only inferred native IDs are looked up.
pub fn export_with_names(checked: &CheckedProgram, registry: &Registry,
    names: &crate::write::LabelNames) -> Result<Value, String> {
    if names.len() != checked.program.program.value().forms.len() {
        return Err("display namespace does not cover this exact checked prefix".into());
    }
    Ok(export_typed_named(checked, registry, names)?.json)
}

pub(crate) fn export_typed(checked: &CheckedProgram, registry: &Registry) -> Result<TypedSiteExport, String> {
    let names = crate::write::label_names(&checked.program.program, registry);
    export_typed_named(checked, registry, &names)
}

pub(crate) fn export_typed_named(checked: &CheckedProgram, registry: &Registry,
    names: &crate::write::LabelNames) -> Result<TypedSiteExport, String> {
    export_sites(checked, registry, Some(names))
}

/// The column type of each site argument of `checked`, as [`export_typed`]
/// gives them, without that export's JSON. It fails where `export_typed` does.
pub(crate) fn site_columns(checked: &CheckedProgram, registry: &Registry) -> Result<BTreeMap<NodePath, SiteColumnType>, String> {
    Ok(export_sites(checked, registry, None)?.columns)
}

/// The export of the site types of `checked`, whose JSON names the labels
/// with `names`; with no `names`, the JSON is null.
fn export_sites(checked: &CheckedProgram, registry: &Registry,
    names: Option<&crate::write::LabelNames>) -> Result<TypedSiteExport, String> {
    /// What the walk of a form collects. The JSON is built only where the
    /// export has names.
    struct Sites {
        rendered: bool,
        arguments: Vec<Value>,
        comparisons: Vec<Value>,
        column_types: BTreeMap<NodePath, SiteColumnType>,
        /// The labels that a site argument or an operand of the scope uses.
        used: std::collections::BTreeSet<u32>,
        /// The path of the label scope that the walk is in.
        scope: NodePath,
        /// The path of each node that opens a label scope of its own, which
        /// the walk of the scope it stands in leaves out.
        nested: Vec<NodePath>,
    }
    let clauses = SolverClauses::of_shared_program(std::sync::Arc::clone(&checked.program));
    let cases = CaseInferences::new(&clauses, registry);
    let inference = Inference::new(&checked.program, &cases);
    let mut out = Sites { rendered: names.is_some(), arguments: Vec::new(), comparisons: Vec::new(), column_types: BTreeMap::new(), used: Default::default(),
        scope: NodePath::default(), nested: Vec::new() };
    let mut variables = Vec::new();
    let mut scopes = Vec::new();
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
        out: &mut Sites,
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
            out.column_types.insert(arg_at.clone(), SiteColumnType {
                scope_path: out.scope.clone(), ty: column_type.clone(),
            });
            let label_id = crate::types::use_label(label);
            out.used.extend(label_id.map(|l| l.0));
            let ty = match label_id {
                Some(l) => typed(reading.labels, l),
                None => column_type.clone(),
            }
            .ok_or_else(|| format!("no native inferred argument type at {arg_at:?}"))?;
            if !out.rendered {
                if label == LabelUse::Zero {
                    crate::study::render_terms::check_zero(&ty)?;
                }
                continue;
            }
            let zero = if label == LabelUse::Zero {
                Some(crate::study::render_terms::zero_meaning(&ty)?)
            } else {
                None
            };
            out.arguments.push(json!({"path":path_json(&arg_at),"site_path":path_json(at),"scope_path":path_json(&out.scope),
                "label_id":label_id.map(|l|l.0),"resolved_type":format!("{ty:?}"),
                "type_identity":crate::study::render_correspondence::type_json(&ty),
                "column_path":path.iter().map(crate::study::render::column).collect::<Vec<_>>(),
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
        out: &mut Sites,
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
                    out,
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
                    out,
                )?;
            }
            return walk(
                NodeRef::Body(input.body.value()),
                &at.child(input.head.len() as u32),
                inference,
                reading,
                grids,
                out,
            );
        }
        if let NodeRef::Conjunct(Conjunct::Constraint(c)) = node {
            let first = typed(reading.labels, c.first.label)
                .ok_or_else(|| format!("no first operand type at {at:?}"))?;
            out.used.insert(c.first.label.0);
            let second = match c.second {
                Operand::Label(l) => {
                    let ty = typed(reading.labels, l.label)
                        .ok_or_else(|| format!("no second operand type at {at:?}"))?;
                    out.used.insert(l.label.0);
                    out.rendered.then(|| json!({"label_id":l.label.0,"resolved_type":format!("{ty:?}"),"frame":frame(&ty,Some(l.label),grids)}))
                }
                Operand::Zero if out.rendered => {
                    Some(json!({"resolved_type":format!("{first:?}"),"literal":crate::study::render_terms::zero_meaning(&first)?,"frame":frame(&first,None,grids)}))
                }
                Operand::Zero => {
                    crate::study::render_terms::check_zero(&first)?;
                    None
                }
            };
            if let Some(second) = second {
                out.comparisons.push(json!({"path":path_json(at),"scope_path":path_json(&out.scope),"operator":format!("{:?}",c.op),
                    "first":{"label_id":c.first.label.0,"resolved_type":format!("{first:?}"),"frame":frame(&first,Some(c.first.label),grids)},"second":second}));
            }
        }
        for (i, child) in node.children().into_iter().enumerate() {
            if crate::program::canonical::opens_scope(node, i, child) {
                out.nested.push(at.child(i as u32));
                continue;
            }
            walk(
                child,
                &at.child(i as u32),
                inference,
                reading,
                grids,
                out,
            )?;
        }
        Ok(())
    }
    fn declarations(node: NodeRef<'_>, at: &NodePath, out: &mut std::collections::BTreeMap<u32,Vec<Value>>, used: &mut std::collections::BTreeSet<u32>, rendered: bool) {
        let columns = match node {
            NodeRef::Clause(c) => Some(&c.columns[..]),
            NodeRef::KeyClause(k) => Some(&k.key.columns[..]),
            NodeRef::Out(o) => Some(&o.key.columns[..]),
            _ => None,
        };
        if let Some(columns) = columns {
            for (i,column) in columns.iter().enumerate() {
                used.insert(column.label.0);
                if rendered {
                    out.entry(column.label.0).or_default()
                        .push(json!({"kind":"declaration_column","path":path_json(at),"column":i}));
                }
            }
        }
        for (i,child) in node.children().into_iter().enumerate() {
            if !crate::program::canonical::opens_scope(node, i, child) {
                declarations(child,&at.child(i as u32),out,used,rendered);
            }
        }
    }
    // Each label scope: a top-level form, or a scope within one, as
    // `opens_scope` gives them. The forms of a `DEMO_RULE` that share its
    // scope are each read under the inference of the form, and the scope's
    // labels under the inference of the rule.
    let program = checked.program.program.value();
    let root = NodeRef::Program(program);
    let mut pending: Vec<(usize, NodePath)> = (0..program.forms.len()).rev().map(|i| (i, NodePath::top(i as u32))).collect();
    while let Some((i, at)) = pending.pop() {
        let forms: Vec<(NodePath, &Form)> = match node_at(root, &at) {
            Some(NodeRef::DemoRule(_)) => {
                let rule = demo_rule(program, &at).ok_or_else(|| format!("no DEMO_RULE form at {at:?}"))?;
                rule_scope_forms(rule).map(|(index, form)| (at.child(index), form)).collect()
            }
            _ => vec![(at.clone(), form_at(program, &at).ok_or_else(|| format!("no form at {at:?}"))?)],
        };
        let infer = |path: &NodePath| inference.infer(path).ok_or_else(|| format!("no native form inference at {path:?}"));
        let inferred = forms.iter().map(|(path, _)| infer(path)).collect::<Result<Vec<_>, _>>()?;
        let bodies: Vec<ScopeBody> = forms.iter().map(|(_, form)| ScopeBody::of(form, registry)).collect();
        let grids: Vec<FormGrids> = inferred.iter().zip(&bodies).map(|(inferred, body)| FormGrids::new(&inference, inferred.reading(PoseOr::Given), body)).collect();
        let first_argument = out.arguments.len();
        let first_comparison = out.comparisons.len();
        out.used.clear();
        out.scope = at.clone();
        let nested_from = out.nested.len();
        for (((path, form), inferred), grids) in forms.iter().zip(&inferred).zip(&grids) {
            let reading = SiteReading { grids: Some(grids), ..inferred.reading(PoseOr::Given) };
            walk(NodeRef::from(*form), path, &inference, reading, grids, &mut out)?;
        }
        // Index original occurrences once per scope, rather than rescanning
        // every site and declaration for every variable.
        let mut occurrence_index = std::collections::BTreeMap::<u32,Vec<Value>>::new();
        for argument in &out.arguments[first_argument..] {
            if let Some(label) = argument["label_id"].as_u64() {
                occurrence_index.entry(label as u32).or_default()
                    .push(json!({"kind":"site_argument","path":argument["path"]}));
            }
        }
        for comparison in &out.comparisons[first_comparison..] {
            for operand in ["first","second"] {
                if let Some(label) = comparison[operand]["label_id"].as_u64() {
                    occurrence_index.entry(label as u32).or_default()
                        .push(json!({"kind":"comparison_operand","path":comparison["path"],"operand":operand}));
                }
            }
        }
        for (path, form) in &forms {
            declarations(NodeRef::from(*form),path,&mut occurrence_index,&mut out.used,out.rendered);
        }
        // The labels of the scope: those of its one form, or those of the
        // `DEMO_RULE`, whose inference meets the types its forms give them.
        let scope_inferred = if forms.len() == 1 && forms[0].0 == at { std::rc::Rc::clone(&inferred[0]) } else { infer(&at)? };
        let labels = &scope_inferred.reading(PoseOr::Given).labels;
        // The spellings of the labels: those of the top-level form's scope.
        let spellings = names.filter(|_| at.0.len() == 1).map(|names| &names[i]);
        let mut scope_labels = Vec::new();
        for (label, _) in labels.iter() {
            let ty = typed(labels, *label)
                .ok_or_else(||format!("no native inferred variable type at {at:?} label {label:?}"))?;
            if !out.used.remove(&label.0) {
                return Err(format!("native inferred variable has no original occurrence at {at:?} label {label:?}"));
            }
            if names.is_some() {
                let occurrences = occurrence_index.remove(&label.0).unwrap_or_default();
                // The grids of the first form of the scope whose inference holds the label.
                let held = inferred.iter().position(|inferred| inferred.labels.iter().any(|(found, _)| found == label)).unwrap_or(0);
                variables.push(json!({"scope_path":path_json(&at),"label_id":label.0,
                    "label_spelling":spellings.and_then(|names| names.iter().find(|(id,_)|id==label)).map(|(_,name)|name.as_ref()),
                    "resolved_type":format!("{ty:?}"),"frame":frame(&ty,Some(*label),&grids[held]),"occurrences":occurrences}));
                scope_labels.push(label.0);
            }
        }
        if names.is_some() {
            scopes.push(json!({"scope_path":path_json(&at),"label_ids":scope_labels,
                "argument_count":out.arguments.len()-first_argument,"comparison_count":out.comparisons.len()-first_comparison}));
        }
        // The scopes within this one, in the order of their paths.
        let nested: Vec<NodePath> = out.nested.drain(nested_from..).collect();
        pending.extend(nested.into_iter().rev().map(|path| (i, path)));
    }
    let Sites { arguments, comparisons, column_types, .. } = out;
    let json = if names.is_some() {
        json!({"arguments":arguments,"comparisons":comparisons,"variables":variables,"scopes":scopes,
            "variable_identity":"(scope_path,label_id); includes comparison-only and branch-local variables; occurrence paths are original AST paths",
            "frame_analysis":"native checker grid evidence; made/native table frames are a separate export part"})
    } else {
        Value::Null
    };
    Ok(TypedSiteExport { columns: column_types, json })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::study::StudyProgram;

    /// `site_columns` gives the columns of `export_typed` for each program, and
    /// the export alone holds JSON.
    #[test]
    fn site_columns_are_the_columns_of_the_export() {
        let registry = Registry::get();
        let programs = [
            "(RULE &output (input *P *Col))\n(OUT (&output ^P ^Col))\n",
            "(RULE &x (input *P *Col) (inside (:A P) (:B P)))\n(RULE &output (&x *P *Col))\n(OUT (&output ^P ^Col))\n",
            "(RULE &x (input *P *Col) (uniform_inset (:K 0) (:B *A)) (compose (:A A) (:B 0) (:C *C)))\n(RULE &output (&x *P *Col))\n(OUT (&output ^P ^Col))\n",
        ];
        for text in programs {
            let program = StudyProgram::from_sexp(text, registry).unwrap_or_else(|fault| panic!("{text}: {fault}"));
            let full = export_typed(program.checked(), registry).expect("the export");
            let columns = site_columns(program.checked(), registry).expect("the columns");
            assert!(!full.columns.is_empty(), "{text}");
            assert_eq!(format!("{columns:?}"), format!("{:?}", full.columns), "{text}");
            assert!(full.json["arguments"].as_array().is_some_and(|arguments| !arguments.is_empty()), "{text}");
        }
    }
}

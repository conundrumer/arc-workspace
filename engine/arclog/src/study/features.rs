//! Search-point metadata from a separately resolved prefix and candidate.
use super::StudyProgram;
use crate::check::{CheckCache, CheckedProgram, SolverClauses, check_shared_program};
use crate::diagnostic::Severity;
use crate::mutation::{path_json, relation_json};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef, node_at};
use crate::program::*;
use crate::registry::Registry;
use crate::resolver::{SolverScope, resolve};
use crate::types::ValueType;
use serde_json::{Value, json};
use std::sync::Arc;

/// A physical/resolved native type. Pose identity is retained, not flattened
/// to its D4 storage representation; records retain each named native field.
pub fn type_json(ty: &ValueType) -> Value {
    match ty {
        ValueType::Record(fields) => {
            json!({"kind":"Record","fields":fields.iter().map(|(n,t)|json!({"name":super::render::column(n),"type":type_json(t)})).collect::<Vec<_>>()})
        }
        ValueType::Pose(assembly) => {
            json!({"kind":"Pose","native_identity":format!("{assembly:?}")})
        }
        _ => json!({"kind":format!("{ty:?}")}),
    }
}

/// Trim trailing INIT clauses as well as trailing top-level forms. The
/// retained interface is checked afresh; missing parameters stay unavailable.
fn candidate_form(
    form: &Form,
    relative: &[crate::program::path::PathStep],
) -> Result<Form, String> {
    if matches!(form, Form::Choose(_) | Form::RigidDet(_)) {
        return Err("prefix-only contextual CHOOSE/RIGID_DET typing is not yet supported".into());
    }
    let Form::Instance(instance) = form else {
        return match form {
            Form::Clause(_) if relative.len() == 1 && relative[0].0 == 0 => Ok(form.clone()),
            _ => Err("prefix-only contextual typing requires a direct RULE/DET body or INIT input/key body".into()),
        };
    };
    let mut instance = instance.value().clone();
    let Some(first) = relative.first().map(|s| s.0 as usize) else {
        return Err("candidate BODY has no owner child".into());
    };
    if first == 0 && instance.key.is_some() {
        if !((relative.len() == 2 && relative[1].0 == 0)
            || (relative.len() == 3 && relative[1].0 > 0 && relative[2].0 == 1))
        {
            return Err("nested INIT candidate BODY scope is unsupported".into());
        }
        let mut key = instance.key.as_ref().unwrap().value().clone();
        let own = relative
            .get(1)
            .ok_or("candidate key BODY path is incomplete")?
            .0 as usize;
        if own > key.inputs.len() {
            return Err("candidate key input is absent".into());
        }
        key.inputs = key.inputs[..own].to_vec().into();
        instance.key = Some(Node::new(key));
        instance.inputs = Arc::from([]);
    } else {
        if relative.len() != 2 || relative[1].0 != 1 {
            return Err("nested INIT candidate BODY scope is unsupported".into());
        }
        let index = first
            .checked_sub(usize::from(instance.key.is_some()))
            .ok_or("candidate input path is absent")?;
        if index >= instance.inputs.len() {
            return Err("candidate input is absent".into());
        }
        instance.inputs = instance.inputs[..=index].to_vec().into();
    }
    Ok(Form::Instance(Node::new(instance)))
}

/// The source AST boundary is shared by independent syntax and typing exports.
pub fn prefix(program: &StudyProgram, point: &NodePath) -> Result<Node<Program>, String> {
    let Some(NodeRef::Body(_)) = node_at(NodeRef::Program(program.program().value()), point) else {
        return Err("candidate path is not a BODY".into());
    };
    let at = point.0.first().ok_or("candidate has no form")?.0 as usize;
    let mut forms = program.program().value().forms[..at].to_vec();
    forms.push(candidate_form(
        &program.program().value().forms[at],
        &point.0[1..],
    )?);
    Ok(Node::new(Program {
        forms: forms.into(),
    }))
}

pub fn checked_prefix(
    program: &StudyProgram,
    point: &NodePath,
    registry: &Registry,
) -> Result<CheckedProgram, String> {
    check_prefix_syntax(prefix(program, point)?, registry)
}

/// Exact source frontier before the selected clause. INIT retains its key and
/// earlier inputs, never later ports or the candidate input itself.
pub fn frontier(program: &StudyProgram, point: &NodePath) -> Result<Node<Program>, String> {
    let candidate = prefix(program, point)?;
    let mut forms = candidate.value().forms.to_vec();
    let last = forms.pop().ok_or("prefix frontier has no candidate")?;
    if let Form::Instance(instance) = last {
        let mut instance = instance.value().clone();
        let relative = &point.0[1..];
        let first = relative.first().ok_or("INIT frontier path is absent")?.0 as usize;
        if first == 0 && instance.key.is_some() {
            let own = relative[1].0 as usize;
            if own > 0 {
                let mut key = instance.key.as_ref().unwrap().value().clone();
                key.inputs = key.inputs[..own - 1].to_vec().into();
                instance.key = Some(Node::new(key));
                forms.push(Form::Instance(Node::new(instance)));
            }
        } else {
            let own = first.checked_sub(usize::from(instance.key.is_some()))
                .ok_or("INIT frontier input is absent")?;
            instance.inputs = instance.inputs[..own].to_vec().into();
            forms.push(Form::Instance(Node::new(instance)));
        }
    }
    Ok(Node::new(Program { forms: forms.into() }))
}

pub fn checked_frontier(program: &StudyProgram, point: &NodePath, registry: &Registry)
    -> Result<CheckedProgram, String> {
    check_prefix_syntax(frontier(program, point)?, registry)
}

fn check_prefix_syntax(prefix: Node<Program>, registry: &Registry) -> Result<CheckedProgram, String> {
    let resolved = resolve(&prefix, None, &SolverScope::default(), registry);
    if resolved
        .diagnostics
        .iter()
        .any(|d| d.severity == Severity::Error)
    {
        return Err(super::diagnostics_text(&resolved.diagnostics));
    }
    let resolved = Arc::new(resolved.value);
    let clauses = SolverClauses::of_shared_program(Arc::clone(&resolved));
    check_shared_program(resolved, &clauses, registry, &mut CheckCache::default())
        .map_err(|d| super::diagnostics_text(&d))
}

/// Restrict the program's one presentation namespace to the actual native
/// label occurrences in each retained prefix form. The caller constructs
/// `checked` with `checked_prefix` from this same program; no names or IDs
/// are paired across forms, and trailing INIT inputs contribute no names.
pub fn prefix_label_names(
    program: &StudyProgram,
    checked: &CheckedProgram,
    registry: &Registry,
) -> Result<crate::write::LabelNames, String> {
    let display = program.label_names(registry);
    checked.program.program.value().forms.iter().enumerate().map(|(index, form)| {
        let mut present = std::collections::BTreeSet::new();
        crate::safety::each_label_use_at(NodeRef::from(form), &NodePath::top(index as u32), &mut |_, use_| {
            if let Some(id) = crate::types::use_label(use_) { present.insert(id.0); }
        });
        let names = display.get(index).ok_or_else(|| format!("display namespace is missing prefix form {index}"))?;
        let retained = names.iter().filter(|(id, _)| present.contains(&id.0)).cloned().collect::<Vec<_>>();
        if let Some(id) = present.iter().find(|id| !retained.iter().any(|(label, _)| label.0 == **id)) {
            return Err(format!("display namespace is missing native label {id} in prefix form {index}"));
        }
        Ok(retained)
    }).collect()
}

fn label(order: &CanonicalOrder, id: LabelId) -> Result<u32, String> {
    let mut found = order
        .label_scopes()
        .into_iter()
        .flat_map(|(_, labels)| labels.iter())
        .filter(|(l, _)| *l == id)
        .map(|(_, p)| *p);
    let first = found.next().ok_or("canonical label is absent")?;
    if found.any(|p| p != first) {
        return Err("canonical label belongs to ambiguous nested scopes".into());
    }
    Ok(first)
}
fn label_use(order: &CanonicalOrder, l: LabelUse) -> Result<Value, String> {
    Ok(match l {
        LabelUse::Zero => json!({"use":"zero"}),
        LabelUse::Fresh(l) => json!({"use":"fresh","label":label(order,l)?}),
        LabelUse::Join(l) => json!({"use":"join","label":label(order,l)?}),
        LabelUse::Key(l) => json!({"use":"key","label":label(order,l)?}),
    })
}

fn columns(
    order: &CanonicalOrder,
    columns: &[RelationColumn],
    ordered: bool,
) -> Result<Vec<Value>, String> {
    let mut columns = columns
        .iter()
        .map(|c| Ok((label(order, c.label)?, super::render::column(&c.name))))
        .collect::<Result<Vec<_>, String>>()?;
    if !ordered {
        columns.sort_by_key(|(label, _)| *label);
    }
    Ok(columns
        .into_iter()
        .map(|(label, name)| json!({"label":label,"column":name}))
        .collect())
}

/// A canonical AST rendering uses the same recorded native list order and
/// label order as the canonical bytes. It is JSON, not executable source.
fn tree(root: NodeRef<'_>, canonical: &NodePath, order: &CanonicalOrder) -> Result<Value, String> {
    let source = order.source_path(canonical);
    let node = node_at(root, &source).ok_or("canonical path has no source node")?;
    let data = match node {
        NodeRef::Label(l) => {
            let mut value = label_use(order, *l)?;
            if let Some(step) = source.0.last() {
                let parent = NodePath(source.0[..source.0.len() - 1].into());
                if let Some(NodeRef::Site(site)) = node_at(root, &parent) {
                    if let Some(SiteArg::NamedLabel { name, .. }) =
                        site.value.args.get(step.0 as usize)
                    {
                        value["field"] = super::render::column(name);
                    }
                }
            }
            return Ok(value);
        }
        NodeRef::Atom(a) => json!({"kind":"atom","relation":relation_json(&a.relation)}),
        NodeRef::Conjunct(Conjunct::Constraint(c)) => {
            let (op, mut operands, symmetric) = crate::program::canonical::normalized_constraint(c);
            if symmetric {
                operands.sort_by_key(|l| l.and_then(|l| label(order, l.label).ok()));
            }
            return Ok(
                json!({"kind":"constraint","op":format!("{op:?}"),"operands":operands.iter().map(|l|match l {None=>Ok(json!({"zero":true})),Some(l)=>Ok(json!({"label":label(order,l.label)?,"fresh":l.fresh}))}).collect::<Result<Vec<Value>,String>>()?}),
            );
        }
        NodeRef::Conjunct(c) => match c {
            Conjunct::Atom(a) => {
                json!({"kind":"atom","relation":relation_json(&a.value().relation)})
            }
            Conjunct::Not(_) => {
                json!({"kind":"not","relation":node.atom().map(|a|relation_json(&a.relation))})
            }
            Conjunct::Or(_) => json!({"kind":"or"}),
            Conjunct::If { .. } => json!({"kind":"if"}),
            Conjunct::All { .. } => json!({"kind":"all"}),
            _ => unreachable!(),
        },
        NodeRef::Body(_) => json!({"kind":"body"}),
        NodeRef::Site(s) => json!({"kind":"site","column":super::render::column(&s.column)}),
        NodeRef::Clause(c) => {
            json!({"kind":format!("{:?}",c.keyword),"defines":super::render::program_relation(&c.derives),
            "columns":columns(order,&c.columns,false)?,"set":c.set,"gloss":c.gloss.as_ref().map(|t|t.0.as_ref()),
            "proposers":c.proposers.iter().map(|n|n.0.as_ref()).collect::<Vec<_>>(),
            "ones":c.ones.iter().map(|one|one.key.iter().map(|l|label(order,*l)).collect::<Result<Vec<_>,String>>()).collect::<Result<Vec<_>,_>>()?})
        }
        NodeRef::Instance(i) => {
            json!({"kind":"INIT","component":i.component.0,"name":format!("{:?}",i.name)})
        }
        NodeRef::KeyClause(k) => {
            json!({"kind":"key","columns":columns(order,&k.key.columns,true)?})
        }
        NodeRef::InstanceInput(i) => json!({"kind":"port","name":i.name.0}),
        NodeRef::Choose(c) => json!({"kind":"CHOOSE","name":format!("{:?}",c.name),
            "candidate_columns":columns(order,&c.candidate_columns,false)?,
            "row_columns":c.rows.as_ref().map(|r|columns(order,&r.columns,true)).transpose()?,
            "from_inside_for":c.from_inside_for}),
        NodeRef::RigidDet(c) => json!({"kind":"RIGID_DET","name":format!("{:?}",c.name),
            "key_columns":c.key.as_ref().map(|r|columns(order,&r.columns,true)).transpose()?,
            "instance_columns":c.instance.as_ref().map(|r|columns(order,&r.columns,true)).transpose()?}),
        NodeRef::Out(o) => json!({"kind":"OUT","columns":columns(order,&o.key.columns,true)?}),
        _ => return Err("canonical rendering node is unsupported".into()),
    };
    let children = (0..node.children().len())
        .map(|i| tree(root, &canonical.child(i as u32), order))
        .collect::<Result<Vec<_>, _>>()?;
    Ok(json!({"node":data,"children":children}))
}

pub fn canonical_clause(form: &Form, path: &NodePath) -> Value {
    let mut budget = SearchBudget::new();
    let (order, canonical) = CanonicalOrder::for_features(form, &mut budget);
    let labels=order.label_scopes().iter().flat_map(|(scope,labels)|labels.iter().map(move |(source,canonical)|json!({"scope_path":path_json(&path.join(scope)),"source_label_id":source.0,"canonical_label":canonical}))).collect::<Vec<_>>();
    match tree(NodeRef::from(form), &NodePath::default(), &order) {
        Ok(rendering) => {
            json!({"clause_id":format!("clause:{}",path.0[0].0),"path":path_json(path),"status":if budget.reached{"partial"}else{"complete"},"hash":format!("{:032x}",canonical.hash.0),"rendering":rendering,"labels":labels,"search_cap_reached":budget.reached})
        }
        Err(reason) => {
            json!({"path":path_json(path),"status":"unsupported","reason":reason,"hash":format!("{:032x}",canonical.hash.0),"labels":labels,"search_cap_reached":budget.reached})
        }
    }
}

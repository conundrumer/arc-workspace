//! Local binding provenance for the shared static atom classifier. A prior
//! source site's physical type is used; a later use of that label, including
//! the atom being classified, cannot narrow the premise.
use super::{CheckedProgram, render_sites};
use crate::program::path::{NodePath, NodeRef};
use crate::program::static_prune;
use crate::program::{Atom, Conjunct, LabelId, LabelUse, Negated, RelationRef, Site, SiteArg};
use crate::registry::Registry;
use crate::types::ValueType;
use serde_json::{Value, json};
use crate::hash::StableHashMap;

/// A prefix check's non-refusal includes Undecided. It is insufficient to
/// certify a replacement. For a flat top-level clause, close the AST as it
/// stands, preserve its declared columns, run the whole native checks on both
/// versions, and require identical scoped label/relation types and checker
/// grid evidence. Incomplete/nested forms retain the original atom.
pub(crate) fn replacement_admitted(
    earlier: &std::sync::Arc<crate::resolver::ResolvedProgram>,
    program: &crate::program::Node<crate::program::Program>,
    body_path: &NodePath,
    replacement: crate::program::Constraint,
    registry: &Registry,
) -> bool {
    use super::frames::FormGrids;
    use super::inference::{CaseInferences, Inference, ScopeBody};
    use super::types::PoseOr;
    use crate::program::{Form, Node, Program};
    let Some(Form::Clause(clause)) = program.value().forms.last() else {
        return false;
    };
    if *body_path != NodePath::default().child(0)
        || clause.value().body.value().conjuncts.iter().any(|c| {
            !matches!(
                c,
                Conjunct::Atom(_) | Conjunct::Constraint(_) | Conjunct::Not(Negated::Atom(_))
            )
        })
    {
        return false;
    }
    let Some(last) = clause.value().body.value().conjuncts.len().checked_sub(1) else {
        return false;
    };
    let form_path = NodePath::top((program.value().forms.len() - 1) as u32);
    let at = form_path.join(body_path).child(last as u32);
    // Mutation's editor preserves the original declaration identity and
    // columns; the general editor intentionally recomputes those interfaces.
    let Ok(equivalent) = crate::mutation::edit::apply(
        program,
        &[crate::mutation::edit::AtomEdit {
            at,
            replacement: Some(Conjunct::Constraint(replacement)),
            kind: "comparison",
            choice_kind: "static_prune",
        }],
    ) else {
        return false;
    };
    let check = |program: &Node<Program>| {
        let resolved =
            std::sync::Arc::new(crate::resolver::resolve_last(earlier, program, registry));
        let clauses = super::SolverClauses::of_shared_program(std::sync::Arc::clone(&resolved));
        super::check_shared_program(
            resolved,
            &clauses,
            registry,
            &mut super::CheckCache::default(),
        )
    };
    let (Ok(left), Ok(right)) = (check(program), check(&equivalent)) else {
        return false;
    };
    let (Some(left_types), Some(right_types)) =
        (left.types.form(&form_path), right.types.form(&form_path))
    else {
        return false;
    };
    if left_types.labels().count() != right_types.labels().count()
        || left_types
            .labels()
            .any(|(label, ty)| right_types.label(label) != Some(ty))
        || left_types.relations().count() != right_types.relations().count()
        || left_types.relations().any(|(relation, types)| {
            !right_types
                .relations()
                .any(|(r, t)| r == relation && t == types)
        })
    {
        return false;
    }
    let left_clauses =
        super::SolverClauses::of_shared_program(std::sync::Arc::clone(&left.program));
    let right_clauses =
        super::SolverClauses::of_shared_program(std::sync::Arc::clone(&right.program));
    let left_cases = CaseInferences::new(&left_clauses, registry);
    let right_cases = CaseInferences::new(&right_clauses, registry);
    let left_inference = Inference::new(&left.program, &left_cases);
    let right_inference = Inference::new(&right.program, &right_cases);
    let (Some(left_form), Some(right_form)) = (
        left_inference.infer(&form_path),
        right_inference.infer(&form_path),
    ) else {
        return false;
    };
    let left_scope = ScopeBody::of(program.value().forms.last().unwrap(), registry);
    let right_scope = ScopeBody::of(equivalent.value().forms.last().unwrap(), registry);
    let left_grids = FormGrids::new(
        &left_inference,
        left_form.reading(PoseOr::Given),
        &left_scope,
    );
    let right_grids = FormGrids::new(
        &right_inference,
        right_form.reading(PoseOr::Given),
        &right_scope,
    );
    left_types.labels().all(|(label, _)| {
        let a = left_grids.grids(label);
        let b = right_grids.grids(label);
        a.iter().all(|grid| b.contains(grid)) && b.iter().all(|grid| a.contains(grid))
    })
}

/// Binding premises may not be taken from the current form's settled type
/// inference: a later use could have narrowed a type parameter or type rule.
/// Registry-fixed scalar types and already finished declared relations are
/// independent of that candidate. Other binding sites are left unknown.
fn binding_columns(
    checked: &CheckedProgram,
    registry: &Registry,
    native: &std::collections::BTreeMap<NodePath, render_sites::SiteColumnType>,
) -> std::collections::BTreeMap<NodePath, render_sites::SiteColumnType> {
    fn walk(
        node: NodeRef<'_>,
        at: &NodePath,
        checked: &CheckedProgram,
        registry: &Registry,
        native: &std::collections::BTreeMap<NodePath, render_sites::SiteColumnType>,
        out: &mut std::collections::BTreeMap<NodePath, render_sites::SiteColumnType>,
    ) {
        if let Some(atom) = node.atom() {
            match &atom.relation {
                RelationRef::Lib(_) | RelationRef::Fact(_) => {
                    if let Some(columns) =
                        crate::resolver::registry_columns::typed_columns(registry, &atom.relation)
                    {
                        for (i, site) in atom.sites.iter().enumerate() {
                            let Some(ty) = columns
                                .iter()
                                .find(|c| c.name == site.column)
                                .and_then(|c| c.ty.fixed())
                            else {
                                continue;
                            };
                            if !ty.is_scalar()
                                || site.value.args.len() != 1
                                || site.value.args[0].label().is_none()
                            {
                                continue;
                            }
                            let path = at.child(i as u32).child(0);
                            if let Some(column) = native.get(&path) {
                                out.insert(
                                    path,
                                    render_sites::SiteColumnType {
                                        scope_path: column.scope_path.clone(),
                                        ty: Some(ty.clone()),
                                    },
                                );
                            }
                        }
                    }
                }
                RelationRef::Declared(_) | RelationRef::Output(_) => {
                    let earlier =
                        checked
                            .program
                            .program_read(&atom.relation)
                            .is_some_and(|node| {
                                let forms = checked.program.forms_of(node);
                                !forms.is_empty()
                                    && forms.iter().all(|form| {
                                        form.0
                                            .first()
                                            .zip(at.0.first())
                                            .is_some_and(|(owner, here)| owner < here)
                                    })
                            });
                    if earlier {
                        // The paths below `at` are the run of the sorted map that starts at `at`.
                        for (path, column) in native
                            .range(at.clone()..)
                            .take_while(|(path, _)| path.0.starts_with(&at.0))
                        {
                            out.insert(
                                path.clone(),
                                render_sites::SiteColumnType {
                                    scope_path: column.scope_path.clone(),
                                    ty: column.ty.clone(),
                                },
                            );
                        }
                    }
                }
                RelationRef::DefinedPort(_) => {}
            }
            return;
        }
        for (i, child) in node.children().into_iter().enumerate() {
            walk(child, &at.child(i as u32), checked, registry, native, out);
        }
    }
    let mut out = std::collections::BTreeMap::new();
    walk(
        NodeRef::Program(checked.program.program.value()),
        &NodePath::default(),
        checked,
        registry,
        native,
        &mut out,
    );
    out
}

fn fresh_at(
    site: &Site,
    at: &NodePath,
    columns: &std::collections::BTreeMap<NodePath, render_sites::SiteColumnType>,
    bindings: &mut StableHashMap<LabelId, ValueType>,
) {
    for (i, arg) in site.value.args.iter().enumerate() {
        let path = at.child(i as u32);
        match arg {
            SiteArg::Field(inner) => fresh_at(inner, &path, columns, bindings),
            SiteArg::Label(LabelUse::Fresh(id))
            | SiteArg::NamedLabel {
                label: LabelUse::Fresh(id),
                ..
            } => {
                if let Some(ty) = columns.get(&path).and_then(|column| column.ty.clone()) {
                    bindings.entry(*id).or_insert(ty);
                }
            }
            _ => {}
        }
    }
}
fn fresh_atom(
    atom: &Atom,
    at: &NodePath,
    columns: &std::collections::BTreeMap<NodePath, render_sites::SiteColumnType>,
    bindings: &mut StableHashMap<LabelId, ValueType>,
) {
    for (i, site) in atom.sites.iter().enumerate() {
        fresh_at(site, &at.child(i as u32), columns, bindings);
    }
}
#[derive(Clone, Default)]
struct Context {
    types: StableHashMap<LabelId, ValueType>,
    // Only earlier positive reads of this conjunction and its ancestors.
    // The bool is the native lifted train-example selection at that read.
    reads: Vec<(Atom, bool, NodePath)>,
}
fn walk_body(
    body: NodeRef<'_>,
    checked: &CheckedProgram,
    at: &NodePath,
    columns: &std::collections::BTreeMap<NodePath, render_sites::SiteColumnType>,
    bindings: &mut Context,
    out: &mut Vec<Match>,
) {
    let NodeRef::Body(body) = body else {
        return;
    };
    for (i, conjunct) in body.conjuncts.iter().enumerate() {
        let path = at.child(i as u32);
        let lookup = |id| bindings.types.get(&id).cloned();
        let train_only = checked.program.reads_train_examples(&path);
        if let Some(found) = static_prune::classify(conjunct, &lookup).or_else(|| {
            let Conjunct::Atom(atom) = conjunct else { return None; };
            bindings.reads.iter().find_map(|(earlier, prior_train_only, body)| {
                // ex_output also certifies train-only lifts in its own
                // conjunction. Do not erase a nested body's only certificate
                // merely because an ancestor already tests the same Example.
                let same_guard = !matches!(atom.value().relation, RelationRef::Fact(crate::program::FactRelation::ExOutput)) || body == at;
                (same_guard && *prior_train_only == train_only).then(|| static_prune::repeated_atom(earlier, atom.value())).flatten()
            })
        }) {
            out.push(Match { path: path.clone(), verdict: found });
        }
        match conjunct {
            Conjunct::Atom(atom) => {
                fresh_atom(atom.value(), &path, columns, &mut bindings.types);
                bindings.reads.push((atom.value().clone(), train_only, at.clone()));
            }
            Conjunct::Or(_)
            | Conjunct::If { .. }
            | Conjunct::All { .. }
            | Conjunct::Not(Negated::Form(_)) => {
                // Branch-local bindings cannot escape as one value without the
                // checker's join. Explore with a copy; preserve the outer map.
                for (j, child) in NodeRef::Conjunct(conjunct)
                    .children()
                    .into_iter()
                    .enumerate()
                {
                    let mut local = bindings.clone();
                    walk_any(child, checked, &path.child(j as u32), columns, &mut local, out);
                }
            }
            _ => {}
        }
    }
}
fn walk_any(
    node: NodeRef<'_>,
    checked: &CheckedProgram,
    at: &NodePath,
    columns: &std::collections::BTreeMap<NodePath, render_sites::SiteColumnType>,
    bindings: &mut Context,
    out: &mut Vec<Match>,
) {
    match node {
        NodeRef::Body(_) => walk_body(node, checked, at, columns, bindings, out),
        NodeRef::Instance(instance) => {
            let mut key = Context::default();
            if let Some(key_clause) = &instance.key {
                let path = at.child(0);
                let mut all = Context::default();
                walk_body(
                    NodeRef::Body(key_clause.value().key.body.value()),
                    checked,
                    &path.child(0),
                    columns,
                    &mut all,
                    out,
                );
                for column in key_clause.value().key.columns.iter() {
                    if let Some(ty) = all.types.get(&column.label) {
                        key.types.insert(column.label, ty.clone());
                    }
                }
                for (child, input) in key_clause.value().inputs.iter().enumerate() {
                    let mut local = key.clone();
                    walk_any(
                        NodeRef::InstanceInput(input.value()),
                        checked,
                        &path.child((child + 1) as u32),
                        columns,
                        &mut local,
                        out,
                    );
                }
            }
            for (j, child) in node.children().into_iter().enumerate() {
                if instance.key.is_some() && j == 0 {
                    continue;
                }
                let mut local = key.clone();
                walk_any(child, checked, &at.child(j as u32), columns, &mut local, out);
            }
        }
        NodeRef::KeyClause(clause) => {
            // Keyed inputs see only the already bound key columns.
            let mut key = Context::default();
            walk_body(
                NodeRef::Body(clause.key.body.value()),
                checked,
                &at.child(0),
                columns,
                &mut key,
                out,
            );
            key.types.retain(|label, _| {
                clause
                    .key
                    .columns
                    .iter()
                    .any(|column| column.label == *label)
            });
            key.reads.clear();
            for (j, child) in node.children().into_iter().enumerate().skip(1) {
                let mut local = key.clone();
                walk_any(child, checked, &at.child(j as u32), columns, &mut local, out);
            }
        }
        NodeRef::InstanceInput(input) => {
            let body = at.child(input.head.len() as u32);
            walk_body(
                NodeRef::Body(input.body.value()),
                checked,
                &body,
                columns,
                bindings,
                out,
            );
        }
        _ => {
            for (j, child) in node.children().into_iter().enumerate() {
                // Each child body is its own scope unless its owner explicitly
                // carries a key above. Claim/ALT forms are independent as well.
                let mut local = bindings.clone();
                walk_any(child, checked, &at.child(j as u32), columns, &mut local, out);
            }
        }
    }
}
/// Source-order matches for a checked program. The native site export is
/// reused for physical binding column types; no JSON type text is reparsed.
pub(crate) struct Match {
    pub path: NodePath,
    pub verdict: static_prune::Verdict,
}

pub(crate) fn matches(checked: &CheckedProgram, registry: &Registry) -> Result<Vec<Match>, String> {
    let native = render_sites::site_columns(checked, registry)?;
    let columns = binding_columns(checked, registry, &native);
    let mut matches = Vec::new();
    for (i, form) in checked.program.program.value().forms.iter().enumerate() {
        let mut bindings = Context::default();
        walk_any(
            NodeRef::from(form),
            checked,
            &NodePath::top(i as u32),
            &columns,
            &mut bindings,
            &mut matches,
        );
    }
    Ok(matches)
}

pub fn export(checked: &CheckedProgram, registry: &Registry) -> Result<Value, String> {
    Ok(report(&matches(checked, registry)?))
}

pub(crate) fn report(matches: &[Match]) -> Value {
    let matches: Vec<_> = matches.iter().map(|m| json!({
        "path":crate::mutation::path_json(&m.path), "class":m.verdict.class.name(), "rule":m.verdict.rule,
        "replacement":m.verdict.replacement.clone().map(|c|crate::mutation::conjunct_json(&Conjunct::Constraint(c)))
    })).collect();
    json!({"schema":"arclog-static-prune-v1","matches":matches,
        "binding_contract":"first registry-fixed scalar binding column or earlier declared relation column; current-form parameters and conditional narrowing supply no premise; branch-local bindings stay local; atom.repeated uses only prior positive exact reads with equal lifted example selection, preserves binders and conjunction-local ex_output certificates"})
}


/// Match only surviving edited sites, mapped by the canonical atomic editor.
/// Untouched gold tests and deleted atoms are not candidate atoms. A compound
/// replacement also owns the primitive tests in its replaced subtree.
pub(crate) fn edited_matches(checked: &CheckedProgram, registry: &Registry,
    edits: &[crate::mutation::edit::AtomEdit]) -> Result<Vec<Match>, String> {
    let sites: Vec<_> = edits.iter().filter(|e|e.replacement.is_some())
        .filter_map(|e|crate::mutation::edit::mapped(&e.at,edits)).collect();
    matches_at(checked,registry,&sites)
}

/// Shared selected-site classifier for sampling and stored-form reads.
pub(crate) fn matches_at(checked: &CheckedProgram, registry: &Registry, sites: &[NodePath]) -> Result<Vec<Match>, String> {
    if sites.is_empty() {return Ok(Vec::new())}
    Ok(matches(checked,registry)?.into_iter().filter(|m| sites.iter().any(|site|
        m.path.0.starts_with(&site.0) || site.0.starts_with(&m.path.0))).collect())
}

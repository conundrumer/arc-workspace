//! Atomic edits at original AST paths, preserving every clause interface.
//!
//! The general program editor intentionally recomputes heads. The study must
//! instead keep them: deleting their only binder makes an edit unavailable.
use std::collections::BTreeMap;
use std::sync::Arc;

use crate::layout::Layout;
use crate::program::path::NodePath;
use crate::program::*;

#[derive(Clone, Debug)]
pub struct AtomEdit {
    pub at: NodePath,
    pub replacement: Option<Conjunct>,
    pub kind: &'static str,
    pub choice_kind: &'static str,
}

/// Translate an original path after simultaneous deletions. No AST field is
/// renumbered: this maps tree addresses and presentation layout only.
pub fn mapped(at: &NodePath, edits: &[AtomEdit]) -> Option<NodePath> {
    let mut result = at.clone();
    for edit in edits.iter().filter(|e| e.replacement.is_none()) {
        if at.0.starts_with(&edit.at.0) {
            return None;
        }
        let (last, parent) = edit.at.0.split_last()?;
        if at.0.len() > parent.len() && at.0.starts_with(parent) && at.0[parent.len()].0 > last.0 {
            result.0[parent.len()].0 -= 1;
        }
    }
    Some(result)
}


/// Source-order node identities under the actual atomic editor. Container
/// subtrees may change even when their node identity/address is preserved.
pub fn source_paths(program: &Node<Program>, edits: &[AtomEdit]) -> serde_json::Value {
    use crate::program::path::NodeRef;
    use serde_json::{Value, json};
    fn walk(node: NodeRef<'_>, at: &NodePath, edits: &[AtomEdit], out: &mut Vec<Value>) {
        let replaced = edits.iter().any(|e| e.replacement.is_some() && at.0.len()>e.at.0.len() && at.0.starts_with(&e.at.0));
        let after = if replaced {None} else {mapped(at,edits)};
        out.push(json!({"before_path":super::path_json(at),"after_path":after.as_ref().map(super::path_json),
            "status":if replaced {"replaced_subtree"} else if after.is_none() {"deleted"}
                else if edits.iter().any(|e|e.at==*at) {"replaced"} else {"preserved"}}));
        for (i,child) in node.children().into_iter().enumerate() {walk(child,&at.child(i as u32),edits,out);}
    }
    let mut out=Vec::new();
    walk(NodeRef::Program(program.value()),&NodePath::default(),edits,&mut out);
    json!(out)
}

pub fn layout(old: Option<&Layout>, edits: &[AtomEdit]) -> Option<Layout> {
    // Whole-block replacements may allocate private native IDs and reorder
    // subtree paths. Rebuild display layout with gold's namespace instead of
    // applying stale per-path elisions/names to those new sites.
    if edits.iter().any(|e|e.kind=="block" || e.replacement.as_ref().is_some_and(super::blocks::is_block)) {return None}
    let mut result = old?.clone();
    result.nodes = result
        .nodes
        .into_iter()
        .filter_map(|((file, path), mut node)| {
            if edits
                .iter()
                .any(|e| e.replacement.is_some() && path.0.starts_with(&e.at.0))
            {
                // An elided label used to imply its original column name.
                // An argument replacement must now spell that column explicitly.
                node.elided_sites = Box::new([]);
            }
            Some(((file, mapped(&path, edits)?), node))
        })
        .collect();
    Some(result)
}

pub fn apply(program: &Node<Program>, edits: &[AtomEdit]) -> Result<Node<Program>, String> {
    let mut patches = BTreeMap::new();
    for edit in edits {
        if patches
            .insert(edit.at.clone(), edit.replacement.clone())
            .is_some()
        {
            return Err("duplicate_atom_path".into());
        }
    }
    let paths=patches.keys().collect::<Vec<_>>();
    if paths.iter().enumerate().any(|(i,a)|paths.iter().skip(i+1).any(|b|a.0.starts_with(&b.0)||b.0.starts_with(&a.0))) {
        return Err("overlapping_edit_paths".into());
    }
    let mut used = 0;
    let forms = program
        .value()
        .forms
        .iter()
        .enumerate()
        .map(|(index, form)| rewrite_form(form, &NodePath::top(index as u32), &patches, &mut used))
        .collect::<Vec<_>>();
    if used != edits.len() {
        return Err("edit_path_is_not_a_body_atom".into());
    }
    Ok(Node::new(Program {
        forms: forms.into(),
    }))
}

type Patches = BTreeMap<NodePath, Option<Conjunct>>;

fn relevant(at: &NodePath, patches: &Patches) -> bool {
    patches.keys().any(|path| path.0.starts_with(&at.0))
}

fn body(old: &Node<Body>, at: &NodePath, patches: &Patches, used: &mut usize) -> Node<Body> {
    if !relevant(at, patches) {
        return old.clone();
    }
    let mut conjuncts = Vec::new();
    for (index, conjunct) in old.value().conjuncts.iter().enumerate() {
        let path = at.child(index as u32);
        if let Some(replacement) = patches.get(&path) {
            // Admission authenticates the original conjunct and replacement.
            if conjunct.atom().is_some() || matches!(conjunct, Conjunct::Constraint(_)) || super::blocks::is_block(conjunct) {
                *used += 1;
                conjuncts.extend(replacement.clone());
                continue;
            }
        }
        conjuncts.push(wrapped(conjunct, &path, patches, used));
    }
    Node::new(Body {
        conjuncts: conjuncts.into(),
    })
}

fn wrapped(old: &Conjunct, at: &NodePath, patches: &Patches, used: &mut usize) -> Conjunct {
    if let Some(Some(replacement)) = patches.get(at) {
        if old.atom().is_some() || matches!(old, Conjunct::Constraint(_)) || super::blocks::is_block(old) {
            *used += 1;
            return replacement.clone();
        }
    }
    match old {
        Conjunct::Not(Negated::Form(inner)) => Conjunct::Not(Negated::Form(Arc::new(wrapped(
            inner,
            &at.child(0),
            patches,
            used,
        )))),
        Conjunct::Or(branches) => Conjunct::Or(
            branches
                .iter()
                .enumerate()
                .map(|(i, b)| body(b, &at.child(i as u32), patches, used))
                .collect(),
        ),
        Conjunct::If {
            test,
            then,
            otherwise,
        } => Conjunct::If {
            test: body(test, &at.child(0), patches, used),
            then: body(then, &at.child(1), patches, used),
            otherwise: body(otherwise, &at.child(2), patches, used),
        },
        Conjunct::All {
            domain,
            body: inner,
        } => Conjunct::All {
            domain: body(domain, &at.child(0), patches, used),
            body: body(inner, &at.child(1), patches, used),
        },
        _ => old.clone(),
    }
}

fn input(
    old: &Node<InstanceInput>,
    at: &NodePath,
    patches: &Patches,
    used: &mut usize,
) -> Node<InstanceInput> {
    let value = old.value();
    Node::new(InstanceInput {
        body: body(
            &value.body,
            &at.child(value.position(InstanceInputPart::Body)),
            patches,
            used,
        ),
        ..value.clone()
    })
}

fn key(
    old: &Node<KeyClause>,
    at: &NodePath,
    patches: &Patches,
    used: &mut usize,
) -> Node<KeyClause> {
    let value = old.value();
    let key = KeyBody {
        body: body(&value.key.body, &at.child(0), patches, used),
        ..value.key.clone()
    };
    let inputs = value
        .inputs
        .iter()
        .enumerate()
        .map(|(i, inp)| {
            input(
                inp,
                &at.child(value.position(KeyClausePart::Input(i))),
                patches,
                used,
            )
        })
        .collect();
    Node::new(KeyClause { key, inputs })
}

fn rewrite_form(old: &Form, at: &NodePath, patches: &Patches, used: &mut usize) -> Form {
    if !relevant(at, patches) {
        return old.clone();
    }
    match old {
        Form::Clause(clause) => Form::Clause(Node::new(Clause {
            body: body(&clause.value().body, &at.child(0), patches, used),
            ..clause.value().clone()
        })),
        Form::Instance(instance) => {
            let value = instance.value();
            let inputs = value
                .inputs
                .iter()
                .enumerate()
                .map(|(i, inp)| {
                    input(
                        inp,
                        &at.child(value.position(InstancePart::Input(i))),
                        patches,
                        used,
                    )
                })
                .collect();
            Form::Instance(Node::new(Instance {
                key: value.key.as_ref().map(|k| {
                    key(
                        k,
                        &at.child(value.position(InstancePart::Key)),
                        patches,
                        used,
                    )
                }),
                inputs,
                ..value.clone()
            }))
        }
        Form::Choose(choose) => {
            let value = choose.value();
            let rows = value.rows.as_ref().map(|k| KeyBody {
                body: body(
                    &k.body,
                    &at.child(value.position(ChoosePart::For)),
                    patches,
                    used,
                ),
                ..k.clone()
            });
            let from = body(
                &value.from,
                &at.child(value.position(ChoosePart::From)),
                patches,
                used,
            );
            let never = value
                .never
                .iter()
                .enumerate()
                .map(|(i, b)| {
                    body(
                        b,
                        &at.child(value.position(ChoosePart::Never(i))),
                        patches,
                        used,
                    )
                })
                .collect();
            Form::Choose(Node::new(Choose {
                rows,
                from,
                never,
                ..value.clone()
            }))
        }
        Form::RigidDet(rigid) => {
            let value = rigid.value();
            let key = value.key.as_ref().map(|k| KeyBody {
                body: body(
                    &k.body,
                    &at.child(value.position(RigidDetPart::Key)),
                    patches,
                    used,
                ),
                ..k.clone()
            });
            let instance = value.instance.as_ref().map(|k| KeyBody {
                body: body(
                    &k.body,
                    &at.child(value.position(RigidDetPart::Instance)),
                    patches,
                    used,
                ),
                ..k.clone()
            });
            Form::RigidDet(Node::new(RigidDet {
                key,
                instance,
                ..value.clone()
            }))
        }
        _ => old.clone(),
    }
}

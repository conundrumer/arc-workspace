//! What the readers of a program that holds a `DEMONSTRATED` form share: the
//! inputs the form names, with the columns of each, the columns that a
//! `&prediction` clause fills, and the form as the content of a query holds
//! it. The grammar of the stream has no `DEMONSTRATED` form, so neither the
//! writer nor the decoder reads this.

use std::sync::OnceLock;

use crate::program::canonical::{prediction, relation_of};
use crate::program::path::NodePath;
use crate::program::{Clause, ColumnName, DemoRule, DemoRuleName, Demonstrated, Form, InstanceInput, Node, PortName, RelationColumn};
use crate::registry::{Column, ColumnType, Component, ComponentKind, InputPort, Port, Registry, TypeParameter};
use crate::resolver::columns::projection;
use crate::resolver::form_columns::demonstrated_value;
use crate::types::{each_site_label, use_label};

/// The inputs of a `DEMONSTRATED` form: `value`,
/// with the columns `o`, `i` and `v`, then `demonstration`, with the columns
/// `o` and `o2`, each a type parameter. The form has no output.
pub(crate) fn ports() -> &'static Component {
    static PORTS: OnceLock<Component> = OnceLock::new();
    PORTS.get_or_init(|| {
        let column = |name: &str| Column { name: ColumnName::Written(name.into()), ty: ColumnType::Parameter(TypeParameter { name: name.to_uppercase().into(), bound: None }) };
        let input = |name: &str, columns: &[&str]| InputPort {
            port: Port { name: PortName(name.into()), columns: columns.iter().map(|name| column(name)).collect(), copies: Box::new([]), frames: Box::new([]) },
            default: None,
            reads_outputs: false,
            from_key: false,
            need: None,
        };
        Component {
            kind: ComponentKind::TaskStructure,
            type_parameters: Box::new([]),
            inputs: Box::new([input("value", &["o", "i", "v"]), input("demonstration", &["o", "o2"])]),
            outputs: Box::new([]),
        }
    })
}

/// The names of the columns that a `&prediction` clause of a rule of
/// `demonstrated` fills, in this order: each column of
/// the key, then each column of the head of the `value` input, as the
/// evaluation names them (`crate::eval`'s `DEMONSTRATED` form): a site of
/// one label by the label's name, and a site of a record by each field.
/// `None` for a column that no name names.
pub(crate) fn prediction_targets(demonstrated: &Demonstrated) -> Vec<Option<ColumnName>> {
    let key = demonstrated.key.iter().flat_map(|key| key.value().key.columns.iter().map(|column| Some(column.name.clone())));
    let value = demonstrated_value(demonstrated).map(head_names).unwrap_or_default();
    key.chain(value).collect()
}

/// The name of each column of the head of `input`, in the order of its
/// sites, as the evaluation of a `DEMONSTRATED` form names them.
fn head_names(input: &InstanceInput) -> Vec<Option<ColumnName>> {
    let mut names = Vec::new();
    for site in input.head.iter() {
        match projection(site) {
            Some(fields) => names.extend(fields.iter().cloned().map(Some)),
            None => each_site_label(site, &mut Vec::new(), &mut |use_, path| {
                if use_label(use_).is_some() {
                    names.push((path.len() > 1).then(|| path.last().cloned()).flatten());
                }
            }),
        }
    }
    names
}

/// The name that the content of a query gives the `DEMO_RULE` form at `index`
/// among the rules of its form: `$R<index>`.
pub(crate) fn rule_name(index: usize) -> DemoRuleName {
    DemoRuleName(format!("$R{index}").into())
}

/// The name that the content of a query gives the field at `at` of a
/// `DEMO_RULE` form, which no column of the key or of the `value` head has.
pub(crate) fn field_name(at: usize) -> ColumnName {
    ColumnName::Slot(u32::MAX - at as u32)
}

/// `demonstrated` as the content of a query holds it: each rule named by
/// [`rule_name`] with no text, its fields named by [`field_name`], its forms
/// in the order [`super::write::write_order`] gives, no clause of it with a
/// gloss, and each `&prediction` clause with the columns that it fills, each
/// named by the column it fills, in the order of [`prediction_targets`].
pub(crate) fn as_streamed(demonstrated: &Demonstrated, registry: &Registry) -> Demonstrated {
    let targets = prediction_targets(demonstrated);
    let rules = demonstrated.rules.iter().enumerate().map(|(index, rule)| Node::new(streamed_rule(index, rule.value(), &targets, registry))).collect();
    Demonstrated { rules, ..demonstrated.clone() }
}

/// The rule `rule`, at `index`, as [`as_streamed`] gives it.
fn streamed_rule(index: usize, rule: &DemoRule, targets: &[Option<ColumnName>], registry: &Registry) -> DemoRule {
    let leaves: Vec<(&Form, NodePath)> = rule.forms.iter().enumerate().map(|(at, form)| (form, NodePath::top(at as u32))).collect();
    let forms = super::write::write_order(registry, &leaves)
        .into_iter()
        .map(|at| {
            let form = match &rule.forms[at] {
                Form::Clause(clause) if relation_of(&clause.value().derives) == prediction() => {
                    let clause = clause.value();
                    Form::Clause(Node::new(Clause { gloss: None, columns: filled_columns(clause, rule, targets).into(), ..clause.clone() }))
                }
                Form::Clause(clause) if clause.value().gloss.is_some() => Form::Clause(Node::new(Clause { gloss: None, ..clause.value().clone() })),
                form => form.clone(),
            };
            (form, rule.forms.from_alt(at))
        })
        .collect();
    let fields = rule.fields.iter().enumerate().map(|(at, field)| RelationColumn { name: field_name(at), label: field.label }).collect();
    DemoRule { name: rule_name(index), fields, text: None, forms }
}

/// The columns of `targets` that the `&prediction` clause `clause` of
/// `rule` fills: each with the label of the
/// clause's column of its name, or of the rule's field of its name.
pub(crate) fn filled_columns(clause: &Clause, rule: &DemoRule, targets: &[Option<ColumnName>]) -> Vec<RelationColumn> {
    let filled = |name: &ColumnName| clause.columns.iter().chain(rule.fields.iter()).find(|column| column.name == *name);
    targets.iter().flatten().filter_map(|name| filled(name).map(|column| RelationColumn { name: name.clone(), label: column.label })).collect()
}

//! Finding, within a program, a form, a `DEMO_RULE` form or the forms of a
//! name scope by path, and the forms of a label scope.

use crate::program::canonical::shares_rule_scope;
use crate::program::path::NodePath;
use crate::program::{DemoRule, Form, NameScope, Program};

/// The form at `path` of `program`: a top-level form or a form of a
/// `DEMO_RULE`.
pub(in crate::check) fn form_at<'p>(program: &'p Program, path: &NodePath) -> Option<&'p Form> {
    let (first, rest) = path.0.split_first()?;
    form_within(program.forms.get(first.0 as usize)?, &NodePath(rest.into()))
}

/// The form at `path`, a path relative to `form`: `form` itself at the
/// empty path, or a form of a `DEMO_RULE` within it.
pub(in crate::check) fn form_within<'p>(form: &'p Form, path: &NodePath) -> Option<&'p Form> {
    let mut form = form;
    let mut steps = path.0.iter();
    while let Some(step) = steps.next() {
        form = match form {
            Form::Demonstrated(demonstrated) => {
                let rule = demonstrated.value().rule_at(step.0)?;
                rule.forms.get(steps.next()?.0 as usize)?
            }
            _ => return None,
        };
    }
    Some(form)
}

/// Each form of `rule` that stands in the rule's label scope, with its
/// index among the rule's forms.
pub(in crate::check) fn rule_scope_forms(rule: &DemoRule) -> impl Iterator<Item = (u32, &Form)> {
    (0u32..).zip(rule.forms.iter()).filter(|(index, _)| shares_rule_scope(rule, *index as usize))
}

/// The `DEMO_RULE` form at `path` of `program`.
pub(in crate::check) fn demo_rule<'p>(program: &'p Program, path: &NodePath) -> Option<&'p DemoRule> {
    let (first, rest) = path.0.split_first()?;
    rule_within(program.forms.get(first.0 as usize)?, &NodePath(rest.into()))
}

/// The `DEMO_RULE` form at `path`, a path relative to `form`.
pub(in crate::check) fn rule_within<'p>(form: &'p Form, path: &NodePath) -> Option<&'p DemoRule> {
    let (rule, prefix) = path.0.split_last()?;
    let Form::Demonstrated(demonstrated) = form_within(form, &NodePath(prefix.into()))? else { return None };
    demonstrated.value().rule_at(rule.0)
}

/// Each form that declares names in `scope`, with its path: the top-level
/// forms for the program, and a `DEMO_RULE`'s forms for its scope.
pub(in crate::check) fn scope_forms<'p>(program: &'p Program, scope: &NameScope) -> Vec<(NodePath, &'p Form)> {
    let (forms, at) = match scope {
        NameScope::Program => (&program.forms[..], NodePath::default()),
        NameScope::DemoRule(rule) => match demo_rule(program, rule) {
            Some(found) => (&found.forms[..], rule.clone()),
            None => return Vec::new(),
        },
    };
    forms.iter().zip(0u32..).map(|(form, index)| (at.child(index), form)).collect()
}

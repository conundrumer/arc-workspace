//! The naming conditions of the labels of an edited program, which
//! [`Node::apply`] checks: the variant of each bare label at a site, and the
//! one name that each label of a scope takes over its sites. The checks
//! follow the reader: the join rule of `engine/arclog/src/read/labels.rs`
//! gives each join the label that [`ScopeLabels`] ranks it to.

use crate::hash::StableHashMap;

use super::super::canonical::opens_scope;
use super::super::path::{NodePath, NodeRef};
use super::super::*;
use super::{label_of, EditError};
use crate::read::is_type_parameter_column;

/// Refuses each bare label at a site of `node`, at `at`, of the variant
/// that the naming conditions of [`Node::apply`] do not give it; `on_field`
/// where `node` is a field site.
pub(super) fn check_label_kinds(node: NodeRef<'_>, at: &NodePath, on_field: bool) -> Result<(), EditError> {
    let NodeRef::Site(site) = node else {
        for (child, index) in node.children().into_iter().zip(0u32..) {
            check_label_kinds(child, &at.child(index), false)?;
        }
        return Ok(());
    };
    let named = !on_field && matches!(&site.column, ColumnName::Written(column) if is_type_parameter_column(column));
    for (arg, index) in site.value.args.iter().zip(0u32..) {
        let path = at.child(index);
        match arg {
            SiteArg::Field(field) => check_label_kinds(NodeRef::Site(field), &path, true)?,
            SiteArg::Label(LabelUse::Zero) => {}
            SiteArg::Label(_) if !named => {}
            SiteArg::NamedLabel { label, .. } if named && *label != LabelUse::Zero => {}
            SiteArg::Label(_) | SiteArg::NamedLabel { .. } => return Err(EditError::BareLabel { path }),
        }
    }
    Ok(())
}

/// Refuses, in the label scope at `at`, `root`, and in each scope below
/// it, a [`SiteArg::NamedLabel`] whose label takes another name in its
/// scope, and a join of a label whose name another label of the scope takes
/// where the join rule of `engine/arclog/src/read/labels.rs` joins it to a
/// site that makes that other label.
pub(super) fn check_label_names(root: NodeRef<'_>, at: &NodePath) -> Result<(), EditError> {
    let mut scope = ScopeLabels::default();
    scope.walk(root, at, &mut Vec::new())?;
    scope.check_joins()
}

/// The labels of one scope as the text of the program writes them: the
/// name each label takes, and each use of a label with the lists of the text
/// that hold it.
#[derive(Default)]
struct ScopeLabels {
    names: StableHashMap<LabelId, ColumnName>,
    /// Each use, in source order.
    uses: Vec<Use>,
    lists: u32,
}

struct Use {
    /// The lists of the text that hold the use, outermost first.
    lists: Vec<u32>,
    label: LabelUse,
    path: NodePath,
}

/// A list of the text that holds some children of a node and not the
/// node's own other children, by what it holds.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
enum Wrapper {
    /// An input's head.
    Head,
    /// The `for` clause of a `CHOOSE` form.
    For,
    /// The `key` clause of a `RIGID_DET` form.
    RigidKey,
    /// The `instance` clause of a `RIGID_DET` form.
    RigidInstance,
    /// A list of one child only, by its index.
    Own(u32),
}

impl ScopeLabels {
    fn list(&mut self) -> u32 {
        self.lists += 1;
        self.lists
    }

    /// Reads the uses and the names of `node`, at `at`, which `lists` hold,
    /// and checks each label scope below it apart.
    fn walk(&mut self, node: NodeRef<'_>, at: &NodePath, lists: &mut Vec<u32>) -> Result<(), EditError> {
        let depth = lists.len();
        for _ in 0..own_lists(node) {
            let list = self.list();
            lists.push(list);
        }
        match node {
            NodeRef::Label(use_) => self.uses.push(Use { lists: lists.clone(), label: *use_, path: at.clone() }),
            NodeRef::DemoRule(rule) => {
                let head = self.list();
                let lists: Vec<u32> = lists.iter().copied().chain([head]).collect();
                for field in rule.fields.iter() {
                    self.uses.push(Use { lists: lists.clone(), label: LabelUse::Fresh(field.label), path: at.clone() });
                }
            }
            NodeRef::Conjunct(Conjunct::Constraint(constraint)) => {
                let operands = [Some(constraint.first), constraint_second(constraint)];
                for operand in operands.into_iter().flatten() {
                    self.uses.push(Use { lists: lists.clone(), label: operand.into(), path: at.clone() });
                }
            }
            NodeRef::Site(site) => {
                for (arg, index) in site.value.args.iter().zip(0u32..) {
                    if let SiteArg::NamedLabel { name, label } = arg
                        && let Some(label) = label_of(*label)
                        && self.names.entry(label).or_insert_with(|| name.clone()) != name
                    {
                        return Err(EditError::BareLabel { path: at.child(index) });
                    }
                }
            }
            _ => {}
        }
        let mut wrappers: StableHashMap<Wrapper, u32> = StableHashMap::default();
        for (child, index) in node.children().into_iter().zip(0u32..) {
            let path = at.child(index);
            if opens_scope(node, index as usize, child) {
                check_label_names(child, &path)?;
                continue;
            }
            let outer = lists.len();
            for wrapper in wrappers_of(node, index, child) {
                let list = match wrappers.get(&wrapper) {
                    Some(list) => *list,
                    None => {
                        let list = self.list();
                        wrappers.insert(wrapper, list);
                        list
                    }
                };
                lists.push(list);
            }
            self.walk(child, &path, lists)?;
            lists.truncate(outer);
        }
        lists.truncate(depth);
        Ok(())
    }

    /// Refuses each join that the join rule gives a site that makes another
    /// label of its name.
    fn check_joins(&self) -> Result<(), EditError> {
        let named = |use_: &Use| label_of(use_.label).and_then(|label| self.names.get(&label).map(|name| (label, name)));
        for join in &self.uses {
            let (LabelUse::Join(label), Some((_, name))) = (join.label, named(join)) else { continue };
            let makers = self.uses.iter().enumerate().filter(|(_, maker)| {
                matches!(maker.label, LabelUse::Fresh(_) | LabelUse::Key(_)) && named(maker).is_some_and(|(_, other)| other == name)
            });
            let nearest = makers.min_by_key(|(order, maker)| {
                let common = maker.lists.iter().zip(&join.lists).take_while(|(a, b)| a == b).count();
                (usize::MAX - common, maker.lists.len() - common, *order)
            });
            if let Some((_, maker)) = nearest
                && label_of(maker.label) != Some(label)
            {
                return Err(EditError::BareLabel { path: join.path.clone() });
            }
        }
        Ok(())
    }
}

/// The number of lists of the text that `node` is written as and that
/// hold all of its children: a form's, a conjunct's, a site's, an input's;
/// `(NOT (<atom>))` is two.
fn own_lists(node: NodeRef<'_>) -> usize {
    match node {
        NodeRef::Program(_) | NodeRef::Body(_) | NodeRef::Label(_) => 0,
        NodeRef::Conjunct(Conjunct::Not(Negated::Atom(_))) => 2,
        _ => 1,
    }
}

/// The lists of the text that hold `child`, the child at `index` of
/// `parent`, inside the lists of `parent` itself, outermost first.
fn wrappers_of(parent: NodeRef<'_>, index: u32, child: NodeRef<'_>) -> Vec<Wrapper> {
    let own = Wrapper::Own(index);
    match (parent, child) {
        (NodeRef::Clause(_) | NodeRef::InstanceInput(_) | NodeRef::Out(_), NodeRef::Body(_)) => Vec::new(),
        (NodeRef::InstanceInput(_), _) => vec![Wrapper::Head],
        (NodeRef::Choose(choose), _) => match choose.parts().nth(index as usize) {
            Some(ChoosePart::For) => vec![Wrapper::For, own],
            Some(ChoosePart::From) if choose.from_inside_for => vec![Wrapper::For, own],
            _ => vec![own],
        },
        (NodeRef::RigidDet(rigid), _) => {
            let key = rigid.key.iter().map(|_| Wrapper::RigidKey);
            let instance = rigid.instance.iter().map(|_| Wrapper::RigidInstance);
            match rigid.children().nth(index as usize) {
                Some(RigidDetPart::Key) => vec![Wrapper::RigidKey, own],
                Some(RigidDetPart::Instance) => key.chain([Wrapper::RigidInstance, own]).collect(),
                _ => key.chain(instance).collect(),
            }
        }
        (_, NodeRef::Body(_)) => vec![own],
        _ => Vec::new(),
    }
}

/// The lists that [`own_lists`] and [`wrappers_of`] give each node are the
/// lists the reader reads it from: with the names the reader gives the
/// labels, the ranking of [`ScopeLabels::check_joins`] gives each join the
/// label the reader joined it to.
#[cfg(test)]
mod tests {
    use super::*;
    use crate::layout::SourceFile;
    use crate::program::path::node_at;
    use crate::read::read_arclog;

    /// Programs that hold each list that `own_lists` and `wrappers_of` give,
    /// and a join of a label that a site makes in or below it. A program
    /// that makes a name at two sites holds them in two bodies, as the reader
    /// allows (`docs/arclog/arclog.md#sites`).
    const PROGRAMS: [&str; 12] = [
        // An input's head and its key body.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (DEMONSTRATED &catalog\n\
           (key ((&cells (:P *P) (:Col ^Col)))\n\
             (value (P)\n\
               (&cells (:P *P) (:Col Col)) (&cells (:P P)))))\n",
        // A `CHOOSE` form's `for` clause, with its `from` inside it.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (CHOOSE &pick\n\
           (for ((&cells (:P *P)) (&cells (:P P)))\n\
             (from (&cells (:P P) (:Col *Col)))))\n",
        // A `CHOOSE` form's `for` clause, with its `from` outside it.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (CHOOSE &pick\n\
           (for ((&cells (:P *P)) (&cells (:P P))))\n\
           (from (&cells (:P P) (:Col *Col))))\n",
        // A `CHOOSE` form's `for` clause, with its `from` inside it, and a
        // `never` clause.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (CHOOSE &pick\n\
           (for ((&cells (:P *X)))\n\
             (from (&cells (:P *X) (:Col *Col))))\n\
           (never (&cells (:P X))))\n",
        // A `CHOOSE` form's `for` clause, with its `from` outside it, and a
        // `never` clause.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (CHOOSE &pick\n\
           (for ((&cells (:P *X))))\n\
           (from (&cells (:P *X) (:Col *Col)))\n\
           (never (&cells (:P X))))\n",
        // A `RIGID_DET` form's `key` clause, with no `instance` clause.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (RIGID_DET &piece\n\
           (key ((&cells (:P *X) (:Col ^C)))\n\
             (&cells (:P (:a (:b *X))))\n\
             (&cells (:P X))))\n",
        // A `RIGID_DET` form's `key` and `instance` clauses.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (RIGID_DET &piece\n\
           (key ((&cells (:P *X) (:Col ^C)))\n\
             (instance ((&cells (:P *X)))\n\
               (&cells (:P X)))))\n",
        // `(NOT (<atom>))`.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (RULE &a (NOT (&cells (:P *X))) (&cells (:P X)))\n",
        // An `OR`'s later branch.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (RULE &a (OR ((&cells (:P *X))) ((&cells (:P X)))) (&cells (:P X)))\n",
        // An `IF`'s then.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (RULE &a (IF ((&cells (:P *X))) ((&cells (:P X))) ((&cells (:P *Z)))) (&cells (:P X)))\n",
        // A `DEMO_RULE` form's head.
        "(RULE &stage (input (:P *P) (:Col *Col)))\n\
         (DEMONSTRATED &catalog\n\
           (value (P)\n\
             (&stage (:P *P) (:Col *Col)))\n\
           (DEMO_RULE ($Same *P)\n\
             (RULE &prediction (&stage (:P P)))\n\
             (RULE &other (&stage (:P P)))))\n",
        // An input's body and an `INIT` form's key body.
        "(RULE &cells (input (:P *P) (:Col *Col)))\n\
         (INIT &obj Connectivity\n\
           (key ((&cells (:P *Q) (:Col ^Col)))\n\
             (node (P)\n\
               (&cells (:P *P) (:Col Col)) (&cells (:P *Q) (:Col P)))))\n",
    ];

    /// The path of each label scope below `node`, at `at`.
    fn scopes(node: NodeRef<'_>, at: &NodePath, out: &mut Vec<NodePath>) {
        for (child, index) in node.children().into_iter().zip(0u32..) {
            let path = at.child(index);
            if opens_scope(node, index as usize, child) {
                out.push(path.clone());
            }
            scopes(child, &path, out);
        }
    }

    #[test]
    fn the_ranking_over_the_lists_of_each_node_joins_as_the_reader_joins() {
        for text in PROGRAMS {
            let read = read_arclog(text, SourceFile::Arclog).unwrap_or_else(|errors| panic!("{text}: {errors:?}"));
            assert!(read.diagnostics.is_empty(), "{text}: {:?}", read.diagnostics);
            let (program, layout) = read.value;
            let root = NodeRef::Program(program.value());
            let mut paths = Vec::new();
            scopes(root, &NodePath::default(), &mut paths);
            let mut joins = 0;
            for path in paths {
                let node = node_at(root, &path).expect("each scope's path names its node");
                let mut scope = ScopeLabels::default();
                scope.walk(node, &path, &mut Vec::new()).unwrap_or_else(|error| panic!("{text}: {error:?}"));
                let names = &layout.node(SourceFile::Arclog, &path).expect("the reader gives each scope its layout").label_names;
                scope.names = names.iter().map(|(label, name)| (*label, ColumnName::Written(name.clone()))).collect();
                joins += scope.uses.iter().filter(|use_| matches!(use_.label, LabelUse::Join(_))).count();
                if let Err(EditError::BareLabel { path }) = scope.check_joins() {
                    panic!("{text}: the ranking joins the join at {path:?} to another maker than the reader does");
                }
            }
            assert!(joins > 0, "{text}: no join");
        }
    }
}


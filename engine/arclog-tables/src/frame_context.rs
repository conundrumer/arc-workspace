//! Direct grid context proved from native source arguments, never column names.
use super::*;
use arclog::eval::ir::{AtomSource, ClauseIr, RelationAtom};
use arclog::program::FactRelation;
use std::collections::BTreeMap;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(super) enum RowExample {
    Column(usize),
    Constant(TermId),
}

impl RowExample {
    pub(super) fn from_argument(argument: Argument, paths: &IrPaths,
        column_of: impl FnOnce(LabelId) -> Option<usize>) -> Option<Self> {
        match argument {
            Argument::Term(value) => Some(Self::Constant(value)),
            Argument::Variable(variable) => column_of(*paths.labels.get(usize::from(variable.0))?).map(Self::Column),
        }
    }

    pub(super) fn get(self, row: &[TermId]) -> Option<Example> {
        let value = match self { Self::Column(i) => *row.get(i)?, Self::Constant(value) => value };
        match Term::decode(value, &ValueType::Example) {
            Term::Constant(Constant::Example(example)) => Some(example),
            _ => None,
        }
    }
}

/// Distinguish an ambient per-example read from an explicit/lifted read whose
/// Example argument was projected away. The latter has no direct proof.
pub(super) enum ExampleArgument {
    Ambient,
    Explicit(Option<Argument>),
}

pub(super) fn example_argument(checked: &CheckedProgram, at: &NodePath, atom: &RelationAtom) -> ExampleArgument {
    if matches!(atom.source, AtomSource::Fact(FactRelation::ExInput | FactRelation::ExOutput))
        || checked.program.reads_lifted(at) {
        ExampleArgument::Explicit(atom.arguments.0.iter().find(|(position, _)| position.0 == 0).map(|(_, value)| *value))
    } else {
        ExampleArgument::Ambient
    }
}

#[derive(Clone, Debug)]
pub(super) struct DirectContexts {
    entries: Vec<DirectGrids>,
    examples: Vec<DirectGrids>,
    row_examples: Vec<Option<RowExample>>,
}

impl DirectContexts {
    pub(super) fn new(decoder: &Decoder<'_>, checked: &CheckedProgram, form: &NodePath,
        contents: &Contents, earlier: &[&Table]) -> Self {
        let grids = |example| DirectGrids {
            input: grid_extent(decoder, INPUT_FRAME, Some(example)),
            output: grid_extent(decoder, OUTPUT_FRAME, Some(example)),
        };
        let entries = contents.examples.iter().map(|entry| entry.example.map_or(
            DirectGrids { input: None, output: None }, &grids)).collect();
        let (task, _, _) = decoder.evaluation_inputs();
        let examples = task.examples().map(grids).collect();
        let mut proof = Proof {
            checked, contents, earlier, form, names: names_of(decoder.registry(), earlier),
            dets: contents.dets.iter().map(|d| relation_spelled(&d.relation)).collect(),
            bodies: BTreeMap::new(),
        };
        let row_examples = contents.columns.iter().enumerate().map(|(column, _)| {
            if !matches!(contents.frames[column].as_str(), INPUT_FRAME | OUTPUT_FRAME) { return None; }
            proof.column(column)
        }).collect();
        Self { entries, examples, row_examples }
    }

    pub(super) fn at(&self, contents: &Contents, entry: usize, column: usize, row: &[TermId]) -> Option<Extent> {
        let frame = &contents.frames[column];
        match self.row_examples.get(column)? {
            Some(binding) => {
                let example = binding.get(row)?;
                self.examples.get(usize::from(example.index()))?.at(frame)
            }
            None => self.entries.get(entry)?.at(frame),
        }
    }

    pub(super) fn complete(&self, contents: &Contents, column: usize) -> bool {
        // This inspects already materialized cells, not another binding query.
        for (entry, example) in contents.examples.iter().enumerate() {
            if self.row_examples[column].is_none() {
                if self.entries[entry].at(&contents.frames[column]).is_some() { continue; }
                return false;
            }
            let Ok(assigned) = &example.rows else { continue; };
            for (_, models) in &assigned.at { for model in models {
                if let RelationValue::Rows(rows) = model {
                    let mut complete = true;
                    each_row(rows, &mut |row| { complete &= self.at(contents, entry, column, row).is_some(); });
                    if !complete { return false; }
                }
            }}
        }
        true
    }
}

struct Proof<'a> {
    checked: &'a CheckedProgram,
    contents: &'a Contents,
    earlier: &'a [&'a Table],
    form: &'a NodePath,
    names: TableNames,
    dets: Vec<String>,
    bodies: BTreeMap<NodePath, Option<BodyView>>,
}

impl Proof<'_> {
    fn column(&mut self, column: usize) -> Option<RowExample> {
        let contents = self.contents;
        let sources = contents.flows.get(column)?;
        let mut found = None;
        for source in sources {
            for frame in &source.frames {
                // Empty value-only lineage does not contribute another frame.
                // Unknown or made frames cannot prove a direct grid context.
                if !matches!(frame, SourceFrame::Read) { return None; }
                let own = self.source(source, &contents.frames[column])?;
                if found.is_some_and(|held| held != own) { return None; }
                found = Some(own);
            }
        }
        found
    }

    fn source(&mut self, source: &ColumnSource, frame: &str) -> Option<RowExample> {
        // LabelId is local to a form. Never join equal numbers across scopes.
        if source.atom.0.first() != self.form.0.first() { return None; }
        let at = self.body(&source.atom)?;
        let view = self.bodies.get(&at)?.as_ref()?;
        let (atom, paths) = read_at(&view.clause, &view.paths, &source.atom)?;
        if matches!(atom.source, AtomSource::Fact(FactRelation::ExInput)) && frame != INPUT_FRAME
            || matches!(atom.source, AtomSource::Fact(FactRelation::ExOutput)) && frame != OUTPUT_FRAME {
            return None;
        }
        let argument = match example_argument(self.checked, &source.atom, atom) {
            ExampleArgument::Explicit(argument) => argument?,
            ExampleArgument::Ambient => {
                // Propagate an earlier column's proved Example binding through
                // this atom's actual native argument position/path.
                let located = locate(&self.names, &self.dets, source);
                let named = located.table?;
                let column = read_index(&located, source)?;
                let table = self.earlier.get((named.row as usize).checked_sub(EVIDENCE_FACTS.len())?)?;
                let contents = table.contents.as_ref().ok()?;
                let position = match *contents.extents.as_ref()?.contexts.row_examples.get(column)?.as_ref()? {
                    RowExample::Constant(value) => return Some(RowExample::Constant(value)),
                    RowExample::Column(example) => match &named.paths {
                        Some(paths) => {
                            let Resolution::Node(node) = self.checked.program.resolution(&source.atom)? else { return None; };
                            let example_path = paths.get(example)?;
                            self.checked.program.row_paths(*node)?.iter().position(|path| path == example_path)?
                        }
                        None => example,
                    },
                };
                atom.arguments.0.iter().find(|(at, _)| usize::from(at.0) == position)?.1
            }
        };
        RowExample::from_argument(argument, paths, |label| {
            let mut columns = self.contents.columns.iter().enumerate().filter(|(_, column)| {
                column.label_id == Some(label) && column.ty == ValueType::Example
            });
            let (column, _) = columns.next()?;
            columns.next().is_none().then_some(column)
        })
    }

    fn body(&mut self, atom: &NodePath) -> Option<NodePath> {
        let root = NodeRef::Program(self.checked.program.program.value());
        for length in (1..atom.0.len()).rev() {
            let at = NodePath(atom.0[..length].into());
            if matches!(node_at(root, &at), Some(NodeRef::Body(_))) {
                let found = self.bodies.entry(at.clone()).or_insert_with(|| BodyView::at(self.checked, &at).ok());
                if found.is_some() { return Some(at); }
            }
        }
        None
    }
}

/// The native owner of a source path, for relation and algebra atoms alike.
/// Scope remains attached to its original IrPaths even through key/OR nodes.
pub(super) fn node_at_path<'a>(clause:&'a ClauseIr,paths:&'a IrPaths,wanted:&NodePath)->Option<(&'a IrNode,&'a IrPaths)> {
    for (node,at) in clause.nodes.iter().zip(paths.nodes.iter()) {
        match (node,at) {
            (IrNode::Atom(_) | IrNode::Lib(_),NodePaths::Atom(at)) if at==wanted=>return Some((node,paths)),
            (IrNode::Atom(atom),NodePaths::Key(at))=>if let AtomSource::Key(key)=&atom.source {
                if let Some(found)=node_at_path(&key.clause,at,wanted) {return Some(found);}
            },
            (IrNode::Or(union),NodePaths::Branches(branches))=>{
                for (clause,at) in union.branches.iter().zip(branches.iter()) {
                    if let Some(found)=node_at_path(clause,at,wanted) {return Some(found);}
                }
            },
            _=>{},
        }
    }
    None
}

pub(super) fn read_at<'a>(clause:&'a ClauseIr,paths:&'a IrPaths,wanted:&NodePath)->Option<(&'a RelationAtom,&'a IrPaths)> {
    let (IrNode::Atom(atom),paths)=node_at_path(clause,paths,wanted)? else {return None};
    Some((atom,paths))
}

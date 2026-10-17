//! What a file holds beside its node values: places, label names, comments,
//! the elision of sites, and the strings.
//!
//! Implements `work/engine/reader.md`, Programs as values: "A node's places
//! in the files, its label names and its order of atoms and branches are kept
//! beside it, outside its hash, so the writer gives back the file's bytes."
//! and Solvers: "The tree keeps the comments and the strings". The order of
//! atoms and branches is the order of the node's lists, as
//! [`crate::program`] gives.
//!
//! The reader fills a layout and the writer reads it. A synthesized program
//! has no layout, and the writer names its labels as
//! [`crate::write::write_synthesized`] gives.

#![allow(unused_variables, dead_code)]

use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::program::LabelId;

/// One of a solver's two files.
///
/// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, its label names and its order of atoms and branches are kept beside it, outside its hash".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum SolverFile {
    Arclog,
    Arcdata,
}

/// A place in a file: its byte span, and the line and column of its start,
/// both counted from 1.
///
/// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, its label names and its order of atoms and branches are kept beside it, outside its hash".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct SourcePlace {
    pub file: SolverFile,
    pub start: u32,
    pub end: u32,
    pub line: u32,
    pub column: u32,
}

/// A comment of a file, `;;` to the line's end, and where it stands.
///
/// Implements `work/engine/reader.md`, Solvers: "The tree keeps the comments and the strings".
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Comment {
    pub place: SourcePlace,
    pub text: Box<str>,
}

/// The layout of one node: where it stands, the names of the labels it
/// makes, and which of its sites the file elides.
///
/// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, its label names and its order of atoms and branches are kept beside it, outside its hash".
#[derive(Clone, Debug, Default)]
pub struct NodeLayout {
    pub place: Option<SourcePlace>,
    pub label_names: Box<[(LabelId, Box<str>)]>,
    /// The indexes of the node's sites that the file writes as the bare
    /// label, as `docs/arclog.md`, Sites, gives.
    pub elided_sites: Box<[u32]>,
}

/// The layout of a solver's two files.
///
/// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, its label names and its order of atoms and branches are kept beside it, outside its hash".
#[derive(Clone, Debug, Default)]
pub struct Layout {
    pub nodes: StableHashMap<(SolverFile, NodePath), NodeLayout>,
    pub comments: Box<[Comment]>,
}

impl Layout {
    /// The layout of the node at `path` of `file`, if the file holds it.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, its label names and its order of atoms and branches are kept beside it, outside its hash".
    pub fn node(&self, file: SolverFile, path: &NodePath) -> Option<&NodeLayout> {
        todo!()
    }
}

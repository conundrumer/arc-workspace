//! What a file holds beside its node values: places, label names, comments,
//! the elision of sites, and the strings. These stand outside a node's hash,
//! so the writer gives back the file's bytes. The order of atoms and
//! branches is the order of the node's lists, which its canonical hash and
//! its equality leave out, as [`crate::program`] gives.
//!
//! The reader fills a layout and the writer reads it. A synthesized program
//! has no layout, and the writer names its labels as
//! [`crate::write::write_synthesized`] gives.

use std::collections::BTreeMap;

use crate::program::path::NodePath;
use crate::program::LabelId;

/// A file the s-expression reader reads: one of a solver's two files, or one
/// of the lib files under `engine/lib/`, as [`crate::registry`] gives.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum SourceFile {
    Arclog,
    Arcdata,
    /// `engine/lib/registry.sexpr`.
    LibRegistry,
    /// `engine/lib/proposers.arclog`.
    LibProposers,
}

/// A place in a file: its byte span, and the line and column of its start,
/// both counted from 1.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct SourcePlace {
    pub file: SourceFile,
    pub start: u32,
    pub end: u32,
    pub line: u32,
    pub column: u32,
}

/// A place in a solver's file, or in the file of the solver its
/// `representative` line names, which holds forms of its case programs: the
/// task id that names the file, or `None` for a lib file under
/// `engine/lib/`, and the place in it. A reader that reads one file gives
/// `None`, and [`crate::read::read_solver`] gives the solver's task id. The
/// claims of a solver with a `representative` line belong to the
/// representative's file (`docs/arclog/arcdata.md#header`), so an error in
/// one of them stands at a place of that file.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct FilePlace {
    pub task_id: Option<Box<str>>,
    pub place: SourcePlace,
}

/// A comment of a file, `;;` to the line's end, and where it stands. `text`
/// is the comment as written, from its first `;`.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Comment {
    pub place: SourcePlace,
    pub text: Box<str>,
}

/// The layout of one node: where it stands, where each of its own tokens
/// stands, the names of the labels it makes, and which of its sites the
/// file elides.
#[derive(Clone, Debug, Default)]
pub struct NodeLayout {
    pub place: Option<SourcePlace>,
    /// The place of each token the node writes outside its children, in the
    /// order the file writes them: its parentheses, keywords, names and
    /// strings, and the labels of a site or a constraint. A bare-label
    /// argument of a site has its token here, among its site's tokens. The
    /// root of a file, the empty path, holds one: the place of the file's
    /// end.
    pub tokens: Box<[SourcePlace]>,
    /// The name the file writes for each label the node makes. A label is
    /// made by the form that is its scope, as [`LabelId`] gives.
    pub label_names: Box<[(LabelId, Box<str>)]>,
    /// The indexes of the node's sites that the file writes as the bare
    /// label, as `docs/arclog/arclog.md#sites` gives.
    pub elided_sites: Box<[u32]>,
}

/// The layout of a solver's two files. A node of the arclog file is keyed by
/// its path, as [`crate::program::path::node_at`] walks it, and a node of
/// the arcdata file by its path, as [`crate::program::path::data_node_at`]
/// walks it. A bare-label argument of a site has no node layout of its own,
/// as [`NodeLayout::tokens`] gives.
#[derive(Clone, Debug, Default)]
pub struct Layout {
    pub nodes: BTreeMap<(SourceFile, NodePath), NodeLayout>,
    /// Each comment of the two files.
    pub comments: Box<[Comment]>,
}

impl Layout {
    /// The layout of the node at `path` of `file`, if the file holds it.
    pub fn node(&self, file: SourceFile, path: &NodePath) -> Option<&NodeLayout> {
        self.nodes.get(&(file, path.clone()))
    }
}

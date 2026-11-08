//! The source of an Ident column: the form that makes the column's values.
//!
//! An Ident column has one source. A label at two Ident columns of two
//! sources has an empty meet, and an `OR`, an `IF` or a type parameter that
//! takes columns of two sources has no join, so the type check refuses them.

use crate::hash::StableHash;

/// The source of an Ident column.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub enum IdentSource {
    /// A declared column with no maker yet, and an Ident read from a file.
    Open,
    /// The one source of the column.
    Form(SourceId),
}

/// The identity of a source: a hash of the maker form's resolved content and
/// its output port, or, for a form with no content, of its name, its canonical
/// form and its output port. The type check reads it to refuse a join across
/// sources, and the type name of an Ident column in a TableHash holds it. The
/// type names of a table export hold no source.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct SourceId(pub StableHash);

impl std::fmt::Debug for SourceId {
    /// The first 32 bits of the hash, in hexadecimal.
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{:08x}", (self.0 .0 >> 96) as u32)
    }
}

impl std::fmt::Debug for IdentSource {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            IdentSource::Open => f.write_str("Open"),
            IdentSource::Form(id) => write!(f, "Form({id:?})"),
        }
    }
}

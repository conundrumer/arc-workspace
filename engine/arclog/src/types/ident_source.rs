//! The source of an Ident column: the form that makes the column's values.
//!
//! An Ident column has one source. A label at two Ident columns of two
//! sources has an empty meet, and an `OR`, an `IF` or a type parameter that
//! takes columns of two sources has no join, so the type check refuses them.
//! The environment variable `ARCLOG_IDENT_SOURCE` turns the sources on.

use std::sync::OnceLock;

use crate::hash::StableHash;

/// The source of an Ident column.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub enum IdentSource {
    /// A declared column with no maker yet, an Ident read from a file, and
    /// every Ident while sources are off.
    Open,
    /// The one source of the column.
    Form(SourceId),
}

/// The identity of a source: a hash of the maker form's name, its canonical
/// form and its output port.
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

/// How much of the Ident source feature is on.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum IdentMode {
    /// Every Ident is [`IdentSource::Open`].
    Off,
    /// The type check gives each maker's Ident output its own source.
    Type,
    /// As `Type`, and an Ident's value holds the identity of its maker.
    Value,
}

/// The mode that `ARCLOG_IDENT_SOURCE` gives, read at the first call:
/// unset, empty or `0` for [`IdentMode::Off`], `type`, or `value`.
///
/// # Panics
///
/// At the first call, where the variable holds any other text.
pub fn ident_mode() -> IdentMode {
    static MODE: OnceLock<IdentMode> = OnceLock::new();
    *MODE.get_or_init(|| match std::env::var("ARCLOG_IDENT_SOURCE") {
        Err(_) => IdentMode::Off,
        Ok(text) => match text.as_str() {
            "" | "0" => IdentMode::Off,
            "type" => IdentMode::Type,
            "value" => IdentMode::Value,
            other => panic!("ARCLOG_IDENT_SOURCE is `{other}`; it must be unset, `type` or `value`"),
        },
    })
}

/// Whether the type check gives Ident outputs their sources.
pub fn sources_on() -> bool {
    ident_mode() != IdentMode::Off
}

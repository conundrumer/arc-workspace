//! What each subcommand's runs of the engine share: the table of the lib's
//! constructions and the bound on the bytes of a task session.

use std::sync::OnceLock;

use arclog::eval::instance::Constructions;
use arclog::registry::Registry;

/// The bound on the bytes of a task session of the engine's runs.
pub(crate) const SESSION_BYTES: usize = 1 << 32;

/// The table of the lib's constructions, built once.
pub(crate) fn constructions() -> Result<&'static Constructions, String> {
    static TABLE: OnceLock<Result<Constructions, String>> = OnceLock::new();
    TABLE
        .get_or_init(|| arclog_constructions::constructions(Registry::get()).map_err(|fault| format!("no table of constructions: {fault:?}")))
        .as_ref()
        .map_err(Clone::clone)
}

//! The parts of the lib whose Souffle form makes a free choice that
//! `docs/engine/equivariance.md#free-choices` records as a fault of the
//! Souffle lib, so that the comparison with the Souffle record gives a
//! difference there as that fault.

use super::evaluation::{Compared, Rows, Subject};

/// The section that records each free choice of [`RECORDED`].
pub(super) const SECTION: &str = "docs/engine/equivariance.md#free-choices";

/// Each element whose Souffle form makes a free choice the section
/// records, with the output the choice reaches, where it reaches one
/// output alone.
const RECORDED: &[(&str, Option<&str>)] = &[("same_line", None), ("Wallpaper", Some("action"))];

/// Whether the part at `index` of `subject` is one whose Souffle form
/// makes a free choice the section records.
fn recorded(subject: &Subject<'_>, index: usize) -> bool {
    let output = match subject {
        Subject::Relation { .. } => None,
        Subject::Component { component, .. } | Subject::Unfold { component, .. } => Some(&*component.outputs[index].name.0),
    };
    RECORDED.iter().any(|&(name, part)| name == subject.name() && (part.is_none() || part == output))
}

/// `walks` split into the parts whose differences are differences of the
/// engine's and those whose differences are faults of the Souffle lib:
/// each holds no row on either side at a part of the other.
pub(super) fn split(subject: &Subject<'_>, walks: &[Compared]) -> (Vec<Compared>, Vec<Compared>) {
    let only = |faults: bool| -> Vec<Compared> {
        let keep = |parts: &[Rows]| -> Vec<Rows> {
            parts.iter().enumerate().map(|(at, rows)| if recorded(subject, at) == faults { rows.clone() } else { Rows::new() }).collect()
        };
        walks.iter().map(|(engine, souffle)| (keep(engine), keep(souffle))).collect()
    };
    (only(false), only(true))
}

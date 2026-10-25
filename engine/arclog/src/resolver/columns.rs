//! The columns of a relation's rows, as the sites of a read name them: the
//! names of the columns, the slot of each column, and the place of each
//! column path in a row. The source of each column path stands in
//! [`super::column_sources`], the columns that the registry declares in
//! [`super::registry_columns`], and the columns that each kind of form gives
//! its relation in [`super::form_columns`].

use super::ColumnPosition;
use crate::program::{ColumnName, KeyBody, Site, SiteArg};
use crate::relations::{ColumnGroup, ColumnIndex};

use crate::read::spelling::KEY;

/// The column of a `RIGID_DET` output that holds the pose,
/// `docs/arclog/rigid.md#semantics`.
const POSE: &str = "Pose";
/// The Example column of a lifted read, `docs/arclog/arclog.md#program`.
const EXAMPLE: &str = "E";

fn written(name: &str) -> ColumnName {
    ColumnName::Written(name.into())
}

/// The name of the key column of a keyed form's relation.
pub(crate) fn key() -> ColumnName {
    written(KEY)
}

/// The name of the Example column of a lifted read.
pub(crate) fn example() -> ColumnName {
    written(EXAMPLE)
}

/// The name of the column of a `RIGID_DET` output that holds the pose.
pub(crate) fn pose() -> ColumnName {
    written(POSE)
}

/// The text of `name`, or `c<position>` where the name has none.
fn text(name: &ColumnName, position: usize) -> String {
    match name {
        ColumnName::Written(text) => text.to_string(),
        ColumnName::Slot(_) => format!("c{position}"),
    }
}

/// One column of a relation as a site names it: a column of one row
/// position, or a record, one row position per field.
#[derive(Clone, PartialEq, Eq, Debug)]
pub(super) enum Slot {
    Column(ColumnName),
    Record { name: ColumnName, fields: Box<[ColumnName]> },
}

impl Slot {
    pub(super) fn name(&self) -> &ColumnName {
        match self {
            Slot::Column(name) | Slot::Record { name, .. } => name,
        }
    }

    fn width(&self) -> u16 {
        match self {
            Slot::Column(_) => 1,
            Slot::Record { fields, .. } => fields.len() as u16,
        }
    }

    /// The slot of the column `name` of a head site's port: a record
    /// where `record` gives its fields.
    pub(super) fn of(name: &ColumnName, record: Option<&[ColumnName]>) -> Slot {
        match record {
            Some(fields) => Slot::Record { name: name.clone(), fields: fields.into() },
            None => Slot::Column(name.clone()),
        }
    }
}

/// Where a column path stands in a relation's rows.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(super) enum Place {
    Column(ColumnPosition),
    /// A record's columns, which a site on the record reads.
    Group(ColumnGroup),
    /// A field of a record.
    Field(ColumnPosition, ColumnGroup),
}

/// The columns of a relation, in the order of its rows.
#[derive(Clone, PartialEq, Eq, Debug, Default)]
pub(crate) struct Columns(pub(super) Box<[Slot]>);

impl Columns {
    pub(super) fn of_names(names: impl IntoIterator<Item = ColumnName>) -> Columns {
        Columns(names.into_iter().map(Slot::Column).collect())
    }

    pub(crate) fn names(&self) -> impl Iterator<Item = &ColumnName> + '_ {
        self.0.iter().map(Slot::name)
    }

    /// The name of each row position, in row order: a column's name, and
    /// a record's `<record>.<field>` per field. A name with no text is
    /// `c<position>`, its row position.
    pub(super) fn row_names(&self) -> Vec<String> {
        let mut names = Vec::new();
        for slot in self.0.iter() {
            let position = names.len();
            match slot {
                Slot::Column(name) => names.push(text(name, position)),
                Slot::Record { name, fields } => {
                    let record = text(name, position);
                    for field in fields.iter() {
                        let field = text(field, names.len());
                        names.push(format!("{record}.{field}"));
                    }
                }
            }
        }
        names
    }

    /// The place of the column at `path`: a column's name, then, on a
    /// record, a field's. A path past a column of one row position names
    /// that column, as the name of a bare label at a type parameter
    /// bound to one label does.
    pub(super) fn place(&self, path: &[ColumnName]) -> Option<Place> {
        let (first, rest) = path.split_first()?;
        let mut start = 0u16;
        for slot in self.0.iter() {
            if slot.name() == first {
                return match slot {
                    Slot::Column(_) => Some(Place::Column(ColumnPosition(start))),
                    Slot::Record { fields, .. } => {
                        let group = ColumnGroup { start: ColumnIndex(start), len: slot.width() };
                        match rest.first() {
                            None => Some(Place::Group(group)),
                            Some(field) => {
                                let index = fields.iter().position(|f| f == field)?;
                                Some(Place::Field(ColumnPosition(start + index as u16), group))
                            }
                        }
                    }
                };
            }
            start += slot.width();
        }
        None
    }

    /// The columns of the lifted relation, with the Example column
    /// first, as a `DET` reads a `RULE` relation.
    pub(super) fn lifted(&self) -> Columns {
        Columns(std::iter::once(Slot::Column(example())).chain(self.0.iter().cloned()).collect())
    }

    /// Writes the columns: each name, and each record's fields.
    pub(super) fn write(&self, out: &mut crate::program::canonical::CanonicalWriter) {
        out.len(self.0.len());
        for slot in self.0.iter() {
            match slot {
                Slot::Column(name) => {
                    out.write(&[0]);
                    out.name(name);
                }
                Slot::Record { name, fields } => {
                    out.write(&[1]);
                    out.name(name);
                    out.len(fields.len());
                    for field in fields.iter() {
                        out.name(field);
                    }
                }
            }
        }
    }
}

/// The fields of the record that the head site `site` projects onto
/// its column's type parameter, or `None` where it projects one label.
pub(crate) fn projection(site: &Site) -> Option<Box<[ColumnName]>> {
    match &site.value.args[..] {
        [SiteArg::Label(_) | SiteArg::NamedLabel { .. }] => None,
        args => Some(
            args.iter()
                .filter_map(|arg| match arg {
                    SiteArg::NamedLabel { name, .. } => Some(name.clone()),
                    SiteArg::Field(field) => Some(field.column.clone()),
                    SiteArg::Label(_) => None,
                })
                .collect(),
        ),
    }
}

pub(super) fn key_fields(key: &KeyBody) -> Box<[ColumnName]> {
    key.columns.iter().map(|column| column.name.clone()).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn row_names_give_a_records_fields_as_record_dot_field() {
        let columns = Columns(Box::new([
            Slot::Column(written("P")),
            Slot::Record { name: written("key"), fields: Box::new([written("A"), written("B")]) },
            Slot::Column(written("Z")),
        ]));
        assert_eq!(columns.row_names(), ["P", "key.A", "key.B", "Z"]);
    }

    #[test]
    fn row_names_give_a_name_with_no_text_as_c_and_its_row_position() {
        let columns = Columns(Box::new([
            Slot::Column(written("P")),
            Slot::Column(ColumnName::Slot(7)),
            Slot::Record { name: ColumnName::Slot(8), fields: Box::new([ColumnName::Slot(9)]) },
        ]));
        assert_eq!(columns.row_names(), ["P", "c1", "c2.c2"]);
    }
}

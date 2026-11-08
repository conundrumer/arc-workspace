//! A list of columns in which no column stands twice.

use std::fmt;
use std::ops::Deref;

/// A column that a list names twice.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RepeatedColumn(pub u16);

impl fmt::Display for RepeatedColumn {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "column {} stands twice", self.0)
    }
}

impl std::error::Error for RepeatedColumn {}

/// Columns of a relation, in the order given, each at most once. A read of a relation at some of its columns takes this type, so no read is asked for a column twice.
#[derive(Clone, PartialEq, Eq, Hash, serde::Serialize, serde::Deserialize)]
#[serde(try_from = "Box<[u16]>")]
pub struct Columns(Box<[u16]>);

impl Columns {
    /// The columns of `list`, in its order: the first column that stands twice where there is one.
    pub fn new(list: impl Into<Box<[u16]>>) -> Result<Columns, RepeatedColumn> {
        let list = list.into();
        for (at, column) in list.iter().enumerate() {
            if list[..at].contains(column) {
                return Err(RepeatedColumn(*column));
            }
        }
        Ok(Columns(list))
    }

    /// The columns of `list`, where it has no column twice; otherwise a panic that names `text`, the text of the term that the list belongs to.
    pub fn of_term(list: &[u16], text: &str) -> Columns {
        Columns::new(list).unwrap_or_else(|repeat| panic!("{repeat} in the columns {list:?} of the term {text}"))
    }

    /// One column.
    pub fn one(column: u16) -> Columns {
        Columns(Box::new([column]))
    }

    /// The columns before the `at`th and those from it on.
    pub fn split(&self, at: u16) -> (&[u16], &[u16]) {
        self.0.split_at(usize::from(at))
    }
}

impl Deref for Columns {
    type Target = [u16];

    fn deref(&self) -> &[u16] {
        &self.0
    }
}

impl fmt::Debug for Columns {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Debug::fmt(&self.0, f)
    }
}

impl TryFrom<Box<[u16]>> for Columns {
    type Error = RepeatedColumn;

    fn try_from(list: Box<[u16]>) -> Result<Columns, RepeatedColumn> {
        Columns::new(list)
    }
}

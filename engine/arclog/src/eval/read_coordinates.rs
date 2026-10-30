//! Native relation-read coordinates for compiler and table provenance.

/// The column of the relation a source reads.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SourceColumn {
    /// The source gives no column: a constant, or a lib name.
    None,
    /// The row position of the column.
    Position(u16),
    /// The Example of the entry that the source's table holds.
    Example,
}

/// Coordinates shared by provenance (IR -> source) and frame lookups
/// (source -> IR). Input aliases ExInput with its Example column removed;
/// lifted reads add an explicit Example before their original schema.
#[derive(Clone, Copy)]
pub struct ReadCoordinates {
    shift: i32,
    example: Option<u16>,
}

impl ReadCoordinates {
    pub fn new(input: bool, lifted: bool) -> Self {
        Self {
            shift: if input {
                1
            } else if lifted {
                -1
            } else {
                0
            },
            example: (!input && lifted).then_some(0),
        }
    }

    pub fn source(self, argument: u16) -> Option<SourceColumn> {
        if self.example == Some(argument) {
            return Some(SourceColumn::Example);
        }
        u16::try_from(i32::from(argument) + self.shift)
            .ok()
            .map(SourceColumn::Position)
    }

    pub fn argument(self, source: SourceColumn) -> Option<u16> {
        match source {
            SourceColumn::None => None,
            SourceColumn::Example => self.example,
            SourceColumn::Position(position) => {
                u16::try_from(i32::from(position) - self.shift).ok()
            }
        }
    }
}

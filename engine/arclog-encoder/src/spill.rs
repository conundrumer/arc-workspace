//! Stored rows on disk, as streamable zstd. A walk moves the values that its terms read last to a
//! file, so that its memory stays bounded, and reads a value back from its file before a term
//! reads it. A value read back holds the same rows in the same order.

use std::io::{Read, Write};
use std::path::Path;
use std::sync::Arc;

use crate::native::{Cell, Part, Table, Val};

/// The fewest cells a value holds for a walk to move it to disk.
pub const MIN_CELLS: usize = 1 << 14;

/// The cells that one block of a file holds.
const BLOCK_CELLS: usize = 1 << 18;

/// The zstd level of a file: a low one, since a file is read back within the walk.
const LEVEL: i32 = 1;

/// The bytes of a file that one read of the file takes in.
const READ_BYTES: usize = 1 << 20;

/// Writes the parts of a value to the file at `path`.
pub fn write(path: &Path, parts: &[Part]) -> std::io::Result<()> {
    let mut out = zstd::stream::write::Encoder::new(std::fs::File::create(path)?, LEVEL)?;
    out.write_all(&(parts.len() as u64).to_ne_bytes())?;
    let mut block: Vec<u8> = Vec::with_capacity(BLOCK_CELLS * 4);
    for part in parts {
        out.write_all(&(part.columns.len() as u64).to_ne_bytes())?;
        for column in part.columns.iter() {
            out.write_all(&column.to_ne_bytes())?;
        }
        out.write_all(&(part.table.arity as u64).to_ne_bytes())?;
        out.write_all(&(part.table.len as u64).to_ne_bytes())?;
        out.write_all(&part.table.hash().to_ne_bytes())?;
        for cells in part.table.cells().chunks(BLOCK_CELLS) {
            block.clear();
            for cell in cells {
                block.extend_from_slice(&cell.to_ne_bytes());
            }
            out.write_all(&block)?;
        }
    }
    out.finish()?.flush()
}

fn read_count(input: &mut impl Read) -> std::io::Result<usize> {
    let mut bytes = [0u8; 8];
    input.read_exact(&mut bytes)?;
    Ok(u64::from_ne_bytes(bytes) as usize)
}

/// The value that [`write`] wrote to the file at `path`.
pub fn read(path: &Path) -> std::io::Result<Val> {
    let mut input = zstd::stream::read::Decoder::with_buffer(std::io::BufReader::with_capacity(READ_BYTES, std::fs::File::open(path)?))?;
    let count = read_count(&mut input)?;
    let mut parts: Vec<Part> = Vec::with_capacity(count);
    let mut block: Vec<u8> = Vec::new();
    for _ in 0..count {
        let width = read_count(&mut input)?;
        let mut columns: Vec<u16> = Vec::with_capacity(width);
        for _ in 0..width {
            let mut bytes = [0u8; 2];
            input.read_exact(&mut bytes)?;
            columns.push(u16::from_ne_bytes(bytes));
        }
        let arity = read_count(&mut input)?;
        let len = read_count(&mut input)?;
        let mut hash = [0u8; 16];
        input.read_exact(&mut hash)?;
        let hash = u128::from_ne_bytes(hash);
        let mut cells: Vec<Cell> = Vec::with_capacity(arity * len);
        let mut left = arity * len;
        // The block grows to the most that one read of this file takes.
        if block.len() < left.min(BLOCK_CELLS) * 4 {
            block.resize(left.min(BLOCK_CELLS) * 4, 0);
        }
        while left > 0 {
            let take = left.min(BLOCK_CELLS);
            input.read_exact(&mut block[..take * 4])?;
            cells.extend(block[..take * 4].chunks_exact(4).map(|bytes| Cell::from_ne_bytes([bytes[0], bytes[1], bytes[2], bytes[3]])));
            left -= take;
        }
        // A table of no columns holds no cells, and its length is 0 or 1. The cells of any other were written in ascending order.
        let table = if arity == 0 { Table::unit(len == 1) } else { Table::ascending_with_hash(arity, cells, hash) };
        parts.push(Part { table, columns: columns.into_boxed_slice() });
    }
    Ok(Val::Rows(Arc::new(parts)))
}

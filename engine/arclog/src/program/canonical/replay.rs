//! The writes of a form through a name writer other than [`AsWritten`],
//! kept on the form's node, each with the bytes that each call of its name
//! writer appended. A write's bytes depend on the form and on those bytes
//! alone, so a later write of the form whose name writer appends the same
//! bytes for each of those calls gives the kept form.

use std::sync::Mutex;

use super::*;

/// The writes a node keeps. A node keeps at most [`CACHED_WRITES`], the
/// latest first.
#[derive(Debug, Default)]
pub(super) struct WriteCache(Mutex<Vec<CachedWrite>>);

/// The number of writes a node keeps.
const CACHED_WRITES: usize = 8;

/// One write: each call its name writer took, with the bytes it appended,
/// and the form written.
#[derive(Debug)]
struct CachedWrite {
    calls: Box<[(NameCall, Box<[u8]>)]>,
    form: CanonicalForm,
    /// What the write noted in the gauges a cost carries, which a read of it notes again.
    notes: crate::eval::NoteId,
}

/// A call of a [`NameWriter`], by its arguments.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
enum NameCall {
    Name(RelationRef),
    Own(DeclaredName),
    /// A column, in an order of the columns of its relation.
    Column(RelationRef, Box<[ColumnName]>, usize),
    ColumnOrders(RelationRef),
}

impl NameCall {
    /// The bytes `names` appends on this call.
    fn bytes(&self, names: &dyn NameWriter) -> Vec<u8> {
        let mut out = CanonicalWriter::default();
        match self {
            NameCall::Name(relation) => names.write_name(relation, &mut out),
            NameCall::Own(name) => names.write_own(name, &mut out),
            NameCall::Column(relation, column, order) => names.write_column_in(relation, column, *order, &mut out),
            NameCall::ColumnOrders(relation) => out.len(names.column_orders(relation)),
        }
        out.bytes
    }
}

/// A name writer that records each distinct call of the writer it wraps,
/// with the bytes that writer appended.
struct Recording<'n> {
    names: &'n dyn NameWriter,
    calls: std::cell::RefCell<StableHashMap<NameCall, Box<[u8]>>>,
    /// Whether a search under the write passed the labeling node cap.
    reached: std::cell::Cell<bool>,
}

impl Recording<'_> {
    fn call(&self, call: NameCall, out: &mut CanonicalWriter) {
        if let Some(bytes) = self.calls.borrow().get(&call) {
            return out.write(bytes);
        }
        let bytes = call.bytes(self.names);
        out.write(&bytes);
        self.calls.borrow_mut().insert(call, bytes.into());
    }
}

impl NameWriter for Recording<'_> {
    fn write_name(&self, relation: &RelationRef, out: &mut CanonicalWriter) {
        self.call(NameCall::Name(relation.clone()), out);
    }

    fn write_own(&self, name: &DeclaredName, out: &mut CanonicalWriter) {
        self.call(NameCall::Own(name.clone()), out);
    }

    fn write_column(&self, relation: &RelationRef, column: &[ColumnName], out: &mut CanonicalWriter) {
        self.write_column_in(relation, column, 0, out);
    }

    fn column_orders(&self, relation: &RelationRef) -> usize {
        self.call(NameCall::ColumnOrders(relation.clone()), &mut CanonicalWriter::default());
        self.names.column_orders(relation)
    }

    fn write_column_in(&self, relation: &RelationRef, column: &[ColumnName], order: usize, out: &mut CanonicalWriter) {
        self.call(NameCall::Column(relation.clone(), column.into(), order), out);
    }

    fn labeling_bound_reached(&self) {
        self.reached.set(true);
        self.names.labeling_bound_reached();
    }
}

/// The form `write` gives through `names`, a write of `form`, or the form
/// of a write that the node of `form` keeps whose every call `names`
/// answers with the same bytes. `write` writes `form` alone and reads no
/// name but through the name writer it is given. A write with a search past
/// the labeling node cap is kept nowhere, so that each use of it reaches
/// `names.labeling_bound_reached()`.
pub(crate) fn cached_write(form: &Form, names: &dyn NameWriter, write: impl FnOnce(&dyn NameWriter) -> CanonicalForm) -> CanonicalForm {
    if names.feature_sites() {
        return write(names);
    }
    let cache = &super::form::cache(form).writes.0;
    let matches = |found: &CachedWrite| found.calls.iter().all(|(call, bytes)| call.bytes(names)[..] == bytes[..]);
    let found = cache.lock().expect("no write panics while it holds the cached writes").iter().find(|found| matches(found)).map(|found| (found.form.clone(), found.notes));
    if let Some((form, notes)) = found {
        crate::eval::replay_notes(notes);
        return form;
    }
    let recording = Recording { names, calls: Default::default(), reached: Default::default() };
    let (form_written, notes) = crate::eval::noting(|| write(&recording));
    if recording.reached.get() {
        return form_written;
    }
    let calls: Box<[(NameCall, Box<[u8]>)]> = recording.calls.into_inner().into_iter().collect();
    let mut cached = cache.lock().expect("no write panics while it holds the cached writes");
    cached.insert(0, CachedWrite { calls, form: form_written.clone(), notes });
    cached.truncate(CACHED_WRITES);
    form_written
}

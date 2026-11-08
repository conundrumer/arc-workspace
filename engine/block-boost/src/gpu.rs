//! The CUDA side of `softmax-gpu` (gpu/bbgpu.cu): the arrays of the store and of the pairs on the card, and the calls that `softmax` makes in place of its
//! CPU gradient, pair sums, histogram, partition and score steps. Built without the feature `gpu`, every call panics.

use super::{Bin, Cut, Pairs, Store};
use std::ffi::c_void;

macro_rules! ffi {
    ($(fn $name:ident($($arg:ident: $ty:ty),*) $(-> $ret:ty)?;)*) => {
        #[cfg(feature = "gpu")]
        unsafe extern "C" {
            $(fn $name($($arg: $ty),*) $(-> $ret)?;)*
        }
        $(
            #[cfg(not(feature = "gpu"))]
            #[allow(unused_variables)]
            unsafe fn $name($($arg: $ty),*) $(-> $ret)? {
                panic!("this block-boost was built without --features gpu")
            }
        )*
    };
}

ffi! {
    fn bbgpu_init(device: i32, kept: u32, bins: u32, num_uses: u32, maps: u32, pairs: u64, rows: u64, groups: u64, leaves: u32) -> *mut c_void;
    fn bbgpu_set_columns(ctx: *mut c_void, col_start: *const u32, zero_pos: *const u32, has_nan: *const u8, col_uses: *const u64);
    fn bbgpu_set_use(ctx: *mut c_void, u: u32, map: u32, blocks: u64, ptr: *const u64, bid: *const u32, entries: u64);
    fn bbgpu_set_pairs(ctx: *mut c_void, block: *const u32, start: *const u32);
    fn bbgpu_set_rows(ctx: *mut c_void, row_pair: *const u32, label: *const u8, group_start: *const u32);
    fn bbgpu_report(ctx: *mut c_void);
    fn bbgpu_score_set(ctx: *mut c_void, score: *const f64);
    fn bbgpu_score_get(ctx: *mut c_void, score: *mut f64);
    fn bbgpu_sync(ctx: *mut c_void);
    fn bbgpu_gradient(ctx: *mut c_void) -> f64;
    fn bbgpu_fill(ctx: *mut c_void, slot: u32, start: u64, len: u64);
    fn bbgpu_root(ctx: *mut c_void, slot: u32, out_g: *mut f64, out_h: *mut f64);
    fn bbgpu_subtract(ctx: *mut c_void, dst: u32, src: u32);
    fn bbgpu_download(ctx: *mut c_void, slot: u32, out: *mut Bin);
    fn bbgpu_partition(ctx: *mut c_void, start: u64, len: u64, column: u32, pos: u32, default_left: i32, set: *const u64, set_words: u32, out: *mut u64);
    fn bbgpu_add_value(ctx: *mut c_void, start: u64, len: u64, value: f64);
    fn bbgpu_reset_items(ctx: *mut c_void);
}

/// The card's copy of a store and of its pairs, and the pairs' scores.
pub struct Gpu {
    ctx: *mut c_void,
    free_slots: Vec<u32>,
}

impl Gpu {
    /// Puts the store's columns and uses, the pairs, and the rows' pairs, labels and group starts on the card.
    pub fn new(store: &Store, pairs: &Pairs, label: &[u8], group_start: &[u32], leaves: usize) -> Gpu {
        let device: i32 = std::env::var("BB_GPU_DEVICE").ok().and_then(|x| x.parse().ok()).unwrap_or(0);
        let slots = leaves + 3;
        let ctx = unsafe { bbgpu_init(device, store.kept as u32, store.bins as u32, store.uses.len() as u32, store.maps.len() as u32, pairs.count() as u64, store.rows as u64, (group_start.len() - 1) as u64, leaves as u32) };
        assert!(!ctx.is_null());
        unsafe {
            bbgpu_set_columns(ctx, store.col_start.as_ptr(), store.zero_pos.as_ptr(), store.has_nan.as_ptr(), store.col_uses.as_ptr());
            for (u, data) in store.uses.iter().enumerate() {
                bbgpu_set_use(ctx, u as u32, data.map as u32, (data.ptr.len() - 1) as u64, data.ptr.as_ptr(), data.bid.as_ptr(), data.bid.len() as u64);
            }
            bbgpu_set_pairs(ctx, pairs.block.as_ptr(), pairs.start.as_ptr());
            bbgpu_set_rows(ctx, pairs.row_pair.as_ptr(), label.as_ptr(), group_start.as_ptr());
            bbgpu_report(ctx);
        }
        Gpu { ctx, free_slots: (0..slots as u32).rev().collect() }
    }

    pub fn sync(&self) {
        unsafe { bbgpu_sync(self.ctx) }
    }

    pub fn take_slot(&mut self) -> u32 {
        self.free_slots.pop().expect("the card has a histogram for each live leaf")
    }

    pub fn give_slot(&mut self, slot: u32) {
        self.free_slots.push(slot);
    }

    pub fn set_score(&self, score: &[f64]) {
        unsafe { bbgpu_score_set(self.ctx, score.as_ptr()) }
    }

    pub fn get_score(&self, score: &mut [f64]) {
        unsafe { bbgpu_score_get(self.ctx, score.as_mut_ptr()) }
    }

    /// The gradients and Hessians of the pairs' rows, summed by pair. Gives the sum of the groups' losses.
    pub fn gradient(&self) -> f64 {
        unsafe { bbgpu_gradient(self.ctx) }
    }

    /// The pairs in order, and the histogram of all of them in `slot`. Gives the sums of their gradients and of their Hessians.
    pub fn root(&self, slot: u32) -> (f64, f64) {
        let (mut g, mut h) = (0.0, 0.0);
        unsafe { bbgpu_root(self.ctx, slot, &mut g, &mut h) };
        (g, h)
    }

    pub fn fill(&self, slot: u32, start: usize, len: usize) {
        unsafe { bbgpu_fill(self.ctx, slot, start as u64, len as u64) }
    }

    /// `dst` less `src`, in every bin.
    pub fn subtract(&self, dst: u32, src: u32) {
        unsafe { bbgpu_subtract(self.ctx, dst, src) }
    }

    pub fn download(&self, slot: u32, out: &mut [Bin]) {
        unsafe { bbgpu_download(self.ctx, slot, out.as_mut_ptr()) }
    }

    /// Partitions the pairs `start..start + len` by the split: the places up to a position go left, or the places of a category set. Gives the count of pairs that go left
    /// and of the rows they stand for.
    pub fn partition(&self, start: usize, len: usize, column: u32, cut: &Cut, default_left: bool) -> (usize, usize) {
        let mut out = [0u64; 2];
        let (pos, set, words) = match cut {
            Cut::Upto(pos) => (*pos, std::ptr::null(), 0),
            Cut::Set(bits) => (0, bits.as_ptr(), bits.len() as u32),
        };
        unsafe { bbgpu_partition(self.ctx, start as u64, len as u64, column, pos, default_left as i32, set, words, out.as_mut_ptr()) };
        (out[0] as usize, out[1] as usize)
    }

    pub fn add_value(&self, start: usize, len: usize, value: f64) {
        unsafe { bbgpu_add_value(self.ctx, start as u64, len as u64, value) }
    }

    pub fn reset_items(&self) {
        unsafe { bbgpu_reset_items(self.ctx) }
    }
}

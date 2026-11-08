//! Walks over the cells of a grid, for the catalog's cell kinds and the generator's parts: the regions of free cells that
//! a set of cells encloses, and the layers of cells at each number of steps from a set of cells.
//!
//! A cell of a frame of height `h` and width `w` is written as `row * w + column`.

/// Calls `each` with the cells of each 4-connected region of free cells that does not touch the edge of the frame.
/// `blocked` holds a flag per cell of the frame, true where the cell is not free.
pub fn for_each_enclosed_region(mut blocked: Vec<bool>, h: usize, w: usize, mut each: impl FnMut(&[usize])) {
    let mut stack = Vec::new();
    let mut region = Vec::new();
    for start in 0..h * w {
        if blocked[start] {
            continue;
        }
        blocked[start] = true;
        stack.push(start);
        region.clear();
        let mut on_edge = false;
        while let Some(at) = stack.pop() {
            region.push(at);
            let (r, c) = (at / w, at % w);
            on_edge |= r == 0 || c == 0 || r + 1 == h || c + 1 == w;
            let mut go = |next: usize| {
                if !blocked[next] {
                    blocked[next] = true;
                    stack.push(next);
                }
            };
            if r > 0 {
                go(at - w);
            }
            if r + 1 < h {
                go(at + w);
            }
            if c > 0 {
                go(at - 1);
            }
            if c + 1 < w {
                go(at + 1);
            }
        }
        if !on_edge {
            each(&region);
        }
    }
}

/// The count of 4-connected regions outside a cell set that it encloses, where a region is enclosed if it does not
/// reach the edge of the set's bounding box widened by one cell on each side.
pub fn enclosed_regions(list: &[(u8, u8)]) -> u32 {
    let (rmin, rmax) = (list.iter().map(|x| i32::from(x.0)).min().unwrap_or(0), list.iter().map(|x| i32::from(x.0)).max().unwrap_or(0));
    let (cmin, cmax) = (list.iter().map(|x| i32::from(x.1)).min().unwrap_or(0), list.iter().map(|x| i32::from(x.1)).max().unwrap_or(0));
    let (h, w) = ((rmax - rmin + 3) as usize, (cmax - cmin + 3) as usize);
    let mut blocked = vec![false; h * w];
    for (r, c) in list {
        blocked[(i32::from(*r) - rmin + 1) as usize * w + (i32::from(*c) - cmin + 1) as usize] = true;
    }
    let mut regions = 0;
    for_each_enclosed_region(blocked, h, w, |_| regions += 1);
    regions
}

/// Walks outward from the start cells in layers. The cells of layer k are the cells that the fewest steps reach in k
/// steps, where a step goes to a neighbor along a row or a column, or also along a diagonal with `diagonal`. For each
/// cell of a layer, in order of layer, `reach` gets the cell and k. When `reach` gives true for a cell, the walk stops
/// after the rest of that layer.
pub fn walk_outward(start: impl IntoIterator<Item = usize>, h: usize, w: usize, diagonal: bool, mut reach: impl FnMut(usize, u16) -> bool) {
    let mut seen = vec![false; h * w];
    let mut layer = Vec::new();
    for at in start {
        if !seen[at] {
            seen[at] = true;
            layer.push(at);
        }
    }
    let mut steps = 0u16;
    while !layer.is_empty() {
        steps += 1;
        let mut ahead = Vec::new();
        let mut stop = false;
        for at in &layer {
            let (r, c) = (at / w, at % w);
            for nr in r.saturating_sub(1)..(r + 2).min(h) {
                for nc in c.saturating_sub(1)..(c + 2).min(w) {
                    if !diagonal && nr != r && nc != c {
                        continue;
                    }
                    let next = nr * w + nc;
                    if !seen[next] {
                        seen[next] = true;
                        ahead.push(next);
                        stop |= reach(next, steps);
                    }
                }
            }
        }
        if stop {
            return;
        }
        layer = ahead;
    }
}

// GPU kernels for `block-boost softmax-gpu`: the gradient of the softmax objective, the sums of each pair's rows, the histogram of a leaf's pairs, the stable
// partition of a leaf's pairs by a split, and the update of the pairs' scores. The tree's growth, the best split of a histogram, the column sampler, the model
// lines and the checkpoints stay in src/main.rs. Everything runs in the default stream, so calls are in order; a call that returns a value waits for the stream.
//
// What a pair is, what a block's entries are, and what a split sends left are as in main.rs (`Pairs`, `Store`, `SplitTest`).
#include <cuda_runtime.h>
#include <cub/cub.cuh>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#define CK(x) do { cudaError_t e_ = (x); if (e_ != cudaSuccess) { fprintf(stderr, "bbgpu: %s:%d %s: %s\n", __FILE__, __LINE__, #x, cudaGetErrorString(e_)); abort(); } } while (0)

static const uint32_t NONE = 0xFFFFFFFFu;
static const uint32_t NO_ENTRY = 1, GOES_LEFT = 2, GOES_RIGHT = 3;
static const int MAX_USES = 8;
static const int THREADS = 256;

struct Bin { double g, h; };

// One use: a map's blocks, each block's entries (bin numbers, ascending), and the working arrays of the leaf's block sums.
struct UseDev {
    uint32_t map;
    uint64_t blocks;
    const uint64_t* ptr;
    const uint32_t* bid;
    uint32_t* memo;      // per block: stamp << 2 | code, the answer of the latest split
    double* sg;          // per block: the sum of the leaf's pairs' gradients
    double* sh;
    uint32_t* seen;      // per block: 1 once the block is in `touched`
    uint32_t* touched;   // the blocks that hold a pair of the leaf
    uint32_t* count;     // how many
};

struct SplitArgs {
    uint32_t start, end, zero, pos;
    int has_nan, default_left;
    uint64_t mask;
    uint32_t stamp;
};

struct Ctx {
    uint32_t kept = 0, bins = 0, num_uses = 0, maps = 0, slots = 0;
    uint64_t pairs = 0, rows = 0, groups = 0;
    uint32_t* col_start = nullptr; uint32_t* zero_pos = nullptr; uint8_t* has_nan = nullptr; uint64_t* col_uses = nullptr;
    std::vector<uint32_t> h_col_start, h_zero_pos; std::vector<uint8_t> h_has_nan; std::vector<uint64_t> h_col_uses;
    UseDev uses_h[MAX_USES];
    UseDev* uses_d = nullptr;
    uint32_t* pair_block = nullptr;   // pair * maps + map
    uint32_t* pair_start = nullptr;   // pairs + 1: the rows of pair p are start[p]..start[p + 1] of the pair's order, so only the count is used
    uint32_t* row_pair = nullptr;
    uint8_t* label = nullptr;
    uint32_t* group_start = nullptr;
    double *pair_g = nullptr, *pair_h = nullptr, *pair_score = nullptr;
    double* loss = nullptr;
    uint32_t* idx = nullptr;          // the leaves' pairs, a leaf in a range
    uint32_t* scratch = nullptr;
    uint32_t* flag = nullptr;
    uint32_t* where = nullptr;
    unsigned long long* counts = nullptr;   // [left pairs, left rows]
    double* hist = nullptr;           // slots * bins * 2 doubles
    double* totals = nullptr;         // [sum g, sum h]
    void* temp = nullptr; size_t temp_bytes = 0;
    uint32_t stamp = 0;
    size_t used_bytes = 0;
};

template <class T> static T* dalloc(Ctx* c, size_t n, const char* what) {
    T* p = nullptr;
    size_t bytes = n * sizeof(T);
    if (bytes == 0) bytes = sizeof(T);
    cudaError_t e = cudaMalloc((void**)&p, bytes);
    if (e != cudaSuccess) {
        fprintf(stderr, "bbgpu: no %.2f GiB of device memory for %s: %s\n", bytes / 1073741824.0, what, cudaGetErrorString(e));
        abort();
    }
    c->used_bytes += bytes;
    return p;
}

// A large array of the store: device memory where it fits, else managed memory (which the card pages in over the bus).
template <class T> static T* dalloc_big(Ctx* c, size_t n, const char* what) {
    T* p = nullptr;
    size_t bytes = n * sizeof(T);
    if (bytes == 0) bytes = sizeof(T);
    if (cudaMalloc((void**)&p, bytes) == cudaSuccess) {
        c->used_bytes += bytes;
        return p;
    }
    cudaGetLastError();
    fprintf(stderr, "bbgpu: %s (%.2f GiB) does not fit in device memory; using managed memory\n", what, bytes / 1073741824.0);
    CK(cudaMallocManaged((void**)&p, bytes));
    return p;
}

template <class T> static void upload(T* to, const T* from, size_t n) {
    const size_t chunk = (size_t)256 << 20;   // bytes
    size_t done = 0, bytes = n * sizeof(T);
    while (done < bytes) {
        size_t step = bytes - done < chunk ? bytes - done : chunk;
        CK(cudaMemcpy((char*)to + done, (const char*)from + done, step, cudaMemcpyHostToDevice));
        done += step;
    }
}

static inline unsigned grid_for(uint64_t n, unsigned per_block = THREADS) {
    uint64_t g = (n + per_block - 1) / per_block;
    if (g == 0) g = 1;
    if (g > 2147483647ull) g = 2147483647ull;
    return (unsigned)g;
}

// ---------------------------------------------------------------------------------------------------------------- kernels

__global__ void k_iota(uint32_t* a, uint64_t n) {
    uint64_t i = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x;
    for (; i < n; i += (uint64_t)gridDim.x * blockDim.x) a[i] = (uint32_t)i;
}

// One thread to a group. The group's loss is -ln(sum of p over its positive ids); the gradient p - q and the Hessian p(1 - p), floored at 1e-6, are rounded to
// f32 as main.rs does and added, as f64, to the sums of the row's pair.
__global__ void k_gradient(const uint32_t* gstart, uint64_t groups, const uint32_t* row_pair, const uint8_t* label, const double* score, double* pg, double* ph, double* loss) {
    uint64_t g = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x;
    double mine = 0.0;
    if (g < groups) {
        uint32_t a = gstart[g], b = gstart[g + 1];
        double most = -INFINITY, most_positive = -INFINITY;
        for (uint32_t i = a; i < b; i++) {
            double s = score[row_pair[i]];
            if (s > most) most = s;
            if (label[i] > 0 && s > most_positive) most_positive = s;
        }
        double all = 0.0, positive = 0.0;
        for (uint32_t i = a; i < b; i++) {
            double s = score[row_pair[i]];
            all += exp(s - most);
            if (label[i] > 0) positive += exp(s - most_positive);
        }
        for (uint32_t i = a; i < b; i++) {
            uint32_t pair = row_pair[i];
            double s = score[pair];
            double p = exp(s - most) / all;
            double q = label[i] > 0 ? exp(s - most_positive) / positive : 0.0;
            float gf = (float)(p - q);
            double hv = p * (1.0 - p);
            if (!(hv >= 1e-6)) hv = 1e-6;
            float hf = (float)hv;
            atomicAdd(&pg[pair], (double)gf);
            atomicAdd(&ph[pair], (double)hf);
        }
        mine = (most + log(all)) - (most_positive + log(positive));
    }
    // One atomic for each warp.
    for (int o = 16; o > 0; o >>= 1) mine += __shfl_down_sync(0xffffffffu, mine, o);
    if ((threadIdx.x & 31) == 0) atomicAdd(loss, mine);
}

// Adds the leaf's pairs' gradient and Hessian sums to the sums of their blocks in one map, and lists each block once.
__global__ void k_block_sums(const uint32_t* items, uint64_t n, const uint32_t* pair_block, uint32_t maps, UseDev use, const double* pg, const double* ph) {
    uint64_t i = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    uint32_t p = items[i];
    uint32_t b = pair_block[(uint64_t)p * maps + use.map];
    if (b == NONE) return;
    atomicAdd(&use.sg[b], pg[p]);
    atomicAdd(&use.sh[b], ph[p]);
    if (atomicExch(&use.seen[b], 1u) == 0u) {
        uint32_t at = atomicAdd(use.count, 1u);
        use.touched[at] = b;
    }
}

// Adds each touched block's sums to the bins of its entries: a warp to a block.
__global__ void k_scatter(UseDev use, Bin* hist) {
    uint32_t count = *use.count;
    uint64_t warp = ((uint64_t)blockIdx.x * blockDim.x + threadIdx.x) >> 5;
    uint64_t warps = ((uint64_t)gridDim.x * blockDim.x) >> 5;
    int lane = threadIdx.x & 31;
    for (uint64_t w = warp; w < count; w += warps) {
        uint32_t b = use.touched[w];
        double g = use.sg[b], h = use.sh[b];
        uint64_t lo = use.ptr[b], hi = use.ptr[b + 1];
        for (uint64_t e = lo + lane; e < hi; e += 32) {
            uint32_t bin = use.bid[e];
            atomicAdd(&hist[bin].g, g);
            atomicAdd(&hist[bin].h, h);
        }
    }
}

__global__ void k_clear_blocks(UseDev use) {
    uint32_t count = *use.count;
    uint64_t i = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x;
    for (; i < count; i += (uint64_t)gridDim.x * blockDim.x) {
        uint32_t b = use.touched[i];
        use.sg[b] = 0.0;
        use.sh[b] = 0.0;
        use.seen[b] = 0u;
    }
}

__global__ void k_subtract(double* dst, const double* src, uint64_t n) {
    uint64_t i = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) dst[i] -= src[i];
}

// What the use's block b says of the split: no entry in the column, or the side its entry goes to (Store::left, SplitTest::code).
__device__ __forceinline__ uint32_t code_of(const UseDev& d, uint32_t b, const SplitArgs& s) {
    uint64_t lo = d.ptr[b], hi = d.ptr[b + 1];
    uint64_t l = lo, h = hi;
    while (l < h) {
        uint64_t m = (l + h) >> 1;
        if (d.bid[m] < s.start) l = m + 1; else h = m;
    }
    if (l < hi && d.bid[l] < s.end) {
        uint32_t bid = d.bid[l];
        bool left;
        if (s.has_nan && bid == s.end - 1) {
            left = s.default_left != 0;
        } else {
            uint32_t index = bid - s.start;
            uint32_t place = index < s.zero ? index : index + 1;
            left = place <= s.pos;
        }
        return left ? GOES_LEFT : GOES_RIGHT;
    }
    return NO_ENTRY;
}

__device__ __forceinline__ bool goes_left(const UseDev* uses, const uint32_t* pair_block, uint32_t maps, uint32_t p, const SplitArgs& s) {
    uint64_t mask = s.mask;
    while (mask != 0) {
        int u = __ffsll((long long)mask) - 1;
        mask &= mask - 1;
        const UseDev& d = uses[u];
        uint32_t b = pair_block[(uint64_t)p * maps + d.map];
        if (b == NONE) continue;
        volatile uint32_t* cell = d.memo + b;
        uint32_t seen = *cell;
        uint32_t code;
        if ((seen >> 2) == s.stamp) {
            code = seen & 3u;
        } else {
            code = code_of(d, b, s);
            *cell = (s.stamp << 2) | code;
        }
        if (code != NO_ENTRY) return code == GOES_LEFT;
    }
    return s.zero <= s.pos;
}

__global__ void k_flags(const uint32_t* items, uint64_t n, const uint32_t* pair_block, uint32_t maps, const UseDev* uses, SplitArgs s, const uint32_t* pair_start, uint32_t* flag, unsigned long long* counts) {
    uint64_t i = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x;
    unsigned long long left_pairs = 0, left_rows = 0;
    if (i < n) {
        uint32_t p = items[i];
        bool left = goes_left(uses, pair_block, maps, p, s);
        flag[i] = left ? 1u : 0u;
        if (left) {
            left_pairs = 1;
            left_rows = pair_start[p + 1] - pair_start[p];
        }
    }
    for (int o = 16; o > 0; o >>= 1) {
        left_pairs += __shfl_down_sync(0xffffffffu, left_pairs, o);
        left_rows += __shfl_down_sync(0xffffffffu, left_rows, o);
    }
    if ((threadIdx.x & 31) == 0 && left_pairs) {
        atomicAdd(&counts[0], left_pairs);
        atomicAdd(&counts[1], left_rows);
    }
}

// Stable: a left pair goes after the left pairs before it, a right pair after all left pairs and the right pairs before it.
__global__ void k_scatter_items(const uint32_t* items, uint64_t n, const uint32_t* flag, const uint32_t* where, const unsigned long long* counts, uint32_t* out) {
    uint64_t i = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    uint64_t left = counts[0];
    uint64_t to = flag[i] ? (uint64_t)where[i] : left + (i - where[i]);
    out[to] = items[i];
}

__global__ void k_add_value(const uint32_t* items, uint64_t n, double* score, double value) {
    uint64_t i = (uint64_t)blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) score[items[i]] += value;
}

// ---------------------------------------------------------------------------------------------------------------- the C interface

extern "C" {

void* bbgpu_init(int device, uint32_t kept, uint32_t bins, uint32_t num_uses, uint32_t maps, uint64_t pairs, uint64_t rows, uint64_t groups, uint32_t leaves) {
    CK(cudaSetDevice(device));
    cudaDeviceProp prop;
    CK(cudaGetDeviceProperties(&prop, device));
    size_t free_b, total_b;
    CK(cudaMemGetInfo(&free_b, &total_b));
    fprintf(stderr, "bbgpu: %s sm_%d%d, %.1f GiB free of %.1f GiB\n", prop.name, prop.major, prop.minor, free_b / 1073741824.0, total_b / 1073741824.0);
    if (num_uses > (uint32_t)MAX_USES) { fprintf(stderr, "bbgpu: %u uses\n", num_uses); abort(); }
    if (pairs >= 2147483647ull) { fprintf(stderr, "bbgpu: %llu pairs\n", (unsigned long long)pairs); abort(); }
    Ctx* c = new Ctx();
    c->kept = kept; c->bins = bins; c->num_uses = num_uses; c->maps = maps; c->pairs = pairs; c->rows = rows; c->groups = groups;
    c->slots = leaves + 3;
    c->col_start = dalloc<uint32_t>(c, kept + 1, "col_start");
    c->zero_pos = dalloc<uint32_t>(c, kept, "zero_pos");
    c->has_nan = dalloc<uint8_t>(c, kept, "has_nan");
    c->col_uses = dalloc<uint64_t>(c, kept, "col_uses");
    c->pair_block = dalloc<uint32_t>(c, pairs * maps, "pair_block");
    c->pair_start = dalloc<uint32_t>(c, pairs + 1, "pair_start");
    c->row_pair = dalloc<uint32_t>(c, rows, "row_pair");
    c->label = dalloc<uint8_t>(c, rows, "label");
    c->group_start = dalloc<uint32_t>(c, groups + 1, "group_start");
    c->pair_g = dalloc<double>(c, pairs, "pair_g");
    c->pair_h = dalloc<double>(c, pairs, "pair_h");
    c->pair_score = dalloc<double>(c, pairs, "pair_score");
    c->loss = dalloc<double>(c, 1, "loss");
    c->idx = dalloc<uint32_t>(c, pairs, "idx");
    c->scratch = dalloc<uint32_t>(c, pairs, "scratch");
    c->flag = dalloc<uint32_t>(c, pairs, "flag");
    c->where = dalloc<uint32_t>(c, pairs, "where");
    c->counts = dalloc<unsigned long long>(c, 2, "counts");
    c->hist = dalloc<double>(c, (size_t)c->slots * bins * 2, "histograms");
    c->totals = dalloc<double>(c, 2, "totals");
    // The scratch of cub's scan and sums.
    size_t a = 0, b = 0;
    CK(cub::DeviceScan::ExclusiveSum(nullptr, a, (uint32_t*)nullptr, (uint32_t*)nullptr, (int)pairs));
    CK(cub::DeviceReduce::Sum(nullptr, b, (double*)nullptr, (double*)nullptr, (int)pairs));
    c->temp_bytes = a > b ? a : b;
    c->temp = dalloc<char>(c, c->temp_bytes, "cub temp");
    CK(cudaMemset(c->pair_score, 0, pairs * sizeof(double)));
    CK(cudaMemset(c->hist, 0, (size_t)c->slots * bins * 2 * sizeof(double)));
    return c;
}

void bbgpu_set_columns(void* ctx, const uint32_t* col_start, const uint32_t* zero_pos, const uint8_t* has_nan, const uint64_t* col_uses) {
    Ctx* c = (Ctx*)ctx;
    upload(c->col_start, col_start, c->kept + 1);
    upload(c->zero_pos, zero_pos, c->kept);
    upload(c->has_nan, has_nan, c->kept);
    upload(c->col_uses, col_uses, c->kept);
    c->h_col_start.assign(col_start, col_start + c->kept + 1);
    c->h_zero_pos.assign(zero_pos, zero_pos + c->kept);
    c->h_has_nan.assign(has_nan, has_nan + c->kept);
    c->h_col_uses.assign(col_uses, col_uses + c->kept);
}

// Use u: its map, its blocks' count, the pointers into the entries (blocks + 1 of them) and the entries (bin numbers).
void bbgpu_set_use(void* ctx, uint32_t u, uint32_t map, uint64_t blocks, const uint64_t* ptr, const uint32_t* bid, uint64_t entries) {
    Ctx* c = (Ctx*)ctx;
    UseDev& d = c->uses_h[u];
    d.map = map;
    d.blocks = blocks;
    uint64_t* dptr = dalloc<uint64_t>(c, blocks + 1, "use ptr");
    upload(dptr, ptr, blocks + 1);
    uint32_t* dbid = dalloc_big<uint32_t>(c, entries, "use bid");
    upload(dbid, bid, entries);
    d.ptr = dptr;
    d.bid = dbid;
    d.memo = dalloc<uint32_t>(c, blocks, "memo");
    d.sg = dalloc<double>(c, blocks, "block sums g");
    d.sh = dalloc<double>(c, blocks, "block sums h");
    d.seen = dalloc<uint32_t>(c, blocks, "seen");
    d.touched = dalloc<uint32_t>(c, blocks, "touched");
    d.count = dalloc<uint32_t>(c, 1, "count");
    CK(cudaMemset(d.memo, 0, blocks * sizeof(uint32_t)));
    CK(cudaMemset(d.sg, 0, blocks * sizeof(double)));
    CK(cudaMemset(d.sh, 0, blocks * sizeof(double)));
    CK(cudaMemset(d.seen, 0, blocks * sizeof(uint32_t)));
    CK(cudaMemset(d.count, 0, sizeof(uint32_t)));
    if (u + 1 == c->num_uses) {
        c->uses_d = dalloc<UseDev>(c, c->num_uses, "uses");
        CK(cudaMemcpy(c->uses_d, c->uses_h, c->num_uses * sizeof(UseDev), cudaMemcpyHostToDevice));
    }
}

void bbgpu_set_pairs(void* ctx, const uint32_t* block, const uint32_t* start) {
    Ctx* c = (Ctx*)ctx;
    upload(c->pair_block, block, c->pairs * c->maps);
    upload(c->pair_start, start, c->pairs + 1);
}

void bbgpu_set_rows(void* ctx, const uint32_t* row_pair, const uint8_t* label, const uint32_t* group_start) {
    Ctx* c = (Ctx*)ctx;
    upload(c->row_pair, row_pair, c->rows);
    upload(c->label, label, c->rows);
    upload(c->group_start, group_start, c->groups + 1);
}

void bbgpu_report(void* ctx) {
    Ctx* c = (Ctx*)ctx;
    size_t free_b, total_b;
    CK(cudaMemGetInfo(&free_b, &total_b));
    fprintf(stderr, "bbgpu: %.2f GiB allocated, %.1f GiB free of %.1f GiB\n", c->used_bytes / 1073741824.0, free_b / 1073741824.0, total_b / 1073741824.0);
}

void bbgpu_score_set(void* ctx, const double* score) {
    Ctx* c = (Ctx*)ctx;
    upload(c->pair_score, score, c->pairs);
}

void bbgpu_score_get(void* ctx, double* score) {
    Ctx* c = (Ctx*)ctx;
    CK(cudaMemcpy(score, c->pair_score, c->pairs * sizeof(double), cudaMemcpyDeviceToHost));
}

void bbgpu_sync(void*) {
    CK(cudaDeviceSynchronize());
}

// The gradient and Hessian of every row, added to the sums of its pair. Gives the sum of the groups' losses.
double bbgpu_gradient(void* ctx) {
    Ctx* c = (Ctx*)ctx;
    CK(cudaMemsetAsync(c->pair_g, 0, c->pairs * sizeof(double)));
    CK(cudaMemsetAsync(c->pair_h, 0, c->pairs * sizeof(double)));
    CK(cudaMemsetAsync(c->loss, 0, sizeof(double)));
    k_gradient<<<grid_for(c->groups, 128), 128>>>(c->group_start, c->groups, c->row_pair, c->label, c->pair_score, c->pair_g, c->pair_h, c->loss);
    CK(cudaGetLastError());
    double loss = 0.0;
    CK(cudaMemcpy(&loss, c->loss, sizeof(double), cudaMemcpyDeviceToHost));
    return loss;
}

// The histogram of the pairs idx[start..start + len] into slot `slot`, which this clears first.
void bbgpu_fill(void* ctx, uint32_t slot, uint64_t start, uint64_t len) {
    Ctx* c = (Ctx*)ctx;
    Bin* hist = (Bin*)(c->hist + (size_t)slot * c->bins * 2);
    CK(cudaMemsetAsync(hist, 0, (size_t)c->bins * sizeof(Bin)));
    if (len == 0) return;
    for (uint32_t u = 0; u < c->num_uses; u++) {
        UseDev d = c->uses_h[u];
        CK(cudaMemsetAsync(d.count, 0, sizeof(uint32_t)));
        k_block_sums<<<grid_for(len), THREADS>>>(c->idx + start, len, c->pair_block, c->maps, d, c->pair_g, c->pair_h);
        k_scatter<<<4096, THREADS>>>(d, hist);
        k_clear_blocks<<<1024, THREADS>>>(d);
    }
    CK(cudaGetLastError());
}

// The pairs are in order again, over all pairs; gives the sums of all pairs' gradients and Hessians, and fills `slot`.
void bbgpu_root(void* ctx, uint32_t slot, double* out_g, double* out_h) {
    Ctx* c = (Ctx*)ctx;
    k_iota<<<grid_for(c->pairs), THREADS>>>(c->idx, c->pairs);
    size_t bytes = c->temp_bytes;
    CK(cub::DeviceReduce::Sum(c->temp, bytes, c->pair_g, c->totals, (int)c->pairs));
    bytes = c->temp_bytes;
    CK(cub::DeviceReduce::Sum(c->temp, bytes, c->pair_h, c->totals + 1, (int)c->pairs));
    bbgpu_fill(ctx, slot, 0, c->pairs);
    double t[2];
    CK(cudaMemcpy(t, c->totals, sizeof t, cudaMemcpyDeviceToHost));
    *out_g = t[0];
    *out_h = t[1];
}

// dst -= src, bin by bin.
void bbgpu_subtract(void* ctx, uint32_t dst, uint32_t src) {
    Ctx* c = (Ctx*)ctx;
    uint64_t n = (uint64_t)c->bins * 2;
    k_subtract<<<grid_for(n), THREADS>>>(c->hist + (size_t)dst * n, c->hist + (size_t)src * n, n);
    CK(cudaGetLastError());
}

void bbgpu_download(void* ctx, uint32_t slot, Bin* out) {
    Ctx* c = (Ctx*)ctx;
    CK(cudaMemcpy(out, c->hist + (size_t)slot * c->bins * 2, (size_t)c->bins * sizeof(Bin), cudaMemcpyDeviceToHost));
}

// Stably partitions idx[start..start + len] by the split. Gives, in out[0] and out[1], the count of pairs that go left and the count of rows they stand for.
void bbgpu_partition(void* ctx, uint64_t start, uint64_t len, uint32_t column, uint32_t pos, int default_left, uint64_t* out) {
    Ctx* c = (Ctx*)ctx;
    SplitArgs s;
    s.start = c->h_col_start[column];
    s.end = c->h_col_start[column + 1];
    s.zero = c->h_zero_pos[column];
    s.pos = pos;
    s.has_nan = c->h_has_nan[column] != 0;
    s.default_left = default_left;
    s.mask = c->h_col_uses[column];
    s.stamp = ++c->stamp;
    if (s.stamp >= (1u << 30)) { fprintf(stderr, "bbgpu: a memo stamp has 30 bits\n"); abort(); }
    CK(cudaMemsetAsync(c->counts, 0, 2 * sizeof(unsigned long long)));
    uint32_t* items = c->idx + start;
    k_flags<<<grid_for(len), THREADS>>>(items, len, c->pair_block, c->maps, c->uses_d, s, c->pair_start, c->flag, c->counts);
    size_t bytes = c->temp_bytes;
    CK(cub::DeviceScan::ExclusiveSum(c->temp, bytes, c->flag, c->where, (int)len));
    k_scatter_items<<<grid_for(len), THREADS>>>(items, len, c->flag, c->where, c->counts, c->scratch);
    CK(cudaMemcpyAsync(items, c->scratch, len * sizeof(uint32_t), cudaMemcpyDeviceToDevice));
    unsigned long long h[2];
    CK(cudaMemcpy(h, c->counts, sizeof h, cudaMemcpyDeviceToHost));
    out[0] = h[0];
    out[1] = h[1];
}

// Adds `value` to the score of each pair in idx[start..start + len].
void bbgpu_add_value(void* ctx, uint64_t start, uint64_t len, double value) {
    Ctx* c = (Ctx*)ctx;
    if (len == 0) return;
    k_add_value<<<grid_for(len), THREADS>>>(c->idx + start, len, c->pair_score, value);
    CK(cudaGetLastError());
}

// Puts the pairs in order, as a replay of a tree begins.
void bbgpu_reset_items(void* ctx) {
    Ctx* c = (Ctx*)ctx;
    k_iota<<<grid_for(c->pairs), THREADS>>>(c->idx, c->pairs);
    CK(cudaGetLastError());
}

}  // extern "C"

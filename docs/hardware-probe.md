# Hardware probe — dev machine

## Specs

- **Model:** MacBook Pro (Mac16,7), macOS 15.7.1
- **Chip:** Apple M4 Pro — 14 CPU cores (10P/4E), 20 GPU cores
- **Memory:** 24 GB unified LPDDR5
- **Storage:** 1 TB SSD, 694 GB free
- **Accelerator:** MPS (Metal); no CUDA

## Probe

Ran a PyTorch script under `uv run --with torch` (torch 2.11.0, Python 3.13.7) covering:

1. matmul on MPS in fp32 / fp16 / bf16 (512×512)
2. `scaled_dot_product_attention` on MPS at shape `(1, 16, 4096, 64)` fp16, timed across all four `SDPBackend` selections
3. 4096×4096 matmul throughput on CPU and MPS across dtypes
4. MPS memory allocator state after the run

## Results

### Dtype support (MPS)

| dtype | matmul |
|---|---|
| float32 | ok |
| float16 | ok |
| bfloat16 | ok |

### SDPA backend timing (MPS, fp16, S=4096)

| backend hint | ms / call |
|---|---|
| MATH | 64.59 |
| EFFICIENT_ATTENTION | 63.12 |
| FLASH_ATTENTION | 62.47 |
| CUDNN_ATTENTION | 61.17 |

All four hints land within ~3 ms; `sdpa_kernel` hint does not change the underlying kernel on MPS.

### Throughput (4096×4096 matmul)

| device / dtype | ms / iter | TFLOPS |
|---|---|---|
| cpu fp32 | 52.4 | 2.62 |
| mps fp16 | 19.4 | 7.08 |
| mps bf16 | 18.8 | 7.31 |
| mps fp32 | 21.7 | 6.34 |

CPU fp16 matmul has no fast kernel and was excluded; a 4096×4096 attempt did not complete within 18 minutes of 100% CPU.

### Memory

After the probe: `current_allocated = 0.23 GB`, `driver_allocated = 2.73 GB`.

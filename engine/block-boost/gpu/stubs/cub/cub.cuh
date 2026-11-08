#pragma once
#include <cuda_runtime.h>
namespace cub {
struct DeviceScan { template <class A, class B> static cudaError_t ExclusiveSum(void*, size_t&, A, B, int); };
struct DeviceReduce { template <class A, class B> static cudaError_t Sum(void*, size_t&, A, B, int); };
}

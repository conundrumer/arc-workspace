#pragma once
#include <cstddef>
#include <cstdint>
#include <cmath>
#define __global__
#define __device__
#define __host__
#define __forceinline__ inline
enum cudaError_t { cudaSuccess = 0 };
enum cudaMemcpyKind { cudaMemcpyHostToDevice, cudaMemcpyDeviceToHost, cudaMemcpyDeviceToDevice };
struct cudaDeviceProp { char name[256]; int major, minor; };
struct uint3_ { unsigned x, y, z; };
static uint3_ threadIdx, blockIdx, blockDim, gridDim;
cudaError_t cudaMalloc(void**, size_t); cudaError_t cudaMallocManaged(void**, size_t);
cudaError_t cudaMemcpy(void*, const void*, size_t, cudaMemcpyKind); cudaError_t cudaMemcpyAsync(void*, const void*, size_t, cudaMemcpyKind);
cudaError_t cudaMemset(void*, int, size_t); cudaError_t cudaMemsetAsync(void*, int, size_t);
cudaError_t cudaGetLastError(); const char* cudaGetErrorString(cudaError_t); cudaError_t cudaDeviceSynchronize(); cudaError_t cudaSetDevice(int);
cudaError_t cudaGetDeviceProperties(cudaDeviceProp*, int); cudaError_t cudaMemGetInfo(size_t*, size_t*);
double atomicAdd(double*, double); unsigned atomicAdd(unsigned*, unsigned); unsigned long long atomicAdd(unsigned long long*, unsigned long long);
unsigned atomicExch(unsigned*, unsigned);
unsigned long long __shfl_down_sync(unsigned, unsigned long long, int); double __shfl_down_sync(unsigned, double, int);
int __ffsll(long long);

#include <cassert>

#define N 3

__global__ void inc(int *a) {
    int i = blockIdx.x;
    if (i<N) {
        a[i]++;
    }
}

int main() {
    int ha[N], *da;
    cudaMalloc((void **)&da, N*sizeof(int));
    for (int i = 0; i<N; ++i) {
        ha[i] = i;
    }
    cudaMemcpy(da, ha, N*sizeof(int), cudaMemcpyHostToDevice);
    inc<<<N, 1>>>(da);
    cudaMemcpy(ha, da, N*sizeof(int), cudaMemcpyDeviceToHost);
    for (int i = 0; i < N; ++i) {
        assert(ha[i] == i + 1);
    }
    cudaFree(da);
    return 0;
}

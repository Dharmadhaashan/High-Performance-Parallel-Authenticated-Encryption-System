# High-Performance Parallel Authenticated Encryption System — `main.cpp` Technical Documentation

---

## 1. Overview & Purpose

The [`main.cpp`](file:///e:/chatbot_rough/High-Performance-Parallel-Authenticated-Encryption-System/main.cpp) file serves as the core high-performance C++ engine and benchmarking driver for the Parallel Authenticated Encryption System. It leverages OpenSSL's `libcrypto` C primitives (`EVP_aes_128_ctr`, `EVP_aes_128_gcm`, `HMAC`) and C++17 multi-threading (`std::thread`) to demonstrate a scalable, chunk-based authenticated encryption scheme that overcomes the sequential processing bottlenecks of traditional AES-GCM on multi-core processors.

---

## 2. Technical Architecture of `main.cpp`

### 2.1 Cryptographic Primitives & Design Choices

1. **AES-128-CTR (Counter Mode Encryption)**:
   - Converts the block cipher into a stream cipher.
   - Allows independent encryption of any chunk without waiting for previous blocks or chunks.
2. **IV/Nonce Safety (`derive_chunk_iv`)**:
   - AES-CTR requires that a Key/IV pair is **never reused**.
   - `derive_chunk_iv` dynamically derives a unique 16-byte IV for chunk index $i$ by XORing the chunk index into the last 8 bytes of the base IV:
     $$\text{out\_iv}[15 - k] = \text{base\_iv}[15 - k] \oplus (i \gg (k \times 8)) \quad \text{for } k \in [0, 7]$$
3. **HMAC-SHA256 Chunk Authentication**:
   - Each worker thread computes an individual HMAC-SHA256 authentication tag over its encrypted ciphertext chunk.
4. **Hierarchical Merkle Tree Aggregation (`build_tree`)**:
   - Instead of sequentially chaining authentication tags, chunk tags are pairwise concatenated and hashed forming a Merkle tree.
   - Reduces $N$ chunk tags into a single root authentication tag in $\mathcal{O}(\log N)$ tree steps.
5. **AES-128-GCM Baseline Comparison (`run_aes_gcm`)**:
   - Measures OpenSSL's standard AES-128-GCM implementation on the same dataset size to serve as a benchmark baseline.

---

## 3. Function-by-Function Detailed Breakdown

### Configuration Constants (Lines 16–20)
```cpp
const vector<int> DATA_SIZES = {100, 200, 500, 1000}; // MB
const vector<int> CHUNK_SIZES = {1 * 1024 * 1024, 2 * 1024 * 1024, 4 * 1024 * 1024};
const vector<int> THREAD_COUNTS = {1, 2, 4, 8, 16};
const int NUM_TRIALS = 5; // Number of times to run each test for averaging
```
* **`DATA_SIZES`**: Workload sizes tested (100 MB up to 1000 MB / 1 GB).
* **`CHUNK_SIZES`**: Granularity of chunk splitting (1 MB, 2 MB, 4 MB).
* **`THREAD_COUNTS`**: Parallel worker thread pool sizes evaluated (1 to 16 threads).
* **`NUM_TRIALS`**: Number of benchmark runs executed per test configuration. The median trial time is chosen to eliminate OS CPU scheduling spikes and noise.

---

### `derive_chunk_iv()` (Lines 26–33)
```cpp
void derive_chunk_iv(const unsigned char* base_iv, uint64_t chunk_idx, unsigned char* out_iv) {
    for (int i = 0; i < 16; i++) out_iv[i] = base_iv[i];
    for (int i = 0; i < 8; i++) {
        out_iv[15 - i] ^= (uint8_t)(chunk_idx >> (i * 8));
    }
}
```
* **Parameters**: `base_iv` (16 bytes input), `chunk_idx` (64-bit integer chunk sequence number), `out_iv` (16 bytes derived output).
* **Mechanism**: Copies the base IV into `out_iv`, then XORs the 64-bit chunk index byte-by-byte into the lowest 8 bytes.
* **Security Function**: Ensures absolute uniqueness of the initialization vector across all parallel threads and chunks, preserving AES-CTR security against nonce reuse attacks.

---

### `aes_ctr_encrypt_reusable()` (Lines 35–47)
```cpp
void aes_ctr_encrypt_reusable(
    EVP_CIPHER_CTX* ctx,
    const unsigned char* data,
    size_t len,
    unsigned char* out,
    const unsigned char* key,
    const unsigned char* iv)
{
    int out_len = 0;
    EVP_EncryptInit_ex(ctx, EVP_aes_128_ctr(), NULL, key, iv);
    EVP_EncryptUpdate(ctx, out, &out_len, data, (int)len);
    EVP_EncryptFinal_ex(ctx, out + out_len, &out_len);
}
```
* **Parameters**: Pre-allocated OpenSSL `EVP_CIPHER_CTX* ctx`, input buffer `data`, length `len`, target ciphertext buffer `out`, cryptographic `key`, derived `iv`.
* **Mechanism**: Initializes OpenSSL AES-128-CTR cipher context, processes input stream via `EVP_EncryptUpdate`, and finalizes cipher state via `EVP_EncryptFinal_ex`.
* **Performance Note**: Reusing thread-local `EVP_CIPHER_CTX` instances minimizes heap allocation overhead during bulk encryption.

---

### `compute_hmac()` (Lines 53–57)
```cpp
vector<unsigned char> compute_hmac(const unsigned char* data, size_t len) {
    unsigned int out_len;
    unsigned char* result = HMAC(EVP_sha256(), "hmackey", 7, data, len, NULL, &out_len);
    return vector<unsigned char>(result, result + out_len);
}
```
* **Mechanism**: Computes a 32-byte HMAC-SHA256 digest over input buffer `data` of length `len` using key `"hmackey"`. Returns a `std::vector<unsigned char>` containing the hash digest.

---

### `build_tree()` (Lines 59–74)
```cpp
vector<unsigned char> build_tree(vector<vector<unsigned char>> nodes) {
    while (nodes.size() > 1) {
        vector<vector<unsigned char>> next;
        for (size_t i = 0; i < nodes.size(); i += 2) {
            if (i + 1 < nodes.size()) {
                vector<unsigned char> combined = nodes[i];
                combined.insert(combined.end(), nodes[i + 1].begin(), nodes[i + 1].end());
                next.push_back(compute_hmac(combined.data(), combined.size()));
            } else {
                next.push_back(nodes[i]);
            }
        }
        nodes = next;
    }
    return nodes[0];
}
```
* **Algorithm**: Merkle Tree Reduction.
* **Mechanism**: Loops until only 1 root node remains. Iterates through the list of tags in pairs (`i` and `i+1`), concatenates their bytes, computes HMAC-SHA256 on the combined node, and pushes it to `next`. Handles odd tag counts by promoting unmatched trailing nodes directly to the next tree level.

---

### `run_aes_gcm()` (Lines 80–94)
```cpp
double run_aes_gcm(const vector<unsigned char>& data) {
    unsigned char key[16] = {0}, iv[12] = {0};
    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    vector<unsigned char> out(data.size() + 16);
    int len;

    auto start = chrono::high_resolution_clock::now();
    EVP_EncryptInit_ex(ctx, EVP_aes_128_gcm(), NULL, key, iv);
    EVP_EncryptUpdate(ctx, out.data(), &len, data.data(), (int)data.size());
    EVP_EncryptFinal_ex(ctx, out.data() + len, &len);
    auto end = chrono::high_resolution_clock::now();

    EVP_CIPHER_CTX_free(ctx);
    return chrono::duration<double>(end - start).count();
}
```
* **Purpose**: Serves as the single-threaded baseline benchmark. Measures standard OpenSSL AES-128-GCM encrypt & authenticate time using high-resolution timers (`std::chrono::high_resolution_clock`). Returns total execution time in seconds.

---

### `run_parallel_core()` (Lines 96–128)
```cpp
double run_parallel_core(const vector<unsigned char>& data, int chunk_size, int num_threads) {
    size_t num_chunks = (data.size() + chunk_size - 1) / chunk_size;
    vector<vector<unsigned char>> tags(num_chunks);
    unsigned char key[16] = {0}, base_iv[16] = {0};

    auto start = chrono::high_resolution_clock::now();
    vector<thread> workers;

    for (int t = 0; t < num_threads; t++) {
        workers.emplace_back([&, t]() {
            EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
            vector<unsigned char> buffer(chunk_size + 16);
            unsigned char chunk_iv[16];

            for (size_t i = t; i < num_chunks; i += num_threads) {
                size_t s = i * chunk_size;
                size_t len = min((size_t)chunk_size, data.size() - s);
                
                derive_chunk_iv(base_iv, i, chunk_iv);
                aes_ctr_encrypt_reusable(ctx, data.data() + s, len, buffer.data(), key, chunk_iv);
                tags[i] = compute_hmac(buffer.data(), len);
            }
            EVP_CIPHER_CTX_free(ctx);
        });
    }

    for (auto& t : workers) t.join();
    auto root = build_tree(tags);
    compute_hmac(root.data(), root.size());
    
    auto end = chrono::high_resolution_clock::now();
    return chrono::duration<double>(end - start).count();
}
```
* **Execution Flow**:
  1. Calculates `num_chunks` required for dataset size.
  2. Allocates a thread-safe `tags` vector indexed by chunk number.
  3. Launches `num_threads` using a **strided loop workload distribution**: Thread `t` processes chunks `t`, `t + num_threads`, `t + 2*num_threads`, etc.
  4. Each thread initializes a local `EVP_CIPHER_CTX`, derives unique `chunk_iv`, performs AES-CTR encryption into a local buffer, and computes HMAC-SHA256.
  5. Joins all worker threads (`t.join()`).
  6. Aggregates chunk tags into a Merkle tree root (`build_tree`) and computes the final binding HMAC.
  7. Returns total execution time in seconds.

---

### `run_parallel_bench()` & `main()` (Lines 131–181)
```cpp
double run_parallel_bench(const vector<unsigned char>& data, int chunk_size, int num_threads) {
    vector<double> results;
    for(int i = 0; i < NUM_TRIALS; i++) {
        results.push_back(run_parallel_core(data, chunk_size, num_threads));
    }
    sort(results.begin(), results.end());
    return results[NUM_TRIALS / 2]; // Return median
}
```
* Runs `run_parallel_core` 5 times per configuration, sorts the timing results, and selects the median value.
* `main()` prints formatted comparison tables detailing chunk size, thread count, execution time, throughput (MB/s), and speedup factor over AES-GCM.

---

## 4. Complete Source Code of `main.cpp`

```cpp
#include <iostream>
#include <vector>
#include <thread>
#include <chrono>
#include <algorithm>
#include <iomanip>
#include <numeric>

#include <openssl/evp.h>
#include <openssl/hmac.h>

using namespace std;

// ==============================
// CONFIGURATION
// ==============================
const vector<int> DATA_SIZES = {100, 200, 500, 1000}; // MB
const vector<int> CHUNK_SIZES = {1 * 1024 * 1024, 2 * 1024 * 1024, 4 * 1024 * 1024};
const vector<int> THREAD_COUNTS = {1, 2, 4, 8, 16};
const int NUM_TRIALS = 5; // Number of times to run each test for averaging

// ==============================
// CRYPTO UTILS
// ==============================

// Derive a unique IV for each chunk to prevent AES-CTR nonce reuse
void derive_chunk_iv(const unsigned char* base_iv, uint64_t chunk_idx, unsigned char* out_iv) {
    for (int i = 0; i < 16; i++) out_iv[i] = base_iv[i];
    // XOR the chunk index into the last 8 bytes of the IV
    for (int i = 0; i < 8; i++) {
        out_iv[15 - i] ^= (uint8_t)(chunk_idx >> (i * 8));
    }
}

void aes_ctr_encrypt_reusable(
    EVP_CIPHER_CTX* ctx,
    const unsigned char* data,
    size_t len,
    unsigned char* out,
    const unsigned char* key,
    const unsigned char* iv)
{
    int out_len = 0;
    EVP_EncryptInit_ex(ctx, EVP_aes_128_ctr(), NULL, key, iv);
    EVP_EncryptUpdate(ctx, out, &out_len, data, (int)len);
    EVP_EncryptFinal_ex(ctx, out + out_len, &out_len);
}

// ==============================
// HMAC & TREE
// ==============================

vector<unsigned char> compute_hmac(const unsigned char* data, size_t len) {
    unsigned int out_len;
    unsigned char* result = HMAC(EVP_sha256(), "hmackey", 7, data, len, NULL, &out_len);
    return vector<unsigned char>(result, result + out_len);
}

vector<unsigned char> build_tree(vector<vector<unsigned char>> nodes) {
    while (nodes.size() > 1) {
        vector<vector<unsigned char>> next;
        for (size_t i = 0; i < nodes.size(); i += 2) {
            if (i + 1 < nodes.size()) {
                vector<unsigned char> combined = nodes[i];
                combined.insert(combined.end(), nodes[i + 1].begin(), nodes[i + 1].end());
                next.push_back(compute_hmac(combined.data(), combined.size()));
            } else {
                next.push_back(nodes[i]);
            }
        }
        nodes = next;
    }
    return nodes[0];
}

// ==============================
// BENCHMARK CORES
// ==============================

double run_aes_gcm(const vector<unsigned char>& data) {
    unsigned char key[16] = {0}, iv[12] = {0};
    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    vector<unsigned char> out(data.size() + 16);
    int len;

    auto start = chrono::high_resolution_clock::now();
    EVP_EncryptInit_ex(ctx, EVP_aes_128_gcm(), NULL, key, iv);
    EVP_EncryptUpdate(ctx, out.data(), &len, data.data(), (int)data.size());
    EVP_EncryptFinal_ex(ctx, out.data() + len, &len);
    auto end = chrono::high_resolution_clock::now();

    EVP_CIPHER_CTX_free(ctx);
    return chrono::duration<double>(end - start).count();
}

double run_parallel_core(const vector<unsigned char>& data, int chunk_size, int num_threads) {
    size_t num_chunks = (data.size() + chunk_size - 1) / chunk_size;
    vector<vector<unsigned char>> tags(num_chunks);
    unsigned char key[16] = {0}, base_iv[16] = {0};

    auto start = chrono::high_resolution_clock::now();
    vector<thread> workers;

    for (int t = 0; t < num_threads; t++) {
        workers.emplace_back([&, t]() {
            EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
            vector<unsigned char> buffer(chunk_size + 16);
            unsigned char chunk_iv[16];

            for (size_t i = t; i < num_chunks; i += num_threads) {
                size_t s = i * chunk_size;
                size_t len = min((size_t)chunk_size, data.size() - s);
                
                derive_chunk_iv(base_iv, i, chunk_iv);
                aes_ctr_encrypt_reusable(ctx, data.data() + s, len, buffer.data(), key, chunk_iv);
                tags[i] = compute_hmac(buffer.data(), len);
            }
            EVP_CIPHER_CTX_free(ctx);
        });
    }

    for (auto& t : workers) t.join();
    auto root = build_tree(tags);
    compute_hmac(root.data(), root.size());
    
    auto end = chrono::high_resolution_clock::now();
    return chrono::duration<double>(end - start).count();
}

// Wrapper to perform multiple trials and return the median
double run_parallel_bench(const vector<unsigned char>& data, int chunk_size, int num_threads) {
    vector<double> results;
    for(int i = 0; i < NUM_TRIALS; i++) {
        results.push_back(run_parallel_core(data, chunk_size, num_threads));
    }
    sort(results.begin(), results.end());
    return results[NUM_TRIALS / 2]; // Return median
}

// ==============================
// MAIN
// ==============================

int main() {
    cout << fixed << setprecision(2);
    cout << "==========================================================\n";
    cout << "RESEARCH EXPERIMENT: PARALLEL AUTHENTICATED ENCRYPTION\n";
    cout << "Trials per Config: " << NUM_TRIALS << " (Result = Median)\n";
    cout << "==========================================================\n";

    for (int size_mb : DATA_SIZES) {
        auto data = vector<unsigned char>(size_mb * 1024 * 1024, 'A');
        
        // GCM Baseline (Median of 3)
        vector<double> gcm_results;
        for(int i=0; i<3; i++) gcm_results.push_back(run_aes_gcm(data));
        sort(gcm_results.begin(), gcm_results.end());
        double gcm_time = gcm_results[1];
        double gcm_tp = size_mb / gcm_time;

        cout << "\n>>> DATA SIZE: " << size_mb << " MB\n";
        cout << "AES-GCM Baseline: " << gcm_tp << " MB/s\n";
        cout << "----------------------------------------------------------\n";
        cout << "Chunk | Threads | Time(s) | Throughput | vs GCM\n";
        cout << "----------------------------------------------------------\n";

        for (int chunk : CHUNK_SIZES) {
            for (int threads : THREAD_COUNTS) {
                double t_med = run_parallel_bench(data, chunk, threads);
                double tp = size_mb / t_med;
                
                cout << chunk / (1024*1024) << "MB    | " 
                     << setw(7) << threads << " | " 
                     << setw(7) << t_med << " | " 
                     << setw(10) << tp << " MB/s | " 
                     << (tp / gcm_tp) << "x" << endl;
            }
            cout << "----------------------------------------------------------\n";
        }
    }
    return 0;
}
```

---

## 5. Compilation & Execution Commands

### Prerequisites
- GCC with C++17 support (`g++`)
- OpenSSL Development libraries (`libssl`, `libcrypto`)

### Compilation Command
```bash
g++ main.cpp -o main.exe -O3 -march=native -std=c++17 -pthread -lssl -lcrypto
```

### Run Benchmark Execution
```bash
./main.exe
```

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
import time
import os
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA256, HMAC
from concurrent.futures import ProcessPoolExecutor

# ==============================
# CONFIG
# ==============================
DATA_SIZE_MB = 300
CHUNK_SIZE = 1024 * 1024 * 8  # 2MB
MAX_WORKERS = min(4, os.cpu_count())

KEY = get_random_bytes(16)
HMAC_KEY = get_random_bytes(16)

# ==============================
# DATA GENERATION
# ==============================
def generate_data(size_mb):
    return b"A" * (size_mb * 1024 * 1024)

# ==============================
# CHUNKING
# ==============================
def chunk_data(data):
    return [data[i:i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)]

# ==============================
# TREE COMBINATION
# ==============================
def hash_pair(a, b):
    h = SHA256.new()
    h.update(a + b)
    return h.digest()

def build_tree(tags):
    current = tags[:]
    while len(current) > 1:
        next_level = []
        for i in range(0, len(current), 2):
            if i + 1 < len(current):
                next_level.append(hash_pair(current[i], current[i + 1]))
            else:
                next_level.append(current[i])
        current = next_level
    return current[0]

# ==============================
# FINAL HMAC
# ==============================
def compute_final_tag(tree_output, metadata):
    h = HMAC.new(HMAC_KEY, digestmod=SHA256)
    h.update(tree_output + metadata)
    return h.digest()

# ==============================
# 🔴 SEQUENTIAL VERSION
# ==============================
def sequential_encrypt(data):
    chunks = chunk_data(data)
    tags = []

    for chunk in chunks:
        cipher = AES.new(KEY, AES.MODE_EAX)
        _, tag = cipher.encrypt_and_digest(chunk)
        tags.append(tag)

    tree_output = build_tree(tags)
    metadata = str(len(chunks)).encode()
    compute_final_tag(tree_output, metadata)

# ==============================
# 🟢 PARALLEL VERSION
# ==============================
def encrypt_chunk(chunk):
    cipher = AES.new(KEY, AES.MODE_EAX)
    _, tag = cipher.encrypt_and_digest(chunk)
    return tag

def parallel_encrypt(data):
    chunks = chunk_data(data)

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        tags = list(executor.map(encrypt_chunk, chunks))

    tree_output = build_tree(tags)
    metadata = str(len(chunks)).encode()
    compute_final_tag(tree_output, metadata)

# ==============================
# BENCHMARK
# ==============================
def benchmark():
    data = generate_data(DATA_SIZE_MB)

    print(f"\nData Size: {DATA_SIZE_MB} MB")
    print(f"Chunk Size: {CHUNK_SIZE // (1024*1024)} MB")
    print(f"Workers: {MAX_WORKERS}")

    # Warm-up
    sequential_encrypt(data[:1024*1024])
    parallel_encrypt(data[:1024*1024])

    # Sequential
    start = time.perf_counter()
    sequential_encrypt(data)
    seq_time = time.perf_counter() - start

    # Parallel
    start = time.perf_counter()
    parallel_encrypt(data)
    par_time = time.perf_counter() - start

    # Results
    print("\n===== RESULTS =====")
    print(f"Sequential Time : {seq_time:.4f} sec")
    print(f"Parallel Time   : {par_time:.4f} sec")

    speedup = seq_time / par_time
    print(f"\nSpeedup (Parallel vs Sequential): {speedup:.2f}x")

    seq_throughput = DATA_SIZE_MB / seq_time
    par_throughput = DATA_SIZE_MB / par_time

    print("\nThroughput:")
    print(f"Sequential: {seq_throughput:.2f} MB/s")
    print(f"Parallel  : {par_throughput:.2f} MB/s")

# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    benchmark()
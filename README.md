# Parallel Authenticated Encryption System

## Overview

This project presents a **chunk-based parallel authenticated encryption framework** designed to improve the performance of secure data processing on multi-core systems. The system combines **AES-CTR encryption**, **HMAC-SHA256 authentication**, and **tree-based integrity aggregation** to eliminate authentication bottlenecks commonly found in traditional authenticated encryption schemes such as AES-GCM.

The framework processes data in parallel by dividing it into chunks, encrypting and authenticating each chunk independently, and securely combining authentication tags using a tree-based structure. Experimental results demonstrate significant throughput improvements for large datasets.

---

## Motivation

Modern applications such as cloud storage, secure databases, distributed systems, and large-scale data processing require both:

- Data Confidentiality
- Data Integrity and Authenticity

Although AES-GCM is widely adopted for authenticated encryption, its authentication phase introduces sequential dependencies that limit scalability on multi-core architectures.

This project explores a parallel approach to authenticated encryption that improves throughput while maintaining strong integrity guarantees.

---

## Key Features

- Chunk-based data processing
- Parallel AES-CTR encryption
- HMAC-SHA256 based authentication
- Tree-based authentication tag aggregation
- Multi-threaded execution
- AES-GCM baseline comparison
- Scalability analysis across different data sizes and thread counts

---

## System Architecture

```text
Input Data
    |
    v
+----------------+
| Data Chunking  |
+----------------+
    |
    v
+----------------+
| AES-CTR        |
| Encryption     |
+----------------+
    |
    v
+----------------+
| HMAC-SHA256    |
| Authentication |
+----------------+
    |
    v
+----------------+
| Tree-Based     |
| Aggregation    |
+----------------+
    |
    v
+----------------+
| Final HMAC     |
+----------------+
    |
    v
 Final Authentication Tag
```

---

## Technologies Used

### Language
- C++

### Cryptography
- OpenSSL
- AES-128-CTR
- HMAC-SHA256

### System Programming
- Multithreading
- Parallel Computing
- Concurrent Processing

---

## Experimental Setup

### Data Sizes Tested

- 100 MB
- 200 MB
- 500 MB
- 1000 MB (1 GB)

### Chunk Sizes Tested

- 1 MB
- 2 MB
- 4 MB

### Thread Configurations

- 1 Thread
- 2 Threads
- 4 Threads
- 8 Threads
- 16 Threads

---

## Performance Metrics

The following metrics were evaluated:

- Execution Time
- Throughput (MB/s)
- Speedup
- Scalability
- Improvement over AES-GCM

---

## Results Summary

### Best Observed Result

| Metric | Value |
|----------|----------|
| Dataset Size | 1 GB |
| Chunk Size | 1 MB |
| Threads | 16 |
| Throughput Improvement | Up to 7× over AES-GCM |

### Key Findings

- Smaller chunk sizes achieved better parallel efficiency.
- Throughput increased with thread count.
- The proposed system outperformed AES-GCM for large workloads.
- Tree-based aggregation effectively removed authentication bottlenecks.

---

## Building the Project

### Prerequisites

Install:

- MSYS2 MinGW64
- OpenSSL

### Install OpenSSL

```bash
pacman -S mingw-w64-x86_64-openssl
```

### Compile

```bash
g++ main.cpp -o main.exe -O3 -march=native -std=c++17 -pthread -lssl -lcrypto
```

### Run

```bash
./main.exe
```

---

## Sample Output

```text
===== FINAL RESEARCH EXPERIMENT =====

DATA SIZE: 100 MB

AES-GCM Throughput: 2512 MB/s

Chunk Size: 1 MB
Threads: 16
Throughput: 4000 MB/s
Improvement vs AES-GCM: 1.59x
```

---

## Project Structure

```text
crypto_project/
│
├── main.cpp
├── README.md
└── results/
```

---

## Applications

- Secure Cloud Storage
- Large Scale Data Processing
- Distributed Computing Systems
- Secure Databases
- High-Performance Cryptographic Systems
- Enterprise Data Security

---

## Future Enhancements

- GPU-based acceleration using CUDA
- Adaptive chunk sizing
- Dynamic load balancing
- Integration with standard AEAD constructions
- SIMD optimization
- Formal security analysis

---

## Research Contribution

This work proposes a practical chunk-based authenticated encryption architecture that leverages multi-core processors to improve secure data processing performance. By combining parallel encryption, chunk-level authentication, and tree-based integrity verification, the framework demonstrates significant throughput improvements compared to conventional AES-GCM implementations.

---

## Author

Dharmadhaashan P

Project Domain:
**Applied Cryptography | Parallel Computing | Secure Systems**

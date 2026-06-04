import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Data extracted from your latest experiment results
data = {
    "Data Size (MB)": [100]*15 + [200]*15 + [500]*15 + [1000]*15,
    "Chunk Size": ["1MB", "1MB", "1MB", "1MB", "1MB", "2MB", "2MB", "2MB", "2MB", "2MB", "4MB", "4MB", "4MB", "4MB", "4MB"] * 4,
    "Threads": [1, 2, 4, 8, 16] * 12,
    "Throughput (MB/s)": [
        # 100MB
        1569.74, 3177.97, 5544.07, 8914.64, 8353.31, # 1MB Chunk
        1617.88, 2934.38, 5129.81, 6348.76, 4524.31, # 2MB Chunk
        1531.68, 2967.02, 4582.09, 4182.75, 3348.46, # 4MB Chunk
        # 200MB
        1655.13, 3238.61, 5912.91, 9747.54, 9789.24,
        1700.51, 3081.15, 5840.01, 8851.40, 6621.40,
        1657.21, 2974.66, 4475.76, 4902.66, 4040.53,
        # 500MB
        1647.09, 3320.33, 6056.22, 8998.18, 10280.83,
        1654.32, 3333.97, 6158.01, 9629.50, 6089.51,
        1710.90, 3283.51, 5782.42, 5011.06, 4170.47,
        # 1000MB
        1666.87, 3242.92, 6262.70, 10744.52, 11116.13,
        1627.15, 3309.74, 5829.12, 9281.13, 6925.81,
        1660.39, 3315.38, 5840.57, 4461.85, 4565.23
    ]
}

baselines = {100: 3803.79, 200: 5885.50, 500: 4910.08, 1000: 3692.39}
df = pd.DataFrame(data)

# --- CHART 1: Scaling Analysis (Line Plots) ---
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
axes = axes.flatten()
data_sizes = [100, 200, 500, 1000]

for i, size in enumerate(data_sizes):
    ax = axes[i]
    subset = df[df["Data Size (MB)"] == size]
    for chunk in subset["Chunk Size"].unique():
        chunk_data = subset[subset["Chunk Size"] == chunk]
        ax.plot(chunk_data["Threads"], chunk_data["Throughput (MB/s)"], marker='o', label=f"Chunk: {chunk}")
    ax.axhline(y=baselines[size], color='r', linestyle='--', label=f"AES-GCM Baseline")
    ax.set_title(f"Performance for {size} MB Data")
    ax.set_xlabel("Number of Threads")
    ax.set_ylabel("Throughput (MB/s)")
    ax.legend()
    ax.grid(True, linestyle=':', alpha=0.6)

plt.tight_layout()
plt.savefig("performance_analysis.png")

# --- CHART 2: Peak Comparison (Bar Chart) ---
peak_performance = []
for size in data_sizes:
    peak_row = df[df["Data Size (MB)"] == size]["Throughput (MB/s)"].max()
    peak_performance.append({"Size": f"{size}MB", "Type": "Proposed (Peak)", "Throughput": peak_row})
    peak_performance.append({"Size": f"{size}MB", "Type": "AES-GCM", "Throughput": baselines[size]})

plt.figure(figsize=(10, 6))
sns.barplot(x="Size", y="Throughput", hue="Type", data=pd.DataFrame(peak_performance))
plt.title("Peak Throughput Comparison")
plt.ylabel("Throughput (MB/s)")
plt.savefig("peak_comparison.png")
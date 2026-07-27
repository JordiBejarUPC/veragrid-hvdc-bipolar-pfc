import glob
import pandas as pd

# Find all chunk files
files = sorted(glob.glob("results_chunk_*.parquet"))

print(f"Found {len(files)} chunk files. Merging...")
df_all = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

# Save the final consolidated dataset
df_all.to_parquet("all_contingency_results.parquet")
print("All results consolidated into 'all_contingency_results.parquet'!")

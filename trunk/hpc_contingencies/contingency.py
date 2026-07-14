import os
import sys
import pandas as pd
import numpy as np


def run_calculation(contingency_id):
    """
    Your actual simulation/calculation goes here.
    This is a mock implementation returning dummy results.
    """
    return {
        "contingency_id": contingency_id,
        "result_value": np.random.random(),
        "status": "SUCCESS"
    }


def main():
    # Retrieve the unique task index assigned by Slurm
    task_id = int(os.environ.get("SLURM_ARRAY_TASK_ID", 0))

    # Total workload configuration
    total_contingencies = 56000
    num_chunks = 100
    chunk_size = total_contingencies // num_chunks  # 560 contingencies per task

    # Calculate the range boundaries for this specific task
    start_idx = task_id * chunk_size
    end_idx = start_idx + chunk_size

    chunk_results = []
    print(f"Task ID {task_id}: Processing range {start_idx} to {end_idx}...")

    for i in range(start_idx, end_idx):
        result = run_calculation(i)
        chunk_results.append(result)

    # Convert to DataFrame and save as a compressed Parquet file
    # Parquet is highly optimized for size and reading speed compared to CSV
    df = pd.DataFrame(chunk_results)
    output_filename = f"results_chunk_{task_id}.parquet"
    df.to_parquet(output_filename)

    print(f"Task ID {task_id}: Saved chunk successfully to {output_filename}")


if __name__ == "__main__":
    main()

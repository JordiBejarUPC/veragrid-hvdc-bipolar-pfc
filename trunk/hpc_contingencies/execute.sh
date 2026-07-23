#!/bin/bash
#SBATCH --job-name=contingency_sim
#SBATCH --output=logs/array_%A_%a.out
#SBATCH --error=logs/array_%A_%a.err
#SBATCH --array=0-99%20               # Launches 100 tasks (IDs 0-99), max 20 running at once
#SBATCH --nodes=1                     # 1 node per task
#SBATCH --ntasks=1                    # 1 process per task
#SBATCH --cpus-per-task=1             # Adjust if your calculation uses multithreading
#SBATCH --mem=2G                      # Memory allocation per task
#SBATCH --time=02:00:00               # Walltime limit for each task

# Run the python script. Slurm automatically injects $SLURM_ARRAY_TASK_ID into the environment.
python contingency_processor.py

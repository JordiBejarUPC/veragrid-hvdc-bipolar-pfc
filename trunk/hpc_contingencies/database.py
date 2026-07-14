import os
import sqlite3
import time
import numpy as np

DB_FILE = "contingency_results.db"


def initialize_database():
    """Run this once before launching jobs to create the table structure."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS results
                      (
                          contingency_id
                          INTEGER
                          PRIMARY
                          KEY,
                          result_value
                          REAL,
                          status
                          TEXT
                      )''')
    conn.commit()
    conn.close()


def save_result_safely(contingency_id, result_value, status):
    # Set a 30-second timeout so the process waits patiently if the database is busy
    conn = sqlite3.connect(DB_FILE, timeout=30.0)

    # Enable WAL mode for significantly better concurrent write handling
    conn.execute('PRAGMA journal_mode=WAL;')

    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO results (contingency_id, result_value, status) VALUES (?, ?, ?)",
            (contingency_id, result_value, status)
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        # In case of extreme lock contention, wait a randomized split-second and retry once
        time.sleep(np.random.uniform(0.1, 0.5))
        cursor.execute(
            "INSERT OR REPLACE INTO results (contingency_id, result_value, status) VALUES (?, ?, ?)",
            (contingency_id, result_value, status)
        )
        conn.commit()
    finally:
        conn.close()

# Example usage within your main loop:
# result = run_calculation(i)
# save_result_safely(i, result["result_value"], result["status"])

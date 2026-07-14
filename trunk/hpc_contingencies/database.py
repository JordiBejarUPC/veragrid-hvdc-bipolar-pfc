import os
import sqlite3
import time
import numpy as np

DB_FILE = "contingency_results.db"

def initialize_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contingency_results
        (
            execution_id INTEGER,
            contingency_id INTEGER,
            result_value REAL,
            status TEXT,
            PRIMARY KEY (execution_id, contingency_id)
        )
    ''')
    conn.commit()
    conn.close()


def save_result(exec_id, contingency_id, result_value, status):
    initialize_database()

    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL;')

    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO contingency_results (execution_id, contingency_id, result_value, status) VALUES (?, ?, ?, ?)",
            (exec_id, contingency_id, result_value, status)
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        time.sleep(np.random.uniform(0.1, 0.5))
        cursor.execute(
            "INSERT OR REPLACE INTO contingency_results (execution_id, contingency_id, result_value, status) VALUES (?, ?, ?, ?)",
            (exec_id, contingency_id, result_value, status)
        )
        conn.commit()
    finally:
        conn.close()


def cleanup_database():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE);')
    conn.close()


if __name__ == '__main__':
    execution_id = os.getpid()
    save_result(execution_id, 123, 0.456, "SUCCESS")
    cleanup_database()
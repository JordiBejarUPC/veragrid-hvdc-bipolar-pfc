# Dependencies: pip install orjson msgspec zipfile-deflate64
import zipfile
import zipfile_deflate64
import time
import json
import orjson
import msgspec
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed


# --- JSON DECODERS ---
def decode_json(raw_bytes: bytes):
    return json.loads(raw_bytes.decode('utf-8'))


def decode_orjson(raw_bytes: bytes):
    return orjson.loads(raw_bytes)


def decode_msgspec(raw_bytes: bytes):
    return msgspec.json.decode(raw_bytes)


JSON_PARSERS = {
    "json": decode_json,
    "orjson": decode_orjson,
    "msgspec": decode_msgspec,
}

ZIP_MODULES = {
    "zipfile (std)": zipfile,
    "zipfile_deflate64": zipfile_deflate64,
}


# --- WORKER FUNCTION FOR PROCESS POOL ---
def parse_process_worker(zip_path: str, filename: str, parser_key: str, use_deflate64: bool) -> dict:
    mod = zipfile_deflate64 if use_deflate64 else zipfile
    parser = JSON_PARSERS[parser_key]
    with mod.ZipFile(zip_path, 'r') as z:
        return parser(z.read(filename))


# --- RUNNER STRATEGIES ---

# 1. Single-Threaded Sequential
def run_single_thread_benchmark(zip_mod, zip_path: str, filenames: list[str], parser_key: str) -> float:
    start_time = time.perf_counter()
    parser = JSON_PARSERS[parser_key]

    with zip_mod.ZipFile(zip_path, 'r') as z:
        results = [parser(z.read(name)) for name in filenames]

    return time.perf_counter() - start_time


# 2. Multi-Threaded Concurrent Read + Parse
def run_thread_benchmark(zip_mod, zip_path: str, filenames: list[str], parser_key: str) -> float:
    start_time = time.perf_counter()
    parser = JSON_PARSERS[parser_key]

    def _worker(filename: str):
        with zip_mod.ZipFile(zip_path, 'r') as z:
            return parser(z.read(filename))

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(_worker, name) for name in filenames]
        _ = [f.result() for f in as_completed(futures)]

    return time.perf_counter() - start_time


# 3. Two-Phase: Sequential Zip Read -> Multi-Threaded Parse (Eliminates File Handle Locks)
def run_twophase_thread_benchmark(zip_mod, zip_path: str, filenames: list[str], parser_key: str) -> float:
    start_time = time.perf_counter()
    parser = JSON_PARSERS[parser_key]

    # Phase 1: Read raw compressed bytes sequentially into RAM
    raw_file_bytes = []
    with zip_mod.ZipFile(zip_path, 'r') as z:
        for name in filenames:
            raw_file_bytes.append(z.read(name))

    # Phase 2: Parse raw bytes across threads (orjson/msgspec drop the GIL)
    with ThreadPoolExecutor() as executor:
        _ = list(executor.map(parser, raw_file_bytes))

    return time.perf_counter() - start_time


# 4. Multi-Process Execution (ProcessPool)
def run_process_benchmark(use_deflate64: bool, zip_path: str, filenames: list[str], parser_key: str) -> float:
    start_time = time.perf_counter()

    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(parse_process_worker, zip_path, name, parser_key, use_deflate64)
            for name in filenames
        ]
        _ = [f.result() for f in as_completed(futures)]

    return time.perf_counter() - start_time


if __name__ == "__main__":
    # zip_path = "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/GB Network.gridcal"
    zip_path = "/home/santi/Escritorio/future_model.veragrid"

    with zipfile.ZipFile(zip_path, 'r') as z:
        json_files = [f for f in z.namelist() if f.endswith('.model')]

    print(f"Benchmarking {len(json_files)} files in '{zip_path}' across Execution Strategies...\n")

    baseline_time = None
    results = []


    def record_result(label: str, elapsed: float):
        global baseline_time
        if baseline_time is None:
            baseline_time = elapsed  # Baseline is Single-Threaded + zipfile (std) + json
        speedup = baseline_time / elapsed
        results.append((label, elapsed, speedup))
        print(f"[{label:<50}] {elapsed:.3f}s | {speedup:.2f}x baseline")


    # --- EXECUTION MATRIX ---

    # A. Single-Threaded
    for z_name, z_mod in ZIP_MODULES.items():
        for j_name in JSON_PARSERS.keys():
            label = f"SingleThread + {z_name} + {j_name}"
            elapsed = run_single_thread_benchmark(z_mod, zip_path, json_files, j_name)
            record_result(label, elapsed)

    # B. ThreadPool (Concurrent ZIP Read + Decode)
    for z_name, z_mod in ZIP_MODULES.items():
        for j_name in JSON_PARSERS.keys():
            label = f"ThreadPool + {z_name} + {j_name}"
            elapsed = run_thread_benchmark(z_mod, zip_path, json_files, j_name)
            record_result(label, elapsed)

    # C. TwoPhase ThreadPool (Pre-read Bytes -> Parallel Decode)
    for z_name, z_mod in ZIP_MODULES.items():
        for j_name in JSON_PARSERS.keys():
            label = f"TwoPhase(PreRead) + {z_name} + {j_name}"
            elapsed = run_twophase_thread_benchmark(z_mod, zip_path, json_files, j_name)
            record_result(label, elapsed)

    # D. ProcessPool (Multi-Process)
    for z_name in ZIP_MODULES.keys():
        use_def64 = (z_name == "zipfile_deflate64")
        for j_name in JSON_PARSERS.keys():
            label = f"ProcessPool + {z_name} + {j_name}"
            elapsed = run_process_benchmark(use_def64, zip_path, json_files, j_name)
            record_result(label, elapsed)

    # --- SUMMARY DISPLAY ---
    print("\n" + "=" * 70)
    print(f"{'Combo / Strategy':<51} | {'Time (s)':<8} | {'Speedup':<8}")
    print("=" * 70)
    for combo, t, sp in sorted(results, key=lambda x: x[1]):
        print(f"{combo:<51} | {t:<8.3f} | {sp:.2f}x")
    print("=" * 70)
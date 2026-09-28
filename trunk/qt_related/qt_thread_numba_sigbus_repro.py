"""
Minimal PySide6 QThread + Numba reproducer for macOS native crashes.

Run examples:

    python trunk/qt_related/qt_thread_numba_sigbus_repro.py
    python trunk/qt_related/qt_thread_numba_sigbus_repro.py --compile-in-worker
    python trunk/qt_related/qt_thread_numba_sigbus_repro.py --kernel graph-dispatch --compile-in-worker
    python trunk/qt_related/qt_thread_numba_sigbus_repro.py --workers 4 --iterations 200
    python trunk/qt_related/qt_thread_numba_sigbus_repro.py --no-cache

The interesting case is ``--compile-in-worker``: the first Numba compilation
happens inside a QThread instead of the main Qt thread.  ``--kernel sample`` is
intentionally tiny; ``--kernel graph-dispatch`` is still standalone but closer
to optimization-code patterns: graph traversal, classification, sparse-style
arrays, and dispatch loops.
"""

from __future__ import annotations

import argparse
import faulthandler
import os
import platform
import signal
import sys
import threading
import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QCoreApplication, QObject, QThread, QTimer, Signal, Slot


def _read_numba_cache_enabled() -> bool:
    return os.environ.get("QT_NUMBA_REPRO_DISABLE_CACHE", "0") != "1"


NUMBA_CACHE_ENABLED = _read_numba_cache_enabled()

import numba as nb


@nb.njit(cache=NUMBA_CACHE_ENABLED)
def sample_numba_kernel(a: np.ndarray, b: np.ndarray, rounds: int) -> float:
    """
    A small nopython kernel with enough work to force LLVM/JIT and repeated execution.
    """
    acc = 0.0
    n, m = a.shape

    for r in range(rounds):
        scale = 1.0 / (1.0 + r)

        for i in range(n):
            row_acc = 0.0
            for j in range(m):
                x = a[i, j] + b[j, i]
                row_acc += np.sin(x) * np.cos(x * scale) + np.sqrt(abs(x) + 1.0)

            acc += row_acc * scale

    return acc


def sample_kernel_batch(worker_id: int, size: int, rounds: int) -> float:
    rng = np.random.default_rng(seed=10_000 + worker_id)
    a = rng.normal(size=(size, size)).astype(np.float64)
    b = rng.normal(size=(size, size)).astype(np.float64)
    return float(sample_numba_kernel(a, b, rounds))


@nb.njit(cache=NUMBA_CACHE_ENABLED)
def classify_nodes(p_injection: np.ndarray, node_type: np.ndarray) -> tuple[int, int, int, float]:
    slack_count = 0
    pq_count = 0
    pv_count = 0
    best_pv = -1
    best_injection = -1e100

    for i in range(node_type.size):
        if node_type[i] == 3:
            slack_count += 1
        elif node_type[i] == 2:
            pv_count += 1
            if p_injection[i] > best_injection:
                best_injection = p_injection[i]
                best_pv = i
        else:
            pq_count += 1

    if slack_count == 0 and best_pv >= 0:
        slack_count = 1
        pv_count -= 1

    return slack_count, pq_count, pv_count, best_injection


@nb.njit(cache=NUMBA_CACHE_ENABLED)
def count_islands(node_count: int, indptr: np.ndarray, indices: np.ndarray, active: np.ndarray) -> int:
    visited = np.zeros(node_count, dtype=np.int8)
    stack = np.empty(node_count, dtype=np.int64)
    islands = 0

    for node in range(node_count):
        if visited[node] == 0 and active[node] != 0:
            islands += 1
            stack_size = 1
            stack[0] = node

            while stack_size > 0:
                stack_size -= 1
                current = stack[stack_size]

                if visited[current] != 0:
                    continue

                visited[current] = 1

                for ptr in range(indptr[current], indptr[current + 1]):
                    other = indices[ptr]
                    if visited[other] == 0 and active[other] != 0:
                        stack[stack_size] = other
                        stack_size += 1

    return islands


@nb.njit(cache=NUMBA_CACHE_ENABLED)
def diagonal_csc_checksum(values: np.ndarray) -> float:
    checksum = 0.0
    for i in range(values.size):
        checksum += i
        checksum += i + 1
        checksum += values[i]
    return checksum


@nb.njit(cache=NUMBA_CACHE_ENABLED)
def greedy_dispatch_kernel(load: np.ndarray,
                           pmax: np.ndarray,
                           pmin: np.ndarray,
                           active: np.ndarray,
                           cost: np.ndarray) -> float:
    total_cost = 0.0
    unserved = 0.0
    timesteps, generators = pmax.shape

    for t in range(timesteps):
        remaining = load[t]

        for _ in range(generators):
            best = -1
            best_cost = 1e100

            for g in range(generators):
                if active[t, g] != 0 and cost[t, g] < best_cost:
                    best = g
                    best_cost = cost[t, g]

            if best < 0:
                break

            dispatch = pmax[t, best]
            if dispatch < pmin[t, best]:
                dispatch = pmin[t, best]
            if dispatch > remaining:
                dispatch = remaining

            total_cost += dispatch * cost[t, best]
            remaining -= dispatch
            active[t, best] = 0

            if remaining <= 1e-9:
                break

        if remaining > 0.0:
            unserved += remaining

    return total_cost + 1000.0 * unserved


@nb.njit(cache=NUMBA_CACHE_ENABLED)
def graph_dispatch_kernel(p_injection: np.ndarray,
                          node_type: np.ndarray,
                          indptr: np.ndarray,
                          indices: np.ndarray,
                          node_active: np.ndarray,
                          diagonal: np.ndarray,
                          load: np.ndarray,
                          pmax: np.ndarray,
                          pmin: np.ndarray,
                          gen_active: np.ndarray,
                          gen_cost: np.ndarray) -> float:
    slack_count, pq_count, pv_count, best_injection = classify_nodes(p_injection, node_type)
    islands = count_islands(p_injection.size, indptr, indices, node_active)
    sparse_checksum = diagonal_csc_checksum(diagonal)
    dispatch_cost = greedy_dispatch_kernel(load, pmax, pmin, gen_active, gen_cost)

    return slack_count + pq_count + pv_count + best_injection + islands + sparse_checksum + dispatch_cost


def graph_dispatch_kernel_batch(worker_id: int, size: int, rounds: int) -> float:
    node_count = max(4, size)
    edge_entries = 2 * node_count

    p_injection = np.zeros(node_count, dtype=np.float64)
    p_injection[0] = 10.0 + worker_id
    p_injection[1::2] = -1.0

    node_type = np.ones(node_count, dtype=np.int64)
    node_type[0] = 2

    indptr = np.arange(0, edge_entries + 1, 2, dtype=np.int64)
    indices = np.empty(edge_entries, dtype=np.int64)
    for i in range(node_count):
        indices[2 * i] = i
        indices[2 * i + 1] = (i + 1) % node_count

    node_active = np.ones(node_count, dtype=np.int64)
    diagonal = np.ones(node_count, dtype=np.float64)

    timesteps = max(1, min(rounds, 16))
    generators = 4
    load = np.full(timesteps, 3.0, dtype=np.float64)
    pmax = np.full((timesteps, generators), 1.0, dtype=np.float64)
    pmin = np.zeros((timesteps, generators), dtype=np.float64)
    gen_active = np.ones((timesteps, generators), dtype=np.int64)
    gen_cost = np.tile(np.array([[30.0, 10.0, 20.0, 40.0]], dtype=np.float64), (timesteps, 1))

    return float(
        graph_dispatch_kernel(
            p_injection,
            node_type,
            indptr,
            indices,
            node_active,
            diagonal,
            load,
            pmax,
            pmin,
            gen_active,
            gen_cost,
        )
    )


@dataclass
class WorkerConfig:
    worker_id: int
    iterations: int
    size: int
    rounds: int
    kernel: str
    compile_in_worker: bool


class NumbaWorker(QObject):
    progress = Signal(int, int, float)
    failed = Signal(int, str)
    finished = Signal(int)

    def __init__(self, config: WorkerConfig):
        super().__init__()
        self.config = config

    @Slot()
    def run(self) -> None:
        try:
            cfg = self.config
            print(
                f"[worker {cfg.worker_id}] starting on Python thread "
                f"{threading.get_ident()}, Qt thread object {id(QThread.currentThread())}"
            )

            if cfg.compile_in_worker:
                print(
                    f"[worker {cfg.worker_id}] first Numba call for {cfg.kernel!r} "
                    "will compile in this QThread"
                )
            else:
                print(f"[worker {cfg.worker_id}] using main-thread-compiled {cfg.kernel!r} dispatchers")

            last = 0.0
            for iteration in range(cfg.iterations):
                last = run_kernel_batch(
                    kernel=cfg.kernel,
                    worker_id=cfg.worker_id,
                    size=cfg.size,
                    rounds=cfg.rounds,
                )

                if iteration == 0 or (iteration + 1) % max(1, cfg.iterations // 10) == 0:
                    self.progress.emit(cfg.worker_id, iteration + 1, last)

            self.finished.emit(cfg.worker_id)

        except BaseException as exc:  # pragma: no cover - native crash will bypass this
            self.failed.emit(self.config.worker_id, repr(exc))
            self.finished.emit(self.config.worker_id)


class ReproController(QObject):
    def __init__(self, config: argparse.Namespace):
        super().__init__()
        self.config = config
        self.threads: list[QThread] = []
        self.workers: list[NumbaWorker] = []
        self.remaining = config.workers
        self.failed = False
        self.started_at = time.perf_counter()

    @Slot()
    def start(self) -> None:
        if not self.config.compile_in_worker:
            print(f"[main] compiling {self.config.kernel!r} before starting QThreads")
            result = run_kernel_batch(
                kernel=self.config.kernel,
                worker_id=-1,
                size=self.config.size,
                rounds=self.config.rounds,
            )
            print(f"[main] warm-up result={result:.9g}")

        for worker_id in range(self.config.workers):
            thread = QThread()
            worker = NumbaWorker(
                WorkerConfig(
                    worker_id=worker_id,
                    iterations=self.config.iterations,
                    size=self.config.size,
                    rounds=self.config.rounds,
                    kernel=self.config.kernel,
                    compile_in_worker=self.config.compile_in_worker,
                )
            )

            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.progress.connect(self.on_progress)
            worker.failed.connect(self.on_failed)
            worker.finished.connect(self.on_worker_finished)
            worker.finished.connect(thread.quit)
            worker.failed.connect(thread.quit)
            thread.finished.connect(worker.deleteLater)
            thread.finished.connect(lambda worker_id=worker_id: self.on_thread_finished(worker_id))
            thread.finished.connect(thread.deleteLater)

            self.threads.append(thread)
            self.workers.append(worker)
            thread.start()

    @Slot(int, int, float)
    def on_progress(self, worker_id: int, iteration: int, value: float) -> None:
        print(f"[worker {worker_id}] iteration={iteration} value={value:.9g}")

    @Slot(int, str)
    def on_failed(self, worker_id: int, message: str) -> None:
        self.failed = True
        print(f"[worker {worker_id}] Python exception: {message}", file=sys.stderr)

    @Slot(int)
    def on_worker_finished(self, worker_id: int) -> None:
        print(f"[worker {worker_id}] finished")

    @Slot(int)
    def on_thread_finished(self, worker_id: int) -> None:
        self.remaining -= 1
        print(f"[thread {worker_id}] stopped; remaining={self.remaining}")

        if self.remaining == 0:
            elapsed = time.perf_counter() - self.started_at
            print(f"[main] all workers finished in {elapsed:.3f}s")
            QCoreApplication.exit(1 if self.failed else 0)


def print_environment(args: argparse.Namespace) -> None:
    print("=== environment ===")
    print(f"executable: {sys.executable}")
    print(f"python: {sys.version.replace(os.linesep, ' ')}")
    print(f"platform: {platform.platform()}")
    print(f"machine: {platform.machine()}")
    print(f"process id: {os.getpid()}")
    print(f"main python thread: {threading.get_ident()}")
    print(f"numpy: {np.__version__}")
    print(f"numba: {nb.__version__}")
    print(f"llvmlite: {getattr(__import__('llvmlite'), '__version__', 'unknown')}")
    print(f"PySide6: {__import__('PySide6').__version__}")
    print(f"NUMBA_CACHE_ENABLED: {NUMBA_CACHE_ENABLED}")
    print(f"args: {args}")
    print("===================")


def run_kernel_batch(kernel: str, worker_id: int, size: int, rounds: int) -> float:
    if kernel == "sample":
        return sample_kernel_batch(worker_id=worker_id, size=size, rounds=rounds)
    if kernel == "graph-dispatch":
        return graph_dispatch_kernel_batch(worker_id=worker_id, size=size, rounds=rounds)

    raise ValueError(f"Unknown kernel {kernel!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PySide6 QThread + Numba SIGBUS reproducer")
    parser.add_argument(
        "--kernel",
        choices=("sample", "graph-dispatch"),
        default="sample",
        help="Use a tiny standalone kernel or a standalone graph/dispatch workload",
    )
    parser.add_argument("--workers", type=int, default=1, help="Number of QThreads to launch")
    parser.add_argument("--iterations", type=int, default=50, help="Kernel calls per worker")
    parser.add_argument("--size", type=int, default=64, help="Square matrix size")
    parser.add_argument("--rounds", type=int, default=6, help="Inner compute rounds per kernel call")
    parser.add_argument(
        "--compile-in-worker",
        action="store_true",
        help="Let the first Numba compilation happen inside the QThread",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Re-exec with Numba cache disabled for this reproducer",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    if args.no_cache and NUMBA_CACHE_ENABLED:
        env = os.environ.copy()
        env["QT_NUMBA_REPRO_DISABLE_CACHE"] = "1"
        os.execve(sys.executable, [sys.executable, *sys.argv], env)

    faulthandler.enable(all_threads=True)
    for sig in (signal.SIGBUS, signal.SIGSEGV, signal.SIGABRT, signal.SIGILL):
        try:
            faulthandler.register(sig, all_threads=True, chain=True)
        except RuntimeError:
            pass

    print_environment(args)

    app = QCoreApplication(sys.argv)
    controller = ReproController(args)
    QTimer.singleShot(0, controller.start)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

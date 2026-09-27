"""
Standalone PySide6 + Numba/llvmlite SIGBUS reproducer.

This intentionally contains no VeraGrid imports.  It extracts the shape of the
failing code path: a QThread triggers first compilation of a Numba function that
calls another Numba function and returns a jitclass sparse matrix object.

Observed failing environment:
    macOS arm64, Python 3.14.3, numba 0.67.0, llvmlite 0.49.0, PySide6 6.11.2

Run:
    python trunk/qt_related/numba_qthread_jitclass_sigbus_repro.py
    python trunk/qt_related/numba_qthread_jitclass_sigbus_repro.py --main-thread
    python trunk/qt_related/numba_qthread_jitclass_sigbus_repro.py --no-cache
"""

from __future__ import annotations

import argparse
import faulthandler
import os
import platform
import signal
import sys
import threading
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QCoreApplication, QObject, QThread, QTimer, Signal, Slot


def read_cache_enabled() -> bool:
    return os.environ.get("NUMBA_QTHREAD_REPRO_DISABLE_CACHE", "0") != "1"


NUMBA_CACHE_ENABLED = read_cache_enabled()

import numba as nb
from numba import types
from numba.experimental import jitclass


@jitclass([
    ("n_rows", nb.int32),
    ("n_cols", nb.int32),
    ("nnz", nb.int32),
    ("data", nb.float64[:]),
    ("indices", nb.int32[:]),
    ("indptr", nb.int32[:]),
    ("format", types.unicode_type),
])
class CscMatrix:
    def __init__(self, n_rows: int, n_cols: int, nnz: int, force_zeros: bool):
        self.format = "csc"
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.nnz = nnz

        if force_zeros:
            self.data = np.zeros(nnz, dtype=np.float64)
            self.indices = np.zeros(nnz, dtype=np.int32)
            self.indptr = np.zeros(n_cols + 1, dtype=np.int32)
        else:
            self.data = np.empty(nnz, dtype=np.float64)
            self.indices = np.empty(nnz, dtype=np.int32)
            self.indptr = np.empty(n_cols + 1, dtype=np.int32)

        self.indptr[0] = 0

    def resize(self, nnz: np.int32):
        self.nnz = nnz
        self.data = self.data[:nnz]
        self.indices = self.indices[:nnz]


@nb.jit(cache=NUMBA_CACHE_ENABLED)
def make_lookup(size: int, indices: np.ndarray) -> np.ndarray:
    lookup = np.full(size, -1, dtype=np.int32)
    lookup[indices] = np.arange(len(indices), dtype=np.int32)
    return lookup


@nb.jit(cache=NUMBA_CACHE_ENABLED)
def sparse_derivatives(Yx: np.ndarray,
                       Yp: np.ndarray,
                       Yi: np.ndarray,
                       V: np.ndarray,
                       Vm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(Yp) - 1
    Ibus = np.zeros(n, dtype=np.complex128)
    dS_dVm_x = Yx.copy()
    dS_dVa_x = Yx.copy()
    E = V.copy()

    for j in range(n):
        if Vm[j] != 0.0:
            E[j] /= Vm[j]

        for k in range(Yp[j], Yp[j + 1]):
            i = Yi[k]
            current = Yx[k] * V[j]
            Ibus[i] += current
            dS_dVm_x[k] = Yx[k] * E[j]
            dS_dVa_x[k] = -current

    for j in range(n):
        buffer = np.conj(Ibus[j]) * E[j]

        for k in range(Yp[j], Yp[j + 1]):
            i = Yi[k]
            dS_dVm_x[k] = V[i] * np.conj(dS_dVm_x[k])

            if j == i:
                dS_dVa_x[k] += Ibus[j]
                dS_dVm_x[k] += buffer

            dS_dVa_x[k] = (1j * V[i]) * np.conj(dS_dVa_x[k])

    return dS_dVm_x, dS_dVa_x


@nb.jit( cache=NUMBA_CACHE_ENABLED)
def create_jacobian_like(nbus: int,
                         Yx: np.ndarray,
                         Yp: np.ndarray,
                         Yi: np.ndarray,
                         V: np.ndarray,
                         idx_dtheta: np.ndarray,
                         idx_dVm: np.ndarray,
                         idx_dP: np.ndarray,
                         idx_dQ: np.ndarray) -> CscMatrix:
    dS_dVm_x, dS_dVa_x = sparse_derivatives(Yx, Yp, Yi, V, np.abs(V))

    nj = len(idx_dtheta) + len(idx_dVm)
    nnz_estimate = 5 * len(dS_dVm_x)
    J = CscMatrix(nj, nj, nnz_estimate, False)

    lookup_dP = make_lookup(nbus, idx_dP)
    lookup_dQ = make_lookup(nbus, idx_dQ)

    n_no_slack = len(idx_dtheta)
    nnz = 0
    p = 0
    J.indptr[p] = nnz

    for j in idx_dtheta:
        for k in range(Yp[j], Yp[j + 1]):
            i = Yi[k]
            ii = lookup_dP[i]

            if idx_dtheta[ii] == i:
                J.data[nnz] = dS_dVa_x[k].real
                J.indices[nnz] = ii
                nnz += 1

        for k in range(Yp[j], Yp[j + 1]):
            i = Yi[k]
            ii = lookup_dQ[i]

            if idx_dQ[ii] == i:
                J.data[nnz] = dS_dVa_x[k].imag
                J.indices[nnz] = ii + n_no_slack
                nnz += 1

        p += 1
        J.indptr[p] = nnz

    for j in idx_dVm:
        for k in range(Yp[j], Yp[j + 1]):
            i = Yi[k]
            ii = lookup_dP[i]

            if idx_dtheta[ii] == i:
                J.data[nnz] = dS_dVm_x[k].real
                J.indices[nnz] = ii
                nnz += 1

        for k in range(Yp[j], Yp[j + 1]):
            i = Yi[k]
            ii = lookup_dQ[i]

            if idx_dQ[ii] == i:
                J.data[nnz] = dS_dVm_x[k].imag
                J.indices[nnz] = ii + n_no_slack
                nnz += 1

        p += 1
        J.indptr[p] = nnz

    J.indptr[p] = nnz
    J.resize(nnz)
    return J


def make_inputs(nbus: int):
    indptr = np.arange(0, 3 * nbus + 1, 3, dtype=np.int32)
    indices = np.empty(3 * nbus, dtype=np.int32)
    data = np.empty(3 * nbus, dtype=np.complex128)

    for j in range(nbus):
        rows = ((j - 1) % nbus, j, (j + 1) % nbus)
        for offset, row in enumerate(rows):
            k = 3 * j + offset
            indices[k] = row
            if row == j:
                data[k] = 2.0 + 0.1j
            else:
                data[k] = -1.0 - 0.05j

    V = np.ones(nbus, dtype=np.complex128)
    idx_dtheta = np.arange(1, nbus, dtype=np.int32)
    idx_dVm = np.arange(1, nbus, dtype=np.int32)
    idx_dP = idx_dtheta.copy()
    idx_dQ = idx_dVm.copy()
    return data, indptr, indices, V, idx_dtheta, idx_dVm, idx_dP, idx_dQ


def run_compile_and_call(nbus: int) -> None:
    print(f"calling create_jacobian_like on Python thread {threading.get_ident()}", flush=True)
    args = make_inputs(nbus)
    J = create_jacobian_like(nbus, *args)
    print(f"ok nnz={J.nnz} shape=({J.n_rows}, {J.n_cols})", flush=True)


class Worker(QObject):
    finished = Signal()

    def __init__(self, nbus: int):
        super().__init__()
        self.nbus = nbus

    @Slot()
    def run(self):
        print(
            f"worker started on Python thread {threading.get_ident()}, "
            f"Qt thread object {id(QThread.currentThread())}",
            flush=True,
        )
        run_compile_and_call(self.nbus)
        self.finished.emit()


@dataclass
class Controller:
    app: QCoreApplication
    worker: Worker | None = None
    thread: QThread | None = None

    def start_worker(self, nbus: int) -> None:
        self.thread = QThread()
        self.worker = Worker(nbus)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.app.quit)
        self.thread.start()


def print_environment(args: argparse.Namespace) -> None:
    print("=== environment ===", flush=True)
    print(f"executable: {sys.executable}", flush=True)
    print(f"python: {sys.version.replace(os.linesep, ' ')}", flush=True)
    print(f"platform: {platform.platform()}", flush=True)
    print(f"machine: {platform.machine()}", flush=True)
    print(f"numpy: {np.__version__}", flush=True)
    print(f"numba: {nb.__version__}", flush=True)
    print(f"llvmlite: {getattr(__import__('llvmlite'), '__version__', 'unknown')}", flush=True)
    print(f"PySide6: {__import__('PySide6').__version__}", flush=True)
    print(f"NUMBA_CACHE_ENABLED: {NUMBA_CACHE_ENABLED}", flush=True)
    print(f"args: {args}", flush=True)
    print("===================", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PySide6 QThread Numba jitclass SIGBUS reproducer")
    parser.add_argument("--main-thread", action="store_true", help="Compile and run outside QThread")
    parser.add_argument("--no-cache", action="store_true", help="Re-exec with Numba cache disabled")
    parser.add_argument("--nbus", type=int, default=4)
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
        env["NUMBA_QTHREAD_REPRO_DISABLE_CACHE"] = "1"
        os.execve(sys.executable, [sys.executable, *sys.argv], env)

    faulthandler.enable(all_threads=True)
    for sig in (signal.SIGBUS, signal.SIGSEGV, signal.SIGABRT, signal.SIGILL):
        try:
            faulthandler.register(sig, all_threads=True, chain=True)
        except RuntimeError:
            pass

    print_environment(args)

    if args.main_thread:
        run_compile_and_call(args.nbus)
        return 0

    app = QCoreApplication(sys.argv)
    controller = Controller(app=app)
    QTimer.singleShot(0, lambda: controller.start_worker(args.nbus))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

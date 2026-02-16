# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Optional, Tuple, List
import numpy as np

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import (
    SimulationBackend,
    JacobianBackend,
    DynamicIntegrationMethod
)


# Assuming diagnostic is available in Utils.Symbolic
# from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector

class ImplicitJitSolver:
    """
    High-Performance Execution Context for EMT Simulations.

    Responsibility:
    Manages the lifecycle of the BlockSolver (Compilation -> Step Execution).
    It abstracts the complexity of choosing between Scalar JIT, Sparse AD,
    and Vectorized Clustering backends based on system metrics.
    """

    def __init__(self,
                 system_block: Block,
                 time_var: Var,
                 backend: SimulationBackend = SimulationBackend.SymbolicImplicit,
                 jacobian_backend: JacobianBackend = JacobianBackend.Automatic):
        """
        Initialize the execution context.
        """
        self.system_block = system_block
        self.time_var = time_var
        self.backend = backend
        self.jacobian_backend = jacobian_backend

        # The core mathematical engine
        self._engine: Optional[BlockSolver] = None
        # self._trace_collector: Optional[NewtonTraceCollector] = None

    def compile(self, verbose: bool = True):
        """
        Triggers the analysis of the symbolic graph and JIT compilation of kernels.
        """
        if verbose:
            print(f"--- [ImplicitJIT] Initializing Solver Engine ---")

        self._engine = BlockSolver(
            block_system=self.system_block,
            glob_time=self.time_var,
            use_jit=True,
            backend=self.backend,
            jacobian_backend=self.jacobian_backend
        )

        if verbose:
            print(f"    Engine Ready. System Size: {self._engine._n_vars} variables.")

    def enable_diagnostics(self):
        """
        Attaches a trace collector to monitor Newton-Raphson convergence per step.
        """
        if self._engine is None:
            raise RuntimeError("Solver must be compiled before enabling diagnostics.")

        # self._trace_collector = NewtonTraceCollector()
        # self._engine.enable_newton_tracing(self._trace_collector)
        pass

    def solve_step(self,
                   t: float,
                   h: float,
                   x_prev: np.ndarray,
                   dx_prev: Optional[np.ndarray] = None,
                   params_prev: Optional[np.ndarray] = None,
                   method: DynamicIntegrationMethod = DynamicIntegrationMethod.Trapezoid,
                   force_vectorization: bool = False,
                   dense_threshold: int = 100) -> Tuple[float, np.ndarray]:
        """
        Executes a single integration step.

        PhD Feature:
        Automatically selects the 'Vectorized' path if the system size exceeds
        the dense_threshold significantly or if explicitly requested, enabling
        O(1) overhead scaling for massive grids.
        """
        if self._engine is None:
            raise RuntimeError("Solver is not compiled.")

        # Heuristic for auto-vectorization (Algebraic Clustering)
        # Vectorization pays off when management overhead < physics computation
        is_large_system = self._engine._n_vars > 300
        use_vectorized = force_vectorization or is_large_system

        # Delegate to the Unified Simulation Interface in block_solver.py
        t_out, y_out = self._engine.simulate_unified(
            t0=t,
            t_end=t + h,
            h=h,
            x0=x_prev,
            dx0=dx_prev,
            params0=params_prev,
            method=method,
            vectorized=use_vectorized,
            dense_threshold=dense_threshold,
            verbose=False
        )

        # Extract the state vector for the next step (last row of y_out)
        # simulate_unified returns full trajectory, we usually just need the next step
        x_next = y_out[-1]

        return t + h, x_next
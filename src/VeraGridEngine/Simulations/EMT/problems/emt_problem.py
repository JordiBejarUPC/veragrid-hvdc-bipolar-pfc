# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import (
    SimulationBackend,
    JacobianBackend,
    DynamicIntegrationMethod
)


class EmtProblemBase(ABC):
    """
    Abstract Base Class for Normalized EMT Problems.

    Architectural Role:
    Acts as the 'Universal Container' that decouples the physical definition
    (Topology) from the numerical engine (Solver). It orchestrates the transition
    between the symbolic definition and the compiled JIT execution.
    """

    def __init__(self, name: str = "EmtSystem"):
        """
        Initialize the problem container.

        Args:
            name: Name of the system for logging and debugging.
        """
        self.name = name

        # Global Symbolic Namespace (Root Block)
        self.root_block = Block(name=f"{name}_Root")

        # Global Time Variable
        self.t_sym = Var("t_global")

        # Numerical Engine (Lazy Initialization)
        self.solver: Optional[BlockSolver] = None

        self._is_compiled = False

    @abstractmethod
    def build_structure(self):
        """
        Abstract method where specific system topology must be defined.
        Implementations should instantiate devices and use the TopologyAssembler
        to connect them within the root_block.
        """
        pass

    def compile_system(self,
                       backend: SimulationBackend = SimulationBackend.SymbolicImplicit,
                       jacobian_backend: JacobianBackend = JacobianBackend.Automatic,
                       verbose: bool = True):
        """
        Finalizes the system definition and triggers JIT compilation of kernels.

        Args:
            backend: Simulation backend (Legacy vs SymbolicImplicit).
            jacobian_backend: Differentiation strategy (Symbolic vs Automatic).
            verbose: Enable compilation timing logs.
        """
        if verbose:
            print(f"--- [EMT-System] Compiling '{self.name}' ---")

        # 1. Build Topology
        self.build_structure()

        # 2. Instantiate BlockSolver (The Mathematical Brain)
        self.solver = BlockSolver(
            block_system=self.root_block,
            glob_time=self.t_sym,
            use_jit=True,
            backend=backend,
            jacobian_backend=jacobian_backend
        )

        self._is_compiled = True

        if verbose:
            print(f"    System Compiled: {self.solver._n_vars} Variables "
                  f"({self.solver._n_state} States, {self.solver._n_alg} Algebraic)")

    def solve_step(self,
                   t: float,
                   h: float,
                   x_prev: np.ndarray,
                   dx_prev: Optional[np.ndarray] = None,
                   params_prev: Optional[np.ndarray] = None,
                   method: DynamicIntegrationMethod = DynamicIntegrationMethod.Trapezoid,
                   **kwargs) -> Tuple[float, np.ndarray]:
        """
        Executes a single unified integration step.

        PhD Feature:
        Dynamically detects if the Vectorized Engine (Algebraic Clustering)
        should be used based on system complexity (>300 vars) or explicit flags.
        """
        if not self._is_compiled or self.solver is None:
            raise RuntimeError("EMT Simulation must be compiled before running steps.")

        # Logic for Doctoral Strategy Selection
        force_vectorized = kwargs.get('vectorized', False)
        # Automatic threshold: if many variables, assume vectorization benefit
        auto_vectorize = (self.solver._n_vars > 300)
        use_vec = force_vectorized or auto_vectorize

        # Delegate to the Unified Solver Interface
        t_out, y_out = self.solver.simulate_unified(
            t0=t,
            t_end=t + h,
            h=h,
            x0=x_prev,
            dx0=dx_prev,
            params0=params_prev,
            method=method,
            vectorized=use_vec,
            dense_threshold=kwargs.get('dense_threshold', 100),
            boundary_update_fn=kwargs.get('boundary_update_fn', None),
            verbose=False
        )

        # Return next time and next state vector (last row of result)
        return t_out[-1], y_out[-1]

    def get_initial_state_empty(self) -> np.ndarray:
        """
        Returns a zero-initialized state vector of the correct size.
        """
        if self.solver is None:
            return np.array([])
        return np.zeros(self.solver._n_vars)
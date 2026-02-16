# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr
from VeraGridEngine.Utils.Symbolic.block import Block


class EmtDeviceInterface(ABC):
    """
    Abstract Base Class for Normalized EMT Devices.

    Architectural Role:
    Standardizes the physical definition of components to enable:
    1. Algebraic Clustering: Automatic detection of identical device patterns.
    2. Topological Assembly: Automatic KCL generation via port definitions.
    """

    def __init__(self, name: str):
        self.name = name
        self.block = Block(name=f"Dev_{name}")
        self._ports: Dict[str, Var] = {}
        self._is_built = False

        # Helper: Asegura que el bloque esté inicializado correctamente
        self._ensure_lists()

    def _ensure_lists(self):
        """
        Internal Helper: Guarantees that the internal Block lists exist
        and are not None, preventing AttributeErrors during build.
        """
        if not hasattr(self.block, 'state_vars') or self.block.state_vars is None:
            self.block.state_vars = []
        if not hasattr(self.block, 'state_eqs') or self.block.state_eqs is None:
            self.block.state_eqs = []
        if not hasattr(self.block, 'algebraic_vars') or self.block.algebraic_vars is None:
            self.block.algebraic_vars = []
        if not hasattr(self.block, 'algebraic_eqs') or self.block.algebraic_eqs is None:
            self.block.algebraic_eqs = []
        if not hasattr(self.block, 'parameters') or self.block.parameters is None:
            self.block.parameters = {}

    @abstractmethod
    def build_model(self):
        """
        Abstract method where specific device physics must be defined.
        """
        pass

    def get_block(self) -> Block:
        """
        Retrieves the fully configured symbolic block for this device.
        """
        if not self._is_built:
            self.build_model()
            self._is_built = True
        return self.block

    def define_port(self, terminal_name: str, current_var: Var):
        """
        Registers a current variable as an external connection port.
        """
        self._ports[terminal_name] = current_var

    def get_ports(self) -> Dict[str, Var]:
        return self._ports

    # ==========================================================================
    # HELPERS: Métodos seguros para definir ecuaciones sin tocar listas crudas
    # ==========================================================================

    def add_state_equation(self, diff_var: Var, rhs_expr: Expr):
        """
        Helper seguro para registrar una ecuación diferencial: d(x)/dt = f(x, u).
        Maneja internamente la sincronización de las listas de variables y ecuaciones.
        """
        self._ensure_lists()
        # 1. Registramos la variable de estado
        self.block.state_vars.append(diff_var)
        # 2. Registramos la ecuación correspondiente (RHS)
        self.block.state_eqs.append(rhs_expr)

    def add_algebraic_equation(self, lhs_expr: Expr, rhs_expr: Optional[Expr] = None):
        """
        Helper seguro para registrar una ecuación algebraica: 0 = LHS - RHS.
        """
        self._ensure_lists()
        if rhs_expr is not None:
            expr = lhs_expr - rhs_expr
        else:
            expr = lhs_expr
        self.block.algebraic_eqs.append(expr)

    def add_algebraic_variable(self, var: Var):
        """
        Helper seguro para registrar una variable algebraica (incógnita).
        """
        self._ensure_lists()
        self.block.algebraic_vars.append(var)

    def set_parameters(self, params_dict: Dict[Var, any]):
        """
        Helper para asignar parámetros de forma masiva.
        """
        self._ensure_lists()
        self.block.parameters.update(params_dict)
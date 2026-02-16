# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Optional
from collections import defaultdict
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.Devices.device_interface import EmtDeviceInterface


class TopologyAssembler:
    """
    Symbolic Network Assembler.

    Responsibility:
    Constructs the Kirchhoff Current Law (KCL) algebraic equations dynamically.
    It maps device terminals to grid nodes, enabling the automatic generation
    of the sparse Jacobian structure required for the Scatter-Add strategy.
    """

    def __init__(self):
        """
        Initialize the assembler.
        """
        # Maps Grid_Node_ID -> List of Current Injection Expressions
        self._nodal_injections: Dict[str, List[Expr]] = defaultdict(list)
        self._ground_nodes = {'gnd', '0', 'ground'}

    def connect_device(self, device: EmtDeviceInterface, connection_map: Dict[str, str]):
        """
        Registers a device's terminal currents into the global nodal balance dictionary.

        Args:
            device: The device instance containing the physics block.
            connection_map: Mapping {'Device_Terminal_Name': 'Grid_Node_ID'}.
        """
        device_ports = device.get_ports()

        for term_name, node_id in connection_map.items():
            # Skip ground nodes (infinite bus / reference)
            if node_id.lower() in self._ground_nodes:
                continue

            if term_name not in device_ports:
                raise ValueError(f"Device '{device.name}' does not have a port named '{term_name}'.")

            # Get the symbolic variable representing current leaving the terminal
            i_injection = device_ports[term_name]

            # Register injection for KCL generation
            self._nodal_injections[node_id].append(i_injection)

    def assemble(self, root_block: Block):
        """
        Generates KCL algebraic equations (Sum(I) = 0) for every node
        and injects them into the system's root block.

        This step implicitly defines the sparsity pattern that the
        Vectorized Jacobian Strategy will optimize via Scatter-Add.
        """
        for node_id, currents in self._nodal_injections.items():
            if not currents:
                continue

            # KCL: Sum(I_injections) = 0
            # We construct the symbolic expression: I1 + I2 + ... + In
            kcl_expr = currents[0]
            for i in range(1, len(currents)):
                kcl_expr = kcl_expr + currents[i]

            # Add to the global DAE system
            # The BlockSolver will treat this as an algebraic constraint g(x,y) = 0
            root_block.add_algebraic_eq(kcl_expr)
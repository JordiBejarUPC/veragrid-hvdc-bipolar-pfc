# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Topology.simulation_indices import SimulationIndices
from VeraGridEngine.enumerations import BusMode


def test_1():
    fname = os.path.join('data', 'grids', 'IEEE14_types_test.gridcal')
    circuit = gce.FileOpen(fname).open()
    sn_nc = gce.compile_numerical_circuit_at(circuit)

    # snapshot types
    sn_types = sn_nc.bus_data.bus_types

    # the first time step does not change the generator status, hence it should be equal to the snapshot
    expected = [3, 2, 2, 1, 1, 2, 1, 2, 1, 1, 1, 1, 1, 1]
    assert (np.allclose(expected, sn_types))


def test_automatic_slack_promotion_updates_control_masks() -> None:
    """Synchronize bus control masks when a PV bus becomes the reference.

    :return: None.
    """
    # Build one connected AC circuit whose voltage-controlled generator bus is
    # intentionally not declared as slack, exercising the numerical fallback.
    circuit: gce.MultiCircuit = gce.MultiCircuit()
    pv_bus: gce.Bus = gce.Bus(name="PV bus")
    pq_bus: gce.Bus = gce.Bus(name="PQ bus")
    circuit.add_bus(pv_bus)
    circuit.add_bus(pq_bus)
    circuit.add_line(gce.Line(bus_from=pv_bus, bus_to=pq_bus, r=0.01, x=0.1))
    circuit.add_generator(
        bus=pv_bus,
        api_obj=gce.Generator(name="PV generator", P=10.0, vset=1.0),
    )
    circuit.add_load(
        bus=pq_bus,
        api_obj=gce.Load(name="PQ load", P=10.0, Q=1.0),
    )

    # Compile the canonical controls before asking the numerical circuit to
    # choose the missing angular reference from the available PV buses.
    numerical_circuit: NumericalCircuit = gce.compile_numerical_circuit_at(circuit)
    simulation_indices: SimulationIndices = numerical_circuit.get_simulation_indices()
    reference_index: int = int(simulation_indices.vd[0])

    assert reference_index == 0
    assert numerical_circuit.bus_data.bus_types[reference_index] == BusMode.Slack_tpe.value
    assert not bool(numerical_circuit.bus_data.is_p_controlled[reference_index])
    assert not bool(numerical_circuit.bus_data.is_q_controlled[reference_index])
    assert bool(numerical_circuit.bus_data.is_vm_controlled[reference_index])
    assert bool(numerical_circuit.bus_data.is_va_controlled[reference_index])

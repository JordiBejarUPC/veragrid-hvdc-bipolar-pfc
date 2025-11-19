# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from typing import Dict
from VeraGridEngine.Devices.measurement import (PiMeasurement, PfMeasurement, PtMeasurement, PgMeasurement,
                                                QiMeasurement, QfMeasurement, QtMeasurement, QgMeasurement,
                                                VmMeasurement, VaMeasurement,
                                                IfMeasurement, ItMeasurement)

from VeraGridEngine.Devices.Aggregation import *
from VeraGridEngine.Devices.Branches import *
from VeraGridEngine.Devices.Injections import *
from VeraGridEngine.Devices.Substation import *
from VeraGridEngine.Devices.Associations import *
from VeraGridEngine.Devices.Diagrams import *
from VeraGridEngine.Devices.Fluid import *
from VeraGridEngine.Devices.Dynamic import *

from VeraGridEngine.Devices.types import ALL_DEV_TYPES


def get_objects_dictionary() -> Dict[str, ALL_DEV_TYPES]:
    """
    creates a dictionary with the types and the circuit objects
    :return: Dictionary instance
    """

    # this list must be sorted in dependency order so that the
    # loading algorithm is able to find the object substitutions

    object_types = {
        'modelling_authority': ModellingAuthority(),

        'area': Area(),
        'zone': Zone(),

        'country': Country(),
        'community': Community(),
        'region': Region(),
        'municipality': Municipality(),

        'substation': Substation(),
        'voltage_level': VoltageLevel(),

        'technology': Technology(),

        'fuel': Fuel(),

        'emission': EmissionGas(),

        'facility': Facility(),

        'rms_model_template': RmsModelTemplate(),

        'bus': Bus(),

        'bus_bar': BusBar(),

        'load': Load(),

        'static_generator': StaticGenerator(),

        'battery': Battery(),

        'generator': Generator(),

        'shunt': Shunt(),

        'linear_shunt': ControllableShunt(),

        'external_grid': ExternalGrid(),

        'current_injection': CurrentInjection(),

        'wires': Wire(),
        'overhead_line_types': OverheadLineType(),
        'underground_cable_types': UndergroundLineType(),
        'sequence_line_types': SequenceLineType(),
        'transformer_types': TransformerType(),

        'branch_group': BranchGroup(),

        'branch': Branch(),
        'transformer2w': Transformer2W(),

        'windings': Winding(),
        'transformer3w': Transformer3W(),

        'line': Line(),
        'dc_line': DcLine(),

        'hvdc': HvdcLine(),

        'vsc': VSC(),
        'upfc': UPFC(),

        'series_reactance': SeriesReactance(),

        'switch': Switch(),

        'contingency_group': ContingencyGroup(),
        'contingency': Contingency(),

        'remedial_action_group': RemedialActionGroup(),
        'remedial_action': RemedialAction(),

        'investments_group': InvestmentsGroup(),
        'investment': Investment(),

        'fluid_node': FluidNode(),
        'fluid_path': FluidPath(),
        'fluid_turbine': FluidTurbine(),
        'fluid_pump': FluidPump(),
        'fluid_p2x': FluidP2x(),


    }
    return object_types

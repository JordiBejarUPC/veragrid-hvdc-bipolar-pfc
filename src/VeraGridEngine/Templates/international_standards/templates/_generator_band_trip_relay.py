# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Shared implementation for PSS/E-style generator band trip relays."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.procedural_logic import ProceduralLogicBase
from VeraGridEngine.Utils.procedural_logic import bool_or
from VeraGridEngine.Utils.procedural_logic import flipflop
from VeraGridEngine.Utils.procedural_logic import pickup_dropoff
from VeraGridEngine.enumerations import DeviceType


def build_generator_band_trip_relay(
        vf: VarFactory,
        name: str,
        measurement_name: str,
        lower_name: str,
        upper_name: str,
        lower_default: float,
        upper_default: float,
) -> EmtModelTemplate:
    """
    Build pickup, breaker-delay, and retained-trip stages around one admissible band.

    :param vf: Variable factory that owns the relay symbols.
    :type vf: VarFactory
    :param name: Runtime relay name.
    :type name: str
    :param measurement_name: Public measurement input name.
    :type measurement_name: str
    :param lower_name: Lower-threshold parameter name.
    :type lower_name: str
    :param upper_name: Upper-threshold parameter name.
    :type upper_name: str
    :param lower_default: Default lower threshold.
    :type lower_default: float
    :param upper_default: Default upper threshold.
    :type upper_default: float
    :return: Materialized generator trip relay.
    :rtype: EmtModelTemplate
    """
    templ: EmtModelTemplate = EmtModelTemplate(name=name)
    templ.tpe = DeviceType.NoDevice

    # Allocate the public measurement and relay settings before composing timing logic.
    measurement: Var = vf.add_var(name=f"{measurement_name}_{name}")
    lower: Var = vf.add_var(name=f"{lower_name}_{name}")
    upper: Var = vf.add_var(name=f"{upper_name}_{name}")
    pickup_time: Var = vf.add_var(name=f"TP_{name}")
    breaker_time: Var = vf.add_var(name=f"TB_{name}")
    manual_reset: Var = vf.add_var(name=f"ManualReset_{name}")

    pickup_mode: Var = vf.add_var(name=f"PickupMode_{name}")
    breaker_mode: Var = vf.add_var(name=f"BreakerMode_{name}")
    trip_mode: Var = vf.add_var(name=f"TripMode_{name}")

    outside_band: Var = vf.add_var(name=f"OutsideBand_{name}")
    pickup_status: Var = vf.add_var(name=f"PickupStatus_{name}")
    breaker_status: Var = vf.add_var(name=f"BreakerStatus_{name}")
    trip: Var = vf.add_var(name=f"Trip_{name}")

    zero: Const = vf.add_const(value=0.0)
    half: Const = vf.add_const(value=0.5)
    outside_expr: Expr = bool_or(measurement < lower, measurement >= upper)

    # Settings remain runtime event parameters while timer states remain procedural modes.
    event_dict: dict[Var, Expr | Const] = dict({
        lower: vf.add_const(value=lower_default),
        upper: vf.add_const(value=upper_default),
        pickup_time: vf.add_const(value=0.00005),
        breaker_time: vf.add_const(value=0.083),
        manual_reset: zero,
    })
    mode_dict: dict[Var, Expr | Const] = dict({
        pickup_mode: zero,
        breaker_mode: zero,
        trip_mode: zero,
    })
    procedural_logic: list[ProceduralLogicBase] = list([
        pickup_dropoff(
            output=pickup_mode,
            boolexpr=outside_expr,
            Tpick=pickup_time,
            Tdrop=zero,
            name=f"pickup_timer_{name}",
        ),
        pickup_dropoff(
            output=breaker_mode,
            # Arm the breaker deadline from the original threshold crossing.
            # Chaining two independent timer objects would make the second
            # stage inherit the solver's previous accepted sample time and
            # could incorrectly overlap TP and TB at an exact forced event.
            boolexpr=outside_expr,
            Tpick=pickup_time + breaker_time,
            Tdrop=zero,
            name=f"breaker_timer_{name}",
        ),
        flipflop(
            boolset=breaker_mode > half,
            boolreset=manual_reset > half,
            output=trip_mode,
            name=f"trip_latch_{name}",
        ),
    ])

    templ.block = Block(
        algebraic_vars=[outside_band, pickup_status, breaker_status, trip],
        algebraic_eqs=[
            outside_band - outside_expr,
            pickup_status - pickup_mode,
            breaker_status - breaker_mode,
            trip - trip_mode,
        ],
        init_eqs={
            measurement: vf.add_const(value=(lower_default + upper_default) / 2.0),
            outside_band: zero,
            pickup_status: zero,
            breaker_status: zero,
            trip: zero,
        },
        event_dict=event_dict,
        mode_dict=mode_dict,
        procedural_logic=procedural_logic,
        in_vars=[measurement],
        out_vars=[trip],
        name=name,
    )
    return templ

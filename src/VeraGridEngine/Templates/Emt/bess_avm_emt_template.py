# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Expr
import VeraGridEngine.Utils.Symbolic.symbolic as sym

from VeraGridEngine.Templates.Emt.converter_emt_template import (
    _build_pseudo_emt_converter_vsc_block,
    _build_pseudo_emt_converter_pll_block,
    _build_pseudo_emt_converter_outer_loop_block,
    _build_pseudo_emt_converter_inner_loop_block,
    _build_pseudo_emt_converter_transformer_block,
)


def get_battery_avm_emt_template(vf: VarFactory, name: str) -> Block:
    """
    Build the aggregated battery block used by the Level-1 BESS template.

    The block represents the storage side as a Thevenin battery equivalent
    connected to the DC terminal used by the existing pseudo-EMT VSC block. It
    intentionally does not include a DC-link capacitor because the imported VSC
    block already owns the internal DC-link state ``v_dc`` and its capacitance
    ``C_dc``. Duplicating that capacitor here would create two competing DC
    energy buffers.

    Electrical model
    ----------------
    The battery is represented by a smooth open-circuit voltage and a terminal
    resistance::

        v_oc  = v_min + (v_max - v_min) * soc_limited
        v_bus = v_oc - r_bat * i_bat

    where ``i_bat`` is taken as positive when the BESS discharges and delivers
    active power to the converter DC side. The DC terminal voltage ``v_bus`` is
    passed to the imported VSC block as its ``v_dc_bus`` input.

    Energy model
    ------------
    The state of charge is updated from the battery terminal power. Positive
    power discharges the battery, while negative power charges it. Separate
    charge and discharge efficiencies are used through a smooth power split.

    Scope
    -----
    This is a Level-1 network EMT approximation. It includes SoC, aggregated
    open-circuit voltage, internal resistance and efficiency. It does not include
    cell electrochemistry, balancing, thermal behaviour, degradation, a detailed
    BMS, or a bidirectional DC-DC converter. A future Level-2 model can replace
    this block by an averaged DC-DC stage while keeping the imported VSC/control
    blocks unchanged.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Battery-side EMT block.
    """
    # ------------------------------------------------------------------
    # Inputs from the imported VSC block.
    # ------------------------------------------------------------------
    i_dc = vf.add_var(name=f"i_dc_bat_in_{name}")

    # ------------------------------------------------------------------
    # Battery state and derivative.
    # ------------------------------------------------------------------
    soc = vf.add_var(name=f"soc_{name}")
    d_soc = vf.add_diff_var(name=f"d_soc_{name}", base_var=soc)

    # ------------------------------------------------------------------
    # Algebraic battery variables.
    # ------------------------------------------------------------------
    v_dc_bus = vf.add_var(name=f"v_dc_bus_bat_{name}", reference=VarPowerFlowRefferenceType.Vdc)
    v_oc = vf.add_var(name=f"v_oc_bat_{name}")
    i_bat = vf.add_var(name=f"i_bat_{name}")
    p_bat = vf.add_var(name=f"p_bat_{name}")
    p_dis = vf.add_var(name=f"p_dis_bat_{name}")
    p_ch = vf.add_var(name=f"p_ch_bat_{name}")

    # ------------------------------------------------------------------
    # Local battery parameters.
    # ------------------------------------------------------------------
    e_cap = vf.add_var(name=f"e_cap_bat_{name}")
    v_min = vf.add_var(name=f"v_min_bat_{name}")
    v_max = vf.add_var(name=f"v_max_bat_{name}")
    r_bat = vf.add_var(name=f"r_bat_{name}")
    eta_ch = vf.add_var(name=f"eta_ch_bat_{name}")
    eta_dis = vf.add_var(name=f"eta_dis_bat_{name}")
    soc_min = vf.add_var(name=f"soc_min_bat_{name}")
    soc_max = vf.add_var(name=f"soc_max_bat_{name}")
    soc0 = vf.add_var(name=f"soc0_bat_{name}")

    c0 = vf.add_const(0.0)
    c1 = vf.add_const(1.0)
    c_half = vf.add_const(0.5)
    eps = vf.add_const(1e-10)

    soc_limited: Expr = sym.hard_sat(soc, soc_min, soc_max)
    p_abs: Expr = sym.sqrt(p_bat * p_bat + eps)
    p_dis_expr: Expr = c_half * (p_bat + p_abs)
    p_ch_expr: Expr = c_half * (-p_bat + p_abs)

    return Block(
        state_eqs=[
            # Positive battery power discharges the battery; negative power
            # charges it. Efficiencies are applied on the energy side.
            (-p_dis / (eta_dis + eps) + eta_ch * p_ch) / (e_cap + eps),
        ],
        state_vars=[soc],
        diff_vars=[d_soc],
        algebraic_eqs=[
            # Smooth SoC-dependent open-circuit voltage.
            v_oc - (v_min + (v_max - v_min) * soc_limited),
            # The VSC DC terminal current is the battery current in this
            # one-stage Level-1 model.
            i_bat - i_dc,
            # Resistive Thevenin terminal relation feeding the VSC DC bus.
            v_dc_bus - (v_oc - r_bat * i_bat),
            # Battery terminal power, positive when discharging.
            p_bat - v_dc_bus * i_bat,
            # Smooth discharge and charge power components.
            p_dis - p_dis_expr,
            p_ch - p_ch_expr,
        ],
        algebraic_vars=[v_dc_bus, v_oc, i_bat, p_bat, p_dis, p_ch],
        event_dict={
            e_cap: vf.add_const(10.0),
            v_min: vf.add_const(0.80),
            v_max: vf.add_const(1.20),
            r_bat: vf.add_const(0.02),
            eta_ch: vf.add_const(0.96),
            eta_dis: vf.add_const(0.96),
            soc_min: vf.add_const(0.05),
            soc_max: vf.add_const(0.95),
            soc0: vf.add_const(0.50),
        },
        init_eqs={
            soc: soc0,
            v_oc: v_min + (v_max - v_min) * soc0,
            i_bat: c0,
            v_dc_bus: c1,
            p_bat: c0,
            p_dis: c0,
            p_ch: c0,
        },
        diff_init_eqs={d_soc: c0},
        in_vars=[i_dc],
        out_vars=[v_dc_bus, soc, v_oc, i_bat, p_bat, p_dis, p_ch],
        name=f"{name}_battery",
    )


def get_bess_avm_grid_following_emt_template(
    vf: VarFactory,
    name: str = "bess_avm_grid_following_emt",
) -> EmtModelTemplate:
    """
    Build a Level-1 averaged-value grid-following BESS EMT template.

    This template assembles an aggregated Battery Energy Storage System by
    reusing the existing pseudo-EMT converter blocks from
    ``converter_emt_template.py`` and adding only the BESS-specific storage
    block. The goal is to avoid duplicating PLL, VSC, outer-loop, inner-loop and
    dq0/abc interface logic that already exists in the standard VeraGrid
    converter template.

    Physical structure
    ------------------
    The assembled model is::

        battery Thevenin equivalent + SoC
            -> VSC DC terminal
            -> imported VSC/DC-link block
            -> imported SRF-PLL
            -> imported outer Vdc/Q or P/Q loop
            -> imported inner dq0 current controller
            -> imported AC-side L/R dq0 interface
            -> abc current injection into the EMT network

    The battery block provides the DC terminal voltage consumed by the imported
    VSC block. The imported VSC block still owns the internal DC-link capacitor
    and converter power/loss equations. This avoids having two DC-link
    capacitors in the same BESS model.

    Included behaviour
    ------------------
    * Aggregated SoC state.
    * SoC-dependent open-circuit voltage.
    * Battery internal resistance.
    * Charge/discharge efficiencies.
    * Existing averaged VSC power balance and DC-link dynamics.
    * Existing PLL, dq0 current control, current limiting and modulation limit.
    * Existing dq0-to-abc network current injection.

    Not included
    ------------
    * Switching-level PWM or semiconductor devices.
    * Cell-level electrochemistry, thermal behaviour or degradation.
    * Detailed BMS and cell balancing.
    * Bidirectional DC-DC converter stage.
    * Additional plant-level PPC logic beyond the imported converter controls.

    Sign convention
    ---------------
    Positive AC active power follows the existing pseudo-EMT converter
    convention. Positive battery power means the battery discharges into the
    converter DC side and SoC decreases.

    :param vf: EMT symbolic variable factory.
    :param name: Symbolic model name.
    :return: Fully assembled EMT BESS template.
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name
    templ.block.name = name

    # ------------------------------------------------------------------
    # Network-facing AC terminal variables. The BESS is modelled as an AC
    # device with an internal battery, so the DC bus voltage is produced by the
    # battery block rather than received from an external DC network.
    # ------------------------------------------------------------------
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowRefferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowRefferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowRefferenceType.v_C)

    # ------------------------------------------------------------------
    # Imported converter/control blocks.
    # ------------------------------------------------------------------
    vsc_block = _build_pseudo_emt_converter_vsc_block(vf=vf, name=name)
    pll_block = _build_pseudo_emt_converter_pll_block(vf=vf, name=name)
    outer_loop_block = _build_pseudo_emt_converter_outer_loop_block(vf=vf, name=name)
    inner_loop_block = _build_pseudo_emt_converter_inner_loop_block(vf=vf, name=name)
    transformer_block = _build_pseudo_emt_converter_transformer_block(vf=vf, name=name)

    # ------------------------------------------------------------------
    # New BESS-specific block.
    # ------------------------------------------------------------------
    battery_block = get_battery_avm_emt_template(vf=vf, name=name)

    # ------------------------------------------------------------------
    # Wiring copied from the existing full pseudo-EMT converter assembly, with
    # only one change: the VSC DC terminal input is connected to the battery
    # block output instead of an external DC bus variable.
    # ------------------------------------------------------------------
    transformer_block.connect(transformer_block.in_vars[0:3], [v_A, v_B, v_C])
    vsc_block.connect([vsc_block.in_vars[6]], [battery_block.out_vars[0]])

    # The VSC DC terminal current is fed back to the battery block so the SoC
    # and Thevenin terminal voltage follow the converter operating point.
    battery_block.connect([battery_block.in_vars[0]], [vsc_block.out_vars[1]])

    # Transformer/interface provides dq0 voltages and currents to the VSC and
    # the control hierarchy.
    vsc_block.connect(vsc_block.in_vars[0:3], transformer_block.out_vars[6:9])
    vsc_block.connect(vsc_block.in_vars[3:6], transformer_block.out_vars[3:6])
    pll_block.connect([pll_block.in_vars[0]], [transformer_block.out_vars[7]])
    outer_loop_block.connect(outer_loop_block.in_vars[0:6], transformer_block.out_vars[6:12])
    inner_loop_block.connect(inner_loop_block.in_vars[0:3], transformer_block.out_vars[6:9])
    inner_loop_block.connect(inner_loop_block.in_vars[3:6], transformer_block.out_vars[3:6])

    # VSC block exports physical quantities and parameters used by the controls.
    pll_block.connect(
        pll_block.in_vars[1:5],
        [vsc_block.out_vars[8], vsc_block.out_vars[16], vsc_block.out_vars[17], vsc_block.out_vars[9]],
    )
    outer_loop_block.connect(
        [outer_loop_block.in_vars[6], outer_loop_block.in_vars[7], outer_loop_block.in_vars[8]],
        [vsc_block.out_vars[0], vsc_block.out_vars[2], vsc_block.out_vars[3]],
    )
    outer_loop_block.connect(
        outer_loop_block.in_vars[9:22],
        [
            vsc_block.out_vars[4],
            vsc_block.out_vars[5],
            vsc_block.out_vars[6],
            vsc_block.out_vars[7],
            vsc_block.out_vars[10],
            vsc_block.out_vars[26],
            vsc_block.out_vars[20],
            vsc_block.out_vars[21],
            vsc_block.out_vars[22],
            vsc_block.out_vars[23],
            vsc_block.out_vars[24],
            vsc_block.out_vars[29],
            vsc_block.out_vars[30],
        ],
    )
    inner_loop_block.connect(
        [inner_loop_block.in_vars[6], inner_loop_block.in_vars[7], inner_loop_block.in_vars[8], inner_loop_block.in_vars[9]],
        [pll_block.out_vars[1], vsc_block.out_vars[8], vsc_block.out_vars[11], vsc_block.out_vars[12]],
    )
    inner_loop_block.connect(inner_loop_block.in_vars[10:13], outer_loop_block.out_vars[2:5])
    inner_loop_block.connect(
        inner_loop_block.in_vars[13:25],
        [
            vsc_block.out_vars[18],
            vsc_block.out_vars[19],
            vsc_block.out_vars[30],
            vsc_block.out_vars[25],
            vsc_block.out_vars[7],
            vsc_block.out_vars[0],
            vsc_block.out_vars[31],
            vsc_block.out_vars[4],
            vsc_block.out_vars[5],
            vsc_block.out_vars[6],
            vsc_block.out_vars[26],
            vsc_block.out_vars[10],
        ],
    )

    # Controller outputs drive the AC interface dynamics.
    transformer_block.connect([transformer_block.in_vars[3], transformer_block.in_vars[4]], pll_block.out_vars)
    transformer_block.connect(
        transformer_block.in_vars[5:8],
        [vsc_block.out_vars[8], vsc_block.out_vars[11], vsc_block.out_vars[12]],
    )
    transformer_block.connect(transformer_block.in_vars[8:11], inner_loop_block.out_vars)
    transformer_block.connect(
        transformer_block.in_vars[11:16],
        [vsc_block.out_vars[4], vsc_block.out_vars[5], vsc_block.out_vars[6], vsc_block.out_vars[26], vsc_block.out_vars[10]],
    )

    # ------------------------------------------------------------------
    # Unified model assembly.
    # ------------------------------------------------------------------
    templ.block.children.extend([
        battery_block,
        vsc_block,
        pll_block,
        inner_loop_block,
        outer_loop_block,
        transformer_block,
    ])
    templ.block.unify_blocks()
    templ.block.in_vars = [v_A, v_B, v_C]
    templ.block.out_vars = [
        transformer_block.out_vars[0],
        transformer_block.out_vars[1],
        transformer_block.out_vars[2],
        vsc_block.out_vars[1],
        battery_block.out_vars[1],
        battery_block.out_vars[4],
    ]

    # ------------------------------------------------------------------
    # External mapping for EmtProblemDae.
    # ------------------------------------------------------------------
    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,
        # The BESS has an internal battery/DC source. Do not expose an external
        # DC-voltage network port here, otherwise the EMT assembler tries to
        # connect an additional DC-network equation to an internal algebraic
        # variable and the compiled DAE can become non-square.
        VarPowerFlowRefferenceType.i_A: transformer_block.out_vars[0],
        VarPowerFlowRefferenceType.i_B: transformer_block.out_vars[1],
        VarPowerFlowRefferenceType.i_C: transformer_block.out_vars[2],
        # Idc is internal to the BESS battery/VSC coupling. The AC network only
        # sees the three-phase current injection.
        VarPowerFlowRefferenceType.P: vsc_block.out_vars[2],
        VarPowerFlowRefferenceType.Q: vsc_block.out_vars[3],
        VarPowerFlowRefferenceType.phi_v: vsc_block.out_vars[9],
        VarPowerFlowRefferenceType.Vpk: vsc_block.out_vars[10],
    }

    # The static/API mapping remains exactly the one expected by the imported
    # VSC block, so existing converter initialization code can keep working.
    templ.block.api_obj_mapping = dict(vsc_block.api_obj_mapping)

    return templ

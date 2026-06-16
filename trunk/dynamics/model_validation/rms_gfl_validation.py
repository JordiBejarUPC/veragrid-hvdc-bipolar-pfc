#!/usr/bin/env python3
"""
RMS validation using Grid 2 topology with TrafoGFL + simple VSC RMS model.

Topology:
AC Bus 1 -> Transformer (TrafoGFL) -> AC Bus 3 -> VSC -> DC Bus 2
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import numpy as np
import matplotlib.pyplot as plt
import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import ConverterControlType, VarPowerFlowReferenceType
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Templates.Rms.vsc_gfl_dclinked import build_vsc_rms
from VeraGridEngine.Templates.Rms.vsc_gfl import TrafoGflBuild
from VeraGridEngine.Templates.Rms.dc_voltage_source import DCPVSourceAveraged
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_zip_template import ZIPLoadBuild
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Utils.Symbolic.block import Block


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

    return None


def set_event_in_block(var, value, vf, block: Block) -> bool:
    if var in block.event_dict:
        block.event_dict[var] = vf.add_const(value)
        return True
    for mdl in block.children:
        if set_event_in_block(var, value, vf, mdl):
            return True
    return False


def get_event_value_by_name(block: Block, name: str):
    for var, eq in block.event_dict.items():
        if var.name == name and hasattr(eq, 'value'):
            return eq.value
    for mdl in block.children:
        val = get_event_value_by_name(mdl, name)
        if val is not None:
            return val
    return None


def print_gfl_init_consistency(grid2, pf_results):
    if len(grid2.transformers2w) == 0 or len(grid2.vsc_devices) == 0:
        return

    trafo = grid2.transformers2w[0]
    vsc = grid2.vsc_devices[0]

    bus_names = [b.name for b in grid2.buses]
    idx_f = bus_names.index(trafo.bus_from.name)
    idx_t = bus_names.index(trafo.bus_to.name)

    vm_f = np.abs(pf_results.voltage[idx_f])
    va_f = np.angle(pf_results.voltage[idx_f])
    vm_t = np.abs(pf_results.voltage[idx_t])
    va_t = np.angle(pf_results.voltage[idx_t])

    # For TrafoGflBuild initialization, P/Q are tied to transformer "to" side
    # (VarPowerFlowReferenceType.Pt/Qt on the transformer model), not St_vsc.
    branch_list = list(grid2.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))
    branch_idx = branch_list.index(trafo)
    pt_vsc = float(np.real(pf_results.St[branch_idx]) / grid2.Sbase)
    qt_vsc = float(np.imag(pf_results.St[branch_idx]) / grid2.Sbase)

    # Parameters used by build_gfl_converter_model defaults
    k_pq = get_event_value_by_name(trafo.rms_model, 'k_pq')
    R = get_event_value_by_name(trafo.rms_model, 'R')
    L = get_event_value_by_name(trafo.rms_model, 'L')
    if k_pq is None:
        k_pq = 1.5
    if R is None:
        R = 0.01
    if L is None:
        L = 0.05

    k_pq = 1.0
    R = 0.01
    L = 0.05

    P = -pt_vsc
    Q = -qt_vsc
    theta = va_t 
    omega = 1.0
    k = 1.0
    v_d_g = 0.0
    v_q_g = vm_t
    i_q = (1.0 / k_pq) * P / v_q_g
    i_d = (1.0 / k_pq) * Q / v_q_g

    # Estimate dq currents from transformer branch current phasor
    # using the same dq frame angle (theta = Va_t).
    i_d_from_if = None
    i_q_from_if = None
    i_d_from_it = None
    i_q_from_it = None
    if trafo in branch_list:
        branch_idx = branch_list.index(trafo)
        if branch_idx < len(pf_results.If):
            i_f = pf_results.If[branch_idx]
            i_d_from_if = np.abs(i_f) * np.sin(np.angle(i_f) - theta)
            i_q_from_if = np.abs(i_f) * np.cos(np.angle(i_f) - theta)
        if branch_idx < len(pf_results.It):
            i_t = pf_results.It[branch_idx]
            i_d_from_it = np.abs(i_t) * np.sin(np.angle(i_t) - theta)
            i_q_from_it = np.abs(i_t) * np.cos(np.angle(i_t) - theta)

    v_d_c_from_pq = v_d_g - ( R * i_d - omega * L * i_q)
    v_q_c_from_pq = v_q_g - (-R * i_q - omega * L * i_d)

    v_d_c_from_internal_bus = vm_f * np.sin(va_f - theta)
    v_q_c_from_internal_bus = vm_f * np.cos(va_f - theta)

    print("\n" + "-" * 70)
    print("GFL Init Consistency Check")
    print("-" * 70)
    print(f"  Vm_f={vm_f:.6f}, Va_f={va_f:.6f} rad, Vm_t={vm_t:.6f}, Va_t={va_t:.6f} rad")
    print(f"  Pt_vsc={pt_vsc:.6f}, Qt_vsc={qt_vsc:.6f} -> P={P:.6f}, Q={Q:.6f}")
    print(f"  k_pq={k_pq:.6f}, R={R:.6f}, L={L:.6f}, omega={omega:.6f}")
    print(f"  i_d={i_d:.6f}, i_q={i_q:.6f}")
    if i_d_from_if is not None and i_q_from_if is not None:
        print(f"  i_d/i_q from If phasor = {i_d_from_if:.6f}, {i_q_from_if:.6f}")
    if i_d_from_it is not None and i_q_from_it is not None:
        print(f"  i_d/i_q from It phasor = {i_d_from_it:.6f}, {i_q_from_it:.6f}")
    print(f"  v_d_c from P/Q init = {v_d_c_from_pq:.9f}")
    print(f"  v_q_c from P/Q init = {v_q_c_from_pq:.9f}")
    print(f"  v_d_c from internal bus = {v_d_c_from_internal_bus:.9f}")
    print(f"  v_q_c from internal bus = {v_q_c_from_internal_bus:.9f}")
    print(f"  mismatch dv_d = {v_d_c_from_pq - v_d_c_from_internal_bus:.6f}")
    print(f"  mismatch dv_q = {v_q_c_from_pq - v_q_c_from_internal_bus:.6f}")


def print_trafo_powerflow_equation_consistency(grid, pf_results):
    """Quick PF-side check for dq/trafo equations used in NUACTIS-style models."""
    if len(grid.transformers2w) == 0:
        return

    bus_names = [b.name for b in grid.buses]
    branches = list(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))

    print("\n" + "-" * 70)
    print("Trafo PF Equation Consistency (NUACTIS-style)")
    print("-" * 70)

    for trafo in grid.transformers2w:
        if trafo not in branches:
            continue

        bidx = branches.index(trafo)
        idx_f = bus_names.index(trafo.bus_from.name)
        idx_t = bus_names.index(trafo.bus_to.name)

        vm_f = float(np.abs(pf_results.voltage[idx_f]))
        va_f = float(np.angle(pf_results.voltage[idx_f]))
        vm_t = float(np.abs(pf_results.voltage[idx_t]))
        va_t = float(np.angle(pf_results.voltage[idx_t]))

        # Use branch "to" powers like NUACTIS Pt/Qt wiring in current setup
        pt = float(np.real(pf_results.St[bidx]) / grid.Sbase)
        qt = float(np.imag(pf_results.St[bidx]) / grid.Sbase)

        theta = va_t
        omega = 1.0
        r_traf = float(getattr(trafo, 'R', getattr(trafo, 'r', 0.01)))
        l_traf = float(getattr(trafo, 'X', getattr(trafo, 'x', 0.05)))

        vd = vm_f * np.sin(va_f - theta)
        vq = vm_f * np.cos(va_f - theta)

        # From P_act = -Pt, Q_act = -Qt with P_act=vq*iq+vd*id, Q_act=vq*id-vd*iq
        den = vd * vd + vq * vq + 1e-12
        iq = ((-pt) * vq - (-qt) * vd) / den
        id_ = ((-qt) * vq + (-pt) * vd) / den

        vd_c_from_rl = vd - r_traf * id_ + omega * l_traf * iq
        vq_c_from_rl = vq - r_traf * iq - omega * l_traf * id_

        vd_c_from_bus = vm_f * np.sin(va_f - theta)
        vq_c_from_bus = vm_f * np.cos(va_f - theta)

        print(f"  {trafo.name}:")
        print(f"    Pt={pt:.6f}, Qt={qt:.6f}, Vm_f={vm_f:.6f}, Vm_t={vm_t:.6f}")
        print(f"    id={id_:.6f}, iq={iq:.6f}, R={r_traf:.6f}, L={l_traf:.6f}")
        print(f"    RL v_d_c={vd_c_from_rl:.6f}, bus v_d={vd_c_from_bus:.6f}, mismatch={vd_c_from_rl - vd_c_from_bus:.6f}")
        print(f"    RL v_q_c={vq_c_from_rl:.6f}, bus v_q={vq_c_from_bus:.6f}, mismatch={vq_c_from_rl - vq_c_from_bus:.6f}")


def print_vsc_pf_loss_consistency(grid, pf_results):
    if len(grid.vsc_devices) == 0:
        return

    print("\n" + "-" * 70)
    print("VSC PF Loss Consistency")
    print("-" * 70)

    bus_names = [b.name for b in grid.buses]
    branches = list(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))
    for i, vsc in enumerate(grid.vsc_devices):
        if i >= len(pf_results.St_vsc):
            continue

        pf = float((pf_results.Pfp_vsc[i] + pf_results.Pfn_vsc[i]) / grid.Sbase)
        pt = float(np.real(pf_results.St_vsc[i]) / grid.Sbase)
        qt = float(np.imag(pf_results.St_vsc[i]) / grid.Sbase)

        vm_t = float(np.abs(pf_results.voltage[bus_names.index(vsc.bus_to.name)]))
        va_t = float(np.angle(pf_results.voltage[bus_names.index(vsc.bus_to.name)]))
        im_from_pq = float(np.sqrt(pt * pt + qt * qt) / (vm_t ))
        i_d_from_pq = float(qt / (vm_t + 1e-12))
        i_q_from_pq = float(pt / (vm_t + 1e-12))
        im_from_idiq_pq = float(np.sqrt(i_d_from_pq * i_d_from_pq + i_q_from_pq * i_q_from_pq))

        im_from_it = np.nan
        if hasattr(pf_results, 'It_vsc') and i < len(pf_results.It_vsc):
            im_from_it = float(np.abs(pf_results.It_vsc[i]) / grid.Sbase)

        im_from_branch = np.nan
        im_from_idiq_branch = np.nan
        branch_i_max = 0.0
        branch_i_max_cplx = None
        for bidx, br in enumerate(branches):
            if br.bus_from.idtag == vsc.bus_to.idtag and bidx < len(pf_results.If):
                i_cplx = pf_results.If[bidx]
                i_abs = float(np.abs(i_cplx))
                if i_abs > branch_i_max:
                    branch_i_max = i_abs
                    branch_i_max_cplx = i_cplx
            if br.bus_to.idtag == vsc.bus_to.idtag and bidx < len(pf_results.It):
                i_cplx = pf_results.It[bidx]
                i_abs = float(np.abs(i_cplx))
                if i_abs > branch_i_max:
                    branch_i_max = i_abs
                    branch_i_max_cplx = i_cplx
        if branch_i_max > 0.0:
            im_from_branch = branch_i_max
        if branch_i_max_cplx is not None:
            i_d_branch = float(np.abs(branch_i_max_cplx) * np.sin(np.angle(branch_i_max_cplx) - va_t))
            i_q_branch = float(np.abs(branch_i_max_cplx) * np.cos(np.angle(branch_i_max_cplx) - va_t))
            im_from_idiq_branch = float(np.sqrt(i_d_branch * i_d_branch + i_q_branch * i_q_branch))

        im_used = im_from_it if np.isfinite(im_from_it) and im_from_it > 0 else im_from_pq
        p_loss = float(vsc.alpha1 + vsc.alpha2 * im_used + vsc.alpha3 * im_used * im_used)
        residual = pf + pt - p_loss
        residual_branch = np.nan
        if np.isfinite(im_from_branch) and im_from_branch > 0:
            p_loss_branch = float(vsc.alpha1 + vsc.alpha2 * im_from_branch + vsc.alpha3 * im_from_branch * im_from_branch)
            residual_branch = pf + pt - p_loss_branch

        print(f"  {vsc.name}:")
        print(f"    Pf={pf:.9f}, Pt={pt:.9f}, Qt={qt:.9f}, Vm_to={vm_t:.9f}")
        print(f"    Im(PQ/V)={im_from_pq:.9f}, Im(|It_vsc|)={im_from_it:.9f}, Im(branch)={im_from_branch:.9f}, Im(used)={im_used:.9f}")
        print(f"    Im(i_d,i_q from P/Q)={im_from_idiq_pq:.9f}, Im(i_d,i_q from branch)={im_from_idiq_branch:.9f}")
        print(f"    Loss(alpha)={p_loss:.9f}, residual Pf+Pt-loss(It_vsc)={residual:.9e}")
        print(f"    residual Pf+Pt-loss(branch)={residual_branch:.9e}")

def create_grid_2():
    circuit = vge.MultiCircuit(name='Grid 2 - Transformer + GFL VSC')

    bus1_ac = vge.Bus(name='Bus 1 (AC)', Vnom=230.0, is_slack=True)
    bus3_ac = vge.Bus(name='Bus 1_1 (AC)', Vnom=230.0)
    bus4_ac = vge.Bus(name='Bus 4 (AC)', Vnom=230.0)
    bus2_dc = vge.Bus(name='Bus 2 (DC)', Vnom=320.0, is_dc=True)
    circuit.add_bus(bus1_ac)
    circuit.add_bus(bus3_ac)
    circuit.add_bus(bus4_ac)
    circuit.add_bus(bus2_dc)
    

    gen1 = vge.Generator(name='Generator', P=10.0, vset=0.98)
    circuit.add_generator(bus1_ac, gen1)

    dc_load = vge.Generator(name='DC Load', P=4)
    circuit.add_generator(bus2_dc, dc_load)

    ac_load = vge.Load(name='AC Load', P=3.0, Q=0.0)
    circuit.add_load(bus=bus4_ac, api_obj=ac_load)

    transformer = vge.Transformer2W(
        name='Transformer',
        bus_from=bus3_ac,
        bus_to=bus1_ac,
        rate=100.0,
        r=0.01,
        x=0.05,
    )
    circuit.add_transformer2w(transformer)

    line34 = vge.Line(
        name='Line 3-4',
        bus_from=bus3_ac,
        bus_to=bus4_ac,
        r=0.02,
        x=0.08,
        b=0.0,
        rate=100.0,
    )
    circuit.add_line(line34)

    vsc = vge.VSC(
        name='VSC',
        bus_from=bus2_dc,
        bus_to=bus3_ac,
        rate=100.0,
        control1=ConverterControlType.Pac,
        control2=ConverterControlType.Vm_dc,
        control1_val=1.0,
        control2_val=1.02,
    )
    circuit.add_vsc(vsc)

    return circuit


def run_power_flow(circuit, grid_name):
    print(f"\nRunning Power Flow on {grid_name}...")
    pf_options = vge.PowerFlowOptions(
        solver_type=SolverType.NR,
        verbose=True,
        retry_with_other_methods=True,
        max_iter=100,
        tolerance=1e-11,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    return vge.power_flow(grid=circuit, options=pf_options)


def initialize_grid2_rms_models(grid2, pf_results):
    print("\n" + "-" * 70)
    print("Initializing RMS Models for Grid 2 with TrafoGFL + simple VSC model")
    print("-" * 70)

    vf = grid2.var_factory

    for bus in grid2.buses:
        if bus.rms_model.empty():
            initialize_bus_rms(bus, vf)

    for vsc in grid2.vsc_devices:
        print(f"  Initializing VSC '{vsc.name}' with build_vsc_rms...")
        vsc.rms_model = build_vsc_rms(vfactory=vf, name=vsc.name).block

        if len(pf_results.St_vsc) > 0:
            vsc_idx = list(grid2.vsc_devices).index(vsc)
            if vsc_idx < len(pf_results.St_vsc):
                qt_ref = find_name_in_block('Qt_ref', vsc.rms_model)
                if qt_ref is not None:
                    qt_pf = float(np.imag(pf_results.St_vsc[vsc_idx]) / grid2.Sbase)
                    set_event_in_block(qt_ref, qt_pf, vf, vsc.rms_model)

        if vsc.bus_to.rms_model.empty():
            initialize_bus_rms(vsc.bus_to, vf)
        vm_vsc = vsc.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
        bus_vm = vsc.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
        grid2.var_factory.add_connections([vm_vsc], [bus_vm])
        print("    ✓ VSC RMS model assigned")

    for trafo in grid2.transformers2w:
        print(f"  Initializing Transformer '{trafo.name}' with TrafoGflBuild...")
        trafo.rms_model = TrafoGflBuild(
            vfactory=vf,
            name=trafo.name,
            control1=ConverterControlType.Vm_dc,
            control2=ConverterControlType.Qac,
        ).block
        trafo.rms_model.unify_blocks()

        kp_vdc_var = find_name_in_block('Kp_vdc', trafo.rms_model)
        ki_vdc_var = find_name_in_block('Ki_vdc', trafo.rms_model)
        if kp_vdc_var is not None:
            set_event_in_block(kp_vdc_var, 0.01, vf, trafo.rms_model)
        if ki_vdc_var is not None:
            set_event_in_block(ki_vdc_var, 0.006, vf, trafo.rms_model)
        if kp_vdc_var is not None or ki_vdc_var is not None:
            print("    - Tuned Vdc PI gains: Kp_vdc=0.01, Ki_vdc=0.006")

        if trafo.bus_from.rms_model.empty():
            initialize_bus_rms(trafo.bus_from, vf)
        if trafo.bus_to.rms_model.empty():
            initialize_bus_rms(trafo.bus_to, vf)

        vm_f = trafo.rms_model.external_mapping[VarPowerFlowReferenceType.Vmf]
        va_f = trafo.rms_model.external_mapping[VarPowerFlowReferenceType.Vaf]
        vm_t = trafo.rms_model.external_mapping[VarPowerFlowReferenceType.Vmt]
        va_t = trafo.rms_model.external_mapping[VarPowerFlowReferenceType.Vat]

        bus_vm_f = trafo.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
        bus_va_f = trafo.bus_from.rms_model.external_mapping[VarPowerFlowReferenceType.Va]
        bus_vm_t = trafo.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
        bus_va_t = trafo.bus_to.rms_model.external_mapping[VarPowerFlowReferenceType.Va]

        grid2.var_factory.add_connections([vm_f, va_f, vm_t, va_t], [bus_vm_f, bus_va_f, bus_vm_t, bus_va_t])

        # Force TrafoGFL reactive initialization to match PF branch "to" side.
        branch_list = list(grid2.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))
        if trafo in branch_list:
            branch_idx = branch_list.index(trafo)
            qt_pf = pf_results.St[branch_idx].imag / grid2.Sbase
            qt_var = trafo.rms_model.external_mapping[VarPowerFlowReferenceType.Qt]
            trafo.rms_model.init_eqs[qt_var] = vf.add_const(float(qt_pf))

            q_ref_var = find_name_in_block('Q_ref', trafo.rms_model)
            if q_ref_var is not None:
                set_event_in_block(q_ref_var, float(-qt_pf), vf, trafo.rms_model)
        print("    ✓ Transformer RMS model assigned")

    for line in grid2.lines:
        print(f"  Initializing AC Line '{line.name}' with RMS line model...")
        line.rms_model = get_line_rms_template(vf, name=line.name).block
        set_rms_model(device=line, model=line.rms_model, var_factory=vf)
        print("    ✓ AC line RMS model assigned")

    for gen in grid2.generators:
        bus = gen.bus
        if bus.is_dc:
            print(f"  Initializing DC Generator '{gen.name}' at DC bus '{bus.name}' with DCPVSourceAveraged...")
            if bus.rms_model.empty():
                initialize_bus_rms(bus, vf)
            vdc = bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]
            gen.rms_model = DCPVSourceAveraged(vfactory=vf, Vdc=vdc, name=gen.name).block

            vdc0 = float(np.abs(pf_results.voltage[list(grid2.buses).index(bus)]))
            pdc0 = float(gen.P) / grid2.Sbase
            eta0 = 0.98
            vmp0 = max(0.8 * vdc0, min(0.98 * vdc0, vdc0 - 1e-3))
            ratio = max(vmp0 / (vdc0 + 1e-6), 1e-3)
            isc0 = max(abs(pdc0) / (eta0 * ratio + 1e-6), 1e-4)

            cdc_var = find_name_in_block('Cdc', gen.rms_model)
            eta_var = find_name_in_block('eta_boost', gen.rms_model)
            vmp_var = find_name_in_block('Vmp_stc', gen.rms_model)
            isc_var = find_name_in_block('Isc_stc', gen.rms_model)
            eps_v_var = find_name_in_block('eps_v', gen.rms_model)
            g_var = find_name_in_block('G', gen.rms_model)
            t_var = find_name_in_block('T', gen.rms_model)
            if cdc_var is not None:
                set_event_in_block(cdc_var, 0.10, vf, gen.rms_model)
            if eta_var is not None:
                set_event_in_block(eta_var, eta0, vf, gen.rms_model)
            if vmp_var is not None:
                set_event_in_block(vmp_var, vmp0, vf, gen.rms_model)
            if isc_var is not None:
                set_event_in_block(isc_var, isc0, vf, gen.rms_model)
            if eps_v_var is not None:
                set_event_in_block(eps_v_var, 1e-6, vf, gen.rms_model)
            if g_var is not None:
                set_event_in_block(g_var, 1000.0, vf, gen.rms_model)
            if t_var is not None:
                set_event_in_block(t_var, 25.0, vf, gen.rms_model)

            print(f"    - Tuned PV DC source: Cdc=0.10, eta_boost={eta0:.3f}, Vmp_stc={vmp0:.4f}, Isc_stc={isc0:.4f}")
            print("    ✓ DC Generator RMS model assigned")
        else:
            print(f"  Initializing AC Generator '{gen.name}' at AC bus '{bus.name}'...")
            if bus.rms_model.empty():
                initialize_bus_rms(bus, vf)
            gen_model = get_complete_generator_template_rms(vfactory=vf, name=gen.name).block
            set_rms_model(device=gen, model=gen_model, var_factory=vf)

    for load in grid2.get_loads():
        print(f"  Initializing AC Load '{load.name}' with ZIP load model...")
        load_model = ZIPLoadBuild(
            vfactory=vf,
            name=load.name,
            Pl0=-float(load.P) / grid2.Sbase,
            Ql0=-float(load.Q) / grid2.Sbase,
        ).block
        set_rms_model(device=load, model=load_model, var_factory=vf)
        load_vm = load_model.external_mapping[VarPowerFlowReferenceType.Vm]
        bus_vm = load.bus.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
        grid2.var_factory.add_connections([load_vm], [bus_vm])
        print("    ✓ AC load RMS model assigned")

    if len(grid2.vsc_devices) > 0 and len(grid2.transformers2w) > 0:
        vsc = grid2.vsc_devices[0]
        trafo = grid2.transformers2w[0]
        if hasattr(vsc.bus_from, 'rms_model') and vsc.bus_from.rms_model is not None:
            if hasattr(trafo.rms_model, 'in_vars') and len(trafo.rms_model.in_vars) > 0:
                vdc_trafo = trafo.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]
                vdc_bus = vsc.bus_from.rms_model.out_vars[0]
                grid2.var_factory.add_connections([vdc_trafo], [vdc_bus])
                print("  ✓ Connected transformer to DC bus")

    print("  ✓ All RMS models initialized successfully")


def run_rms_simulation(grid2, pf_results):
    print("\n" + "-" * 70)
    print("Running RMS Dynamic Simulation on Grid 2")
    print("-" * 70)

    events_group = RmsEventsGroup(name="Grid2 RMS Simulation")
    grid2.add_rms_events_group(events_group)

    dc_gen = None
    for gen in grid2.generators:
        if gen.bus.is_dc:
            dc_gen = gen
            break

    if dc_gen is not None and dc_gen.rms_model is not None:
        g_var = find_name_in_block('G', dc_gen.rms_model)
        if g_var is not None:
            g0 = 1000.0
            g_target = 700.0
            ramp_times = [0.10, 0.12, 0.14, 0.16]
            for k, t_evt in enumerate(ramp_times, start=1):
                alpha = k / len(ramp_times)
                val = (1.0 - alpha) * g0 + alpha * g_target
                event = RmsEvent(
                    device=dc_gen,
                    parameter=g_var,
                    time=t_evt,
                    value=val,
                    group=events_group,
                )
                grid2.add_rms_event(event)
            print(f"  Added event: PV irradiance ramp G {g0:.1f} -> {g_target:.1f} W/m^2 from t=0.10s to t=0.16s")

    rms_options = vge.RmsOptions(
        simulation_time=10,
        time_step=0.01,
        max_iter=30,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
    )

    rms_driver = vge.RmsSimulationDriver(
        grid=grid2,
        options=rms_options,
        pf_results=pf_results,
        engine=vge.EngineType.VeraGrid,
    )

    rms_driver.run()
    results = rms_driver.results
    print(f"  ✓ RMS simulation complete (converged={results.converged})")

    plot_rms_results(grid2, results)


def plot_rms_results(grid2, results):
    print("\n" + "-" * 70)
    print("Plotting RMS Results")
    print("-" * 70)

    if results is None or results.values is None or len(results.time_array) == 0:
        print("  ⚠ No results to plot")
        return

    t_raw = np.array(results.time_array)
    if np.issubdtype(t_raw.dtype, np.datetime64):
        t = (t_raw - t_raw[0]) / np.timedelta64(1, 's')
        t = t.astype(float)
    else:
        t = t_raw.astype(float)
    y = results.values[:, :, 0]

    # Skip the final sample to keep plots available even if
    # the last integration step fails to converge.
    n_samples = min(len(t), y.shape[0])
    if n_samples == 0:
        print("  ⚠ No samples available to plot")
        return
    n_plot = n_samples - 0 if n_samples > 1 else n_samples
    t_plot = t[:n_plot]
    y_plot = y[:n_plot, :]
    uid2idx = results.uid2idx

    fig, axes = plt.subplots(5, 1, figsize=(12, 16))
    ax1, ax1_i, ax2, ax3, ax4 = axes

    trafo = grid2.transformers2w[0] if len(grid2.transformers2w) > 0 else None
    vsc = grid2.vsc_devices[0] if len(grid2.vsc_devices) > 0 else None
    dc_gen = next((g for g in grid2.generators if g.bus.is_dc), None)

    def plot_var(ax, block, var_name, label):
        var = find_name_in_block(var_name, block)
        if var is None:
            return False
        idx = uid2idx.get(var.uid)
        if idx is None:
            return False
        ax.plot(t_plot, y_plot[:, idx], label=label, linewidth=1.5)
        return True

    plotted1_v = False
    plotted1_i = False
    plotted2 = False
    plotted3 = False
    plotted4 = False

    if trafo is not None and trafo.rms_model is not None:
        plotted1_v |= plot_var(ax1, trafo.rms_model, 'v_d_c', 'v_d_c')
        plotted1_v |= plot_var(ax1, trafo.rms_model, 'v_q_c', 'v_q_c')
        plotted1_v |= plot_var(ax1, trafo.rms_model, 'y_vd_hat', 'vd_hat')
        plotted1_v |= plot_var(ax1, trafo.rms_model, 'y_vq_hat', 'vq_hat')

        plotted1_i |= plot_var(ax1_i, trafo.rms_model, 'i_d', 'i_d')
        plotted1_i |= plot_var(ax1_i, trafo.rms_model, 'i_q', 'i_q')
        plotted1_i |= plot_var(ax1_i, trafo.rms_model, 'i_d_ref', 'i_d_ref')
        plotted1_i |= plot_var(ax1_i, trafo.rms_model, 'i_q_ref', 'i_q_ref')
        plotted1_i |= plot_var(ax1_i, trafo.rms_model, 'i_d_ref_sat', 'i_d_ref_sat')
        plotted1_i |= plot_var(ax1_i, trafo.rms_model, 'i_q_ref_sat', 'i_q_ref_sat')

        plotted2 |= plot_var(ax2, trafo.rms_model, 'Pf_vsc_control', 'Pf_vsc_control')
        plotted2 |= plot_var(ax2, trafo.rms_model, 'Pt_vsc_control', 'Pt_vsc_control')
        plotted2 |= plot_var(ax2, trafo.rms_model, 'Qt_vsc_control', 'Qt_vsc_control')

    if vsc is not None and vsc.rms_model is not None:
        plotted2 |= plot_var(ax2, vsc.rms_model, 'Pf_vsc', 'Pf_vsc')
        plotted2 |= plot_var(ax2, vsc.rms_model, 'Pt', 'Pt')
        plotted4 |= plot_var(ax4, vsc.rms_model, 'Pf_vsc', 'Pf_vsc')

    if dc_gen is not None and dc_gen.rms_model is not None:
        plotted3 |= plot_var(ax3, dc_gen.rms_model, 'Idc', 'Idc')
        plotted3 |= plot_var(ax3, dc_gen.rms_model, 'Idc_src', 'Idc_src')
        plotted3 |= plot_var(ax3, dc_gen.rms_model, 'Pdc', 'Pdc')
        plotted3 |= plot_var(ax3, dc_gen.rms_model, 'duty', 'duty')
        plotted3 |= plot_var(ax3, dc_gen.rms_model, 'Ipv_av', 'Ipv_av')
        plotted4 |= plot_var(ax4, dc_gen.rms_model, 'Pdc', 'Pdc')
        if dc_gen.bus.rms_model is not None:
            plotted3 |= plot_var(ax3, dc_gen.bus.rms_model, 'Vdc', 'Vdc_bus')

    if plotted1_v:
        ax1.set_title('TrafoGFL dq Voltages')
        ax1.set_ylabel('Voltage (pu)')
        ax1.grid(True)
        ax1.legend(loc='upper right')

    if plotted1_i:
        ax1_i.set_title('TrafoGFL dq Currents')
        ax1_i.set_ylabel('Current (pu)')
        ax1_i.grid(True)
        ax1_i.legend(loc='upper right')

    if plotted2:
        ax2.set_title('Power Variables')
        ax2.set_ylabel('pu')
        ax2.grid(True)
        ax2.legend(loc='upper right')

    if plotted3:
        ax3.set_title('DC Variables')
        ax3.set_ylabel('pu')
        ax3.grid(True)
        ax3.legend(loc='upper right')
        ax3.axvline(x=0.1, color='red', linestyle=':', alpha=0.7)

    if plotted4:
        ax4.set_title('VSC Pf vs Pdc')
        ax4.set_xlabel('Time (s)')
        ax4.set_ylabel('pu')
        ax4.grid(True)
        ax4.legend(loc='upper right')
        ax4.axvline(x=0.1, color='red', linestyle=':', alpha=0.7)

    for ax in axes:
        ax.set_xlim([0, t_plot[-1]])

    print(f"  Time span plotted: 0.0 to {t_plot[-1]:.3f} s")

    plt.tight_layout()
    plt.show()
    plt.savefig('rms_gfl_validation_results.png', dpi=150)
    plt.close(fig)
    print("  ✓ Plot saved to rms_gfl_validation_results.png")


if __name__ == "__main__":
    print("=" * 70)
    print("INVERTER EXAMPLE: Transformer (TrafoGFL) + simple VSC RMS")
    print("=" * 70)

    grid2 = create_grid_2()
    results2 = run_power_flow(grid2, "Grid 2")

    if not results2.converged:
        print("\n✗ Grid 2 power flow did not converge")
        sys.exit(1)

    print("\n" + "-" * 70)
    print("Bus Voltages (Power Flow)")
    print("-" * 70)
    for i, bus in enumerate(grid2.buses):
        vm = np.abs(results2.voltage[i])
        va_deg = np.degrees(np.angle(results2.voltage[i]))
        bus_type = "DC" if bus.is_dc else "AC"
        print(f"  {bus.name:20s}: Vm={vm:.6f} pu, Va={va_deg:.4f} deg ({bus_type})")

    print("\n" + "-" * 70)
    print("Transformer Taps (Power Flow)")
    print("-" * 70)
    for trafo in grid2.transformers2w:
        print(f"  {trafo.name:20s}: tap_module={trafo.tap_module:.6f}, tap_phase={trafo.tap_phase:.6f} rad")

    print_vsc_pf_loss_consistency(grid2, results2)

    initialize_grid2_rms_models(grid2, results2)
    print_gfl_init_consistency(grid2, results2)
    print_trafo_powerflow_equation_consistency(grid2, results2)
    run_rms_simulation(grid2, results2)

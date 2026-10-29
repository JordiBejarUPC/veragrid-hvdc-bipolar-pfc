# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys
import numpy as np
import matplotlib.pyplot as plt

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
src_root = os.path.join(repo_root, "src")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if src_root not in sys.path:
    sys.path.insert(0, src_root)
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Templates.Rms.line_rms_template import get_dc_line_rms_template, get_line_rms_template
from VeraGridEngine.Templates.Rms.voltage_source_template import VoltageSourceBuild
from VeraGridEngine.Templates.Rms.vsc_gfl_dclinked import build_vsc_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod, ConverterControlType, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
import VeraGridEngine.api as gce

from trunk.nu_actis.nuactis_master_pwm_template_modified import build_trafo_master_block
from trunk.nu_actis.nuactis_slave_pwm_template_modified import build_trafo_slave_block, connect_rms_vsc_to_buses


def dump_grid_topology(grid, label: str):
    print(f"\n[DEBUG] {label}")
    print(f"transformers2w order ({len(grid.get_transformers2w())}):")
    for i, t in enumerate(grid.get_transformers2w()):
        print(f"  [{i}] {t.name}: {t.idtag[:8]} {t.bus_from.name}->{t.bus_to.name}")

    print("branch iterator order add_vsc=False/add_hvdc=False/add_switch=True:")
    for i, br in enumerate(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True)):
        print(f"  [{i}] {type(br).__name__} | {br.name} | {br.idtag[:8]}")


def print_nuactis_pf_consistency(grid, pf_results):
    """Check whether NUACTIS dq/trafo equations are compatible with PF point."""
    branches = list(grid.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True))
    bus_names = [b.name for b in grid.buses]

    print("\n" + "-" * 70)
    print("NUACTIS PF Equation Consistency")
    print("-" * 70)

    for trafo in [t for t in grid.transformers2w if t.rms_model is not None]:
        if trafo not in branches:
            continue

        bidx = branches.index(trafo)
        idx_f = bus_names.index(trafo.bus_from.name)
        idx_t = bus_names.index(trafo.bus_to.name)

        vm_f = float(np.abs(pf_results.voltage[idx_f]))
        va_f = float(np.angle(pf_results.voltage[idx_f]))
        vm_t = float(np.abs(pf_results.voltage[idx_t]))
        va_t = float(np.angle(pf_results.voltage[idx_t]))

        pt = float(np.real(pf_results.St[bidx]) / grid.Sbase)
        qt = float(np.imag(pf_results.St[bidx]) / grid.Sbase)

        theta = va_t
        omega = 1.0
        r_traf = float(getattr(trafo, 'r', 0.005))
        l_traf = 0.12

        vd_from_bus = vm_f * np.sin(va_f - theta)
        vq_from_bus = vm_f * np.cos(va_f - theta)
        vd_to_bus = vm_t * np.sin(va_t - theta)
        vq_to_bus = vm_t * np.cos(va_t - theta)

        v_q_g = vq_to_bus
        P = pt
        Q = qt
        k_pq = 1.0
        i_q = (1.0 / k_pq) * P / v_q_g
        i_d = (1.0 / k_pq) * Q / v_q_g


        i_d_from_if = None
        i_q_from_if = None
        i_d_from_it = None
        i_q_from_it = None
        if bidx < len(pf_results.If):
            i_f = pf_results.If[bidx]
            i_d_from_if = float(np.abs(i_f) * np.sin(np.angle(i_f) - theta))
            i_q_from_if = float(np.abs(i_f) * np.cos(np.angle(i_f) - theta))
        if bidx < len(pf_results.It):
            i_t = pf_results.It[bidx]
            i_d_from_it = float(np.abs(i_t) * np.sin(np.angle(i_t) - theta))
            i_q_from_it = float(np.abs(i_t) * np.cos(np.angle(i_t) - theta))

        vd_c_from_rl = vd_to_bus + (r_traf * i_d) - (omega * l_traf * i_q)
        vq_c_from_rl = vq_to_bus - (r_traf * i_q) - (omega * l_traf * i_d)

        vd_c_from_bus = vm_f * np.sin(va_f - theta)
        vq_c_from_bus = vm_f * np.cos(va_f - theta)

        print(f"  {trafo.name}:")
        print(f"    Pt={pt:.6f}, Qt={qt:.6f}, Vm_f={vm_f:.6f}, Vm_t={vm_t:.6f}")
        print(f"    i_d={i_d:.6f}, i_q={i_q:.6f}, R={r_traf:.6f}, L={l_traf:.6f}")
        print(f"    v_d={vd_to_bus:.6f}, v_q={vq_to_bus:.6f}")
        if i_d_from_if is not None and i_q_from_if is not None:
            print(f"    i_d/i_q from If phasor = {i_d_from_if:.6f}, {i_q_from_if:.6f} (dm={i_d - i_d_from_if:+.6f}, dq={i_q - i_q_from_if:+.6f})")
        if i_d_from_it is not None and i_q_from_it is not None:
            print(f"    i_d/i_q from It phasor = {i_d_from_it:.6f}, {i_q_from_it:.6f} (dm={i_d - i_d_from_it:+.6f}, dq={i_q - i_q_from_it:+.6f})")
        print(f"    v_d (from-bus closure) = {vd_from_bus:.6f}")
        print(f"    v_q (from-bus closure) = {vq_from_bus:.6f}")
        print(f"    v_d_c (RL, dt=0) = {vd_c_from_rl:.6f}, v_d_c (bus closure) = {vd_c_from_bus:.6f}, mismatch = {vd_c_from_rl - vd_c_from_bus:.6f}")
        print(f"    v_q_c (RL, dt=0) = {vq_c_from_rl:.6f}, v_q_c (bus closure) = {vq_c_from_bus:.6f}, mismatch = {vq_c_from_rl - vq_c_from_bus:.6f}")


def find_var_in_block(block, var_name: str):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.in_vars + block.out_vars:
        if var.name == var_name:
            return var

    for child in block.children:
        found = find_var_in_block(child, var_name)
        if found is not None:
            return found

    return None


def collect_var_names_in_block(block, names: set[str] | None = None):
    if names is None:
        names = set()

    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.in_vars + block.out_vars:
        names.add(var.name)

    for child in block.children:
        collect_var_names_in_block(child, names)

    return names


def collect_vars_in_block(block, vars_by_uid: dict[int, object] | None = None):
    if vars_by_uid is None:
        vars_by_uid = dict()

    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.in_vars + block.out_vars:
        vars_by_uid[var.uid] = var

    for child in block.children:
        collect_vars_in_block(child, vars_by_uid)

    return list(vars_by_uid.values())


def pick_solved_var(block, problem, preferred_exact: list[str] | None = None, preferred_contains: list[str] | None = None, exclude_contains: list[str] | None = None):
    preferred_exact = preferred_exact or []
    preferred_contains = preferred_contains or []
    exclude_contains = exclude_contains or []

    vars_all = collect_vars_in_block(block)
    solved_vars = [v for v in vars_all if v.uid in problem.uid2idx_vars]

    for target in preferred_exact:
        for var in solved_vars:
            if var.name == target:
                return var

    for token in preferred_contains:
        for var in solved_vars:
            if token in var.name and not any(ex in var.name for ex in exclude_contains):
                return var

    return None


def find_var_by_prefix_and_tag(block, prefix: str, tag: str):
    all_names = sorted(collect_var_names_in_block(block))

    exact_name = f"{prefix}_{tag}"
    var = find_var_in_block(block, exact_name)
    if var is not None:
        return var

    candidates = [name for name in all_names if name.startswith(prefix + "_") and tag in name]
    if len(candidates) > 0:
        return find_var_in_block(block, candidates[0])

    return None


def iter_blocks_recursive(block):
    yield block
    for child in block.children:
        yield from iter_blocks_recursive(child)


def get_control_internal_var(trafo_block, key: str):
    for blk in iter_blocks_recursive(trafo_block):
        internal = getattr(blk, "internal_vars", None)
        if isinstance(internal, dict) and key in internal:
            return internal[key]
    return None


def get_var_value_at(var, problem, y_values, sample_idx: int = -1):
    if var is None:
        return None
    var_idx = problem.uid2idx_vars.get(var.uid, None)
    if var_idx is None:
        return None
    return float(y_values[sample_idx, var_idx])


def print_control_blocks_outputs(trafo, problem, y_values, sample_idx: int = -1):
    print(f"\n[DEBUG] Control block outputs for {trafo.name}")
    control_block_tokens = ("Outer_ctrl_P", "Outer_ctrl_Q", "Current_Limiter", "Inner_ctrl_Current", "EPC_Block")

    for child in iter_blocks_recursive(trafo.rms_model):
        child_name = str(getattr(child, "name", ""))
        if not any(token in child_name for token in control_block_tokens):
            continue

        print(f"  - {child_name}:")
        for out_var in child.out_vars:
            value = get_var_value_at(out_var, problem, y_values, sample_idx)
            if value is None:
                print(f"      {out_var.name} = <not in solved vars>")
            else:
                print(f"      {out_var.name} = {value:.6f}")

    id_ref_lmtd_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_contains=["id_ref_lmtd_", "id_ref_"],
    )
    iq_ref_lmtd_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_contains=["iq_ref_lmtd_", "iq_ref_"],
    )
    id_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_exact=[f"id_{trafo.name}"],
        preferred_contains=["id_"],
        exclude_contains=["id_ref", "id_limit", "id_lim_cal"],
    )
    iq_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_exact=[f"iq_{trafo.name}"],
        preferred_contains=["iq_"],
        exclude_contains=["iq_ref", "iq_limit", "iq_lim_cal"],
    )

    id_target_val = get_var_value_at(id_ref_lmtd_var, problem, y_values, sample_idx)
    iq_target_val = get_var_value_at(iq_ref_lmtd_var, problem, y_values, sample_idx)
    id_val = get_var_value_at(id_var, problem, y_values, sample_idx)
    iq_val = get_var_value_at(iq_var, problem, y_values, sample_idx)

    if id_target_val is not None:
        print(f"  objective value (id target) = {id_target_val:.6f}")
    else:
        print("  objective value (id target) = <not available>")

    if iq_target_val is not None:
        print(f"  objective value (iq target) = {iq_target_val:.6f}")
    else:
        print("  objective value (iq target) = <not available>")

    if id_val is not None:
        print(f"  measured id = {id_val:.6f}")
    else:
        print("  measured id = <not available>")

    if iq_val is not None:
        print(f"  measured iq = {iq_val:.6f}")
    else:
        print("  measured iq = <not available>")

    if id_target_val is not None and id_val is not None:
        print(f"  id tracking error = {id_target_val - id_val:+.6e}")
    if iq_target_val is not None and iq_val is not None:
        print(f"  iq tracking error = {iq_target_val - iq_val:+.6e}")


def print_current_frame_sanity(trafo, problem, y_values, sample_idx: int = -1):
    print(f"\n[DEBUG] dq frame sanity for {trafo.name}")

    id_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_exact=[f"id_{trafo.name}"],
        preferred_contains=["id_"],
        exclude_contains=["id_ref", "id_limit", "id_lim_cal"],
    )
    iq_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_exact=[f"iq_{trafo.name}"],
        preferred_contains=["iq_"],
        exclude_contains=["iq_ref", "iq_limit", "iq_lim_cal"],
    )
    id_ctrl = get_var_value_at(id_var, problem, y_values, sample_idx)
    iq_ctrl = get_var_value_at(iq_var, problem, y_values, sample_idx)

    vmt = trafo.rms_model.external_mapping.get(VarPowerFlowReferenceType.Vmt, None)
    vat = trafo.rms_model.external_mapping.get(VarPowerFlowReferenceType.Vat, None)
    pt = trafo.rms_model.external_mapping.get(VarPowerFlowReferenceType.Pt, None)
    qt = trafo.rms_model.external_mapping.get(VarPowerFlowReferenceType.Qt, None)

    vm_t = get_var_value_at(vmt, problem, y_values, sample_idx)
    va_t = get_var_value_at(vat, problem, y_values, sample_idx)
    p_t = get_var_value_at(pt, problem, y_values, sample_idx)
    q_t = get_var_value_at(qt, problem, y_values, sample_idx)

    if None in (id_ctrl, iq_ctrl, vm_t, va_t, p_t, q_t) or abs(vm_t) < 1e-9:
        print("  could not compute sanity check (missing solved vars)")
        return

    v_t = vm_t * np.exp(1j * va_t)
    s_t = p_t + 1j * q_t
    i_t = np.conj(s_t / v_t)

    i_mag = float(np.abs(i_t))
    i_ang = float(np.angle(i_t))
    theta = float(va_t)
    id_from_phasor = i_mag * np.sin(i_ang - theta)
    iq_from_phasor = i_mag * np.cos(i_ang - theta)

    print(f"  controller id/iq = {id_ctrl:+.6f}, {iq_ctrl:+.6f}")
    print(f"  phasor    id/iq = {id_from_phasor:+.6f}, {iq_from_phasor:+.6f}  (from Pt/Qt at to-side)")
    print(f"  mismatch  id/iq = {id_ctrl - id_from_phasor:+.6e}, {iq_ctrl - iq_from_phasor:+.6e}")


grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# Buses
bus1 = gce.Bus(name="Bus1", Vnom=400, is_slack=True)
bus2 = gce.Bus(name="Bus2", Vnom=400)
bus2_1 = gce.Bus(name="Bus2_1", Vnom=520)
bus3 = gce.Bus(name="Bus3", Vnom=1013.5, is_dc=True)
bus4 = gce.Bus(name="Bus4", Vnom=1013.5, is_dc=True)
bus5_1 = gce.Bus(name="Bus5_1", Vnom=520)
bus5 = gce.Bus(name="Bus5", Vnom=400)
bus6 = gce.Bus(name="Bus6", Vnom=400, is_slack=True)

for bus in [bus1, bus2, bus2_1, bus3, bus4, bus5_1, bus5, bus6]:
    grid.add_bus(bus)

for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)

# External grids
generatorA = gce.Generator(name="Gen_Thev_A", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.3)
generatorB = gce.Generator(name="Gen_Thev_B", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.3)
grid.add_generator(bus1, generatorA)
grid.add_generator(bus6, generatorB)

# AC lines
lineA = gce.Line(name="L12", bus_from=bus1, bus_to=bus2, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
lineB = gce.Line(name="L56", bus_from=bus5, bus_to=bus6, r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
grid.add_line(lineA)
grid.add_line(lineB)

# Transformers
trafoA = gce.Transformer2W(
    name="Trafo_2_2_1",
    bus_from=bus2_1,
    bus_to=bus2,
    HV=520.0,
    LV=400.0,
    nominal_power=900.0,
    r=0.005,
    x=0.12,
    rate=900.0,
    tap_module=1.0,
    tap_phase=0.0,
)
trafoB = gce.Transformer2W(
    name="Trafo_5_1_5",
    bus_from=bus5_1,
    bus_to=bus5,
    HV=520.0,
    LV=400.0,
    nominal_power=900.0,
    r=0.005,
    x=0.12,
    rate=900.0,
    tap_module=1.0,
    tap_phase=0.0,
)
grid.add_transformer2w(trafoB)

grid.add_transformer2w(trafoA)
dump_grid_topology(grid, "after adding trafoA and trafoB")

# VSCs
p_transfer_mw = 30.0
q_transfer_mvar = 0.0


vsc_slave = gce.VSC(
    name="VSC_slave451",
    bus_from=bus4,
    bus_to=bus5_1,
    rate=100.0,
    control1=ConverterControlType.Qac,
    control2=ConverterControlType.Pac,
    control1_val=q_transfer_mvar,
    control2_val=p_transfer_mw,
)

vsc_master = gce.VSC(
    name="VSC_master213",
    bus_from=bus3,
    bus_to=bus2_1,
    rate=100.0,
    control1=ConverterControlType.Qac,
    control2=ConverterControlType.Vm_dc,
    control1_val=q_transfer_mvar,
    control2_val=1.0,
)
grid.add_vsc(vsc_master)
grid.add_vsc(vsc_slave)

# DC line
dc_line = gce.DcLine(name="DC_line", bus_from=bus3, bus_to=bus4, rate=900.0, r=0.001)
grid.add_dc_line(dc_line)

# Build RMS models
genA_mdl = VoltageSourceBuild(grid.var_factory, name=generatorA.name).block
genB_mdl = VoltageSourceBuild(grid.var_factory, name=generatorB.name).block

lineA_mdl = get_line_rms_template(grid.var_factory, name=lineA.name).block
lineB_mdl = get_line_rms_template(grid.var_factory, name=lineB.name).block
dc_line_mdl = get_dc_line_rms_template(grid.var_factory, name=dc_line.name).block

trafo_master_mdl = build_trafo_master_block(vfactory=grid.var_factory, name=trafoA.name).block
trafo_slave_mdl = build_trafo_slave_block(
    vfactory=grid.var_factory,
    name=trafoB.name,
    q_control_type=vsc_slave.control1,
).block

vsc_master_mdl = build_vsc_rms(vfactory=grid.var_factory, name=vsc_master.name).block
vsc_slave_mdl = build_vsc_rms(vfactory=grid.var_factory, name=vsc_slave.name).block

# Assign models
set_rms_model(device=generatorA, model=genA_mdl, var_factory=grid.var_factory)
set_rms_model(device=generatorB, model=genB_mdl, var_factory=grid.var_factory)
set_rms_model(device=lineA, model=lineA_mdl, var_factory=grid.var_factory)
set_rms_model(device=lineB, model=lineB_mdl, var_factory=grid.var_factory)

dc_line.rms_model = dc_line_mdl
trafoA.rms_model = trafo_master_mdl
trafoB.rms_model = trafo_slave_mdl
vsc_master.rms_model = vsc_master_mdl
vsc_slave.rms_model = vsc_slave_mdl

# Connect DC line to DC buses
dc_vm_f = dc_line.rms_model.external_mapping[VarPowerFlowReferenceType.Vmf]
dc_vm_t = dc_line.rms_model.external_mapping[VarPowerFlowReferenceType.Vmt]
bus3_vdc = bus3.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]
bus4_vdc = bus4.rms_model.external_mapping[VarPowerFlowReferenceType.Vdc]
grid.var_factory.add_connections([dc_vm_f, dc_vm_t], [bus3_vdc, bus4_vdc])

# Connect master/slave trafo-control models to buses
connect_rms_vsc_to_buses(
    vsc_model=trafoA.rms_model,
    controlled_bus_model=bus2_1.rms_model,
    grid_bus_model=bus2.rms_model,
    dc_bus_model=bus3.rms_model,
    var_factory=grid.var_factory,
)
connect_rms_vsc_to_buses(
    vsc_model=trafoB.rms_model,
    controlled_bus_model=bus5_1.rms_model,
    grid_bus_model=bus5.rms_model,
    dc_bus_model=bus4.rms_model,
    var_factory=grid.var_factory,
)

# Connect standalone VSC DC/link model to trafo-control outputs
for vsc_dev, trafo_model in [(vsc_master, trafoA.rms_model), (vsc_slave, trafoB.rms_model)]:
    im_trafo = trafo_model.external_mapping[VarPowerFlowReferenceType.Im]
    pf_trafo = trafo_model.external_mapping[VarPowerFlowReferenceType.Pf]
    vmf_trafo = trafo_model.external_mapping[VarPowerFlowReferenceType.Vmf]

    if len(vsc_dev.rms_model.in_vars) >= 2:
        grid.var_factory.add_connections(
            [vsc_dev.rms_model.in_vars[0], vsc_dev.rms_model.in_vars[1]],
            [im_trafo, pf_trafo],
        )
    elif len(vsc_dev.rms_model.in_vars) == 1:
        grid.var_factory.add_connections(
            [vsc_dev.rms_model.in_vars[0]],
            [vmf_trafo],
        )
    else:
        raise RuntimeError(f"Unexpected VSC model input count: {len(vsc_dev.rms_model.in_vars)}")


options = gce.PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=0,
    initialize_with_existing_solution=True,
    tolerance=1e-10,
    max_iter=30,
    control_q=False,
    control_taps_modules=True,
    control_taps_phase=True,
    control_remote_voltage=True,
    orthogonalize_controls=True,
    apply_temperature_correction=True,
    branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=False,
    generate_report=False,
)

res = gce.power_flow(grid, options=options)
print(f"Converged? {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())
print_nuactis_pf_consistency(grid, res)

# Ensure voltage-source generator references are numerically initialized from PF.
for gen_dev in [generatorA, generatorB]:
    bus_idx = next(i for i, b in enumerate(grid.buses) if b is gen_dev.bus)
    vm0 = float(np.abs(res.voltage[bus_idx]))
    va0 = float(np.angle(res.voltage[bus_idx]))

    vg0_var = next((v for v in gen_dev.rms_model.event_dict.keys() if v.name == "Vg0"), None)
    ag0_var = next((v for v in gen_dev.rms_model.event_dict.keys() if v.name == "Ag0"), None)
    if vg0_var is not None:
        gen_dev.rms_model.event_dict[vg0_var] = grid.var_factory.add_const(vm0)
    if ag0_var is not None:
        gen_dev.rms_model.event_dict[ag0_var] = grid.var_factory.add_const(va0)

rms_options = RmsOptions(
    time_step=0.001,
    simulation_time=2.0,
    tolerance=1e-6,
    integration_method=DynamicIntegrationMethod.DaeBackEuler,
    initialization_method=RmsInitializationMethod.Explicit,
    use_init_values=False,
    max_iter=1000,
    verbose=0,
)

problem = RmsProblemDae(grid=grid, options=rms_options, pf_results=res)
events_group = RmsEventsGroup("simulation1")
generator_a_vg0 = next((var for var in genA_mdl.event_dict.keys() if var.name == "Vg0"), None)
if generator_a_vg0 is None:
    raise RuntimeError("Could not find Vg0 event variable for generatorA RMS model")

event_time = 0.1
event_value = 1.00001

grid.add_rms_event(
    RmsEvent(
        device=generatorA,
        parameter=generator_a_vg0,
        time=event_time,
        value=event_value,
        group=events_group,
    )
)
problem.set_events_group(events_group)

solver = BackEulerImplicitIntegration(
    problem=problem,
    t0=0,
    t_end=rms_options.simulation_time,
    h=rms_options.time_step,
    max_iter=rms_options.max_iter,
)

try:
    t, y, well_initialized, converged = solver.simulate()
    print("RMS simulation finished", well_initialized, converged, len(t))
except Exception as exc:
    print(f"RMS simulation failed before completion: {exc}")
    t = solver.t.copy()
    y = solver.y.copy()
    well_initialized = False
    converged = False

last_valid_idx = 0
for idx in range(1, len(t)):
    if t[idx] > t[idx - 1]:
        last_valid_idx = idx
    else:
        break

t_plot = t[:last_valid_idx + 1]
y_plot = y[:last_valid_idx + 1, :]
print(f"Plotting {len(t_plot)} time samples (partial run: {not converged})")

for trafo in [trafoA, trafoB]:
    print_control_blocks_outputs(trafo=trafo, problem=problem, y_values=y_plot, sample_idx=-1)
    print_current_frame_sanity(trafo=trafo, problem=problem, y_values=y_plot, sample_idx=-1)

bus1_vm = bus1.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
bus6_vm = bus6.rms_model.external_mapping[VarPowerFlowReferenceType.Vm]
genA_p = genA_mdl.external_mapping[VarPowerFlowReferenceType.P]
genB_p = genB_mdl.external_mapping[VarPowerFlowReferenceType.P]

plt.figure(figsize=(10, 7))

plt.subplot(3, 1, 1)
plt.plot(t_plot, y_plot[:, problem.get_var_idx(bus1_vm)], label="Vm Bus1")
plt.plot(t_plot, y_plot[:, problem.get_var_idx(bus6_vm)], label="Vm Bus6")
plt.axvline(event_time, color="black", linestyle="--", linewidth=1.0, label=f"Event @ {event_time:.3f} s")
plt.ylabel("Voltage (p.u.)")
plt.grid(True, alpha=0.3)
plt.legend()

plt.subplot(3, 1, 2)
plt.plot(t_plot, y_plot[:, problem.get_var_idx(genA_p)], label="P Gen_Thev_A")
plt.plot(t_plot, y_plot[:, problem.get_var_idx(genB_p)], label="P Gen_Thev_B")
plt.axvline(event_time, color="black", linestyle="--", linewidth=1.0, label=f"Event @ {event_time:.3f} s")
plt.ylabel("Active Power (p.u.)")
plt.grid(True, alpha=0.3)
plt.legend()

plt.subplot(3, 1, 3)
for trafo in [trafoA, trafoB]:
    id_ref_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_contains=["id_ref_lmtd_", "id_ref_"],
    )
    iq_ref_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_contains=["iq_ref_lmtd_", "iq_ref_"],
    )
    id_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_exact=[f"id_{trafo.name}"],
        preferred_contains=["id_"],
        exclude_contains=["id_ref", "id_limit", "id_lim_cal"],
    )
    iq_var = pick_solved_var(
        trafo.rms_model,
        problem,
        preferred_exact=[f"iq_{trafo.name}"],
        preferred_contains=["iq_"],
        exclude_contains=["iq_ref", "iq_limit", "iq_lim_cal"],
    )

    if id_ref_var is not None and id_ref_var.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(id_ref_var)], label=f"{trafo.name} id_ref")
    else:
        block_var_names = collect_var_names_in_block(trafo.rms_model)
        candidate_names = sorted([n for n in block_var_names if "id_ref" in n])
        print(f"[WARN] Could not plot id_ref for {trafo.name}. Candidates in block: {candidate_names}")

    if iq_ref_var is not None and iq_ref_var.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(iq_ref_var)], label=f"{trafo.name} iq_ref")
    else:
        block_var_names = collect_var_names_in_block(trafo.rms_model)
        candidate_names = sorted([n for n in block_var_names if "iq_ref" in n])
        print(f"[WARN] Could not plot iq_ref for {trafo.name}. Candidates in block: {candidate_names}")

    if id_var is not None and id_var.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(id_var)], linestyle="--", label=f"{trafo.name} id")
    else:
        block_var_names = collect_var_names_in_block(trafo.rms_model)
        candidate_names = sorted([n for n in block_var_names if n.startswith("id_")])
        print(f"[WARN] Could not plot id for {trafo.name}. Candidates in block: {candidate_names}")

    if iq_var is not None and iq_var.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(iq_var)], linestyle="--", label=f"{trafo.name} iq")
    else:
        block_var_names = collect_var_names_in_block(trafo.rms_model)
        candidate_names = sorted([n for n in block_var_names if n.startswith("iq_")])
        print(f"[WARN] Could not plot iq for {trafo.name}. Candidates in block: {candidate_names}")

plt.axvline(event_time, color="black", linestyle="--", linewidth=1.0, label=f"Event @ {event_time:.3f} s")
plt.xlabel("Time (s)")
plt.ylabel("Current (p.u.)")
plt.grid(True, alpha=0.3)
plt.legend(ncol=2, fontsize=8)

plt.tight_layout()

# Diagnostic figure: ref paths, limiter activity, mode flags, and tracking errors
diag_var_labels = [
    ("id_ref", ["id_ref_"], []),
    ("id_ref_lmtd", ["id_ref_lmtd_", "id_ref_"], []),
    ("iq_ref", ["iq_ref_"], []),
    ("iq_ref_lmtd", ["iq_ref_lmtd_", "iq_ref_"], []),
    ("id", ["id_"], ["id_ref", "id_limit", "id_lim_cal"]),
    ("iq", ["iq_"], ["iq_ref", "iq_limit", "iq_lim_cal"]),
    ("id_limit", ["id_limit_"], []),
    ("iq_limit", ["iq_limit_"], []),
    ("sel2", ["proc_select_2"], []),
    ("sel3", ["proc_select_3"], []),
    ("sel4", ["proc_select_4"], []),
    ("sel5", ["proc_select_5"], []),
]

diag = {}
for trafo in [trafoA, trafoB]:
    diag[trafo.name] = {}
    for label, preferred_contains, exclude_contains in diag_var_labels:
        diag[trafo.name][label] = pick_solved_var(
            trafo.rms_model,
            problem,
            preferred_contains=preferred_contains,
            exclude_contains=exclude_contains,
        )

plt.figure(figsize=(12, 10))

plt.subplot(4, 1, 1)
for trafo in [trafoA, trafoB]:
    tref = diag[trafo.name]["id_ref"]
    tlmtd = diag[trafo.name]["id_ref_lmtd"]
    if tref is not None and tref.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(tref)], label=f"{trafo.name} id_ref")
    if tlmtd is not None and tlmtd.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(tlmtd)], linestyle="--", label=f"{trafo.name} id_ref_lmtd")
plt.axvline(event_time, color="black", linestyle="--", linewidth=1.0)
plt.ylabel("d-axis refs")
plt.grid(True, alpha=0.3)
plt.legend(ncol=2, fontsize=8)

plt.subplot(4, 1, 2)
for trafo in [trafoA, trafoB]:
    tref = diag[trafo.name]["iq_ref"]
    tlmtd = diag[trafo.name]["iq_ref_lmtd"]
    if tref is not None and tref.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(tref)], label=f"{trafo.name} iq_ref")
    if tlmtd is not None and tlmtd.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(tlmtd)], linestyle="--", label=f"{trafo.name} iq_ref_lmtd")
plt.axvline(event_time, color="black", linestyle="--", linewidth=1.0)
plt.ylabel("q-axis refs")
plt.grid(True, alpha=0.3)
plt.legend(ncol=2, fontsize=8)

plt.subplot(4, 1, 3)
for trafo in [trafoA, trafoB]:
    id_lim = diag[trafo.name]["id_limit"]
    iq_lim = diag[trafo.name]["iq_limit"]
    if id_lim is not None and id_lim.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(id_lim)], label=f"{trafo.name} id_limit")
    if iq_lim is not None and iq_lim.uid in problem.uid2idx_vars:
        plt.plot(t_plot, y_plot[:, problem.get_var_idx(iq_lim)], linestyle="--", label=f"{trafo.name} iq_limit")
plt.axvline(event_time, color="black", linestyle="--", linewidth=1.0)
plt.ylabel("Current limits")
plt.grid(True, alpha=0.3)
plt.legend(ncol=2, fontsize=8)

plt.subplot(4, 1, 4)
for trafo in [trafoA, trafoB]:
    id_ref_lmtd = diag[trafo.name]["id_ref_lmtd"]
    iq_ref_lmtd = diag[trafo.name]["iq_ref_lmtd"]
    id_var = diag[trafo.name]["id"]
    iq_var = diag[trafo.name]["iq"]

    if id_ref_lmtd is not None and id_var is not None and id_ref_lmtd.uid in problem.uid2idx_vars and id_var.uid in problem.uid2idx_vars:
        err_id = y_plot[:, problem.get_var_idx(id_ref_lmtd)] - y_plot[:, problem.get_var_idx(id_var)]
        plt.plot(t_plot, err_id, label=f"{trafo.name} e_id")
    if iq_ref_lmtd is not None and iq_var is not None and iq_ref_lmtd.uid in problem.uid2idx_vars and iq_var.uid in problem.uid2idx_vars:
        err_iq = y_plot[:, problem.get_var_idx(iq_ref_lmtd)] - y_plot[:, problem.get_var_idx(iq_var)]
        plt.plot(t_plot, err_iq, linestyle="--", label=f"{trafo.name} e_iq")

    for sel_label in ["sel2", "sel3", "sel4", "sel5"]:
        sel_var = diag[trafo.name][sel_label]
        if sel_var is not None and sel_var.uid in problem.uid2idx_vars:
            plt.plot(
                t_plot,
                y_plot[:, problem.get_var_idx(sel_var)],
                alpha=0.35,
                linewidth=0.9,
                label=f"{trafo.name} {sel_label}",
            )

plt.axvline(event_time, color="black", linestyle="--", linewidth=1.0)
plt.xlabel("Time (s)")
plt.ylabel("Errors / selects")
plt.grid(True, alpha=0.3)
plt.legend(ncol=3, fontsize=7)
plt.tight_layout()

plt.show()

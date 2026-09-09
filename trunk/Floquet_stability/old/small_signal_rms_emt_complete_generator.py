# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import sys, os
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import SmallSignalStabilityEmtOptions
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_results import SmallSignalStabilityEmtResults
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import SmallSignalStabilityEmtDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template_v2 import get_complete_generator_template_rms
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_complete_generator_template_emt
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph

from VeraGridEngine.enumerations import DynamicIntegrationMethod, ShuntConnectionType, RmsInitializationMethod, EmtSolverTypes, SmallSignalEmtBuildTypes

import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################


def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

def plot_s_domain_eigenvalues(
    eigenvalues_1: np.ndarray,
    eigenvalues_2: np.ndarray,
    label_1: str = "Solver 1",
    label_2: str = "Solver 2",
) -> None:
    """Plot and compare two sets of EMT eigenvalues on the complex plane."""

    eigenvalues_1 = np.asarray(eigenvalues_1, dtype=complex).ravel()
    eigenvalues_2 = np.asarray(eigenvalues_2, dtype=complex).ravel()

    # Remove invalid values before calculating limits and plotting.
    valid_1 = np.isfinite(eigenvalues_1.real) & np.isfinite(eigenvalues_1.imag)
    valid_2 = np.isfinite(eigenvalues_2.real) & np.isfinite(eigenvalues_2.imag)

    eigenvalues_1 = eigenvalues_1[valid_1]
    eigenvalues_2 = eigenvalues_2[valid_2]

    if eigenvalues_1.size == 0 and eigenvalues_2.size == 0:
        return

    # Calculate plot limits using both eigenvalue sets.
    all_eigenvalues = np.concatenate((eigenvalues_1, eigenvalues_2))
    all_re = np.real(all_eigenvalues)
    all_im = np.imag(all_eigenvalues)

    data_span_re = np.ptp(all_re)
    data_span_im = np.ptp(all_im)

    margin_x = max(data_span_re * 0.1, 1.0)
    margin_y = max(data_span_im * 0.1, 1.0)

    x_min = all_re.min() - margin_x
    x_max = all_re.max() + margin_x
    y_min = all_im.min() - margin_y
    y_max = all_im.max() + margin_y

    # Constant damping-ratio lines: zeta = 5 %.
    zeta = 0.05
    slope = np.sqrt(1.0 - zeta**2) / zeta

    x_z = np.linspace(min(-200.0, x_min), 0.0, 400)
    y_z = slope * x_z

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.plot(
        x_z,
        y_z,
        "--",
        color="grey",
        linewidth=0.7,
        alpha=0.6,
        label=r"$\zeta = 5\%$",
    )
    ax.plot(
        x_z,
        -y_z,
        "--",
        color="grey",
        linewidth=0.7,
        alpha=0.6,
    )

    if eigenvalues_1.size > 0:
        ax.scatter(
            eigenvalues_1.real,
            eigenvalues_1.imag,
            color="tab:blue",
            marker="o",
            s=100,
            alpha=0.8,
            label=label_1,
        )

    if eigenvalues_2.size > 0:
        ax.scatter(
            eigenvalues_2.real,
            eigenvalues_2.imag,
            color="tab:orange",
            marker="x",
            s=100,
            linewidths=2.0,
            alpha=0.8,
            label=label_2,
        )

    ax.set_title("S-Domain Stability Plot")
    ax.set_xlabel("Real [rad/s]")
    ax.set_ylabel("Imaginary [rad/s]")

    ax.axhline(0.0, color="black", linewidth=1.0)
    ax.axvline(0.0, color="black", linewidth=1.0)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    ax.grid(True, alpha=0.3)
    ax.legend()

    fig.tight_layout()
    plt.show(block=False)

def _format_complex_value(value: complex, decimals: int = 3) -> str:
    """Format a complex value for display inside a table cell."""
    if np.isclose(value.imag, 0.0):
        return f"{value.real:.{decimals}f}"

    return f"{value.real:.{decimals}f}{value.imag:+.{decimals}f}j"

def _plot_single_participation_factors_table(
    pfactors: np.ndarray,
    title: str,
    decimals: int = 2,
) -> None:
    """
    Plot one participation-factor matrix as a heatmap table.

    Rows: State 1, State 2, ...
    Columns: Mode 1, Mode 2, ...

    Cell text shows the complex participation factor.
    Cell color is based on abs(participation factor).
    """
    pfactors = np.asarray(pfactors, dtype=complex)

    if pfactors.ndim != 2:
        raise ValueError(
            "Each participation-factor set must be a 2D array with shape "
            "(n_states, n_modes)."
        )

    if pfactors.size == 0:
        return

    n_states, n_modes = pfactors.shape

    state_labels = [f"State {i + 1}" for i in range(n_states)]
    mode_labels = [f"Mode {j + 1}" for j in range(n_modes)]

    magnitudes = np.abs(pfactors)
    min_magnitude = magnitudes.min()
    max_magnitude = magnitudes.max()

    # Adaptive figure size:
    # - large enough for screen viewing
    # - cells become visually smaller when there are many rows/columns
    fig_width = min(max(10.0, 0.75 * n_modes + 3.0), 20.0)
    fig_height = min(max(7.0, 0.45 * n_states + 2.5), 14.0)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    try:
        fig.canvas.manager.set_window_title(title)
    except Exception:
        pass

    image = ax.imshow(
        magnitudes,
        cmap="Blues",
        aspect="auto",
        vmin=min_magnitude,
        vmax=max_magnitude if max_magnitude > min_magnitude else min_magnitude + 1.0,
    )

    ax.set_xticks(np.arange(n_modes))
    ax.set_yticks(np.arange(n_states))
    ax.set_xticklabels(mode_labels, fontsize=max(6, min(10, int(220 / max(n_modes, 1)))))
    ax.set_yticklabels(state_labels, fontsize=max(6, min(10, int(220 / max(n_states, 1)))))

    ax.tick_params(
        axis="x",
        top=True,
        bottom=False,
        labeltop=True,
        labelbottom=False,
    )

    ax.set_xlabel("Modes")
    ax.xaxis.set_label_position("top")
    ax.set_ylabel("States")
    ax.set_title(title, pad=25)

    # Cell borders
    ax.set_xticks(np.arange(-0.5, n_modes, 1.0), minor=True)
    ax.set_yticks(np.arange(-0.5, n_states, 1.0), minor=True)
    ax.grid(which="minor", color="black", linestyle="-", linewidth=0.4)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Adaptive text size so cells look less crowded for large matrices
    cell_fontsize = max(5, min(9, int(180 / max(n_states, n_modes, 1))))

    color_range = max_magnitude - min_magnitude

    for i in range(n_states):
        for j in range(n_modes):
            magnitude = magnitudes[i, j]

            if color_range > 0.0:
                normalized = (magnitude - min_magnitude) / color_range
            else:
                normalized = 0.0

            text_color = "white" if normalized > 0.55 else "black"

            ax.text(
                j,
                i,
                _format_complex_value(pfactors[i, j], decimals=decimals),
                ha="center",
                va="center",
                color=text_color,
                fontsize=cell_fontsize,
            )

    cbar = fig.colorbar(image, ax=ax)
    cbar.set_label("|Participation factor|")

    fig.tight_layout()


def plot_two_participation_factors_tables(
    pfactors_1: np.ndarray,
    pfactors_2: np.ndarray,
    title_1: str = "Participation Factors - Set 1",
    title_2: str = "Participation Factors - Set 2",
    decimals: int = 2,
) -> None:
    """
    Plot two participation-factor matrices in two separate figures,
    so they can be visually compared at the same time.
    """
    _plot_single_participation_factors_table(
        pfactors=pfactors_1,
        title=title_1,
        decimals=decimals,
    )

    _plot_single_participation_factors_table(
        pfactors=pfactors_2,
        title=title_2,
        decimals=decimals,
    )

    plt.show(block=False)



#####################################################################################
#                    Grid
#####################################################################################

grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

#####################################################################################
#                    Devices
#####################################################################################

# Buses
vnom = 10 #kV
bus0 = gce.Bus(name="Bus0", Vnom=vnom, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=vnom)

grid.add_bus(bus0)
grid.add_bus(bus1)


for bus in grid.buses:
    initialize_bus_rms(bus, vf=grid.var_factory)


# Lines
line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)


# physical configuration (Overhead line tower)
tower = gce.OverheadLineType(name="Tower", Vnom=vnom)
wire = gce.Wire(name="Panther 30/7 ACSR",
                diameter=21.0,
                diameter_internal=9.0,
                is_tube=True,
                r=0.1363,
                max_current=1)
tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
tower.compute()

line0.apply_template(tower, grid.Sbase, grid.fBase)

# load
R_ph =100 #ohm
v_ph = vnom / (3**0.5)
P_ph = (v_ph**2) / R_ph # kv*kv/ohm = MW
print("P_ph=", P_ph)

# load = gce.Load(name="load",P1= P/3, P2= P/3, P3= P/3, Q1= Q/3, Q2= Q/3, Q3= Q/3)
load = gce.Load(name="load",P1= P_ph, P2= P_ph, P3= P_ph, Q1= 0.0, Q2= 0.0, Q3= 0.0)
load.conn = ShuntConnectionType.GroundedStar

# Generators
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=0.001, x1=1.7)


grid.add_line(line0)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_load(bus=bus1, api_obj=load)
for bus in grid.buses:
    get_bus_emt_template(grid, bus)

######################################################################################################
# Build Rms models
######################################################################################################


# generator
genqec_mdl_rms = get_complete_generator_template_rms(grid.var_factory).block

# line
line_mdl_rms = get_line_rms_template(grid.var_factory).block

# load
load_mdl_rms = get_load_rms_template(grid.var_factory).block

######################################################################################################
# Build EMT models
######################################################################################################

# generator
gen_mdl_emt = get_complete_generator_template_emt(vf = grid.var_factory).block

# line
line_mdl_emt = get_pi_line_emt_template(vf=grid.var_factory, phN = False, phA = True, phB = True, phC = True).block

# load
load_mdl_emt = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

######################################################################################################
# Add rms models to devices
######################################################################################################

set_rms_model(device=gen0, model=genqec_mdl_rms, var_factory= grid.var_factory)

set_rms_model(device=line0, model=line_mdl_rms, var_factory= grid.var_factory)

set_rms_model(device=load, model=load_mdl_rms, var_factory= grid.var_factory)

######################################################################################################
# Add emt models to devices
######################################################################################################

set_emt_model(device=gen0, model=gen_mdl_emt, var_factory= grid.var_factory)

set_emt_model(device=line0, model=line_mdl_emt, var_factory= grid.var_factory)

set_emt_model(device=load, model=load_mdl_emt, var_factory= grid.var_factory)

######################################################################################################
# Power flow
######################################################################################################

options = gce.PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=0,
    initialize_with_existing_solution=True,
    tolerance=1e-6,
    max_iter=25,
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
print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

power_flow_3ph = PowerFlowDriver3Ph(grid, options)
power_flow_3ph.run()
res_3ph = power_flow_3ph.results
print(f"Converged: {res_3ph.converged}")
print(res_3ph.get_bus_df())
print(res_3ph.get_branch_df())


rms_options = RmsOptions(time_step=0.001,
                     simulation_time=1,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     initialization_method=RmsInitializationMethod.Explicit,
                     use_init_values=False,
                     max_iter=1000,
                     verbose=0)

sss_options = RmsSmallSignalStabilityOptions(k=0,
                                            ss_assessment_time= 0.0)

emt_options = EmtOptions(time_step=5e-6,
                         simulation_time=0.04,
                         tolerance=1e-6,
                         solver_type=EmtSolverTypes.Automatic,
                         integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
                         verbose=1)

floquet_options = SmallSignalStabilityEmtOptions(k=29,
                                                 target_period=1.0 / grid.fBase,
                                                 ss_assessment_time=0.1,
                                                 build_type=SmallSignalEmtBuildTypes.Arnoldi,
                                                 verbose=1)

######################################################################################################
# Prepare driver
######################################################################################################

small_signal_driver = SmallSignalStabilityRmsDriver(grid=grid,
                                                        rms_options=rms_options,
                                                        sss_options=sss_options,
                                                        pf_results=res)

floquet_driver = SmallSignalStabilityEmtDriver(grid=grid,
                                               pf_results=res_3ph,
                                               emt_options=emt_options,
                                               sss_options=floquet_options)

######################################################################################################
# Run simulations
######################################################################################################

small_signal_driver.run_small_signal_stability()

rms_eigenvalues = small_signal_driver.results.eigenvalues
rms_PFactors = small_signal_driver.results.participation_factors
# print(f"eigenvalues={rms_eigenvalues}")
print(f"PFactors={rms_eigenvalues}")


floquet_driver.run()
emt_eigenvalues = floquet_driver.results.eigenvalues
emt_PFactors = floquet_driver.results.participation_factors

######################################################################################################
# Plot eigenvalue results
######################################################################################################


plot_s_domain_eigenvalues(
    eigenvalues_1=rms_eigenvalues,
    eigenvalues_2=emt_eigenvalues,
    label_1="RMS eigenvalues",
    label_2="EMT eigenvalues",
)

plot_two_participation_factors_tables(
    pfactors_1=rms_PFactors,
    pfactors_2=emt_PFactors,
    title_1="RMS participation factors",
    title_2="EMT participation factors",
)


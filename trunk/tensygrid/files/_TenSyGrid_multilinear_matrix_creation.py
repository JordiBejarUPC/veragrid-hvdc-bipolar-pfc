# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Small Signal Analysis for Phasor-based RMS Grid.

This script creates the phasor problem manually and injects it into the SmallSignalStabilityRmsDriver.
"""

import numpy as np
import sys, os

from trunk.tensygrid.files._PolynomialMatrixBuilder_class import PolynomialMatrixBuilder

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

from matplotlib import pyplot as plt

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import SmallSignalStabilityRmsOptions
from VeraGridEngine.Simulations.Rms.problems.rms_problem_phasor import RmsProblemPhasor
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Templates.Rms.bus_phasor_rms_template import initialize_bus_phasor_rms
from VeraGridEngine.Templates.Rms.line_phasor_rms_template import get_line_phasor_rms_template
from VeraGridEngine.Templates.Rms.load_phasor_current_rms_template import get_load_phasor_current_rms_template
from VeraGridEngine.Templates.Rms.genqec_phasor_rms_template import get_complete_generator_template_phasor
from VeraGridEngine.Templates.templates_common_functions import set_rms_model


def small_signal_analysis(comparar):
    """Perform small signal analysis on the phasor grid."""
    print("=" * 60)
    print("SMALL SIGNAL ANALYSIS - PHASOR RMS")
    print("=" * 60)

    # ===================================================================
    # CREATE GRID (Same as phasor validation)
    # ===================================================================
    print("\n[1] Creating phasor grid...")

    Sbase = 100.0
    grid = gce.MultiCircuit(Sbase=Sbase, fbase=50.0)

    bus0 = gce.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    for bus in grid.buses:
        initialize_bus_phasor_rms(bus, vf=grid.rms_var_factory)

    line = gce.Line(name="Line", bus_from=bus0, bus_to=bus1,
                    r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
    grid.add_line(line)

    load = gce.Load(P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)

    gen = gce.Generator(name="Gen0", P=10, vset=1.0, Snom=900)
    grid.add_generator(bus=bus0, api_obj=gen)

    # Build RMS models
    genqec = get_complete_generator_template_phasor(grid.rms_var_factory, name="Gen0").block

    line_mdl = get_line_phasor_rms_template(grid.rms_var_factory).block
    line_mdl.connect([line_mdl.in_vars[0]], [bus0.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[1]], [bus0.rms_model.out_vars[1]])
    line_mdl.connect([line_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])

    # Attach line model to the line device
    set_rms_model(device=line, model=line_mdl, var_factory=grid.rms_var_factory)

    genqec.connect([genqec.in_vars[0]], [bus0.rms_model.out_vars[0]])
    genqec.connect([genqec.in_vars[1]], [bus0.rms_model.out_vars[1]])

    set_rms_model(device=gen, model=genqec, var_factory=grid.rms_var_factory)

    load_mdl = get_load_phasor_current_rms_template(grid.rms_var_factory).block
    load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
    load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])
    # Current values will be set after power flow
    set_rms_model(device=load, model=load_mdl, var_factory=grid.rms_var_factory)

    print("  ✓ Grid created with multilinear generator")

    # ===================================================================
    # POWER FLOW
    # ===================================================================
    print("\n[2] Running power flow...")
    pf_options = gce.PowerFlowOptions()
    pf_results = gce.power_flow(grid, pf_options)

    if pf_results.converged:
        print(f"  ✓ Power flow converged")
        for i, bus in enumerate(grid.buses):
            v = pf_results.voltage[i]
            print(f"    {bus.name}: Vm={abs(v):.4f} pu")
    else:
        print("  ✗ Power flow failed")
        return False

    # ===================================================================
    # CREATE PHASOR PROBLEM
    # ===================================================================
    print("\n[3] Creating phasor problem...")

    rms_options = RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20
    )

    phasor_problem = RmsProblemPhasor(grid=grid, options=rms_options, pf_results=pf_results)

    if comparar:
        print(f"  ✓ Phasor problem created with {phasor_problem.get_states_number()} states")

        # ===================================================================
        # CREATE DRIVER AND SWAP PROBLEM
        # ===================================================================
        print("\n[4] Setting up small signal driver...")

        ss_options = SmallSignalStabilityRmsOptions(ss_assessment_time=0)

        # Create driver with dummy grid (it will create RmsProblemDae internally)
        dummy_grid = gce.MultiCircuit(Sbase=Sbase)
        driver = SmallSignalStabilityRmsDriver(
            grid=dummy_grid,
            rms_options=rms_options,
            sss_options=ss_options,
            pf_results=pf_results
        )

        # Swap in the actual phasor problem
        driver.problem = phasor_problem
        driver.k = phasor_problem.get_states_number()  # Update state count

        print("  ✓ Driver configured with phasor problem")

        # ===================================================================
        # RUN ANALYSIS
        # ===================================================================
        print("\n[5] Running small signal analysis...")
        driver.run()

        # ===================================================================
        # DISPLAY RESULTS
        # ===================================================================
        print("\n[6] Analysis complete!")

        eigenvalues = driver.results.eigenvalues
        participation_factors = driver.results.participation_factors
        damping_ratios = driver.results.damping_ratios
        frequencies = driver.results.conjugate_frequencies

        print(f"  Found {len(eigenvalues)} eigenvalues")

        # Display dominant modes
        print(f"\n  Dominant eigenvalues (top 10):")
        print(f"  {'Mode':<6} {'Real':<15} {'Imag':<15} {'Freq (Hz)':<12} {'Damping':<12} {'Status'}")
        print(f"  {'-' * 80}")

        for i in range(min(10, len(eigenvalues))):
            lam = eigenvalues[i]
            real_part = np.real(lam)
            imag_part = np.imag(lam)
            freq = frequencies[i] if i < len(frequencies) else abs(imag_part) / (2 * np.pi)
            damping = damping_ratios[i] if i < len(damping_ratios) else 0.0

            status = "Stable" if real_part < -1e-6 else "UNSTABLE" if real_part > 1e-6 else "Marginal"
            print(f"  {i + 1:<6} {real_part:<15.6f} {imag_part:<15.6f} {freq:<12.4f} {damping:<12.4f} {status}")

        # Stability
        max_real = np.max(np.real(eigenvalues))
        print(f"\n  Stability: {'STABLE' if max_real < -1e-6 else 'UNSTABLE' if max_real > 1e-6 else 'MARGINAL'}")

        # ===================================================================
        # PLOT
        # ===================================================================
        print("\n[7] Generating plots...")

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Eigenvalue map
        ax1 = axes[0]
        real_parts = np.real(eigenvalues)
        imag_parts = np.imag(eigenvalues)
        colors = ['red' if r > 0 else 'blue' for r in real_parts]
        ax1.scatter(real_parts, imag_parts, c=colors, alpha=0.6, s=50)
        ax1.axvline(x=0, color='k', linestyle='--', linewidth=1)
        ax1.set_xlabel('Real Part')
        ax1.set_ylabel('Imaginary Part')
        ax1.set_title('Eigenvalue Map (Phasor RMS with Multilinear Generator)')
        ax1.grid(True, alpha=0.3)

        # Participation factors
        ax2 = axes[1]
        if participation_factors is not None and len(participation_factors) > 0:
            n_modes = min(3, participation_factors.shape[1])
            n_states = min(10, participation_factors.shape[0])
            x = np.arange(n_states)
            width = 0.25

            for mode_idx in range(n_modes):
                pf = participation_factors[:n_states, mode_idx]
                pf = pf / np.sum(pf) if np.sum(pf) > 0 else pf
                ax2.bar(x + mode_idx * width, pf, width,
                        label=f'Mode {mode_idx + 1} ({np.real(eigenvalues[mode_idx]):.3f})')

            ax2.set_xlabel('State Variable')
            ax2.set_ylabel('Participation Factor')
            ax2.set_title('Participation Factors (Dominant Modes)')
            ax2.set_xticks(x + width)
            ax2.set_xticklabels([f'State {i}' for i in range(n_states)])
            ax2.legend()
            ax2.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        plt.show()

    return True, phasor_problem


if __name__ == "__main__":
    success, phasor_problem = small_signal_analysis(comparar = False)
    # sys.exit(0 if success else 1)

    algebraic_eqs: list[str] = list(phasor_problem._algebraic_eqs)
    state_eqs: list[str] = list(phasor_problem._state_eqs)
    algebraic_vars: list[str] = list([str(expression) for expression in phasor_problem._algebraic_vars])
    state_vars: list[str] = list([str(expression) for expression in phasor_problem._state_vars])
    print(f"\nState variables ({len(state_vars)}): {state_vars}")
    print(f"\nAlgebraic variables ({len(algebraic_vars)}): {algebraic_vars}")

    eqs: list[str] = algebraic_eqs + state_eqs
    print(f"\nNumber of equations: {len(eqs)}")
    print(f"\nEquation 1: {eqs[0]}")
    builder = PolynomialMatrixBuilder(
        eqs=eqs,
        ineqs=[],
        state_vars=state_vars,
        #state_ids=phasor_problem.uid2idx_vars,
        algebraic_vars=algebraic_vars,
        #algebraic_ids=phasor_problem._algebraic_ids,
        verbose=True
    )
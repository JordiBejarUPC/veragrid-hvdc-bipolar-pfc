# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import sys
import os

# Ensure the library can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from VeraGridEngine.basic_structures import Logger

def run_transformer_generalized_pf():
    # Initialize grid
    grid = gce.MultiCircuit()

    # Define buses
    # Bus 1 is the Slack bus (135 kV)
    bus1 = gce.Bus(name='Bus 1', Vnom=135, is_slack=True)
    # Bus 2 is a 135 kV bus
    bus2 = gce.Bus(name='Bus 2', Vnom=135)
    # Bus 3 is a 100 kV bus (load side)
    bus3 = gce.Bus(name='Bus 3', Vnom=100)

    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)

    # Define AC lines
    # Line between Bus 1 and Bus 2 (both 135 kV) - OK
    line12 = gce.Line(name="line 1-2", bus_from=bus1, bus_to=bus2, r=0.01, x=0.05, b=0.0, rate=100.0)
    grid.add_line(line12)

    # Define transformer types
    trafo_type = gce.TransformerType(name='TransformerType',
                                     hv_nominal_voltage=135,
                                     lv_nominal_voltage=100,
                                     nominal_power=50.0,
                                     copper_losses=100.0,
                                     short_circuit_voltage=10.0) # 10% impedance
    grid.add_transformer_type(trafo_type)

    # Transformer 1 (Controllable): Bus 2 -> Bus 3
    trafo_1 = gce.Transformer2W(name='Trafo 2-3 (Controllable)',
                                bus_from=bus2,
                                bus_to=bus3,
                                template=trafo_type,
                                tap_module_control_mode=gce.TapModuleControl.Vm,
                                vset=1.02, # Regulate Bus 3 to 1.02 pu
                                tap_phase_control_mode=gce.TapPhaseControl.Pf,
                                Pset=5.0,  # Regulate active power flow to 5 MW
                                tap_module_min=0.8,
                                tap_module_max=1.2,
                                tap_phase_min=-30 / 180 * np.pi,
                                tap_phase_max=30 / 180 * np.pi)
    trafo_1.regulation_bus = bus3
    grid.add_transformer2w(trafo_1)

    # Transformer 2 (Fixed): Bus 1 -> Bus 3
    # This creates a loop 1-2-3-1
    trafo_2 = gce.Transformer2W(name='Trafo 1-3 (Fixed)',
                                bus_from=bus1,
                                bus_to=bus3,
                                template=trafo_type)
    grid.add_transformer2w(trafo_2)

    # Define generators
    # Setting reasonable impedance to avoid singular Jacobian
    gen1 = gce.Generator(name='Gen1', Snom=100.0, r1=1e-4, x1=0.1)
    grid.add_generator(bus=bus1, api_obj=gen1)

    # Define Load at Bus 3
    # Total load 10 MW. Transformer 1 should take 5 MW, Transformer 2 takes the rest.
    load1 = gce.Load(name='Load1', P=10.0, Q=2.0)
    grid.add_load(bus=bus3, api_obj=load1)

    # Apply templates to compute R, X, etc. from TransformerTypes
    grid.apply_all_branch_types()

    # Compile numerical circuit
    # CRITICAL: enable tap controls during compilation
    logger = Logger()
    nc = gce.compile_numerical_circuit_at(grid, 
                                          t_idx=None, 
                                          control_taps_modules=True, 
                                          control_taps_phase=True, 
                                          logger=logger)
    
    if logger.error_count() > 0:
        print("Compilation Errors:")
        for entry in logger.entries:
            if entry.severity == gce.LogSeverity.Error:
                print(entry)
        return

    options = PowerFlowOptions(gce.SolverType.NR, 
                               verbose=2, 
                               control_taps_modules=True, 
                               control_taps_phase=True)

    # Initial guesses
    V0 = nc.bus_data.Vbus
    S0 = nc.get_power_injections_pu()
    I0 = nc.get_current_injections_pu()
    Y0 = nc.get_admittance_injections_pu()
    Qmin, Qmax = nc.get_reactive_power_limits()

    # Create Generalized Power Flow formulation
    pf_form = PfGeneralizedFormulation(V0=V0, S0=S0, I0=I0, Y0=Y0, 
                                       Qmin=Qmin, Qmax=Qmax, 
                                       nc=nc, 
                                       options=options, 
                                       logger=logger)

    print("\nSolving using Generalized Power Flow Formulation...")
    
    # Run Newton-Raphson solver
    # The solver takes the formulation object itself
    results = newton_raphson_fx(problem=pf_form,
                                tol=options.tolerance,
                                max_iter=options.max_iter,
                                trust=options.trust_radius,
                                verbose=options.verbose,
                                logger=logger)

    if results.converged:
        print("\nPower Flow Converged Successfully!")
        
        print("\nBranch Results:")
        for i in range(nc.nbr):
            name = nc.passive_branch_data.names[i]
            f_bus = nc.bus_data.names[nc.passive_branch_data.F[i]]
            t_bus = nc.bus_data.names[nc.passive_branch_data.T[i]]
            p_flow = results.Sf[i].real
            q_flow = results.Sf[i].imag
            m_val = results.tap_module[i]
            tau_val = results.tap_angle[i]
            
            print(f"Branch: {name} ({f_bus} -> {t_bus})")
            print(f"  P: {p_flow:.4f} MW, Q: {q_flow:.4f} MVAr")
            print(f"  Tap Module: {m_val:.4f}, Tap Phase: {np.degrees(tau_val):.4f} deg")

        print("\nBus Voltages:")
        dict_idx = nc.bus_data.get_idtag_dict()
        for i in range(nc.nbus):
            name = nc.bus_data.names[i]
            vm = np.abs(results.V[i])
            va = np.degrees(np.angle(results.V[i]))
            print(f"Bus: {name} | V: {vm:.4f} pu | Angle: {va:.4f} deg")

        # Verify specific setpoints for Transformer 1
        target_v = 1.02
        target_p = 5.0
        
        v_idx = dict_idx[bus3.idtag]
        actual_v = np.abs(results.V[v_idx])
        
        # Branch data mapping
        br_idtag_to_idx = {tag: i for i, tag in enumerate(nc.passive_branch_data.idtag)}
        trafo_idx = br_idtag_to_idx[trafo_1.idtag]
        actual_p = results.Sf[trafo_idx].real
        
        print(f"\nSetpoint Verification for {trafo_1.name}:")
        print(f"  Voltage at Bus 3: {actual_v:.4f} pu (Target: {target_v:.4f} pu)")
        print(f"  Active Power Flow: {actual_p:.4f} MW (Target: {target_p:.4f} MW)")

    else:
        print("\nPower Flow FAILED to converge.")
        print(f"Final Error: {results.norm_f}")

if __name__ == "__main__":
    run_transformer_generalized_pf()

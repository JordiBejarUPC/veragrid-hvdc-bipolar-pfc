# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Small Signal Analysis for Phasor-based RMS Grid.

This script creates the phasor problem manually and injects it into the SmallSignalStabilityRmsDriver.
"""
from typing import Tuple, Any

#import sys
#import numpy as np
from PolynomialMatrixBuilder import PolynomialMatrixBuilder
#from matplotlib import pyplot as plt
import VeraGridEngine.api as vge
from VeraGridEngine import to_implicit


def define_problem():

    # ===================================================================
    # CREATE GRID (Same as phasor validation)
    # ===================================================================
    print("\n[1] Creating phasor grid...")

    Sbase = 100.0
    grid = vge.MultiCircuit(Sbase=Sbase, fbase=50.0)

    bus0 = vge.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = vge.Bus(name="Bus1", Vnom=10)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    for bus in grid.buses:
        vge.initialize_bus_phasor_rms(bus, vf=grid.var_factory)

    line = vge.Line(name="Line", bus_from=bus0, bus_to=bus1,
                    r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
    grid.add_line(line)

    load = vge.Load(P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)

    gen = vge.Generator(name="Gen0", P=10, vset=1.0, Snom=900)
    grid.add_generator(bus=bus0, api_obj=gen)

    # Build RMS models
    genqec = vge.get_complete_generator_template_phasor(grid.var_factory, name="Gen0").block
    genqec = vge.to_implicit(genqec, grid.var_factory)

    line_mdl = vge.get_line_phasor_rms_template(grid.var_factory).block
    line_mdl.connect([line_mdl.in_vars[0]], [bus0.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[1]], [bus0.rms_model.out_vars[1]])
    line_mdl.connect([line_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])

    # Attach line model to the line device
    vge.set_rms_model(device=line, model=line_mdl, var_factory=grid.var_factory)

    genqec.connect([genqec.in_vars[0]], [bus0.rms_model.out_vars[0]])
    genqec.connect([genqec.in_vars[1]], [bus0.rms_model.out_vars[1]])

    vge.set_rms_model(device=gen, model=genqec, var_factory=grid.var_factory)

    load_mdl = vge.get_load_phasor_current_rms_template(grid.var_factory).block
    load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
    load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])
    # Convert power to current: I = S* / V* (approximation for initialization)
    # For V ≈ 1.0, Ir ≈ P, Ii ≈ Q
    load_mdl.set_parameter_in_model(var_name="Ir0", new_value=-0.1)
    load_mdl.set_parameter_in_model(var_name="Ii0", new_value=-0.01)
    vge.set_rms_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    print("  ✓ Grid created with multilinear generator")

    # ===================================================================
    # POWER FLOW
    # ===================================================================
    print("\n[2] Running power flow...")
    pf_options = vge.PowerFlowOptions()
    pf_results = vge.power_flow(grid, pf_options)

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

    rms_options = vge.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20
    )

    phasor_problem = vge.RmsProblemPhasor(grid=grid, options=rms_options, pf_results=pf_results)
    print(f"  ✓ Phasor problem created with {phasor_problem.get_states_number()} states")

    return phasor_problem


def solve_problem(phasor_problem):
    # 1. Initialize the builder.
    # The __init__ will trigger the lifting and register auxiliary symbols.
    builder: PolynomialMatrixBuilder = PolynomialMatrixBuilder(
        problem=phasor_problem,
        verbose=False
    )

    # --- ESCÁNER DE DEBUG ---
    print("\n[DEBUG] Buscando el escondite de los parámetros...")
    atributos = [a for a in dir(phasor_problem) if not a.startswith('_')]
    print(f"Atributos disponibles en phasor_problem: {atributos}")

    # Vamos a probar los escondites más comunes de las librerías DAE/Phasor
    for candidato in ['p', 'params', 'parameters', 'sys_params', 'p_val', 'constants']:
        if hasattr(phasor_problem, candidato):
            valor = getattr(phasor_problem, candidato)
            if isinstance(valor, dict) and len(valor) > 0:
                print(f"¡BINGO! Los parámetros están en el atributo: '{candidato}' (Contiene {len(valor)} elementos)")
            elif hasattr(valor, '__dict__'):
                print(f"¡OJO! '{candidato}' es un objeto. Sus atributos son: {list(vars(valor).keys())[:10]}...")
    print("--------------------------\n")

    # 2. Construct the v_dict (operating point)
    # Rules: Initialize dict with dict()
    v_dict: dict = dict()

    # Extract base guesses from phasor_problem.
    # We assume phasor_problem.init_guess is a dict {id: value}
    # and phasor_problem.sys_vars is a dict {id: sympy_var_or_obj}
    base_guesses: dict = getattr(phasor_problem, "init_guess", dict())
    sys_vars: dict = getattr(phasor_problem, "sys_vars", dict())

    # NUEVO: Intentar extraer los parámetros del sistema
    sys_params: dict = getattr(phasor_problem, "sys_params", dict())
    if not sys_params:
        # El nombre exacto depende de la API de VeraGrid. Cubrimos las opciones más comunes:
        sys_params = getattr(phasor_problem, "parameters", getattr(phasor_problem, "params", dict()))

    # 1. Map original variables (states/algebraics) to their values using string keys
    for var_id, value in base_guesses.items():
        var_obj: any = sys_vars.get(var_id, None)
        if var_obj is not None:
            v_dict[str(var_obj)] = float(value)

    # 2. NUEVO: Map parameters to their values
    for param_id, param_val in sys_params.items():
        param_obj: any = sys_vars.get(param_id, None)
        if param_obj is not None:
            v_dict[str(param_obj)] = float(param_val)
        else:
            # Si el diccionario de parámetros usa directamente los nombres de las variables como keys
            v_dict[str(param_id)] = float(param_val)

    # 3. Handle Auxiliary Variables (The "Lifting" variables)
    # We iterate over all symbols registered in the builder
    for sym in builder.all_symbols:
        s_name: str = sym.name

        # If the symbol is not in our v_dict, it's likely an auxiliary one
        if s_name not in v_dict:
            # Case A: Multiplication Auxiliary (x_mulauxN -> value = x)
            if "_mulaux" in s_name:
                parent_name: str = s_name.split("_mulaux")[0]
                parent_val: float | None = v_dict.get(parent_name, None)
                if parent_val is not None:
                    v_dict[s_name] = parent_val
                else:
                    pass

            # Case B: Inverse Auxiliary (x_invauxN -> value = 1/x)
            elif "_invaux" in s_name:
                parent_name: str = s_name.split("_invaux")[0]
                parent_val: float | None = v_dict.get(parent_name, None)
                if parent_val is not None and parent_val != 0.0:
                    v_dict[s_name] = 1.0 / parent_val
                elif parent_val == 0.0:
                    # Avoid division by zero, set a small epsilon or 0.0
                    v_dict[s_name] = 0.0
                else:
                    pass
            else:
                pass
        else:
            # Already mapped
            pass
    print("\n[DEBUG] Cazando variables perdidas (en 0.0):")
    ceros_count = 0
    for sym in builder.all_symbols:
        s_name = sym.name
        # Si la variable no está en v_dict, o está pero vale 0.0
        val = v_dict.get(s_name, 0.0)
        if abs(val) <= 1e-6:
            print(f"  Falta o es cero -> {s_name}")
            ceros_count += 1

    print(f"Total de variables en cero: {ceros_count} de {len(builder.all_symbols)}")
    builder.linearize(v_dict=v_dict)
    res: Tuple[Any, Any, Any, Any, bool, float] = builder.compute_stability()
    stable: bool = res[4]
    margin: float = res[5]
    print(margin)
    pass


if __name__ == "__main__":
    phasor_problem = define_problem()
    solve_problem(phasor_problem)




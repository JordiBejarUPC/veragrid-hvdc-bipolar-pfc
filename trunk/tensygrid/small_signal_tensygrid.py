import numpy as np
from typing import Any, Tuple, List
from PolynomialMatrixBuilder import PolynomialMatrixBuilder
import VeraGridEngine.api as vge
import sympy as sp
import re
import matplotlib.pyplot as plt

def inspect_e_matrix_derivatives_v2(builder_obj, problem_obj) -> None:
    """
    Inspecciona las columnas de la matriz E mapeando correctamente contra
    las variables de estado reales del problema fasorial.
    """
    import scipy.sparse as sps
    import numpy as np

    E = builder_obj.E
    if sps.issparse(E):
        E_dense = E.toarray()
    else:
        E_dense = np.array(E)

    # El vector real que dicta las columnas de la matriz E
    state_vars = problem_obj.state_and_algebraic_vars

    active_vars = []
    dead_vars = []

    for j, sym in enumerate(state_vars):
        # Máximo valor absoluto en la columna j
        col_max_val = np.max(np.abs(E_dense[:, j]))
        sym_name = str(sym.name)

        if col_max_val > 1e-10:
            active_vars.append(sym_name)
        else:
            dead_vars.append(sym_name)

    #print("\n" + "="*60)
    #print("INSPECCIÓN EXACTA DE LA MATRIZ E (ESTADOS REALES)")
    #print("="*60)
    #print(f"[+] Estados con dinámica ACTIVA (Rango aportado: {len(active_vars)})")
    #for state in active_vars:
    #    print(f"    ✓ {state}")

    #print("="*60 + "\n")

def inspect_algebraic_states(builder_obj: PolynomialMatrixBuilder, e_matrix: np.ndarray) -> None:
    """
    Finds and prints the variables that have become algebraic (zeros on the diagonal of E).
    """
    zero_tolerance = 1e-10
    algebraic_vars: List[str] = []

    for i, symbol in enumerate(builder_obj.all_symbols):
        if abs(e_matrix[i, i]) < zero_tolerance:
            algebraic_vars.append(str(symbol.name))

    print(f"[DEBUG] Found {len(algebraic_vars)} algebraic/dependent variables in E.")
    print(f"[DEBUG] Affected variables: {algebraic_vars}")

def define_problem():
    """Creates the grid, runs the power flow, and returns the phasor problem."""
    print("\n[1] Creating phasor grid...")
    Sbase = 100.0
    grid = vge.MultiCircuit(Sbase=Sbase, fbase=50.0)

    bus0 = vge.Bus(name="Bus0", Vnom=10, is_slack=True)
    bus1 = vge.Bus(name="Bus1", Vnom=10)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    for bus in grid.buses:
        vge.initialize_bus_phasor_rms(bus, vf=grid.rms_var_factory)

    line = vge.Line(name="Line", bus_from=bus0, bus_to=bus1,
                    r=0.029585798816568046, x=0.07100591715976332, b=0.03, rate=900.0)
    grid.add_line(line)

    load = vge.Load(P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)

    gen = vge.Generator(name="Gen0", P=10, vset=1.0, Snom=900)
    grid.add_generator(bus=bus0, api_obj=gen)

    # RMS Models
    genqec = vge.get_complete_generator_template_phasor(grid.rms_var_factory, name="Gen0").block
    genqec = vge.to_implicit(genqec, grid.rms_var_factory)

    line_mdl = vge.get_line_phasor_rms_template(grid.rms_var_factory).block
    line_mdl.connect([line_mdl.in_vars[0]], [bus0.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[1]], [bus0.rms_model.out_vars[1]])
    line_mdl.connect([line_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    line_mdl.connect([line_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])

    vge.set_rms_model(device=line, model=line_mdl, var_factory=grid.rms_var_factory)

    genqec.connect([genqec.in_vars[0]], [bus0.rms_model.out_vars[0]])
    genqec.connect([genqec.in_vars[1]], [bus0.rms_model.out_vars[1]])
    vge.set_rms_model(device=gen, model=genqec, var_factory=grid.rms_var_factory)

    load_mdl = vge.get_load_phasor_current_rms_template(grid.rms_var_factory).block
    load_mdl.connect([load_mdl.in_vars[0]], [bus1.rms_model.out_vars[0]])
    load_mdl.connect([load_mdl.in_vars[1]], [bus1.rms_model.out_vars[1]])
    load_mdl.set_parameter_in_model(var_name="Ir0", new_value=-0.1)
    load_mdl.set_parameter_in_model(var_name="Ii0", new_value=-0.01)
    vge.set_rms_model(device=load, model=load_mdl, var_factory=grid.rms_var_factory)

    print("  ✓ Grid and models created.")

    print("\n[2] Running power flow...")
    pf_options = vge.PowerFlowOptions()
    pf_results = vge.power_flow(grid, pf_options)

    if not pf_results.converged:
        print("  ✗ Power flow failed")
        return False

    print(f"  ✓ Power flow converged. Bus1: Vm={abs(pf_results.voltage[1]):.4f} pu")

    print("\n[3] Creating phasor problem...")
    rms_options = vge.RmsOptions(
        time_step=0.01,
        simulation_time=1.0,
        tolerance=1e-6,
        max_iter=20
    )
    phasor_problem = vge.RmsProblemPhasor(grid=grid, options=rms_options, pf_results=pf_results)
    vge.save_file(grid, "test_tensygrid.gridcal")

    return phasor_problem



def solve_problem(problem: Any) -> None:
    print("\n[4] Rebuilding equations and extracting exact physics...")
    builder = PolynomialMatrixBuilder(problem=problem, verbose=True)
    v_dict: dict  = dict()

    def safe_get_value(val):
        try:
            return float(val)
        except:
            if hasattr(val, 'value'):
                try:
                    return float(val.value)
                except:
                    pass
        return None

    # 3. EXTRACT x0 (Equilibrium point)
    try:
        x0 = problem.get_x0()
        for i, sym in enumerate(problem.state_and_algebraic_vars):
            v_dict[str(sym.name)] = float(x0[i])
    except Exception:
        pass

    # 4. EXTRACTION FROM THE PHOTO PATHS
    # Based on your screenshot: _variable_parameters and _variable_parameters_values
    if hasattr(problem, '_variable_parameters') and hasattr(problem, '_variable_parameters_values'):
        names = problem._variable_parameters
        values = problem._variable_parameters_values
        if names is not None and values is not None:
            # If values is a list/array and names contains the symbols
            for name_obj, val_obj in zip(names, values):
                s_name = str(name_obj.name) if hasattr(name_obj, 'name') else str(name_obj)
                val = safe_get_value(val_obj)
                if val is not None:
                    v_dict[s_name] = val

    # Backup just in case there are also fixed constants
    if hasattr(problem, '_constant_parameters') and hasattr(problem, '_constant_params'):
        for n, v in zip(problem._constant_parameters, problem._constant_params):
            s_name = str(n.name) if hasattr(n, 'name') else str(n)
            val = safe_get_value(v)
            if val is not None:
                v_dict[s_name] = val

    # 5. LIFTING SUPPORT AND DEFAULT VALUES
    missing: list = list()

    for sym in builder.all_symbols:
        s_name = str(sym.name)
        if s_name not in v_dict:
            if '_invaux' in s_name:
                base = s_name.split('_invaux')[0]
                v_dict[s_name] = (1.0 / v_dict[base]) if base in v_dict and abs(v_dict[base]) > 1e-12 else 1.0
            elif '_mulaux' in s_name:
                base = s_name.split('_mulaux')[0]
                v_dict[s_name] = v_dict[base] if base in v_dict else 1.0
            else:
                missing.append(s_name)
                v_dict[s_name] = 0.0

    if missing:
        print(f"[!] Still missing: {missing}")

    print("[*] Linearizing model with real parameters...")
    builder.linearize(v_dict=v_dict)


    A_mat = builder.A.toarray() if hasattr(builder.A, 'toarray') else np.array(builder.A)
    E_mat = builder.E.toarray() if hasattr(builder.E, 'toarray') else np.array(builder.E)

    builder.A = A_mat
    builder.E = E_mat
    # ---------------------------------

    if hasattr(builder, 'E_matrix') and builder.E_matrix is not None:
        inspect_algebraic_states(builder, builder.E_matrix)

    inspect_e_matrix_derivatives_v2(builder, problem)
    res = builder.compute_stability()

    eigenvalues = res[0]
    stable = res[4]
    margin = res[5] if res[5] is not None else 0.0

    print("\n" + "=" * 80)
    print("SMALL SIGNAL ANALYSIS COMPLETE - POLYNOMIAL BUILDER")
    print("=" * 80)
    print(f"  Found {len(eigenvalues)} finite eigenvalues")
    print(f"  System is stable: {stable}")
    print(f"  Stability margin: {margin:.4f}")
    print("=" * 80)
    return eigenvalues

if __name__ == "__main__":
    problem = define_problem()
    calculated_evs = []
    if problem:
        # Obtenemos los autovalores reales del cálculo del Builder
        calculated_evs = solve_problem(problem)

    # La lista de referencia que proporcionaste
    reference_evs = [complex(x) for x in
                     ["(-20.000000001+0j)", "(-10.000000001+0j)", "(-50.00000013636582+0j)", "(-49.9999998638391+0j)",
                      "(-12.168789431034414+0j)", "(-10.142655446318065+0j)", "(-6.854035294550814+0j)",
                      "(-5.029702766536969+0j)", "(-3.6156680497265823+0j)", "(0.7258649757244431+0j)",
                      "(-1.8851882786542178+0j)", "(-1.719135993985083+0.32085026247445086j)",
                      "(-1.7191359939850832-0.3208502624744508j)", "(-0.49201422052160765+0.8707873679911879j)",
                      "(-0.49201422052160765-0.870787367991188j)", "(-0.48381848641530006+0.465928959924564j)",
                      "(-0.48381848641530006-0.46592895992456396j)", "(-0.10000000099999705+0j)",
                      "(-0.11161483998140341+0j)", "(-0.9999999991690246+0j)", "(-1.0000000028309748+0j)",
                      "(-0.39635072300328184+0j)", "(-10.00000000099956+0j)", "(-1.0000000000000023e-09+0j)",
                      "(-9.999999999999996e-10+0j)", "(-9.999999999999992e-10+0j)"]]

    plt.figure(figsize=(10, 6))

    # 1. Graficar los autovalores de REFERENCIA (Cruces pequeñas)
    plt.scatter(np.real(reference_evs), np.imag(reference_evs),
                color='gray', marker='x', alpha=0.5, label='Referencia')

    # 2. Graficar los autovalores CALCULADOS (Cruces grandes de color)
    if len(calculated_evs) > 0:
        # Filtramos infinitos para que no rompan el zoom del gráfico
        finite_evs = calculated_evs[np.isfinite(calculated_evs) & (np.abs(calculated_evs) < 1e6)]

        plt.scatter(np.real(finite_evs), np.imag(finite_evs),
                    c=(np.real(finite_evs) > 1e-6), cmap='coolwarm',
                    marker='+', s=100, linewidths=2, label='Calculados (Builder)')

    plt.axvline(0, color='k', linestyle='--')
    plt.axhline(0, color='k', alpha=0.3)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.title('Comparativa de Eigenvalues: Referencia vs Builder')
    plt.xlabel('Real')
    plt.ylabel('Imag')
    plt.savefig("scatter.png", dpi=300)
    plt.show()
import VeraGridEngine.api as gce
import numpy as np

def run_equivalence_test():
    # Parameters
    r, x, b, g = 0.05, 0.2, 0.04, 0.01
    v_nom = 100.0

    # --- Case 1: Standard Line ---
    grid_line = gce.MultiCircuit()
    b1_l = gce.Bus(name='B1', Vnom=v_nom, is_slack=True)
    b2_l = gce.Bus(name='B2', Vnom=v_nom)
    grid_line.add_bus(b1_l)
    grid_line.add_bus(b2_l)
    
    line = gce.Line(name="Line", bus_from=b1_l, bus_to=b2_l, r=r, x=x, b=b)
    grid_line.add_line(line)
    
    drv_line = gce.PowerFlowDriver(grid=grid_line)
    drv_line.run()
    
    # Manually compile numerical circuit to get Ybus
    nc_line = gce.compile_numerical_circuit_at(circuit=grid_line, t_idx=None)
    ybus_line = nc_line.get_admittance_matrices().Ybus.toarray()

    # --- Case 2: Transformer acting as a Line ---
    grid_trafo = gce.MultiCircuit()
    b1_t = gce.Bus(name='B1', Vnom=v_nom, is_slack=True)
    b2_t = gce.Bus(name='B2', Vnom=v_nom)
    grid_trafo.add_bus(b1_t)
    grid_trafo.add_bus(b2_t)
    
    # We set tap_module=1.0 and tap_phase=0.0 to match a line
    # Note: Line model in VeraGrid doesn't use 'g', so we set g=0 for similarity
    trafo = gce.Transformer2W(name="Trafo", bus_from=b1_t, bus_to=b2_t, 
                             r=r, x=x, g=0.0, b=b, 
                             tap_module=1.0, tap_phase=0.0)
    grid_trafo.add_transformer2w(trafo)
    
    drv_trafo = gce.PowerFlowDriver(grid=grid_trafo)
    drv_trafo.run()
    
    nc_trafo = gce.compile_numerical_circuit_at(circuit=grid_trafo, t_idx=None)
    ybus_trafo = nc_trafo.get_admittance_matrices().Ybus.toarray()

    # --- Comparison ---
    print("--- Admittance Matrix (Ybus) Comparison ---")
    print("Line Model Ybus:\n", ybus_line)
    print("\nTransformer Model Ybus (m=1, tau=0):\n", ybus_trafo)
    
    is_equivalent = np.allclose(ybus_line, ybus_trafo)
    print(f"\nEquivalence Match: {is_equivalent}")
    
    if is_equivalent:
        print("\nConclusion: A transformer with tap_module=1 and tap_phase=0 is mathematically identical to a line.")
    else:
        # If they differ, check why. Note: Transformers apply shunt half-and-half in Pi model just like Lines.
        diff = np.abs(ybus_line - ybus_trafo)
        print("\nMax difference:", np.max(diff))

if __name__ == "__main__":
    run_equivalence_test()

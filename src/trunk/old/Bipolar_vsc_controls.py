import itertools
import pandas as pd
import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes

Ub = 220
Sb = 100
Rb = (Ub ** 2) / Sb

rlin_12, rlin_13, rlin_23 = 2, 3, 1  # ohms

#Contorl modes for vsc1, vsc2, vsc3, vsc4
CONTROL_MODES = [
    ConverterControlType.Vm_dc,
    ConverterControlType.Qac,
    ConverterControlType.Pdc,
    ConverterControlType.Pac,
]

VSC_VALUES = {
    "VSC_1": {
        ConverterControlType.Vm_dc:  1.0,
        ConverterControlType.Pdc:  -30.0,
        ConverterControlType.Qac:    0.0,
        ConverterControlType.Pac:   30.0,
    },
    "VSC_2": {
        ConverterControlType.Vm_dc: -1.01,
        ConverterControlType.Pdc:  -30.0,
        ConverterControlType.Qac:    0.0,
        ConverterControlType.Pac:   30.0,
    },
    "VSC_3": {
        ConverterControlType.Vm_dc:  1.0,
        ConverterControlType.Pdc:   30.0,
        ConverterControlType.Qac:    0.0,
        ConverterControlType.Pac:  -30.0,
    },
    "VSC_4": {
        ConverterControlType.Vm_dc: -1.01,
        ConverterControlType.Pdc:   30.0,
        ConverterControlType.Qac:    0.0,
        ConverterControlType.Pac:  -30.0,
    },
}

# C(4,2) = 6 pairs per vsc
VALID_PAIRS = list(itertools.combinations(CONTROL_MODES, 2))

# 6^4 = 1296 Total combinations
ALL_COMBINATIONS = list(itertools.product(VALID_PAIRS, repeat=4))

print(f"Modos de control disponibles   : {len(CONTROL_MODES)}")
print(f"Parejas válidas por convertidor: {len(VALID_PAIRS)}")
print(f"Total de combinaciones a probar: {len(ALL_COMBINATIONS)}\n")


def build_and_run(vsc_pairs):
    try:
        grid = gce.MultiCircuit(name="Bipolar_system", Sbase=Sb)

        bus1 = gce.Bus(name="Bus1",
                       Vnom=Ub,
                       is_slack=True)
        grid.add_bus(bus1)
        bus8 = gce.Bus(name="Bus8",
                       Vnom=Ub,
                       is_slack=True)
        grid.add_bus(bus8)
        # DC buses
        bus2 = gce.Bus(name="Bus2",
                       Vnom=Ub,
                       is_dc=True)
        grid.add_bus(bus2)

        bus3 = gce.Bus(name="Bus3",
                       Vnom=Ub,
                       is_dc=True)
        grid.add_bus(bus3)

        bus4 = gce.Bus(name="Bus4",
                       Vnom=Ub,
                       is_dc=True)
        grid.add_bus(bus4)

        bus5 = gce.Bus(name="Bus5",
                       Vnom=Ub,
                       is_dc=True,
                       Vm0=1,
                       Va0=3.14)
        grid.add_bus(bus5)

        bus6 = gce.Bus(name="Bus6",
                       Vnom=Ub,
                       is_dc=True,
                       is_grounded=True,
                       Vm0=0.0001)
        grid.add_bus(bus6)

        bus7 = gce.Bus(name="Bus7",
                       Vnom=Ub,
                       is_dc=True,
                       is_grounded=True,
                       Vm0=0.0001)
        grid.add_bus(bus7)

        # Generators
        grid.add_generator(bus1, gce.Generator(name='g1',
                                               vset=1.0))

        grid.add_generator(bus8, gce.Generator(name='g8',
                                               vset=1.0))

        # DC_lines
        grid.add_dc_line(gce.DcLine(name="dc_line_23",
                                    bus_from=bus2,
                                    bus_to=bus3,
                                    r=rlin_23 / Rb))

        grid.add_dc_line(gce.DcLine(name="dc_line_45",
                                    bus_from=bus4,
                                    bus_to=bus5,
                                    r=rlin_23 / Rb))

        grid.add_dc_line(gce.DcLine(name="dc_line_0",
                                    bus_from=bus6,
                                    bus_to=bus7,
                                    r=rlin_13 / Rb))


        vsc_configs = [
            ("VSC_1", bus2, bus1,  bus6),
            ("VSC_2", bus2_dc, bus12_ac, bus0_1_dc),
            ("VSC_3", bus3_dc, bus3_ac,  bus0_2_dc),
            ("VSC_4", bus4_dc, bus4_ac,  bus0_2_dc),
        ]

        for i, (name, bus_dc, bus_ac, bus_dc_n) in enumerate(vsc_configs):
            c1, c2 = vsc_pairs[i]
            vals = VSC_VALUES[name]
            grid.add_vsc(gce.VSC(
                name=name,
                bus_from=bus_dc,
                bus_to=bus_ac,
                bus_dc_n=bus_dc_n,
                alpha1=0.01, alpha2=0.01, alpha3=0.01,
                control1=c1,
                control2=c2,
                control1_val=vals[c1],
                control2_val=vals[c2],
            ))

        options_pf = gce.PowerFlowOptions(verbose=0, generate_report=False,
                                          retry_with_other_methods=False)
        results = gce.power_flow(grid, options=options_pf)

        pf_dict = {}
        if results.converged:
            branch_df = results.get_branch_df()
            pf_series = branch_df.iloc[:, 0]   # columna Pf
            for branch_name, pf_val in pf_series.items():
                pf_dict[branch_name] = pf_val

        return results.converged, results.error, pf_dict

    except Exception as e:
        return False, str(e), {}


def ctrl_name(c):
    return c.name if hasattr(c, 'name') else str(c)

records = []

for idx, combo in enumerate(ALL_COMBINATIONS, start=1):
    converged, error, pf_dict = build_and_run(combo)

    record = {
        "combo_id":   idx,
        "VSC1_ctrl1": ctrl_name(combo[0][0]),
        "VSC1_ctrl2": ctrl_name(combo[0][1]),
        "VSC2_ctrl1": ctrl_name(combo[1][0]),
        "VSC2_ctrl2": ctrl_name(combo[1][1]),
        "VSC3_ctrl1": ctrl_name(combo[2][0]),
        "VSC3_ctrl2": ctrl_name(combo[2][1]),
        "VSC4_ctrl1": ctrl_name(combo[3][0]),
        "VSC4_ctrl2": ctrl_name(combo[3][1]),
        "converged":  converged,
        "error":      error if isinstance(error, float) else None,
    }

    for branch_name, pf_val in pf_dict.items():
        record[f"Pf_{branch_name}"] = pf_val

    records.append(record)

    status = "✓ CONVERGED" if converged else "✗ FAILED"
    err_str = f"| err={error:.2e}" if isinstance(error, float) else ""
    print(f"[{idx:>4}/{len(ALL_COMBINATIONS)}] {status} "
          f"VSC1:({ctrl_name(combo[0][0])},{ctrl_name(combo[0][1])}) "
          f"VSC2:({ctrl_name(combo[1][0])},{ctrl_name(combo[1][1])}) "
          f"VSC3:({ctrl_name(combo[2][0])},{ctrl_name(combo[2][1])}) "
          f"VSC4:({ctrl_name(combo[3][0])},{ctrl_name(combo[3][1])}) "
          f"{err_str}")

#Results storage
df = pd.DataFrame(records)
df.to_csv("vsc_combination_results.csv", index=False)

total   = len(df)
n_conv  = int(df["converged"].sum())
n_fail  = total - n_conv

print("\n" + "="*60)
print("  RESUMEN FINAL")
print("="*60)
print(f"  Total combinaciones probadas : {total}")
print(f"  Convergidas                  : {n_conv}")
print(f"  Fallidas                     : {n_fail}")
print(f"  Resultados guardados en      : vsc_combination_results.csv")
print("="*60)

converged_df = df[df["converged"]].copy()
pf_cols  = [c for c in converged_df.columns if c.startswith("Pf_")]
ctrl_cols = ["combo_id", "VSC1_ctrl1", "VSC1_ctrl2", "VSC2_ctrl1", "VSC2_ctrl2",
             "VSC3_ctrl1", "VSC3_ctrl2", "VSC4_ctrl1", "VSC4_ctrl2", "error"]

if not converged_df.empty:
    print(f"\nCombinaciones convergidas ({n_conv}) con Pf por rama:")
    print(converged_df[ctrl_cols + pf_cols].to_string(index=False))

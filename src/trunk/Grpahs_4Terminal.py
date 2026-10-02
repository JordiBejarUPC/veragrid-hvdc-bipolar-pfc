import os
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import VeraGridEngine.api as gce
from VeraGridEngine import PfcControlType
from VeraGridEngine.enumerations import ConverterControlType, ResultTypes


# =============================================================================
# PROSECCO 4-terminal bipolar HVDC system
# Comparison:
#   1) Physical network WITHOUT PFC
#   2) Physical network WITH PFC
#
# The two networks are rebuilt independently. The no-PFC network contains
# neither the PFC nor its intermediate buses.
#
# IMPORTANT:
#   The cable thermal rating is NOT defined in the original VeraGrid models.
#   Set CABLE_RATING_A to the actual continuous thermal current rating of the
#   cable/conductor you want to use in the paper.
# =============================================================================


# =============================================================================
# 1. BASE PARAMETERS
# =============================================================================

Ub = 525.0                         # kV
Sb = 100.0                         # MVA
Rb = (Ub ** 2) / Sb                # ohm
Ib = Sb / Ub                       # kA

# Converter losses
a = 0.5515 / Sb
b = 0.887 * (Ib / Sb)
c = 3.77 * ((Ib ** 2) / Sb)

# Land cable
r_ohm_m_land = 1.7241e-8           # ohm*m
a_mm2_land = 3000                  # mm^2
d_m_land = 1000                    # m
a_m2_land = a_mm2_land * 1e-6
r_ohm_km_land = r_ohm_m_land * (d_m_land / a_m2_land)
r_pu_km_land = r_ohm_km_land / Rb

# Sea cable
r_ohm_m_sea = 1.7241e-8            # ohm*m
a_mm2_sea = 2500                   # mm^2
d_m_sea = 1000                     # m
a_m2_sea = a_mm2_sea * 1e-6
r_ohm_km_sea = r_ohm_m_sea * (d_m_sea / a_m2_sea)
r_pu_km_sea = r_ohm_km_sea / Rb


# =============================================================================
# 2. COMMON NETWORK DATA
#
# IMPORTANT:
# These values are deliberately identical in both cases.
# They are taken from the PFC model and used also in the no-PFC topology.
# Only the physical PFC insertion changes.
# =============================================================================

d0a = 12
d0c = 12
d1 = 300
d2 = 200
d3 = 400
d4a = 150
d4b = 150
d5 = 200


# =============================================================================
# 3. STUDY SETTINGS
# =============================================================================

# OWF power per station. The original model has 3000 MW at each OWF and
# 1500 MW per pole. Therefore, when P_OWF is changed, each offshore pole
# receives P_OWF / 2.
OWF_POWER_MW = np.arange(3000.0, 4800.0 + 1.0, 100.0)

# Actual cable thermal rating must be supplied by the user/project.
# 3000 A is ONLY a placeholder and must not be interpreted as a rating
# derived from the 2500/3000 mm^2 cross-section.
CABLE_RATING_A = 3000.0

PF_TOLERANCE = 1e-8

# PFC current candidates. The PFC model uses Is in kA internally.
# In the original model:
#       1 / Ib = 5.25 pu -> 1.0 kA
#
# We search the PFC current because a fixed arbitrary Is can make the PFC
# worsen a particular branch. The "With PFC" curve therefore represents
# the best feasible PFC operating point for each congestion condition.
PFC_CURRENT_A = np.arange(-1500.0, 1500.0 + 1.0, 100.0)

OUTPUT_DIR = "PROSECCO_PFC_comparison"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# =============================================================================
# 4. BUS CREATION
# =============================================================================

def create_common_buses(grid):
    """
    Creates the 27 buses present in the original no-PFC/PFC models.
    Returns a dictionary indexed exactly as in the original scripts.
    """

    d_buses = {
        1: ("Bus1_ac", Ub, False, False, True),
        2: ("Bus2_ac", Ub, False, False, True),
        3: ("Bus3_ac", Ub, False, False, True),
        4: ("Bus4_ac", Ub, False, False, True),

        # Positive pole
        5: ("Bus0a_dc_+", Ub, True, False, False),
        6: ("Bus0c_dc_+", Ub, True, False, False),
        7: ("Bus1_dc_+", Ub, True, False, False),
        8: ("Bus2_dc_+", Ub, True, False, False),
        9: ("Bus3_dc_+", Ub, True, False, False),
        10: ("Bus4_dc_+", Ub, True, False, False),
        11: ("Bus5_dc_+", Ub, True, False, False),

        # DMR
        12: ("Bus0a_dc_0+", Ub, True, False, False),
        13: ("Bus0c_dc_0+", Ub, True, False, False),
        14: ("Bus0a_dc_0-", Ub, True, False, False),
        15: ("Bus0c_dc_0-", Ub, True, False, False),
        16: ("Bus1_dc_0", Ub, True, False, False),
        17: ("Bus2_dc_0", Ub, True, False, False),
        18: ("Bus3_dc_0", Ub, True, True, False),
        19: ("Bus4_dc_0", Ub, True, False, False),
        20: ("Bus5_dc_0", Ub, True, False, False),

        # Negative pole
        21: ("Bus0a_dc_-", Ub, True, False, False),
        22: ("Bus0c_dc_-", Ub, True, False, False),
        23: ("Bus1_dc_-", Ub, True, False, False),
        24: ("Bus2_dc_-", Ub, True, False, False),
        25: ("Bus3_dc_-", Ub, True, False, False),
        26: ("Bus4_dc_-", Ub, True, False, False),
        27: ("Bus5_dc_-", Ub, True, False, False),
    }

    buses = {}

    for key, data in d_buses.items():
        bus_name, v_nom, is_dc, is_grounded, is_slack = data

        if "_0" in bus_name:
            bus = gce.Bus(
                name=bus_name,
                Vnom=v_nom,
                is_slack=is_slack,
                is_dc=is_dc,
                is_grounded=is_grounded,
                Vm0=0.0000001,
                Va0=0.000001
            )
        elif "_-" in bus_name:
            bus = gce.Bus(
                name=bus_name,
                Vnom=v_nom,
                is_slack=is_slack,
                is_dc=is_dc,
                is_grounded=is_grounded,
                Va0=math.pi
            )
        else:
            bus = gce.Bus(
                name=bus_name,
                Vnom=v_nom,
                is_slack=is_slack,
                is_dc=is_dc,
                is_grounded=is_grounded
            )

        grid.add_bus(bus)
        buses[key] = bus

    return buses


# =============================================================================
# 5. BUILD ONE NETWORK
# =============================================================================

def build_grid(with_pfc, owf_power_mw, pfc_current_a=0.0):
    """
    Build one complete network.

    with_pfc=False:
        The PFC and all four PFC intermediate buses are physically absent.

    with_pfc=True:
        The PFC and its intermediate buses are physically inserted.

    owf_power_mw:
        Total active power generated by each OWF station.
        Each offshore VSC pole is controlled to owf_power_mw / 2.

    pfc_current_a:
        Positive-pole PFC Is in amperes.
        Negative-pole PFC Is is the opposite value.
    """

    grid = gce.MultiCircuit(
        name="4TerminalsBipolarSystem_WithPFC"
        if with_pfc
        else "4TerminalsBipolarSystem_WithoutPFC",
        Sbase=Sb
    )

    buses = create_common_buses(grid)

    # Unpack original bus numbering
    (
        bus1, bus2, bus3, bus4, bus5, bus6, bus7, bus8, bus9,
        bus10, bus11, bus12, bus13, bus14, bus15, bus16, bus17,
        bus18, bus19, bus20, bus21, bus22, bus23, bus24, bus25,
        bus26, bus27
    ) = [buses[i] for i in range(1, 28)]

    # -------------------------------------------------------------------------
    # PFC intermediate buses
    # -------------------------------------------------------------------------
    if with_pfc:
        bus2r_pos = gce.Bus(
            name="B2_pfc_r_+",
            Vnom=Ub,
            is_slack=False,
            is_dc=True,
            is_grounded=False
        )
        bus2s_pos = gce.Bus(
            name="B2_pfc_s_+",
            Vnom=Ub,
            is_slack=False,
            is_dc=True,
            is_grounded=False
        )
        bus2r_neg = gce.Bus(
            name="B2_pfc_r_-",
            Vnom=Ub,
            is_slack=False,
            is_dc=True,
            is_grounded=False,
            Va0=math.pi
        )
        bus2s_neg = gce.Bus(
            name="B2_pfc_s_-",
            Vnom=Ub,
            is_slack=False,
            is_dc=True,
            is_grounded=False,
            Va0=math.pi
        )

        grid.add_bus(bus2r_pos)
        grid.add_bus(bus2s_pos)
        grid.add_bus(bus2r_neg)
        grid.add_bus(bus2s_neg)

        # PFC current in kA -> PFC control expects the same per-unit scaling
        # used by the original model: Is_pu = Is_A / (Ib[kA] * 1000).
        pfc_is_pu = pfc_current_a / (Ib * 1000.0)

        grid.add_pfc(
            gce.PFC(
                name="PFC+",
                bus_dc_q=bus7,
                bus_dc_r=bus2r_pos,
                bus_dc_s=bus2s_pos,
                control1=PfcControlType.Is_pfc,
                control1_val=pfc_is_pu
            )
        )

        grid.add_pfc(
            gce.PFC(
                name="PFC-",
                bus_dc_q=bus23,
                bus_dc_r=bus2r_neg,
                bus_dc_s=bus2s_neg,
                control1=PfcControlType.Is_pfc,
                control1_val=-pfc_is_pu
            )
        )

    # -------------------------------------------------------------------------
    # HVDC lines
    #
    # The no-PFC and PFC networks use the SAME physical cable lengths.
    # Only the two branches split by the PFC are changed:
    #
    # WITHOUT PFC:
    #   Bus1+ -> Bus2+
    #   Bus1+ -> Bus5+
    #
    # WITH PFC:
    #   Bus1+ -> PFC -> Bus2+/Bus5+
    #
    # The rest of the network is identical.
    # -------------------------------------------------------------------------
    if with_pfc:
        pos_cable1_from = bus2r_pos
        pos_cable3_from = bus2s_pos
        neg_cable1_from = bus2r_neg
        neg_cable3_from = bus2s_neg
    else:
        pos_cable1_from = bus7
        pos_cable3_from = bus7
        neg_cable1_from = bus23
        neg_cable3_from = bus23

    d_lines = {
        1: (bus5, bus7, d0a, "dc_cable0a_+", "land"),
        2: (bus6, bus10, d0c, "dc_cable0c_+", "land"),
        3: (pos_cable1_from, bus8, d1, "dc_cable1_+", "sea"),
        4: (bus7, bus9, d4a, "dc_cable4a_+", "sea"),
        5: (bus9, bus10, d4b, "dc_cable4b_+", "sea"),
        6: (pos_cable3_from, bus11, d3, "dc_cable3_+", "sea"),
        7: (bus8, bus11, d2, "dc_cable2_+", "sea"),
        8: (bus10, bus11, d5, "dc_cable5_+", "sea"),

        9: (bus12, bus16, d0a, "dc_cable0a_0+", "land"),
        10: (bus13, bus19, d0c, "dc_cable0c_0+", "land"),
        11: (bus14, bus16, d0a, "dc_cable0a_0-", "land"),
        12: (bus15, bus19, d0c, "dc_cable0c_0-", "land"),
        13: (bus16, bus17, d1, "dc_cable1_0", "sea"),
        14: (bus16, bus18, d4a, "dc_cable4a_0", "sea"),
        15: (bus18, bus19, d4b, "dc_cable4b_0", "sea"),
        16: (bus16, bus20, d3, "dc_cable3_0", "sea"),
        17: (bus17, bus20, d2, "dc_cable2_0", "sea"),
        18: (bus19, bus20, d5, "dc_cable5_0", "sea"),

        19: (bus21, bus23, d0a, "dc_cable0a_-", "land"),
        20: (bus22, bus26, d0c, "dc_cable0c_-", "land"),
        21: (neg_cable1_from, bus24, d1, "dc_cable1_-", "sea"),
        22: (bus23, bus25, d4a, "dc_cable4a_-", "sea"),
        23: (bus25, bus26, d4b, "dc_cable4b_-", "sea"),
        24: (neg_cable3_from, bus27, d3, "dc_cable3_-", "sea"),
        25: (bus24, bus27, d2, "dc_cable2_-", "sea"),
        26: (bus26, bus27, d5, "dc_cable5_-", "sea"),
    }

    for _, data in d_lines.items():
        bus_from, bus_to, distance, name, cable_type = data

        resistance = (
            r_pu_km_land if cable_type == "land"
            else r_pu_km_sea
        )

        grid.add_dc_line(
            gce.DcLine(
                name=name,
                bus_from=bus_from,
                bus_to=bus_to,
                r=resistance,
                length=distance
            )
        )

    # -------------------------------------------------------------------------
    # AC generators / OWFs
    # -------------------------------------------------------------------------
    grid.add_generator(
        bus1,
        gce.Generator(name="AC grid 1", vset=1.0)
    )

    grid.add_generator(
        bus2,
        gce.Generator(name="AC grid 2", vset=1.0)
    )

    grid.add_generator(
        bus3,
        gce.Generator(
            name="OWF 1",
            vset=1.0,
            P=owf_power_mw
        )
    )

    grid.add_generator(
        bus4,
        gce.Generator(
            name="OWF 2",
            vset=1.0,
            P=owf_power_mw
        )
    )

    # -------------------------------------------------------------------------
    # Offshore VSC power per pole
    #
    # Original model:
    #   OWF station = 3000 MW
    #   VSC_3+ / VSC_4+ = 1500 MW
    #   VSC_3- / VSC_4- = 1500 MW
    #
    # Therefore:
    #   P_pole = P_OWF / 2
    # -------------------------------------------------------------------------
    p_pole = owf_power_mw / 2.0

    # Onshore droop VSCs: preserve the PFC script settings exactly.
    for name, bus_ac, bus_dc, bus_n in [
        ("VSC_1+", bus1, bus5, bus12),
        ("VSC_2+", bus2, bus6, bus13),
        ("VSC_1-", bus1, bus21, bus14),
        ("VSC_2-", bus2, bus22, bus15),
    ]:
        grid.add_vsc(
            gce.VSC(
                name=name,
                bus_to=bus_ac,
                bus_from=bus_dc,
                bus_dc_n=bus_n,
                rate=3000,
                alpha1=a,
                alpha2=b,
                alpha3=c,
                control1=ConverterControlType.Pdc_droop,
                control1_val=1,
                control1_val_min=-3000,
                control1_val_max=3000,
                control1_droop=1,
                control1_droop_val=1.0,
                control1_droop_val_min=0.9,
                control1_droop_val_max=1.1,
                control2=ConverterControlType.Qac,
                control2_val=0.0
            )
        )

    # Offshore VSCs: P control follows the OWF sweep.
    for name, bus_ac, bus_dc, bus_n in [
        ("VSC_3+", bus3, bus8, bus17),
        ("VSC_4+", bus4, bus11, bus20),
        ("VSC_3-", bus3, bus24, bus17),
        ("VSC_4-", bus4, bus27, bus20),
    ]:
        grid.add_vsc(
            gce.VSC(
                name=name,
                bus_to=bus_ac,
                bus_from=bus_dc,
                bus_dc_n=bus_n,
                alpha1=a,
                alpha2=b,
                alpha3=c,
                control1=ConverterControlType.Pac,
                control2=ConverterControlType.Qac,
                control1_val=p_pole,
                control2_val=0.0
            )
        )

    return grid


# =============================================================================
# 6. POWER FLOW
# =============================================================================

def solve_grid(grid):
    options_pf = gce.PowerFlowOptions(
        verbose=0,
        generate_report=False,
        retry_with_other_methods=False,
        use_stored_guess=True,
        tolerance=PF_TOLERANCE
    )

    return gce.power_flow(grid, options=options_pf)


# =============================================================================
# 7. EXTRACT DC CABLE CURRENTS
# =============================================================================

def get_cable_currents_a(results):
    """
    Returns a Series with DC branch active current from-end in amperes.
    """

    df = results.mdl(
        result_type=ResultTypes.BranchActiveCurrentFrom
    ).get_data_frame()

    # The VeraGrid result is in pu on the system current base.
    df_a = df * Ib * 1000.0

    # Usually the dataframe contains one column. Flatten robustly.
    if isinstance(df_a, pd.DataFrame):
        if df_a.shape[1] == 1:
            series = df_a.iloc[:, 0]
        else:
            # If several columns exist, use the first column.
            series = df_a.iloc[:, 0]
    else:
        series = pd.Series(df_a)

    return series


def get_dc_cable_metrics(results):
    """
    Calculates maximum absolute DC cable current and loading.
    Only cables whose name starts with 'dc_cable' are included.
    """

    currents = get_cable_currents_a(results)

    rows = []

    for name, current in currents.items():
        name = str(name)

        if not name.startswith("dc_cable"):
            continue

        current_a = float(np.real(current))
        loading_pct = abs(current_a) / CABLE_RATING_A * 100.0

        rows.append({
            "cable": name,
            "current_A": current_a,
            "abs_current_A": abs(current_a),
            "loading_pct": loading_pct
        })

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError(
            "No DC cable branches were found in BranchActiveCurrentFrom results."
        )

    df = df.sort_values("loading_pct", ascending=False).reset_index(drop=True)

    return df


# =============================================================================
# 8. RUN ONE OPERATING POINT
# =============================================================================

def evaluate_without_pfc(owf_power_mw):
    grid = build_grid(
        with_pfc=False,
        owf_power_mw=owf_power_mw
    )

    results = solve_grid(grid)

    if not results.converged:
        return {
            "case": "Without PFC",
            "owf_power_mw": owf_power_mw,
            "pfc_current_a": np.nan,
            "converged": False,
            "error_pu": results.error,
            "iterations": results.iterations,
            "time_s": results.elapsed,
            "max_loading_pct": np.nan,
            "max_current_A": np.nan,
            "max_cable": "PF did not converge"
        }

    cable_df = get_dc_cable_metrics(results)
    worst = cable_df.iloc[0]

    return {
        "case": "Without PFC",
        "owf_power_mw": owf_power_mw,
        "pfc_current_a": np.nan,
        "converged": True,
        "error_pu": results.error,
        "iterations": results.iterations,
        "time_s": results.elapsed,
        "max_loading_pct": worst["loading_pct"],
        "max_current_A": worst["abs_current_A"],
        "max_cable": worst["cable"]
    }


def evaluate_with_pfc(owf_power_mw):
    """
    For the installed-PFC topology, search the PFC current setpoint and retain
    the operating point that minimizes the maximum DC cable loading.

    This is NOT equivalent to the no-PFC case:
        Is = 0 still means that the PFC is installed.

    The no-PFC case is evaluated separately with the PFC physically absent.
    """

    best = None

    for pfc_current_a in PFC_CURRENT_A:

        grid = build_grid(
            with_pfc=True,
            owf_power_mw=owf_power_mw,
            pfc_current_a=pfc_current_a
        )

        results = solve_grid(grid)

        if not results.converged:
            continue

        cable_df = get_dc_cable_metrics(results)
        worst = cable_df.iloc[0]

        candidate = {
            "case": "With PFC",
            "owf_power_mw": owf_power_mw,
            "pfc_current_a": pfc_current_a,
            "converged": True,
            "error_pu": results.error,
            "iterations": results.iterations,
            "time_s": results.elapsed,
            "max_loading_pct": worst["loading_pct"],
            "max_current_A": worst["abs_current_A"],
            "max_cable": worst["cable"]
        }

        if (
            best is None
            or candidate["max_loading_pct"] < best["max_loading_pct"]
        ):
            best = candidate

    if best is None:
        return {
            "case": "With PFC",
            "owf_power_mw": owf_power_mw,
            "pfc_current_a": np.nan,
            "converged": False,
            "error_pu": np.nan,
            "iterations": np.nan,
            "time_s": np.nan,
            "max_loading_pct": np.nan,
            "max_current_A": np.nan,
            "max_cable": "No converged PFC solution"
        }

    return best


# =============================================================================
# 9. MAIN STUDY
# =============================================================================

if __name__ == "__main__":

    print("\n==============================================================")
    print(" PROSECCO HVDC PFC CONGESTION STUDY")
    print("==============================================================")
    print(f"Ub = {Ub:.1f} kV")
    print(f"Sb = {Sb:.1f} MVA")
    print(f"Ib = {Ib:.6f} kA")
    print(f"Cable rating = {CABLE_RATING_A:.1f} A")
    print("")

    results_all = []

    for p_owf in OWF_POWER_MW:

        print(f"\nOWF power per station = {p_owf:.0f} MW")
        print("-" * 60)

        # ---------------------------------------------------------------------
        # Case 1: physically no PFC
        # ---------------------------------------------------------------------
        no_pfc = evaluate_without_pfc(p_owf)
        results_all.append(no_pfc)

        print(
            f"Without PFC: "
            f"{no_pfc['max_loading_pct']:.2f}% "
            f"({no_pfc['max_cable']})"
            if no_pfc["converged"]
            else "Without PFC: NOT CONVERGED"
        )

        # ---------------------------------------------------------------------
        # Case 2: physically installed PFC
        # ---------------------------------------------------------------------
        with_pfc = evaluate_with_pfc(p_owf)
        results_all.append(with_pfc)

        print(
            f"With PFC:    "
            f"{with_pfc['max_loading_pct']:.2f}% "
            f"({with_pfc['max_cable']}), "
            f"Is = {with_pfc['pfc_current_a']:.0f} A"
            if with_pfc["converged"]
            else "With PFC: NOT CONVERGED"
        )

    df_results = pd.DataFrame(results_all)

    csv_file = os.path.join(
        OUTPUT_DIR,
        "PROSECCO_PFC_congestion_results.csv"
    )
    df_results.to_csv(csv_file, index=False)

    # =============================================================================
    # 10. MONEY GRAPH
    # =============================================================================

    plt.figure(figsize=(7.0, 4.5))

    for case in ["Without PFC", "With PFC"]:

        df_case = df_results[
            (df_results["case"] == case)
            & (df_results["converged"])
        ].sort_values("owf_power_mw")

        plt.plot(
            df_case["owf_power_mw"],
            df_case["max_loading_pct"],
            marker="o",
            linewidth=1.5,
            label=case
        )

    plt.axhline(
        100.0,
        linestyle="--",
        linewidth=1.2,
        label="Cable thermal limit"
    )

    plt.xlabel("OWF power injection per station [MW]")
    plt.ylabel("Maximum DC cable loading [%]")
    plt.grid(True, linestyle=":", alpha=0.7)
    plt.legend()
    plt.tight_layout()

    money_graph = os.path.join(
        OUTPUT_DIR,
        "PROSECCO_PFC_money_graph.pdf"
    )

    plt.savefig(money_graph, format="pdf", bbox_inches="tight")
    plt.savefig(
        os.path.join(
            OUTPUT_DIR,
            "PROSECCO_PFC_money_graph.png"
        ),
        dpi=300,
        bbox_inches="tight"
    )
    plt.show()

    # =============================================================================
    # 11. MAXIMUM FEASIBLE OWF TRANSFER
    # =============================================================================

    feasible = df_results[
        df_results["converged"]
        & (df_results["max_loading_pct"] <= 100.0)
    ].copy()

    print("\n==============================================================")
    print(" MAXIMUM OWF POWER WITHOUT THERMAL CONGESTION")
    print("==============================================================")

    for case in ["Without PFC", "With PFC"]:

        case_feasible = feasible[
            feasible["case"] == case
        ]

        if case_feasible.empty:
            print(f"{case}: no feasible operating point in the sweep")
            continue

        best = case_feasible.loc[
            case_feasible["owf_power_mw"].idxmax()
        ]

        print(
            f"{case}: "
            f"{best['owf_power_mw']:.0f} MW/station, "
            f"max loading = {best['max_loading_pct']:.2f}%, "
            f"worst cable = {best['max_cable']}"
        )

        if case == "With PFC":
            print(
                f"           optimal Is = "
                f"{best['pfc_current_a']:.0f} A"
            )

    # =============================================================================
    # 12. CONGESTION-RELIEF TABLE
    # =============================================================================

    pivot = df_results.pivot(
        index="owf_power_mw",
        columns="case",
        values="max_loading_pct"
    )

    if "Without PFC" in pivot.columns and "With PFC" in pivot.columns:
        pivot["Loading reduction [% points]"] = (
            pivot["Without PFC"] - pivot["With PFC"]
        )

        pivot["Relative reduction [%]"] = (
            100.0
            * (pivot["Without PFC"] - pivot["With PFC"])
            / pivot["Without PFC"]
        )

    table_file = os.path.join(
        OUTPUT_DIR,
        "PROSECCO_PFC_loading_comparison.csv"
    )
    pivot.to_csv(table_file)

    print("\nResults saved to:")
    print(f"  {csv_file}")
    print(f"  {table_file}")
    print(f"  {money_graph}")

    print("\nDone.")
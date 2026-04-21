# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

mpl.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman"],
    "axes.labelsize": 12,
    "font.size": 12,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
})

#
# def plot_results_by_time(csv, what_to_plot='v'):
#     df = pd.read_csv(csv)
#     time = df["Time [s]"]
#
#     # detect unique bus numbers or line numbers from column names
#     if what_to_plot in ['v', 'i_s']:
#         # bus columns: bus3_A, bus3_B, ...
#         bus_ids = sorted({col.split('_')[0][3:] for col in df.columns if col.startswith("bus")})
#
#         plt.figure(figsize=(10, 6))
#         for bid in bus_ids:
#             # find phases: A,B,C,N
#             phases = sorted({col.split('_')[1] for col in df.columns if col.startswith(f"bus{bid}_")})
#             for ph in phases:
#                 series = df[f"bus{bid}_{ph}"]
#                 label = f"bus{bid}_{ph}"
#                 plt.plot(time * 1e3, series, label=label)
#
#         plt.xlabel("Time [ms]")
#         plt.ylabel("Voltage [V]" if what_to_plot == 'v' else "Current [A]")
#         plt.title("Bus Voltages" if what_to_plot == 'v' else "Source Currents")
#         plt.legend()
#         plt.grid(True)
#         plt.ylim([-350000,350000])
#         plt.show()
#
#     if what_to_plot == "i_line":
#
#         # detect line IDs by scanning CSV column names
#         line_ids = sorted({
#             col.split('_')[0][4:]  # extract the number after "line"
#             for col in df.columns
#             if col.startswith("line")
#         })
#
#         plt.figure(figsize=(10, 6))
#
#         for lid in line_ids:
#
#             # detect which phases exist for this line
#             phases = sorted({
#                 col.split('_')[2]  # A, B, C, N
#                 for col in df.columns
#                 if col.startswith(f"line{lid}_")
#             })
#
#             for ph in phases:
#
#                 col_from = f"line{lid}_from_{ph}"
#                 col_to = f"line{lid}_to_{ph}"
#
#                 # make sure both ends exist
#                 if col_from not in df.columns or col_to not in df.columns:
#                     continue
#
#                 I_from = df[col_from]
#                 I_to = df[col_to]
#
#                 plt.plot(time * 1e3, I_from, label=f"line{lid}_from_{ph}")
#                 plt.plot(time * 1e3, -I_to, label=f"line{lid}_to_{ph}")
#
#         plt.xlabel("Time [ms]")
#         plt.ylabel("Current [A]")
#         plt.title("Line Currents")
#         plt.legend()
#         plt.grid(True)
#         plt.show()
#         # # line columns: line1_from_A, line1_to_A, etc.
#         # line_ids = sorted({col.split('_')[0][4:] for col in df.columns if col.startswith("line")})
#         #
#         # plt.figure(figsize=(10, 6))
#         # for lid in line_ids:
#         #     # detect which phases exist
#         #     phases = sorted({col.split('_')[2] for col in df.columns if col.startswith(f"line{lid}_")})
#         #
#         #     for ph in phases:
#         #         Ia = df[f"line{lid}_from_{ph}"]
#         #         Ib = df[f"line{lid}_to_{ph}"]
#         #
#         #         plt.plot(time * 1e3, Ia, label=f"line{lid}_from_{ph}")
#         #         plt.plot(time * 1e3, -Ib, label=f"line{lid}_to_{ph}")
#         #
#         # plt.xlabel("Time [ms]")
#         # plt.ylabel("Current [A]")
#         # plt.title("Line Currents")
#         # plt.legend()
#         # plt.grid(True)
#         # plt.show()
#
# # =============================================================
# # 1) PLOT TENSIONS
# # =============================================================
# def plot_voltages(csv):
#     df = pd.read_csv(csv)
#     time = df["time_s"] * 1e3  # ms
#     # time = df["time_s"]  # s
#
#     plt.figure(figsize=(12, 6))
#
#     for col in df.columns:
#         if col.startswith("v_"):
#             plt.plot(time, df[col], label=col)
#
#     plt.xlabel("Time [ms]")
#     plt.ylabel("Voltage [V]")
#     plt.title("Voltages")
#     plt.grid(True)
#     plt.legend()
#     plt.show()
#
#
# # =============================================================
# # 2) PLOT Isource
# # =============================================================
# def plot_isource(csv):
#     df = pd.read_csv(csv)
#     time = df["time_s"] * 1e3
#
#     plt.figure(figsize=(12, 6))
#
#     for col in df.columns:
#         if col.startswith("Is_"):
#             plt.plot(time, df[col], label=col)
#
#     plt.xlabel("Time [ms]")
#     plt.ylabel("Source Current [A]")
#     plt.title("Injection Currents (Isource)")
#     plt.grid(True)
#     plt.legend()
#     plt.show()
#
#
# # =============================================================
# # 3) PLOT LINE CURRENTS
# # =============================================================
# def plot_ilines(csv):
#     df = pd.read_csv(csv)
#
#     time = df["time_s"] * 1e3  # ms
#     plt.figure(figsize=(12, 6))
#
#     phases = ["a", "b", "c", "n"]
#
#     # detect line names from "Ifrom_a_line 1-2"
#     line_names = sorted({
#         col.split("_line ")[1]
#         for col in df.columns
#         if "_line " in col
#     })
#
#     for line in line_names:
#         for ph in phases:
#             col_from = f"Ifrom_{ph}_line {line}"
#             col_to   = f"Ito_{ph}_line {line}"
#
#             if col_from in df.columns:
#                 plt.plot(time, df[col_from], label=col_from)
#
#             if col_to in df.columns:
#                 plt.plot(time, -df[col_to], label=col_to)
#
#     plt.xlabel("Time [ms]")
#     plt.ylabel("Line Current [A]")
#     plt.title("Line Currents")
#     plt.grid(True)
#     plt.legend()
#     plt.show()
#
#
#
# # =============================================================
# # 4) GENERATOR PLOTS
# # =============================================================
# def plot_generators(x_csv, dx_csv):
#     df_x = pd.read_csv(x_csv)
#     df_dx = pd.read_csv(dx_csv)
#     time = df_x["time_s"] * 1e3
#
#     # detect all generator indices
#     gens = sorted({col.split("_")[-1].replace("Gen","") for col in df_x.columns if "_Gen" in col})
#
#     # ============== THETA =============
#     plt.figure(figsize=(12, 6))
#     for g in gens:
#         for var in ["theta"]:
#             col = f"{var}_Gen{g}"
#             if col in df_x.columns:
#                 plt.plot(time, df_x[col], label=col)
#     plt.legend()
#     plt.grid()
#     plt.title("Rotor angle")
#     plt.xlabel("Time [ms]")
#     plt.ylabel("Rotor angle [rad]")
#     plt.show()
#
#     # ============== OMEGA =============
#     plt.figure(figsize=(12, 6))
#     for g in gens:
#         for var in ["omega"]:
#             col = f"{var}_Gen{g}"
#             if col in df_x.columns:
#                 plt.plot(time, df_x[col], label=col)
#     plt.legend()
#     plt.grid()
#     plt.title("Omega")
#     plt.xlabel("Time [ms]")
#     plt.ylabel("Angular frequency [p.u.]")
#     plt.show()
#     # ============== TORQUES =============
#     plt.figure(figsize=(12,6))
#     for g in gens:
#         for var in ["te", "tm"]:
#             col = f"{var}_Gen{g}"
#             if col in df_x.columns:
#                 plt.plot(time, df_x[col], label=col)
#     plt.ylim([0.5, 1.5])
#     plt.legend()
#     plt.grid()
#     plt.title("Torques")
#     plt.xlabel("Time [ms]")
#     plt.ylabel("Torque [p.u.]")
#     plt.show()
#
#     # ============== POWERS ==============
#     plt.figure(figsize=(12,6))
#     for g in gens:
#         for var in ["Pe", "Qe", "Pm"]:
#             col = f"{var}_Gen{g}"
#             if col in df_x.columns:
#                 plt.plot(time, df_x[col], label=col)
#     plt.legend()
#     plt.grid()
#     plt.title("Electric and mechanical Power")
#     plt.xlabel("Time [ms]")
#     plt.ylabel("Power [p.u.]")
#     plt.show()
#
#     # ============== i_dq0 =================
#     plt.figure(figsize=(12,6))
#     for g in gens:
#         for var in ["i_d", "i_q", "i_0"]:
#             col = f"{var}_Gen{g}"
#             if col in df_x.columns:
#                 plt.plot(time, df_x[col], label=col)
#     plt.legend()
#     plt.grid()
#     plt.title("Currents dq0")
#     plt.xlabel("Time [ms]")
#     plt.ylabel("Current [p.u.]")
#     plt.show()
#
#     # ============== psi_dq0 ===============
#     plt.figure(figsize=(12,6))
#     for g in gens:
#         for var in ["psi_d", "psi_q", "psi_0"]:
#             col = f"{var}_Gen{g}"
#             if col in df_x.columns:
#                 plt.plot(time, df_x[col], label=col)
#     plt.legend()
#     plt.grid()
#     plt.title("Fluxes dq0")
#     plt.xlabel("Time [ms]")
#     plt.ylabel("Electromagnetic flux [p.u.]")
#     plt.show()
#
#
# def plot_v_i(v_csv, x_csv):
#     df_v = pd.read_csv(v_csv)
#     df_x = pd.read_csv(x_csv)
#     time = df_v["time_s"] * 1e3  # ms
#
#     fig, axs = plt.subplots(2, 2, figsize=(12, 8))
#     axs = axs.flatten()
#
#     for col in df_v.columns:
#         if col.startswith("v_") and col.endswith("_Bus1"):
#             axs[0].plot(time, df_v[col], label=col)
#     axs[0].set_title('Voltages abc')
#     axs[0].set_xlabel('Time [ms]')
#     axs[0].set_ylabel('Voltage [p.u.]')
#     # axs[0].set_ylim([-3, 3])  #
#     axs[0].legend(loc='upper right')
#     axs[0].grid(True)
#
#     gens = sorted({col.split("_")[-1].replace("Gen", "") for col in df_x.columns if "_Gen" in col})
#
#     for g in gens:
#         for var in ["v_d", "v_q", "v_0"]:
#             col = f"{var}_Gen{g}"
#             if col in df_x.columns:
#                 axs[2].plot(time, df_x[col], label=col)
#     axs[2].set_title('Voltages dq0')
#     axs[2].set_xlabel('Time [ms]')
#     axs[2].set_ylabel('Voltage [p.u.]')
#     axs[2].set_ylim([-3, 3])  #
#     axs[2].legend(loc='upper right')
#     axs[2].grid(True)
#
#     for g in gens:
#         for var in ["i_a", "i_b", "i_c"]:
#             col = f"{var}_Gen{g}"
#             if col in df_x.columns:
#                 axs[1].plot(time, df_x[col], label=col)
#     axs[1].set_title('Currents abc')
#     axs[1].set_xlabel('Time [ms]')
#     axs[1].set_ylabel('Current [p.u.]')
#     axs[1].set_ylim([-2, 2])
#     axs[1].legend(loc='upper right')
#     axs[1].grid(True)
#
#     for g in gens:
#         for var in ["i_d", "i_q", "i_0"]:
#             col = f"{var}_Gen{g}"
#             if col in df_x.columns:
#                 axs[3].plot(time, df_x[col], label=col)
#     axs[3].set_title('Currents dq0')
#     axs[3].set_xlabel('Time [ms]')
#     axs[3].set_ylabel('Current [p.u.]')
#     axs[3].legend(loc='upper left')
#     axs[3].set_ylim([-2, 2])
#     axs[3].grid(True)
#
#     plt.suptitle('Synchronous Generator – Voltages and Currents', fontsize=14, fontweight='bold')
#     plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.96])
#     plt.show()


    #####################333

def plot_results_by_time(csv, what_to_plot='v'):
    df = pd.read_csv(csv)
    time = df["Time [s]"]

    if what_to_plot in ['v', 'i_s']:
        bus_ids = sorted({col.split('_')[0][3:] for col in df.columns if col.startswith("bus")})

        plt.figure(figsize=(10, 6))
        for bid in bus_ids:
            phases = sorted({col.split('_')[1] for col in df.columns if col.startswith(f"bus{bid}_")})
            for ph in phases:
                series = df[f"bus{bid}_{ph}"]
                label = f"bus{bid}_{ph}"
                plt.plot(time * 1e3, series, label=label)

        plt.xlabel(r"Time [ms]")
        plt.ylabel(r"$Voltage\;[\mathrm{p.u.}]$" if what_to_plot == 'v' else r"$Current \;[\mathrm{p.u.}]$")
        plt.title(r"Bus voltages $v_{abc}$" if what_to_plot == 'v' else r"Source currents")
        plt.legend()
        plt.grid(True)
        plt.ylim([-350000, 350000])
        plt.show()

    if what_to_plot == "i_line":
        line_ids = sorted({
            col.split('_')[0][4:]
            for col in df.columns
            if col.startswith("line")
        })

        plt.figure(figsize=(10, 6))

        for lid in line_ids:
            phases = sorted({
                col.split('_')[2]
                for col in df.columns
                if col.startswith(f"line{lid}_")
            })

            for ph in phases:
                col_from = f"line{lid}_from_{ph}"
                col_to = f"line{lid}_to_{ph}"

                if col_from not in df.columns or col_to not in df.columns:
                    continue

                I_from = df[col_from]
                I_to = df[col_to]

                plt.plot(time * 1e3, I_from, label=f"line{lid}_from_{ph}")
                plt.plot(time * 1e3, -I_to, label=f"line{lid}_to_{ph}")

        plt.xlabel(r"Time [ms]")
        plt.ylabel(r"$i\;[\mathrm{p.u.}]$")
        plt.title(r"Line currents")
        plt.legend()
        plt.grid(True)
        plt.show()

# =============================================================
# 1) PLOT VOLTAGES
# =============================================================
def plot_voltages(csv):
    df = pd.read_csv(csv)
    time = df["time_s"] * 1e3

    plt.figure(figsize=(12, 6))

    for col in df.columns:
        if col.startswith("v_"):
            plt.plot(time, df[col], label=col)

    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"Voltage\;[p.u.]")
    # plt.ylim([-1000,1000])
    plt.title(r"Voltages")
    plt.grid(True)
    plt.legend()
    plt.show()

# =============================================================
# 2) PLOT ISOURCE
# =============================================================
def plot_isource(csv):
    df = pd.read_csv(csv)
    time = df["time_s"] * 1e3

    plt.figure(figsize=(12, 6))

    for col in df.columns:
        if col.startswith("Is_"):
            plt.plot(time, df[col], label=col)

    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"$i_s\;[\mathrm{p.u.}]$")
    plt.title(r"Injection currents $i_s$")
    plt.grid(True)
    plt.legend()
    plt.show()

# =============================================================
# 3) PLOT LINE CURRENTS
# =============================================================
def plot_itrafo(csv):
    df = pd.read_csv(csv)
    time = df["time_s"] * 1e3

    plt.figure(figsize=(12, 6))
    phases = ["a", "b", "c", "n"]

    line_names = sorted({
        col.split("_trafo ")[1]
        for col in df.columns
        if "_trafo " in col
    })

    for line in line_names:
        for ph in phases:
            col_from = f"Ifrom_{ph}_trafo {line}"
            col_to = f"Ito_{ph}_trafo {line}"

            if col_from in df.columns:
                plt.plot(time, df[col_from], label=col_from)

            if col_to in df.columns:
                plt.plot(time, -df[col_to], label=col_to, linestyle='--')

    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"$i_{\mathrm{trafo}}\;[\mathrm{p.u.}]$")
    plt.title(r"Transformer currents")
    plt.grid(True)
    plt.legend()
    plt.show()

def plot_ilines(csv):
    df = pd.read_csv(csv)
    time = df["time_s"] * 1e3

    plt.figure(figsize=(12, 6))
    phases = ["a", "b", "c", "n"]

    line_names = sorted({
        col.split("_line ")[1]
        for col in df.columns
        if "_line " in col
    })

    for line in line_names:
        for ph in phases:
            col_from = f"Ifrom_{ph}_line {line}"
            col_to = f"Ito_{ph}_line {line}"

            if col_from in df.columns:
                plt.plot(time, df[col_from], label=col_from)

            if col_to in df.columns:
                plt.plot(time, -df[col_to], label=col_to)

    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"$i_{\mathrm{line}}\;[\mathrm{p.u.}]$")
    plt.title(r"Line currents")
    plt.grid(True)
    plt.legend()
    plt.show()

# =============================================================
# 4) GENERATOR PLOTS
# =============================================================
def plot_generators(x_csv, dx_csv):
    df_x = pd.read_csv(x_csv)
    df_dx = pd.read_csv(dx_csv)
    time = df_x["time_s"] * 1e3

    gens = sorted({col.split("_")[-1].replace("Gen", "") for col in df_x.columns if "_Gen" in col})

    # Rotor angle
    plt.figure(figsize=(12, 6))
    for g in gens:
        col = f"theta_Gen{g}"
        if col in df_x.columns:
            plt.plot(time, df_x[col], label=col)
    plt.title(r"Rotor angle $\theta$")
    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"$\theta\;[\mathrm{rad}]$")
    plt.legend()
    plt.grid()
    plt.show()

    # Omega
    plt.figure(figsize=(12, 6))
    for g in gens:
        col = f"omega_Gen{g}"
        if col in df_x.columns:
            plt.plot(time, df_x[col], label=col)
    plt.title(r"Angular speed $\omega$")
    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"$\omega\;[\mathrm{p.u.}]$")
    plt.legend()
    plt.grid()
    plt.show()

    # Torques
    plt.figure(figsize=(12, 6))
    for g in gens:
        for var in ["Te", "Tm"]:
            col = f"{var}_Gen{g}"
            if col in df_x.columns:
                plt.plot(time, df_x[col], label=col)
    plt.ylim([0.5, 1.5])
    plt.title(r"Torques")
    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"$\Gamma~[\mathrm{p.u.}]$")
    plt.legend()
    plt.grid()
    plt.show()

    # Powers
    plt.figure(figsize=(12, 6))
    for g in gens:
        for var in ["Pe", "Qe", "Pm"]:
            col = f"{var}_Gen{g}"
            if col in df_x.columns:
                plt.plot(time, df_x[col], label=col)
    plt.title(r"Electric and mechanical power")
    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"Power $[\mathrm{p.u.}]$")
    plt.legend()
    plt.grid()
    plt.show()

    # Currents dq0
    plt.figure(figsize=(12, 6))
    for g in gens:
        for var in ["i_d", "i_q", "i_0"]:
            col = f"{var}_Gen{g}"
            if col in df_x.columns:
                plt.plot(time, df_x[col], label=col)
    plt.title(r"Currents in $dq0$ frame")
    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"Current $[\mathrm{p.u.}]$")
    plt.legend()
    plt.grid()
    plt.show()

    # Fluxes dq0
    plt.figure(figsize=(12, 6))
    for g in gens:
        for var in ["psi_d", "psi_q", "psi_0"]:
            col = f"{var}_Gen{g}"
            if col in df_x.columns:
                plt.plot(time, df_x[col], label=col)
    plt.title(r"Fluxes in $dq0$ frame")
    plt.xlabel(r"Time [ms]")
    plt.ylabel(r"$\psi\;[\mathrm{p.u.}]$")
    plt.legend()
    plt.grid()
    plt.show()

# =============================================================
# 5) COMBINED VOLTAGE & CURRENT PLOTS
# =============================================================
def plot_v_i(v_csv, x_csv):
    df_v = pd.read_csv(v_csv)
    df_x = pd.read_csv(x_csv)
    time = df_v["time_s"] * 1e3

    fig, axs = plt.subplots(2, 2, figsize=(12, 8))
    axs = axs.flatten()

    for col in df_v.columns:
        if col.startswith("v_") and col.endswith("_Bus1"):
            axs[0].plot(time, df_v[col], label=col)
    axs[0].set_title(r"Voltages $v_{abc}$")
    axs[0].set_xlabel(r"Time [ms]")
    axs[0].set_ylabel(r"Voltage\;$[\mathrm{p.u.}]$")
    axs[0].legend(loc="upper right")
    axs[0].grid(True)

    gens = sorted({col.split("_")[-1].replace("Gen", "") for col in df_x.columns if "_Gen" in col})

    for g in gens:
        for var in ["v_d", "v_q", "v_0"]:
            col = f"{var}_Gen{g}"
            if col in df_x.columns:
                axs[2].plot(time, df_x[col], label=col)
    axs[2].set_title(r"Voltages $v_{dq0}$")
    axs[2].set_xlabel(r"Time [ms]")
    axs[2].set_ylabel(r"Voltage\;$[\mathrm{p.u.}]$")
    axs[2].set_ylim([-3, 3])
    axs[2].legend(loc="upper right")
    axs[2].grid(True)

    for g in gens:
        for var in ["i_a", "i_b", "i_c"]:
            col = f"{var}_Gen{g}"
            if col in df_x.columns:
                axs[1].plot(time, df_x[col], label=col)
    axs[1].set_title(r"Currents $i_{abc}$")
    axs[1].set_xlabel(r"Time [ms]")
    axs[1].set_ylabel(r"Current\;$[\mathrm{p.u.}]$")
    axs[1].set_ylim([-2, 2])
    axs[1].legend(loc="upper right")
    axs[1].grid(True)

    for g in gens:
        for var in ["i_d", "i_q", "i_0"]:
            col = f"{var}_Gen{g}"
            if col in df_x.columns:
                axs[3].plot(time, df_x[col], label=col)
    axs[3].set_title(r"Currents $i_{dq0}$")
    axs[3].set_xlabel(r"Time [ms]")
    axs[3].set_ylabel(r"Current\;$[\mathrm{p.u.}]$")
    axs[3].set_ylim([-2, 2])
    axs[3].legend(loc="upper left")
    axs[3].grid(True)

    plt.suptitle(
        r"Synchronous generator -- voltages and currents",
        fontsize=14
    )
    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.96])
    plt.show()






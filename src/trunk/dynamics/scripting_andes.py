# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
To run this script andes must be installed (pip install andes)
"""
import andes
import time 
from andes.io.json import write
import matplotlib
import pandas as pd
import numpy as np
matplotlib.use('TkAgg')  # or 'QtAgg', depending on your system

def main():
    
    # ss = andes.load('src/trunk/dynamics/Two_Areas_PSS_E/Benchmark_4ger_33_2015.raw', default_config=True)
    # write(ss, 'my_system.json', overwrite=True)

    np.set_printoptions(precision=15, suppress=False)

    start = time.time()
    # ss = andes.load('Gen_Load/kundur_ieee_no_shunt.json', default_config=True)
    ss = andes.load('Gen_Load/simple_system3.json', default_config=True)
    n_xy = len(ss.dae.xy_name)
    print(f"Andes variables = {n_xy}")
    ss.files.no_output = True

    # fix P & Q load Andes
    ss.PQ.config.p2p = 1.0
    ss.PQ.config.p2i = 0
    ss.PQ.config.p2z = 0

    ss.PQ.config.q2q = 1.0
    ss.PQ.config.q2i = 0
    ss.PQ.config.q2z = 0

    # Run PF
    ss.PFlow.config.tol = 1e-6
    ss.PFlow.run()

    print(f"Bus voltages = {ss.Bus.v.v}")
    print(f"Bus angles = {ss.Bus.a.v}")

    end_pf = time.time()
    print(f"ANDES - PF time = {end_pf-start:.6f} [s]")


    # Logging
    time_history = []
    #bus
    v_history = [[] for _ in range(len(ss.Bus))]
    a_history = [[] for _ in range(len(ss.Bus))]

    #PV
    q_PV_history = [[] for _ in range(len(ss.PV))] #

    #slack
    p_Slack_history = [[] for _ in range(len(ss.Slack))] #
    q_Slack_history = [[] for _ in range(len(ss.Slack))] #

    #GENCLS
    delta_history = [[] for _ in range(len(ss.GENCLS))] #
    omega_history = [[] for _ in range(len(ss.GENCLS))]
    Id_history = [[] for _ in range(len(ss.GENCLS))] #
    Iq_history = [[] for _ in range(len(ss.GENCLS))] #
    vd_history = [[] for _ in range(len(ss.GENCLS))] #
    vq_history = [[] for _ in range(len(ss.GENCLS))] #
    tm_history = [[] for _ in range(len(ss.GENCLS))]
    te_history = [[] for _ in range(len(ss.GENCLS))]
    Pe_history = [[] for _ in range(len(ss.GENCLS))]  #
    Qe_history = [[] for _ in range(len(ss.GENCLS))]  #
    psid_history = [[] for _ in range(len(ss.GENCLS))]  #
    psiq_history = [[] for _ in range(len(ss.GENCLS))]  #
    vf_history = [[] for _ in range(len(ss.GENCLS))]
    XadIfd_history = [[] for _ in range(len(ss.GENCLS))] #

    #PQ (load)
    Ppf_history = [[] for _ in range(len(ss.PQ))]
    Qpf_history = [[] for _ in range(len(ss.PQ))] #
    
    start_tds = time.time()
    # Run TDS
    tds = ss.TDS
    tds.config.fixt = 1
    tds.config.shrinkt = 0
    tds.config.tstep = 0.001
    tds.config.tf = 20.0
    tds.t = 0.0
    tds.init()
    print(len(ss.dae.x))
    print(len(ss.dae.y))

    end_tds = time.time()
    print(f"ANDES - Compiling time = {end_tds-start_tds:.6f} [s]")

    one = True
    # Step-by-step simulation
    start_sim = time.time()

    while tds.t < tds.config.tf:

        if tds.t > 2.5 and one == True:
            # ss.PQ.set(src='Ppf', idx='PQ_1', attr='v', value=9.0)  #event
            one = False
            # Log current state
        time_history.append(tds.t)
        for i in range(len(ss.Bus)):
            v_history[i].append(ss.Bus.v.v[i])
            a_history[i].append(ss.Bus.a.v[i])
        for i in range(len(ss.PV)):
            q_PV_history[i].append(ss.PV.q.v[i]) #
        for i in range(len(ss.Slack)):
            p_Slack_history[i].append(ss.Slack.p.v[i])  #
            q_Slack_history[i].append(ss.Slack.q.v[i]) #
        for i in range(len(ss.GENCLS)):
            delta_history[i].append(ss.GENCLS.delta.v[i]) #
            omega_history[i].append(ss.GENCLS.omega.v[i])
            Id_history[i].append(ss.GENCLS.Id.v[i]) #
            Iq_history[i].append(ss.GENCLS.Iq.v[i]) #
            vd_history[i].append(ss.GENCLS.vd.v[i]) #
            vq_history[i].append(ss.GENCLS.vq.v[i]) #
            tm_history[i].append(ss.GENCLS.tm.v[i])
            te_history[i].append(ss.GENCLS.te.v[i])
            Pe_history[i].append(ss.GENCLS.Pe.v[i])  #
            Qe_history[i].append(ss.GENCLS.Qe.v[i])  #
            psid_history[i].append(ss.GENCLS.psid.v[i])  #
            psiq_history[i].append(ss.GENCLS.psiq.v[i])
            vf_history[i].append(ss.GENCLS.vf.v[i])
            XadIfd_history[i].append(ss.GENCLS.XadIfd.v[i]) #
        for i in range(len(ss.PQ)):
            Ppf_history[i].append(ss.PQ.Ppf.v[i])
            Qpf_history[i].append(ss.PQ.Qpf.v[i]) #


        # Advance one time step
        tds.itm_step()
        tds.t += tds.config.tstep

    end = time.time()
    print(f"ANDES - Execution time: {end - start_sim:.6f} [s]")

    #add to csv
    #bus
    v_df = pd.DataFrame(list(zip(*v_history)))  # shape: [T, n_loads]
    v_df.columns = [f"v_andes_Bus_{i + 1}" for i in range(len(v_history))]
    a_df = pd.DataFrame(list(zip(*a_history)))  # shape: [T, n_loads]
    a_df.columns = [f"a_andes_Bus_{i + 1}" for i in range(len(a_history))]

    #PV
    q_PV_df = pd.DataFrame(list(zip(*q_PV_history)))  # shape: [T, n_loads]
    q_PV_df.columns = [f"q_PV_andes_{i + 1}" for i in range(len(q_PV_history))]

    #slack
    p_Slack_df = pd.DataFrame(list(zip(*p_Slack_history)))  # shape: [T, n_loads]
    p_Slack_df.columns = [f"p_Slack_andes_{i}" for i in range(len(p_Slack_history))]
    q_Slack_df = pd.DataFrame(list(zip(*q_Slack_history)))  # shape: [T, n_loads]
    q_Slack_df.columns = [f"q_Slack_andes_{i}" for i in range(len(q_Slack_history))]

    #GENCLS
    delta_df = pd.DataFrame(list(zip(*delta_history)))  # shape: [T, n_generators]  #
    delta_df.columns = [f"delta_andes_gen_{i + 1}" for i in range(len(delta_history))] #
    omega_df = pd.DataFrame(list(zip(*omega_history)))  # shape: [T, n_generators]
    omega_df.columns = [f"omega_andes_gen_{i+1}" for i in range(len(omega_history))]
    Id_df = pd.DataFrame(list(zip(*Id_history)))  # shape: [T, n_generators] #
    Id_df.columns = [f"Id_andes_gen_{i + 1}" for i in range(len(Id_history))] #
    Iq_df = pd.DataFrame(list(zip(*Iq_history)))  # shape: [T, n_generators] #
    Iq_df.columns = [f"Iq_andes_gen_{i + 1}" for i in range(len(Iq_history))] #
    vd_df = pd.DataFrame(list(zip(*vd_history)))  # shape: [T, n_generators] #
    vd_df.columns = [f"vd_andes_gen_{i + 1}" for i in range(len(vd_history))] #
    vq_df = pd.DataFrame(list(zip(*vq_history)))  # shape: [T, n_generators] #
    vq_df.columns = [f"vq_andes_gen_{i + 1}" for i in range(len(vq_history))] #
    tm_df = pd.DataFrame(list(zip(*tm_history)))  # shape: [T, n_generators]
    tm_df.columns = [f"tm_andes_gen_{i+1}" for i in range(len(omega_history))]
    te_df = pd.DataFrame(list(zip(*te_history)))  # shape: [T, n_generators]
    te_df.columns = [f"te_andes_gen_{i+1}" for i in range(len(omega_history))]
    Pe_df = pd.DataFrame(list(zip(*Pe_history)))  # shape: [T, n_generators] #
    Pe_df.columns = [f"Pe_andes_gen_{i + 1}" for i in range(len(Pe_history))]  #
    Qe_df = pd.DataFrame(list(zip(*Qe_history)))  # shape: [T, n_generators] #
    Qe_df.columns = [f"Qe_andes_gen_{i + 1}" for i in range(len(Qe_history))]  #
    psid_df = pd.DataFrame(list(zip(*psid_history)))  # shape: [T, n_loads]
    psid_df.columns = [f"psid_andes_gen_{i + 1}" for i in range(len(psid_history))]
    psiq_df = pd.DataFrame(list(zip(*psiq_history)))  # shape: [T, n_loads]
    psiq_df.columns = [f"psiq_andes_gen_{i + 1}" for i in range(len(psiq_history))]
    vf_df = pd.DataFrame(list(zip(*vf_history)))  # shape: [T, n_loads]
    vf_df.columns = [f"vf_andes_gen_{i + 1}" for i in range(len(vf_history))]
    XadIfd_df = pd.DataFrame(list(zip(*XadIfd_history)))  # shape: [T, n_generators] #
    XadIfd_df.columns = [f"XadIfd_andes_gen_{i + 1}" for i in range(len(XadIfd_history))] #

    #PQ
    Ppf_df = pd.DataFrame(list(zip(*Ppf_history)))      # shape: [T, n_loads]
    Ppf_df.columns = [f"Ppf_andes_load_{i}" for i in range(len(Ppf_history))]
    Qpf_df = pd.DataFrame(list(zip(*Qpf_history)))  # shape: [T, n_loads]
    Qpf_df.columns = [f"Qpf_andes_load_{i}" for i in range(len(Qpf_history))]

    # Combine all into a single DataFrame
    df = pd.DataFrame({'Time [s]': time_history})
    df = pd.concat([ df, v_df, a_df, q_PV_df, p_Slack_df, q_Slack_df, delta_df, omega_df, Id_df, Iq_df, vd_df,
                     vq_df, tm_df, te_df, Pe_df, Qe_df, psid_df, psiq_df, vf_df, XadIfd_df, Qpf_df, Ppf_df ], axis=1)
    df.to_csv("simulation_andes_output.csv", index=False)
    print('simulation results saved in simulation_andes_output.csv')

    # # Plot
    # plt.figure(figsize=(10, 6))
    # for i, omega in enumerate(omega_history):
    #     plt.plot(time_history, omega, label=f'Gen {i+1}')
    # plt.xlabel("Time [s]")
    # plt.ylabel("Speed [pu]")
    # plt.title("Generator Speed ω vs Time")
    # plt.legend()
    # plt.grid(True)
    # plt.tight_layout()
    # plt.show()

if __name__ == '__main__':
    main()



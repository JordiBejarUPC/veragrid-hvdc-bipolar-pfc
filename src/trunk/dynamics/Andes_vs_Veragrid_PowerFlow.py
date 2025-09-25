# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pdb

import pandas as pd
import matplotlib.pyplot as plt

df_VeraGrid_PF = pd.read_csv('PowerFlow_VeraGrid_output.csv')
df_Andes_PF = pd.read_csv('PowerFlow_andes_output.csv')

#variables veragrid
v_bus1_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_1"]
v_bus2_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_2"]
v_bus3_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_3"]
v_bus4_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_4"]
# v_bus5_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_5"]
# v_bus6_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_6"]
# v_bus7_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_7"]
# v_bus8_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_8"]
# v_bus9_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_9"]
# v_bus10_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_10"]
# v_bus11_V_PF = df_VeraGrid_PF["v_PF_VeraGrid_Bus_11"]

a_bus1_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_1"]
a_bus2_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_2"]
a_bus3_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_3"]
a_bus4_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_4"]
# a_bus5_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_5"]
# a_bus6_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_6"]
# a_bus7_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_7"]
# a_bus8_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_8"]
# a_bus9_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_9"]
# a_bus10_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_10"]
# a_bus11_V_PF = df_VeraGrid_PF["a_PF_VeraGrid_Bus_11"]

p_bus1_V_PF = df_VeraGrid_PF["p_PF_VeraGrid_Bus_1"]
p_bus2_V_PF = df_VeraGrid_PF["p_PF_VeraGrid_Bus_2"]
p_bus3_V_PF = df_VeraGrid_PF["p_PF_VeraGrid_Bus_3"]
p_bus4_V_PF = df_VeraGrid_PF["p_PF_VeraGrid_Bus_4"]
q_bus1_V_PF = df_VeraGrid_PF["q_PF_VeraGrid_Bus_1"]
q_bus2_V_PF = df_VeraGrid_PF["q_PF_VeraGrid_Bus_2"]
q_bus3_V_PF = df_VeraGrid_PF["q_PF_VeraGrid_Bus_3"]
q_bus4_V_PF = df_VeraGrid_PF["q_PF_VeraGrid_Bus_4"]
#variables andes
v_bus1_A_PF = df_Andes_PF["v_PF_andes_Bus_1"]
v_bus2_A_PF = df_Andes_PF["v_PF_andes_Bus_2"]
v_bus3_A_PF = df_Andes_PF["v_PF_andes_Bus_3"]
v_bus4_A_PF = df_Andes_PF["v_PF_andes_Bus_4"]
# v_bus5_A_PF = df_Andes_PF["v_PF_andes_Bus_5"]
# v_bus6_A_PF = df_Andes_PF["v_PF_andes_Bus_6"]
# v_bus7_A_PF = df_Andes_PF["v_PF_andes_Bus_7"]
# v_bus8_A_PF = df_Andes_PF["v_PF_andes_Bus_8"]
# v_bus9_A_PF = df_Andes_PF["v_PF_andes_Bus_9"]
# v_bus10_A_PF = df_Andes_PF["v_PF_andes_Bus_10"]
# v_bus11_A_PF = df_Andes_PF["v_PF_andes_Bus_11"]


a_bus1_A_PF = df_Andes_PF["a_PF_andes_Bus_1"]
a_bus2_A_PF = df_Andes_PF["a_PF_andes_Bus_2"]
a_bus3_A_PF = df_Andes_PF["a_PF_andes_Bus_3"]
a_bus4_A_PF = df_Andes_PF["a_PF_andes_Bus_4"]
# a_bus5_A_PF = df_Andes_PF["a_PF_andes_Bus_5"]
# a_bus6_A_PF = df_Andes_PF["a_PF_andes_Bus_6"]
# a_bus7_A_PF = df_Andes_PF["a_PF_andes_Bus_7"]
# a_bus8_A_PF = df_Andes_PF["a_PF_andes_Bus_8"]
# a_bus9_A_PF = df_Andes_PF["a_PF_andes_Bus_9"]
# a_bus10_A_PF = df_Andes_PF["a_PF_andes_Bus_10"]
# a_bus11_A_PF = df_Andes_PF["a_PF_andes_Bus_11"]

p_bus1_A_PF = df_Andes_PF["p_Slack_PF_andes_0"]
p_bus4_A_PF = df_Andes_PF["Ppf_PF_andes_load_0"]
q_bus1_A_PF = df_Andes_PF["q_Slack_PF_andes_0"]
q_bus3_A_PF = df_Andes_PF["q_PV_PF_andes_1"]
q_bus4_A_PF = df_Andes_PF["Qpf_PF_andes_load_0"]

#error [%]
v_Bus1_PF = (abs(v_bus1_A_PF)-abs(v_bus1_V_PF))*100/abs(v_bus1_A_PF)
v_Bus2_PF = (abs(v_bus2_A_PF)-abs(v_bus2_V_PF))*100/abs(v_bus2_A_PF)
v_Bus3_PF = (abs(v_bus3_A_PF)-abs(v_bus3_V_PF))*100/abs(v_bus3_A_PF)
v_Bus4_PF = (abs(v_bus4_A_PF)-abs(v_bus4_V_PF))*100/abs(v_bus4_A_PF)
# v_Bus5_PF = (abs(v_bus5_A_PF)-abs(v_bus5_V_PF))*100/abs(v_bus5_A_PF)
# v_Bus6_PF = (abs(v_bus6_A_PF)-abs(v_bus6_V_PF))*100/abs(v_bus6_A_PF)
# v_Bus7_PF = (abs(v_bus7_A_PF)-abs(v_bus7_V_PF))*100/abs(v_bus7_A_PF)
# v_Bus8_PF = (abs(v_bus8_A_PF)-abs(v_bus8_V_PF))*100/abs(v_bus8_A_PF)
# v_Bus9_PF = (abs(v_bus9_A_PF)-abs(v_bus9_V_PF))*100/abs(v_bus9_A_PF)
# v_Bus10_PF = (abs(v_bus10_A_PF)-abs(v_bus10_V_PF))*100/abs(v_bus10_A_PF)
# v_Bus11_PF = (abs(v_bus11_A_PF)-abs(v_bus11_V_PF))*100/abs(v_bus11_A_PF)

a_Bus1_PF = (abs(a_bus1_A_PF)-abs(a_bus1_V_PF))*100/abs(a_bus1_A_PF)
a_Bus2_PF = (abs(a_bus2_A_PF)-abs(a_bus2_V_PF))*100/abs(a_bus2_A_PF)
a_Bus3_PF = (abs(a_bus3_A_PF)-abs(a_bus3_V_PF))*100/abs(a_bus3_A_PF)
a_Bus4_PF = (abs(a_bus4_A_PF)-abs(a_bus4_V_PF))*100/abs(a_bus4_A_PF)
# a_Bus5_PF = (abs(a_bus5_A_PF)-abs(a_bus5_V_PF))*100/abs(a_bus5_A_PF)
# a_Bus6_PF = (abs(a_bus6_A_PF)-abs(a_bus6_V_PF))*100/abs(a_bus6_A_PF)
# a_Bus7_PF = (abs(a_bus7_A_PF)-abs(a_bus7_V_PF))*100/abs(a_bus7_A_PF)
# a_Bus8_PF = (abs(a_bus8_A_PF)-abs(a_bus8_V_PF))*100/abs(a_bus8_A_PF)
# a_Bus9_PF = (abs(a_bus9_A_PF)-abs(a_bus9_V_PF))*100/abs(a_bus9_A_PF)
# a_Bus10_PF = (abs(a_bus10_A_PF)-abs(a_bus10_V_PF))*100/abs(a_bus10_A_PF)
# a_Bus11_PF = (abs(a_bus11_A_PF)-abs(a_bus11_V_PF))*100/abs(a_bus11_A_PF)

p_Bus1_PF = (abs(p_bus1_A_PF)-abs(p_bus1_V_PF))*100/abs(p_bus1_A_PF)
p_Bus4_PF = (abs(p_bus4_A_PF)-abs(p_bus4_V_PF))*100/abs(p_bus4_A_PF)
q_Bus1_PF = (abs(q_bus1_A_PF)-abs(q_bus1_V_PF))*100/abs(q_bus1_A_PF)
q_Bus3_PF = (abs(q_bus3_A_PF)-abs(q_bus3_V_PF))*100/abs(q_bus3_A_PF)
q_Bus4_PF = (abs(q_bus4_A_PF)-abs(q_bus4_V_PF))*100/abs(q_bus4_A_PF)

# df_errors_PF = pd.DataFrame({
#     "Variable": ["v_Bus1", "v_Bus2", "v_Bus3", "v_Bus4","v_Bus5", "v_Bus6", "v_Bus7", "v_Bus8","v_Bus9", "v_Bus10",
#                  "v_Bus11", "a_Bus1", "a_Bus2", "a_Bus3", "a_Bus4","a_Bus5", "a_Bus6", "a_Bus7", "a_Bus8", "a_Bus9",
#                  "a_Bus10", "a_Bus11","p_Bus1","p_Bus4", "q_Bus1","q_Bus3", "q_Bus4"],
#     "Abs_error": [v_Bus1_PF, v_Bus2_PF, v_Bus3_PF, v_Bus4_PF, v_Bus5_PF, v_Bus6_PF, v_Bus7_PF, v_Bus8_PF,v_Bus9_PF,
#                   v_Bus10_PF, v_Bus11_PF, a_Bus1_PF, a_Bus2_PF, a_Bus3_PF, a_Bus4_PF, a_Bus5_PF, a_Bus5_PF, a_Bus7_PF,
#                   a_Bus8_PF,a_Bus9_PF, a_Bus10_PF, a_Bus11_PF, p_Bus1_PF, p_Bus4_PF, q_Bus1_PF, q_Bus3_PF, q_Bus4_PF ]
# })
df_errors_PF = pd.DataFrame({
    "Variable": ["v_Bus1", "v_Bus2", "v_Bus3", "v_Bus4", "a_Bus1", "a_Bus2", "a_Bus3", "a_Bus4","p_Bus1",
                 "p_Bus4", "q_Bus1","q_Bus3", "q_Bus4"],
    "Abs_error": [v_Bus1_PF, v_Bus2_PF, v_Bus3_PF, v_Bus4_PF, a_Bus1_PF, a_Bus2_PF, a_Bus3_PF, a_Bus4_PF,
                  p_Bus1_PF, p_Bus4_PF, q_Bus1_PF, q_Bus3_PF, q_Bus4_PF ]
})
df_errors_PF.to_csv("error_PowerFlow.csv", index=False)
print(df_errors_PF)

# variables error comparison
#state vars
df_VeraGrid_ini = pd.read_csv('init_guess_VeraGrid_output.csv')
df_Andes_sim = pd.read_csv('simulation_andes_output.csv')

#variables veragrid
#bus
v_bus1_V_ini = df_VeraGrid_ini["Vm_VeraGrid_Bus_1"]
v_bus2_V_ini = df_VeraGrid_ini["Vm_VeraGrid_Bus_2"]
v_bus3_V_ini = df_VeraGrid_ini["Vm_VeraGrid_Bus_3"]
v_bus4_V_ini = df_VeraGrid_ini["Vm_VeraGrid_Bus_4"]
a_bus1_V_ini = df_VeraGrid_ini["Va_VeraGrid_Bus_1"]
a_bus2_V_ini = df_VeraGrid_ini["Va_VeraGrid_Bus_2"]
a_bus3_V_ini = df_VeraGrid_ini["Va_VeraGrid_Bus_3"]
a_bus4_V_ini = df_VeraGrid_ini["Va_VeraGrid_Bus_4"]
#line
Pf_line1_V_ini = df_VeraGrid_ini["Pf_VeraGrid_line_1"]
Pf_line2_V_ini = df_VeraGrid_ini["Pf_VeraGrid_line_2"]
Pf_line3_V_ini = df_VeraGrid_ini["Pf_VeraGrid_line_3"]
Pt_line1_V_ini = df_VeraGrid_ini["Pt_VeraGrid_line_1"]
Pt_line2_V_ini = df_VeraGrid_ini["Pt_VeraGrid_line_2"]
Pt_line3_V_ini = df_VeraGrid_ini["Pt_VeraGrid_line_3"]
Qf_line1_V_ini = df_VeraGrid_ini["Qf_VeraGrid_line_1"]
Qf_line2_V_ini = df_VeraGrid_ini["Qf_VeraGrid_line_2"]
Qf_line3_V_ini = df_VeraGrid_ini["Qf_VeraGrid_line_3"]
Qt_line1_V_ini = df_VeraGrid_ini["Qt_VeraGrid_line_1"]
Qt_line2_V_ini = df_VeraGrid_ini["Qt_VeraGrid_line_2"]
Qt_line3_V_ini = df_VeraGrid_ini["Qt_VeraGrid_line_3"]
#gencls
delta_gen1_V_ini = df_VeraGrid_ini["delta_VeraGrid_gen_1"]
delta_gen2_V_ini = df_VeraGrid_ini["delta_VeraGrid_gen_2"]
omega_gen1_V_ini = df_VeraGrid_ini["omega_VeraGrid_gen_1"]
omega_gen2_V_ini = df_VeraGrid_ini["omega_VeraGrid_gen_2"]
Id_gen1_V_ini = df_VeraGrid_ini["Id_VeraGrid_gen_1"]
Id_gen2_V_ini = df_VeraGrid_ini["Id_VeraGrid_gen_2"]
Iq_gen1_V_ini = df_VeraGrid_ini["Iq_VeraGrid_gen_1"]
Iq_gen2_V_ini = df_VeraGrid_ini["Iq_VeraGrid_gen_2"]
vd_gen1_V_ini = df_VeraGrid_ini["vd_VeraGrid_gen_1"]
vd_gen2_V_ini = df_VeraGrid_ini["vd_VeraGrid_gen_2"]
vq_gen1_V_ini = df_VeraGrid_ini["vq_VeraGrid_gen_1"]
vq_gen2_V_ini = df_VeraGrid_ini["vq_VeraGrid_gen_2"]
tm_gen1_V_ini = df_VeraGrid_ini["tm_VeraGrid_gen_1"]
tm_gen2_V_ini = df_VeraGrid_ini["tm_VeraGrid_gen_2"]
te_gen1_V_ini = df_VeraGrid_ini["te_VeraGrid_gen_1"]
te_gen2_V_ini = df_VeraGrid_ini["te_VeraGrid_gen_2"]
Pg_gen1_V_ini = df_VeraGrid_ini["Pg_VeraGrid_gen_1"]
Pg_gen2_V_ini = df_VeraGrid_ini["Pg_VeraGrid_gen_2"]
Qg_gen1_V_ini = df_VeraGrid_ini["Qg_VeraGrid_gen_1"]
Qg_gen2_V_ini = df_VeraGrid_ini["Qg_VeraGrid_gen_2"]
psid_gen1_V_ini = df_VeraGrid_ini["psid_VeraGrid_gen_1"]
psid_gen2_V_ini = df_VeraGrid_ini["psid_VeraGrid_gen_2"]
psiq_gen1_V_ini = df_VeraGrid_ini["psiq_VeraGrid_gen_1"]
psiq_gen2_V_ini = df_VeraGrid_ini["psiq_VeraGrid_gen_2"]
et_gen1_V_ini = df_VeraGrid_ini["et_VeraGrid_gen_1"]
et_gen2_V_ini = df_VeraGrid_ini["et_VeraGrid_gen_2"]
#load
Pl_load_V_ini = df_VeraGrid_ini["Pl_VeraGrid_load_1"]
Ql_load_V_ini = df_VeraGrid_ini["Ql_VeraGrid_load_1"]

#variables andes
#bus
v_bus1_A_ini = df_Andes_sim["v_andes_Bus_1"][0]
v_bus2_A_ini = df_Andes_sim["v_andes_Bus_2"][0]
v_bus3_A_ini = df_Andes_sim["v_andes_Bus_3"][0]
v_bus4_A_ini = df_Andes_sim["v_andes_Bus_4"][0]
a_bus1_A_ini = df_Andes_sim["a_andes_Bus_1"][0]
a_bus2_A_ini = df_Andes_sim["a_andes_Bus_2"][0]
a_bus3_A_ini = df_Andes_sim["a_andes_Bus_3"][0]
a_bus4_A_ini = df_Andes_sim["a_andes_Bus_4"][0]
#PV
q_PV_A_ini = df_Andes_sim["q_PV_andes_1"][0]
#slack
p_Slack_A_ini = df_Andes_sim["p_Slack_andes_0"][0]
q_Slack_A_ini = df_Andes_sim["q_Slack_andes_0"][0]
#gencls
delta_gen1_A_ini = df_Andes_sim["delta_andes_gen_1"]
delta_gen2_A_ini = df_Andes_sim["delta_andes_gen_2"]
omega_gen1_A_ini = df_Andes_sim["omega_andes_gen_1"]
omega_gen2_A_ini = df_Andes_sim["omega_andes_gen_2"]
Id_gen1_A_ini = df_Andes_sim["Id_andes_gen_1"]
Id_gen2_A_ini = df_Andes_sim["Id_andes_gen_2"]
Iq_gen1_A_ini = df_Andes_sim["Iq_andes_gen_1"]
Iq_gen2_A_ini = df_Andes_sim["Iq_andes_gen_2"]
vd_gen1_A_ini = df_Andes_sim["vd_andes_gen_1"]
vd_gen2_A_ini = df_Andes_sim["vd_andes_gen_2"]
vq_gen1_A_ini = df_Andes_sim["vq_andes_gen_1"]
vq_gen2_A_ini = df_Andes_sim["vq_andes_gen_2"]
tm_gen1_A_ini = df_Andes_sim["tm_andes_gen_1"]
tm_gen2_A_ini = df_Andes_sim["tm_andes_gen_2"]
te_gen1_A_ini = df_Andes_sim["te_andes_gen_1"]
te_gen2_A_ini = df_Andes_sim["te_andes_gen_2"]
Pg_gen1_A_ini = df_Andes_sim["Pe_andes_gen_1"]
Pg_gen2_A_ini = df_Andes_sim["Pe_andes_gen_2"]
Qg_gen1_A_ini = df_Andes_sim["Qe_andes_gen_1"]
Qg_gen2_A_ini = df_Andes_sim["Qe_andes_gen_2"]
psid_gen1_A_ini = df_Andes_sim["psid_andes_gen_1"]
psid_gen2_A_ini = df_Andes_sim["psid_andes_gen_2"]
psiq_gen1_A_ini = df_Andes_sim["psiq_andes_gen_1"]
psiq_gen2_A_ini = df_Andes_sim["psiq_andes_gen_2"]
vf_gen1_A_ini = df_Andes_sim["vf_andes_gen_1"]
vf_gen2_A_ini = df_Andes_sim["vf_andes_gen_2"]
XadIfd_gen1_A_ini = df_Andes_sim["XadIfd_andes_gen_1"]
XadIfd_gen2_A_ini = df_Andes_sim["XadIfd_andes_gen_2"]
#load
Ppf_load_A_ini = df_Andes_sim["Ppf_andes_load_0"]
Qpf_load_A_ini = df_Andes_sim["Qpf_andes_load_0"]

#error [%]
#bus
v_Bus1_ini = (abs(v_bus1_A_ini)-abs(v_bus1_V_ini))*100/abs(v_bus1_A_ini)
v_Bus2_ini = (abs(v_bus2_A_ini)-abs(v_bus2_V_ini))*100/abs(v_bus2_A_ini)
v_Bus3_ini = (abs(v_bus3_A_ini)-abs(v_bus3_V_ini))*100/abs(v_bus3_A_ini)
v_Bus4_ini = (abs(v_bus4_A_ini)-abs(v_bus4_V_ini))*100/abs(v_bus4_A_ini)
a_Bus1_ini = (abs(a_bus1_A_ini)-abs(a_bus1_V_ini))*100/abs(a_bus1_A_ini)
a_Bus2_ini = (abs(a_bus2_A_ini)-abs(a_bus2_V_ini))*100/abs(a_bus2_A_ini)
a_Bus3_ini = (abs(a_bus3_A_ini)-abs(a_bus3_V_ini))*100/abs(a_bus3_A_ini)
a_Bus4_ini = (abs(a_bus4_A_ini)-abs(a_bus4_V_ini))*100/abs(a_bus4_A_ini)
#gen
delta_gen1_ini = (abs(delta_gen1_A_ini)-abs(delta_gen1_V_ini))*100/abs(delta_gen1_A_ini)
delta_gen2_ini = (abs(delta_gen2_A_ini)-abs(delta_gen2_V_ini))*100/abs(delta_gen2_A_ini)
omega_gen1_ini = (abs(omega_gen1_A_ini)-abs(omega_gen1_V_ini))*100/abs(omega_gen1_A_ini)
omega_gen2_ini = (abs(omega_gen2_A_ini)-abs(omega_gen2_V_ini))*100/abs(omega_gen2_A_ini)
Id_gen1_ini = (abs(Id_gen1_A_ini)-abs(Id_gen1_V_ini))*100/abs(Id_gen1_A_ini)
Id_gen2_ini = (abs(Id_gen2_A_ini)-abs(Id_gen2_V_ini))*100/abs(Id_gen2_A_ini)
Iq_gen1_ini = (abs(Iq_gen1_A_ini)-abs(Iq_gen1_V_ini))*100/abs(Iq_gen1_A_ini)
Iq_gen2_ini = (abs(Iq_gen2_A_ini)-abs(Iq_gen2_V_ini))*100/abs(Iq_gen2_A_ini)
vd_gen1_ini = (abs(vd_gen1_A_ini)-abs(vd_gen1_V_ini))*100/abs(vd_gen1_A_ini)
vd_gen2_ini = (abs(vd_gen2_A_ini)-abs(vd_gen2_V_ini))*100/abs(vd_gen2_A_ini)
vq_gen1_ini = (abs(vq_gen1_A_ini)-abs(vq_gen1_V_ini))*100/abs(vq_gen1_A_ini)
vq_gen2_ini = (abs(vq_gen2_A_ini)-abs(vq_gen2_V_ini))*100/abs(vq_gen2_A_ini)
tm_gen1_ini = (abs(tm_gen1_A_ini)-abs(tm_gen1_V_ini))*100/abs(tm_gen1_A_ini)
tm_gen2_ini = (abs(tm_gen2_A_ini)-abs(tm_gen2_V_ini))*100/abs(tm_gen2_A_ini)
te_gen1_ini = (abs(te_gen1_A_ini)-abs(te_gen1_V_ini))*100/abs(te_gen1_A_ini)
te_gen2_ini = (abs(te_gen2_A_ini)-abs(te_gen2_V_ini))*100/abs(te_gen2_A_ini)
Pg_gen1_ini = (abs(Pg_gen1_A_ini)-abs(Pg_gen1_V_ini))*100/abs(Pg_gen1_A_ini)
Pg_gen2_ini = (abs(Pg_gen2_A_ini)-abs(Pg_gen2_V_ini))*100/abs(Pg_gen2_A_ini)
Qg_gen1_ini = (abs(Qg_gen1_A_ini)-abs(Qg_gen1_V_ini))*100/abs(Qg_gen1_A_ini)
Qg_gen2_ini = (abs(Qg_gen2_A_ini)-abs(Qg_gen2_V_ini))*100/abs(Qg_gen2_A_ini)
psid_gen1_ini = (abs(psid_gen1_A_ini)-abs(psid_gen1_V_ini))*100/abs(psid_gen1_A_ini)
psid_gen2_ini = (abs(psid_gen2_A_ini)-abs(psid_gen2_V_ini))*100/abs(psid_gen2_A_ini)
psiq_gen1_ini = (abs(psiq_gen1_A_ini)-abs(psiq_gen1_V_ini))*100/abs(psiq_gen1_A_ini)
psiq_gen2_ini = (abs(psiq_gen2_A_ini)-abs(psiq_gen2_V_ini))*100/abs(psiq_gen2_A_ini)
#load
P_load_ini = (abs(Ppf_load_A_ini)-abs(Pl_load_V_ini))*100/abs(Ppf_load_A_ini)
Q_load_ini = (abs(Qpf_load_A_ini)-abs(Ql_load_V_ini))*100/abs(Qpf_load_A_ini)

df_errors_ini = pd.DataFrame({
    "Variable": ["v_Bus1", "v_Bus2", "v_Bus3", "v_Bus4","a_Bus1", "a_Bus2", "a_Bus3", "a_Bus4","delta_gen1",
                 "delta_gen2", "omega_gen1","omega_gen2", "Id_gen1", "Id_gen2", "Iq_gen1", "Iq_gen2", "vd_gen1",
                 "vd_gen2", "tm_gen1", "tm_gen2", "te_gen1", "te_gen2", "Pe_gen1", "Pe_gen2", "Qe_gen1","Qe_gen2",
                 "psid_gen1","psid_gen2","psiq_gen1","psiq_gen2", "P_load_ini", "Q_load_ini"],
    "Abs_error": [v_Bus1_ini, v_Bus2_ini, v_Bus3_ini, v_Bus4_ini, a_Bus1_ini, a_Bus2_ini, a_Bus3_ini, a_Bus4_ini,
                  delta_gen1_ini, delta_gen2_ini, omega_gen1_ini, omega_gen2_ini, Id_gen1_ini, Id_gen2_ini,Iq_gen1_ini, Iq_gen2_ini, vd_gen1_ini,vd_gen2_ini,
                  tm_gen1_ini, tm_gen2_ini, te_gen1_ini, te_gen2_ini, Pg_gen1_ini, Pg_gen2_ini, Qg_gen1_ini, Qg_gen2_ini,
                  psid_gen1_ini, psid_gen2_ini, psiq_gen1_ini,psiq_gen2_ini,P_load_ini, Q_load_ini]
})
df_errors_ini.to_csv("error_initialization.csv", index=False)
print(df_errors_ini)








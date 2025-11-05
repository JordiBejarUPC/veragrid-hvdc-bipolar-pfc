\* myProblem *\
Minimize
OBJ: DeltaSL_down_0 + DeltaSL_up_0 + Delta_down_0 - Delta_up_0 + ac_flow_0_16
 + ac_flow_0_17 - ac_flow_0_21 - hvdc_flow_0_0
Subject To
ac_flow_ps_fix0_16: - 1.79797907152 Va_0_3 + 1.79797907152 Va_0_8
 + ac_flow_0_16 = 0.106620158941
ac_flow_ps_fix0_21: 4.78194338179 Va_0_15 - 4.78194338179 Va_0_6
 + ac_flow_0_21 = -0.23909716909
ac_flows_0_0: - 23.7473284256 Va_0_3 + 23.7473284256 Va_0_4 + ac_flow_0_0 = 0
ac_flows_0_1: 5.02765208648 Va_0_10 - 5.02765208648 Va_0_5 + ac_flow_0_1 = 0
ac_flows_0_10: - 16.9004563123 Va_0_0 + 16.9004563123 Va_0_1 + ac_flow_0_10
 = 0
ac_flows_0_11: - 4.48350071736 Va_0_0 + 4.48350071736 Va_0_4 + ac_flow_0_11
 = 0
ac_flows_0_12: - 5.0512703945 Va_0_1 + 5.0512703945 Va_0_2 + ac_flow_0_12 = 0
ac_flows_0_13: - 5.67150635209 Va_0_1 + 5.67150635209 Va_0_3 + ac_flow_0_13
 = 0
ac_flows_0_14: - 5.75109270761 Va_0_1 + 5.75109270761 Va_0_4 + ac_flow_0_14
 = 0
ac_flows_0_15: - 5.84692743963 Va_0_2 + 5.84692743963 Va_0_3 + ac_flow_0_15
 = 0
ac_flows_0_17: - 3.96793905246 Va_0_4 + 3.96793905246 Va_0_5 + ac_flow_0_17
 = 0
ac_flows_0_18: - 5.67697984672 Va_0_6 + 5.67697984672 Va_0_7 + ac_flow_0_18
 = 0
ac_flows_0_19: - 9.09008271975 Va_0_6 + 9.09008271975 Va_0_8 + ac_flow_0_19
 = 0
ac_flows_0_2: 3.90915132325 Va_0_11 - 3.90915132325 Va_0_5 + ac_flow_0_2 = 0
ac_flows_0_20: - 200 Va_0_14 + 200 Va_0_4 + ac_flow_0_20 = 0
ac_flows_0_3: 7.67636447379 Va_0_12 - 7.67636447379 Va_0_5 + ac_flow_0_3 = 0
ac_flows_0_4: - 11.8343195266 Va_0_8 + 11.8343195266 Va_0_9 + ac_flow_0_4 = 0
ac_flows_0_5: 3.69849840965 Va_0_13 - 3.69849840965 Va_0_8 + ac_flow_0_5 = 0
ac_flows_0_6: 5.20643515385 Va_0_10 - 5.20643515385 Va_0_9 + ac_flow_0_6 = 0
ac_flows_0_7: - 5.00300180108 Va_0_11 + 5.00300180108 Va_0_12 + ac_flow_0_7
 = 0
ac_flows_0_8: - 2.87339808057 Va_0_12 + 2.87339808057 Va_0_13 + ac_flow_0_8
 = 0
ac_flows_0_9: - 1000 Va_0_15 + 1000 Va_0_3 + ac_flow_0_9 = 0
deltas_equality_0: DeltaSL_down_0 - DeltaSL_up_0 - Delta_down_0 + Delta_up_0
 = 0
kirchhoff_0_0: - 0.333333 Delta_down_0 - ac_flow_0_10 - ac_flow_0_11
 = -0.592887637492
kirchhoff_0_1: - 0.333333 Delta_down_0 + ac_flow_0_10 - ac_flow_0_12
 - ac_flow_0_13 - ac_flow_0_14 = -0.375887637492
kirchhoff_0_10: ac_flow_0_1 + ac_flow_0_6 - hvdc_flow_0_0 = 0.035
kirchhoff_0_11: ac_flow_0_2 - ac_flow_0_7 = 0.061
kirchhoff_0_12: ac_flow_0_3 + ac_flow_0_7 - ac_flow_0_8 = 0.135
kirchhoff_0_13: ac_flow_0_5 + ac_flow_0_8 = 0.149
kirchhoff_0_14: - ac_flow_0_20 + hvdc_flow_0_0 = 0
kirchhoff_0_15: ac_flow_0_21 - ac_flow_0_9 = 0
kirchhoff_0_2: - 0.333333 Delta_down_0 + ac_flow_0_12 - ac_flow_0_15
 = 0.349112362508
kirchhoff_0_3: - ac_flow_0_0 + ac_flow_0_13 + ac_flow_0_15 - ac_flow_0_16
 + ac_flow_0_9 = 0.478
kirchhoff_0_4: ac_flow_0_0 + ac_flow_0_11 + ac_flow_0_14 - ac_flow_0_17
 + ac_flow_0_20 = 0.076
kirchhoff_0_5: 0.5 Delta_up_0 - ac_flow_0_1 + ac_flow_0_17 - ac_flow_0_2
 - ac_flow_0_3 = -0.480887637492
kirchhoff_0_6: - ac_flow_0_18 - ac_flow_0_19 - ac_flow_0_21 = 0
kirchhoff_0_7: 0.5 Delta_up_0 + ac_flow_0_18 = -0.218449450034
kirchhoff_0_8: ac_flow_0_16 + ac_flow_0_19 - ac_flow_0_4 - ac_flow_0_5 = 0.295
kirchhoff_0_9: ac_flow_0_4 - ac_flow_0_6 = 0.09
Bounds
 DeltaSL_down_0 <= 1e+20
 DeltaSL_up_0 <= 1e+20
 Delta_down_0 <= 1e+20
 Delta_up_0 <= 1e+20
 Va_0_0 = 0
 -6.28 <= Va_0_1 <= 6.28
 -6.28 <= Va_0_10 <= 6.28
 -6.28 <= Va_0_11 <= 6.28
 -6.28 <= Va_0_12 <= 6.28
 -6.28 <= Va_0_13 <= 6.28
 -6.28 <= Va_0_14 <= 6.28
 -6.28 <= Va_0_15 <= 6.28
 -6.28 <= Va_0_2 <= 6.28
 -6.28 <= Va_0_3 <= 6.28
 -6.28 <= Va_0_4 <= 6.28
 -6.28 <= Va_0_5 <= 6.28
 -6.28 <= Va_0_6 <= 6.28
 -6.28 <= Va_0_7 <= 6.28
 -6.28 <= Va_0_8 <= 6.28
 -6.28 <= Va_0_9 <= 6.28
 -1e+20 <= ac_flow_0_0 <= 1e+20
 -1e+20 <= ac_flow_0_1 <= 1e+20
 -2 <= ac_flow_0_10 <= 2
 -1 <= ac_flow_0_11 <= 1
 -1e+20 <= ac_flow_0_12 <= 1e+20
 -1 <= ac_flow_0_13 <= 1
 -0.8 <= ac_flow_0_14 <= 0.8
 -0.5 <= ac_flow_0_15 <= 0.5
 -0.5 <= ac_flow_0_16 <= 0.5
 -0.8 <= ac_flow_0_17 <= 0.8
 -0.5 <= ac_flow_0_18 <= 0.5
 -0.5 <= ac_flow_0_19 <= 0.5
 -1e+20 <= ac_flow_0_2 <= 1e+20
 -1e+20 <= ac_flow_0_20 <= 1e+20
 -0.2 <= ac_flow_0_21 <= 0.2
 -1e+20 <= ac_flow_0_3 <= 1e+20
 -1e+20 <= ac_flow_0_4 <= 1e+20
 -1e+20 <= ac_flow_0_5 <= 1e+20
 -1e+20 <= ac_flow_0_6 <= 1e+20
 -1e+20 <= ac_flow_0_7 <= 1e+20
 -1e+20 <= ac_flow_0_8 <= 1e+20
 -1e+20 <= ac_flow_0_9 <= 1e+20
 -10 <= hvdc_flow_0_0 <= 10
End

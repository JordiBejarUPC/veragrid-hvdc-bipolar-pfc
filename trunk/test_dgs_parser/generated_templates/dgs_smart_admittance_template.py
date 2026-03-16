# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\DGS_test_type_models.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_smart_admittance_emt_template(vf: VarFactory, name: str = 'Smart_Admittance') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Smart_Admittance_ACLINE_Ltrafo = vf.add_var('Smart_Admittance__ACLINE_Ltrafo_' + name)
    Smart_Admittance_CAPABILITY_Ilim_neg = vf.add_var('Smart_Admittance__CAPABILITY_Ilim_neg_' + name)
    Smart_Admittance_CAPABILITY_Imax_conv = vf.add_var('Smart_Admittance__CAPABILITY_Imax_conv_' + name)
    Smart_Admittance_CAPABILITY_Iposneg_prio = vf.add_var('Smart_Admittance__CAPABILITY_Iposneg_prio_' + name)
    Smart_Admittance_CAPABILITY_PQ_prio = vf.add_var('Smart_Admittance__CAPABILITY_PQ_prio_' + name)
    Smart_Admittance_CAPABILITY_PlantEff = vf.add_var('Smart_Admittance__CAPABILITY_PlantEff_' + name)
    Smart_Admittance_CAPABILITY_PlimD_crit = vf.add_var('Smart_Admittance__CAPABILITY_PlimD_crit_' + name)
    Smart_Admittance_CAPABILITY_PmvLim_charge = vf.add_var('Smart_Admittance__CAPABILITY_PmvLim_charge_' + name)
    Smart_Admittance_CAPABILITY_PmvLim_discharge = vf.add_var('Smart_Admittance__CAPABILITY_PmvLim_discharge_' + name)
    Smart_Admittance_CAPABILITY_Qlim_cap = vf.add_var('Smart_Admittance__CAPABILITY_Qlim_cap_' + name)
    Smart_Admittance_CAPABILITY_Qlim_ind = vf.add_var('Smart_Admittance__CAPABILITY_Qlim_ind_' + name)
    Smart_Admittance_CAPABILITY_TrafoEff = vf.add_var('Smart_Admittance__CAPABILITY_TrafoEff_' + name)
    Smart_Admittance_CAPABILITY_Vmax_TransfoFlux = vf.add_var('Smart_Admittance__CAPABILITY_Vmax_TransfoFlux_' + name)
    Smart_Admittance_CAPABILITY_Vmax_auxiliary = vf.add_var('Smart_Admittance__CAPABILITY_Vmax_auxiliary_' + name)
    Smart_Admittance_CAPABILITY_Vmax_conv = vf.add_var('Smart_Admittance__CAPABILITY_Vmax_conv_' + name)
    Smart_Admittance_CAPABILITY_Vmin_auxiliary = vf.add_var('Smart_Admittance__CAPABILITY_Vmin_auxiliary_' + name)
    Smart_Admittance_CAPABILITY_inv_V_limH = vf.add_var('Smart_Admittance__CAPABILITY_inv_V_limH_' + name)
    Smart_Admittance_CAPABILITY_inv_V_limL = vf.add_var('Smart_Admittance__CAPABILITY_inv_V_limL_' + name)
    Smart_Admittance_GFOR_VirtualX_pu_std = vf.add_var('Smart_Admittance__GFOR_VirtualX_pu_std_' + name)
    Smart_Admittance_GFOR_tau_VA = vf.add_var('Smart_Admittance__GFOR_tau_VA_' + name)
    Smart_Admittance_GFOR_vPosD_fault_Tramp = vf.add_var('Smart_Admittance__GFOR_vPosD_fault_Tramp_' + name)
    Smart_Admittance_Pmax_dyn = vf.add_var('Smart_Admittance__Pmax_dyn_' + name)
    Smart_Admittance_PmvLim_crit = vf.add_var('Smart_Admittance__PmvLim_crit_' + name)
    Smart_Admittance_VdcRef = vf.add_var('Smart_Admittance__VdcRef_' + name)
    Smart_Admittance_f1 = vf.add_var('Smart_Admittance__f1_' + name)
    Smart_Admittance_inv_Xtrafo_pu = vf.add_var('Smart_Admittance__inv_Xtrafo_pu_' + name)
    Smart_Admittance_va_mode = vf.add_var('Smart_Admittance__va_mode_' + name)

    # --- State Variables ---
    Smart_Admittance_x1d_va = vf.add_var('Smart_Admittance__x1d_va_' + name)
    Smart_Admittance_x1q_va = vf.add_var('Smart_Admittance__x1q_va_' + name)
    Smart_Admittance_x2d_va = vf.add_var('Smart_Admittance__x2d_va_' + name)
    Smart_Admittance_x2q_va = vf.add_var('Smart_Admittance__x2q_va_' + name)

    # --- Algebraic / Shared Variables ---
    FRT1_flag = vf.add_var('FRT1_flag_' + name)
    FRT1_flag_1 = vf.add_var('FRT1_flag_' + name)
    I_mag = vf.add_var('I_mag_' + name)
    I_mag_1 = vf.add_var('I_mag_' + name)
    I_mag_sq = vf.add_var('I_mag_sq_' + name)
    I_mag_sq_1 = vf.add_var('I_mag_sq_' + name)
    I_neg_avail = vf.add_var('I_neg_avail_' + name)
    I_neg_avail_1 = vf.add_var('I_neg_avail_' + name)
    I_pos_used = vf.add_var('I_pos_used_' + name)
    I_pos_used_1 = vf.add_var('I_pos_used_' + name)
    ImaxCapacitive = vf.add_var('ImaxCapacitive_' + name)
    ImaxCapacitive_1 = vf.add_var('ImaxCapacitive_' + name)
    ImaxInductive = vf.add_var('ImaxInductive_' + name)
    ImaxInductive_1 = vf.add_var('ImaxInductive_' + name)
    Overload_Flag = vf.add_var('Overload_Flag_' + name)
    PPCChigh = vf.add_var('PPCChigh_' + name)
    PPCChigh_1 = vf.add_var('PPCChigh_' + name)
    PPCClow = vf.add_var('PPCClow_' + name)
    PPCClow_1 = vf.add_var('PPCClow_' + name)
    P_capab_high = vf.add_var('P_capab_high_' + name)
    P_capab_low = vf.add_var('P_capab_low_' + name)
    P_chg_normal = vf.add_var('P_chg_normal_' + name)
    P_chg_normal_1 = vf.add_var('P_chg_normal_' + name)
    P_dis_normal = vf.add_var('P_dis_normal_' + name)
    P_dis_normal_1 = vf.add_var('P_dis_normal_' + name)
    Pvsc = vf.add_var('Pvsc_' + name)
    Pvsc_1 = vf.add_var('Pvsc_' + name)
    Q_capab_high = vf.add_var('Q_capab_high_' + name)
    Q_capab_low = vf.add_var('Q_capab_low_' + name)
    Qvsc = vf.add_var('Qvsc_' + name)
    Qvsc_1 = vf.add_var('Qvsc_' + name)
    Smart_Admittance_ACLINE_Ltrafo_1 = vf.add_var('Smart_Admittance__ACLINE_Ltrafo_' + name)
    Smart_Admittance_CAPABILITY_Imax_conv_1 = vf.add_var('Smart_Admittance__CAPABILITY_Imax_conv_' + name)
    Smart_Admittance_CAPABILITY_PQ_prio_1 = vf.add_var('Smart_Admittance__CAPABILITY_PQ_prio_' + name)
    Smart_Admittance_CAPABILITY_PlantEff_1 = vf.add_var('Smart_Admittance__CAPABILITY_PlantEff_' + name)
    Smart_Admittance_CAPABILITY_PmvLim_charge_1 = vf.add_var('Smart_Admittance__CAPABILITY_PmvLim_charge_' + name)
    Smart_Admittance_CAPABILITY_PmvLim_discharge_1 = vf.add_var('Smart_Admittance__CAPABILITY_PmvLim_discharge_' + name)
    Smart_Admittance_CAPABILITY_TrafoEff_1 = vf.add_var('Smart_Admittance__CAPABILITY_TrafoEff_' + name)
    Smart_Admittance_CAPABILITY_Vmax_TransfoFlux_1 = vf.add_var('Smart_Admittance__CAPABILITY_Vmax_TransfoFlux_' + name)
    Smart_Admittance_CAPABILITY_Vmax_auxiliary_1 = vf.add_var('Smart_Admittance__CAPABILITY_Vmax_auxiliary_' + name)
    Smart_Admittance_CAPABILITY_Vmin_auxiliary_1 = vf.add_var('Smart_Admittance__CAPABILITY_Vmin_auxiliary_' + name)
    Smart_Admittance_FlagLimit = vf.add_var('Smart_Admittance__FlagLimit_' + name)
    Smart_Admittance_GFOR_VirtualX_pu_std_1 = vf.add_var('Smart_Admittance__GFOR_VirtualX_pu_std_' + name)
    Smart_Admittance_GFOR_tau_VA_1 = vf.add_var('Smart_Admittance__GFOR_tau_VA_' + name)
    Smart_Admittance_MaxAuxiliaryVoltage = vf.add_var('Smart_Admittance__MaxAuxiliaryVoltage_' + name)
    Smart_Admittance_MaxAuxiliaryVoltage_1 = vf.add_var('Smart_Admittance__MaxAuxiliaryVoltage_' + name)
    Smart_Admittance_MaxTransfoFluxVoltage = vf.add_var('Smart_Admittance__MaxTransfoFluxVoltage_' + name)
    Smart_Admittance_MaxTransfoFluxVoltage_1 = vf.add_var('Smart_Admittance__MaxTransfoFluxVoltage_' + name)
    Smart_Admittance_MinAuxiliaryVoltage = vf.add_var('Smart_Admittance__MinAuxiliaryVoltage_' + name)
    Smart_Admittance_MinAuxiliaryVoltage_1 = vf.add_var('Smart_Admittance__MinAuxiliaryVoltage_' + name)
    Smart_Admittance_PlantEff = vf.add_var('Smart_Admittance__PlantEff_' + name)
    Smart_Admittance_PlantEff_1 = vf.add_var('Smart_Admittance__PlantEff_' + name)
    Smart_Admittance_Pmax_dyn_1 = vf.add_var('Smart_Admittance__Pmax_dyn_' + name)
    Smart_Admittance_PmvLim_charge = vf.add_var('Smart_Admittance__PmvLim_charge_' + name)
    Smart_Admittance_PmvLim_charge_1 = vf.add_var('Smart_Admittance__PmvLim_charge_' + name)
    Smart_Admittance_PmvLim_crit_1 = vf.add_var('Smart_Admittance__PmvLim_crit_' + name)
    Smart_Admittance_PmvLim_discharge = vf.add_var('Smart_Admittance__PmvLim_discharge_' + name)
    Smart_Admittance_PmvLim_discharge_1 = vf.add_var('Smart_Admittance__PmvLim_discharge_' + name)
    Smart_Admittance_Q_priority_flag = vf.add_var('Smart_Admittance__Q_priority_flag_' + name)
    Smart_Admittance_Q_priority_flag_1 = vf.add_var('Smart_Admittance__Q_priority_flag_' + name)
    Smart_Admittance_T_va_ramp = vf.add_var('Smart_Admittance__T_va_ramp_' + name)
    Smart_Admittance_T_va_ramp_1 = vf.add_var('Smart_Admittance__T_va_ramp_' + name)
    Smart_Admittance_VdcRef_1 = vf.add_var('Smart_Admittance__VdcRef_' + name)
    Smart_Admittance_alpha_va = vf.add_var('Smart_Admittance__alpha_va_' + name)
    Smart_Admittance_alpha_va_1 = vf.add_var('Smart_Admittance__alpha_va_' + name)
    Smart_Admittance_f1_1 = vf.add_var('Smart_Admittance__f1_' + name)
    Smart_Admittance_inv_PlantEff = vf.add_var('Smart_Admittance__inv_PlantEff_' + name)
    Smart_Admittance_inv_PlantEff_1 = vf.add_var('Smart_Admittance__inv_PlantEff_' + name)
    Smart_Admittance_inv_Xtrafo_Lout_pu = vf.add_var('Smart_Admittance__inv_Xtrafo_Lout_pu_' + name)
    Smart_Admittance_inv_Xtrafo_Lout_pu_1 = vf.add_var('Smart_Admittance__inv_Xtrafo_Lout_pu_' + name)
    Smart_Admittance_inv_Xtrafo_pu_1 = vf.add_var('Smart_Admittance__inv_Xtrafo_pu_' + name)
    Smart_Admittance_inv_k_eff_trafo = vf.add_var('Smart_Admittance__inv_k_eff_trafo_' + name)
    Smart_Admittance_inv_k_eff_trafo_1 = vf.add_var('Smart_Admittance__inv_k_eff_trafo_' + name)
    Smart_Admittance_k_eff_trafo = vf.add_var('Smart_Admittance__k_eff_trafo_' + name)
    Smart_Admittance_k_eff_trafo_1 = vf.add_var('Smart_Admittance__k_eff_trafo_' + name)
    Smart_Admittance_rv = vf.add_var('Smart_Admittance__rv_' + name)
    Smart_Admittance_rv_1 = vf.add_var('Smart_Admittance__rv_' + name)
    Smart_Admittance_val_Id_target = vf.add_var('Smart_Admittance__val_Id_target_' + name)
    Smart_Admittance_val_Id_target_1 = vf.add_var('Smart_Admittance__val_Id_target_' + name)
    Smart_Admittance_val_Imag_calc = vf.add_var('Smart_Admittance__val_Imag_calc_' + name)
    Smart_Admittance_val_Imag_calc_1 = vf.add_var('Smart_Admittance__val_Imag_calc_' + name)
    Smart_Admittance_val_Iq_target = vf.add_var('Smart_Admittance__val_Iq_target_' + name)
    Smart_Admittance_val_Iq_target_1 = vf.add_var('Smart_Admittance__val_Iq_target_' + name)
    Smart_Admittance_val_V_safe = vf.add_var('Smart_Admittance__val_V_safe_' + name)
    Smart_Admittance_val_V_safe_1 = vf.add_var('Smart_Admittance__val_V_safe_' + name)
    Smart_Admittance_val_e1d_req = vf.add_var('Smart_Admittance__val_e1d_req_' + name)
    Smart_Admittance_val_e1d_req_1 = vf.add_var('Smart_Admittance__val_e1d_req_' + name)
    Smart_Admittance_val_e1q_req = vf.add_var('Smart_Admittance__val_e1q_req_' + name)
    Smart_Admittance_val_e1q_req_1 = vf.add_var('Smart_Admittance__val_e1q_req_' + name)
    Smart_Admittance_x1d_va_1 = vf.add_var('Smart_Admittance__x1d_va_' + name)
    Smart_Admittance_x1q_va_1 = vf.add_var('Smart_Admittance__x1q_va_' + name)
    Smart_Admittance_x2d_va_1 = vf.add_var('Smart_Admittance__x2d_va_' + name)
    Smart_Admittance_x2q_va_1 = vf.add_var('Smart_Admittance__x2q_va_' + name)
    Smart_Admittance_xv = vf.add_var('Smart_Admittance__xv_' + name)
    Smart_Admittance_xv_1 = vf.add_var('Smart_Admittance__xv_' + name)
    V1vsc = vf.add_var('V1vsc_' + name)
    V1vsc_1 = vf.add_var('V1vsc_' + name)
    V_max_safe = vf.add_var('V_max_safe_' + name)
    V_max_safe_1 = vf.add_var('V_max_safe_' + name)
    denom = vf.add_var('denom_' + name)
    denom_1 = vf.add_var('denom_' + name)
    e1d = vf.add_var('e1d_' + name)
    e1d_1 = vf.add_var('e1d_' + name)
    e1q = vf.add_var('e1q_' + name)
    e1q_1 = vf.add_var('e1q_' + name)
    e2d = vf.add_var('e2d_' + name)
    e2d_1 = vf.add_var('e2d_' + name)
    e2q = vf.add_var('e2q_' + name)
    e2q_1 = vf.add_var('e2q_' + name)
    e_int_d = vf.add_var('e_int_d_' + name)
    i1d_hat = vf.add_var('i1d_hat_' + name)
    i1d_hat_dyn = vf.add_var('i1d_hat_dyn_' + name)
    i1d_hat_dyn_1 = vf.add_var('i1d_hat_dyn_' + name)
    i1d_hat_nodyn = vf.add_var('i1d_hat_nodyn_' + name)
    i1d_hat_nodyn_1 = vf.add_var('i1d_hat_nodyn_' + name)
    i1q_hat = vf.add_var('i1q_hat_' + name)
    i1q_hat_dyn = vf.add_var('i1q_hat_dyn_' + name)
    i1q_hat_dyn_1 = vf.add_var('i1q_hat_dyn_' + name)
    i1q_hat_nodyn = vf.add_var('i1q_hat_nodyn_' + name)
    i1q_hat_nodyn_1 = vf.add_var('i1q_hat_nodyn_' + name)
    i2_mag = vf.add_var('i2_mag_' + name)
    i2_mag_1 = vf.add_var('i2_mag_' + name)
    i2d_hat = vf.add_var('i2d_hat_' + name)
    i2d_hat_dyn = vf.add_var('i2d_hat_dyn_' + name)
    i2d_hat_dyn_1 = vf.add_var('i2d_hat_dyn_' + name)
    i2d_hat_nodyn = vf.add_var('i2d_hat_nodyn_' + name)
    i2d_hat_nodyn_1 = vf.add_var('i2d_hat_nodyn_' + name)
    i2q_hat = vf.add_var('i2q_hat_' + name)
    i2q_hat_dyn = vf.add_var('i2q_hat_dyn_' + name)
    i2q_hat_dyn_1 = vf.add_var('i2q_hat_dyn_' + name)
    i2q_hat_nodyn = vf.add_var('i2q_hat_nodyn_' + name)
    i2q_hat_nodyn_1 = vf.add_var('i2q_hat_nodyn_' + name)
    i_cap_raw = vf.add_var('i_cap_raw_' + name)
    i_cap_raw_1 = vf.add_var('i_cap_raw_' + name)
    i_ind_raw = vf.add_var('i_ind_raw_' + name)
    i_ind_raw_1 = vf.add_var('i_ind_raw_' + name)
    id2_raw = vf.add_var('id2_raw_' + name)
    id2_raw_1 = vf.add_var('id2_raw_' + name)
    idMVhigh = vf.add_var('idMVhigh_' + name)
    idMVhigh_1 = vf.add_var('idMVhigh_' + name)
    idMVlow = vf.add_var('idMVlow_' + name)
    idMVlow_1 = vf.add_var('idMVlow_' + name)
    id_avail = vf.add_var('id_avail_' + name)
    id_avail_1 = vf.add_var('id_avail_' + name)
    id_bal = vf.add_var('id_bal_' + name)
    id_bal_1 = vf.add_var('id_bal_' + name)
    id_lim_rect = vf.add_var('id_lim_rect_' + name)
    id_lim_rect_1 = vf.add_var('id_lim_rect_' + name)
    id_neg_sat = vf.add_var('id_neg_sat_' + name)
    id_neg_sat_1 = vf.add_var('id_neg_sat_' + name)
    id_pos_sat = vf.add_var('id_pos_sat_' + name)
    id_pos_sat_1 = vf.add_var('id_pos_sat_' + name)
    id_prio = vf.add_var('id_prio_' + name)
    id_prio_1 = vf.add_var('id_prio_' + name)
    id_raw = vf.add_var('id_raw_' + name)
    id_raw_1 = vf.add_var('id_raw_' + name)
    inv_V1vsc = vf.add_var('inv_V1vsc_' + name)
    inv_V1vsc_1 = vf.add_var('inv_V1vsc_' + name)
    iq2_raw = vf.add_var('iq2_raw_' + name)
    iq2_raw_1 = vf.add_var('iq2_raw_' + name)
    iq_bal = vf.add_var('iq_bal_' + name)
    iq_bal_1 = vf.add_var('iq_bal_' + name)
    iq_lim_rect = vf.add_var('iq_lim_rect_' + name)
    iq_lim_rect_1 = vf.add_var('iq_lim_rect_' + name)
    iq_neg_sat = vf.add_var('iq_neg_sat_' + name)
    iq_neg_sat_1 = vf.add_var('iq_neg_sat_' + name)
    iq_pos_sat = vf.add_var('iq_pos_sat_' + name)
    iq_pos_sat_1 = vf.add_var('iq_pos_sat_' + name)
    iq_prio = vf.add_var('iq_prio_' + name)
    iq_prio_1 = vf.add_var('iq_prio_' + name)
    iq_raw = vf.add_var('iq_raw_' + name)
    iq_raw_1 = vf.add_var('iq_raw_' + name)
    lim1 = vf.add_var('lim1_' + name)
    lim1_1 = vf.add_var('lim1_' + name)
    lim2 = vf.add_var('lim2_' + name)
    lim2_1 = vf.add_var('lim2_' + name)
    rv_init = vf.add_var('rv_init_' + name)
    safe_V1vsc = vf.add_var('safe_V1vsc_' + name)
    safe_V1vsc_1 = vf.add_var('safe_V1vsc_' + name)
    scale_bal = vf.add_var('scale_bal_' + name)
    scale_bal_1 = vf.add_var('scale_bal_' + name)
    scale_final = vf.add_var('scale_final_' + name)
    scale_final_1 = vf.add_var('scale_final_' + name)
    scale_neg = vf.add_var('scale_neg_' + name)
    scale_neg_1 = vf.add_var('scale_neg_' + name)
    time = vf.add_var('time_' + name)
    u1d = vf.add_var('u1d_' + name)
    u1d_1 = vf.add_var('u1d_' + name)
    u1q = vf.add_var('u1q_' + name)
    u1q_1 = vf.add_var('u1q_' + name)
    u2d = vf.add_var('u2d_' + name)
    u2d_1 = vf.add_var('u2d_' + name)
    u2d_dif = vf.add_var('u2d_dif_' + name)
    u2d_dif_1 = vf.add_var('u2d_dif_' + name)
    u2q = vf.add_var('u2q_' + name)
    u2q_1 = vf.add_var('u2q_' + name)
    u2q_dif = vf.add_var('u2q_dif_' + name)
    u2q_dif_1 = vf.add_var('u2q_dif_' + name)
    ud_dif = vf.add_var('ud_dif_' + name)
    ud_dif_1 = vf.add_var('ud_dif_' + name)
    uq_dif = vf.add_var('uq_dif_' + name)
    uq_dif_1 = vf.add_var('uq_dif_' + name)
    use_prio_Q = vf.add_var('use_prio_Q_' + name)
    use_prio_Q_1 = vf.add_var('use_prio_Q_' + name)
    viol_P = vf.add_var('viol_P_' + name)
    viol_P_1 = vf.add_var('viol_P_' + name)
    viol_Q = vf.add_var('viol_Q_' + name)
    viol_Q_1 = vf.add_var('viol_Q_' + name)
    w1 = vf.add_var('w1_' + name)
    w1_1 = vf.add_var('w1_' + name)
    xv_init = vf.add_var('xv_init_' + name)

    # --- Derivative Variables ---
    d_Smart_Admittance_x1d_va = vf.add_diff_var('d_Smart_Admittance__x1d_va_' + name, base_var=Smart_Admittance_x1d_va)
    d_Smart_Admittance_x1q_va = vf.add_diff_var('d_Smart_Admittance__x1q_va_' + name, base_var=Smart_Admittance_x1q_va)
    d_Smart_Admittance_x2d_va = vf.add_diff_var('d_Smart_Admittance__x2d_va_' + name, base_var=Smart_Admittance_x2d_va)
    d_Smart_Admittance_x2q_va = vf.add_diff_var('d_Smart_Admittance__x2q_va_' + name, base_var=Smart_Admittance_x2q_va)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (((((e1d_1 - u1d_1) - (Smart_Admittance_rv_1 * Smart_Admittance_x1d_va_1)) + (Smart_Admittance_xv_1 * Smart_Admittance_x1q_va_1)) * w1_1) / Smart_Admittance_xv_1),
            (((((e1q_1 - u1q_1) - (Smart_Admittance_xv_1 * Smart_Admittance_x1d_va_1)) - (Smart_Admittance_rv_1 * Smart_Admittance_x1q_va_1)) * w1_1) / Smart_Admittance_xv_1),
            (((((e2d_1 - u2d_1) - (Smart_Admittance_rv_1 * Smart_Admittance_x2d_va_1)) - (Smart_Admittance_xv_1 * Smart_Admittance_x2q_va_1)) * w1_1) / Smart_Admittance_xv_1),
            (((((e2q_1 - u2q_1) + (Smart_Admittance_xv_1 * Smart_Admittance_x2d_va_1)) - (Smart_Admittance_rv_1 * Smart_Admittance_x2q_va_1)) * w1_1) / Smart_Admittance_xv_1),
        ],
        state_vars=[Smart_Admittance_x1d_va, Smart_Admittance_x1q_va, Smart_Admittance_x2d_va, Smart_Admittance_x2q_va],
        algebraic_eqs=[
            (w1 - ((sym.Const(2.0) * sym.Const(3.141592653589793)) * Smart_Admittance_f1_1)),
            (Smart_Admittance_rv - ((Smart_Admittance_GFOR_VirtualX_pu_std_1 / Smart_Admittance_GFOR_tau_VA_1) / w1_1)),
            (Smart_Admittance_xv - Smart_Admittance_GFOR_VirtualX_pu_std_1),
            (rv_init - Smart_Admittance_rv_1),
            (xv_init - Smart_Admittance_xv_1),
            (Smart_Admittance_PmvLim_discharge - Smart_Admittance_CAPABILITY_PmvLim_discharge_1),
            (Smart_Admittance_PmvLim_charge - Smart_Admittance_CAPABILITY_PmvLim_charge_1),
            (Smart_Admittance_inv_PlantEff - (sym.Const(1.0) / Smart_Admittance_CAPABILITY_PlantEff_1)),
            (Smart_Admittance_PlantEff - Smart_Admittance_CAPABILITY_PlantEff_1),
            (Smart_Admittance_Q_priority_flag - Smart_Admittance_CAPABILITY_PQ_prio_1),
            (Smart_Admittance_MaxTransfoFluxVoltage - Smart_Admittance_CAPABILITY_Vmax_TransfoFlux_1),
            (Smart_Admittance_MaxAuxiliaryVoltage - Smart_Admittance_CAPABILITY_Vmax_auxiliary_1),
            (Smart_Admittance_MinAuxiliaryVoltage - Smart_Admittance_CAPABILITY_Vmin_auxiliary_1),
            (Smart_Admittance_k_eff_trafo - Smart_Admittance_CAPABILITY_TrafoEff_1),
            (Smart_Admittance_inv_k_eff_trafo - (sym.Const(1.0) / Smart_Admittance_CAPABILITY_TrafoEff_1)),
            (Smart_Admittance_inv_Xtrafo_Lout_pu - Smart_Admittance_ACLINE_Ltrafo_1),
            (i1d_hat_dyn - Smart_Admittance_x1d_va_1),
            (i1q_hat_dyn - Smart_Admittance_x1q_va_1),
            (ud_dif - (e1d_1 - u1d_1)),
            (uq_dif - (e1q_1 - u1q_1)),
            (denom - ((Smart_Admittance_rv_1 * Smart_Admittance_rv_1) + (Smart_Admittance_xv_1 * Smart_Admittance_xv_1))),
            (i1d_hat_nodyn - (((Smart_Admittance_rv_1 * ud_dif_1) + (uq_dif_1 * Smart_Admittance_xv_1)) / denom_1)),
            (i1q_hat_nodyn - (((Smart_Admittance_rv_1 * uq_dif_1) - (ud_dif_1 * Smart_Admittance_xv_1)) / denom_1)),
            (Smart_Admittance_T_va_ramp - sym.Const(0.3)),
            (Smart_Admittance_alpha_va - ((sym.heaviside((Smart_Admittance_T_va_ramp_1 - sym.Const(1e-06))) * ((sym.Const(1.0) * sym.heaviside(((time / Smart_Admittance_T_va_ramp_1) - sym.Const(1.0)))) + ((time / Smart_Admittance_T_va_ramp_1) * (sym.Const(1) - sym.heaviside(((time / Smart_Admittance_T_va_ramp_1) - sym.Const(1.0))))))) + ((sym.Const(1.0) - sym.heaviside((Smart_Admittance_T_va_ramp_1 - sym.Const(1e-06)))) * sym.Const(1.0)))),
            (id_raw - (((sym.Const(1.0) - Smart_Admittance_alpha_va_1) * i1d_hat_nodyn_1) + (Smart_Admittance_alpha_va_1 * i1d_hat_dyn_1))),
            (iq_raw - (((sym.Const(1.0) - Smart_Admittance_alpha_va_1) * i1q_hat_nodyn_1) + (Smart_Admittance_alpha_va_1 * i1q_hat_dyn_1))),
            (i2d_hat_dyn - Smart_Admittance_x2d_va_1),
            (i2q_hat_dyn - Smart_Admittance_x2q_va_1),
            (u2d_dif - (e2d_1 - u2d_1)),
            (u2q_dif - (e2q_1 - u2q_1)),
            (i2d_hat_nodyn - (((Smart_Admittance_rv_1 * u2d_dif_1) + (u2q_dif_1 * Smart_Admittance_xv_1)) / denom_1)),
            (i2q_hat_nodyn - (((Smart_Admittance_rv_1 * u2q_dif_1) - (u2d_dif_1 * Smart_Admittance_xv_1)) / denom_1)),
            (id2_raw - (((sym.Const(1.0) - Smart_Admittance_alpha_va_1) * i2d_hat_nodyn_1) + (Smart_Admittance_alpha_va_1 * i2d_hat_dyn_1))),
            (iq2_raw - (((sym.Const(1.0) - Smart_Admittance_alpha_va_1) * i2q_hat_nodyn_1) + (Smart_Admittance_alpha_va_1 * i2q_hat_dyn_1))),
            (e_int_d - e1d_1),
            (safe_V1vsc - ((sym.Const(0.01) * sym.heaviside((sym.Const(0.01) - V1vsc_1))) + (V1vsc_1 * (sym.Const(1) - sym.heaviside((sym.Const(0.01) - V1vsc_1)))))),
            (inv_V1vsc - (sym.Const(1.0) / safe_V1vsc_1)),
            (P_dis_normal - ((Smart_Admittance_PmvLim_discharge_1 * sym.heaviside((Smart_Admittance_Pmax_dyn_1 - Smart_Admittance_PmvLim_discharge_1))) + (Smart_Admittance_Pmax_dyn_1 * (sym.Const(1) - sym.heaviside((Smart_Admittance_Pmax_dyn_1 - Smart_Admittance_PmvLim_discharge_1)))))),
            (P_chg_normal - ((Smart_Admittance_PmvLim_charge_1 * sym.heaviside((Smart_Admittance_PmvLim_charge_1 - (-Smart_Admittance_Pmax_dyn_1)))) + ((-Smart_Admittance_Pmax_dyn_1) * (sym.Const(1) - sym.heaviside((Smart_Admittance_PmvLim_charge_1 - (-Smart_Admittance_Pmax_dyn_1))))))),
            (PPCChigh - (Smart_Admittance_PlantEff_1 * ((sym.heaviside((FRT1_flag_1 - sym.Const(0.5))) * Smart_Admittance_PmvLim_crit_1) + ((sym.Const(1.0) - sym.heaviside((FRT1_flag_1 - sym.Const(0.5)))) * P_dis_normal_1)))),
            (PPCClow - (Smart_Admittance_inv_PlantEff_1 * ((sym.heaviside((FRT1_flag_1 - sym.Const(0.5))) * (-Smart_Admittance_PmvLim_crit_1)) + ((sym.Const(1.0) - sym.heaviside((FRT1_flag_1 - sym.Const(0.5)))) * P_chg_normal_1)))),
            (idMVhigh - ((((PPCChigh_1 * inv_V1vsc_1) * Smart_Admittance_inv_k_eff_trafo_1) * sym.heaviside((Smart_Admittance_CAPABILITY_Imax_conv_1 - ((PPCChigh_1 * inv_V1vsc_1) * Smart_Admittance_inv_k_eff_trafo_1)))) + (Smart_Admittance_CAPABILITY_Imax_conv_1 * (sym.Const(1) - sym.heaviside((Smart_Admittance_CAPABILITY_Imax_conv_1 - ((PPCChigh_1 * inv_V1vsc_1) * Smart_Admittance_inv_k_eff_trafo_1))))))),
            (idMVlow - ((((PPCClow_1 * inv_V1vsc_1) * Smart_Admittance_k_eff_trafo_1) * sym.heaviside((((PPCClow_1 * inv_V1vsc_1) * Smart_Admittance_k_eff_trafo_1) - (-Smart_Admittance_CAPABILITY_Imax_conv_1)))) + ((-Smart_Admittance_CAPABILITY_Imax_conv_1) * (sym.Const(1) - sym.heaviside((((PPCClow_1 * inv_V1vsc_1) * Smart_Admittance_k_eff_trafo_1) - (-Smart_Admittance_CAPABILITY_Imax_conv_1))))))),
            (lim1 - ((safe_V1vsc_1 - Smart_Admittance_VdcRef_1) * Smart_Admittance_inv_Xtrafo_Lout_pu_1)),
            (V_max_safe - ((Smart_Admittance_MaxAuxiliaryVoltage_1 * sym.heaviside((Smart_Admittance_MaxTransfoFluxVoltage_1 - Smart_Admittance_MaxAuxiliaryVoltage_1))) + (Smart_Admittance_MaxTransfoFluxVoltage_1 * (sym.Const(1) - sym.heaviside((Smart_Admittance_MaxTransfoFluxVoltage_1 - Smart_Admittance_MaxAuxiliaryVoltage_1)))))),
            (lim2 - ((safe_V1vsc_1 - V_max_safe_1) * Smart_Admittance_inv_Xtrafo_pu_1)),
            (i_cap_raw - ((lim1_1 * sym.heaviside((lim2_1 - lim1_1))) + (lim2_1 * (sym.Const(1) - sym.heaviside((lim2_1 - lim1_1)))))),
            (ImaxCapacitive - (((-Smart_Admittance_CAPABILITY_Imax_conv_1) * sym.heaviside(((-Smart_Admittance_CAPABILITY_Imax_conv_1) - i_cap_raw_1))) + (i_cap_raw_1 * (sym.Const(1) - sym.heaviside(((-Smart_Admittance_CAPABILITY_Imax_conv_1) - i_cap_raw_1)))))),
            (i_ind_raw - ((safe_V1vsc_1 - Smart_Admittance_MinAuxiliaryVoltage_1) * Smart_Admittance_inv_Xtrafo_pu_1)),
            (ImaxInductive - ((Smart_Admittance_CAPABILITY_Imax_conv_1 * sym.heaviside((i_ind_raw_1 - Smart_Admittance_CAPABILITY_Imax_conv_1))) + (i_ind_raw_1 * (sym.Const(1) - sym.heaviside((i_ind_raw_1 - Smart_Admittance_CAPABILITY_Imax_conv_1)))))),
            (id_lim_rect - ((idMVlow_1 * sym.heaviside((idMVlow_1 - ((idMVhigh_1 * sym.heaviside((id_raw_1 - idMVhigh_1))) + (id_raw_1 * (sym.Const(1) - sym.heaviside((id_raw_1 - idMVhigh_1)))))))) + (((idMVhigh_1 * sym.heaviside((id_raw_1 - idMVhigh_1))) + (id_raw_1 * (sym.Const(1) - sym.heaviside((id_raw_1 - idMVhigh_1))))) * (sym.Const(1) - sym.heaviside((idMVlow_1 - ((idMVhigh_1 * sym.heaviside((id_raw_1 - idMVhigh_1))) + (id_raw_1 * (sym.Const(1) - sym.heaviside((id_raw_1 - idMVhigh_1))))))))))),
            (iq_lim_rect - ((ImaxCapacitive_1 * sym.heaviside((ImaxCapacitive_1 - ((ImaxInductive_1 * sym.heaviside((iq_raw_1 - ImaxInductive_1))) + (iq_raw_1 * (sym.Const(1) - sym.heaviside((iq_raw_1 - ImaxInductive_1)))))))) + (((ImaxInductive_1 * sym.heaviside((iq_raw_1 - ImaxInductive_1))) + (iq_raw_1 * (sym.Const(1) - sym.heaviside((iq_raw_1 - ImaxInductive_1))))) * (sym.Const(1) - sym.heaviside((ImaxCapacitive_1 - ((ImaxInductive_1 * sym.heaviside((iq_raw_1 - ImaxInductive_1))) + (iq_raw_1 * (sym.Const(1) - sym.heaviside((iq_raw_1 - ImaxInductive_1))))))))))),
            (I_mag_sq - ((id_lim_rect_1 * id_lim_rect_1) + (iq_lim_rect_1 * iq_lim_rect_1))),
            (I_mag - sym.sqrt(I_mag_sq_1)),
            (iq_prio - (((-Smart_Admittance_CAPABILITY_Imax_conv_1) * sym.heaviside(((-Smart_Admittance_CAPABILITY_Imax_conv_1) - ((Smart_Admittance_CAPABILITY_Imax_conv_1 * sym.heaviside((iq_lim_rect_1 - Smart_Admittance_CAPABILITY_Imax_conv_1))) + (iq_lim_rect_1 * (sym.Const(1) - sym.heaviside((iq_lim_rect_1 - Smart_Admittance_CAPABILITY_Imax_conv_1)))))))) + (((Smart_Admittance_CAPABILITY_Imax_conv_1 * sym.heaviside((iq_lim_rect_1 - Smart_Admittance_CAPABILITY_Imax_conv_1))) + (iq_lim_rect_1 * (sym.Const(1) - sym.heaviside((iq_lim_rect_1 - Smart_Admittance_CAPABILITY_Imax_conv_1))))) * (sym.Const(1) - sym.heaviside(((-Smart_Admittance_CAPABILITY_Imax_conv_1) - ((Smart_Admittance_CAPABILITY_Imax_conv_1 * sym.heaviside((iq_lim_rect_1 - Smart_Admittance_CAPABILITY_Imax_conv_1))) + (iq_lim_rect_1 * (sym.Const(1) - sym.heaviside((iq_lim_rect_1 - Smart_Admittance_CAPABILITY_Imax_conv_1))))))))))),
            (id_avail - sym.sqrt(((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - ((Smart_Admittance_CAPABILITY_Imax_conv_1 * Smart_Admittance_CAPABILITY_Imax_conv_1) - (iq_prio_1 * iq_prio_1))))) + (((Smart_Admittance_CAPABILITY_Imax_conv_1 * Smart_Admittance_CAPABILITY_Imax_conv_1) - (iq_prio_1 * iq_prio_1)) * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - ((Smart_Admittance_CAPABILITY_Imax_conv_1 * Smart_Admittance_CAPABILITY_Imax_conv_1) - (iq_prio_1 * iq_prio_1))))))))),
            (id_prio - ((sym.heaviside((id_lim_rect_1 - sym.Const(0.0))) * ((id_lim_rect_1 * sym.heaviside((id_avail_1 - id_lim_rect_1))) + (id_avail_1 * (sym.Const(1) - sym.heaviside((id_avail_1 - id_lim_rect_1)))))) + ((sym.Const(1.0) - sym.heaviside((id_lim_rect_1 - sym.Const(0.0)))) * ((id_lim_rect_1 * sym.heaviside((id_lim_rect_1 - (-id_avail_1)))) + ((-id_avail_1) * (sym.Const(1) - sym.heaviside((id_lim_rect_1 - (-id_avail_1))))))))),
            (scale_bal - ((sym.heaviside((I_mag_1 - Smart_Admittance_CAPABILITY_Imax_conv_1)) * (Smart_Admittance_CAPABILITY_Imax_conv_1 / ((sym.Const(1e-06) * sym.heaviside((sym.Const(1e-06) - I_mag_1))) + (I_mag_1 * (sym.Const(1) - sym.heaviside((sym.Const(1e-06) - I_mag_1))))))) + ((sym.Const(1.0) - sym.heaviside((I_mag_1 - Smart_Admittance_CAPABILITY_Imax_conv_1))) * sym.Const(1.0)))),
            (id_bal - (id_lim_rect_1 * scale_bal_1)),
            (iq_bal - (iq_lim_rect_1 * scale_bal_1)),
            (use_prio_Q - (((sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((FRT1_flag_1 - sym.Const(0.5)))) * (sym.Const(1.0) - sym.heaviside((Smart_Admittance_Q_priority_flag_1 - sym.Const(0.5)))))) * sym.Const(1.0)) + ((sym.Const(1.0) - (sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((FRT1_flag_1 - sym.Const(0.5)))) * (sym.Const(1.0) - sym.heaviside((Smart_Admittance_Q_priority_flag_1 - sym.Const(0.5))))))) * sym.Const(0.0)))),
            (id_pos_sat - ((sym.heaviside((use_prio_Q_1 - sym.Const(0.5))) * id_prio_1) + ((sym.Const(1.0) - sym.heaviside((use_prio_Q_1 - sym.Const(0.5)))) * id_bal_1))),
            (iq_pos_sat - ((sym.heaviside((use_prio_Q_1 - sym.Const(0.5))) * iq_prio_1) + ((sym.Const(1.0) - sym.heaviside((use_prio_Q_1 - sym.Const(0.5)))) * iq_bal_1))),
            (scale_final - ((sym.heaviside((I_mag_1 - sym.Const(1e-06))) * (sym.sqrt(((id_pos_sat_1 * id_pos_sat_1) + (iq_pos_sat_1 * iq_pos_sat_1))) / I_mag_1)) + ((sym.Const(1.0) - sym.heaviside((I_mag_1 - sym.Const(1e-06)))) * sym.Const(1.0)))),
            (I_pos_used - (I_mag_1 * scale_final_1)),
            (I_neg_avail - ((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - (Smart_Admittance_CAPABILITY_Imax_conv_1 - I_pos_used_1)))) + ((Smart_Admittance_CAPABILITY_Imax_conv_1 - I_pos_used_1) * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - (Smart_Admittance_CAPABILITY_Imax_conv_1 - I_pos_used_1))))))),
            (i2_mag - sym.sqrt(((id2_raw_1 * id2_raw_1) + (iq2_raw_1 * iq2_raw_1)))),
            (scale_neg - ((sym.heaviside((i2_mag_1 - I_neg_avail_1)) * (I_neg_avail_1 / ((sym.Const(1e-06) * sym.heaviside((sym.Const(1e-06) - i2_mag_1))) + (i2_mag_1 * (sym.Const(1) - sym.heaviside((sym.Const(1e-06) - i2_mag_1))))))) + ((sym.Const(1.0) - sym.heaviside((i2_mag_1 - I_neg_avail_1))) * sym.Const(1.0)))),
            (id_neg_sat - (id2_raw_1 * scale_neg_1)),
            (iq_neg_sat - (iq2_raw_1 * scale_neg_1)),
            (viol_P - (((sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((id_raw_1 - idMVhigh_1))) * (sym.Const(1.0) - sym.heaviside((idMVlow_1 - id_raw_1))))) * sym.Const(1.0)) + ((sym.Const(1.0) - (sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((id_raw_1 - idMVhigh_1))) * (sym.Const(1.0) - sym.heaviside((idMVlow_1 - id_raw_1)))))) * sym.Const(0.0)))),
            (viol_Q - (((sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((iq_raw_1 - ImaxInductive_1))) * (sym.Const(1.0) - sym.heaviside((ImaxCapacitive_1 - iq_raw_1))))) * sym.Const(1.0)) + ((sym.Const(1.0) - (sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((iq_raw_1 - ImaxInductive_1))) * (sym.Const(1.0) - sym.heaviside((ImaxCapacitive_1 - iq_raw_1)))))) * sym.Const(0.0)))),
            (Overload_Flag - ((sym.heaviside((sym.Const(0.05) - time)) * sym.Const(0.0)) + ((sym.Const(1.0) - sym.heaviside((sym.Const(0.05) - time))) * (((sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((viol_P_1 - sym.Const(0.5)))) * (sym.Const(1.0) - sym.heaviside((viol_Q_1 - sym.Const(0.5)))))) * sym.Const(1.0)) + ((sym.Const(1.0) - (sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((viol_P_1 - sym.Const(0.5)))) * (sym.Const(1.0) - sym.heaviside((viol_Q_1 - sym.Const(0.5))))))) * sym.Const(0.0)))))),
            (P_capab_high - PPCChigh_1),
            (P_capab_low - PPCClow_1),
            (Q_capab_high - (safe_V1vsc_1 * sym.abs(ImaxInductive_1))),
            (Q_capab_low - (safe_V1vsc_1 * (-sym.abs(ImaxCapacitive_1)))),
            (i1d_hat - id_pos_sat_1),
            (i1q_hat - iq_pos_sat_1),
            (i2d_hat - id_neg_sat_1),
            (i2q_hat - iq_neg_sat_1),
            (Smart_Admittance_val_V_safe - ((sym.heaviside((sym.Const(0.01) - V1vsc_1)) * sym.Const(1.0)) + ((sym.Const(1.0) - sym.heaviside((sym.Const(0.01) - V1vsc_1))) * V1vsc_1))),
            (Smart_Admittance_val_Id_target - (Pvsc_1 / Smart_Admittance_val_V_safe_1)),
            (Smart_Admittance_val_Iq_target - ((-Qvsc_1) / Smart_Admittance_val_V_safe_1)),
            (Smart_Admittance_val_Imag_calc - sym.sqrt(((Smart_Admittance_val_Id_target_1 * Smart_Admittance_val_Id_target_1) + (Smart_Admittance_val_Iq_target_1 * Smart_Admittance_val_Iq_target_1)))),
            (Smart_Admittance_val_e1d_req - (u1d_1 + ((Smart_Admittance_rv_1 * Smart_Admittance_val_Id_target_1) - (Smart_Admittance_xv_1 * Smart_Admittance_val_Iq_target_1)))),
            (Smart_Admittance_val_e1q_req - (u1q_1 + ((Smart_Admittance_xv_1 * Smart_Admittance_val_Id_target_1) + (Smart_Admittance_rv_1 * Smart_Admittance_val_Iq_target_1)))),
        ],
        algebraic_vars=[w1, Smart_Admittance_rv, Smart_Admittance_xv, rv_init, xv_init, Smart_Admittance_PmvLim_discharge, Smart_Admittance_PmvLim_charge, Smart_Admittance_inv_PlantEff, Smart_Admittance_PlantEff, Smart_Admittance_Q_priority_flag, Smart_Admittance_MaxTransfoFluxVoltage, Smart_Admittance_MaxAuxiliaryVoltage, Smart_Admittance_MinAuxiliaryVoltage, Smart_Admittance_k_eff_trafo, Smart_Admittance_inv_k_eff_trafo, Smart_Admittance_inv_Xtrafo_Lout_pu, i1d_hat_dyn, i1q_hat_dyn, ud_dif, uq_dif, denom, i1d_hat_nodyn, i1q_hat_nodyn, Smart_Admittance_T_va_ramp, Smart_Admittance_alpha_va, id_raw, iq_raw, i2d_hat_dyn, i2q_hat_dyn, u2d_dif, u2q_dif, i2d_hat_nodyn, i2q_hat_nodyn, id2_raw, iq2_raw, e_int_d, safe_V1vsc, inv_V1vsc, P_dis_normal, P_chg_normal, PPCChigh, PPCClow, idMVhigh, idMVlow, lim1, V_max_safe, lim2, i_cap_raw, ImaxCapacitive, i_ind_raw, ImaxInductive, id_lim_rect, iq_lim_rect, I_mag_sq, I_mag, iq_prio, id_avail, id_prio, scale_bal, id_bal, iq_bal, use_prio_Q, id_pos_sat, iq_pos_sat, scale_final, I_pos_used, I_neg_avail, i2_mag, scale_neg, id_neg_sat, iq_neg_sat, viol_P, viol_Q, Overload_Flag, P_capab_high, P_capab_low, Q_capab_high, Q_capab_low, i1d_hat, i1q_hat, i2d_hat, i2q_hat, Smart_Admittance_val_V_safe, Smart_Admittance_val_Id_target, Smart_Admittance_val_Iq_target, Smart_Admittance_val_Imag_calc, Smart_Admittance_val_e1d_req, Smart_Admittance_val_e1q_req],
        in_vars=[e1d, e1q, e2d, e2q, u1d, u1q, u2d, u2q, V1vsc, FRT1_flag, Pvsc, Qvsc],
        out_vars=[i1d_hat, i1q_hat, i2d_hat, i2q_hat, e_int_d, Overload_Flag, Q_capab_high, Q_capab_low, P_capab_high, P_capab_low, xv_init, rv_init],
        name='Smart_Admittance'
    )
    templ.block.diff_vars = [d_Smart_Admittance_x1d_va, d_Smart_Admittance_x1q_va, d_Smart_Admittance_x2d_va, d_Smart_Admittance_x2q_va]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Smart_Admittance_f1: vf.add_const(None, name='f1'),
        Smart_Admittance_va_mode: vf.add_const(None, name='va_mode'),
        Smart_Admittance_GFOR_VirtualX_pu_std: vf.add_const(None, name='GFOR_VirtualX_pu_std'),
        Smart_Admittance_GFOR_tau_VA: vf.add_const(None, name='GFOR_tau_VA'),
        Smart_Admittance_GFOR_vPosD_fault_Tramp: vf.add_const(None, name='GFOR_vPosD_fault_Tramp'),
        Smart_Admittance_CAPABILITY_Imax_conv: vf.add_const(None, name='CAPABILITY_Imax_conv'),
        Smart_Admittance_CAPABILITY_Vmax_conv: vf.add_const(None, name='CAPABILITY_Vmax_conv'),
        Smart_Admittance_CAPABILITY_PmvLim_discharge: vf.add_const(None, name='CAPABILITY_PmvLim_discharge'),
        Smart_Admittance_CAPABILITY_PmvLim_charge: vf.add_const(None, name='CAPABILITY_PmvLim_charge'),
        Smart_Admittance_CAPABILITY_Qlim_cap: vf.add_const(None, name='CAPABILITY_Qlim_cap'),
        Smart_Admittance_CAPABILITY_Qlim_ind: vf.add_const(None, name='CAPABILITY_Qlim_ind'),
        Smart_Admittance_CAPABILITY_PQ_prio: vf.add_const(None, name='CAPABILITY_PQ_prio'),
        Smart_Admittance_CAPABILITY_Iposneg_prio: vf.add_const(None, name='CAPABILITY_Iposneg_prio'),
        Smart_Admittance_CAPABILITY_inv_V_limH: vf.add_const(None, name='CAPABILITY_inv_V_limH'),
        Smart_Admittance_CAPABILITY_inv_V_limL: vf.add_const(None, name='CAPABILITY_inv_V_limL'),
        Smart_Admittance_CAPABILITY_Ilim_neg: vf.add_const(None, name='CAPABILITY_Ilim_neg'),
        Smart_Admittance_CAPABILITY_PlimD_crit: vf.add_const(None, name='CAPABILITY_PlimD_crit'),
        Smart_Admittance_CAPABILITY_PlantEff: vf.add_const(None, name='CAPABILITY_PlantEff'),
        Smart_Admittance_CAPABILITY_TrafoEff: vf.add_const(None, name='CAPABILITY_TrafoEff'),
        Smart_Admittance_CAPABILITY_Vmin_auxiliary: vf.add_const(None, name='CAPABILITY_Vmin_auxiliary'),
        Smart_Admittance_CAPABILITY_Vmax_TransfoFlux: vf.add_const(None, name='CAPABILITY_Vmax_TransfoFlux'),
        Smart_Admittance_CAPABILITY_Vmax_auxiliary: vf.add_const(None, name='CAPABILITY_Vmax_auxiliary'),
        Smart_Admittance_ACLINE_Ltrafo: vf.add_const(None, name='ACLINE_Ltrafo'),
        Smart_Admittance_inv_Xtrafo_pu: vf.add_const(None, name='inv_Xtrafo_pu'),
        Smart_Admittance_Pmax_dyn: vf.add_const(None, name='Pmax_dyn'),
        Smart_Admittance_PmvLim_crit: vf.add_const(None, name='PmvLim_crit'),
        Smart_Admittance_VdcRef: vf.add_const(None, name='VdcRef'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Smart_Admittance_rv: ((Smart_Admittance_GFOR_VirtualX_pu_std_1 / Smart_Admittance_GFOR_tau_VA_1) / w1_1),
        Smart_Admittance_xv: Smart_Admittance_GFOR_VirtualX_pu_std_1,
        rv_init: Smart_Admittance_rv_1,
        xv_init: Smart_Admittance_xv_1,
        Smart_Admittance_x1d_va: Smart_Admittance_val_Id_target_1,
        Smart_Admittance_x1q_va: Smart_Admittance_val_Iq_target_1,
        Smart_Admittance_x2d_va: vf.add_const(0.0, name=''),
        Smart_Admittance_x2q_va: vf.add_const(0.0, name=''),
        i1d_hat: Smart_Admittance_val_Id_target_1,
        i1q_hat: Smart_Admittance_val_Iq_target_1,
        i1d_hat_nodyn: Smart_Admittance_val_Id_target_1,
        i1q_hat_nodyn: Smart_Admittance_val_Iq_target_1,
        i2d_hat: vf.add_const(0.0, name=''),
        i2q_hat: vf.add_const(0.0, name=''),
        id_raw: Smart_Admittance_val_Id_target_1,
        iq_raw: Smart_Admittance_val_Iq_target_1,
        id2_raw: vf.add_const(0.0, name=''),
        iq2_raw: vf.add_const(0.0, name=''),
        I_mag: Smart_Admittance_val_Imag_calc_1,
        e1d: Smart_Admittance_val_e1d_req_1,
        e1q: Smart_Admittance_val_e1q_req_1,
        e_int_d: Smart_Admittance_val_e1d_req_1,
        e2d: u2d_1,
        e2q: u2q_1,
        Overload_Flag: vf.add_const(0.0, name=''),
        Smart_Admittance_FlagLimit: vf.add_const(0.0, name=''),
        PPCChigh: (Smart_Admittance_PlantEff_1 * Smart_Admittance_PmvLim_discharge_1),
        PPCClow: (Smart_Admittance_inv_PlantEff_1 * Smart_Admittance_PmvLim_charge_1),
        P_capab_high: PPCChigh_1,
        P_capab_low: PPCClow_1,
        idMVhigh: Smart_Admittance_CAPABILITY_Imax_conv_1,
        idMVlow: ((-sym.Const(1.0)) * Smart_Admittance_CAPABILITY_Imax_conv_1),
        ImaxCapacitive: ((-sym.Const(1.0)) * Smart_Admittance_CAPABILITY_Imax_conv_1),
        ImaxInductive: Smart_Admittance_CAPABILITY_Imax_conv_1,
        Q_capab_high: (V1vsc_1 * Smart_Admittance_CAPABILITY_Imax_conv_1),
        Q_capab_low: ((-V1vsc_1) * Smart_Admittance_CAPABILITY_Imax_conv_1),
        id_pos_sat: Smart_Admittance_val_Id_target_1,
        iq_pos_sat: Smart_Admittance_val_Iq_target_1,
        id_neg_sat: vf.add_const(0.0, name=''),
        iq_neg_sat: vf.add_const(0.0, name=''),
        id_lim_rect: Smart_Admittance_val_Id_target_1,
        iq_lim_rect: Smart_Admittance_val_Iq_target_1,
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_smart_admittance_emt_template(vf=vf, name='Smart_Admittance' if name is None else name)

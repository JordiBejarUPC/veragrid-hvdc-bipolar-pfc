# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\DGS_test_type_models.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
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
    I_mag = vf.add_var('I_mag_' + name)
    I_mag_sq = vf.add_var('I_mag_sq_' + name)
    I_neg_avail = vf.add_var('I_neg_avail_' + name)
    I_pos_used = vf.add_var('I_pos_used_' + name)
    ImaxCapacitive = vf.add_var('ImaxCapacitive_' + name)
    ImaxInductive = vf.add_var('ImaxInductive_' + name)
    Overload_Flag = vf.add_var('Overload_Flag_' + name)
    PPCChigh = vf.add_var('PPCChigh_' + name)
    PPCClow = vf.add_var('PPCClow_' + name)
    P_capab_high = vf.add_var('P_capab_high_' + name)
    P_capab_low = vf.add_var('P_capab_low_' + name)
    P_chg_normal = vf.add_var('P_chg_normal_' + name)
    P_dis_normal = vf.add_var('P_dis_normal_' + name)
    Pvsc = vf.add_var('Pvsc_' + name)
    Q_capab_high = vf.add_var('Q_capab_high_' + name)
    Q_capab_low = vf.add_var('Q_capab_low_' + name)
    Qvsc = vf.add_var('Qvsc_' + name)
    Smart_Admittance_FlagLimit = vf.add_var('Smart_Admittance__FlagLimit_' + name)
    Smart_Admittance_MaxAuxiliaryVoltage = vf.add_var('Smart_Admittance__MaxAuxiliaryVoltage_' + name)
    Smart_Admittance_MaxTransfoFluxVoltage = vf.add_var('Smart_Admittance__MaxTransfoFluxVoltage_' + name)
    Smart_Admittance_MinAuxiliaryVoltage = vf.add_var('Smart_Admittance__MinAuxiliaryVoltage_' + name)
    Smart_Admittance_PlantEff = vf.add_var('Smart_Admittance__PlantEff_' + name)
    Smart_Admittance_PmvLim_charge = vf.add_var('Smart_Admittance__PmvLim_charge_' + name)
    Smart_Admittance_PmvLim_discharge = vf.add_var('Smart_Admittance__PmvLim_discharge_' + name)
    Smart_Admittance_Q_priority_flag = vf.add_var('Smart_Admittance__Q_priority_flag_' + name)
    Smart_Admittance_T_va_ramp = vf.add_var('Smart_Admittance__T_va_ramp_' + name)
    Smart_Admittance_alpha_va = vf.add_var('Smart_Admittance__alpha_va_' + name)
    Smart_Admittance_inv_PlantEff = vf.add_var('Smart_Admittance__inv_PlantEff_' + name)
    Smart_Admittance_inv_Xtrafo_Lout_pu = vf.add_var('Smart_Admittance__inv_Xtrafo_Lout_pu_' + name)
    Smart_Admittance_inv_k_eff_trafo = vf.add_var('Smart_Admittance__inv_k_eff_trafo_' + name)
    Smart_Admittance_k_eff_trafo = vf.add_var('Smart_Admittance__k_eff_trafo_' + name)
    Smart_Admittance_proc_select_0 = vf.add_var('Smart_Admittance__proc_select_0_' + name)
    Smart_Admittance_proc_select_1 = vf.add_var('Smart_Admittance__proc_select_1_' + name)
    Smart_Admittance_proc_select_10 = vf.add_var('Smart_Admittance__proc_select_10_' + name)
    Smart_Admittance_proc_select_11 = vf.add_var('Smart_Admittance__proc_select_11_' + name)
    Smart_Admittance_proc_select_12 = vf.add_var('Smart_Admittance__proc_select_12_' + name)
    Smart_Admittance_proc_select_13 = vf.add_var('Smart_Admittance__proc_select_13_' + name)
    Smart_Admittance_proc_select_14 = vf.add_var('Smart_Admittance__proc_select_14_' + name)
    Smart_Admittance_proc_select_2 = vf.add_var('Smart_Admittance__proc_select_2_' + name)
    Smart_Admittance_proc_select_3 = vf.add_var('Smart_Admittance__proc_select_3_' + name)
    Smart_Admittance_proc_select_4 = vf.add_var('Smart_Admittance__proc_select_4_' + name)
    Smart_Admittance_proc_select_5 = vf.add_var('Smart_Admittance__proc_select_5_' + name)
    Smart_Admittance_proc_select_6 = vf.add_var('Smart_Admittance__proc_select_6_' + name)
    Smart_Admittance_proc_select_7 = vf.add_var('Smart_Admittance__proc_select_7_' + name)
    Smart_Admittance_proc_select_8 = vf.add_var('Smart_Admittance__proc_select_8_' + name)
    Smart_Admittance_proc_select_9 = vf.add_var('Smart_Admittance__proc_select_9_' + name)
    Smart_Admittance_rv = vf.add_var('Smart_Admittance__rv_' + name)
    Smart_Admittance_val_Id_target = vf.add_var('Smart_Admittance__val_Id_target_' + name)
    Smart_Admittance_val_Imag_calc = vf.add_var('Smart_Admittance__val_Imag_calc_' + name)
    Smart_Admittance_val_Iq_target = vf.add_var('Smart_Admittance__val_Iq_target_' + name)
    Smart_Admittance_val_V_safe = vf.add_var('Smart_Admittance__val_V_safe_' + name)
    Smart_Admittance_val_e1d_req = vf.add_var('Smart_Admittance__val_e1d_req_' + name)
    Smart_Admittance_val_e1q_req = vf.add_var('Smart_Admittance__val_e1q_req_' + name)
    Smart_Admittance_xv = vf.add_var('Smart_Admittance__xv_' + name)
    V1vsc = vf.add_var('V1vsc_' + name)
    V_max_safe = vf.add_var('V_max_safe_' + name)
    denom = vf.add_var('denom_' + name)
    e1d = vf.add_var('e1d_' + name)
    e1q = vf.add_var('e1q_' + name)
    e2d = vf.add_var('e2d_' + name)
    e2q = vf.add_var('e2q_' + name)
    e_int_d = vf.add_var('e_int_d_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    i1d_hat = vf.add_var('i1d_hat_' + name)
    i1d_hat_dyn = vf.add_var('i1d_hat_dyn_' + name)
    i1d_hat_nodyn = vf.add_var('i1d_hat_nodyn_' + name)
    i1q_hat = vf.add_var('i1q_hat_' + name)
    i1q_hat_dyn = vf.add_var('i1q_hat_dyn_' + name)
    i1q_hat_nodyn = vf.add_var('i1q_hat_nodyn_' + name)
    i2_mag = vf.add_var('i2_mag_' + name)
    i2d_hat = vf.add_var('i2d_hat_' + name)
    i2d_hat_dyn = vf.add_var('i2d_hat_dyn_' + name)
    i2d_hat_nodyn = vf.add_var('i2d_hat_nodyn_' + name)
    i2q_hat = vf.add_var('i2q_hat_' + name)
    i2q_hat_dyn = vf.add_var('i2q_hat_dyn_' + name)
    i2q_hat_nodyn = vf.add_var('i2q_hat_nodyn_' + name)
    i_cap_raw = vf.add_var('i_cap_raw_' + name)
    i_ind_raw = vf.add_var('i_ind_raw_' + name)
    id2_raw = vf.add_var('id2_raw_' + name)
    idMVhigh = vf.add_var('idMVhigh_' + name)
    idMVlow = vf.add_var('idMVlow_' + name)
    id_avail = vf.add_var('id_avail_' + name)
    id_bal = vf.add_var('id_bal_' + name)
    id_lim_rect = vf.add_var('id_lim_rect_' + name)
    id_neg_sat = vf.add_var('id_neg_sat_' + name)
    id_pos_sat = vf.add_var('id_pos_sat_' + name)
    id_prio = vf.add_var('id_prio_' + name)
    id_raw = vf.add_var('id_raw_' + name)
    inv_V1vsc = vf.add_var('inv_V1vsc_' + name)
    iq2_raw = vf.add_var('iq2_raw_' + name)
    iq_bal = vf.add_var('iq_bal_' + name)
    iq_lim_rect = vf.add_var('iq_lim_rect_' + name)
    iq_neg_sat = vf.add_var('iq_neg_sat_' + name)
    iq_pos_sat = vf.add_var('iq_pos_sat_' + name)
    iq_prio = vf.add_var('iq_prio_' + name)
    iq_raw = vf.add_var('iq_raw_' + name)
    lim1 = vf.add_var('lim1_' + name)
    lim2 = vf.add_var('lim2_' + name)
    rv_init = vf.add_var('rv_init_' + name)
    safe_V1vsc = vf.add_var('safe_V1vsc_' + name)
    scale_bal = vf.add_var('scale_bal_' + name)
    scale_final = vf.add_var('scale_final_' + name)
    scale_neg = vf.add_var('scale_neg_' + name)
    u1d = vf.add_var('u1d_' + name)
    u1q = vf.add_var('u1q_' + name)
    u2d = vf.add_var('u2d_' + name)
    u2d_dif = vf.add_var('u2d_dif_' + name)
    u2q = vf.add_var('u2q_' + name)
    u2q_dif = vf.add_var('u2q_dif_' + name)
    ud_dif = vf.add_var('ud_dif_' + name)
    uq_dif = vf.add_var('uq_dif_' + name)
    use_prio_Q = vf.add_var('use_prio_Q_' + name)
    viol_P = vf.add_var('viol_P_' + name)
    viol_Q = vf.add_var('viol_Q_' + name)
    w1 = vf.add_var('w1_' + name)
    xv_init = vf.add_var('xv_init_' + name)

    # --- Derivative Variables ---
    d_Smart_Admittance_x1d_va = vf.add_diff_var('d_Smart_Admittance__x1d_va_' + name, base_var=Smart_Admittance_x1d_va)
    d_Smart_Admittance_x1q_va = vf.add_diff_var('d_Smart_Admittance__x1q_va_' + name, base_var=Smart_Admittance_x1q_va)
    d_Smart_Admittance_x2d_va = vf.add_diff_var('d_Smart_Admittance__x2d_va_' + name, base_var=Smart_Admittance_x2d_va)
    d_Smart_Admittance_x2q_va = vf.add_diff_var('d_Smart_Admittance__x2q_va_' + name, base_var=Smart_Admittance_x2q_va)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (((((e1d - u1d) - (Smart_Admittance_rv * Smart_Admittance_x1d_va)) + (Smart_Admittance_xv * Smart_Admittance_x1q_va)) * w1) / Smart_Admittance_xv),
            (((((e1q - u1q) - (Smart_Admittance_xv * Smart_Admittance_x1d_va)) - (Smart_Admittance_rv * Smart_Admittance_x1q_va)) * w1) / Smart_Admittance_xv),
            (((((e2d - u2d) - (Smart_Admittance_rv * Smart_Admittance_x2d_va)) - (Smart_Admittance_xv * Smart_Admittance_x2q_va)) * w1) / Smart_Admittance_xv),
            (((((e2q - u2q) + (Smart_Admittance_xv * Smart_Admittance_x2d_va)) - (Smart_Admittance_rv * Smart_Admittance_x2q_va)) * w1) / Smart_Admittance_xv),
        ],
        state_vars=[Smart_Admittance_x1d_va, Smart_Admittance_x1q_va, Smart_Admittance_x2d_va, Smart_Admittance_x2q_va],
        algebraic_eqs=[
            (w1 - ((sym.Const(2.0) * sym.Const(3.141592653589793)) * Smart_Admittance_f1)),
            (Smart_Admittance_rv - ((Smart_Admittance_GFOR_VirtualX_pu_std / Smart_Admittance_GFOR_tau_VA) / w1)),
            (Smart_Admittance_xv - Smart_Admittance_GFOR_VirtualX_pu_std),
            (rv_init - Smart_Admittance_rv),
            (xv_init - Smart_Admittance_xv),
            (Smart_Admittance_PmvLim_discharge - Smart_Admittance_CAPABILITY_PmvLim_discharge),
            (Smart_Admittance_PmvLim_charge - Smart_Admittance_CAPABILITY_PmvLim_charge),
            (Smart_Admittance_inv_PlantEff - (sym.Const(1.0) / Smart_Admittance_CAPABILITY_PlantEff)),
            (Smart_Admittance_PlantEff - Smart_Admittance_CAPABILITY_PlantEff),
            (Smart_Admittance_Q_priority_flag - Smart_Admittance_CAPABILITY_PQ_prio),
            (Smart_Admittance_MaxTransfoFluxVoltage - Smart_Admittance_CAPABILITY_Vmax_TransfoFlux),
            (Smart_Admittance_MaxAuxiliaryVoltage - Smart_Admittance_CAPABILITY_Vmax_auxiliary),
            (Smart_Admittance_MinAuxiliaryVoltage - Smart_Admittance_CAPABILITY_Vmin_auxiliary),
            (Smart_Admittance_k_eff_trafo - Smart_Admittance_CAPABILITY_TrafoEff),
            (Smart_Admittance_inv_k_eff_trafo - (sym.Const(1.0) / Smart_Admittance_CAPABILITY_TrafoEff)),
            (Smart_Admittance_inv_Xtrafo_Lout_pu - Smart_Admittance_ACLINE_Ltrafo),
            (i1d_hat_dyn - Smart_Admittance_x1d_va),
            (i1q_hat_dyn - Smart_Admittance_x1q_va),
            (ud_dif - (e1d - u1d)),
            (uq_dif - (e1q - u1q)),
            (denom - ((Smart_Admittance_rv * Smart_Admittance_rv) + (Smart_Admittance_xv * Smart_Admittance_xv))),
            (i1d_hat_nodyn - (((Smart_Admittance_rv * ud_dif) + (uq_dif * Smart_Admittance_xv)) / denom)),
            (i1q_hat_nodyn - (((Smart_Admittance_rv * uq_dif) - (ud_dif * Smart_Admittance_xv)) / denom)),
            (Smart_Admittance_T_va_ramp - sym.Const(0.3)),
            (Smart_Admittance_alpha_va - ((Smart_Admittance_proc_select_0 * ((sym.Const(1.0) * sym.heaviside(((glob_time / Smart_Admittance_T_va_ramp) - sym.Const(1.0)))) + ((glob_time / Smart_Admittance_T_va_ramp) * (sym.Const(1) - sym.heaviside(((glob_time / Smart_Admittance_T_va_ramp) - sym.Const(1.0))))))) + ((sym.Const(1.0) - Smart_Admittance_proc_select_0) * sym.Const(1.0)))),
            (id_raw - (((sym.Const(1.0) - Smart_Admittance_alpha_va) * i1d_hat_nodyn) + (Smart_Admittance_alpha_va * i1d_hat_dyn))),
            (iq_raw - (((sym.Const(1.0) - Smart_Admittance_alpha_va) * i1q_hat_nodyn) + (Smart_Admittance_alpha_va * i1q_hat_dyn))),
            (i2d_hat_dyn - Smart_Admittance_x2d_va),
            (i2q_hat_dyn - Smart_Admittance_x2q_va),
            (u2d_dif - (e2d - u2d)),
            (u2q_dif - (e2q - u2q)),
            (i2d_hat_nodyn - (((Smart_Admittance_rv * u2d_dif) + (u2q_dif * Smart_Admittance_xv)) / denom)),
            (i2q_hat_nodyn - (((Smart_Admittance_rv * u2q_dif) - (u2d_dif * Smart_Admittance_xv)) / denom)),
            (id2_raw - (((sym.Const(1.0) - Smart_Admittance_alpha_va) * i2d_hat_nodyn) + (Smart_Admittance_alpha_va * i2d_hat_dyn))),
            (iq2_raw - (((sym.Const(1.0) - Smart_Admittance_alpha_va) * i2q_hat_nodyn) + (Smart_Admittance_alpha_va * i2q_hat_dyn))),
            (e_int_d - e1d),
            (safe_V1vsc - ((sym.Const(0.01) * sym.heaviside((sym.Const(0.01) - V1vsc))) + (V1vsc * (sym.Const(1) - sym.heaviside((sym.Const(0.01) - V1vsc)))))),
            (inv_V1vsc - (sym.Const(1.0) / safe_V1vsc)),
            (P_dis_normal - ((Smart_Admittance_PmvLim_discharge * sym.heaviside((Smart_Admittance_Pmax_dyn - Smart_Admittance_PmvLim_discharge))) + (Smart_Admittance_Pmax_dyn * (sym.Const(1) - sym.heaviside((Smart_Admittance_Pmax_dyn - Smart_Admittance_PmvLim_discharge)))))),
            (P_chg_normal - ((Smart_Admittance_PmvLim_charge * sym.heaviside((Smart_Admittance_PmvLim_charge - (-Smart_Admittance_Pmax_dyn)))) + ((-Smart_Admittance_Pmax_dyn) * (sym.Const(1) - sym.heaviside((Smart_Admittance_PmvLim_charge - (-Smart_Admittance_Pmax_dyn))))))),
            (PPCChigh - (Smart_Admittance_PlantEff * ((Smart_Admittance_proc_select_1 * Smart_Admittance_PmvLim_crit) + ((sym.Const(1.0) - Smart_Admittance_proc_select_1) * P_dis_normal)))),
            (PPCClow - (Smart_Admittance_inv_PlantEff * ((Smart_Admittance_proc_select_2 * (-Smart_Admittance_PmvLim_crit)) + ((sym.Const(1.0) - Smart_Admittance_proc_select_2) * P_chg_normal)))),
            (idMVhigh - ((((PPCChigh * inv_V1vsc) * Smart_Admittance_inv_k_eff_trafo) * sym.heaviside((Smart_Admittance_CAPABILITY_Imax_conv - ((PPCChigh * inv_V1vsc) * Smart_Admittance_inv_k_eff_trafo)))) + (Smart_Admittance_CAPABILITY_Imax_conv * (sym.Const(1) - sym.heaviside((Smart_Admittance_CAPABILITY_Imax_conv - ((PPCChigh * inv_V1vsc) * Smart_Admittance_inv_k_eff_trafo))))))),
            (idMVlow - ((((PPCClow * inv_V1vsc) * Smart_Admittance_k_eff_trafo) * sym.heaviside((((PPCClow * inv_V1vsc) * Smart_Admittance_k_eff_trafo) - (-Smart_Admittance_CAPABILITY_Imax_conv)))) + ((-Smart_Admittance_CAPABILITY_Imax_conv) * (sym.Const(1) - sym.heaviside((((PPCClow * inv_V1vsc) * Smart_Admittance_k_eff_trafo) - (-Smart_Admittance_CAPABILITY_Imax_conv))))))),
            (lim1 - ((safe_V1vsc - Smart_Admittance_VdcRef) * Smart_Admittance_inv_Xtrafo_Lout_pu)),
            (V_max_safe - ((Smart_Admittance_MaxAuxiliaryVoltage * sym.heaviside((Smart_Admittance_MaxTransfoFluxVoltage - Smart_Admittance_MaxAuxiliaryVoltage))) + (Smart_Admittance_MaxTransfoFluxVoltage * (sym.Const(1) - sym.heaviside((Smart_Admittance_MaxTransfoFluxVoltage - Smart_Admittance_MaxAuxiliaryVoltage)))))),
            (lim2 - ((safe_V1vsc - V_max_safe) * Smart_Admittance_inv_Xtrafo_pu)),
            (i_cap_raw - ((lim1 * sym.heaviside((lim2 - lim1))) + (lim2 * (sym.Const(1) - sym.heaviside((lim2 - lim1)))))),
            (ImaxCapacitive - (((-Smart_Admittance_CAPABILITY_Imax_conv) * sym.heaviside(((-Smart_Admittance_CAPABILITY_Imax_conv) - i_cap_raw))) + (i_cap_raw * (sym.Const(1) - sym.heaviside(((-Smart_Admittance_CAPABILITY_Imax_conv) - i_cap_raw)))))),
            (i_ind_raw - ((safe_V1vsc - Smart_Admittance_MinAuxiliaryVoltage) * Smart_Admittance_inv_Xtrafo_pu)),
            (ImaxInductive - ((Smart_Admittance_CAPABILITY_Imax_conv * sym.heaviside((i_ind_raw - Smart_Admittance_CAPABILITY_Imax_conv))) + (i_ind_raw * (sym.Const(1) - sym.heaviside((i_ind_raw - Smart_Admittance_CAPABILITY_Imax_conv)))))),
            (id_lim_rect - ((idMVlow * sym.heaviside((idMVlow - ((idMVhigh * sym.heaviside((id_raw - idMVhigh))) + (id_raw * (sym.Const(1) - sym.heaviside((id_raw - idMVhigh)))))))) + (((idMVhigh * sym.heaviside((id_raw - idMVhigh))) + (id_raw * (sym.Const(1) - sym.heaviside((id_raw - idMVhigh))))) * (sym.Const(1) - sym.heaviside((idMVlow - ((idMVhigh * sym.heaviside((id_raw - idMVhigh))) + (id_raw * (sym.Const(1) - sym.heaviside((id_raw - idMVhigh))))))))))),
            (iq_lim_rect - ((ImaxCapacitive * sym.heaviside((ImaxCapacitive - ((ImaxInductive * sym.heaviside((iq_raw - ImaxInductive))) + (iq_raw * (sym.Const(1) - sym.heaviside((iq_raw - ImaxInductive)))))))) + (((ImaxInductive * sym.heaviside((iq_raw - ImaxInductive))) + (iq_raw * (sym.Const(1) - sym.heaviside((iq_raw - ImaxInductive))))) * (sym.Const(1) - sym.heaviside((ImaxCapacitive - ((ImaxInductive * sym.heaviside((iq_raw - ImaxInductive))) + (iq_raw * (sym.Const(1) - sym.heaviside((iq_raw - ImaxInductive))))))))))),
            (I_mag_sq - ((id_lim_rect * id_lim_rect) + (iq_lim_rect * iq_lim_rect))),
            (I_mag - sym.sqrt(I_mag_sq)),
            (iq_prio - (((-Smart_Admittance_CAPABILITY_Imax_conv) * sym.heaviside(((-Smart_Admittance_CAPABILITY_Imax_conv) - ((Smart_Admittance_CAPABILITY_Imax_conv * sym.heaviside((iq_lim_rect - Smart_Admittance_CAPABILITY_Imax_conv))) + (iq_lim_rect * (sym.Const(1) - sym.heaviside((iq_lim_rect - Smart_Admittance_CAPABILITY_Imax_conv)))))))) + (((Smart_Admittance_CAPABILITY_Imax_conv * sym.heaviside((iq_lim_rect - Smart_Admittance_CAPABILITY_Imax_conv))) + (iq_lim_rect * (sym.Const(1) - sym.heaviside((iq_lim_rect - Smart_Admittance_CAPABILITY_Imax_conv))))) * (sym.Const(1) - sym.heaviside(((-Smart_Admittance_CAPABILITY_Imax_conv) - ((Smart_Admittance_CAPABILITY_Imax_conv * sym.heaviside((iq_lim_rect - Smart_Admittance_CAPABILITY_Imax_conv))) + (iq_lim_rect * (sym.Const(1) - sym.heaviside((iq_lim_rect - Smart_Admittance_CAPABILITY_Imax_conv))))))))))),
            (id_avail - sym.sqrt(((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - ((Smart_Admittance_CAPABILITY_Imax_conv * Smart_Admittance_CAPABILITY_Imax_conv) - (iq_prio * iq_prio))))) + (((Smart_Admittance_CAPABILITY_Imax_conv * Smart_Admittance_CAPABILITY_Imax_conv) - (iq_prio * iq_prio)) * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - ((Smart_Admittance_CAPABILITY_Imax_conv * Smart_Admittance_CAPABILITY_Imax_conv) - (iq_prio * iq_prio))))))))),
            (id_prio - ((Smart_Admittance_proc_select_3 * ((id_lim_rect * sym.heaviside((id_avail - id_lim_rect))) + (id_avail * (sym.Const(1) - sym.heaviside((id_avail - id_lim_rect)))))) + ((sym.Const(1.0) - Smart_Admittance_proc_select_3) * ((id_lim_rect * sym.heaviside((id_lim_rect - (-id_avail)))) + ((-id_avail) * (sym.Const(1) - sym.heaviside((id_lim_rect - (-id_avail))))))))),
            (scale_bal - ((Smart_Admittance_proc_select_4 * (Smart_Admittance_CAPABILITY_Imax_conv / ((sym.Const(1e-06) * sym.heaviside((sym.Const(1e-06) - I_mag))) + (I_mag * (sym.Const(1) - sym.heaviside((sym.Const(1e-06) - I_mag))))))) + ((sym.Const(1.0) - Smart_Admittance_proc_select_4) * sym.Const(1.0)))),
            (id_bal - (id_lim_rect * scale_bal)),
            (iq_bal - (iq_lim_rect * scale_bal)),
            (use_prio_Q - ((Smart_Admittance_proc_select_5 * sym.Const(1.0)) + ((sym.Const(1.0) - Smart_Admittance_proc_select_5) * sym.Const(0.0)))),
            (id_pos_sat - ((Smart_Admittance_proc_select_6 * id_prio) + ((sym.Const(1.0) - Smart_Admittance_proc_select_6) * id_bal))),
            (iq_pos_sat - ((Smart_Admittance_proc_select_7 * iq_prio) + ((sym.Const(1.0) - Smart_Admittance_proc_select_7) * iq_bal))),
            (scale_final - ((Smart_Admittance_proc_select_8 * (sym.sqrt(((id_pos_sat * id_pos_sat) + (iq_pos_sat * iq_pos_sat))) / I_mag)) + ((sym.Const(1.0) - Smart_Admittance_proc_select_8) * sym.Const(1.0)))),
            (I_pos_used - (I_mag * scale_final)),
            (I_neg_avail - ((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - (Smart_Admittance_CAPABILITY_Imax_conv - I_pos_used)))) + ((Smart_Admittance_CAPABILITY_Imax_conv - I_pos_used) * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - (Smart_Admittance_CAPABILITY_Imax_conv - I_pos_used))))))),
            (i2_mag - sym.sqrt(((id2_raw * id2_raw) + (iq2_raw * iq2_raw)))),
            (scale_neg - ((Smart_Admittance_proc_select_9 * (I_neg_avail / ((sym.Const(1e-06) * sym.heaviside((sym.Const(1e-06) - i2_mag))) + (i2_mag * (sym.Const(1) - sym.heaviside((sym.Const(1e-06) - i2_mag))))))) + ((sym.Const(1.0) - Smart_Admittance_proc_select_9) * sym.Const(1.0)))),
            (id_neg_sat - (id2_raw * scale_neg)),
            (iq_neg_sat - (iq2_raw * scale_neg)),
            (viol_P - ((Smart_Admittance_proc_select_10 * sym.Const(1.0)) + ((sym.Const(1.0) - Smart_Admittance_proc_select_10) * sym.Const(0.0)))),
            (viol_Q - ((Smart_Admittance_proc_select_11 * sym.Const(1.0)) + ((sym.Const(1.0) - Smart_Admittance_proc_select_11) * sym.Const(0.0)))),
            (Overload_Flag - ((Smart_Admittance_proc_select_13 * sym.Const(0.0)) + ((sym.Const(1.0) - Smart_Admittance_proc_select_13) * ((Smart_Admittance_proc_select_12 * sym.Const(1.0)) + ((sym.Const(1.0) - Smart_Admittance_proc_select_12) * sym.Const(0.0)))))),
            (P_capab_high - PPCChigh),
            (P_capab_low - PPCClow),
            (Q_capab_high - (safe_V1vsc * sym.abs(ImaxInductive))),
            (Q_capab_low - (safe_V1vsc * (-sym.abs(ImaxCapacitive)))),
            (i1d_hat - id_pos_sat),
            (i1q_hat - iq_pos_sat),
            (i2d_hat - id_neg_sat),
            (i2q_hat - iq_neg_sat),
            (Smart_Admittance_val_V_safe - ((Smart_Admittance_proc_select_14 * sym.Const(1.0)) + ((sym.Const(1.0) - Smart_Admittance_proc_select_14) * V1vsc))),
            (Smart_Admittance_val_Id_target - (Pvsc / Smart_Admittance_val_V_safe)),
            (Smart_Admittance_val_Iq_target - ((-Qvsc) / Smart_Admittance_val_V_safe)),
            (Smart_Admittance_val_Imag_calc - sym.sqrt(((Smart_Admittance_val_Id_target * Smart_Admittance_val_Id_target) + (Smart_Admittance_val_Iq_target * Smart_Admittance_val_Iq_target)))),
            (Smart_Admittance_val_e1d_req - (u1d + ((Smart_Admittance_rv * Smart_Admittance_val_Id_target) - (Smart_Admittance_xv * Smart_Admittance_val_Iq_target)))),
            (Smart_Admittance_val_e1q_req - (u1q + ((Smart_Admittance_xv * Smart_Admittance_val_Id_target) + (Smart_Admittance_rv * Smart_Admittance_val_Iq_target)))),
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
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Smart_Admittance_proc_select_0: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_1: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_2: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_3: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_4: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_5: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_6: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_7: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_8: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_9: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_10: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_11: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_12: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_13: vf.add_const(0.0, name=''),
        Smart_Admittance_proc_select_14: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Smart_Admittance_rv: ((Smart_Admittance_GFOR_VirtualX_pu_std / Smart_Admittance_GFOR_tau_VA) / w1),
        Smart_Admittance_xv: Smart_Admittance_GFOR_VirtualX_pu_std,
        rv_init: Smart_Admittance_rv,
        xv_init: Smart_Admittance_xv,
        Smart_Admittance_x1d_va: Smart_Admittance_val_Id_target,
        Smart_Admittance_x1q_va: Smart_Admittance_val_Iq_target,
        Smart_Admittance_x2d_va: vf.add_const(0.0, name=''),
        Smart_Admittance_x2q_va: vf.add_const(0.0, name=''),
        i1d_hat: Smart_Admittance_val_Id_target,
        i1q_hat: Smart_Admittance_val_Iq_target,
        i1d_hat_nodyn: Smart_Admittance_val_Id_target,
        i1q_hat_nodyn: Smart_Admittance_val_Iq_target,
        i2d_hat: vf.add_const(0.0, name=''),
        i2q_hat: vf.add_const(0.0, name=''),
        id_raw: Smart_Admittance_val_Id_target,
        iq_raw: Smart_Admittance_val_Iq_target,
        id2_raw: vf.add_const(0.0, name=''),
        iq2_raw: vf.add_const(0.0, name=''),
        I_mag: Smart_Admittance_val_Imag_calc,
        e1d: Smart_Admittance_val_e1d_req,
        e1q: Smart_Admittance_val_e1q_req,
        e_int_d: Smart_Admittance_val_e1d_req,
        e2d: u2d,
        e2q: u2q,
        Overload_Flag: vf.add_const(0.0, name=''),
        Smart_Admittance_FlagLimit: vf.add_const(0.0, name=''),
        PPCChigh: (Smart_Admittance_PlantEff * Smart_Admittance_PmvLim_discharge),
        PPCClow: (Smart_Admittance_inv_PlantEff * Smart_Admittance_PmvLim_charge),
        P_capab_high: PPCChigh,
        P_capab_low: PPCClow,
        idMVhigh: Smart_Admittance_CAPABILITY_Imax_conv,
        idMVlow: ((-sym.Const(1.0)) * Smart_Admittance_CAPABILITY_Imax_conv),
        ImaxCapacitive: ((-sym.Const(1.0)) * Smart_Admittance_CAPABILITY_Imax_conv),
        ImaxInductive: Smart_Admittance_CAPABILITY_Imax_conv,
        Q_capab_high: (V1vsc * Smart_Admittance_CAPABILITY_Imax_conv),
        Q_capab_low: ((-V1vsc) * Smart_Admittance_CAPABILITY_Imax_conv),
        id_pos_sat: Smart_Admittance_val_Id_target,
        iq_pos_sat: Smart_Admittance_val_Iq_target,
        id_neg_sat: vf.add_const(0.0, name=''),
        iq_neg_sat: vf.add_const(0.0, name=''),
        id_lim_rect: Smart_Admittance_val_Id_target,
        iq_lim_rect: Smart_Admittance_val_Iq_target,
    }
    templ.block.procedural_logic = [
        sampled_value(output=Smart_Admittance_proc_select_0, source=(Smart_Admittance_T_va_ramp > 1e-06)),
        sampled_value(output=Smart_Admittance_proc_select_1, source=(FRT1_flag > 0.5)),
        sampled_value(output=Smart_Admittance_proc_select_2, source=(FRT1_flag > 0.5)),
        sampled_value(output=Smart_Admittance_proc_select_3, source=(id_lim_rect > 0.0)),
        sampled_value(output=Smart_Admittance_proc_select_4, source=(I_mag > Smart_Admittance_CAPABILITY_Imax_conv)),
        sampled_value(output=Smart_Admittance_proc_select_5, source=(1.0 - ((1.0 - sym.heaviside((FRT1_flag - 0.5))) * (1.0 - sym.heaviside((Smart_Admittance_Q_priority_flag - 0.5)))))),
        sampled_value(output=Smart_Admittance_proc_select_6, source=(use_prio_Q > 0.5)),
        sampled_value(output=Smart_Admittance_proc_select_7, source=(use_prio_Q > 0.5)),
        sampled_value(output=Smart_Admittance_proc_select_8, source=(I_mag > 1e-06)),
        sampled_value(output=Smart_Admittance_proc_select_9, source=(i2_mag > I_neg_avail)),
        sampled_value(output=Smart_Admittance_proc_select_10, source=(1.0 - ((1.0 - sym.heaviside((id_raw - idMVhigh))) * (1.0 - sym.heaviside((idMVlow - id_raw)))))),
        sampled_value(output=Smart_Admittance_proc_select_11, source=(1.0 - ((1.0 - sym.heaviside((iq_raw - ImaxInductive))) * (1.0 - sym.heaviside((ImaxCapacitive - iq_raw)))))),
        sampled_value(output=Smart_Admittance_proc_select_12, source=(1.0 - ((1.0 - sym.heaviside((viol_P - 0.5))) * (1.0 - sym.heaviside((viol_Q - 0.5)))))),
        sampled_value(output=Smart_Admittance_proc_select_13, source=(glob_time < 0.05)),
        sampled_value(output=Smart_Admittance_proc_select_14, source=(V1vsc < 0.01)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_smart_admittance_emt_template(vf=vf, name='Smart_Admittance' if name is None else name)

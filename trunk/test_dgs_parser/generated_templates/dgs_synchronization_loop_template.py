# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\DGS_test_type_models.dgs

import numpy as np
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_synchronization_loop_emt_template(vf: VarFactory, name: str = 'Synchronization Loop') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_2H_s_KD_H = vf.add_var('1/(2H s + KD)__H_' + name)
    v_1_2H_s_KD_Xv = vf.add_var('1/(2H s + KD)__Xv_' + name)
    v_1_2H_s_KD_f1 = vf.add_var('1/(2H s + KD)__f1_' + name)
    v_1_2H_s_KD_zeta = vf.add_var('1/(2H s + KD)__zeta_' + name)
    v_1_2Hs_H = vf.add_var('1/2Hs__H_' + name)
    v_1_2Hs_H_2 = vf.add_var('1/2Hs__H_' + name)
    Capability_and_limitation_MaxAuxiliaryVoltage = vf.add_var('Capability_and_limitation__MaxAuxiliaryVoltage_' + name)
    Capability_and_limitation_MaxAuxiliaryVoltage_1 = vf.add_var('Capability_and_limitation__MaxAuxiliaryVoltage_' + name)
    Capability_and_limitation_MaxTransfoFluxVoltage = vf.add_var('Capability_and_limitation__MaxTransfoFluxVoltage_' + name)
    Capability_and_limitation_MaxTransfoFluxVoltage_1 = vf.add_var('Capability_and_limitation__MaxTransfoFluxVoltage_' + name)
    Capability_and_limitation_MinAuxiliaryVoltage = vf.add_var('Capability_and_limitation__MinAuxiliaryVoltage_' + name)
    Capability_and_limitation_MinAuxiliaryVoltage_1 = vf.add_var('Capability_and_limitation__MinAuxiliaryVoltage_' + name)
    Capability_and_limitation_PlantEff = vf.add_var('Capability_and_limitation__PlantEff_' + name)
    Capability_and_limitation_PlantEff_1 = vf.add_var('Capability_and_limitation__PlantEff_' + name)
    Capability_and_limitation_Pmax_dyn = vf.add_var('Capability_and_limitation__Pmax_dyn_' + name)
    Capability_and_limitation_Pmax_dyn_1 = vf.add_var('Capability_and_limitation__Pmax_dyn_' + name)
    Capability_and_limitation_PmvLim_charge = vf.add_var('Capability_and_limitation__PmvLim_charge_' + name)
    Capability_and_limitation_PmvLim_charge_1 = vf.add_var('Capability_and_limitation__PmvLim_charge_' + name)
    Capability_and_limitation_PmvLim_crit = vf.add_var('Capability_and_limitation__PmvLim_crit_' + name)
    Capability_and_limitation_PmvLim_crit_1 = vf.add_var('Capability_and_limitation__PmvLim_crit_' + name)
    Capability_and_limitation_PmvLim_discharge = vf.add_var('Capability_and_limitation__PmvLim_discharge_' + name)
    Capability_and_limitation_PmvLim_discharge_1 = vf.add_var('Capability_and_limitation__PmvLim_discharge_' + name)
    Capability_and_limitation_Xtrafo_pu = vf.add_var('Capability_and_limitation__Xtrafo_pu_' + name)
    Capability_and_limitation_Xtrafo_pu_1 = vf.add_var('Capability_and_limitation__Xtrafo_pu_' + name)
    Capability_and_limitation_inv_PlantEff = vf.add_var('Capability_and_limitation__inv_PlantEff_' + name)
    Capability_and_limitation_inv_PlantEff_1 = vf.add_var('Capability_and_limitation__inv_PlantEff_' + name)
    Capability_and_limitation_inv_Xtrafo_Lout_pu = vf.add_var('Capability_and_limitation__inv_Xtrafo_Lout_pu_' + name)
    Capability_and_limitation_inv_Xtrafo_Lout_pu_1 = vf.add_var('Capability_and_limitation__inv_Xtrafo_Lout_pu_' + name)
    Capability_and_limitation_inv_Xtrafo_pu = vf.add_var('Capability_and_limitation__inv_Xtrafo_pu_' + name)
    Capability_and_limitation_inv_Xtrafo_pu_1 = vf.add_var('Capability_and_limitation__inv_Xtrafo_pu_' + name)
    Capability_and_limitation_inv_k_eff_trafo = vf.add_var('Capability_and_limitation__inv_k_eff_trafo_' + name)
    Capability_and_limitation_inv_k_eff_trafo_1 = vf.add_var('Capability_and_limitation__inv_k_eff_trafo_' + name)
    Capability_and_limitation_k_eff_trafo = vf.add_var('Capability_and_limitation__k_eff_trafo_' + name)
    Capability_and_limitation_k_eff_trafo_1 = vf.add_var('Capability_and_limitation__k_eff_trafo_' + name)
    Capability_block_Imax = vf.add_var('Capability_block__Imax_' + name)
    Capability_block_Imax_1 = vf.add_var('Capability_block__Imax_' + name)
    Capability_block_MaxAuxiliaryVoltage = vf.add_var('Capability_block__MaxAuxiliaryVoltage_' + name)
    Capability_block_MaxAuxiliaryVoltage_1 = vf.add_var('Capability_block__MaxAuxiliaryVoltage_' + name)
    Capability_block_MaxTransfoFluxVoltage = vf.add_var('Capability_block__MaxTransfoFluxVoltage_' + name)
    Capability_block_MaxTransfoFluxVoltage_1 = vf.add_var('Capability_block__MaxTransfoFluxVoltage_' + name)
    Capability_block_MinAuxiliaryVoltage = vf.add_var('Capability_block__MinAuxiliaryVoltage_' + name)
    Capability_block_MinAuxiliaryVoltage_1 = vf.add_var('Capability_block__MinAuxiliaryVoltage_' + name)
    Capability_block_PlantEff = vf.add_var('Capability_block__PlantEff_' + name)
    Capability_block_PlantEff_1 = vf.add_var('Capability_block__PlantEff_' + name)
    Capability_block_Pmax_dyn = vf.add_var('Capability_block__Pmax_dyn_' + name)
    Capability_block_Pmax_dyn_1 = vf.add_var('Capability_block__Pmax_dyn_' + name)
    Capability_block_PmvLim_charge = vf.add_var('Capability_block__PmvLim_charge_' + name)
    Capability_block_PmvLim_charge_1 = vf.add_var('Capability_block__PmvLim_charge_' + name)
    Capability_block_PmvLim_crit = vf.add_var('Capability_block__PmvLim_crit_' + name)
    Capability_block_PmvLim_crit_1 = vf.add_var('Capability_block__PmvLim_crit_' + name)
    Capability_block_PmvLim_discharge = vf.add_var('Capability_block__PmvLim_discharge_' + name)
    Capability_block_PmvLim_discharge_1 = vf.add_var('Capability_block__PmvLim_discharge_' + name)
    Capability_block_VdcRef = vf.add_var('Capability_block__VdcRef_' + name)
    Capability_block_VdcRef_1 = vf.add_var('Capability_block__VdcRef_' + name)
    Capability_block_Xtrafo_pu = vf.add_var('Capability_block__Xtrafo_pu_' + name)
    Capability_block_Xtrafo_pu_1 = vf.add_var('Capability_block__Xtrafo_pu_' + name)
    Capability_block_inv_PlantEff = vf.add_var('Capability_block__inv_PlantEff_' + name)
    Capability_block_inv_PlantEff_1 = vf.add_var('Capability_block__inv_PlantEff_' + name)
    Capability_block_inv_Xtrafo_Lout_pu = vf.add_var('Capability_block__inv_Xtrafo_Lout_pu_' + name)
    Capability_block_inv_Xtrafo_Lout_pu_1 = vf.add_var('Capability_block__inv_Xtrafo_Lout_pu_' + name)
    Capability_block_inv_Xtrafo_pu = vf.add_var('Capability_block__inv_Xtrafo_pu_' + name)
    Capability_block_inv_Xtrafo_pu_1 = vf.add_var('Capability_block__inv_Xtrafo_pu_' + name)
    Capability_block_inv_k_eff_trafo = vf.add_var('Capability_block__inv_k_eff_trafo_' + name)
    Capability_block_inv_k_eff_trafo_1 = vf.add_var('Capability_block__inv_k_eff_trafo_' + name)
    Capability_block_k_eff_trafo = vf.add_var('Capability_block__k_eff_trafo_' + name)
    Capability_block_k_eff_trafo_1 = vf.add_var('Capability_block__k_eff_trafo_' + name)
    Current_controller_ki_cc = vf.add_var('Current controller__ki_cc_' + name)
    Current_controller_kp_cc = vf.add_var('Current controller__kp_cc_' + name)
    Current_controller_l = vf.add_var('Current controller__l_' + name)
    Events_param_ROCOF = vf.add_var('Events__param_ROCOF_' + name)
    Events_param_ROCOF_2 = vf.add_var('Events__param_ROCOF_' + name)
    Events_param_phase_jump = vf.add_var('Events__param_phase_jump_' + name)
    Events_param_phase_jump_2 = vf.add_var('Events__param_phase_jump_' + name)
    Events_param_voltage_jump = vf.add_var('Events__param_voltage_jump_' + name)
    Events_param_voltage_jump_2 = vf.add_var('Events__param_voltage_jump_' + name)
    Fault_Detection_V1max = vf.add_var('Fault Detection__V1max_' + name)
    Fault_Detection_V1max_1 = vf.add_var('Fault Detection__V1max_' + name)
    Fault_Detection_V1min = vf.add_var('Fault Detection__V1min_' + name)
    Fault_Detection_V1min_1 = vf.add_var('Fault Detection__V1min_' + name)
    Fault_Detection_V2max = vf.add_var('Fault Detection__V2max_' + name)
    Fault_Detection_V2max_1 = vf.add_var('Fault Detection__V2max_' + name)
    Fault_Detection_V2min = vf.add_var('Fault Detection__V2min_' + name)
    Fault_Detection_V2min_1 = vf.add_var('Fault Detection__V2min_' + name)
    Grid_electrical_interface_p_mode = vf.add_var('Grid electrical interface__p_mode_' + name)
    MV_voltage_limit_MaxAuxiliaryVoltage = vf.add_var('MV_voltage_limit__MaxAuxiliaryVoltage_' + name)
    MV_voltage_limit_MaxAuxiliaryVoltage_2 = vf.add_var('MV_voltage_limit__MaxAuxiliaryVoltage_' + name)
    MV_voltage_limit_MaxTransfoFluxVoltage = vf.add_var('MV_voltage_limit__MaxTransfoFluxVoltage_' + name)
    MV_voltage_limit_MaxTransfoFluxVoltage_2 = vf.add_var('MV_voltage_limit__MaxTransfoFluxVoltage_' + name)
    MV_voltage_limit_MinAuxiliaryVoltage = vf.add_var('MV_voltage_limit__MinAuxiliaryVoltage_' + name)
    MV_voltage_limit_MinAuxiliaryVoltage_2 = vf.add_var('MV_voltage_limit__MinAuxiliaryVoltage_' + name)
    MV_voltage_limit_inv_Xtrafo_Lout_pu = vf.add_var('MV_voltage_limit__inv_Xtrafo_Lout_pu_' + name)
    MV_voltage_limit_inv_Xtrafo_Lout_pu_2 = vf.add_var('MV_voltage_limit__inv_Xtrafo_Lout_pu_' + name)
    MV_voltage_limit_inv_Xtrafo_pu = vf.add_var('MV_voltage_limit__inv_Xtrafo_pu_' + name)
    MV_voltage_limit_inv_Xtrafo_pu_2 = vf.add_var('MV_voltage_limit__inv_Xtrafo_pu_' + name)
    PCC_Measurements_T_plot_ramp = vf.add_var('PCC Measurements__T_plot_ramp_' + name)
    PCC_Measurements_f1 = vf.add_var('PCC Measurements__f1_' + name)
    PCC_Measurements_ki_pll = vf.add_var('PCC Measurements__ki_pll_' + name)
    PCC_Measurements_kp_pll = vf.add_var('PCC Measurements__kp_pll_' + name)
    PCC_Measurements_tau_plot = vf.add_var('PCC Measurements__tau_plot_' + name)
    Power_VI_limit_PlantEff = vf.add_var('Power_VI_limit__PlantEff_' + name)
    Power_VI_limit_PlantEff_2 = vf.add_var('Power_VI_limit__PlantEff_' + name)
    Power_VI_limit_Pmax_dyn = vf.add_var('Power_VI_limit__Pmax_dyn_' + name)
    Power_VI_limit_Pmax_dyn_2 = vf.add_var('Power_VI_limit__Pmax_dyn_' + name)
    Power_VI_limit_PmvLim_charge = vf.add_var('Power_VI_limit__PmvLim_charge_' + name)
    Power_VI_limit_PmvLim_charge_2 = vf.add_var('Power_VI_limit__PmvLim_charge_' + name)
    Power_VI_limit_PmvLim_crit = vf.add_var('Power_VI_limit__PmvLim_crit_' + name)
    Power_VI_limit_PmvLim_crit_2 = vf.add_var('Power_VI_limit__PmvLim_crit_' + name)
    Power_VI_limit_PmvLim_discharge = vf.add_var('Power_VI_limit__PmvLim_discharge_' + name)
    Power_VI_limit_PmvLim_discharge_2 = vf.add_var('Power_VI_limit__PmvLim_discharge_' + name)
    Power_VI_limit_Xtrafo_pu = vf.add_var('Power_VI_limit__Xtrafo_pu_' + name)
    Power_VI_limit_Xtrafo_pu_2 = vf.add_var('Power_VI_limit__Xtrafo_pu_' + name)
    Power_VI_limit_inv_PlantEff = vf.add_var('Power_VI_limit__inv_PlantEff_' + name)
    Power_VI_limit_inv_PlantEff_2 = vf.add_var('Power_VI_limit__inv_PlantEff_' + name)
    Power_VI_limit_inv_k_eff_trafo = vf.add_var('Power_VI_limit__inv_k_eff_trafo_' + name)
    Power_VI_limit_inv_k_eff_trafo_1 = vf.add_var('Power_VI_limit__inv_k_eff_trafo_' + name)
    Power_VI_limit_k_eff_trafo = vf.add_var('Power_VI_limit__k_eff_trafo_' + name)
    Power_VI_limit_k_eff_trafo_1 = vf.add_var('Power_VI_limit__k_eff_trafo_' + name)
    Protection_DtLVRT_1 = vf.add_var('Protection__DtLVRT_1_' + name)
    Protection_DtLVRT_2 = vf.add_var('Protection__DtLVRT_2_' + name)
    Protection_DtLVRT_3 = vf.add_var('Protection__DtLVRT_3_' + name)
    Protection_DtLVRT_4 = vf.add_var('Protection__DtLVRT_4_' + name)
    Protection_DtOVRT_1 = vf.add_var('Protection__DtOVRT_1_' + name)
    Protection_DtOVRT_2 = vf.add_var('Protection__DtOVRT_2_' + name)
    Protection_DtOVRT_3 = vf.add_var('Protection__DtOVRT_3_' + name)
    Protection_DtOVRT_4 = vf.add_var('Protection__DtOVRT_4_' + name)
    Protection_HighThr_Freq1 = vf.add_var('Protection__HighThr_Freq1_' + name)
    Protection_HighThr_Freq2 = vf.add_var('Protection__HighThr_Freq2_' + name)
    Protection_HighThr_FreqFast = vf.add_var('Protection__HighThr_FreqFast_' + name)
    Protection_HighThr_Voltage = vf.add_var('Protection__HighThr_Voltage_' + name)
    Protection_HighThr_VoltageFast = vf.add_var('Protection__HighThr_VoltageFast_' + name)
    Protection_LVRT_activation_thr = vf.add_var('Protection__LVRT_activation_thr_' + name)
    Protection_Limit_RoCoF = vf.add_var('Protection__Limit_RoCoF_' + name)
    Protection_LineMonitorType = vf.add_var('Protection__LineMonitorType_' + name)
    Protection_LowThr_Freq1 = vf.add_var('Protection__LowThr_Freq1_' + name)
    Protection_LowThr_Freq2 = vf.add_var('Protection__LowThr_Freq2_' + name)
    Protection_LowThr_FreqFast = vf.add_var('Protection__LowThr_FreqFast_' + name)
    Protection_LowThr_Voltage = vf.add_var('Protection__LowThr_Voltage_' + name)
    Protection_LowThr_VoltageFast = vf.add_var('Protection__LowThr_VoltageFast_' + name)
    Protection_OVRT_activation_thr = vf.add_var('Protection__OVRT_activation_thr_' + name)
    Protection_TOFreq_1 = vf.add_var('Protection__TOFreq_1_' + name)
    Protection_TOFreq_2 = vf.add_var('Protection__TOFreq_2_' + name)
    Protection_TOFreq_Fast = vf.add_var('Protection__TOFreq_Fast_' + name)
    Protection_TOvolt = vf.add_var('Protection__TOvolt_' + name)
    Protection_TOvolt_Fast = vf.add_var('Protection__TOvolt_Fast_' + name)
    Protection_TRoCoF = vf.add_var('Protection__TRoCoF_' + name)
    Protection_TUFreq_1 = vf.add_var('Protection__TUFreq_1_' + name)
    Protection_TUFreq_2 = vf.add_var('Protection__TUFreq_2_' + name)
    Protection_TUFreq_Fast = vf.add_var('Protection__TUFreq_Fast_' + name)
    Protection_TUvolt = vf.add_var('Protection__TUvolt_' + name)
    Protection_TUvolt_Fast = vf.add_var('Protection__TUvolt_Fast_' + name)
    Protection_vLV_1 = vf.add_var('Protection__vLV_1_' + name)
    Protection_vLV_2 = vf.add_var('Protection__vLV_2_' + name)
    Protection_vLV_3 = vf.add_var('Protection__vLV_3_' + name)
    Protection_vLV_4 = vf.add_var('Protection__vLV_4_' + name)
    Protection_vLV_5 = vf.add_var('Protection__vLV_5_' + name)
    Protection_vOV_1 = vf.add_var('Protection__vOV_1_' + name)
    Protection_vOV_2 = vf.add_var('Protection__vOV_2_' + name)
    Protection_vOV_3 = vf.add_var('Protection__vOV_3_' + name)
    Protection_vOV_4 = vf.add_var('Protection__vOV_4_' + name)
    Protection_vOV_5 = vf.add_var('Protection__vOV_5_' + name)
    Q_Vac_droop_kd_V = vf.add_var('Q/Vac droop__kd_V_' + name)
    Q_Vac_droop_kd_V_1 = vf.add_var('Q/Vac droop__kd_V_' + name)
    Q_Vac_droop_ki_Q = vf.add_var('Q/Vac droop__ki_Q_' + name)
    Q_Vac_droop_ki_Q_1 = vf.add_var('Q/Vac droop__ki_Q_' + name)
    Q_Vac_droop_tau_Q_meas = vf.add_var('Q/Vac droop__tau_Q_meas_' + name)
    Q_Vac_droop_tau_V = vf.add_var('Q/Vac droop__tau_V_' + name)
    Q_Vac_droop_tau_V_1 = vf.add_var('Q/Vac droop__tau_V_' + name)
    Smart_Admittance_Imax_pu = vf.add_var('Smart_Admittance__Imax_pu_' + name)
    Smart_Admittance_MaxAuxiliaryVoltage = vf.add_var('Smart_Admittance__MaxAuxiliaryVoltage_' + name)
    Smart_Admittance_MaxTransfoFluxVoltage = vf.add_var('Smart_Admittance__MaxTransfoFluxVoltage_' + name)
    Smart_Admittance_MinAuxiliaryVoltage = vf.add_var('Smart_Admittance__MinAuxiliaryVoltage_' + name)
    Smart_Admittance_PlantEff = vf.add_var('Smart_Admittance__PlantEff_' + name)
    Smart_Admittance_Pmax_dyn = vf.add_var('Smart_Admittance__Pmax_dyn_' + name)
    Smart_Admittance_PmvLim_charge = vf.add_var('Smart_Admittance__PmvLim_charge_' + name)
    Smart_Admittance_PmvLim_crit = vf.add_var('Smart_Admittance__PmvLim_crit_' + name)
    Smart_Admittance_PmvLim_discharge = vf.add_var('Smart_Admittance__PmvLim_discharge_' + name)
    Smart_Admittance_Q_priority_flag = vf.add_var('Smart_Admittance__Q_priority_flag_' + name)
    Smart_Admittance_VdcRef = vf.add_var('Smart_Admittance__VdcRef_' + name)
    Smart_Admittance_f1 = vf.add_var('Smart_Admittance__f1_' + name)
    Smart_Admittance_inv_PlantEff = vf.add_var('Smart_Admittance__inv_PlantEff_' + name)
    Smart_Admittance_inv_Xtrafo_Lout_pu = vf.add_var('Smart_Admittance__inv_Xtrafo_Lout_pu_' + name)
    Smart_Admittance_inv_Xtrafo_pu = vf.add_var('Smart_Admittance__inv_Xtrafo_pu_' + name)
    Smart_Admittance_inv_k_eff_trafo = vf.add_var('Smart_Admittance__inv_k_eff_trafo_' + name)
    Smart_Admittance_k_eff_trafo = vf.add_var('Smart_Admittance__k_eff_trafo_' + name)
    Smart_Admittance_rv = vf.add_var('Smart_Admittance__rv_' + name)
    Smart_Admittance_va_mode = vf.add_var('Smart_Admittance__va_mode_' + name)
    Smart_Admittance_xv = vf.add_var('Smart_Admittance__xv_' + name)
    Synchronization_Loop_H = vf.add_var('Synchronization Loop__H_' + name)
    Synchronization_Loop_H_1 = vf.add_var('Synchronization Loop__H_' + name)
    Synchronization_Loop_KD = vf.add_var('Synchronization Loop__KD_' + name)
    Synchronization_Loop_KD_1 = vf.add_var('Synchronization Loop__KD_' + name)
    Synchronization_Loop_K_fil_meas = vf.add_var('Synchronization Loop__K_fil_meas_' + name)
    Synchronization_Loop_Kdroop_f = vf.add_var('Synchronization Loop__Kdroop_f_' + name)
    Synchronization_Loop_f1 = vf.add_var('Synchronization Loop__f1_' + name)
    Synchronization_Loop_f1_1 = vf.add_var('Synchronization Loop__f1_' + name)
    Synchronization_Loop_tau_P = vf.add_var('Synchronization Loop__tau_P_' + name)
    Synchronization_Loop_tau_P_1 = vf.add_var('Synchronization Loop__tau_P_' + name)
    V_f_control_signals_md_DV = vf.add_var('V&f control signals md__DV_' + name)
    V_f_control_signals_md_Df = vf.add_var('V&f control signals md__Df_' + name)
    V_f_control_signals_md_mV = vf.add_var('V&f control signals md__mV_' + name)
    V_f_control_signals_md_mf = vf.add_var('V&f control signals md__mf_' + name)
    VSC_Measurements_lv = vf.add_var('VSC Measurements__lv_' + name)
    VSC_Measurements_rv = vf.add_var('VSC Measurements__rv_' + name)
    Vac_Events_ROCOF = vf.add_var('Vac_Events__ROCOF_' + name)
    Vac_Events_param_f_ref = vf.add_var('Vac_Events__param_f_ref_' + name)
    Vac_Events_t_ROCOF = vf.add_var('Vac_Events__t_ROCOF_' + name)
    Virtual_Admittance_f1 = vf.add_var('Virtual Admittance__f1_' + name)
    Virtual_Admittance_rv = vf.add_var('Virtual Admittance__rv_' + name)
    Virtual_Admittance_xv = vf.add_var('Virtual Admittance__xv_' + name)
    angle_integrator_f1 = vf.add_var('angle integrator__f1_' + name)
    w1_s_f1 = vf.add_var('w1/s__f1_' + name)

    # --- State Variables ---
    v_1_2H_s_KD_xp = vf.add_var('1/(2H s + KD)__xp_' + name)
    v_1_2Hs_xw = vf.add_var('1/2Hs__xw_' + name)
    v_1_2Hs_xw_2 = vf.add_var('1/2Hs__xw_' + name)
    Current_controller_x1d_cc = vf.add_var('Current controller__x1d_cc_' + name)
    Current_controller_x1q_cc = vf.add_var('Current controller__x1q_cc_' + name)
    Current_controller_x2d_cc = vf.add_var('Current controller__x2d_cc_' + name)
    Current_controller_x2q_cc = vf.add_var('Current controller__x2q_cc_' + name)
    Current_controller_xu1d = vf.add_var('Current controller__xu1d_' + name)
    Current_controller_xu1q = vf.add_var('Current controller__xu1q_' + name)
    PCC_Measurements_xPpcc = vf.add_var('PCC Measurements__xPpcc_' + name)
    PCC_Measurements_xQpcc = vf.add_var('PCC Measurements__xQpcc_' + name)
    PCC_Measurements_xt = vf.add_var('PCC Measurements__xt_' + name)
    PCC_Measurements_xw = vf.add_var('PCC Measurements__xw_' + name)
    Smart_Admittance_x1d_va = vf.add_var('Smart_Admittance__x1d_va_' + name)
    Smart_Admittance_x1q_va = vf.add_var('Smart_Admittance__x1q_va_' + name)
    Smart_Admittance_x2d_va = vf.add_var('Smart_Admittance__x2d_va_' + name)
    Smart_Admittance_x2q_va = vf.add_var('Smart_Admittance__x2q_va_' + name)
    V_f_control_signals_md_RV = vf.add_var('V&f control signals md__RV_' + name)
    V_f_control_signals_md_Rf = vf.add_var('V&f control signals md__Rf_' + name)
    Vac_Events_d_f = vf.add_var('Vac_Events__d_f_' + name)
    Vac_Events_f = vf.add_var('Vac_Events__f_' + name)
    Virtual_Admittance_x1d_va = vf.add_var('Virtual Admittance__x1d_va_' + name)
    Virtual_Admittance_x1q_va = vf.add_var('Virtual Admittance__x1q_va_' + name)
    Virtual_Admittance_x2d_va = vf.add_var('Virtual Admittance__x2d_va_' + name)
    Virtual_Admittance_x2q_va = vf.add_var('Virtual Admittance__x2q_va_' + name)
    angle_integrator_x = vf.add_var('angle integrator__x_' + name)
    w1_s_x = vf.add_var('w1/s__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_2H_s_KD_H_1 = vf.add_var('1/(2H s + KD)__H_' + name)
    v_1_2H_s_KD_Xv_1 = vf.add_var('1/(2H s + KD)__Xv_' + name)
    v_1_2H_s_KD_f1_1 = vf.add_var('1/(2H s + KD)__f1_' + name)
    v_1_2H_s_KD_inc_xp = vf.add_var('1/(2H s + KD)__inc(xp)_' + name)
    v_1_2H_s_KD_xp_1 = vf.add_var('1/(2H s + KD)__xp_' + name)
    v_1_2H_s_KD_zeta_1 = vf.add_var('1/(2H s + KD)__zeta_' + name)
    v_1_2Hs_H_1 = vf.add_var('1/2Hs__H_' + name)
    v_1_2Hs_H_3 = vf.add_var('1/2Hs__H_' + name)
    v_1_2Hs_xw_1 = vf.add_var('1/2Hs__xw_' + name)
    v_1_2Hs_xw_3 = vf.add_var('1/2Hs__xw_' + name)
    Capability_and_limitation_inc_Idneg_cap_max = vf.add_var('Capability_and_limitation__inc(Idneg_cap_max)_' + name)
    Capability_and_limitation_inc_Idneg_cap_min = vf.add_var('Capability_and_limitation__inc(Idneg_cap_min)_' + name)
    Capability_and_limitation_inc_Iqneg_cap_max = vf.add_var('Capability_and_limitation__inc(Iqneg_cap_max)_' + name)
    Capability_and_limitation_inc_Iqneg_cap_min = vf.add_var('Capability_and_limitation__inc(Iqneg_cap_min)_' + name)
    Capability_and_limitation_inc_flag_crit_cond_high = vf.add_var('Capability_and_limitation__inc(flag_crit_cond_high)_' + name)
    Capability_and_limitation_inc_flag_crit_cond_low = vf.add_var('Capability_and_limitation__inc(flag_crit_cond_low)_' + name)
    Capability_block_inc_PMVhigh = vf.add_var('Capability_block__inc(PMVhigh)_' + name)
    Capability_block_inc_PMVlow = vf.add_var('Capability_block__inc(PMVlow)_' + name)
    Capability_block_inc_QMVhigh = vf.add_var('Capability_block__inc(QMVhigh)_' + name)
    Capability_block_inc_QMVlow = vf.add_var('Capability_block__inc(QMVlow)_' + name)
    Capability_block_inc_Qref_in = vf.add_var('Capability_block__inc(Qref_in)_' + name)
    Capability_block_inc_VMVhigh = vf.add_var('Capability_block__inc(VMVhigh)_' + name)
    Capability_block_inc_VMVlow = vf.add_var('Capability_block__inc(VMVlow)_' + name)
    Capability_block_inc_idMVhigh = vf.add_var('Capability_block__inc(idMVhigh)_' + name)
    Capability_block_inc_idMVlow = vf.add_var('Capability_block__inc(idMVlow)_' + name)
    Capability_block_inc_idneg = vf.add_var('Capability_block__inc(idneg)_' + name)
    Capability_block_inc_idpos = vf.add_var('Capability_block__inc(idpos)_' + name)
    Capability_block_inc_iqMVhigh = vf.add_var('Capability_block__inc(iqMVhigh)_' + name)
    Capability_block_inc_iqMVlow = vf.add_var('Capability_block__inc(iqMVlow)_' + name)
    Capability_block_inc_iqneg = vf.add_var('Capability_block__inc(iqneg)_' + name)
    Capability_block_inc_iqpos = vf.add_var('Capability_block__inc(iqpos)_' + name)
    Current_controller_inc_i1d_ref = vf.add_var('Current controller__inc(i1d_ref)_' + name)
    Current_controller_inc_i1q_ref = vf.add_var('Current controller__inc(i1q_ref)_' + name)
    Current_controller_inc_i2d_ref = vf.add_var('Current controller__inc(i2d_ref)_' + name)
    Current_controller_inc_i2q_ref = vf.add_var('Current controller__inc(i2q_ref)_' + name)
    Current_controller_inc_x1d_cc = vf.add_var('Current controller__inc(x1d_cc)_' + name)
    Current_controller_inc_x1q_cc = vf.add_var('Current controller__inc(x1q_cc)_' + name)
    Current_controller_inc_x2d_cc = vf.add_var('Current controller__inc(x2d_cc)_' + name)
    Current_controller_inc_x2q_cc = vf.add_var('Current controller__inc(x2q_cc)_' + name)
    Current_controller_inc_xu1d = vf.add_var('Current controller__inc(xu1d)_' + name)
    Current_controller_inc_xu1q = vf.add_var('Current controller__inc(xu1q)_' + name)
    Current_controller_ki_cc_1 = vf.add_var('Current controller__ki_cc_' + name)
    Current_controller_kp_cc_1 = vf.add_var('Current controller__kp_cc_' + name)
    Current_controller_l_1 = vf.add_var('Current controller__l_' + name)
    Current_controller_u1df = vf.add_var('Current controller__u1df_' + name)
    Current_controller_u1qf = vf.add_var('Current controller__u1qf_' + name)
    Current_controller_x2d_cc_1 = vf.add_var('Current controller__x2d_cc_' + name)
    Current_controller_x2q_cc_1 = vf.add_var('Current controller__x2q_cc_' + name)
    Current_controller_xu1d_1 = vf.add_var('Current controller__xu1d_' + name)
    Current_controller_xu1q_1 = vf.add_var('Current controller__xu1q_' + name)
    DP = vf.add_var('DP_' + name)
    DP_1 = vf.add_var('DP_' + name)
    DP_full = vf.add_var('DP_full_' + name)
    DP_full_1 = vf.add_var('DP_full_' + name)
    Df = vf.add_var('Df_' + name)
    Df_1 = vf.add_var('Df_' + name)
    Dw = vf.add_var('Dw_' + name)
    Dw_1 = vf.add_var('Dw_' + name)
    Events_inc_ROCOF = vf.add_var('Events__inc(ROCOF)_' + name)
    Events_inc_ROCOF_1 = vf.add_var('Events__inc(ROCOF)_' + name)
    Events_inc_phase_jump = vf.add_var('Events__inc(phase_jump)_' + name)
    Events_inc_phase_jump_1 = vf.add_var('Events__inc(phase_jump)_' + name)
    Events_inc_voltage_jump = vf.add_var('Events__inc(voltage_jump)_' + name)
    Events_inc_voltage_jump_1 = vf.add_var('Events__inc(voltage_jump)_' + name)
    Events_param_ROCOF_1 = vf.add_var('Events__param_ROCOF_' + name)
    Events_param_ROCOF_3 = vf.add_var('Events__param_ROCOF_' + name)
    Events_param_phase_jump_1 = vf.add_var('Events__param_phase_jump_' + name)
    Events_param_phase_jump_3 = vf.add_var('Events__param_phase_jump_' + name)
    Events_param_voltage_jump_1 = vf.add_var('Events__param_voltage_jump_' + name)
    Events_param_voltage_jump_3 = vf.add_var('Events__param_voltage_jump_' + name)
    FRT1_flag = vf.add_var('FRT1_flag_' + name)
    FRT1_flag_1 = vf.add_var('FRT1_flag_' + name)
    FRT2_flag = vf.add_var('FRT2_flag_' + name)
    FRT_neg_flag = vf.add_var('FRT_neg_flag_' + name)
    FRT_pos_flag = vf.add_var('FRT_pos_flag_' + name)
    FRT_pos_flag_1 = vf.add_var('FRT_pos_flag_' + name)
    Fault_Detection_inc_FRT1_flag = vf.add_var('Fault Detection__inc(FRT1_flag)_' + name)
    Fault_Detection_inc_FRT1_flag_1 = vf.add_var('Fault Detection__inc(FRT1_flag)_' + name)
    Fault_Detection_inc_FRT2_flag = vf.add_var('Fault Detection__inc(FRT2_flag)_' + name)
    Fault_Detection_inc_FRT2_flag_1 = vf.add_var('Fault Detection__inc(FRT2_flag)_' + name)
    Freq_Alarm = vf.add_var('Freq_Alarm_' + name)
    Freq_Alarm_1 = vf.add_var('Freq_Alarm_' + name)
    Grid_electrical_interface_p_mode_1 = vf.add_var('Grid electrical interface__p_mode_' + name)
    I = vf.add_var('I_' + name)
    I_1 = vf.add_var('I_' + name)
    I_mag = vf.add_var('I_mag_' + name)
    I_mag_1 = vf.add_var('I_mag_' + name)
    I_mag_sq = vf.add_var('I_mag_sq_' + name)
    I_mag_sq_1 = vf.add_var('I_mag_sq_' + name)
    I_neg_avail = vf.add_var('I_neg_avail_' + name)
    I_neg_avail_1 = vf.add_var('I_neg_avail_' + name)
    I_pos_used = vf.add_var('I_pos_used_' + name)
    I_pos_used_1 = vf.add_var('I_pos_used_' + name)
    Ia = vf.add_var('Ia_' + name)
    Ib = vf.add_var('Ib_' + name)
    Ic = vf.add_var('Ic_' + name)
    Id_max = vf.add_var('Id_max_' + name)
    Id_max_1 = vf.add_var('Id_max_' + name)
    Id_min = vf.add_var('Id_min_' + name)
    Idneg_cap_max = vf.add_var('Idneg_cap_max_' + name)
    Idneg_cap_min = vf.add_var('Idneg_cap_min_' + name)
    Imax = vf.add_var('Imax_' + name)
    Imax_1 = vf.add_var('Imax_' + name)
    ImaxCapacitive = vf.add_var('ImaxCapacitive_' + name)
    ImaxCapacitive_1 = vf.add_var('ImaxCapacitive_' + name)
    ImaxInductive = vf.add_var('ImaxInductive_' + name)
    ImaxInductive_1 = vf.add_var('ImaxInductive_' + name)
    Iq_max = vf.add_var('Iq_max_' + name)
    Iq_max_1 = vf.add_var('Iq_max_' + name)
    Iq_min = vf.add_var('Iq_min_' + name)
    Iq_min_1 = vf.add_var('Iq_min_' + name)
    Iqneg_cap_max = vf.add_var('Iqneg_cap_max_' + name)
    Iqneg_cap_min = vf.add_var('Iqneg_cap_min_' + name)
    KD = vf.add_var('KD_' + name)
    KD_1 = vf.add_var('KD_' + name)
    KS = vf.add_var('KS_' + name)
    KS_1 = vf.add_var('KS_' + name)
    LVRT_Alarm = vf.add_var('LVRT_Alarm_' + name)
    LVRT_Alarm_1 = vf.add_var('LVRT_Alarm_' + name)
    LvrtOn = vf.add_var('LvrtOn_' + name)
    LvrtOn_1 = vf.add_var('LvrtOn_' + name)
    MV_voltage_limit_MaxAuxiliaryVoltage_1 = vf.add_var('MV_voltage_limit__MaxAuxiliaryVoltage_' + name)
    MV_voltage_limit_MaxAuxiliaryVoltage_3 = vf.add_var('MV_voltage_limit__MaxAuxiliaryVoltage_' + name)
    MV_voltage_limit_MaxTransfoFluxVoltage_1 = vf.add_var('MV_voltage_limit__MaxTransfoFluxVoltage_' + name)
    MV_voltage_limit_MaxTransfoFluxVoltage_3 = vf.add_var('MV_voltage_limit__MaxTransfoFluxVoltage_' + name)
    MV_voltage_limit_MinAuxiliaryVoltage_1 = vf.add_var('MV_voltage_limit__MinAuxiliaryVoltage_' + name)
    MV_voltage_limit_MinAuxiliaryVoltage_3 = vf.add_var('MV_voltage_limit__MinAuxiliaryVoltage_' + name)
    MV_voltage_limit_cap_reserve = vf.add_var('MV_voltage_limit__cap_reserve_' + name)
    MV_voltage_limit_cap_reserve_1 = vf.add_var('MV_voltage_limit__cap_reserve_' + name)
    MV_voltage_limit_i_ind = vf.add_var('MV_voltage_limit__i_ind_' + name)
    MV_voltage_limit_i_ind_1 = vf.add_var('MV_voltage_limit__i_ind_' + name)
    MV_voltage_limit_inc_ImaxCapacitive = vf.add_var('MV_voltage_limit__inc(ImaxCapacitive)_' + name)
    MV_voltage_limit_inc_ImaxInductive = vf.add_var('MV_voltage_limit__inc(ImaxInductive)_' + name)
    MV_voltage_limit_inc_reactive_reserve = vf.add_var('MV_voltage_limit__inc(reactive_reserve)_' + name)
    MV_voltage_limit_ind_reserve = vf.add_var('MV_voltage_limit__ind_reserve_' + name)
    MV_voltage_limit_ind_reserve_1 = vf.add_var('MV_voltage_limit__ind_reserve_' + name)
    MV_voltage_limit_inv_Xtrafo_Lout_pu_1 = vf.add_var('MV_voltage_limit__inv_Xtrafo_Lout_pu_' + name)
    MV_voltage_limit_inv_Xtrafo_Lout_pu_3 = vf.add_var('MV_voltage_limit__inv_Xtrafo_Lout_pu_' + name)
    MV_voltage_limit_inv_Xtrafo_pu_1 = vf.add_var('MV_voltage_limit__inv_Xtrafo_pu_' + name)
    MV_voltage_limit_inv_Xtrafo_pu_3 = vf.add_var('MV_voltage_limit__inv_Xtrafo_pu_' + name)
    MV_voltage_limit_lim1 = vf.add_var('MV_voltage_limit__lim1_' + name)
    MV_voltage_limit_lim1_1 = vf.add_var('MV_voltage_limit__lim1_' + name)
    MV_voltage_limit_lim2 = vf.add_var('MV_voltage_limit__lim2_' + name)
    MV_voltage_limit_lim2_1 = vf.add_var('MV_voltage_limit__lim2_' + name)
    Master_Trip = vf.add_var('Master_Trip_' + name)
    OR_General = vf.add_var('OR_General_' + name)
    OVRT_Alarm = vf.add_var('OVRT_Alarm_' + name)
    OVRT_Alarm_1 = vf.add_var('OVRT_Alarm_' + name)
    Overload_Flag = vf.add_var('Overload_Flag_' + name)
    OvrtOn = vf.add_var('OvrtOn_' + name)
    OvrtOn_1 = vf.add_var('OvrtOn_' + name)
    P = vf.add_var('P_' + name)
    P_1 = vf.add_var('P_' + name)
    PCC_Measurements_Ppcc_tot = vf.add_var('PCC Measurements__Ppcc_tot_' + name)
    PCC_Measurements_Qpcc_tot = vf.add_var('PCC Measurements__Qpcc_tot_' + name)
    PCC_Measurements_f1_1 = vf.add_var('PCC Measurements__f1_' + name)
    PCC_Measurements_i1i = vf.add_var('PCC Measurements__i1i_' + name)
    PCC_Measurements_i1r = vf.add_var('PCC Measurements__i1r_' + name)
    PCC_Measurements_i2i = vf.add_var('PCC Measurements__i2i_' + name)
    PCC_Measurements_i2r = vf.add_var('PCC Measurements__i2r_' + name)
    PCC_Measurements_inc_Ppcc = vf.add_var('PCC Measurements__inc(Ppcc)_' + name)
    PCC_Measurements_inc_Ppcc_1 = vf.add_var('PCC Measurements__inc(Ppcc)_' + name)
    PCC_Measurements_inc_Qpcc = vf.add_var('PCC Measurements__inc(Qpcc)_' + name)
    PCC_Measurements_inc_Qpcc_1 = vf.add_var('PCC Measurements__inc(Qpcc)_' + name)
    PCC_Measurements_inc_V1pcc = vf.add_var('PCC Measurements__inc(V1pcc)_' + name)
    PCC_Measurements_inc_V1pcc_1 = vf.add_var('PCC Measurements__inc(V1pcc)_' + name)
    PCC_Measurements_inc_V2pcc = vf.add_var('PCC Measurements__inc(V2pcc)_' + name)
    PCC_Measurements_inc_V2pcc_1 = vf.add_var('PCC Measurements__inc(V2pcc)_' + name)
    PCC_Measurements_inc_wpcc = vf.add_var('PCC Measurements__inc(wpcc)_' + name)
    PCC_Measurements_inc_xPpcc = vf.add_var('PCC Measurements__inc(xPpcc)_' + name)
    PCC_Measurements_inc_xQpcc = vf.add_var('PCC Measurements__inc(xQpcc)_' + name)
    PCC_Measurements_inc_xt = vf.add_var('PCC Measurements__inc(xt)_' + name)
    PCC_Measurements_inc_xw = vf.add_var('PCC Measurements__inc(xw)_' + name)
    PCC_Measurements_ki_pll_1 = vf.add_var('PCC Measurements__ki_pll_' + name)
    PCC_Measurements_kp_pll_1 = vf.add_var('PCC Measurements__kp_pll_' + name)
    PCC_Measurements_tau_plot_1 = vf.add_var('PCC Measurements__tau_plot_' + name)
    PCC_Measurements_xPpcc_1 = vf.add_var('PCC Measurements__xPpcc_' + name)
    PCC_Measurements_xQpcc_1 = vf.add_var('PCC Measurements__xQpcc_' + name)
    PCC_Measurements_xt_1 = vf.add_var('PCC Measurements__xt_' + name)
    PCC_Measurements_xw_1 = vf.add_var('PCC Measurements__xw_' + name)
    PMV_capab_high = vf.add_var('PMV_capab_high_' + name)
    PMV_capab_low = vf.add_var('PMV_capab_low_' + name)
    PMVhigh = vf.add_var('PMVhigh_' + name)
    PMVlow = vf.add_var('PMVlow_' + name)
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
    P_elec = vf.add_var('P_elec_' + name)
    P_int = vf.add_var('P_int_' + name)
    P_int_1 = vf.add_var('P_int_' + name)
    Pmeas = vf.add_var('Pmeas_' + name)
    Pmeas_1 = vf.add_var('Pmeas_' + name)
    Pos_Seq_Current_Limiter_inc_FRT2_flag = vf.add_var('Pos. Seq. Current Limiter__inc(FRT2_flag)_' + name)
    Pos_Seq_Current_Limiter_inc_Qref = vf.add_var('Pos. Seq. Current Limiter__inc(Qref)_' + name)
    Pos_Seq_Current_Limiter_inc_i1d_hat = vf.add_var('Pos. Seq. Current Limiter__inc(i1d_hat)_' + name)
    Pos_Seq_Current_Limiter_inc_i1q_hat = vf.add_var('Pos. Seq. Current Limiter__inc(i1q_hat)_' + name)
    Power_VI_limit_PPCChigh = vf.add_var('Power_VI_limit__PPCChigh_' + name)
    Power_VI_limit_PPCChigh_1 = vf.add_var('Power_VI_limit__PPCChigh_' + name)
    Power_VI_limit_PPCClow = vf.add_var('Power_VI_limit__PPCClow_' + name)
    Power_VI_limit_PPCClow_1 = vf.add_var('Power_VI_limit__PPCClow_' + name)
    Power_VI_limit_PlantEff_1 = vf.add_var('Power_VI_limit__PlantEff_' + name)
    Power_VI_limit_PlantEff_3 = vf.add_var('Power_VI_limit__PlantEff_' + name)
    Power_VI_limit_Pmax_dyn_1 = vf.add_var('Power_VI_limit__Pmax_dyn_' + name)
    Power_VI_limit_Pmax_dyn_3 = vf.add_var('Power_VI_limit__Pmax_dyn_' + name)
    Power_VI_limit_PmvLim_charge_1 = vf.add_var('Power_VI_limit__PmvLim_charge_' + name)
    Power_VI_limit_PmvLim_charge_3 = vf.add_var('Power_VI_limit__PmvLim_charge_' + name)
    Power_VI_limit_PmvLim_crit_1 = vf.add_var('Power_VI_limit__PmvLim_crit_' + name)
    Power_VI_limit_PmvLim_crit_3 = vf.add_var('Power_VI_limit__PmvLim_crit_' + name)
    Power_VI_limit_PmvLim_discharge_1 = vf.add_var('Power_VI_limit__PmvLim_discharge_' + name)
    Power_VI_limit_PmvLim_discharge_3 = vf.add_var('Power_VI_limit__PmvLim_discharge_' + name)
    Power_VI_limit_Xtrafo_pu_1 = vf.add_var('Power_VI_limit__Xtrafo_pu_' + name)
    Power_VI_limit_Xtrafo_pu_3 = vf.add_var('Power_VI_limit__Xtrafo_pu_' + name)
    Power_VI_limit_inc_PMVhigh = vf.add_var('Power_VI_limit__inc(PMVhigh)_' + name)
    Power_VI_limit_inc_PMVlow = vf.add_var('Power_VI_limit__inc(PMVlow)_' + name)
    Power_VI_limit_inc_QMVhigh = vf.add_var('Power_VI_limit__inc(QMVhigh)_' + name)
    Power_VI_limit_inc_QMVlow = vf.add_var('Power_VI_limit__inc(QMVlow)_' + name)
    Power_VI_limit_inc_VMVhigh = vf.add_var('Power_VI_limit__inc(VMVhigh)_' + name)
    Power_VI_limit_inc_VMVlow = vf.add_var('Power_VI_limit__inc(VMVlow)_' + name)
    Power_VI_limit_inc_idMVhigh = vf.add_var('Power_VI_limit__inc(idMVhigh)_' + name)
    Power_VI_limit_inc_idMVlow = vf.add_var('Power_VI_limit__inc(idMVlow)_' + name)
    Power_VI_limit_inc_iqMVhigh = vf.add_var('Power_VI_limit__inc(iqMVhigh)_' + name)
    Power_VI_limit_inc_iqMVlow = vf.add_var('Power_VI_limit__inc(iqMVlow)_' + name)
    Power_VI_limit_inv_PlantEff_1 = vf.add_var('Power_VI_limit__inv_PlantEff_' + name)
    Power_VI_limit_inv_PlantEff_3 = vf.add_var('Power_VI_limit__inv_PlantEff_' + name)
    Ppcc = vf.add_var('Ppcc_' + name)
    Ppcc_1 = vf.add_var('Ppcc_' + name)
    Ppcc_raw = vf.add_var('Ppcc_raw_' + name)
    Ppcc_raw_1 = vf.add_var('Ppcc_raw_' + name)
    Pref = vf.add_var('Pref_' + name)
    Protection_DtLVRT_1_1 = vf.add_var('Protection__DtLVRT_1_' + name)
    Protection_DtLVRT_2_1 = vf.add_var('Protection__DtLVRT_2_' + name)
    Protection_DtLVRT_3_1 = vf.add_var('Protection__DtLVRT_3_' + name)
    Protection_DtLVRT_4_1 = vf.add_var('Protection__DtLVRT_4_' + name)
    Protection_DtOVRT_1_1 = vf.add_var('Protection__DtOVRT_1_' + name)
    Protection_DtOVRT_2_1 = vf.add_var('Protection__DtOVRT_2_' + name)
    Protection_DtOVRT_3_1 = vf.add_var('Protection__DtOVRT_3_' + name)
    Protection_DtOVRT_4_1 = vf.add_var('Protection__DtOVRT_4_' + name)
    Protection_HighThr_Freq1_1 = vf.add_var('Protection__HighThr_Freq1_' + name)
    Protection_HighThr_Freq2_1 = vf.add_var('Protection__HighThr_Freq2_' + name)
    Protection_HighThr_FreqFast_1 = vf.add_var('Protection__HighThr_FreqFast_' + name)
    Protection_HighThr_Voltage_1 = vf.add_var('Protection__HighThr_Voltage_' + name)
    Protection_HighThr_VoltageFast_1 = vf.add_var('Protection__HighThr_VoltageFast_' + name)
    Protection_LVRT_activation_thr_1 = vf.add_var('Protection__LVRT_activation_thr_' + name)
    Protection_Limit_RoCoF_1 = vf.add_var('Protection__Limit_RoCoF_' + name)
    Protection_LineMonitorType_1 = vf.add_var('Protection__LineMonitorType_' + name)
    Protection_LowThr_Freq1_1 = vf.add_var('Protection__LowThr_Freq1_' + name)
    Protection_LowThr_Freq2_1 = vf.add_var('Protection__LowThr_Freq2_' + name)
    Protection_LowThr_FreqFast_1 = vf.add_var('Protection__LowThr_FreqFast_' + name)
    Protection_LowThr_Voltage_1 = vf.add_var('Protection__LowThr_Voltage_' + name)
    Protection_LowThr_VoltageFast_1 = vf.add_var('Protection__LowThr_VoltageFast_' + name)
    Protection_OVRT_activation_thr_1 = vf.add_var('Protection__OVRT_activation_thr_' + name)
    Protection_inc_Freq_Alarm = vf.add_var('Protection__inc(Freq_Alarm)_' + name)
    Protection_inc_LVRT_Alarm = vf.add_var('Protection__inc(LVRT_Alarm)_' + name)
    Protection_inc_Master_Trip = vf.add_var('Protection__inc(Master_Trip)_' + name)
    Protection_inc_OVRT_Alarm = vf.add_var('Protection__inc(OVRT_Alarm)_' + name)
    Protection_inc_RoCoF_Alarm = vf.add_var('Protection__inc(RoCoF_Alarm)_' + name)
    Protection_vLV_1_1 = vf.add_var('Protection__vLV_1_' + name)
    Protection_vLV_2_1 = vf.add_var('Protection__vLV_2_' + name)
    Protection_vLV_3_1 = vf.add_var('Protection__vLV_3_' + name)
    Protection_vLV_4_1 = vf.add_var('Protection__vLV_4_' + name)
    Protection_vLV_5_1 = vf.add_var('Protection__vLV_5_' + name)
    Protection_vOV_1_1 = vf.add_var('Protection__vOV_1_' + name)
    Protection_vOV_2_1 = vf.add_var('Protection__vOV_2_' + name)
    Protection_vOV_3_1 = vf.add_var('Protection__vOV_3_' + name)
    Protection_vOV_4_1 = vf.add_var('Protection__vOV_4_' + name)
    Protection_vOV_5_1 = vf.add_var('Protection__vOV_5_' + name)
    Pset = vf.add_var('Pset_' + name)
    Pvsc = vf.add_var('Pvsc_' + name)
    Q = vf.add_var('Q_' + name)
    Q_1 = vf.add_var('Q_' + name)
    Q_Vac_droop_denom_v = vf.add_var('Q/Vac droop__denom_v_' + name)
    Q_Vac_droop_inc_NoMoreNoLess = vf.add_var('Q/Vac droop__inc(NoMoreNoLess)_' + name)
    Q_Vac_droop_inc_Qref = vf.add_var('Q/Vac droop__inc(Qref)_' + name)
    Q_Vac_droop_inc_Qref_1 = vf.add_var('Q/Vac droop__inc(Qref)_' + name)
    Q_Vac_droop_inc_Qref_out = vf.add_var('Q/Vac droop__inc(Qref_out)_' + name)
    Q_Vac_droop_inc_Qref_out_1 = vf.add_var('Q/Vac droop__inc(Qref_out)_' + name)
    Q_Vac_droop_inc_Vf = vf.add_var('Q/Vac droop__inc(Vf)_' + name)
    Q_Vac_droop_inc_Vf_1 = vf.add_var('Q/Vac droop__inc(Vf)_' + name)
    Q_Vac_droop_inc_Vref = vf.add_var('Q/Vac droop__inc(Vref)_' + name)
    Q_Vac_droop_inc_Vref_1 = vf.add_var('Q/Vac droop__inc(Vref)_' + name)
    Q_Vac_droop_inc_e_pre = vf.add_var('Q/Vac droop__inc(e_pre)_' + name)
    Q_Vac_droop_inc_eq = vf.add_var('Q/Vac droop__inc(eq)_' + name)
    Q_Vac_droop_inc_i1q_ref = vf.add_var('Q/Vac droop__inc(i1q_ref)_' + name)
    Q_Vac_droop_inc_rv = vf.add_var('Q/Vac droop__inc(rv)_' + name)
    Q_Vac_droop_inc_xQ_meas_f = vf.add_var('Q/Vac droop__inc(xQ_meas_f)_' + name)
    Q_Vac_droop_inc_xV = vf.add_var('Q/Vac droop__inc(xV)_' + name)
    Q_Vac_droop_inc_xV_1 = vf.add_var('Q/Vac droop__inc(xV)_' + name)
    Q_Vac_droop_inc_xv = vf.add_var('Q/Vac droop__inc(xv)_' + name)
    Q_Vac_droop_val_cos = vf.add_var('Q/Vac droop__val_cos_' + name)
    Q_Vac_droop_val_sin = vf.add_var('Q/Vac droop__val_sin_' + name)
    QMV_capab_high = vf.add_var('QMV_capab_high_' + name)
    QMV_capab_low = vf.add_var('QMV_capab_low_' + name)
    QMVhigh = vf.add_var('QMVhigh_' + name)
    QMVlow = vf.add_var('QMVlow_' + name)
    QPCChigh = vf.add_var('QPCChigh_' + name)
    QPCChigh_1 = vf.add_var('QPCChigh_' + name)
    QPCClow = vf.add_var('QPCClow_' + name)
    QPCClow_1 = vf.add_var('QPCClow_' + name)
    Q_capab_high = vf.add_var('Q_capab_high_' + name)
    Q_capab_low = vf.add_var('Q_capab_low_' + name)
    Q_elec = vf.add_var('Q_elec_' + name)
    Q_int = vf.add_var('Q_int_' + name)
    Q_int_1 = vf.add_var('Q_int_' + name)
    Qlim_cap = vf.add_var('Qlim_cap_' + name)
    Qlim_ind = vf.add_var('Qlim_ind_' + name)
    Qpcc = vf.add_var('Qpcc_' + name)
    Qpcc_1 = vf.add_var('Qpcc_' + name)
    Qpcc_raw = vf.add_var('Qpcc_raw_' + name)
    Qpcc_raw_1 = vf.add_var('Qpcc_raw_' + name)
    Qref = vf.add_var('Qref_' + name)
    Qref_1 = vf.add_var('Qref_' + name)
    Qref1 = vf.add_var('Qref1_' + name)
    Qref_in = vf.add_var('Qref_in_' + name)
    Qref_out = vf.add_var('Qref_out_' + name)
    Qvsc = vf.add_var('Qvsc_' + name)
    Qvsc_1 = vf.add_var('Qvsc_' + name)
    ROCOF = vf.add_var('ROCOF_' + name)
    RoCoF_Alarm = vf.add_var('RoCoF_Alarm_' + name)
    RoCoF_Alarm_1 = vf.add_var('RoCoF_Alarm_' + name)
    RoCoF_measured = vf.add_var('RoCoF_measured_' + name)
    RoCoF_measured_1 = vf.add_var('RoCoF_measured_' + name)
    Sat_Lim_Neg_inc_id_sat_low = vf.add_var('Sat. Lim. Neg.__inc(id_sat_low)_' + name)
    Sat_Lim_Neg_inc_id_sat_low_1 = vf.add_var('Sat. Lim. Neg.__inc(id_sat_low)_' + name)
    Sat_Lim_Neg_inc_id_sat_up = vf.add_var('Sat. Lim. Neg.__inc(id_sat_up)_' + name)
    Sat_Lim_Neg_inc_id_sat_up_1 = vf.add_var('Sat. Lim. Neg.__inc(id_sat_up)_' + name)
    Sat_Lim_Neg_inc_iq_sat_low = vf.add_var('Sat. Lim. Neg.__inc(iq_sat_low)_' + name)
    Sat_Lim_Neg_inc_iq_sat_low_1 = vf.add_var('Sat. Lim. Neg.__inc(iq_sat_low)_' + name)
    Sat_Lim_Neg_inc_iq_sat_up = vf.add_var('Sat. Lim. Neg.__inc(iq_sat_up)_' + name)
    Sat_Lim_Neg_inc_iq_sat_up_1 = vf.add_var('Sat. Lim. Neg.__inc(iq_sat_up)_' + name)
    Sat_Lim_Neg_inc_theta = vf.add_var('Sat. Lim. Neg.__inc(theta)_' + name)
    Sat_Lim_Neg_inc_theta_1 = vf.add_var('Sat. Lim. Neg.__inc(theta)_' + name)
    Sat_Lim_Pos_inc_id_sat_low = vf.add_var('Sat. Lim. Pos.__inc(id_sat_low)_' + name)
    Sat_Lim_Pos_inc_id_sat_low_1 = vf.add_var('Sat. Lim. Pos.__inc(id_sat_low)_' + name)
    Sat_Lim_Pos_inc_id_sat_up = vf.add_var('Sat. Lim. Pos.__inc(id_sat_up)_' + name)
    Sat_Lim_Pos_inc_id_sat_up_1 = vf.add_var('Sat. Lim. Pos.__inc(id_sat_up)_' + name)
    Sat_Lim_Pos_inc_iq_sat_low = vf.add_var('Sat. Lim. Pos.__inc(iq_sat_low)_' + name)
    Sat_Lim_Pos_inc_iq_sat_low_1 = vf.add_var('Sat. Lim. Pos.__inc(iq_sat_low)_' + name)
    Sat_Lim_Pos_inc_iq_sat_up = vf.add_var('Sat. Lim. Pos.__inc(iq_sat_up)_' + name)
    Sat_Lim_Pos_inc_iq_sat_up_1 = vf.add_var('Sat. Lim. Pos.__inc(iq_sat_up)_' + name)
    Saturation_Amplitude_inc_i_sat = vf.add_var('Saturation Amplitude__inc(i_sat)_' + name)
    Saturation_Amplitude_inc_i_sat_1 = vf.add_var('Saturation Amplitude__inc(i_sat)_' + name)
    Smart_Admittance_Imax_pu_1 = vf.add_var('Smart_Admittance__Imax_pu_' + name)
    Smart_Admittance_MaxAuxiliaryVoltage_1 = vf.add_var('Smart_Admittance__MaxAuxiliaryVoltage_' + name)
    Smart_Admittance_MaxTransfoFluxVoltage_1 = vf.add_var('Smart_Admittance__MaxTransfoFluxVoltage_' + name)
    Smart_Admittance_MinAuxiliaryVoltage_1 = vf.add_var('Smart_Admittance__MinAuxiliaryVoltage_' + name)
    Smart_Admittance_PlantEff_1 = vf.add_var('Smart_Admittance__PlantEff_' + name)
    Smart_Admittance_Pmax_dyn_1 = vf.add_var('Smart_Admittance__Pmax_dyn_' + name)
    Smart_Admittance_PmvLim_charge_1 = vf.add_var('Smart_Admittance__PmvLim_charge_' + name)
    Smart_Admittance_PmvLim_crit_1 = vf.add_var('Smart_Admittance__PmvLim_crit_' + name)
    Smart_Admittance_PmvLim_discharge_1 = vf.add_var('Smart_Admittance__PmvLim_discharge_' + name)
    Smart_Admittance_Q_priority_flag_1 = vf.add_var('Smart_Admittance__Q_priority_flag_' + name)
    Smart_Admittance_T_va_ramp = vf.add_var('Smart_Admittance__T_va_ramp_' + name)
    Smart_Admittance_VdcRef_1 = vf.add_var('Smart_Admittance__VdcRef_' + name)
    Smart_Admittance_f1_1 = vf.add_var('Smart_Admittance__f1_' + name)
    Smart_Admittance_inc_FlagLimit = vf.add_var('Smart_Admittance__inc(FlagLimit)_' + name)
    Smart_Admittance_inc_ImaxCapacitive = vf.add_var('Smart_Admittance__inc(ImaxCapacitive)_' + name)
    Smart_Admittance_inc_ImaxInductive = vf.add_var('Smart_Admittance__inc(ImaxInductive)_' + name)
    Smart_Admittance_inc_Overload_Flag = vf.add_var('Smart_Admittance__inc(Overload_Flag)_' + name)
    Smart_Admittance_inc_PPCChigh = vf.add_var('Smart_Admittance__inc(PPCChigh)_' + name)
    Smart_Admittance_inc_PPCClow = vf.add_var('Smart_Admittance__inc(PPCClow)_' + name)
    Smart_Admittance_inc_P_capab_high = vf.add_var('Smart_Admittance__inc(P_capab_high)_' + name)
    Smart_Admittance_inc_P_capab_low = vf.add_var('Smart_Admittance__inc(P_capab_low)_' + name)
    Smart_Admittance_inc_Q_capab_high = vf.add_var('Smart_Admittance__inc(Q_capab_high)_' + name)
    Smart_Admittance_inc_Q_capab_low = vf.add_var('Smart_Admittance__inc(Q_capab_low)_' + name)
    Smart_Admittance_inc_e2d = vf.add_var('Smart_Admittance__inc(e2d)_' + name)
    Smart_Admittance_inc_e2q = vf.add_var('Smart_Admittance__inc(e2q)_' + name)
    Smart_Admittance_inc_i2d_hat = vf.add_var('Smart_Admittance__inc(i2d_hat)_' + name)
    Smart_Admittance_inc_i2q_hat = vf.add_var('Smart_Admittance__inc(i2q_hat)_' + name)
    Smart_Admittance_inc_id2_raw = vf.add_var('Smart_Admittance__inc(id2_raw)_' + name)
    Smart_Admittance_inc_idMVhigh = vf.add_var('Smart_Admittance__inc(idMVhigh)_' + name)
    Smart_Admittance_inc_idMVlow = vf.add_var('Smart_Admittance__inc(idMVlow)_' + name)
    Smart_Admittance_inc_id_neg_sat = vf.add_var('Smart_Admittance__inc(id_neg_sat)_' + name)
    Smart_Admittance_inc_iq2_raw = vf.add_var('Smart_Admittance__inc(iq2_raw)_' + name)
    Smart_Admittance_inc_iq_neg_sat = vf.add_var('Smart_Admittance__inc(iq_neg_sat)_' + name)
    Smart_Admittance_inc_rv_init = vf.add_var('Smart_Admittance__inc(rv_init)_' + name)
    Smart_Admittance_inc_x2d_va = vf.add_var('Smart_Admittance__inc(x2d_va)_' + name)
    Smart_Admittance_inc_x2q_va = vf.add_var('Smart_Admittance__inc(x2q_va)_' + name)
    Smart_Admittance_inc_xv_init = vf.add_var('Smart_Admittance__inc(xv_init)_' + name)
    Smart_Admittance_inv_PlantEff_1 = vf.add_var('Smart_Admittance__inv_PlantEff_' + name)
    Smart_Admittance_inv_Xtrafo_Lout_pu_1 = vf.add_var('Smart_Admittance__inv_Xtrafo_Lout_pu_' + name)
    Smart_Admittance_inv_Xtrafo_pu_1 = vf.add_var('Smart_Admittance__inv_Xtrafo_pu_' + name)
    Smart_Admittance_inv_k_eff_trafo_1 = vf.add_var('Smart_Admittance__inv_k_eff_trafo_' + name)
    Smart_Admittance_k_eff_trafo_1 = vf.add_var('Smart_Admittance__k_eff_trafo_' + name)
    Smart_Admittance_rv_1 = vf.add_var('Smart_Admittance__rv_' + name)
    Smart_Admittance_val_V_safe = vf.add_var('Smart_Admittance__val_V_safe_' + name)
    Smart_Admittance_x1d_va_1 = vf.add_var('Smart_Admittance__x1d_va_' + name)
    Smart_Admittance_x1q_va_1 = vf.add_var('Smart_Admittance__x1q_va_' + name)
    Smart_Admittance_x2d_va_1 = vf.add_var('Smart_Admittance__x2d_va_' + name)
    Smart_Admittance_x2q_va_1 = vf.add_var('Smart_Admittance__x2q_va_' + name)
    Smart_Admittance_xv_1 = vf.add_var('Smart_Admittance__xv_' + name)
    Synchronization_Loop_inc_Pf = vf.add_var('Synchronization Loop__inc(Pf)_' + name)
    Synchronization_Loop_inc_Pref = vf.add_var('Synchronization Loop__inc(Pref)_' + name)
    Synchronization_Loop_inc_Pset = vf.add_var('Synchronization Loop__inc(Pset)_' + name)
    Synchronization_Loop_inc_Pset_1 = vf.add_var('Synchronization Loop__inc(Pset)_' + name)
    Synchronization_Loop_inc_delta = vf.add_var('Synchronization Loop__inc(delta)_' + name)
    Synchronization_Loop_inc_delta_1 = vf.add_var('Synchronization Loop__inc(delta)_' + name)
    Synchronization_Loop_inc_delta_2 = vf.add_var('Synchronization Loop__inc(delta)_' + name)
    Synchronization_Loop_inc_w = vf.add_var('Synchronization Loop__inc(w)_' + name)
    Synchronization_Loop_inc_w_1 = vf.add_var('Synchronization Loop__inc(w)_' + name)
    Synchronization_Loop_inc_w_2 = vf.add_var('Synchronization Loop__inc(w)_' + name)
    Synchronization_Loop_inc_wref = vf.add_var('Synchronization Loop__inc(wref)_' + name)
    Synchronization_Loop_inc_wset = vf.add_var('Synchronization Loop__inc(wset)_' + name)
    Synchronization_Loop_inc_wset_1 = vf.add_var('Synchronization Loop__inc(wset)_' + name)
    Synchronization_Loop_inc_xP = vf.add_var('Synchronization Loop__inc(xP)_' + name)
    Synchronization_Loop_inc_xP_fil = vf.add_var('Synchronization Loop__inc(xP_fil)_' + name)
    Synchronization_Loop_inc_xP_fil_1 = vf.add_var('Synchronization Loop__inc(xP_fil)_' + name)
    Synchronization_Loop_inc_xp_lim = vf.add_var('Synchronization Loop__inc(xp_lim)_' + name)
    Synchronization_Loop_inc_xp_lim_1 = vf.add_var('Synchronization Loop__inc(xp_lim)_' + name)
    Synchronization_Loop_inc_xt = vf.add_var('Synchronization Loop__inc(xt)_' + name)
    Synchronization_Loop_inc_xt_1 = vf.add_var('Synchronization Loop__inc(xt)_' + name)
    Synchronization_Loop_inc_xw = vf.add_var('Synchronization Loop__inc(xw)_' + name)
    Synchronization_Loop_inc_xw_1 = vf.add_var('Synchronization Loop__inc(xw)_' + name)
    Synchronization_Loop_inc_xw_2 = vf.add_var('Synchronization Loop__inc(xw)_' + name)
    Trip_OF_1 = vf.add_var('Trip_OF_1_' + name)
    Trip_OF_2 = vf.add_var('Trip_OF_2_' + name)
    Trip_OF_Fast = vf.add_var('Trip_OF_Fast_' + name)
    Trip_OV = vf.add_var('Trip_OV_' + name)
    Trip_OV_Fast = vf.add_var('Trip_OV_Fast_' + name)
    Trip_UF_1 = vf.add_var('Trip_UF_1_' + name)
    Trip_UF_2 = vf.add_var('Trip_UF_2_' + name)
    Trip_UF_Fast = vf.add_var('Trip_UF_Fast_' + name)
    Trip_UV = vf.add_var('Trip_UV_' + name)
    Trip_UV_Fast = vf.add_var('Trip_UV_Fast_' + name)
    V = vf.add_var('V_' + name)
    V_1 = vf.add_var('V_' + name)
    V_f_control_signals_md_DV_1 = vf.add_var('V&f control signals md__DV_' + name)
    V_f_control_signals_md_Df_1 = vf.add_var('V&f control signals md__Df_' + name)
    V_f_control_signals_md_RV_1 = vf.add_var('V&f control signals md__RV_' + name)
    V_f_control_signals_md_Rf_1 = vf.add_var('V&f control signals md__Rf_' + name)
    V_f_control_signals_md_inc_RV = vf.add_var('V&f control signals md__inc(RV)_' + name)
    V_f_control_signals_md_inc_Rf = vf.add_var('V&f control signals md__inc(Rf)_' + name)
    V_f_control_signals_md_inc_V0 = vf.add_var('V&f control signals md__inc(V0)_' + name)
    V_f_control_signals_md_inc_f0 = vf.add_var('V&f control signals md__inc(f0)_' + name)
    V_f_control_signals_md_mV_1 = vf.add_var('V&f control signals md__mV_' + name)
    V_f_control_signals_md_mf_1 = vf.add_var('V&f control signals md__mf_' + name)
    V0 = vf.add_var('V0_' + name)
    V1pcc = vf.add_var('V1pcc_' + name)
    V1pcc_1 = vf.add_var('V1pcc_' + name)
    V1vsc = vf.add_var('V1vsc_' + name)
    V1vsc_1 = vf.add_var('V1vsc_' + name)
    V2pcc = vf.add_var('V2pcc_' + name)
    V2pcc_1 = vf.add_var('V2pcc_' + name)
    V2vsc = vf.add_var('V2vsc_' + name)
    VMVhigh = vf.add_var('VMVhigh_' + name)
    VMVhigh_1 = vf.add_var('VMVhigh_' + name)
    VMVlow = vf.add_var('VMVlow_' + name)
    VMVlow_1 = vf.add_var('VMVlow_' + name)
    VSC_Measurements_P1pcc = vf.add_var('VSC Measurements__P1pcc_' + name)
    VSC_Measurements_P2pcc = vf.add_var('VSC Measurements__P2pcc_' + name)
    VSC_Measurements_Q1pcc = vf.add_var('VSC Measurements__Q1pcc_' + name)
    VSC_Measurements_Q2pcc = vf.add_var('VSC Measurements__Q2pcc_' + name)
    VSC_Measurements_i1i = vf.add_var('VSC Measurements__i1i_' + name)
    VSC_Measurements_i1r = vf.add_var('VSC Measurements__i1r_' + name)
    VSC_Measurements_i2i = vf.add_var('VSC Measurements__i2i_' + name)
    VSC_Measurements_i2r = vf.add_var('VSC Measurements__i2r_' + name)
    VSC_Measurements_inc_Pvsc = vf.add_var('VSC Measurements__inc(Pvsc)_' + name)
    VSC_Measurements_inc_Qvsc = vf.add_var('VSC Measurements__inc(Qvsc)_' + name)
    VSC_Measurements_inc_V1vsc = vf.add_var('VSC Measurements__inc(V1vsc)_' + name)
    VSC_Measurements_inc_V2vsc = vf.add_var('VSC Measurements__inc(V2vsc)_' + name)
    VSC_Measurements_inc_cosdelta = vf.add_var('VSC Measurements__inc(cosdelta)_' + name)
    VSC_Measurements_inc_i1d = vf.add_var('VSC Measurements__inc(i1d)_' + name)
    VSC_Measurements_inc_i1q = vf.add_var('VSC Measurements__inc(i1q)_' + name)
    VSC_Measurements_inc_i2d = vf.add_var('VSC Measurements__inc(i2d)_' + name)
    VSC_Measurements_inc_i2q = vf.add_var('VSC Measurements__inc(i2q)_' + name)
    VSC_Measurements_inc_sindelta = vf.add_var('VSC Measurements__inc(sindelta)_' + name)
    VSC_Measurements_inc_u1d = vf.add_var('VSC Measurements__inc(u1d)_' + name)
    VSC_Measurements_inc_u1q = vf.add_var('VSC Measurements__inc(u1q)_' + name)
    VSC_Measurements_inc_u2d = vf.add_var('VSC Measurements__inc(u2d)_' + name)
    VSC_Measurements_inc_u2q = vf.add_var('VSC Measurements__inc(u2q)_' + name)
    VSC_Measurements_lv_1 = vf.add_var('VSC Measurements__lv_' + name)
    VSC_Measurements_rv_1 = vf.add_var('VSC Measurements__rv_' + name)
    VSC_abc_to_dq_inc_val_angle_E = vf.add_var('VSC abc_to_dq__inc(val_angle_E)_' + name)
    VSC_abc_to_dq_val_cos = vf.add_var('VSC abc_to_dq__val_cos_' + name)
    VSC_abc_to_dq_val_sin = vf.add_var('VSC abc_to_dq__val_sin_' + name)
    VSC_abc_to_dq_val_u1i = vf.add_var('VSC abc_to_dq__val_u1i_' + name)
    VSC_abc_to_dq_val_u1r = vf.add_var('VSC abc_to_dq__val_u1r_' + name)
    VSC_abc_to_dq_val_u2i = vf.add_var('VSC abc_to_dq__val_u2i_' + name)
    VSC_abc_to_dq_val_u2r = vf.add_var('VSC abc_to_dq__val_u2r_' + name)
    V_max_safe = vf.add_var('V_max_safe_' + name)
    V_max_safe_1 = vf.add_var('V_max_safe_' + name)
    Vac_Events_ROCOF_1 = vf.add_var('Vac_Events__ROCOF_' + name)
    Vac_Events_d_f_1 = vf.add_var('Vac_Events__d_f_' + name)
    Vac_Events_f_1 = vf.add_var('Vac_Events__f_' + name)
    Vac_Events_f0 = vf.add_var('Vac_Events__f0__' + name)
    Vac_Events_inc_d_f = vf.add_var('Vac_Events__inc(d_f)_' + name)
    Vac_Events_inc_dphiu = vf.add_var('Vac_Events__inc(dphiu)_' + name)
    Vac_Events_inc_f = vf.add_var('Vac_Events__inc(f)_' + name)
    Vac_Events_inc_f0 = vf.add_var('Vac_Events__inc(f0)_' + name)
    Vac_Events_inc_fref = vf.add_var('Vac_Events__inc(fref)_' + name)
    Vac_Events_inc_u0 = vf.add_var('Vac_Events__inc(u0)_' + name)
    VdcRef = vf.add_var('VdcRef_' + name)
    VdcRef_1 = vf.add_var('VdcRef_' + name)
    Virtual_Admittance_f1_1 = vf.add_var('Virtual Admittance__f1_' + name)
    Virtual_Admittance_inc_e1d = vf.add_var('Virtual Admittance__inc(e1d)_' + name)
    Virtual_Admittance_inc_e1q = vf.add_var('Virtual Admittance__inc(e1q)_' + name)
    Virtual_Admittance_inc_e2d = vf.add_var('Virtual Admittance__inc(e2d)_' + name)
    Virtual_Admittance_inc_e2q = vf.add_var('Virtual Admittance__inc(e2q)_' + name)
    Virtual_Admittance_inc_x1d_va = vf.add_var('Virtual Admittance__inc(x1d_va)_' + name)
    Virtual_Admittance_inc_x1q_va = vf.add_var('Virtual Admittance__inc(x1q_va)_' + name)
    Virtual_Admittance_inc_x2d_va = vf.add_var('Virtual Admittance__inc(x2d_va)_' + name)
    Virtual_Admittance_inc_x2q_va = vf.add_var('Virtual Admittance__inc(x2q_va)_' + name)
    Virtual_Admittance_rv_1 = vf.add_var('Virtual Admittance__rv_' + name)
    Virtual_Admittance_x1d_va_1 = vf.add_var('Virtual Admittance__x1d_va_' + name)
    Virtual_Admittance_x1q_va_1 = vf.add_var('Virtual Admittance__x1q_va_' + name)
    Virtual_Admittance_x2d_va_1 = vf.add_var('Virtual Admittance__x2d_va_' + name)
    Virtual_Admittance_x2q_va_1 = vf.add_var('Virtual Admittance__x2q_va_' + name)
    Virtual_Admittance_xv_1 = vf.add_var('Virtual Admittance__xv_' + name)
    Vneg = vf.add_var('Vneg_' + name)
    Volt_Alarm = vf.add_var('Volt_Alarm_' + name)
    Volt_Alarm_1 = vf.add_var('Volt_Alarm_' + name)
    Vpcc = vf.add_var('Vpcc_' + name)
    Vpcc_1 = vf.add_var('Vpcc_' + name)
    Vpos = vf.add_var('Vpos_' + name)
    Vref = vf.add_var('Vref_' + name)
    alpha_plot = vf.add_var('alpha_plot_' + name)
    angle_integrator_f1_1 = vf.add_var('angle integrator__f1_' + name)
    angle_integrator_x_1 = vf.add_var('angle integrator__x_' + name)
    cosdelta = vf.add_var('cosdelta_' + name)
    cosdelta_1 = vf.add_var('cosdelta_' + name)
    costheta = vf.add_var('costheta_' + name)
    costheta_1 = vf.add_var('costheta_' + name)
    delta = vf.add_var('delta_' + name)
    delta_1 = vf.add_var('delta_' + name)
    denom = vf.add_var('denom_' + name)
    denom_1 = vf.add_var('denom_' + name)
    dphiu = vf.add_var('dphiu_' + name)
    dq2ab_inc_u1d_ref = vf.add_var('dq2ab__inc(u1d_ref)_' + name)
    dq2ab_inc_u1q_ref = vf.add_var('dq2ab__inc(u1q_ref)_' + name)
    dq2ab_inc_u2d_ref = vf.add_var('dq2ab__inc(u2d_ref)_' + name)
    dq2ab_inc_u2q_ref = vf.add_var('dq2ab__inc(u2q_ref)_' + name)
    e1d = vf.add_var('e1d_' + name)
    e1d_1 = vf.add_var('e1d_' + name)
    e1q = vf.add_var('e1q_' + name)
    e1q_1 = vf.add_var('e1q_' + name)
    e2d = vf.add_var('e2d_' + name)
    e2d_1 = vf.add_var('e2d_' + name)
    e2q = vf.add_var('e2q_' + name)
    e2q_1 = vf.add_var('e2q_' + name)
    e_int_d = vf.add_var('e_int_d_' + name)
    ed = vf.add_var('ed_' + name)
    ed_1 = vf.add_var('ed_' + name)
    en_OF1 = vf.add_var('en_OF1_' + name)
    en_OF2 = vf.add_var('en_OF2_' + name)
    en_OFFast = vf.add_var('en_OFFast_' + name)
    en_OV = vf.add_var('en_OV_' + name)
    en_OVFast = vf.add_var('en_OVFast_' + name)
    en_RoCoF = vf.add_var('en_RoCoF_' + name)
    en_UF1 = vf.add_var('en_UF1_' + name)
    en_UF2 = vf.add_var('en_UF2_' + name)
    en_UFFast = vf.add_var('en_UFFast_' + name)
    en_UV = vf.add_var('en_UV_' + name)
    en_UVFast = vf.add_var('en_UVFast_' + name)
    enable = vf.add_var('enable_' + name)
    enable_1 = vf.add_var('enable_' + name)
    eq = vf.add_var('eq_' + name)
    eq_1 = vf.add_var('eq_' + name)
    err1d = vf.add_var('err1d_' + name)
    err1d_1 = vf.add_var('err1d_' + name)
    err1q = vf.add_var('err1q_' + name)
    err1q_1 = vf.add_var('err1q_' + name)
    err2d = vf.add_var('err2d_' + name)
    err2d_1 = vf.add_var('err2d_' + name)
    err2q = vf.add_var('err2q_' + name)
    err2q_1 = vf.add_var('err2q_' + name)
    f = vf.add_var('f_' + name)
    f_1 = vf.add_var('f_' + name)
    f0 = vf.add_var('f0_' + name)
    f0_1 = vf.add_var('f0_' + name)
    flag_crit_cond_high = vf.add_var('flag_crit_cond_high_' + name)
    flag_crit_cond_low = vf.add_var('flag_crit_cond_low_' + name)
    flag_overload = vf.add_var('flag_overload_' + name)
    fref = vf.add_var('fref_' + name)
    i1d = vf.add_var('i1d_' + name)
    i1d_1 = vf.add_var('i1d_' + name)
    i1d_hat = vf.add_var('i1d_hat_' + name)
    i1d_hat_1 = vf.add_var('i1d_hat_' + name)
    i1d_hat_dyn = vf.add_var('i1d_hat_dyn_' + name)
    i1d_hat_nodyn = vf.add_var('i1d_hat_nodyn_' + name)
    i1d_ref = vf.add_var('i1d_ref_' + name)
    i1d_ref_1 = vf.add_var('i1d_ref_' + name)
    i1i = vf.add_var('i1i_' + name)
    i1i_1 = vf.add_var('i1i_' + name)
    i1q = vf.add_var('i1q_' + name)
    i1q_1 = vf.add_var('i1q_' + name)
    i1q_hat = vf.add_var('i1q_hat_' + name)
    i1q_hat_1 = vf.add_var('i1q_hat_' + name)
    i1q_hat_dyn = vf.add_var('i1q_hat_dyn_' + name)
    i1q_hat_nodyn = vf.add_var('i1q_hat_nodyn_' + name)
    i1q_ref = vf.add_var('i1q_ref_' + name)
    i1q_ref_1 = vf.add_var('i1q_ref_' + name)
    i1r = vf.add_var('i1r_' + name)
    i1r_1 = vf.add_var('i1r_' + name)
    i2_mag = vf.add_var('i2_mag_' + name)
    i2_mag_1 = vf.add_var('i2_mag_' + name)
    i2_sat = vf.add_var('i2_sat_' + name)
    i2d = vf.add_var('i2d_' + name)
    i2d_1 = vf.add_var('i2d_' + name)
    i2d_hat = vf.add_var('i2d_hat_' + name)
    i2d_hat_1 = vf.add_var('i2d_hat_' + name)
    i2d_hat_dyn = vf.add_var('i2d_hat_dyn_' + name)
    i2d_hat_nodyn = vf.add_var('i2d_hat_nodyn_' + name)
    i2d_ref = vf.add_var('i2d_ref_' + name)
    i2d_ref_1 = vf.add_var('i2d_ref_' + name)
    i2i = vf.add_var('i2i_' + name)
    i2i_1 = vf.add_var('i2i_' + name)
    i2q = vf.add_var('i2q_' + name)
    i2q_1 = vf.add_var('i2q_' + name)
    i2q_hat = vf.add_var('i2q_hat_' + name)
    i2q_hat_1 = vf.add_var('i2q_hat_' + name)
    i2q_hat_dyn = vf.add_var('i2q_hat_dyn_' + name)
    i2q_hat_nodyn = vf.add_var('i2q_hat_nodyn_' + name)
    i2q_ref = vf.add_var('i2q_ref_' + name)
    i2q_ref_1 = vf.add_var('i2q_ref_' + name)
    i2r = vf.add_var('i2r_' + name)
    i2r_1 = vf.add_var('i2r_' + name)
    i_cap_raw = vf.add_var('i_cap_raw_' + name)
    i_cap_raw_1 = vf.add_var('i_cap_raw_' + name)
    i_ind_raw = vf.add_var('i_ind_raw_' + name)
    i_ind_raw_1 = vf.add_var('i_ind_raw_' + name)
    i_sat = vf.add_var('i_sat_' + name)
    i_sat_1 = vf.add_var('i_sat_' + name)
    iactpos_sat = vf.add_var('iactpos_sat_' + name)
    iai = vf.add_var('iai_' + name)
    iai_1 = vf.add_var('iai_' + name)
    iar = vf.add_var('iar_' + name)
    iar_1 = vf.add_var('iar_' + name)
    ibi = vf.add_var('ibi_' + name)
    ibi_1 = vf.add_var('ibi_' + name)
    ibr = vf.add_var('ibr_' + name)
    ibr_1 = vf.add_var('ibr_' + name)
    ici = vf.add_var('ici_' + name)
    ici_1 = vf.add_var('ici_' + name)
    icr = vf.add_var('icr_' + name)
    icr_1 = vf.add_var('icr_' + name)
    id = vf.add_var('id_' + name)
    id_1 = vf.add_var('id_' + name)
    id2_raw = vf.add_var('id2_raw_' + name)
    idMVhigh = vf.add_var('idMVhigh_' + name)
    idMVhigh_1 = vf.add_var('idMVhigh_' + name)
    idMVlow = vf.add_var('idMVlow_' + name)
    idMVlow_1 = vf.add_var('idMVlow_' + name)
    id_avail = vf.add_var('id_avail_' + name)
    id_avail_1 = vf.add_var('id_avail_' + name)
    id_bal = vf.add_var('id_bal_' + name)
    id_bal_1 = vf.add_var('id_bal_' + name)
    id_eff = vf.add_var('id_eff_' + name)
    id_eff_1 = vf.add_var('id_eff_' + name)
    id_hat = vf.add_var('id_hat_' + name)
    id_hat_1 = vf.add_var('id_hat_' + name)
    id_lim_rect = vf.add_var('id_lim_rect_' + name)
    id_lim_rect_1 = vf.add_var('id_lim_rect_' + name)
    id_neg_sat = vf.add_var('id_neg_sat_' + name)
    id_neg_sat_1 = vf.add_var('id_neg_sat_' + name)
    id_pos_sat = vf.add_var('id_pos_sat_' + name)
    id_pos_sat_1 = vf.add_var('id_pos_sat_' + name)
    id_prio = vf.add_var('id_prio_' + name)
    id_prio_1 = vf.add_var('id_prio_' + name)
    id_raw = vf.add_var('id_raw_' + name)
    id_ref = vf.add_var('id_ref_' + name)
    id_ref_1 = vf.add_var('id_ref_' + name)
    id_sat_low = vf.add_var('id_sat_low_' + name)
    id_sat_up = vf.add_var('id_sat_up_' + name)
    id_sat_up_1 = vf.add_var('id_sat_up_' + name)
    id_unsat = vf.add_var('id_unsat_' + name)
    id_unsat_1 = vf.add_var('id_unsat_' + name)
    idneg = vf.add_var('idneg_' + name)
    idpos = vf.add_var('idpos_' + name)
    idpos_sat = vf.add_var('idpos_sat_' + name)
    imag_inst = vf.add_var('imag_inst_' + name)
    inv_V1vsc = vf.add_var('inv_V1vsc_' + name)
    inv_V1vsc_1 = vf.add_var('inv_V1vsc_' + name)
    inv_Vpcc = vf.add_var('inv_Vpcc_' + name)
    inv_Vpcc_1 = vf.add_var('inv_Vpcc_' + name)
    iq = vf.add_var('iq_' + name)
    iq_1 = vf.add_var('iq_' + name)
    iq2_raw = vf.add_var('iq2_raw_' + name)
    iqMVhigh = vf.add_var('iqMVhigh_' + name)
    iqMVhigh_1 = vf.add_var('iqMVhigh_' + name)
    iqMVlow = vf.add_var('iqMVlow_' + name)
    iqMVlow_1 = vf.add_var('iqMVlow_' + name)
    iq_bal = vf.add_var('iq_bal_' + name)
    iq_bal_1 = vf.add_var('iq_bal_' + name)
    iq_eff = vf.add_var('iq_eff_' + name)
    iq_eff_1 = vf.add_var('iq_eff_' + name)
    iq_hat = vf.add_var('iq_hat_' + name)
    iq_hat_1 = vf.add_var('iq_hat_' + name)
    iq_lim_rect = vf.add_var('iq_lim_rect_' + name)
    iq_lim_rect_1 = vf.add_var('iq_lim_rect_' + name)
    iq_neg_sat = vf.add_var('iq_neg_sat_' + name)
    iq_neg_sat_1 = vf.add_var('iq_neg_sat_' + name)
    iq_pos_sat = vf.add_var('iq_pos_sat_' + name)
    iq_pos_sat_1 = vf.add_var('iq_pos_sat_' + name)
    iq_pre = vf.add_var('iq_pre_' + name)
    iq_pre_1 = vf.add_var('iq_pre_' + name)
    iq_prio = vf.add_var('iq_prio_' + name)
    iq_prio_1 = vf.add_var('iq_prio_' + name)
    iq_raw = vf.add_var('iq_raw_' + name)
    iq_ref = vf.add_var('iq_ref_' + name)
    iq_ref_1 = vf.add_var('iq_ref_' + name)
    iq_ref_in = vf.add_var('iq_ref_in_' + name)
    iq_sat_low = vf.add_var('iq_sat_low_' + name)
    iq_sat_up = vf.add_var('iq_sat_up_' + name)
    iq_sat_up_1 = vf.add_var('iq_sat_up_' + name)
    iq_unsat = vf.add_var('iq_unsat_' + name)
    iq_unsat_1 = vf.add_var('iq_unsat_' + name)
    iqneg = vf.add_var('iqneg_' + name)
    iqpos = vf.add_var('iqpos_' + name)
    iqpos_sat = vf.add_var('iqpos_sat_' + name)
    ireactpos_sat = vf.add_var('ireactpos_sat_' + name)
    lim1 = vf.add_var('lim1_' + name)
    lim1_1 = vf.add_var('lim1_' + name)
    lim2 = vf.add_var('lim2_' + name)
    lim2_1 = vf.add_var('lim2_' + name)
    limit_Ipos_Id_max_0 = vf.add_var('limit_Ipos__Id_max_0_' + name)
    limit_Ipos_Id_max_0_1 = vf.add_var('limit_Ipos__Id_max_0_' + name)
    limit_Ipos_Iq_max_1 = vf.add_var('limit_Ipos__Iq_max_1_' + name)
    limit_Ipos_Iq_max_1_1 = vf.add_var('limit_Ipos__Iq_max_1_' + name)
    limit_Ipos_Iq_min_1 = vf.add_var('limit_Ipos__Iq_min_1_' + name)
    limit_Ipos_Iq_min_1_1 = vf.add_var('limit_Ipos__Iq_min_1_' + name)
    limit_Ipos_Ires = vf.add_var('limit_Ipos__Ires__' + name)
    limit_Ipos_Ires_1 = vf.add_var('limit_Ipos__Ires__' + name)
    limit_Ipos_inc_Id_max = vf.add_var('limit_Ipos__inc(Id_max)_' + name)
    limit_Ipos_inc_Id_min = vf.add_var('limit_Ipos__inc(Id_min)_' + name)
    limit_Ipos_inc_Iq_max = vf.add_var('limit_Ipos__inc(Iq_max)_' + name)
    limit_Ipos_inc_Iq_min = vf.add_var('limit_Ipos__inc(Iq_min)_' + name)
    limit_Ipos_mode = vf.add_var('limit_Ipos__mode_' + name)
    limit_Ipos_theta0 = vf.add_var('limit_Ipos__theta0_' + name)
    phase_jump = vf.add_var('phase_jump_' + name)
    phase_jump_1 = vf.add_var('phase_jump_' + name)
    reactive_reserve = vf.add_var('reactive_reserve_' + name)
    reactive_reserve_1 = vf.add_var('reactive_reserve_' + name)
    rv_init = vf.add_var('rv_init_' + name)
    rv_init_1 = vf.add_var('rv_init_' + name)
    safe_V1vsc = vf.add_var('safe_V1vsc_' + name)
    safe_V1vsc_1 = vf.add_var('safe_V1vsc_' + name)
    scale_bal = vf.add_var('scale_bal_' + name)
    scale_bal_1 = vf.add_var('scale_bal_' + name)
    scale_final = vf.add_var('scale_final_' + name)
    scale_final_1 = vf.add_var('scale_final_' + name)
    scale_neg = vf.add_var('scale_neg_' + name)
    scale_neg_1 = vf.add_var('scale_neg_' + name)
    simulateCapBlock_inc_PMV_capab_high = vf.add_var('simulateCapBlock__inc(PMV_capab_high)_' + name)
    simulateCapBlock_inc_PMV_capab_low = vf.add_var('simulateCapBlock__inc(PMV_capab_low)_' + name)
    simulateCapBlock_inc_QMV_capab_high = vf.add_var('simulateCapBlock__inc(QMV_capab_high)_' + name)
    simulateCapBlock_inc_QMV_capab_low = vf.add_var('simulateCapBlock__inc(QMV_capab_low)_' + name)
    simulateCapBlock_inc_id_neg_sat = vf.add_var('simulateCapBlock__inc(id_neg_sat)_' + name)
    simulateCapBlock_inc_id_pos_sat = vf.add_var('simulateCapBlock__inc(id_pos_sat)_' + name)
    simulateCapBlock_inc_iq_neg_sat = vf.add_var('simulateCapBlock__inc(iq_neg_sat)_' + name)
    simulateCapBlock_inc_iq_pos_sat = vf.add_var('simulateCapBlock__inc(iq_pos_sat)_' + name)
    sindelta = vf.add_var('sindelta_' + name)
    sindelta_1 = vf.add_var('sindelta_' + name)
    sintheta = vf.add_var('sintheta_' + name)
    sintheta_1 = vf.add_var('sintheta_' + name)
    t = vf.add_var('t_' + name)
    t_LV = vf.add_var('t_LV_' + name)
    t_OV = vf.add_var('t_OV_' + name)
    t_elapsed_LV = vf.add_var('t_elapsed_LV_' + name)
    t_elapsed_LV_1 = vf.add_var('t_elapsed_LV_' + name)
    t_elapsed_OV = vf.add_var('t_elapsed_OV_' + name)
    t_elapsed_OV_1 = vf.add_var('t_elapsed_OV_' + name)
    tau_plot_eff = vf.add_var('tau_plot_eff_' + name)
    tau_plot_eff_1 = vf.add_var('tau_plot_eff_' + name)
    theta = vf.add_var('theta_' + name)
    theta_1 = vf.add_var('theta_' + name)
    u0 = vf.add_var('u0_' + name)
    u1d = vf.add_var('u1d_' + name)
    u1d_1 = vf.add_var('u1d_' + name)
    u1d_ref = vf.add_var('u1d_ref_' + name)
    u1d_ref_1 = vf.add_var('u1d_ref_' + name)
    u1i = vf.add_var('u1i_' + name)
    u1i_1 = vf.add_var('u1i_' + name)
    u1i_ref = vf.add_var('u1i_ref_' + name)
    u1i_ref_1 = vf.add_var('u1i_ref_' + name)
    u1q = vf.add_var('u1q_' + name)
    u1q_1 = vf.add_var('u1q_' + name)
    u1q_ref = vf.add_var('u1q_ref_' + name)
    u1q_ref_1 = vf.add_var('u1q_ref_' + name)
    u1r = vf.add_var('u1r_' + name)
    u1r_1 = vf.add_var('u1r_' + name)
    u1r_ref = vf.add_var('u1r_ref_' + name)
    u1r_ref_1 = vf.add_var('u1r_ref_' + name)
    u2d = vf.add_var('u2d_' + name)
    u2d_1 = vf.add_var('u2d_' + name)
    u2d_dif = vf.add_var('u2d_dif_' + name)
    u2d_dif_1 = vf.add_var('u2d_dif_' + name)
    u2d_ref = vf.add_var('u2d_ref_' + name)
    u2d_ref_1 = vf.add_var('u2d_ref_' + name)
    u2i = vf.add_var('u2i_' + name)
    u2i_1 = vf.add_var('u2i_' + name)
    u2i_ref = vf.add_var('u2i_ref_' + name)
    u2i_ref_1 = vf.add_var('u2i_ref_' + name)
    u2q = vf.add_var('u2q_' + name)
    u2q_1 = vf.add_var('u2q_' + name)
    u2q_dif = vf.add_var('u2q_dif_' + name)
    u2q_dif_1 = vf.add_var('u2q_dif_' + name)
    u2q_ref = vf.add_var('u2q_ref_' + name)
    u2q_ref_1 = vf.add_var('u2q_ref_' + name)
    u2r = vf.add_var('u2r_' + name)
    u2r_1 = vf.add_var('u2r_' + name)
    u2r_ref = vf.add_var('u2r_ref_' + name)
    u2r_ref_1 = vf.add_var('u2r_ref_' + name)
    u_3Ph = vf.add_var('u_3Ph_' + name)
    u_3Ph_1 = vf.add_var('u_3Ph_' + name)
    u_MaxVLL = vf.add_var('u_MaxVLL_' + name)
    u_MaxVLL_1 = vf.add_var('u_MaxVLL_' + name)
    u_eval = vf.add_var('u_eval_' + name)
    u_eval_1 = vf.add_var('u_eval_' + name)
    uai = vf.add_var('uai_' + name)
    uai_1 = vf.add_var('uai_' + name)
    uar = vf.add_var('uar_' + name)
    uar_1 = vf.add_var('uar_' + name)
    ubi = vf.add_var('ubi_' + name)
    ubi_1 = vf.add_var('ubi_' + name)
    ubr = vf.add_var('ubr_' + name)
    ubr_1 = vf.add_var('ubr_' + name)
    uci = vf.add_var('uci_' + name)
    uci_1 = vf.add_var('uci_' + name)
    ucr = vf.add_var('ucr_' + name)
    ucr_1 = vf.add_var('ucr_' + name)
    ud_dif = vf.add_var('ud_dif_' + name)
    ud_dif_1 = vf.add_var('ud_dif_' + name)
    uq_dif = vf.add_var('uq_dif_' + name)
    uq_dif_1 = vf.add_var('uq_dif_' + name)
    use_prio_Q = vf.add_var('use_prio_Q_' + name)
    use_prio_Q_1 = vf.add_var('use_prio_Q_' + name)
    vLVRT_trip_lim = vf.add_var('vLVRT_trip_lim_' + name)
    vLVRT_trip_lim_1 = vf.add_var('vLVRT_trip_lim_' + name)
    vMV_pos_mode = vf.add_var('vMV_pos_mode_' + name)
    vMV_pos_mode_1 = vf.add_var('vMV_pos_mode_' + name)
    vMV_pos_mode1 = vf.add_var('vMV_pos_mode1_' + name)
    vOVRT_trip_lim = vf.add_var('vOVRT_trip_lim_' + name)
    vOVRT_trip_lim_1 = vf.add_var('vOVRT_trip_lim_' + name)
    vPCC_pos_mag = vf.add_var('vPCC_pos_mag_' + name)
    val_angle_E = vf.add_var('val_angle_E_' + name)
    val_angle_E_1 = vf.add_var('val_angle_E_' + name)
    vdneg = vf.add_var('vdneg_' + name)
    vdpos = vf.add_var('vdpos_' + name)
    viol_P = vf.add_var('viol_P_' + name)
    viol_Q = vf.add_var('viol_Q_' + name)
    voltage_jump = vf.add_var('voltage_jump_' + name)
    voltage_jump_1 = vf.add_var('voltage_jump_' + name)
    vqneg = vf.add_var('vqneg_' + name)
    vqpos = vf.add_var('vqpos_' + name)
    w = vf.add_var('w_' + name)
    w_1 = vf.add_var('w_' + name)
    w1 = vf.add_var('w1_' + name)
    w1_1 = vf.add_var('w1_' + name)
    w1_s_f1_1 = vf.add_var('w1/s__f1_' + name)
    w1_s_inc_x = vf.add_var('w1/s__inc(x)_' + name)
    w1_s_x_1 = vf.add_var('w1/s__x_' + name)
    w_r = vf.add_var('w_r_' + name)
    w_r_1 = vf.add_var('w_r_' + name)
    wn = vf.add_var('wn_' + name)
    wn_1 = vf.add_var('wn_' + name)
    wpcc = vf.add_var('wpcc_' + name)
    wref = vf.add_var('wref_' + name)
    wset = vf.add_var('wset_' + name)
    wset_1 = vf.add_var('wset_' + name)
    xv_init = vf.add_var('xv_init_' + name)
    xv_init_1 = vf.add_var('xv_init_' + name)

    # --- Derivative Variables ---
    d_1_2H_s_KD_xp = vf.add_diff_var('d_1/(2H s + KD)__xp_' + name, base_var=v_1_2H_s_KD_xp)
    d_1_2Hs_xw = vf.add_diff_var('d_1/2Hs__xw_' + name, base_var=v_1_2Hs_xw)
    d_1_2Hs_xw_1 = vf.add_diff_var('d_1/2Hs__xw_' + name, base_var=v_1_2Hs_xw_2)
    d_Current_controller_x1d_cc = vf.add_diff_var('d_Current controller__x1d_cc_' + name, base_var=Current_controller_x1d_cc)
    d_Current_controller_x1q_cc = vf.add_diff_var('d_Current controller__x1q_cc_' + name, base_var=Current_controller_x1q_cc)
    d_Current_controller_x2d_cc = vf.add_diff_var('d_Current controller__x2d_cc_' + name, base_var=Current_controller_x2d_cc)
    d_Current_controller_x2q_cc = vf.add_diff_var('d_Current controller__x2q_cc_' + name, base_var=Current_controller_x2q_cc)
    d_Current_controller_xu1d = vf.add_diff_var('d_Current controller__xu1d_' + name, base_var=Current_controller_xu1d)
    d_Current_controller_xu1q = vf.add_diff_var('d_Current controller__xu1q_' + name, base_var=Current_controller_xu1q)
    d_PCC_Measurements_xPpcc = vf.add_diff_var('d_PCC Measurements__xPpcc_' + name, base_var=PCC_Measurements_xPpcc)
    d_PCC_Measurements_xQpcc = vf.add_diff_var('d_PCC Measurements__xQpcc_' + name, base_var=PCC_Measurements_xQpcc)
    d_PCC_Measurements_xt = vf.add_diff_var('d_PCC Measurements__xt_' + name, base_var=PCC_Measurements_xt)
    d_PCC_Measurements_xw = vf.add_diff_var('d_PCC Measurements__xw_' + name, base_var=PCC_Measurements_xw)
    d_Smart_Admittance_x1d_va = vf.add_diff_var('d_Smart_Admittance__x1d_va_' + name, base_var=Smart_Admittance_x1d_va)
    d_Smart_Admittance_x1q_va = vf.add_diff_var('d_Smart_Admittance__x1q_va_' + name, base_var=Smart_Admittance_x1q_va)
    d_Smart_Admittance_x2d_va = vf.add_diff_var('d_Smart_Admittance__x2d_va_' + name, base_var=Smart_Admittance_x2d_va)
    d_Smart_Admittance_x2q_va = vf.add_diff_var('d_Smart_Admittance__x2q_va_' + name, base_var=Smart_Admittance_x2q_va)
    d_V_f_control_signals_md_RV = vf.add_diff_var('d_V&f control signals md__RV_' + name, base_var=V_f_control_signals_md_RV)
    d_V_f_control_signals_md_Rf = vf.add_diff_var('d_V&f control signals md__Rf_' + name, base_var=V_f_control_signals_md_Rf)
    d_Vac_Events_d_f = vf.add_diff_var('d_Vac_Events__d_f_' + name, base_var=Vac_Events_d_f)
    d_Vac_Events_f = vf.add_diff_var('d_Vac_Events__f_' + name, base_var=Vac_Events_f)
    d_Virtual_Admittance_x1d_va = vf.add_diff_var('d_Virtual Admittance__x1d_va_' + name, base_var=Virtual_Admittance_x1d_va)
    d_Virtual_Admittance_x1q_va = vf.add_diff_var('d_Virtual Admittance__x1q_va_' + name, base_var=Virtual_Admittance_x1q_va)
    d_Virtual_Admittance_x2d_va = vf.add_diff_var('d_Virtual Admittance__x2d_va_' + name, base_var=Virtual_Admittance_x2d_va)
    d_Virtual_Admittance_x2q_va = vf.add_diff_var('d_Virtual Admittance__x2q_va_' + name, base_var=Virtual_Admittance_x2q_va)
    d_angle_integrator_x = vf.add_diff_var('d_angle integrator__x_' + name, base_var=angle_integrator_x)
    d_w1_s_x = vf.add_diff_var('d_w1/s__x_' + name, base_var=w1_s_x)

    # --- Block Assembly ---
    v_1_2H_s_KD = Block(
        state_eqs=[
            (((((-KD_1) / 2.0) / v_1_2H_s_KD_H_1) * Df_1) + (((1.0 / 2.0) / v_1_2H_s_KD_H_1) * DP_1)),
        ],
        state_vars=[v_1_2H_s_KD_xp],
        algebraic_eqs=[
            (w1 - ((2.0 * 3.141592653589793) * v_1_2H_s_KD_f1_1)),
            (KS - (1.0 / v_1_2H_s_KD_Xv_1)),
            (wn - sym.sqrt((((w1_1 * KS_1) / 2.0) / v_1_2H_s_KD_H_1))),
            (KD - ((((2.0 * v_1_2H_s_KD_zeta_1) * wn_1) * 2.0) * v_1_2H_s_KD_H_1)),
            (Df - v_1_2H_s_KD_xp_1),
            (v_1_2H_s_KD_inc_xp - Df_1),
        ],
        algebraic_vars=[w1, KS, wn, KD, Df, v_1_2H_s_KD_inc_xp],
        in_vars=[DP],
        out_vars=[Df],
        name='1/(2H s + KD)'
    )
    v_1_2H_s_KD.diff_vars = [d_1_2H_s_KD_xp]
    v_1_2H_s_KD.event_dict = {
        v_1_2H_s_KD_H: vf.add_const(None, name='H'),
        v_1_2H_s_KD_zeta: vf.add_const(None, name='zeta'),
        v_1_2H_s_KD_f1: vf.add_const(None, name='f1'),
        v_1_2H_s_KD_Xv: vf.add_const(None, name='Xv'),
    }

    v_1_2Hs = Block(
        state_eqs=[
            ((1.0 / (2.0 * v_1_2Hs_H_1)) * DP_full_1),
        ],
        state_vars=[v_1_2Hs_xw],
        algebraic_eqs=[
            (Dw - v_1_2Hs_xw_1),
        ],
        algebraic_vars=[Dw],
        in_vars=[DP_full],
        out_vars=[Dw],
        name='1/2Hs'
    )
    v_1_2Hs.diff_vars = [d_1_2Hs_xw]
    v_1_2Hs.event_dict = {
        v_1_2Hs_H: vf.add_const(None, name='H'),
    }

    v_1_2Hs = Block(
        state_eqs=[
            ((1.0 / (2.0 * v_1_2Hs_H_3)) * DP_1),
        ],
        state_vars=[v_1_2Hs_xw_2],
        algebraic_eqs=[
            (Dw - v_1_2Hs_xw_3),
        ],
        algebraic_vars=[Dw],
        in_vars=[DP],
        out_vars=[Dw],
        name='1/2Hs'
    )
    v_1_2Hs.diff_vars = [d_1_2Hs_xw_1]
    v_1_2Hs.event_dict = {
        v_1_2Hs_H_2: vf.add_const(None, name='H'),
    }

    Capability_and_limitation = Block(
        in_vars=[Vpcc, VdcRef, vMV_pos_mode1, Qlim_cap, Qlim_ind, Imax, idpos, iqpos, idneg, iqneg, idpos_sat, iqpos_sat, FRT_neg_flag, FRT_pos_flag, Qref1],
        out_vars=[idMVhigh, PMVhigh, idMVlow, PMVlow, iqMVlow, iqMVhigh, VMVhigh, VMVlow, QMVhigh, QMVlow, Idneg_cap_max, Iqneg_cap_max, Idneg_cap_min, Iqneg_cap_min, flag_crit_cond_high, flag_crit_cond_low],
        name='Capability_and_limitation'
    )
    Capability_and_limitation.event_dict = {
        Capability_and_limitation_inv_Xtrafo_Lout_pu: vf.add_const(None, name='inv_Xtrafo_Lout_pu'),
        Capability_and_limitation_MaxAuxiliaryVoltage: vf.add_const(None, name='MaxAuxiliaryVoltage'),
        Capability_and_limitation_MaxTransfoFluxVoltage: vf.add_const(None, name='MaxTransfoFluxVoltage'),
        Capability_and_limitation_inv_Xtrafo_pu: vf.add_const(None, name='inv_Xtrafo_pu'),
        Capability_and_limitation_MinAuxiliaryVoltage: vf.add_const(None, name='MinAuxiliaryVoltage'),
        Capability_and_limitation_PmvLim_crit: vf.add_const(None, name='PmvLim_crit'),
        Capability_and_limitation_PmvLim_discharge: vf.add_const(None, name='PmvLim_discharge'),
        Capability_and_limitation_Pmax_dyn: vf.add_const(None, name='Pmax_dyn'),
        Capability_and_limitation_PmvLim_charge: vf.add_const(None, name='PmvLim_charge'),
        Capability_and_limitation_PlantEff: vf.add_const(None, name='PlantEff'),
        Capability_and_limitation_inv_PlantEff: vf.add_const(None, name='inv_PlantEff'),
        Capability_and_limitation_inv_k_eff_trafo: vf.add_const(None, name='inv_k_eff_trafo'),
        Capability_and_limitation_k_eff_trafo: vf.add_const(None, name='k_eff_trafo'),
        Capability_and_limitation_Xtrafo_pu: vf.add_const(None, name='Xtrafo_pu'),
    }

    Capability_and_limitation = Block(
        algebraic_eqs=[
            (Capability_and_limitation_inc_Idneg_cap_max - 0.0),
            (Capability_and_limitation_inc_Idneg_cap_min - 0.0),
            (Capability_and_limitation_inc_Iqneg_cap_max - 0.0),
            (Capability_and_limitation_inc_Iqneg_cap_min - 0.0),
            (Capability_and_limitation_inc_flag_crit_cond_high - 0.0),
            (Capability_and_limitation_inc_flag_crit_cond_low - 0.0),
        ],
        algebraic_vars=[Capability_and_limitation_inc_Idneg_cap_max, Capability_and_limitation_inc_Idneg_cap_min, Capability_and_limitation_inc_Iqneg_cap_max, Capability_and_limitation_inc_Iqneg_cap_min, Capability_and_limitation_inc_flag_crit_cond_high, Capability_and_limitation_inc_flag_crit_cond_low],
        in_vars=[Vpcc, VdcRef, vMV_pos_mode1, Qlim_cap, Qlim_ind, Imax, idpos, iqpos, idneg, iqneg, idpos_sat, iqpos_sat, FRT_neg_flag, FRT_pos_flag, Qref1],
        out_vars=[idMVhigh, PMVhigh, idMVlow, PMVlow, iqMVlow, iqMVhigh, VMVhigh, VMVlow, QMVhigh, QMVlow, Idneg_cap_max, Iqneg_cap_max, Idneg_cap_min, Iqneg_cap_min, flag_crit_cond_high, flag_crit_cond_low],
        name='Capability_and_limitation'
    )
    Capability_and_limitation.event_dict = {
        Capability_and_limitation_inv_Xtrafo_Lout_pu_1: vf.add_const(None, name='inv_Xtrafo_Lout_pu'),
        Capability_and_limitation_MaxAuxiliaryVoltage_1: vf.add_const(None, name='MaxAuxiliaryVoltage'),
        Capability_and_limitation_MaxTransfoFluxVoltage_1: vf.add_const(None, name='MaxTransfoFluxVoltage'),
        Capability_and_limitation_inv_Xtrafo_pu_1: vf.add_const(None, name='inv_Xtrafo_pu'),
        Capability_and_limitation_MinAuxiliaryVoltage_1: vf.add_const(None, name='MinAuxiliaryVoltage'),
        Capability_and_limitation_PmvLim_crit_1: vf.add_const(None, name='PmvLim_crit'),
        Capability_and_limitation_PmvLim_discharge_1: vf.add_const(None, name='PmvLim_discharge'),
        Capability_and_limitation_Pmax_dyn_1: vf.add_const(None, name='Pmax_dyn'),
        Capability_and_limitation_PmvLim_charge_1: vf.add_const(None, name='PmvLim_charge'),
        Capability_and_limitation_PlantEff_1: vf.add_const(None, name='PlantEff'),
        Capability_and_limitation_inv_PlantEff_1: vf.add_const(None, name='inv_PlantEff'),
        Capability_and_limitation_inv_k_eff_trafo_1: vf.add_const(None, name='inv_k_eff_trafo'),
        Capability_and_limitation_k_eff_trafo_1: vf.add_const(None, name='k_eff_trafo'),
        Capability_and_limitation_Xtrafo_pu_1: vf.add_const(None, name='Xtrafo_pu'),
    }

    Capability_block = Block(
        algebraic_eqs=[
            (Capability_block_inc_idpos - iactpos_sat),
            (Capability_block_inc_iqpos - ireactpos_sat),
            (Capability_block_inc_idneg - 0.0),
            (Capability_block_inc_iqneg - 0.0),
            (Capability_block_inc_Qref_in - 0.0),
        ],
        algebraic_vars=[Capability_block_inc_idpos, Capability_block_inc_iqpos, Capability_block_inc_idneg, Capability_block_inc_iqneg, Capability_block_inc_Qref_in],
        in_vars=[idpos, iqpos, vdpos, vqpos, idneg, iqneg, vdneg, vqneg, vPCC_pos_mag, FRT_pos_flag, FRT_neg_flag, Qlim_cap, Qlim_ind, Qref_in],
        out_vars=[QMV_capab_high, QMV_capab_low, PMV_capab_high, PMV_capab_low, id_pos_sat, iq_pos_sat, id_neg_sat, iq_neg_sat],
        name='Capability_block'
    )
    Capability_block.event_dict = {
        Capability_block_inv_Xtrafo_Lout_pu: vf.add_const(None, name='inv_Xtrafo_Lout_pu'),
        Capability_block_MaxAuxiliaryVoltage: vf.add_const(None, name='MaxAuxiliaryVoltage'),
        Capability_block_MaxTransfoFluxVoltage: vf.add_const(None, name='MaxTransfoFluxVoltage'),
        Capability_block_inv_Xtrafo_pu: vf.add_const(None, name='inv_Xtrafo_pu'),
        Capability_block_MinAuxiliaryVoltage: vf.add_const(None, name='MinAuxiliaryVoltage'),
        Capability_block_PmvLim_crit: vf.add_const(None, name='PmvLim_crit'),
        Capability_block_PmvLim_discharge: vf.add_const(None, name='PmvLim_discharge'),
        Capability_block_Pmax_dyn: vf.add_const(None, name='Pmax_dyn'),
        Capability_block_PmvLim_charge: vf.add_const(None, name='PmvLim_charge'),
        Capability_block_PlantEff: vf.add_const(None, name='PlantEff'),
        Capability_block_inv_PlantEff: vf.add_const(None, name='inv_PlantEff'),
        Capability_block_inv_k_eff_trafo: vf.add_const(None, name='inv_k_eff_trafo'),
        Capability_block_k_eff_trafo: vf.add_const(None, name='k_eff_trafo'),
        Capability_block_Xtrafo_pu: vf.add_const(None, name='Xtrafo_pu'),
        Capability_block_Imax: vf.add_const(None, name='Imax'),
        Capability_block_VdcRef: vf.add_const(None, name='VdcRef'),
    }

    Capability_block = Block(
        algebraic_eqs=[
            (Capability_block_inc_idMVhigh - 0.0),
            (Capability_block_inc_PMVhigh - 0.0),
            (Capability_block_inc_idMVlow - 0.0),
            (Capability_block_inc_PMVlow - 0.0),
            (Capability_block_inc_iqMVhigh - 0.0),
            (Capability_block_inc_iqMVlow - 0.0),
            (Capability_block_inc_VMVhigh - 0.0),
            (Capability_block_inc_VMVlow - 0.0),
            (Capability_block_inc_QMVhigh - 0.0),
            (Capability_block_inc_QMVlow - 0.0),
        ],
        algebraic_vars=[Capability_block_inc_idMVhigh, Capability_block_inc_PMVhigh, Capability_block_inc_idMVlow, Capability_block_inc_PMVlow, Capability_block_inc_iqMVhigh, Capability_block_inc_iqMVlow, Capability_block_inc_VMVhigh, Capability_block_inc_VMVlow, Capability_block_inc_QMVhigh, Capability_block_inc_QMVlow],
        in_vars=[idpos, iqpos, vdpos, vqpos, idneg, iqneg, vdneg, vqneg, vPCC_pos_mag, FRT_pos_flag, FRT_neg_flag, Qlim_cap, Qlim_ind, Qref_in],
        out_vars=[QMV_capab_high, QMV_capab_low, PMV_capab_high, PMV_capab_low, id_pos_sat, iq_pos_sat, id_neg_sat, iq_neg_sat],
        name='Capability_block'
    )
    Capability_block.event_dict = {
        Capability_block_inv_Xtrafo_Lout_pu_1: vf.add_const(None, name='inv_Xtrafo_Lout_pu'),
        Capability_block_MaxAuxiliaryVoltage_1: vf.add_const(None, name='MaxAuxiliaryVoltage'),
        Capability_block_MaxTransfoFluxVoltage_1: vf.add_const(None, name='MaxTransfoFluxVoltage'),
        Capability_block_inv_Xtrafo_pu_1: vf.add_const(None, name='inv_Xtrafo_pu'),
        Capability_block_MinAuxiliaryVoltage_1: vf.add_const(None, name='MinAuxiliaryVoltage'),
        Capability_block_PmvLim_crit_1: vf.add_const(None, name='PmvLim_crit'),
        Capability_block_PmvLim_discharge_1: vf.add_const(None, name='PmvLim_discharge'),
        Capability_block_Pmax_dyn_1: vf.add_const(None, name='Pmax_dyn'),
        Capability_block_PmvLim_charge_1: vf.add_const(None, name='PmvLim_charge'),
        Capability_block_PlantEff_1: vf.add_const(None, name='PlantEff'),
        Capability_block_inv_PlantEff_1: vf.add_const(None, name='inv_PlantEff'),
        Capability_block_inv_k_eff_trafo_1: vf.add_const(None, name='inv_k_eff_trafo'),
        Capability_block_k_eff_trafo_1: vf.add_const(None, name='k_eff_trafo'),
        Capability_block_Xtrafo_pu_1: vf.add_const(None, name='Xtrafo_pu'),
        Capability_block_Imax_1: vf.add_const(None, name='Imax'),
        Capability_block_VdcRef_1: vf.add_const(None, name='VdcRef'),
    }

    Current_controller = Block(
        state_eqs=[
            err1d_1,
            err1q_1,
            err2d_1,
            err2q_1,
            ((1.0 / 0.025) * (u1d_1 - Current_controller_xu1d_1)),
            ((1.0 / 0.025) * (u1q_1 - Current_controller_xu1q_1)),
        ],
        state_vars=[Current_controller_x1d_cc, Current_controller_x1q_cc, Current_controller_x2d_cc, Current_controller_x2q_cc, Current_controller_xu1d, Current_controller_xu1q],
        algebraic_eqs=[
            (Current_controller_u1df - Current_controller_xu1d_1),
            (Current_controller_u1qf - Current_controller_xu1q_1),
            (err1d - (i1d_ref_1 - i1d_1)),
            (err1q - (i1q_ref_1 - i1q_1)),
            (err2d - (i2d_ref_1 - i2d_1)),
            (err2q - (i2q_ref_1 - i2q_1)),
            (u2d_ref - (((Current_controller_kp_cc_1 * err2d_1) + (Current_controller_ki_cc_1 * Current_controller_x2d_cc_1)) + ((w_1 * Current_controller_l_1) * i2q_1))),
            (u2q_ref - (((Current_controller_kp_cc_1 * err2q_1) + (Current_controller_ki_cc_1 * Current_controller_x2q_cc_1)) - ((w_1 * Current_controller_l_1) * i2d_1))),
            (Current_controller_inc_i1d_ref - i1d_1),
            (Current_controller_inc_i1q_ref - i1q_1),
            (Current_controller_inc_xu1d - u1d_1),
            (Current_controller_inc_xu1q - u1q_1),
            (Current_controller_inc_x1d_cc - (((u1d_ref_1 - u1d_1) + ((w_1 * Current_controller_l_1) * i1q_1)) / Current_controller_ki_cc_1)),
            (Current_controller_inc_x1q_cc - (((u1q_ref_1 - u1q_1) - ((w_1 * Current_controller_l_1) * i1d_1)) / Current_controller_ki_cc_1)),
            (Current_controller_inc_i2d_ref - i2d_1),
            (Current_controller_inc_i2q_ref - i2q_1),
            (Current_controller_inc_x2d_cc - ((u2d_ref_1 - ((w_1 * Current_controller_l_1) * i2q_1)) / Current_controller_ki_cc_1)),
            (Current_controller_inc_x2q_cc - ((u2q_ref_1 + ((w_1 * Current_controller_l_1) * i2d_1)) / Current_controller_ki_cc_1)),
        ],
        algebraic_vars=[Current_controller_u1df, Current_controller_u1qf, err1d, err1q, err2d, err2q, u2d_ref, u2q_ref, Current_controller_inc_i1d_ref, Current_controller_inc_i1q_ref, Current_controller_inc_xu1d, Current_controller_inc_xu1q, Current_controller_inc_x1d_cc, Current_controller_inc_x1q_cc, Current_controller_inc_i2d_ref, Current_controller_inc_i2q_ref, Current_controller_inc_x2d_cc, Current_controller_inc_x2q_cc],
        in_vars=[i1d_ref, i1q_ref, i2d_ref, i2q_ref, u1d, u1q, u2d, u2q, i1d, i1q, i2d, i2q, w],
        out_vars=[u1d_ref, u1q_ref, u2d_ref, u2q_ref],
        name='Current controller'
    )
    Current_controller.diff_vars = [d_Current_controller_x1d_cc, d_Current_controller_x1q_cc, d_Current_controller_x2d_cc, d_Current_controller_x2q_cc, d_Current_controller_xu1d, d_Current_controller_xu1q]
    Current_controller.event_dict = {
        Current_controller_l: vf.add_const(None, name='l'),
        Current_controller_kp_cc: vf.add_const(None, name='kp_cc'),
        Current_controller_ki_cc: vf.add_const(None, name='ki_cc'),
    }

    Events = Block(
        algebraic_eqs=[
            (Events_inc_voltage_jump - 1.0),
            (Events_inc_ROCOF - 0.0),
            (Events_inc_phase_jump - 0.0),
            (phase_jump - Events_param_phase_jump_1),
            (voltage_jump - Events_param_voltage_jump_1),
            (ROCOF - Events_param_ROCOF_1),
        ],
        algebraic_vars=[Events_inc_voltage_jump, Events_inc_ROCOF, Events_inc_phase_jump, phase_jump, voltage_jump, ROCOF],
        out_vars=[voltage_jump, ROCOF, phase_jump],
        name='Events'
    )
    Events.event_dict = {
        Events_param_phase_jump: vf.add_const(None, name='param_phase_jump'),
        Events_param_ROCOF: vf.add_const(None, name='param_ROCOF'),
        Events_param_voltage_jump: vf.add_const(None, name='param_voltage_jump'),
    }

    Events = Block(
        algebraic_eqs=[
            (Events_inc_voltage_jump_1 - 1.0),
            (Events_inc_ROCOF_1 - 0.0),
            (Events_inc_phase_jump_1 - 0.0),
            (phase_jump - Events_param_phase_jump_3),
            (voltage_jump - Events_param_voltage_jump_3),
            (ROCOF - Events_param_ROCOF_3),
        ],
        algebraic_vars=[Events_inc_voltage_jump_1, Events_inc_ROCOF_1, Events_inc_phase_jump_1, phase_jump, voltage_jump, ROCOF],
        out_vars=[voltage_jump, ROCOF, phase_jump],
        name='Events'
    )
    Events.event_dict = {
        Events_param_phase_jump_2: vf.add_const(None, name='param_phase_jump'),
        Events_param_ROCOF_2: vf.add_const(None, name='param_ROCOF'),
        Events_param_voltage_jump_2: vf.add_const(None, name='param_voltage_jump'),
    }

    Fault_Detection = Block(
        algebraic_eqs=[
            (Fault_Detection_inc_FRT1_flag - 0.0),
            (Fault_Detection_inc_FRT2_flag - 0.0),
        ],
        algebraic_vars=[Fault_Detection_inc_FRT1_flag, Fault_Detection_inc_FRT2_flag],
        in_vars=[V1vsc, V2vsc],
        out_vars=[FRT1_flag, FRT2_flag],
        name='Fault Detection'
    )
    Fault_Detection.event_dict = {
        Fault_Detection_V1min: vf.add_const(None, name='V1min'),
        Fault_Detection_V1max: vf.add_const(None, name='V1max'),
        Fault_Detection_V2min: vf.add_const(None, name='V2min'),
        Fault_Detection_V2max: vf.add_const(None, name='V2max'),
    }

    Fault_Detection = Block(
        algebraic_eqs=[
            (Fault_Detection_inc_FRT1_flag_1 - 0.0),
            (Fault_Detection_inc_FRT2_flag_1 - 0.0),
        ],
        algebraic_vars=[Fault_Detection_inc_FRT1_flag_1, Fault_Detection_inc_FRT2_flag_1],
        in_vars=[V1pcc, V2pcc],
        out_vars=[FRT1_flag, FRT2_flag],
        name='Fault Detection'
    )
    Fault_Detection.event_dict = {
        Fault_Detection_V1min_1: vf.add_const(None, name='V1min'),
        Fault_Detection_V1max_1: vf.add_const(None, name='V1max'),
        Fault_Detection_V2min_1: vf.add_const(None, name='V2min'),
        Fault_Detection_V2max_1: vf.add_const(None, name='V2max'),
    }

    Grid_electrical_interface = Block(
        algebraic_eqs=[
            (ed - u1d_1),
            (eq - u1q_1),
            (Vpos - V1pcc_1),
            (Vneg - V2pcc_1),
            (id_eff - i1d_hat_1),
            (iq_eff - i1q_hat_1),
            (P_int - ((ed_1 * id_eff_1) + (eq_1 * iq_eff_1))),
            (Q_int - ((eq_1 * id_eff_1) - (ed_1 * iq_eff_1))),
            (P_elec - ((Grid_electrical_interface_p_mode_1 * P_int_1) + ((1.0 - Grid_electrical_interface_p_mode_1) * Ppcc_1))),
            (Q_elec - ((Grid_electrical_interface_p_mode_1 * Q_int_1) + ((1.0 - Grid_electrical_interface_p_mode_1) * Qpcc_1))),
        ],
        algebraic_vars=[ed, eq, Vpos, Vneg, id_eff, iq_eff, P_int, Q_int, P_elec, Q_elec],
        in_vars=[u1d, u1q, u2d, u2q, i1d, i1q, i2d, i2q, i1d_hat, i1q_hat, i2d_hat, i2q_hat, Ppcc, Qpcc, V1pcc, V2pcc, w, cosdelta, sindelta, imag_inst],
        out_vars=[ed, eq, Vpos, Vneg, id_eff, iq_eff, P_elec, Q_elec],
        name='Grid electrical interface'
    )
    Grid_electrical_interface.event_dict = {
        Grid_electrical_interface_p_mode: vf.add_const(None, name='p_mode'),
    }

    MV_voltage_limit = Block(
        algebraic_eqs=[
            (MV_voltage_limit_lim1 - ((Vpcc_1 - VdcRef_1) * MV_voltage_limit_inv_Xtrafo_Lout_pu_1)),
            (MV_voltage_limit_lim2 - ((Vpcc_1 - ((MV_voltage_limit_MaxAuxiliaryVoltage_1 * sym.heaviside((MV_voltage_limit_MaxTransfoFluxVoltage_1 - MV_voltage_limit_MaxAuxiliaryVoltage_1))) + (MV_voltage_limit_MaxTransfoFluxVoltage_1 * (1 - sym.heaviside((MV_voltage_limit_MaxTransfoFluxVoltage_1 - MV_voltage_limit_MaxAuxiliaryVoltage_1)))))) * MV_voltage_limit_inv_Xtrafo_pu_1)),
            (MV_voltage_limit_i_ind - ((Vpcc_1 - MV_voltage_limit_MinAuxiliaryVoltage_1) * MV_voltage_limit_inv_Xtrafo_pu_1)),
            (MV_voltage_limit_cap_reserve - sym.abs(((0.0 * sym.heaviside((0.0 - ImaxCapacitive_1))) + (ImaxCapacitive_1 * (1 - sym.heaviside((0.0 - ImaxCapacitive_1))))))),
            (MV_voltage_limit_ind_reserve - sym.abs(((0.0 * sym.heaviside((ImaxInductive_1 - 0.0))) + (ImaxInductive_1 * (1 - sym.heaviside((ImaxInductive_1 - 0.0))))))),
        ],
        algebraic_vars=[MV_voltage_limit_lim1, MV_voltage_limit_lim2, MV_voltage_limit_i_ind, MV_voltage_limit_cap_reserve, MV_voltage_limit_ind_reserve],
        in_vars=[Vpcc, VdcRef, Imax],
        out_vars=[ImaxCapacitive, ImaxInductive, reactive_reserve],
        name='MV_voltage_limit'
    )
    MV_voltage_limit.event_dict = {
        MV_voltage_limit_inv_Xtrafo_Lout_pu: vf.add_const(None, name='inv_Xtrafo_Lout_pu'),
        MV_voltage_limit_MaxAuxiliaryVoltage: vf.add_const(None, name='MaxAuxiliaryVoltage'),
        MV_voltage_limit_MaxTransfoFluxVoltage: vf.add_const(None, name='MaxTransfoFluxVoltage'),
        MV_voltage_limit_inv_Xtrafo_pu: vf.add_const(None, name='inv_Xtrafo_pu'),
        MV_voltage_limit_MinAuxiliaryVoltage: vf.add_const(None, name='MinAuxiliaryVoltage'),
    }

    MV_voltage_limit = Block(
        algebraic_eqs=[
            (MV_voltage_limit_inc_ImaxCapacitive - 0.0),
            (MV_voltage_limit_inc_ImaxInductive - 0.0),
            (MV_voltage_limit_inc_reactive_reserve - 0.0),
            (MV_voltage_limit_lim1_1 - ((Vpcc_1 - VdcRef_1) * MV_voltage_limit_inv_Xtrafo_Lout_pu_3)),
            (MV_voltage_limit_lim2_1 - ((Vpcc_1 - ((MV_voltage_limit_MaxAuxiliaryVoltage_3 * sym.heaviside((MV_voltage_limit_MaxTransfoFluxVoltage_3 - MV_voltage_limit_MaxAuxiliaryVoltage_3))) + (MV_voltage_limit_MaxTransfoFluxVoltage_3 * (1 - sym.heaviside((MV_voltage_limit_MaxTransfoFluxVoltage_3 - MV_voltage_limit_MaxAuxiliaryVoltage_3)))))) * MV_voltage_limit_inv_Xtrafo_pu_3)),
            (MV_voltage_limit_i_ind_1 - ((Vpcc_1 - MV_voltage_limit_MinAuxiliaryVoltage_3) * MV_voltage_limit_inv_Xtrafo_pu_3)),
            (MV_voltage_limit_cap_reserve_1 - sym.abs(((0.0 * sym.heaviside((0.0 - ImaxCapacitive_1))) + (ImaxCapacitive_1 * (1 - sym.heaviside((0.0 - ImaxCapacitive_1))))))),
            (MV_voltage_limit_ind_reserve_1 - sym.abs(((0.0 * sym.heaviside((ImaxInductive_1 - 0.0))) + (ImaxInductive_1 * (1 - sym.heaviside((ImaxInductive_1 - 0.0))))))),
        ],
        algebraic_vars=[MV_voltage_limit_inc_ImaxCapacitive, MV_voltage_limit_inc_ImaxInductive, MV_voltage_limit_inc_reactive_reserve, MV_voltage_limit_lim1_1, MV_voltage_limit_lim2_1, MV_voltage_limit_i_ind_1, MV_voltage_limit_cap_reserve_1, MV_voltage_limit_ind_reserve_1],
        in_vars=[Vpcc, VdcRef, Imax],
        out_vars=[ImaxCapacitive, ImaxInductive, reactive_reserve],
        name='MV_voltage_limit'
    )
    MV_voltage_limit.event_dict = {
        MV_voltage_limit_inv_Xtrafo_Lout_pu_2: vf.add_const(None, name='inv_Xtrafo_Lout_pu'),
        MV_voltage_limit_MaxAuxiliaryVoltage_2: vf.add_const(None, name='MaxAuxiliaryVoltage'),
        MV_voltage_limit_MaxTransfoFluxVoltage_2: vf.add_const(None, name='MaxTransfoFluxVoltage'),
        MV_voltage_limit_inv_Xtrafo_pu_2: vf.add_const(None, name='inv_Xtrafo_pu'),
        MV_voltage_limit_MinAuxiliaryVoltage_2: vf.add_const(None, name='MinAuxiliaryVoltage'),
    }

    PCC_Measurements = Block(
        state_eqs=[
            u1q_1,
            (w1_1 * Dw_1),
        ],
        state_vars=[PCC_Measurements_xw, PCC_Measurements_xt],
        algebraic_eqs=[
            (PCC_Measurements_Ppcc_tot - ((1.0 / 3.0) * ((((((uar_1 * iar_1) + (uai_1 * iai_1)) + (ubr_1 * ibr_1)) + (ubi_1 * ibi_1)) + (ucr_1 * icr_1)) + (uci_1 * ici_1)))),
            (PCC_Measurements_Qpcc_tot - ((1.0 / 3.0) * ((((((uai_1 * iar_1) - (uar_1 * iai_1)) + (ubi_1 * ibr_1)) - (ubr_1 * ibi_1)) + (uci_1 * icr_1)) - (ucr_1 * ici_1)))),
            (u1r - ((1.0 / 3.0) * ((((uar_1 - ((1.0 / 2.0) * ubr_1)) - ((1.0 / 2.0) * ucr_1)) - ((sym.sqrt(3.0) / 2.0) * ubi_1)) + ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u1i - ((1.0 / 3.0) * ((((uai_1 - ((1.0 / 2.0) * ubi_1)) - ((1.0 / 2.0) * uci_1)) + ((sym.sqrt(3.0) / 2.0) * ubr_1)) - ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (PCC_Measurements_i1r - ((1.0 / 3.0) * ((((iar_1 - ((1.0 / 2.0) * ibr_1)) - ((1.0 / 2.0) * icr_1)) - ((sym.sqrt(3.0) / 2.0) * ibi_1)) + ((sym.sqrt(3.0) / 2.0) * ici_1)))),
            (PCC_Measurements_i1i - ((1.0 / 3.0) * ((((iai_1 - ((1.0 / 2.0) * ibi_1)) - ((1.0 / 2.0) * ici_1)) + ((sym.sqrt(3.0) / 2.0) * ibr_1)) - ((sym.sqrt(3.0) / 2.0) * icr_1)))),
            (u2r - ((1.0 / 3.0) * ((((uar_1 - ((1.0 / 2.0) * ubr_1)) - ((1.0 / 2.0) * ucr_1)) + ((sym.sqrt(3.0) / 2.0) * ubi_1)) - ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u2i - ((1.0 / 3.0) * ((((uai_1 - ((1.0 / 2.0) * ubi_1)) - ((1.0 / 2.0) * uci_1)) - ((sym.sqrt(3.0) / 2.0) * ubr_1)) + ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (PCC_Measurements_i2r - ((1.0 / 3.0) * ((((iar_1 - ((1.0 / 2.0) * ibr_1)) - ((1.0 / 2.0) * icr_1)) + ((sym.sqrt(3.0) / 2.0) * ibi_1)) - ((sym.sqrt(3.0) / 2.0) * ici_1)))),
            (PCC_Measurements_i2i - ((1.0 / 3.0) * ((((iai_1 - ((1.0 / 2.0) * ibi_1)) - ((1.0 / 2.0) * ici_1)) - ((sym.sqrt(3.0) / 2.0) * ibr_1)) + ((sym.sqrt(3.0) / 2.0) * icr_1)))),
            (u1d - ((u1r_1 * costheta_1) + (u1i_1 * sintheta_1))),
            (u1q - (((-u1r_1) * sintheta_1) + (u1i_1 * costheta_1))),
            (u2d - ((u2r_1 * costheta_1) - (u2i_1 * sintheta_1))),
            (u2q - ((u2r_1 * sintheta_1) + (u2i_1 * costheta_1))),
            (V1pcc - sym.sqrt(((u1d_1 * u1d_1) + (u1q_1 * u1q_1)))),
            (V2pcc - sym.sqrt(((u2d_1 * u2d_1) + (u2q_1 * u2q_1)))),
            (w1 - ((2.0 * 3.141592653589793) * PCC_Measurements_f1_1)),
            (Dw - ((PCC_Measurements_ki_pll_1 * PCC_Measurements_xw_1) + (PCC_Measurements_kp_pll_1 * u1q_1))),
            (wpcc - (1.0 + Dw_1)),
            (theta - PCC_Measurements_xt_1),
            (costheta - sym.cos(theta_1)),
            (sintheta - sym.sin(theta_1)),
            (PCC_Measurements_inc_Ppcc - ((1.0 / 3.0) * ((((((uar_1 * iar_1) + (uai_1 * iai_1)) + (ubr_1 * ibr_1)) + (ubi_1 * ibi_1)) + (ucr_1 * icr_1)) + (uci_1 * ici_1)))),
            (PCC_Measurements_inc_Qpcc - ((1.0 / 3.0) * ((((((uai_1 * iar_1) - (uar_1 * iai_1)) + (ubi_1 * ibr_1)) - (ubr_1 * ibi_1)) + (uci_1 * icr_1)) - (ucr_1 * ici_1)))),
            (PCC_Measurements_inc_V1pcc - sym.sqrt(((u1d_1 * u1d_1) + (u1q_1 * u1q_1)))),
            (PCC_Measurements_inc_V2pcc - sym.sqrt(((u2d_1 * u2d_1) + (u2q_1 * u2q_1)))),
            (PCC_Measurements_inc_wpcc - 1.0),
            (PCC_Measurements_inc_xw - 0.0),
            (PCC_Measurements_inc_xt - sym.atan2(u1i_1, u1r_1)),
        ],
        algebraic_vars=[PCC_Measurements_Ppcc_tot, PCC_Measurements_Qpcc_tot, u1r, u1i, PCC_Measurements_i1r, PCC_Measurements_i1i, u2r, u2i, PCC_Measurements_i2r, PCC_Measurements_i2i, u1d, u1q, u2d, u2q, V1pcc, V2pcc, w1, Dw, wpcc, theta, costheta, sintheta, PCC_Measurements_inc_Ppcc, PCC_Measurements_inc_Qpcc, PCC_Measurements_inc_V1pcc, PCC_Measurements_inc_V2pcc, PCC_Measurements_inc_wpcc, PCC_Measurements_inc_xw, PCC_Measurements_inc_xt],
        in_vars=[uar, uai, ubr, ubi, ucr, uci, iar, iai, ibr, ibi, icr, ici],
        out_vars=[Ppcc, Qpcc, V1pcc, V2pcc, wpcc],
        name='PCC Measurements'
    )
    PCC_Measurements.diff_vars = [d_PCC_Measurements_xw, d_PCC_Measurements_xt]
    PCC_Measurements.event_dict = {
        PCC_Measurements_kp_pll: vf.add_const(None, name='kp_pll'),
        PCC_Measurements_ki_pll: vf.add_const(None, name='ki_pll'),
        PCC_Measurements_f1: vf.add_const(None, name='f1'),
    }

    PCC_Measurements = Block(
        state_eqs=[
            ((alpha_plot * (Ppcc_raw_1 - PCC_Measurements_xPpcc_1)) / tau_plot_eff_1),
            ((alpha_plot * (Qpcc_raw_1 - PCC_Measurements_xQpcc_1)) / tau_plot_eff_1),
        ],
        state_vars=[PCC_Measurements_xPpcc, PCC_Measurements_xQpcc],
        algebraic_eqs=[
            (Ppcc_raw - ((((((uar_1 * iar_1) + (uai_1 * iai_1)) + (ubr_1 * ibr_1)) + (ubi_1 * ibi_1)) + (ucr_1 * icr_1)) + (uci_1 * ici_1))),
            (Qpcc_raw - ((((((uai_1 * iar_1) - (uar_1 * iai_1)) + (ubi_1 * ibr_1)) - (ubr_1 * ibi_1)) + (uci_1 * icr_1)) - (ucr_1 * ici_1))),
            (tau_plot_eff - ((PCC_Measurements_tau_plot_1 * sym.heaviside((PCC_Measurements_tau_plot_1 - 1e-06))) + (1e-06 * (1 - sym.heaviside((PCC_Measurements_tau_plot_1 - 1e-06)))))),
            (Ppcc - PCC_Measurements_xPpcc_1),
            (Qpcc - PCC_Measurements_xQpcc_1),
            (u1r - ((1.0 / 3.0) * ((((uar_1 - (0.5 * ubr_1)) - (0.5 * ucr_1)) - ((sym.sqrt(3.0) / 2.0) * ubi_1)) + ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u1i - ((1.0 / 3.0) * ((((uai_1 - (0.5 * ubi_1)) - (0.5 * uci_1)) + ((sym.sqrt(3.0) / 2.0) * ubr_1)) - ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (u2r - ((1.0 / 3.0) * ((((uar_1 - (0.5 * ubr_1)) - (0.5 * ucr_1)) + ((sym.sqrt(3.0) / 2.0) * ubi_1)) - ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u2i - ((1.0 / 3.0) * ((((uai_1 - (0.5 * ubi_1)) - (0.5 * uci_1)) - ((sym.sqrt(3.0) / 2.0) * ubr_1)) + ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (V1pcc - sym.sqrt(((u1r_1 * u1r_1) + (u1i_1 * u1i_1)))),
            (V2pcc - sym.sqrt(((u2r_1 * u2r_1) + (u2i_1 * u2i_1)))),
            (PCC_Measurements_inc_xPpcc - Ppcc_raw_1),
            (PCC_Measurements_inc_xQpcc - Qpcc_raw_1),
            (PCC_Measurements_inc_Ppcc_1 - Ppcc_raw_1),
            (PCC_Measurements_inc_Qpcc_1 - Qpcc_raw_1),
            (PCC_Measurements_inc_V1pcc_1 - sym.sqrt(((u1r_1 * u1r_1) + (u1i_1 * u1i_1)))),
            (PCC_Measurements_inc_V2pcc_1 - sym.sqrt(((u2r_1 * u2r_1) + (u2i_1 * u2i_1)))),
        ],
        algebraic_vars=[Ppcc_raw, Qpcc_raw, tau_plot_eff, Ppcc, Qpcc, u1r, u1i, u2r, u2i, V1pcc, V2pcc, PCC_Measurements_inc_xPpcc, PCC_Measurements_inc_xQpcc, PCC_Measurements_inc_Ppcc_1, PCC_Measurements_inc_Qpcc_1, PCC_Measurements_inc_V1pcc_1, PCC_Measurements_inc_V2pcc_1],
        in_vars=[uar, uai, ubr, ubi, ucr, uci, iar, iai, ibr, ibi, icr, ici],
        out_vars=[Ppcc, Qpcc, V1pcc, V2pcc],
        name='PCC Measurements'
    )
    PCC_Measurements.diff_vars = [d_PCC_Measurements_xPpcc, d_PCC_Measurements_xQpcc]
    PCC_Measurements.event_dict = {
        PCC_Measurements_tau_plot: vf.add_const(None, name='tau_plot'),
        PCC_Measurements_T_plot_ramp: vf.add_const(None, name='T_plot_ramp'),
    }

    Pos_Seq_Current_Limiter = Block(
        algebraic_eqs=[
            (Pos_Seq_Current_Limiter_inc_i1d_hat - i1d_ref_1),
            (Pos_Seq_Current_Limiter_inc_i1q_hat - i1q_ref_1),
            (Pos_Seq_Current_Limiter_inc_Qref - Qpcc_1),
            (Pos_Seq_Current_Limiter_inc_FRT2_flag - 0.0),
        ],
        algebraic_vars=[Pos_Seq_Current_Limiter_inc_i1d_hat, Pos_Seq_Current_Limiter_inc_i1q_hat, Pos_Seq_Current_Limiter_inc_Qref, Pos_Seq_Current_Limiter_inc_FRT2_flag],
        in_vars=[i1d_hat, i1q_hat, Qref, FRT2_flag, Qpcc, imag_inst],
        out_vars=[i1d_ref, i1q_ref, i2_sat],
        name='Pos. Seq. Current Limiter'
    )

    Power_VI_limit = Block(
        algebraic_eqs=[
            (Power_VI_limit_PPCChigh - (Power_VI_limit_PlantEff_1 * ((FRT_pos_flag_1 * Power_VI_limit_PmvLim_crit_1) + ((1.0 - FRT_pos_flag_1) * ((Power_VI_limit_PmvLim_discharge_1 * sym.heaviside((Power_VI_limit_Pmax_dyn_1 - Power_VI_limit_PmvLim_discharge_1))) + (Power_VI_limit_Pmax_dyn_1 * (1 - sym.heaviside((Power_VI_limit_Pmax_dyn_1 - Power_VI_limit_PmvLim_discharge_1))))))))),
            (Power_VI_limit_PPCClow - (Power_VI_limit_inv_PlantEff_1 * ((FRT_pos_flag_1 * (-Power_VI_limit_PmvLim_crit_1)) + ((1.0 - FRT_pos_flag_1) * ((Power_VI_limit_PmvLim_charge_1 * sym.heaviside(((-Power_VI_limit_Pmax_dyn_1) - Power_VI_limit_PmvLim_charge_1))) + ((-Power_VI_limit_Pmax_dyn_1) * (1 - sym.heaviside(((-Power_VI_limit_Pmax_dyn_1) - Power_VI_limit_PmvLim_charge_1))))))))),
            (PMVhigh - (idMVhigh_1 * vMV_pos_mode_1)),
            (PMVlow - (idMVlow_1 * vMV_pos_mode_1)),
            (iqMVlow - (((((-1.0) * inv_Vpcc_1) * QPCChigh_1) * sym.heaviside(((((-1.0) * inv_Vpcc_1) * QPCChigh_1) - Iq_min_1))) + (Iq_min_1 * (1 - sym.heaviside(((((-1.0) * inv_Vpcc_1) * QPCChigh_1) - Iq_min_1)))))),
            (iqMVhigh - (((((-1.0) * inv_Vpcc_1) * QPCClow_1) * sym.heaviside((Iq_max_1 - (((-1.0) * inv_Vpcc_1) * QPCClow_1)))) + (Iq_max_1 * (1 - sym.heaviside((Iq_max_1 - (((-1.0) * inv_Vpcc_1) * QPCClow_1))))))),
            (VMVhigh - (((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_1 * iqMVlow_1)) * sym.heaviside(((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_1 * iqMVlow_1)) - 0.0))) + (0.0 * (1 - sym.heaviside(((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_1 * iqMVlow_1)) - 0.0)))))),
            (VMVlow - (((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_1 * iqMVhigh_1)) * sym.heaviside(((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_1 * iqMVhigh_1)) - 0.0))) + (0.0 * (1 - sym.heaviside(((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_1 * iqMVhigh_1)) - 0.0)))))),
            (QMVhigh - (((-1.0) * iqMVhigh_1) * VMVlow_1)),
            (QMVlow - (((-1.0) * iqMVlow_1) * VMVhigh_1)),
        ],
        algebraic_vars=[Power_VI_limit_PPCChigh, Power_VI_limit_PPCClow, PMVhigh, PMVlow, iqMVlow, iqMVhigh, VMVhigh, VMVlow, QMVhigh, QMVlow],
        in_vars=[FRT_pos_flag, inv_Vpcc, Id_max, Id_min, Iq_max, Iq_min, vMV_pos_mode, QPCChigh, QPCClow, Vpcc],
        out_vars=[idMVhigh, PMVhigh, idMVlow, PMVlow, iqMVlow, iqMVhigh, VMVhigh, VMVlow, QMVhigh, QMVlow],
        name='Power_VI_limit'
    )
    Power_VI_limit.event_dict = {
        Power_VI_limit_PmvLim_crit: vf.add_const(None, name='PmvLim_crit'),
        Power_VI_limit_PmvLim_discharge: vf.add_const(None, name='PmvLim_discharge'),
        Power_VI_limit_Pmax_dyn: vf.add_const(None, name='Pmax_dyn'),
        Power_VI_limit_PmvLim_charge: vf.add_const(None, name='PmvLim_charge'),
        Power_VI_limit_PlantEff: vf.add_const(None, name='PlantEff'),
        Power_VI_limit_inv_PlantEff: vf.add_const(None, name='inv_PlantEff'),
        Power_VI_limit_inv_k_eff_trafo: vf.add_const(None, name='inv_k_eff_trafo'),
        Power_VI_limit_k_eff_trafo: vf.add_const(None, name='k_eff_trafo'),
        Power_VI_limit_Xtrafo_pu: vf.add_const(None, name='Xtrafo_pu'),
    }

    Power_VI_limit = Block(
        algebraic_eqs=[
            (Power_VI_limit_inc_idMVhigh - 0.0),
            (Power_VI_limit_inc_PMVhigh - 0.0),
            (Power_VI_limit_inc_idMVlow - 0.0),
            (Power_VI_limit_inc_PMVlow - 0.0),
            (Power_VI_limit_inc_iqMVlow - 0.0),
            (Power_VI_limit_inc_iqMVhigh - 0.0),
            (Power_VI_limit_inc_VMVhigh - 0.0),
            (Power_VI_limit_inc_VMVlow - 0.0),
            (Power_VI_limit_inc_QMVhigh - 0.0),
            (Power_VI_limit_inc_QMVlow - 0.0),
            (Power_VI_limit_PPCChigh_1 - (Power_VI_limit_PlantEff_3 * ((FRT_pos_flag_1 * Power_VI_limit_PmvLim_crit_3) + ((1.0 - FRT_pos_flag_1) * ((Power_VI_limit_PmvLim_discharge_3 * sym.heaviside((Power_VI_limit_Pmax_dyn_3 - Power_VI_limit_PmvLim_discharge_3))) + (Power_VI_limit_Pmax_dyn_3 * (1 - sym.heaviside((Power_VI_limit_Pmax_dyn_3 - Power_VI_limit_PmvLim_discharge_3))))))))),
            (Power_VI_limit_PPCClow_1 - (Power_VI_limit_inv_PlantEff_3 * ((FRT_pos_flag_1 * (-Power_VI_limit_PmvLim_crit_3)) + ((1.0 - FRT_pos_flag_1) * ((Power_VI_limit_PmvLim_charge_3 * sym.heaviside(((-Power_VI_limit_Pmax_dyn_3) - Power_VI_limit_PmvLim_charge_3))) + ((-Power_VI_limit_Pmax_dyn_3) * (1 - sym.heaviside(((-Power_VI_limit_Pmax_dyn_3) - Power_VI_limit_PmvLim_charge_3))))))))),
            (PMVhigh - (idMVhigh_1 * vMV_pos_mode_1)),
            (PMVlow - (idMVlow_1 * vMV_pos_mode_1)),
            (iqMVlow - (((((-1.0) * inv_Vpcc_1) * QPCChigh_1) * sym.heaviside(((((-1.0) * inv_Vpcc_1) * QPCChigh_1) - Iq_min_1))) + (Iq_min_1 * (1 - sym.heaviside(((((-1.0) * inv_Vpcc_1) * QPCChigh_1) - Iq_min_1)))))),
            (iqMVhigh - (((((-1.0) * inv_Vpcc_1) * QPCClow_1) * sym.heaviside((Iq_max_1 - (((-1.0) * inv_Vpcc_1) * QPCClow_1)))) + (Iq_max_1 * (1 - sym.heaviside((Iq_max_1 - (((-1.0) * inv_Vpcc_1) * QPCClow_1))))))),
            (VMVhigh - (((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_3 * iqMVlow_1)) * sym.heaviside(((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_3 * iqMVlow_1)) - 0.0))) + (0.0 * (1 - sym.heaviside(((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_3 * iqMVlow_1)) - 0.0)))))),
            (VMVlow - (((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_3 * iqMVhigh_1)) * sym.heaviside(((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_3 * iqMVhigh_1)) - 0.0))) + (0.0 * (1 - sym.heaviside(((Vpcc_1 - (Power_VI_limit_Xtrafo_pu_3 * iqMVhigh_1)) - 0.0)))))),
            (QMVhigh - (((-1.0) * iqMVhigh_1) * VMVlow_1)),
            (QMVlow - (((-1.0) * iqMVlow_1) * VMVhigh_1)),
        ],
        algebraic_vars=[Power_VI_limit_inc_idMVhigh, Power_VI_limit_inc_PMVhigh, Power_VI_limit_inc_idMVlow, Power_VI_limit_inc_PMVlow, Power_VI_limit_inc_iqMVlow, Power_VI_limit_inc_iqMVhigh, Power_VI_limit_inc_VMVhigh, Power_VI_limit_inc_VMVlow, Power_VI_limit_inc_QMVhigh, Power_VI_limit_inc_QMVlow, Power_VI_limit_PPCChigh_1, Power_VI_limit_PPCClow_1, PMVhigh, PMVlow, iqMVlow, iqMVhigh, VMVhigh, VMVlow, QMVhigh, QMVlow],
        in_vars=[FRT_pos_flag, inv_Vpcc, Id_max, Id_min, Iq_max, Iq_min, vMV_pos_mode, QPCChigh, QPCClow, Vpcc],
        out_vars=[idMVhigh, PMVhigh, idMVlow, PMVlow, iqMVlow, iqMVhigh, VMVhigh, VMVlow, QMVhigh, QMVlow],
        name='Power_VI_limit'
    )
    Power_VI_limit.event_dict = {
        Power_VI_limit_PmvLim_crit_2: vf.add_const(None, name='PmvLim_crit'),
        Power_VI_limit_PmvLim_discharge_2: vf.add_const(None, name='PmvLim_discharge'),
        Power_VI_limit_Pmax_dyn_2: vf.add_const(None, name='Pmax_dyn'),
        Power_VI_limit_PmvLim_charge_2: vf.add_const(None, name='PmvLim_charge'),
        Power_VI_limit_PlantEff_2: vf.add_const(None, name='PlantEff'),
        Power_VI_limit_inv_PlantEff_2: vf.add_const(None, name='inv_PlantEff'),
        Power_VI_limit_inv_k_eff_trafo_1: vf.add_const(None, name='inv_k_eff_trafo'),
        Power_VI_limit_k_eff_trafo_1: vf.add_const(None, name='k_eff_trafo'),
        Power_VI_limit_Xtrafo_pu_2: vf.add_const(None, name='Xtrafo_pu'),
    }

    Protection = Block(
        algebraic_eqs=[
            (u_eval - ((sym.heaviside((Protection_LineMonitorType_1 - 0.5)) * u_MaxVLL_1) + ((1.0 - sym.heaviside((Protection_LineMonitorType_1 - 0.5))) * u_3Ph_1))),
            (LvrtOn - ((sym.heaviside((Protection_LVRT_activation_thr_1 - u_eval_1)) * 1.0) + ((1.0 - sym.heaviside((Protection_LVRT_activation_thr_1 - u_eval_1))) * 0.0))),
            (t_elapsed_LV - (t - t_LV)),
            (vLVRT_trip_lim - ((sym.heaviside((Protection_DtLVRT_1_1 - t_elapsed_LV_1)) * Protection_vLV_1_1) + ((1.0 - sym.heaviside((Protection_DtLVRT_1_1 - t_elapsed_LV_1))) * ((sym.heaviside((Protection_DtLVRT_2_1 - t_elapsed_LV_1)) * Protection_vLV_2_1) + ((1.0 - sym.heaviside((Protection_DtLVRT_2_1 - t_elapsed_LV_1))) * ((sym.heaviside((Protection_DtLVRT_3_1 - t_elapsed_LV_1)) * Protection_vLV_3_1) + ((1.0 - sym.heaviside((Protection_DtLVRT_3_1 - t_elapsed_LV_1))) * ((sym.heaviside((Protection_DtLVRT_4_1 - t_elapsed_LV_1)) * Protection_vLV_4_1) + ((1.0 - sym.heaviside((Protection_DtLVRT_4_1 - t_elapsed_LV_1))) * Protection_vLV_5_1))))))))),
            (LVRT_Alarm - ((((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((LvrtOn_1 - 0.5))) * sym.heaviside((vLVRT_trip_lim_1 - u_eval_1))) * 1.0) + ((1.0 - ((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((LvrtOn_1 - 0.5))) * sym.heaviside((vLVRT_trip_lim_1 - u_eval_1)))) * 0.0))),
            (OvrtOn - ((sym.heaviside((u_eval_1 - Protection_OVRT_activation_thr_1)) * 1.0) + ((1.0 - sym.heaviside((u_eval_1 - Protection_OVRT_activation_thr_1))) * 0.0))),
            (t_elapsed_OV - (t - t_OV)),
            (vOVRT_trip_lim - ((sym.heaviside((Protection_DtOVRT_1_1 - t_elapsed_OV_1)) * Protection_vOV_1_1) + ((1.0 - sym.heaviside((Protection_DtOVRT_1_1 - t_elapsed_OV_1))) * ((sym.heaviside((Protection_DtOVRT_2_1 - t_elapsed_OV_1)) * Protection_vOV_2_1) + ((1.0 - sym.heaviside((Protection_DtOVRT_2_1 - t_elapsed_OV_1))) * ((sym.heaviside((Protection_DtOVRT_3_1 - t_elapsed_OV_1)) * Protection_vOV_3_1) + ((1.0 - sym.heaviside((Protection_DtOVRT_3_1 - t_elapsed_OV_1))) * ((sym.heaviside((Protection_DtOVRT_4_1 - t_elapsed_OV_1)) * Protection_vOV_4_1) + ((1.0 - sym.heaviside((Protection_DtOVRT_4_1 - t_elapsed_OV_1))) * Protection_vOV_5_1))))))))),
            (OVRT_Alarm - ((((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((OvrtOn_1 - 0.5))) * sym.heaviside((u_eval_1 - vOVRT_trip_lim_1))) * 1.0) + ((1.0 - ((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((OvrtOn_1 - 0.5))) * sym.heaviside((u_eval_1 - vOVRT_trip_lim_1)))) * 0.0))),
            (en_OF1 - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((f_1 - Protection_HighThr_Freq1_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((f_1 - Protection_HighThr_Freq1_1)))) * 0.0))),
            (en_OF2 - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((f_1 - Protection_HighThr_Freq2_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((f_1 - Protection_HighThr_Freq2_1)))) * 0.0))),
            (en_OFFast - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((f_1 - Protection_HighThr_FreqFast_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((f_1 - Protection_HighThr_FreqFast_1)))) * 0.0))),
            (en_UF1 - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_Freq1_1 - f_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_Freq1_1 - f_1)))) * 0.0))),
            (en_UF2 - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_Freq2_1 - f_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_Freq2_1 - f_1)))) * 0.0))),
            (en_UFFast - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_FreqFast_1 - f_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_FreqFast_1 - f_1)))) * 0.0))),
            (Freq_Alarm - (((1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - sym.heaviside((Trip_OF_1 - 0.5))) * (1.0 - sym.heaviside((Trip_OF_2 - 0.5)))))) * (1.0 - sym.heaviside((Trip_OF_Fast - 0.5)))))) * (1.0 - sym.heaviside((Trip_UF_1 - 0.5)))))) * (1.0 - sym.heaviside((Trip_UF_2 - 0.5)))))) * (1.0 - sym.heaviside((Trip_UF_Fast - 0.5))))) * 1.0) + ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - sym.heaviside((Trip_OF_1 - 0.5))) * (1.0 - sym.heaviside((Trip_OF_2 - 0.5)))))) * (1.0 - sym.heaviside((Trip_OF_Fast - 0.5)))))) * (1.0 - sym.heaviside((Trip_UF_1 - 0.5)))))) * (1.0 - sym.heaviside((Trip_UF_2 - 0.5)))))) * (1.0 - sym.heaviside((Trip_UF_Fast - 0.5)))))) * 0.0))),
            (en_RoCoF - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((sym.abs(RoCoF_measured_1) - Protection_Limit_RoCoF_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((sym.abs(RoCoF_measured_1) - Protection_Limit_RoCoF_1)))) * 0.0))),
            (en_OV - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((u_eval_1 - Protection_HighThr_Voltage_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((u_eval_1 - Protection_HighThr_Voltage_1)))) * 0.0))),
            (en_OVFast - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((u_eval_1 - Protection_HighThr_VoltageFast_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((u_eval_1 - Protection_HighThr_VoltageFast_1)))) * 0.0))),
            (en_UV - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_Voltage_1 - u_eval_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_Voltage_1 - u_eval_1)))) * 0.0))),
            (en_UVFast - (((sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_VoltageFast_1 - u_eval_1))) * 1.0) + ((1.0 - (sym.heaviside((enable_1 - 0.5)) * sym.heaviside((Protection_LowThr_VoltageFast_1 - u_eval_1)))) * 0.0))),
            (Volt_Alarm - (((1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - sym.heaviside((Trip_OV - 0.5))) * (1.0 - sym.heaviside((Trip_OV_Fast - 0.5)))))) * (1.0 - sym.heaviside((Trip_UV - 0.5)))))) * (1.0 - sym.heaviside((Trip_UV_Fast - 0.5))))) * 1.0) + ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - sym.heaviside((Trip_OV - 0.5))) * (1.0 - sym.heaviside((Trip_OV_Fast - 0.5)))))) * (1.0 - sym.heaviside((Trip_UV - 0.5)))))) * (1.0 - sym.heaviside((Trip_UV_Fast - 0.5)))))) * 0.0))),
            (OR_General - (((1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - sym.heaviside((LVRT_Alarm_1 - 0.5))) * (1.0 - sym.heaviside((OVRT_Alarm_1 - 0.5)))))) * (1.0 - sym.heaviside((Freq_Alarm_1 - 0.5)))))) * (1.0 - sym.heaviside((RoCoF_Alarm_1 - 0.5)))))) * (1.0 - sym.heaviside((Volt_Alarm_1 - 0.5))))) * 1.0) + ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - sym.heaviside((LVRT_Alarm_1 - 0.5))) * (1.0 - sym.heaviside((OVRT_Alarm_1 - 0.5)))))) * (1.0 - sym.heaviside((Freq_Alarm_1 - 0.5)))))) * (1.0 - sym.heaviside((RoCoF_Alarm_1 - 0.5)))))) * (1.0 - sym.heaviside((Volt_Alarm_1 - 0.5)))))) * 0.0))),
            (Protection_inc_LVRT_Alarm - 0.0),
            (Protection_inc_OVRT_Alarm - 0.0),
            (Protection_inc_Freq_Alarm - 0.0),
            (Protection_inc_RoCoF_Alarm - 0.0),
            (Protection_inc_Master_Trip - 0.0),
        ],
        algebraic_vars=[u_eval, LvrtOn, t_elapsed_LV, vLVRT_trip_lim, LVRT_Alarm, OvrtOn, t_elapsed_OV, vOVRT_trip_lim, OVRT_Alarm, en_OF1, en_OF2, en_OFFast, en_UF1, en_UF2, en_UFFast, Freq_Alarm, en_RoCoF, en_OV, en_OVFast, en_UV, en_UVFast, Volt_Alarm, OR_General, Protection_inc_LVRT_Alarm, Protection_inc_OVRT_Alarm, Protection_inc_Freq_Alarm, Protection_inc_RoCoF_Alarm, Protection_inc_Master_Trip],
        in_vars=[u_3Ph, u_MaxVLL, f, enable, RoCoF_measured],
        out_vars=[Master_Trip, LVRT_Alarm, OVRT_Alarm, Freq_Alarm, RoCoF_Alarm],
        name='Protection'
    )
    Protection.event_dict = {
        Protection_LVRT_activation_thr: vf.add_const(None, name='LVRT_activation_thr'),
        Protection_vLV_1: vf.add_const(None, name='vLV_1'),
        Protection_vLV_2: vf.add_const(None, name='vLV_2'),
        Protection_vLV_3: vf.add_const(None, name='vLV_3'),
        Protection_vLV_4: vf.add_const(None, name='vLV_4'),
        Protection_vLV_5: vf.add_const(None, name='vLV_5'),
        Protection_DtLVRT_1: vf.add_const(None, name='DtLVRT_1'),
        Protection_DtLVRT_2: vf.add_const(None, name='DtLVRT_2'),
        Protection_DtLVRT_3: vf.add_const(None, name='DtLVRT_3'),
        Protection_DtLVRT_4: vf.add_const(None, name='DtLVRT_4'),
        Protection_OVRT_activation_thr: vf.add_const(None, name='OVRT_activation_thr'),
        Protection_vOV_1: vf.add_const(None, name='vOV_1'),
        Protection_vOV_2: vf.add_const(None, name='vOV_2'),
        Protection_vOV_3: vf.add_const(None, name='vOV_3'),
        Protection_vOV_4: vf.add_const(None, name='vOV_4'),
        Protection_vOV_5: vf.add_const(None, name='vOV_5'),
        Protection_DtOVRT_1: vf.add_const(None, name='DtOVRT_1'),
        Protection_DtOVRT_2: vf.add_const(None, name='DtOVRT_2'),
        Protection_DtOVRT_3: vf.add_const(None, name='DtOVRT_3'),
        Protection_DtOVRT_4: vf.add_const(None, name='DtOVRT_4'),
        Protection_HighThr_Freq1: vf.add_const(None, name='HighThr_Freq1'),
        Protection_HighThr_Freq2: vf.add_const(None, name='HighThr_Freq2'),
        Protection_HighThr_FreqFast: vf.add_const(None, name='HighThr_FreqFast'),
        Protection_LowThr_Freq1: vf.add_const(None, name='LowThr_Freq1'),
        Protection_LowThr_Freq2: vf.add_const(None, name='LowThr_Freq2'),
        Protection_LowThr_FreqFast: vf.add_const(None, name='LowThr_FreqFast'),
        Protection_TOFreq_1: vf.add_const(None, name='TOFreq_1'),
        Protection_TOFreq_2: vf.add_const(None, name='TOFreq_2'),
        Protection_TOFreq_Fast: vf.add_const(None, name='TOFreq_Fast'),
        Protection_TUFreq_1: vf.add_const(None, name='TUFreq_1'),
        Protection_TUFreq_2: vf.add_const(None, name='TUFreq_2'),
        Protection_TUFreq_Fast: vf.add_const(None, name='TUFreq_Fast'),
        Protection_Limit_RoCoF: vf.add_const(None, name='Limit_RoCoF'),
        Protection_TRoCoF: vf.add_const(None, name='TRoCoF'),
        Protection_HighThr_Voltage: vf.add_const(None, name='HighThr_Voltage'),
        Protection_HighThr_VoltageFast: vf.add_const(None, name='HighThr_VoltageFast'),
        Protection_TOvolt: vf.add_const(None, name='TOvolt'),
        Protection_TOvolt_Fast: vf.add_const(None, name='TOvolt_Fast'),
        Protection_LowThr_Voltage: vf.add_const(None, name='LowThr_Voltage'),
        Protection_LowThr_VoltageFast: vf.add_const(None, name='LowThr_VoltageFast'),
        Protection_TUvolt: vf.add_const(None, name='TUvolt'),
        Protection_TUvolt_Fast: vf.add_const(None, name='TUvolt_Fast'),
        Protection_LineMonitorType: vf.add_const(None, name='LineMonitorType'),
    }

    Q_Vac_droop = Block(
        algebraic_eqs=[
            (Q_Vac_droop_inc_rv - rv_init_1),
            (Q_Vac_droop_inc_xv - xv_init_1),
            (Q_Vac_droop_inc_Vref - V1vsc_1),
            (Q_Vac_droop_inc_xV - V1vsc_1),
            (Q_Vac_droop_inc_Vf - V1vsc_1),
            (Q_Vac_droop_inc_xQ_meas_f - Qvsc_1),
            (Q_Vac_droop_inc_Qref_out - Qvsc_1),
            (Q_Vac_droop_inc_Qref - Qvsc_1),
            (Q_Vac_droop_val_cos - sym.cos(val_angle_E_1)),
            (Q_Vac_droop_val_sin - sym.sin(val_angle_E_1)),
            (Q_Vac_droop_denom_v - ((sym.heaviside((0.001 - V1vsc_1)) * 1.0) + ((1.0 - sym.heaviside((0.001 - V1vsc_1))) * (V1vsc_1 * V1vsc_1)))),
            (Q_Vac_droop_inc_eq - 0.0),
        ],
        algebraic_vars=[Q_Vac_droop_inc_rv, Q_Vac_droop_inc_xv, Q_Vac_droop_inc_Vref, Q_Vac_droop_inc_xV, Q_Vac_droop_inc_Vf, Q_Vac_droop_inc_xQ_meas_f, Q_Vac_droop_inc_Qref_out, Q_Vac_droop_inc_Qref, Q_Vac_droop_val_cos, Q_Vac_droop_val_sin, Q_Vac_droop_denom_v, Q_Vac_droop_inc_eq],
        in_vars=[Q_capab_high, Vref, V1vsc, Qref, Qvsc, Q_capab_low, FRT1_flag, Pvsc, val_angle_E, flag_overload, xv_init, rv_init],
        out_vars=[Qref_out, ed, eq],
        name='Q/Vac droop'
    )
    Q_Vac_droop.event_dict = {
        Q_Vac_droop_tau_Q_meas: vf.add_const(None, name='tau_Q_meas'),
        Q_Vac_droop_ki_Q: vf.add_const(None, name='ki_Q'),
        Q_Vac_droop_tau_V: vf.add_const(None, name='tau_V'),
        Q_Vac_droop_kd_V: vf.add_const(None, name='kd_V'),
    }

    Q_Vac_droop = Block(
        algebraic_eqs=[
            (Q_Vac_droop_inc_Vref_1 - V1pcc_1),
            (Q_Vac_droop_inc_xV_1 - V1pcc_1),
            (Q_Vac_droop_inc_Vf_1 - V1pcc_1),
            (Q_Vac_droop_inc_Qref_1 - 0.0),
            (Q_Vac_droop_inc_Qref_out_1 - Qref_1),
            (Q_Vac_droop_inc_i1q_ref - i1q_hat_1),
            (Q_Vac_droop_inc_NoMoreNoLess - 1.0),
            (Q_Vac_droop_inc_e_pre - ed_1),
        ],
        algebraic_vars=[Q_Vac_droop_inc_Vref_1, Q_Vac_droop_inc_xV_1, Q_Vac_droop_inc_Vf_1, Q_Vac_droop_inc_Qref_1, Q_Vac_droop_inc_Qref_out_1, Q_Vac_droop_inc_i1q_ref, Q_Vac_droop_inc_NoMoreNoLess, Q_Vac_droop_inc_e_pre],
        in_vars=[Q_capab_high, Vref, V1pcc, Qref, Qpcc, Q_capab_low, i1q_hat, i1q_ref, FRT1_flag],
        out_vars=[Qref_out, ed, eq],
        name='Q/Vac droop'
    )
    Q_Vac_droop.event_dict = {
        Q_Vac_droop_ki_Q_1: vf.add_const(None, name='ki_Q'),
        Q_Vac_droop_tau_V_1: vf.add_const(None, name='tau_V'),
        Q_Vac_droop_kd_V_1: vf.add_const(None, name='kd_V'),
    }

    Sat_Lim_Neg = Block(
        algebraic_eqs=[
            (theta - sym.atan2(iq_hat_1, id_hat_1)),
            (costheta - sym.abs(sym.cos(theta_1))),
            (sintheta - sym.abs(sym.sin(theta_1))),
            (id_sat_up - (i_sat_1 * costheta_1)),
            (id_sat_low - ((-i_sat_1) * costheta_1)),
            (iq_sat_up - (i_sat_1 * sintheta_1)),
            (iq_sat_low - ((-i_sat_1) * sintheta_1)),
            (Sat_Lim_Neg_inc_theta - sym.atan2(iq_hat_1, id_hat_1)),
            (Sat_Lim_Neg_inc_id_sat_up - (i_sat_1 * costheta_1)),
            (Sat_Lim_Neg_inc_id_sat_low - ((-i_sat_1) * costheta_1)),
            (Sat_Lim_Neg_inc_iq_sat_up - (i_sat_1 * sintheta_1)),
            (Sat_Lim_Neg_inc_iq_sat_low - ((-i_sat_1) * sintheta_1)),
        ],
        algebraic_vars=[theta, costheta, sintheta, id_sat_up, id_sat_low, iq_sat_up, iq_sat_low, Sat_Lim_Neg_inc_theta, Sat_Lim_Neg_inc_id_sat_up, Sat_Lim_Neg_inc_id_sat_low, Sat_Lim_Neg_inc_iq_sat_up, Sat_Lim_Neg_inc_iq_sat_low],
        in_vars=[i_sat, id_hat, iq_hat],
        out_vars=[id_sat_up, id_sat_low, iq_sat_up, iq_sat_low],
        name='Sat. Lim. Neg.'
    )

    Sat_Lim_Neg = Block(
        algebraic_eqs=[
            (theta - sym.atan2(iq_hat_1, id_hat_1)),
            (costheta - sym.abs(sym.cos(theta_1))),
            (sintheta - sym.abs(sym.sin(theta_1))),
            (id_sat_up - (i_sat_1 * costheta_1)),
            (id_sat_low - ((-i_sat_1) * costheta_1)),
            (iq_sat_up - (i_sat_1 * sintheta_1)),
            (iq_sat_low - ((-i_sat_1) * sintheta_1)),
            (Sat_Lim_Neg_inc_theta_1 - sym.atan2(iq_hat_1, id_hat_1)),
            (Sat_Lim_Neg_inc_id_sat_up_1 - (i_sat_1 * costheta_1)),
            (Sat_Lim_Neg_inc_id_sat_low_1 - ((-i_sat_1) * costheta_1)),
            (Sat_Lim_Neg_inc_iq_sat_up_1 - (i_sat_1 * sintheta_1)),
            (Sat_Lim_Neg_inc_iq_sat_low_1 - ((-i_sat_1) * sintheta_1)),
        ],
        algebraic_vars=[theta, costheta, sintheta, id_sat_up, id_sat_low, iq_sat_up, iq_sat_low, Sat_Lim_Neg_inc_theta_1, Sat_Lim_Neg_inc_id_sat_up_1, Sat_Lim_Neg_inc_id_sat_low_1, Sat_Lim_Neg_inc_iq_sat_up_1, Sat_Lim_Neg_inc_iq_sat_low_1],
        in_vars=[i_sat, id_hat, iq_hat],
        out_vars=[id_sat_up, id_sat_low, iq_sat_up, iq_sat_low],
        name='Sat. Lim. Neg.'
    )

    Sat_Lim_Pos = Block(
        algebraic_eqs=[
            (theta - sym.atan2(iq_hat_1, id_hat_1)),
            (costheta - sym.abs(sym.cos(theta_1))),
            (sintheta - sym.abs(sym.sin(theta_1))),
            (id_sat_up - (i_sat_1 * costheta_1)),
            (id_sat_low - (((-i_sat_1) * i_sat_1) * costheta_1)),
            (iq_sat_up - (i_sat_1 * sintheta_1)),
            (iq_sat_low - (((-i_sat_1) * i_sat_1) * sintheta_1)),
            (Sat_Lim_Pos_inc_id_sat_up - (i_sat_1 * costheta_1)),
            (Sat_Lim_Pos_inc_id_sat_low - ((-i_sat_1) * costheta_1)),
            (Sat_Lim_Pos_inc_iq_sat_up - (i_sat_1 * sintheta_1)),
            (Sat_Lim_Pos_inc_iq_sat_low - ((-i_sat_1) * sintheta_1)),
        ],
        algebraic_vars=[theta, costheta, sintheta, id_sat_up, id_sat_low, iq_sat_up, iq_sat_low, Sat_Lim_Pos_inc_id_sat_up, Sat_Lim_Pos_inc_id_sat_low, Sat_Lim_Pos_inc_iq_sat_up, Sat_Lim_Pos_inc_iq_sat_low],
        in_vars=[i_sat, id_hat, iq_hat],
        out_vars=[id_sat_up, id_sat_low, iq_sat_up, iq_sat_low],
        name='Sat. Lim. Pos.'
    )

    Sat_Lim_Pos = Block(
        algebraic_eqs=[
            (theta - sym.atan2(iq_hat_1, id_hat_1)),
            (costheta - sym.abs(sym.cos(theta_1))),
            (sintheta - sym.abs(sym.sin(theta_1))),
            (id_sat_up - (i_sat_1 * costheta_1)),
            (id_sat_low - (((-i_sat_1) * i_sat_1) * costheta_1)),
            (iq_sat_up - (i_sat_1 * sintheta_1)),
            (iq_sat_low - (((-i_sat_1) * i_sat_1) * sintheta_1)),
            (Sat_Lim_Pos_inc_id_sat_up_1 - (i_sat_1 * costheta_1)),
            (Sat_Lim_Pos_inc_id_sat_low_1 - ((-i_sat_1) * costheta_1)),
            (Sat_Lim_Pos_inc_iq_sat_up_1 - (i_sat_1 * sintheta_1)),
            (Sat_Lim_Pos_inc_iq_sat_low_1 - ((-i_sat_1) * sintheta_1)),
        ],
        algebraic_vars=[theta, costheta, sintheta, id_sat_up, id_sat_low, iq_sat_up, iq_sat_low, Sat_Lim_Pos_inc_id_sat_up_1, Sat_Lim_Pos_inc_id_sat_low_1, Sat_Lim_Pos_inc_iq_sat_up_1, Sat_Lim_Pos_inc_iq_sat_low_1],
        in_vars=[i_sat, id_hat, iq_hat],
        out_vars=[id_sat_up, id_sat_low, iq_sat_up, iq_sat_low],
        name='Sat. Lim. Pos.'
    )

    Saturation_Amplitude = Block(
        algebraic_eqs=[
            (id - (id_sat_up_1 - sym.abs(id_ref_1))),
            (iq - (iq_sat_up_1 - sym.abs(iq_ref_1))),
            (I - sym.sqrt(((id_1 * id_1) + (iq_1 * iq_1)))),
            (i_sat - (I_1 + iq_pre_1)),
            (Saturation_Amplitude_inc_i_sat - (I_1 + iq_pre_1)),
        ],
        algebraic_vars=[id, iq, I, i_sat, Saturation_Amplitude_inc_i_sat],
        in_vars=[id_ref, iq_ref, id_sat_up, iq_sat_up, iq_pre],
        out_vars=[i_sat],
        name='Saturation Amplitude'
    )

    Saturation_Amplitude = Block(
        algebraic_eqs=[
            (id - (id_sat_up_1 - sym.abs(id_ref_1))),
            (iq - (iq_sat_up_1 - sym.abs(iq_ref_1))),
            (I - sym.sqrt(((id_1 * id_1) + (iq_1 * iq_1)))),
            (i_sat - (I_1 + iq_pre_1)),
            (Saturation_Amplitude_inc_i_sat_1 - (I_1 + iq_pre_1)),
        ],
        algebraic_vars=[id, iq, I, i_sat, Saturation_Amplitude_inc_i_sat_1],
        in_vars=[id_ref, iq_ref, id_sat_up, iq_sat_up, iq_pre],
        out_vars=[i_sat],
        name='Saturation Amplitude'
    )

    Smart_Admittance = Block(
        state_eqs=[
            (((((e1d_1 - u1d_1) - (Smart_Admittance_rv_1 * Smart_Admittance_x1d_va_1)) + (Smart_Admittance_xv_1 * Smart_Admittance_x1q_va_1)) * w1_1) / Smart_Admittance_xv_1),
            (((((e1q_1 - u1q_1) - (Smart_Admittance_xv_1 * Smart_Admittance_x1d_va_1)) - (Smart_Admittance_rv_1 * Smart_Admittance_x1q_va_1)) * w1_1) / Smart_Admittance_xv_1),
            (((((e2d_1 - u2d_1) - (Smart_Admittance_rv_1 * Smart_Admittance_x2d_va_1)) - (Smart_Admittance_xv_1 * Smart_Admittance_x2q_va_1)) * w1_1) / Smart_Admittance_xv_1),
            (((((e2q_1 - u2q_1) + (Smart_Admittance_xv_1 * Smart_Admittance_x2d_va_1)) - (Smart_Admittance_rv_1 * Smart_Admittance_x2q_va_1)) * w1_1) / Smart_Admittance_xv_1),
        ],
        state_vars=[Smart_Admittance_x1d_va, Smart_Admittance_x1q_va, Smart_Admittance_x2d_va, Smart_Admittance_x2q_va],
        algebraic_eqs=[
            (w1 - ((2.0 * 3.141592653589793) * Smart_Admittance_f1_1)),
            (Smart_Admittance_inc_rv_init - Smart_Admittance_rv_1),
            (Smart_Admittance_inc_xv_init - Smart_Admittance_xv_1),
            (rv_init - Smart_Admittance_rv_1),
            (xv_init - Smart_Admittance_xv_1),
            (i1d_hat_dyn - Smart_Admittance_x1d_va_1),
            (i1q_hat_dyn - Smart_Admittance_x1q_va_1),
            (ud_dif - (e1d_1 - u1d_1)),
            (uq_dif - (e1q_1 - u1q_1)),
            (denom - ((Smart_Admittance_rv_1 * Smart_Admittance_rv_1) + (Smart_Admittance_xv_1 * Smart_Admittance_xv_1))),
            (i1d_hat_nodyn - (((Smart_Admittance_rv_1 * ud_dif_1) + (uq_dif_1 * Smart_Admittance_xv_1)) / denom_1)),
            (i1q_hat_nodyn - (((Smart_Admittance_rv_1 * uq_dif_1) - (ud_dif_1 * Smart_Admittance_xv_1)) / denom_1)),
            (Smart_Admittance_T_va_ramp - 0.3),
            (i2d_hat_dyn - Smart_Admittance_x2d_va_1),
            (i2q_hat_dyn - Smart_Admittance_x2q_va_1),
            (u2d_dif - (e2d_1 - u2d_1)),
            (u2q_dif - (e2q_1 - u2q_1)),
            (i2d_hat_nodyn - (((Smart_Admittance_rv_1 * u2d_dif_1) + (u2q_dif_1 * Smart_Admittance_xv_1)) / denom_1)),
            (i2q_hat_nodyn - (((Smart_Admittance_rv_1 * u2q_dif_1) - (u2d_dif_1 * Smart_Admittance_xv_1)) / denom_1)),
            (e_int_d - e1d_1),
            (safe_V1vsc - ((0.01 * sym.heaviside((0.01 - V1vsc_1))) + (V1vsc_1 * (1 - sym.heaviside((0.01 - V1vsc_1)))))),
            (inv_V1vsc - (1.0 / safe_V1vsc_1)),
            (P_dis_normal - ((Smart_Admittance_PmvLim_discharge_1 * sym.heaviside((Smart_Admittance_Pmax_dyn_1 - Smart_Admittance_PmvLim_discharge_1))) + (Smart_Admittance_Pmax_dyn_1 * (1 - sym.heaviside((Smart_Admittance_Pmax_dyn_1 - Smart_Admittance_PmvLim_discharge_1)))))),
            (P_chg_normal - ((Smart_Admittance_PmvLim_charge_1 * sym.heaviside((Smart_Admittance_PmvLim_charge_1 - (-Smart_Admittance_Pmax_dyn_1)))) + ((-Smart_Admittance_Pmax_dyn_1) * (1 - sym.heaviside((Smart_Admittance_PmvLim_charge_1 - (-Smart_Admittance_Pmax_dyn_1))))))),
            (PPCChigh - (Smart_Admittance_PlantEff_1 * ((sym.heaviside((FRT1_flag_1 - 0.5)) * Smart_Admittance_PmvLim_crit_1) + ((1.0 - sym.heaviside((FRT1_flag_1 - 0.5))) * P_dis_normal_1)))),
            (PPCClow - (Smart_Admittance_inv_PlantEff_1 * ((sym.heaviside((FRT1_flag_1 - 0.5)) * (-Smart_Admittance_PmvLim_crit_1)) + ((1.0 - sym.heaviside((FRT1_flag_1 - 0.5))) * P_chg_normal_1)))),
            (idMVhigh - ((((PPCChigh_1 * inv_V1vsc_1) * Smart_Admittance_inv_k_eff_trafo_1) * sym.heaviside((Smart_Admittance_Imax_pu_1 - ((PPCChigh_1 * inv_V1vsc_1) * Smart_Admittance_inv_k_eff_trafo_1)))) + (Smart_Admittance_Imax_pu_1 * (1 - sym.heaviside((Smart_Admittance_Imax_pu_1 - ((PPCChigh_1 * inv_V1vsc_1) * Smart_Admittance_inv_k_eff_trafo_1))))))),
            (idMVlow - ((((PPCClow_1 * inv_V1vsc_1) * Smart_Admittance_k_eff_trafo_1) * sym.heaviside((((PPCClow_1 * inv_V1vsc_1) * Smart_Admittance_k_eff_trafo_1) - (-Smart_Admittance_Imax_pu_1)))) + ((-Smart_Admittance_Imax_pu_1) * (1 - sym.heaviside((((PPCClow_1 * inv_V1vsc_1) * Smart_Admittance_k_eff_trafo_1) - (-Smart_Admittance_Imax_pu_1))))))),
            (lim1 - ((safe_V1vsc_1 - Smart_Admittance_VdcRef_1) * Smart_Admittance_inv_Xtrafo_Lout_pu_1)),
            (V_max_safe - ((Smart_Admittance_MaxAuxiliaryVoltage_1 * sym.heaviside((Smart_Admittance_MaxTransfoFluxVoltage_1 - Smart_Admittance_MaxAuxiliaryVoltage_1))) + (Smart_Admittance_MaxTransfoFluxVoltage_1 * (1 - sym.heaviside((Smart_Admittance_MaxTransfoFluxVoltage_1 - Smart_Admittance_MaxAuxiliaryVoltage_1)))))),
            (lim2 - ((safe_V1vsc_1 - V_max_safe_1) * Smart_Admittance_inv_Xtrafo_pu_1)),
            (i_cap_raw - ((lim1_1 * sym.heaviside((lim2_1 - lim1_1))) + (lim2_1 * (1 - sym.heaviside((lim2_1 - lim1_1)))))),
            (ImaxCapacitive - (((-Smart_Admittance_Imax_pu_1) * sym.heaviside(((-Smart_Admittance_Imax_pu_1) - i_cap_raw_1))) + (i_cap_raw_1 * (1 - sym.heaviside(((-Smart_Admittance_Imax_pu_1) - i_cap_raw_1)))))),
            (i_ind_raw - ((safe_V1vsc_1 - Smart_Admittance_MinAuxiliaryVoltage_1) * Smart_Admittance_inv_Xtrafo_pu_1)),
            (ImaxInductive - ((Smart_Admittance_Imax_pu_1 * sym.heaviside((i_ind_raw_1 - Smart_Admittance_Imax_pu_1))) + (i_ind_raw_1 * (1 - sym.heaviside((i_ind_raw_1 - Smart_Admittance_Imax_pu_1)))))),
            (id_lim_rect - ((idMVlow_1 * sym.heaviside((idMVlow_1 - ((idMVhigh_1 * sym.heaviside((id_raw - idMVhigh_1))) + (id_raw * (1 - sym.heaviside((id_raw - idMVhigh_1)))))))) + (((idMVhigh_1 * sym.heaviside((id_raw - idMVhigh_1))) + (id_raw * (1 - sym.heaviside((id_raw - idMVhigh_1))))) * (1 - sym.heaviside((idMVlow_1 - ((idMVhigh_1 * sym.heaviside((id_raw - idMVhigh_1))) + (id_raw * (1 - sym.heaviside((id_raw - idMVhigh_1))))))))))),
            (iq_lim_rect - ((ImaxCapacitive_1 * sym.heaviside((ImaxCapacitive_1 - ((ImaxInductive_1 * sym.heaviside((iq_raw - ImaxInductive_1))) + (iq_raw * (1 - sym.heaviside((iq_raw - ImaxInductive_1)))))))) + (((ImaxInductive_1 * sym.heaviside((iq_raw - ImaxInductive_1))) + (iq_raw * (1 - sym.heaviside((iq_raw - ImaxInductive_1))))) * (1 - sym.heaviside((ImaxCapacitive_1 - ((ImaxInductive_1 * sym.heaviside((iq_raw - ImaxInductive_1))) + (iq_raw * (1 - sym.heaviside((iq_raw - ImaxInductive_1))))))))))),
            (I_mag_sq - ((id_lim_rect_1 * id_lim_rect_1) + (iq_lim_rect_1 * iq_lim_rect_1))),
            (I_mag - sym.sqrt(I_mag_sq_1)),
            (iq_prio - (((-Smart_Admittance_Imax_pu_1) * sym.heaviside(((-Smart_Admittance_Imax_pu_1) - ((Smart_Admittance_Imax_pu_1 * sym.heaviside((iq_lim_rect_1 - Smart_Admittance_Imax_pu_1))) + (iq_lim_rect_1 * (1 - sym.heaviside((iq_lim_rect_1 - Smart_Admittance_Imax_pu_1)))))))) + (((Smart_Admittance_Imax_pu_1 * sym.heaviside((iq_lim_rect_1 - Smart_Admittance_Imax_pu_1))) + (iq_lim_rect_1 * (1 - sym.heaviside((iq_lim_rect_1 - Smart_Admittance_Imax_pu_1))))) * (1 - sym.heaviside(((-Smart_Admittance_Imax_pu_1) - ((Smart_Admittance_Imax_pu_1 * sym.heaviside((iq_lim_rect_1 - Smart_Admittance_Imax_pu_1))) + (iq_lim_rect_1 * (1 - sym.heaviside((iq_lim_rect_1 - Smart_Admittance_Imax_pu_1))))))))))),
            (id_avail - sym.sqrt(((0.0 * sym.heaviside((0.0 - ((Smart_Admittance_Imax_pu_1 * Smart_Admittance_Imax_pu_1) - (iq_prio_1 * iq_prio_1))))) + (((Smart_Admittance_Imax_pu_1 * Smart_Admittance_Imax_pu_1) - (iq_prio_1 * iq_prio_1)) * (1 - sym.heaviside((0.0 - ((Smart_Admittance_Imax_pu_1 * Smart_Admittance_Imax_pu_1) - (iq_prio_1 * iq_prio_1))))))))),
            (id_prio - ((sym.heaviside((id_lim_rect_1 - 0.0)) * ((id_lim_rect_1 * sym.heaviside((id_avail_1 - id_lim_rect_1))) + (id_avail_1 * (1 - sym.heaviside((id_avail_1 - id_lim_rect_1)))))) + ((1.0 - sym.heaviside((id_lim_rect_1 - 0.0))) * ((id_lim_rect_1 * sym.heaviside((id_lim_rect_1 - (-id_avail_1)))) + ((-id_avail_1) * (1 - sym.heaviside((id_lim_rect_1 - (-id_avail_1))))))))),
            (scale_bal - ((sym.heaviside((I_mag_1 - Smart_Admittance_Imax_pu_1)) * (Smart_Admittance_Imax_pu_1 / ((1e-06 * sym.heaviside((1e-06 - I_mag_1))) + (I_mag_1 * (1 - sym.heaviside((1e-06 - I_mag_1))))))) + ((1.0 - sym.heaviside((I_mag_1 - Smart_Admittance_Imax_pu_1))) * 1.0))),
            (id_bal - (id_lim_rect_1 * scale_bal_1)),
            (iq_bal - (iq_lim_rect_1 * scale_bal_1)),
            (use_prio_Q - (((1.0 - ((1.0 - sym.heaviside((FRT1_flag_1 - 0.5))) * (1.0 - sym.heaviside((Smart_Admittance_Q_priority_flag_1 - 0.5))))) * 1.0) + ((1.0 - (1.0 - ((1.0 - sym.heaviside((FRT1_flag_1 - 0.5))) * (1.0 - sym.heaviside((Smart_Admittance_Q_priority_flag_1 - 0.5)))))) * 0.0))),
            (id_pos_sat - ((sym.heaviside((use_prio_Q_1 - 0.5)) * id_prio_1) + ((1.0 - sym.heaviside((use_prio_Q_1 - 0.5))) * id_bal_1))),
            (iq_pos_sat - ((sym.heaviside((use_prio_Q_1 - 0.5)) * iq_prio_1) + ((1.0 - sym.heaviside((use_prio_Q_1 - 0.5))) * iq_bal_1))),
            (scale_final - ((sym.heaviside((I_mag_1 - 1e-06)) * (sym.sqrt(((id_pos_sat_1 * id_pos_sat_1) + (iq_pos_sat_1 * iq_pos_sat_1))) / I_mag_1)) + ((1.0 - sym.heaviside((I_mag_1 - 1e-06))) * 1.0))),
            (I_pos_used - (I_mag_1 * scale_final_1)),
            (I_neg_avail - ((0.0 * sym.heaviside((0.0 - (Smart_Admittance_Imax_pu_1 - I_pos_used_1)))) + ((Smart_Admittance_Imax_pu_1 - I_pos_used_1) * (1 - sym.heaviside((0.0 - (Smart_Admittance_Imax_pu_1 - I_pos_used_1))))))),
            (i2_mag - sym.sqrt(((id2_raw * id2_raw) + (iq2_raw * iq2_raw)))),
            (scale_neg - ((sym.heaviside((i2_mag_1 - I_neg_avail_1)) * (I_neg_avail_1 / ((1e-06 * sym.heaviside((1e-06 - i2_mag_1))) + (i2_mag_1 * (1 - sym.heaviside((1e-06 - i2_mag_1))))))) + ((1.0 - sym.heaviside((i2_mag_1 - I_neg_avail_1))) * 1.0))),
            (id_neg_sat - (id2_raw * scale_neg_1)),
            (iq_neg_sat - (iq2_raw * scale_neg_1)),
            (viol_P - (((1.0 - ((1.0 - sym.heaviside((id_raw - idMVhigh_1))) * (1.0 - sym.heaviside((idMVlow_1 - id_raw))))) * 1.0) + ((1.0 - (1.0 - ((1.0 - sym.heaviside((id_raw - idMVhigh_1))) * (1.0 - sym.heaviside((idMVlow_1 - id_raw)))))) * 0.0))),
            (viol_Q - (((1.0 - ((1.0 - sym.heaviside((iq_raw - ImaxInductive_1))) * (1.0 - sym.heaviside((ImaxCapacitive_1 - iq_raw))))) * 1.0) + ((1.0 - (1.0 - ((1.0 - sym.heaviside((iq_raw - ImaxInductive_1))) * (1.0 - sym.heaviside((ImaxCapacitive_1 - iq_raw)))))) * 0.0))),
            (P_capab_high - PPCChigh_1),
            (P_capab_low - PPCClow_1),
            (Q_capab_high - (safe_V1vsc_1 * sym.abs(ImaxInductive_1))),
            (Q_capab_low - (safe_V1vsc_1 * (-sym.abs(ImaxCapacitive_1)))),
            (i1d_hat - id_pos_sat_1),
            (i1q_hat - iq_pos_sat_1),
            (i2d_hat - id_neg_sat_1),
            (i2q_hat - iq_neg_sat_1),
            (Smart_Admittance_val_V_safe - ((sym.heaviside((0.01 - V1vsc_1)) * 1.0) + ((1.0 - sym.heaviside((0.01 - V1vsc_1))) * V1vsc_1))),
            (Smart_Admittance_inc_x2d_va - 0.0),
            (Smart_Admittance_inc_x2q_va - 0.0),
            (Smart_Admittance_inc_i2d_hat - 0.0),
            (Smart_Admittance_inc_i2q_hat - 0.0),
            (Smart_Admittance_inc_id2_raw - 0.0),
            (Smart_Admittance_inc_iq2_raw - 0.0),
            (Smart_Admittance_inc_e2d - u2d_1),
            (Smart_Admittance_inc_e2q - u2q_1),
            (Smart_Admittance_inc_Overload_Flag - 0.0),
            (Smart_Admittance_inc_FlagLimit - 0.0),
            (Smart_Admittance_inc_PPCChigh - (Smart_Admittance_PlantEff_1 * Smart_Admittance_PmvLim_discharge_1)),
            (Smart_Admittance_inc_PPCClow - (Smart_Admittance_inv_PlantEff_1 * Smart_Admittance_PmvLim_charge_1)),
            (Smart_Admittance_inc_P_capab_high - PPCChigh_1),
            (Smart_Admittance_inc_P_capab_low - PPCClow_1),
            (Smart_Admittance_inc_idMVhigh - Smart_Admittance_Imax_pu_1),
            (Smart_Admittance_inc_idMVlow - ((-1.0) * Smart_Admittance_Imax_pu_1)),
            (Smart_Admittance_inc_ImaxCapacitive - ((-1.0) * Smart_Admittance_Imax_pu_1)),
            (Smart_Admittance_inc_ImaxInductive - Smart_Admittance_Imax_pu_1),
            (Smart_Admittance_inc_Q_capab_high - (V1vsc_1 * Smart_Admittance_Imax_pu_1)),
            (Smart_Admittance_inc_Q_capab_low - ((-V1vsc_1) * Smart_Admittance_Imax_pu_1)),
            (Smart_Admittance_inc_id_neg_sat - 0.0),
            (Smart_Admittance_inc_iq_neg_sat - 0.0),
        ],
        algebraic_vars=[w1, Smart_Admittance_inc_rv_init, Smart_Admittance_inc_xv_init, rv_init, xv_init, i1d_hat_dyn, i1q_hat_dyn, ud_dif, uq_dif, denom, i1d_hat_nodyn, i1q_hat_nodyn, Smart_Admittance_T_va_ramp, i2d_hat_dyn, i2q_hat_dyn, u2d_dif, u2q_dif, i2d_hat_nodyn, i2q_hat_nodyn, e_int_d, safe_V1vsc, inv_V1vsc, P_dis_normal, P_chg_normal, PPCChigh, PPCClow, idMVhigh, idMVlow, lim1, V_max_safe, lim2, i_cap_raw, ImaxCapacitive, i_ind_raw, ImaxInductive, id_lim_rect, iq_lim_rect, I_mag_sq, I_mag, iq_prio, id_avail, id_prio, scale_bal, id_bal, iq_bal, use_prio_Q, id_pos_sat, iq_pos_sat, scale_final, I_pos_used, I_neg_avail, i2_mag, scale_neg, id_neg_sat, iq_neg_sat, viol_P, viol_Q, P_capab_high, P_capab_low, Q_capab_high, Q_capab_low, i1d_hat, i1q_hat, i2d_hat, i2q_hat, Smart_Admittance_val_V_safe, Smart_Admittance_inc_x2d_va, Smart_Admittance_inc_x2q_va, Smart_Admittance_inc_i2d_hat, Smart_Admittance_inc_i2q_hat, Smart_Admittance_inc_id2_raw, Smart_Admittance_inc_iq2_raw, Smart_Admittance_inc_e2d, Smart_Admittance_inc_e2q, Smart_Admittance_inc_Overload_Flag, Smart_Admittance_inc_FlagLimit, Smart_Admittance_inc_PPCChigh, Smart_Admittance_inc_PPCClow, Smart_Admittance_inc_P_capab_high, Smart_Admittance_inc_P_capab_low, Smart_Admittance_inc_idMVhigh, Smart_Admittance_inc_idMVlow, Smart_Admittance_inc_ImaxCapacitive, Smart_Admittance_inc_ImaxInductive, Smart_Admittance_inc_Q_capab_high, Smart_Admittance_inc_Q_capab_low, Smart_Admittance_inc_id_neg_sat, Smart_Admittance_inc_iq_neg_sat],
        in_vars=[e1d, e1q, e2d, e2q, u1d, u1q, u2d, u2q, V1vsc, FRT1_flag, Pvsc, Qvsc],
        out_vars=[i1d_hat, i1q_hat, i2d_hat, i2q_hat, e_int_d, Overload_Flag, Q_capab_high, Q_capab_low, P_capab_high, P_capab_low, xv_init, rv_init],
        name='Smart_Admittance'
    )
    Smart_Admittance.diff_vars = [d_Smart_Admittance_x1d_va, d_Smart_Admittance_x1q_va, d_Smart_Admittance_x2d_va, d_Smart_Admittance_x2q_va]
    Smart_Admittance.event_dict = {
        Smart_Admittance_xv: vf.add_const(None, name='xv'),
        Smart_Admittance_rv: vf.add_const(None, name='rv'),
        Smart_Admittance_f1: vf.add_const(None, name='f1'),
        Smart_Admittance_va_mode: vf.add_const(None, name='va_mode'),
        Smart_Admittance_Imax_pu: vf.add_const(None, name='Imax_pu'),
        Smart_Admittance_PlantEff: vf.add_const(None, name='PlantEff'),
        Smart_Admittance_Q_priority_flag: vf.add_const(None, name='Q_priority_flag'),
        Smart_Admittance_MaxTransfoFluxVoltage: vf.add_const(None, name='MaxTransfoFluxVoltage'),
        Smart_Admittance_MinAuxiliaryVoltage: vf.add_const(None, name='MinAuxiliaryVoltage'),
        Smart_Admittance_inv_Xtrafo_pu: vf.add_const(None, name='inv_Xtrafo_pu'),
        Smart_Admittance_PmvLim_discharge: vf.add_const(None, name='PmvLim_discharge'),
        Smart_Admittance_PmvLim_charge: vf.add_const(None, name='PmvLim_charge'),
        Smart_Admittance_Pmax_dyn: vf.add_const(None, name='Pmax_dyn'),
        Smart_Admittance_PmvLim_crit: vf.add_const(None, name='PmvLim_crit'),
        Smart_Admittance_inv_PlantEff: vf.add_const(None, name='inv_PlantEff'),
        Smart_Admittance_k_eff_trafo: vf.add_const(None, name='k_eff_trafo'),
        Smart_Admittance_inv_k_eff_trafo: vf.add_const(None, name='inv_k_eff_trafo'),
        Smart_Admittance_VdcRef: vf.add_const(None, name='VdcRef'),
        Smart_Admittance_inv_Xtrafo_Lout_pu: vf.add_const(None, name='inv_Xtrafo_Lout_pu'),
        Smart_Admittance_MaxAuxiliaryVoltage: vf.add_const(None, name='MaxAuxiliaryVoltage'),
    }

    Synchronization_Loop = Block(
        algebraic_eqs=[
            (Synchronization_Loop_inc_Pref - Ppcc_1),
            (Synchronization_Loop_inc_xP - Ppcc_1),
            (Synchronization_Loop_inc_Pf - Ppcc_1),
            (Synchronization_Loop_inc_wref - 1.0),
            (Synchronization_Loop_inc_xw_1 - 1.0),
            (Synchronization_Loop_inc_w_1 - 1.0),
            (Synchronization_Loop_inc_delta_1 - sym.atan2(sindelta_1, cosdelta_1)),
        ],
        algebraic_vars=[Synchronization_Loop_inc_Pref, Synchronization_Loop_inc_xP, Synchronization_Loop_inc_Pf, Synchronization_Loop_inc_wref, Synchronization_Loop_inc_xw_1, Synchronization_Loop_inc_w_1, Synchronization_Loop_inc_delta_1],
        in_vars=[wpcc, P_capab_high, wref, Pref, P_capab_low, Ppcc],
        out_vars=[w, cosdelta, sindelta],
        name='Synchronization Loop'
    )
    Synchronization_Loop.event_dict = {
        Synchronization_Loop_H: vf.add_const(None, name='H'),
        Synchronization_Loop_KD: vf.add_const(None, name='KD'),
        Synchronization_Loop_tau_P: vf.add_const(None, name='tau_P'),
        Synchronization_Loop_f1: vf.add_const(None, name='f1'),
    }

    Synchronization_Loop = Block(
        algebraic_eqs=[
            (Synchronization_Loop_inc_xw_2 - 0.0),
            (Synchronization_Loop_inc_xt_1 - delta),
            (Synchronization_Loop_inc_xp_lim_1 - Pmeas_1),
            (Synchronization_Loop_inc_xP_fil_1 - Pmeas_1),
            (Synchronization_Loop_inc_delta_2 - sym.atan2(sindelta_1, cosdelta_1)),
            (Synchronization_Loop_inc_w_2 - wset_1),
            (Synchronization_Loop_inc_wset_1 - 1.0),
            (Synchronization_Loop_inc_Pset_1 - Pmeas_1),
        ],
        algebraic_vars=[Synchronization_Loop_inc_xw_2, Synchronization_Loop_inc_xt_1, Synchronization_Loop_inc_xp_lim_1, Synchronization_Loop_inc_xP_fil_1, Synchronization_Loop_inc_delta_2, Synchronization_Loop_inc_w_2, Synchronization_Loop_inc_wset_1, Synchronization_Loop_inc_Pset_1],
        in_vars=[wset, wref, P_capab_high, P_capab_low, Pset, Pmeas, flag_overload],
        out_vars=[w, cosdelta, sindelta],
        name='Synchronization Loop'
    )
    Synchronization_Loop.event_dict = {
        Synchronization_Loop_H_1: vf.add_const(None, name='H'),
        Synchronization_Loop_Kdroop_f: vf.add_const(None, name='Kdroop_f'),
        Synchronization_Loop_K_fil_meas: vf.add_const(None, name='K_fil_meas'),
        Synchronization_Loop_tau_P_1: vf.add_const(None, name='tau_P'),
        Synchronization_Loop_KD_1: vf.add_const(None, name='KD'),
        Synchronization_Loop_f1_1: vf.add_const(None, name='f1'),
    }

    V_f_control_signals_md = Block(
        state_eqs=[
            V_f_control_signals_md_mV_1,
            V_f_control_signals_md_mf_1,
        ],
        state_vars=[V_f_control_signals_md_RV, V_f_control_signals_md_Rf],
        algebraic_eqs=[
            (f - ((f0 + V_f_control_signals_md_Df_1) + V_f_control_signals_md_Rf_1)),
            (V_f_control_signals_md_inc_Rf - 0.0),
            (V_f_control_signals_md_inc_f0 - (f_1 - V_f_control_signals_md_Df_1)),
            (V - ((V0 + V_f_control_signals_md_DV_1) + V_f_control_signals_md_RV_1)),
            (V_f_control_signals_md_inc_RV - 0.0),
            (V_f_control_signals_md_inc_V0 - (V_1 - V_f_control_signals_md_DV_1)),
        ],
        algebraic_vars=[f, V_f_control_signals_md_inc_Rf, V_f_control_signals_md_inc_f0, V, V_f_control_signals_md_inc_RV, V_f_control_signals_md_inc_V0],
        out_vars=[V, f],
        name='V&f control signals md'
    )
    V_f_control_signals_md.diff_vars = [d_V_f_control_signals_md_RV, d_V_f_control_signals_md_Rf]
    V_f_control_signals_md.event_dict = {
        V_f_control_signals_md_DV: vf.add_const(None, name='DV'),
        V_f_control_signals_md_Df: vf.add_const(None, name='Df'),
        V_f_control_signals_md_mV: vf.add_const(None, name='mV'),
        V_f_control_signals_md_mf: vf.add_const(None, name='mf'),
    }

    VSC_Measurements = Block(
        algebraic_eqs=[
            (u1r - ((1.0 / 3.0) * ((((uar_1 - ((1.0 / 2.0) * ubr_1)) - ((1.0 / 2.0) * ucr_1)) - ((sym.sqrt(3.0) / 2.0) * ubi_1)) + ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u1i - ((1.0 / 3.0) * ((((uai_1 - ((1.0 / 2.0) * ubi_1)) - ((1.0 / 2.0) * uci_1)) + ((sym.sqrt(3.0) / 2.0) * ubr_1)) - ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (u2r - ((1.0 / 3.0) * ((((uar_1 - ((1.0 / 2.0) * ubr_1)) - ((1.0 / 2.0) * ucr_1)) + ((sym.sqrt(3.0) / 2.0) * ubi_1)) - ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u2i - ((1.0 / 3.0) * ((((uai_1 - ((1.0 / 2.0) * ubi_1)) - ((1.0 / 2.0) * uci_1)) - ((sym.sqrt(3.0) / 2.0) * ubr_1)) + ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (i1r - ((1.0 / 3.0) * ((((iar_1 - ((1.0 / 2.0) * ibr_1)) - ((1.0 / 2.0) * icr_1)) - ((sym.sqrt(3.0) / 2.0) * ibi_1)) + ((sym.sqrt(3.0) / 2.0) * ici_1)))),
            (i1i - ((1.0 / 3.0) * ((((iai_1 - ((1.0 / 2.0) * ibi_1)) - ((1.0 / 2.0) * ici_1)) + ((sym.sqrt(3.0) / 2.0) * ibr_1)) - ((sym.sqrt(3.0) / 2.0) * icr_1)))),
            (i2r - ((1.0 / 3.0) * ((((iar_1 - ((1.0 / 2.0) * ibr_1)) - ((1.0 / 2.0) * icr_1)) + ((sym.sqrt(3.0) / 2.0) * ibi_1)) - ((sym.sqrt(3.0) / 2.0) * ici_1)))),
            (i2i - ((1.0 / 3.0) * ((((iai_1 - ((1.0 / 2.0) * ibi_1)) - ((1.0 / 2.0) * ici_1)) - ((sym.sqrt(3.0) / 2.0) * ibr_1)) + ((sym.sqrt(3.0) / 2.0) * icr_1)))),
            (u1d - ((u1r_1 * cosdelta_1) + (u1i_1 * sindelta_1))),
            (u1q - (((-u1r_1) * sindelta_1) + (u1i_1 * cosdelta_1))),
            (u2d - ((u2r_1 * cosdelta_1) - (u2i_1 * sindelta_1))),
            (u2q - ((u2r_1 * sindelta_1) + (u2i_1 * cosdelta_1))),
            (i1d - ((i1r_1 * cosdelta_1) + (i1i_1 * sindelta_1))),
            (i1q - (((-i1r_1) * sindelta_1) + (i1i_1 * cosdelta_1))),
            (i2d - ((i2r_1 * cosdelta_1) - (i2i_1 * sindelta_1))),
            (i2q - ((i2r_1 * sindelta_1) + (i2i_1 * cosdelta_1))),
            (VSC_Measurements_P1pcc - ((u1r_1 * i1r_1) + (u1i_1 * i1i_1))),
            (VSC_Measurements_P2pcc - ((u2r_1 * i2r_1) + (u2i_1 * i2i_1))),
            (VSC_Measurements_Q1pcc - ((u1i_1 * i1r_1) - (u1r_1 * i1i_1))),
            (VSC_Measurements_Q2pcc - ((u2i_1 * i2r_1) - (u2r_1 * i2i_1))),
            (P - ((u1r_1 * i1r_1) + (u1i_1 * i1i_1))),
            (Q - ((u1i_1 * i1r_1) - (u1r_1 * i1i_1))),
            (V - sym.sqrt(((u1r_1 * u1r_1) + (u1i_1 * u1i_1)))),
            (delta_1 - (sym.atan2(u1i_1, u1r_1) + sym.atan2(((P_1 * VSC_Measurements_lv_1) - (Q_1 * VSC_Measurements_rv_1)), (((P_1 * VSC_Measurements_rv_1) + (Q_1 * VSC_Measurements_lv_1)) + (V_1 * V_1))))),
            (Ia - sym.sqrt(((iar_1 * iar_1) + (iai_1 * iai_1)))),
            (Ib - sym.sqrt(((ibr_1 * ibr_1) + (ibi_1 * ibi_1)))),
            (Ic - sym.sqrt(((icr_1 * icr_1) + (ici_1 * ici_1)))),
            (VSC_Measurements_inc_cosdelta - sym.cos(delta)),
            (VSC_Measurements_inc_sindelta - sym.sin(delta)),
            (VSC_Measurements_inc_u1d - ((u1r_1 * cosdelta_1) + (u1i_1 * sindelta_1))),
            (VSC_Measurements_inc_u1q - (((-u1r_1) * sindelta_1) + (u1i_1 * cosdelta_1))),
            (VSC_Measurements_inc_u2d - ((u2r_1 * cosdelta_1) - (u2i_1 * sindelta_1))),
            (VSC_Measurements_inc_u2q - ((u2r_1 * sindelta_1) + (u2i_1 * cosdelta_1))),
            (VSC_Measurements_inc_i1d - ((i1r_1 * cosdelta_1) + (i1i_1 * sindelta_1))),
            (VSC_Measurements_inc_i1q - (((-i1r_1) * sindelta_1) + (i1i_1 * cosdelta_1))),
            (VSC_Measurements_inc_i2d - ((i2r_1 * cosdelta_1) - (i2i_1 * sindelta_1))),
            (VSC_Measurements_inc_i2q - ((i2r_1 * sindelta_1) + (i2i_1 * cosdelta_1))),
        ],
        algebraic_vars=[u1r, u1i, u2r, u2i, i1r, i1i, i2r, i2i, u1d, u1q, u2d, u2q, i1d, i1q, i2d, i2q, VSC_Measurements_P1pcc, VSC_Measurements_P2pcc, VSC_Measurements_Q1pcc, VSC_Measurements_Q2pcc, P, Q, V, delta_1, Ia, Ib, Ic, VSC_Measurements_inc_cosdelta, VSC_Measurements_inc_sindelta, VSC_Measurements_inc_u1d, VSC_Measurements_inc_u1q, VSC_Measurements_inc_u2d, VSC_Measurements_inc_u2q, VSC_Measurements_inc_i1d, VSC_Measurements_inc_i1q, VSC_Measurements_inc_i2d, VSC_Measurements_inc_i2q],
        in_vars=[uar, uai, ubr, ubi, ucr, uci, iar, iai, ibr, ibi, icr, ici, cosdelta, sindelta],
        out_vars=[u1d, u1q, u2d, u2q, i1d, i1q, i2d, i2q, imag_inst],
        name='VSC Measurements'
    )
    VSC_Measurements.event_dict = {
        VSC_Measurements_lv: vf.add_const(None, name='lv'),
        VSC_Measurements_rv: vf.add_const(None, name='rv'),
    }

    VSC_Measurements = Block(
        algebraic_eqs=[
            (Pvsc - ((((((uar_1 * iar_1) + (uai_1 * iai_1)) + (ubr_1 * ibr_1)) + (ubi_1 * ibi_1)) + (ucr_1 * icr_1)) + (uci_1 * ici_1))),
            (Qvsc - ((((((uai_1 * iar_1) - (uar_1 * iai_1)) + (ubi_1 * ibr_1)) - (ubr_1 * ibi_1)) + (uci_1 * icr_1)) - (ucr_1 * ici_1))),
            (u1r - ((1.0 / 3.0) * ((((uar_1 - (0.5 * ubr_1)) - (0.5 * ucr_1)) - ((sym.sqrt(3.0) / 2.0) * ubi_1)) + ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u1i - ((1.0 / 3.0) * ((((uai_1 - (0.5 * ubi_1)) - (0.5 * uci_1)) + ((sym.sqrt(3.0) / 2.0) * ubr_1)) - ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (u2r - ((1.0 / 3.0) * ((((uar_1 - (0.5 * ubr_1)) - (0.5 * ucr_1)) + ((sym.sqrt(3.0) / 2.0) * ubi_1)) - ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u2i - ((1.0 / 3.0) * ((((uai_1 - (0.5 * ubi_1)) - (0.5 * uci_1)) - ((sym.sqrt(3.0) / 2.0) * ubr_1)) + ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (VSC_Measurements_i1r - ((1.0 / 3.0) * ((((iar_1 - (0.5 * ibr_1)) - (0.5 * icr_1)) - ((sym.sqrt(3.0) / 2.0) * ibi_1)) + ((sym.sqrt(3.0) / 2.0) * ici_1)))),
            (VSC_Measurements_i1i - ((1.0 / 3.0) * ((((iai_1 - (0.5 * ibi_1)) - (0.5 * ici_1)) + ((sym.sqrt(3.0) / 2.0) * ibr_1)) - ((sym.sqrt(3.0) / 2.0) * icr_1)))),
            (VSC_Measurements_i2r - ((1.0 / 3.0) * ((((iar_1 - (0.5 * ibr_1)) - (0.5 * icr_1)) + ((sym.sqrt(3.0) / 2.0) * ibi_1)) - ((sym.sqrt(3.0) / 2.0) * ici_1)))),
            (VSC_Measurements_i2i - ((1.0 / 3.0) * ((((iai_1 - (0.5 * ibi_1)) - (0.5 * ici_1)) - ((sym.sqrt(3.0) / 2.0) * ibr_1)) + ((sym.sqrt(3.0) / 2.0) * icr_1)))),
            (V1vsc - sym.sqrt(((u1r_1 * u1r_1) + (u1i_1 * u1i_1)))),
            (V2vsc - sym.sqrt(((u2r_1 * u2r_1) + (u2i_1 * u2i_1)))),
            (VSC_Measurements_inc_Pvsc - ((((((uar_1 * iar_1) + (uai_1 * iai_1)) + (ubr_1 * ibr_1)) + (ubi_1 * ibi_1)) + (ucr_1 * icr_1)) + (uci_1 * ici_1))),
            (VSC_Measurements_inc_Qvsc - ((((((uai_1 * iar_1) - (uar_1 * iai_1)) + (ubi_1 * ibr_1)) - (ubr_1 * ibi_1)) + (uci_1 * icr_1)) - (ucr_1 * ici_1))),
            (VSC_Measurements_inc_V1vsc - sym.sqrt(((u1r_1 * u1r_1) + (u1i_1 * u1i_1)))),
            (VSC_Measurements_inc_V2vsc - sym.sqrt(((u2r_1 * u2r_1) + (u2i_1 * u2i_1)))),
        ],
        algebraic_vars=[Pvsc, Qvsc, u1r, u1i, u2r, u2i, VSC_Measurements_i1r, VSC_Measurements_i1i, VSC_Measurements_i2r, VSC_Measurements_i2i, V1vsc, V2vsc, VSC_Measurements_inc_Pvsc, VSC_Measurements_inc_Qvsc, VSC_Measurements_inc_V1vsc, VSC_Measurements_inc_V2vsc],
        in_vars=[uar, uai, ubr, ubi, ucr, uci, iar, iai, ibr, ibi, icr, ici],
        out_vars=[Pvsc, Qvsc, V1vsc, V2vsc],
        name='VSC Measurements'
    )

    VSC_abc_to_dq = Block(
        algebraic_eqs=[
            (u1r - ((1.0 / 3.0) * ((((uar_1 - (0.5 * ubr_1)) - (0.5 * ucr_1)) - ((sym.sqrt(3.0) / 2.0) * ubi_1)) + ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u1i - ((1.0 / 3.0) * ((((uai_1 - (0.5 * ubi_1)) - (0.5 * uci_1)) + ((sym.sqrt(3.0) / 2.0) * ubr_1)) - ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (u2r - ((1.0 / 3.0) * ((((uar_1 - (0.5 * ubr_1)) - (0.5 * ucr_1)) + ((sym.sqrt(3.0) / 2.0) * ubi_1)) - ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (u2i - ((1.0 / 3.0) * ((((uai_1 - (0.5 * ubi_1)) - (0.5 * uci_1)) - ((sym.sqrt(3.0) / 2.0) * ubr_1)) + ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (u1d - ((u1r_1 * cosdelta_1) + (u1i_1 * sindelta_1))),
            (u1q - (((-u1r_1) * sindelta_1) + (u1i_1 * cosdelta_1))),
            (u2d - ((u2r_1 * cosdelta_1) - (u2i_1 * sindelta_1))),
            (u2q - ((u2r_1 * sindelta_1) + (u2i_1 * cosdelta_1))),
            (VSC_abc_to_dq_val_u1r - ((1.0 / 3.0) * ((((uar_1 - (0.5 * ubr_1)) - (0.5 * ucr_1)) - ((sym.sqrt(3.0) / 2.0) * ubi_1)) + ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (VSC_abc_to_dq_val_u1i - ((1.0 / 3.0) * ((((uai_1 - (0.5 * ubi_1)) - (0.5 * uci_1)) + ((sym.sqrt(3.0) / 2.0) * ubr_1)) - ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
            (val_angle_E - sym.atan2(u1i_1, u1r_1)),
            (VSC_abc_to_dq_val_cos - sym.cos(val_angle_E_1)),
            (VSC_abc_to_dq_val_sin - sym.sin(val_angle_E_1)),
            (VSC_abc_to_dq_inc_val_angle_E - sym.atan2(u1i_1, u1r_1)),
            (VSC_abc_to_dq_val_u2r - ((1.0 / 3.0) * ((((uar_1 - (0.5 * ubr_1)) - (0.5 * ucr_1)) + ((sym.sqrt(3.0) / 2.0) * ubi_1)) - ((sym.sqrt(3.0) / 2.0) * uci_1)))),
            (VSC_abc_to_dq_val_u2i - ((1.0 / 3.0) * ((((uai_1 - (0.5 * ubi_1)) - (0.5 * uci_1)) - ((sym.sqrt(3.0) / 2.0) * ubr_1)) + ((sym.sqrt(3.0) / 2.0) * ucr_1)))),
        ],
        algebraic_vars=[u1r, u1i, u2r, u2i, u1d, u1q, u2d, u2q, VSC_abc_to_dq_val_u1r, VSC_abc_to_dq_val_u1i, val_angle_E, VSC_abc_to_dq_val_cos, VSC_abc_to_dq_val_sin, VSC_abc_to_dq_inc_val_angle_E, VSC_abc_to_dq_val_u2r, VSC_abc_to_dq_val_u2i],
        in_vars=[uar, uai, ubr, ubi, ucr, uci, iar, iai, ibr, ibi, icr, ici, cosdelta, sindelta],
        out_vars=[u1d, u1q, u2d, u2q, val_angle_E],
        name='VSC abc_to_dq'
    )

    Vac_Events = Block(
        state_eqs=[
            Vac_Events_ROCOF_1,
            ((Vac_Events_f_1 * 2.0) * 3.141592653589793),
        ],
        state_vars=[Vac_Events_f, Vac_Events_d_f],
        algebraic_eqs=[
            (u0 - voltage_jump_1),
            (Vac_Events_f0 - (Vac_Events_f_1 / 50.0)),
            (dphiu - (phase_jump_1 + Vac_Events_d_f_1)),
            (fref - 1.0),
            (Vac_Events_inc_d_f - 0.0),
            (Vac_Events_inc_f - 0.0),
            (Vac_Events_inc_f0 - 1.0),
            (Vac_Events_inc_u0 - 1.0),
            (Vac_Events_inc_fref - 1.0),
            (Vac_Events_inc_dphiu - 0.0),
        ],
        algebraic_vars=[u0, Vac_Events_f0, dphiu, fref, Vac_Events_inc_d_f, Vac_Events_inc_f, Vac_Events_inc_f0, Vac_Events_inc_u0, Vac_Events_inc_fref, Vac_Events_inc_dphiu],
        in_vars=[phase_jump, voltage_jump],
        out_vars=[u0, dphiu, f0_1, fref],
        name='Vac_Events'
    )
    Vac_Events.diff_vars = [d_Vac_Events_f, d_Vac_Events_d_f]
    Vac_Events.event_dict = {
        Vac_Events_t_ROCOF: vf.add_const(None, name='t_ROCOF'),
        Vac_Events_ROCOF: vf.add_const(None, name='ROCOF'),
        Vac_Events_param_f_ref: vf.add_const(None, name='param_f_ref'),
    }

    Virtual_Admittance = Block(
        state_eqs=[
            (((((e1d_1 - u1d_1) - (Virtual_Admittance_rv_1 * Virtual_Admittance_x1d_va_1)) + (Virtual_Admittance_xv_1 * Virtual_Admittance_x1q_va_1)) * w1_1) / Virtual_Admittance_xv_1),
            (((((e1q_1 - u1q_1) - (Virtual_Admittance_xv_1 * Virtual_Admittance_x1d_va_1)) - (Virtual_Admittance_rv_1 * Virtual_Admittance_x1q_va_1)) * w1_1) / Virtual_Admittance_xv_1),
            (((((e2d_1 - u2d_1) - (Virtual_Admittance_rv_1 * Virtual_Admittance_x2d_va_1)) - (Virtual_Admittance_xv_1 * Virtual_Admittance_x2q_va_1)) * w1_1) / Virtual_Admittance_xv_1),
            (((((e2q_1 - u2q_1) + (Virtual_Admittance_xv_1 * Virtual_Admittance_x2d_va_1)) - (Virtual_Admittance_rv_1 * Virtual_Admittance_x2q_va_1)) * w1_1) / Virtual_Admittance_xv_1),
        ],
        state_vars=[Virtual_Admittance_x1d_va, Virtual_Admittance_x1q_va, Virtual_Admittance_x2d_va, Virtual_Admittance_x2q_va],
        algebraic_eqs=[
            (w1 - ((2.0 * 3.141592653589793) * Virtual_Admittance_f1_1)),
            (i1d_hat - Virtual_Admittance_x1d_va_1),
            (i1q_hat - Virtual_Admittance_x1q_va_1),
            (i2d_hat - Virtual_Admittance_x2d_va_1),
            (i2q_hat - Virtual_Admittance_x2q_va_1),
            (Virtual_Admittance_inc_x1d_va - i1d_hat_1),
            (Virtual_Admittance_inc_x1q_va - i1q_hat_1),
            (Virtual_Admittance_inc_e1d - ((u1d_1 + (Virtual_Admittance_rv_1 * Virtual_Admittance_x1d_va_1)) - (Virtual_Admittance_xv_1 * Virtual_Admittance_x1q_va_1))),
            (Virtual_Admittance_inc_e1q - ((u1q_1 + (Virtual_Admittance_xv_1 * Virtual_Admittance_x1d_va_1)) + (Virtual_Admittance_rv_1 * Virtual_Admittance_x1q_va_1))),
            (Virtual_Admittance_inc_x2d_va - i2d_hat_1),
            (Virtual_Admittance_inc_x2q_va - i2q_hat_1),
            (Virtual_Admittance_inc_e2d - ((u2d_1 + (Virtual_Admittance_rv_1 * Virtual_Admittance_x2d_va_1)) + (Virtual_Admittance_xv_1 * Virtual_Admittance_x2q_va_1))),
            (Virtual_Admittance_inc_e2q - ((u2q_1 - (Virtual_Admittance_xv_1 * Virtual_Admittance_x2d_va_1)) + (Virtual_Admittance_rv_1 * Virtual_Admittance_x2q_va_1))),
        ],
        algebraic_vars=[w1, i1d_hat, i1q_hat, i2d_hat, i2q_hat, Virtual_Admittance_inc_x1d_va, Virtual_Admittance_inc_x1q_va, Virtual_Admittance_inc_e1d, Virtual_Admittance_inc_e1q, Virtual_Admittance_inc_x2d_va, Virtual_Admittance_inc_x2q_va, Virtual_Admittance_inc_e2d, Virtual_Admittance_inc_e2q],
        in_vars=[e1d, e1q, e2d, e2q, u1d, u1q, u2d, u2q],
        out_vars=[i1d_hat, i1q_hat, i2d_hat, i2q_hat],
        name='Virtual Admittance'
    )
    Virtual_Admittance.diff_vars = [d_Virtual_Admittance_x1d_va, d_Virtual_Admittance_x1q_va, d_Virtual_Admittance_x2d_va, d_Virtual_Admittance_x2q_va]
    Virtual_Admittance.event_dict = {
        Virtual_Admittance_xv: vf.add_const(None, name='xv'),
        Virtual_Admittance_rv: vf.add_const(None, name='rv'),
        Virtual_Admittance_f1: vf.add_const(None, name='f1'),
    }

    angle_integrator = Block(
        state_eqs=[
            (Dw_1 * w_r_1),
        ],
        state_vars=[angle_integrator_x],
        algebraic_eqs=[
            (w_r - (6.283185307179586 * angle_integrator_f1_1)),
            (delta_1 - angle_integrator_x_1),
        ],
        algebraic_vars=[w_r, delta_1],
        in_vars=[Dw],
        out_vars=[delta_1],
        name='angle integrator'
    )
    angle_integrator.diff_vars = [d_angle_integrator_x]
    angle_integrator.event_dict = {
        angle_integrator_f1: vf.add_const(None, name='f1'),
    }

    dq2ab = Block(
        algebraic_eqs=[
            (u1r_ref - ((u1d_ref_1 * cosdelta_1) - (u1q_ref_1 * sindelta_1))),
            (u1i_ref - ((u1d_ref_1 * sindelta_1) + (u1q_ref_1 * cosdelta_1))),
            (u2r_ref - ((u2d_ref_1 * cosdelta_1) + (u2q_ref_1 * sindelta_1))),
            (u2i_ref - (((-u2d_ref_1) * sindelta_1) + (u2q_ref_1 * cosdelta_1))),
            (dq2ab_inc_u1d_ref - ((u1r_ref_1 * cosdelta_1) + (u1i_ref_1 * sindelta_1))),
            (dq2ab_inc_u1q_ref - (((-u1r_ref_1) * sindelta_1) + (u1i_ref_1 * cosdelta_1))),
            (dq2ab_inc_u2d_ref - ((u2r_ref_1 * cosdelta_1) - (u2i_ref_1 * sindelta_1))),
            (dq2ab_inc_u2q_ref - ((u2r_ref_1 * sindelta_1) + (u2i_ref_1 * cosdelta_1))),
        ],
        algebraic_vars=[u1r_ref, u1i_ref, u2r_ref, u2i_ref, dq2ab_inc_u1d_ref, dq2ab_inc_u1q_ref, dq2ab_inc_u2d_ref, dq2ab_inc_u2q_ref],
        in_vars=[u1d_ref, u1q_ref, u2d_ref, u2q_ref, cosdelta, sindelta],
        out_vars=[u1r_ref, u1i_ref, u2r_ref, u2i_ref],
        name='dq2ab'
    )

    iq_ref = Block(
        in_vars=[iq_ref_in],
        out_vars=[iq_ref],
        name='iq_ref'
    )

    limit_Ipos = Block(
        algebraic_eqs=[
            (limit_Ipos_Ires - 0.1),
            (limit_Ipos_mode - ((sym.heaviside((FRT_pos_flag_1 - 0.5)) * 1.0) + ((1.0 - sym.heaviside((FRT_pos_flag_1 - 0.5))) * 0.0))),
            (limit_Ipos_Id_max_0 - ((sym.heaviside((reactive_reserve_1 - 0.0)) * sym.sqrt(((0.0 * sym.heaviside((0.0 - ((Imax_1 * Imax_1) - (reactive_reserve_1 * reactive_reserve_1))))) + (((Imax_1 * Imax_1) - (reactive_reserve_1 * reactive_reserve_1)) * (1 - sym.heaviside((0.0 - ((Imax_1 * Imax_1) - (reactive_reserve_1 * reactive_reserve_1))))))))) + ((1.0 - sym.heaviside((reactive_reserve_1 - 0.0))) * Imax_1))),
            (limit_Ipos_Iq_max_1 - Imax_1),
            (limit_Ipos_Iq_min_1 - (-Imax_1)),
            (Id_min - ((-1.0) * Id_max_1)),
        ],
        algebraic_vars=[limit_Ipos_Ires, limit_Ipos_mode, limit_Ipos_Id_max_0, limit_Ipos_Iq_max_1, limit_Ipos_Iq_min_1, Id_min],
        in_vars=[id_unsat, iq_unsat, Imax, FRT_pos_flag, ImaxCapacitive, ImaxInductive, reactive_reserve],
        out_vars=[Id_max, Iq_max, Iq_min, Id_min],
        name='limit_Ipos'
    )

    limit_Ipos = Block(
        algebraic_eqs=[
            (limit_Ipos_inc_Id_max - 0.0),
            (limit_Ipos_inc_Iq_max - 0.0),
            (limit_Ipos_inc_Iq_min - 0.0),
            (limit_Ipos_inc_Id_min - 0.0),
            (limit_Ipos_Ires_1 - 0.1),
            (limit_Ipos_Id_max_0_1 - ((sym.heaviside((reactive_reserve_1 - 0.0)) * sym.sqrt(((sym.abs(Imax_1) ** 2.0) - (sym.abs(reactive_reserve_1) ** 2.0)))) + ((1.0 - sym.heaviside((reactive_reserve_1 - 0.0))) * Imax_1))),
            (limit_Ipos_Iq_max_1_1 - Imax_1),
            (limit_Ipos_Iq_min_1_1 - (-Imax_1)),
            (limit_Ipos_theta0 - sym.atan2(iq_unsat_1, id_unsat_1)),
            (Id_min - ((-1.0) * Id_max_1)),
        ],
        algebraic_vars=[limit_Ipos_inc_Id_max, limit_Ipos_inc_Iq_max, limit_Ipos_inc_Iq_min, limit_Ipos_inc_Id_min, limit_Ipos_Ires_1, limit_Ipos_Id_max_0_1, limit_Ipos_Iq_max_1_1, limit_Ipos_Iq_min_1_1, limit_Ipos_theta0, Id_min],
        in_vars=[id_unsat, iq_unsat, Imax, FRT_pos_flag, ImaxCapacitive, ImaxInductive, reactive_reserve],
        out_vars=[Id_max, Iq_max, Iq_min, Id_min],
        name='limit_Ipos'
    )

    simulateCapBlock = Block(
        algebraic_eqs=[
            (simulateCapBlock_inc_QMV_capab_high - (-1.0)),
            (simulateCapBlock_inc_QMV_capab_low - 1.0),
            (simulateCapBlock_inc_PMV_capab_high - 1.0),
            (simulateCapBlock_inc_PMV_capab_low - (-1.0)),
            (simulateCapBlock_inc_id_pos_sat - 0.0),
            (simulateCapBlock_inc_iq_pos_sat - (-0.5)),
            (simulateCapBlock_inc_id_neg_sat - 0.0),
            (simulateCapBlock_inc_iq_neg_sat - 0.0),
            (QMV_capab_high - (-1.0)),
            (QMV_capab_low - 1.0),
            (PMV_capab_high - 1.0),
            (PMV_capab_low - (-1.0)),
            (id_pos_sat - 0.0),
            (iq_pos_sat - (-0.5)),
            (id_neg_sat - 0.0),
            (iq_neg_sat - 0.0),
        ],
        algebraic_vars=[simulateCapBlock_inc_QMV_capab_high, simulateCapBlock_inc_QMV_capab_low, simulateCapBlock_inc_PMV_capab_high, simulateCapBlock_inc_PMV_capab_low, simulateCapBlock_inc_id_pos_sat, simulateCapBlock_inc_iq_pos_sat, simulateCapBlock_inc_id_neg_sat, simulateCapBlock_inc_iq_neg_sat, QMV_capab_high, QMV_capab_low, PMV_capab_high, PMV_capab_low, id_pos_sat, iq_pos_sat, id_neg_sat, iq_neg_sat],
        out_vars=[QMV_capab_high, QMV_capab_low, PMV_capab_high, PMV_capab_low, id_pos_sat, iq_pos_sat, id_neg_sat, iq_neg_sat],
        name='simulateCapBlock'
    )

    w1_s = Block(
        state_eqs=[
            (w1_1 * Dw_1),
        ],
        state_vars=[w1_s_x],
        algebraic_eqs=[
            (w1 - ((2.0 * 3.141592653589793) * w1_s_f1_1)),
            (delta_1 - w1_s_x_1),
            (w1_s_inc_x - delta),
        ],
        algebraic_vars=[w1, delta_1, w1_s_inc_x],
        in_vars=[Dw],
        out_vars=[delta_1],
        name='w1/s'
    )
    w1_s.diff_vars = [d_w1_s_x]
    w1_s.event_dict = {
        w1_s_f1: vf.add_const(None, name='f1'),
    }

    templ.block = Block(
        children=[v_1_2H_s_KD, v_1_2Hs, v_1_2Hs, Capability_and_limitation, Capability_and_limitation, Capability_block, Capability_block, Current_controller, Events, Events, Fault_Detection, Fault_Detection, Grid_electrical_interface, MV_voltage_limit, MV_voltage_limit, PCC_Measurements, PCC_Measurements, Pos_Seq_Current_Limiter, Power_VI_limit, Power_VI_limit, Protection, Q_Vac_droop, Q_Vac_droop, Sat_Lim_Neg, Sat_Lim_Neg, Sat_Lim_Pos, Sat_Lim_Pos, Saturation_Amplitude, Saturation_Amplitude, Smart_Admittance, Synchronization_Loop, Synchronization_Loop, V_f_control_signals_md, VSC_Measurements, VSC_Measurements, VSC_abc_to_dq, Vac_Events, Virtual_Admittance, angle_integrator, dq2ab, iq_ref, limit_Ipos, limit_Ipos, simulateCapBlock, w1_s],
        in_vars=[wset, wref, P_capab_high, P_capab_low, Pset, Pmeas, flag_overload],
        out_vars=[w, cosdelta, sindelta],
        name='Synchronization Loop_subgraph'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_synchronization_loop_emt_template(vf=vf, name='Synchronization Loop' if name is None else name)

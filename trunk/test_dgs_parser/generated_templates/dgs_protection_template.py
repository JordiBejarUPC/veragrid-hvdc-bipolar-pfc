# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\DGS_test_type_models.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import aflipflop, flipflop, picdro, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_protection_emt_template(vf: VarFactory, name: str = 'Protection') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
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

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    ACMonitor_Trip = vf.add_var('ACMonitor_Trip_' + name)
    Freq_Alarm = vf.add_var('Freq_Alarm_' + name)
    LVRT_Alarm = vf.add_var('LVRT_Alarm_' + name)
    LvrtOn = vf.add_var('LvrtOn_' + name)
    Master_Trip = vf.add_var('Master_Trip_' + name)
    OLVRT_Trip = vf.add_var('OLVRT_Trip_' + name)
    OLvrtOn = vf.add_var('OLvrtOn_' + name)
    OR_General = vf.add_var('OR_General_' + name)
    OVRT_Alarm = vf.add_var('OVRT_Alarm_' + name)
    OvrtOn = vf.add_var('OvrtOn_' + name)
    Protection_ACMonitor_Tripping = vf.add_var('Protection__ACMonitor_Tripping_' + name)
    Protection_OLVRT_Alarm = vf.add_var('Protection__OLVRT_Alarm_' + name)
    Protection_OLVRT_Tripping = vf.add_var('Protection__OLVRT_Tripping_' + name)
    Protection_proc_aflipflop_11 = vf.add_var('Protection__proc_aflipflop_11_' + name)
    Protection_proc_aflipflop_3 = vf.add_var('Protection__proc_aflipflop_3_' + name)
    Protection_proc_flipflop_53 = vf.add_var('Protection__proc_flipflop_53_' + name)
    Protection_proc_flipflop_54 = vf.add_var('Protection__proc_flipflop_54_' + name)
    Protection_proc_picdro_10 = vf.add_var('Protection__proc_picdro_10_' + name)
    Protection_proc_picdro_18 = vf.add_var('Protection__proc_picdro_18_' + name)
    Protection_proc_picdro_2 = vf.add_var('Protection__proc_picdro_2_' + name)
    Protection_proc_picdro_21 = vf.add_var('Protection__proc_picdro_21_' + name)
    Protection_proc_picdro_24 = vf.add_var('Protection__proc_picdro_24_' + name)
    Protection_proc_picdro_27 = vf.add_var('Protection__proc_picdro_27_' + name)
    Protection_proc_picdro_30 = vf.add_var('Protection__proc_picdro_30_' + name)
    Protection_proc_picdro_33 = vf.add_var('Protection__proc_picdro_33_' + name)
    Protection_proc_picdro_37 = vf.add_var('Protection__proc_picdro_37_' + name)
    Protection_proc_picdro_40 = vf.add_var('Protection__proc_picdro_40_' + name)
    Protection_proc_picdro_43 = vf.add_var('Protection__proc_picdro_43_' + name)
    Protection_proc_picdro_46 = vf.add_var('Protection__proc_picdro_46_' + name)
    Protection_proc_picdro_49 = vf.add_var('Protection__proc_picdro_49_' + name)
    Protection_proc_select_0 = vf.add_var('Protection__proc_select_0_' + name)
    Protection_proc_select_1 = vf.add_var('Protection__proc_select_1_' + name)
    Protection_proc_select_12 = vf.add_var('Protection__proc_select_12_' + name)
    Protection_proc_select_13 = vf.add_var('Protection__proc_select_13_' + name)
    Protection_proc_select_14 = vf.add_var('Protection__proc_select_14_' + name)
    Protection_proc_select_15 = vf.add_var('Protection__proc_select_15_' + name)
    Protection_proc_select_16 = vf.add_var('Protection__proc_select_16_' + name)
    Protection_proc_select_17 = vf.add_var('Protection__proc_select_17_' + name)
    Protection_proc_select_19 = vf.add_var('Protection__proc_select_19_' + name)
    Protection_proc_select_20 = vf.add_var('Protection__proc_select_20_' + name)
    Protection_proc_select_22 = vf.add_var('Protection__proc_select_22_' + name)
    Protection_proc_select_23 = vf.add_var('Protection__proc_select_23_' + name)
    Protection_proc_select_25 = vf.add_var('Protection__proc_select_25_' + name)
    Protection_proc_select_26 = vf.add_var('Protection__proc_select_26_' + name)
    Protection_proc_select_28 = vf.add_var('Protection__proc_select_28_' + name)
    Protection_proc_select_29 = vf.add_var('Protection__proc_select_29_' + name)
    Protection_proc_select_31 = vf.add_var('Protection__proc_select_31_' + name)
    Protection_proc_select_32 = vf.add_var('Protection__proc_select_32_' + name)
    Protection_proc_select_34 = vf.add_var('Protection__proc_select_34_' + name)
    Protection_proc_select_35 = vf.add_var('Protection__proc_select_35_' + name)
    Protection_proc_select_36 = vf.add_var('Protection__proc_select_36_' + name)
    Protection_proc_select_38 = vf.add_var('Protection__proc_select_38_' + name)
    Protection_proc_select_39 = vf.add_var('Protection__proc_select_39_' + name)
    Protection_proc_select_4 = vf.add_var('Protection__proc_select_4_' + name)
    Protection_proc_select_41 = vf.add_var('Protection__proc_select_41_' + name)
    Protection_proc_select_42 = vf.add_var('Protection__proc_select_42_' + name)
    Protection_proc_select_44 = vf.add_var('Protection__proc_select_44_' + name)
    Protection_proc_select_45 = vf.add_var('Protection__proc_select_45_' + name)
    Protection_proc_select_47 = vf.add_var('Protection__proc_select_47_' + name)
    Protection_proc_select_48 = vf.add_var('Protection__proc_select_48_' + name)
    Protection_proc_select_5 = vf.add_var('Protection__proc_select_5_' + name)
    Protection_proc_select_50 = vf.add_var('Protection__proc_select_50_' + name)
    Protection_proc_select_51 = vf.add_var('Protection__proc_select_51_' + name)
    Protection_proc_select_52 = vf.add_var('Protection__proc_select_52_' + name)
    Protection_proc_select_6 = vf.add_var('Protection__proc_select_6_' + name)
    Protection_proc_select_7 = vf.add_var('Protection__proc_select_7_' + name)
    Protection_proc_select_8 = vf.add_var('Protection__proc_select_8_' + name)
    Protection_proc_select_9 = vf.add_var('Protection__proc_select_9_' + name)
    RoCoF_Alarm = vf.add_var('RoCoF_Alarm_' + name)
    RoCoF_measured = vf.add_var('RoCoF_measured_' + name)
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
    Volt_Alarm = vf.add_var('Volt_Alarm_' + name)
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
    f = vf.add_var('f_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    t = vf.add_var('t_' + name)
    t_LV = vf.add_var('t_LV_' + name)
    t_OV = vf.add_var('t_OV_' + name)
    t_elapsed_LV = vf.add_var('t_elapsed_LV_' + name)
    t_elapsed_OV = vf.add_var('t_elapsed_OV_' + name)
    u_3Ph = vf.add_var('u_3Ph_' + name)
    u_MaxVLL = vf.add_var('u_MaxVLL_' + name)
    u_eval = vf.add_var('u_eval_' + name)
    vLVRT_trip_lim = vf.add_var('vLVRT_trip_lim_' + name)
    vOVRT_trip_lim = vf.add_var('vOVRT_trip_lim_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (t - glob_time),
            (u_eval - ((Protection_proc_select_0 * u_MaxVLL) + ((sym.Const(1.0) - Protection_proc_select_0) * u_3Ph))),
            (LvrtOn - ((Protection_proc_select_1 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_1) * sym.Const(0.0)))),
            (t_LV - Protection_proc_aflipflop_3),
            (t_elapsed_LV - (t - t_LV)),
            (vLVRT_trip_lim - ((Protection_proc_select_7 * Protection_vLV_1) + ((sym.Const(1.0) - Protection_proc_select_7) * ((Protection_proc_select_6 * Protection_vLV_2) + ((sym.Const(1.0) - Protection_proc_select_6) * ((Protection_proc_select_5 * Protection_vLV_3) + ((sym.Const(1.0) - Protection_proc_select_5) * ((Protection_proc_select_4 * Protection_vLV_4) + ((sym.Const(1.0) - Protection_proc_select_4) * Protection_vLV_5))))))))),
            (LVRT_Alarm - ((Protection_proc_select_8 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_8) * sym.Const(0.0)))),
            (OvrtOn - ((Protection_proc_select_9 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_9) * sym.Const(0.0)))),
            (t_OV - Protection_proc_aflipflop_11),
            (t_elapsed_OV - (t - t_OV)),
            (vOVRT_trip_lim - ((Protection_proc_select_15 * Protection_vOV_1) + ((sym.Const(1.0) - Protection_proc_select_15) * ((Protection_proc_select_14 * Protection_vOV_2) + ((sym.Const(1.0) - Protection_proc_select_14) * ((Protection_proc_select_13 * Protection_vOV_3) + ((sym.Const(1.0) - Protection_proc_select_13) * ((Protection_proc_select_12 * Protection_vOV_4) + ((sym.Const(1.0) - Protection_proc_select_12) * Protection_vOV_5))))))))),
            (OVRT_Alarm - ((Protection_proc_select_16 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_16) * sym.Const(0.0)))),
            (en_OF1 - ((Protection_proc_select_17 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_17) * sym.Const(0.0)))),
            (Trip_OF_1 - ((Protection_proc_select_19 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_19) * sym.Const(0.0)))),
            (en_OF2 - ((Protection_proc_select_20 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_20) * sym.Const(0.0)))),
            (Trip_OF_2 - ((Protection_proc_select_22 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_22) * sym.Const(0.0)))),
            (en_OFFast - ((Protection_proc_select_23 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_23) * sym.Const(0.0)))),
            (Trip_OF_Fast - ((Protection_proc_select_25 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_25) * sym.Const(0.0)))),
            (en_UF1 - ((Protection_proc_select_26 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_26) * sym.Const(0.0)))),
            (Trip_UF_1 - ((Protection_proc_select_28 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_28) * sym.Const(0.0)))),
            (en_UF2 - ((Protection_proc_select_29 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_29) * sym.Const(0.0)))),
            (Trip_UF_2 - ((Protection_proc_select_31 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_31) * sym.Const(0.0)))),
            (en_UFFast - ((Protection_proc_select_32 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_32) * sym.Const(0.0)))),
            (Trip_UF_Fast - ((Protection_proc_select_34 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_34) * sym.Const(0.0)))),
            (Freq_Alarm - ((Protection_proc_select_35 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_35) * sym.Const(0.0)))),
            (en_RoCoF - ((Protection_proc_select_36 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_36) * sym.Const(0.0)))),
            (RoCoF_Alarm - ((Protection_proc_select_38 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_38) * sym.Const(0.0)))),
            (en_OV - ((Protection_proc_select_39 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_39) * sym.Const(0.0)))),
            (Trip_OV - ((Protection_proc_select_41 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_41) * sym.Const(0.0)))),
            (en_OVFast - ((Protection_proc_select_42 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_42) * sym.Const(0.0)))),
            (Trip_OV_Fast - ((Protection_proc_select_44 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_44) * sym.Const(0.0)))),
            (en_UV - ((Protection_proc_select_45 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_45) * sym.Const(0.0)))),
            (Trip_UV - ((Protection_proc_select_47 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_47) * sym.Const(0.0)))),
            (en_UVFast - ((Protection_proc_select_48 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_48) * sym.Const(0.0)))),
            (Trip_UV_Fast - ((Protection_proc_select_50 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_50) * sym.Const(0.0)))),
            (Volt_Alarm - ((Protection_proc_select_51 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_51) * sym.Const(0.0)))),
            (OR_General - ((Protection_proc_select_52 * sym.Const(1.0)) + ((sym.Const(1.0) - Protection_proc_select_52) * sym.Const(0.0)))),
            (Protection_OLVRT_Alarm - (sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((LVRT_Alarm - sym.Const(0.5)))) * (sym.Const(1.0) - sym.heaviside((OVRT_Alarm - sym.Const(0.5))))))),
            (Protection_OLVRT_Tripping - (sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((OLvrtOn - sym.Const(0.5)))) * (sym.Const(1.0) - sym.heaviside((Protection_OLVRT_Alarm - sym.Const(0.5))))))),
            (OLVRT_Trip - Protection_proc_flipflop_53),
            (Protection_ACMonitor_Tripping - (sym.Const(1.0) - ((sym.Const(1.0) - (sym.Const(1.0) - ((sym.Const(1.0) - sym.heaviside((Freq_Alarm - sym.Const(0.5)))) * (sym.Const(1.0) - sym.heaviside((RoCoF_Alarm - sym.Const(0.5))))))) * (sym.Const(1.0) - sym.heaviside((Volt_Alarm - sym.Const(0.5))))))),
            (ACMonitor_Trip - Protection_proc_flipflop_54),
            (Master_Trip - (sym.Const(1.0) - ((sym.Const(1.0) - ACMonitor_Trip) * (sym.Const(1.0) - OLVRT_Trip)))),
        ],
        algebraic_vars=[t, u_eval, LvrtOn, t_LV, t_elapsed_LV, vLVRT_trip_lim, LVRT_Alarm, OvrtOn, t_OV, t_elapsed_OV, vOVRT_trip_lim, OVRT_Alarm, en_OF1, Trip_OF_1, en_OF2, Trip_OF_2, en_OFFast, Trip_OF_Fast, en_UF1, Trip_UF_1, en_UF2, Trip_UF_2, en_UFFast, Trip_UF_Fast, Freq_Alarm, en_RoCoF, RoCoF_Alarm, en_OV, Trip_OV, en_OVFast, Trip_OV_Fast, en_UV, Trip_UV, en_UVFast, Trip_UV_Fast, Volt_Alarm, OR_General, Protection_OLVRT_Alarm, Protection_OLVRT_Tripping, OLVRT_Trip, Protection_ACMonitor_Tripping, ACMonitor_Trip, Master_Trip],
        in_vars=[u_3Ph, u_MaxVLL, f, enable, RoCoF_measured, OLvrtOn],
        out_vars=[Master_Trip, OLVRT_Trip, ACMonitor_Trip, LVRT_Alarm, OVRT_Alarm, Freq_Alarm, RoCoF_Alarm],
        name='Protection'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
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
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Protection_proc_select_0: vf.add_const(0.0, name=''),
        Protection_proc_select_1: vf.add_const(0.0, name=''),
        Protection_proc_picdro_2: vf.add_const(0.0, name=''),
        Protection_proc_aflipflop_3: vf.add_const(0.0, name=''),
        Protection_proc_select_4: vf.add_const(0.0, name=''),
        Protection_proc_select_5: vf.add_const(0.0, name=''),
        Protection_proc_select_6: vf.add_const(0.0, name=''),
        Protection_proc_select_7: vf.add_const(0.0, name=''),
        Protection_proc_select_8: vf.add_const(0.0, name=''),
        Protection_proc_select_9: vf.add_const(0.0, name=''),
        Protection_proc_picdro_10: vf.add_const(0.0, name=''),
        Protection_proc_aflipflop_11: vf.add_const(0.0, name=''),
        Protection_proc_select_12: vf.add_const(0.0, name=''),
        Protection_proc_select_13: vf.add_const(0.0, name=''),
        Protection_proc_select_14: vf.add_const(0.0, name=''),
        Protection_proc_select_15: vf.add_const(0.0, name=''),
        Protection_proc_select_16: vf.add_const(0.0, name=''),
        Protection_proc_select_17: vf.add_const(0.0, name=''),
        Protection_proc_picdro_18: vf.add_const(0.0, name=''),
        Protection_proc_select_19: vf.add_const(0.0, name=''),
        Protection_proc_select_20: vf.add_const(0.0, name=''),
        Protection_proc_picdro_21: vf.add_const(0.0, name=''),
        Protection_proc_select_22: vf.add_const(0.0, name=''),
        Protection_proc_select_23: vf.add_const(0.0, name=''),
        Protection_proc_picdro_24: vf.add_const(0.0, name=''),
        Protection_proc_select_25: vf.add_const(0.0, name=''),
        Protection_proc_select_26: vf.add_const(0.0, name=''),
        Protection_proc_picdro_27: vf.add_const(0.0, name=''),
        Protection_proc_select_28: vf.add_const(0.0, name=''),
        Protection_proc_select_29: vf.add_const(0.0, name=''),
        Protection_proc_picdro_30: vf.add_const(0.0, name=''),
        Protection_proc_select_31: vf.add_const(0.0, name=''),
        Protection_proc_select_32: vf.add_const(0.0, name=''),
        Protection_proc_picdro_33: vf.add_const(0.0, name=''),
        Protection_proc_select_34: vf.add_const(0.0, name=''),
        Protection_proc_select_35: vf.add_const(0.0, name=''),
        Protection_proc_select_36: vf.add_const(0.0, name=''),
        Protection_proc_picdro_37: vf.add_const(0.0, name=''),
        Protection_proc_select_38: vf.add_const(0.0, name=''),
        Protection_proc_select_39: vf.add_const(0.0, name=''),
        Protection_proc_picdro_40: vf.add_const(0.0, name=''),
        Protection_proc_select_41: vf.add_const(0.0, name=''),
        Protection_proc_select_42: vf.add_const(0.0, name=''),
        Protection_proc_picdro_43: vf.add_const(0.0, name=''),
        Protection_proc_select_44: vf.add_const(0.0, name=''),
        Protection_proc_select_45: vf.add_const(0.0, name=''),
        Protection_proc_picdro_46: vf.add_const(0.0, name=''),
        Protection_proc_select_47: vf.add_const(0.0, name=''),
        Protection_proc_select_48: vf.add_const(0.0, name=''),
        Protection_proc_picdro_49: vf.add_const(0.0, name=''),
        Protection_proc_select_50: vf.add_const(0.0, name=''),
        Protection_proc_select_51: vf.add_const(0.0, name=''),
        Protection_proc_select_52: vf.add_const(0.0, name=''),
        Protection_proc_flipflop_53: vf.add_const(0.0, name=''),
        Protection_proc_flipflop_54: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        LVRT_Alarm: vf.add_const(0.0, name=''),
        OVRT_Alarm: vf.add_const(0.0, name=''),
        Freq_Alarm: vf.add_const(0.0, name=''),
        RoCoF_Alarm: vf.add_const(0.0, name=''),
        OLVRT_Trip: vf.add_const(0.0, name=''),
        ACMonitor_Trip: vf.add_const(0.0, name=''),
        Master_Trip: vf.add_const(0.0, name=''),
        OLvrtOn: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Protection_proc_select_0, source=(Protection_LineMonitorType > 0.5)),
        sampled_value(output=Protection_proc_select_1, source=(u_eval < Protection_LVRT_activation_thr)),
        picdro((LvrtOn == 0.0), 0.02, 0.0, output=Protection_proc_picdro_2),
        aflipflop(t, LvrtOn, Protection_proc_picdro_2, output=Protection_proc_aflipflop_3),
        sampled_value(output=Protection_proc_select_4, source=(t_elapsed_LV <= Protection_DtLVRT_4)),
        sampled_value(output=Protection_proc_select_5, source=(t_elapsed_LV <= Protection_DtLVRT_3)),
        sampled_value(output=Protection_proc_select_6, source=(t_elapsed_LV <= Protection_DtLVRT_2)),
        sampled_value(output=Protection_proc_select_7, source=(t_elapsed_LV <= Protection_DtLVRT_1)),
        sampled_value(output=Protection_proc_select_8, source=((sym.heaviside((enable - 0.5)) * sym.heaviside((LvrtOn - 0.5))) * sym.heaviside((vLVRT_trip_lim - u_eval)))),
        sampled_value(output=Protection_proc_select_9, source=(u_eval > Protection_OVRT_activation_thr)),
        picdro((OvrtOn == 0.0), 0.02, 0.0, output=Protection_proc_picdro_10),
        aflipflop(t, OvrtOn, Protection_proc_picdro_10, output=Protection_proc_aflipflop_11),
        sampled_value(output=Protection_proc_select_12, source=(t_elapsed_OV <= Protection_DtOVRT_4)),
        sampled_value(output=Protection_proc_select_13, source=(t_elapsed_OV <= Protection_DtOVRT_3)),
        sampled_value(output=Protection_proc_select_14, source=(t_elapsed_OV <= Protection_DtOVRT_2)),
        sampled_value(output=Protection_proc_select_15, source=(t_elapsed_OV <= Protection_DtOVRT_1)),
        sampled_value(output=Protection_proc_select_16, source=((sym.heaviside((enable - 0.5)) * sym.heaviside((OvrtOn - 0.5))) * sym.heaviside((u_eval - vOVRT_trip_lim)))),
        sampled_value(output=Protection_proc_select_17, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((f - Protection_HighThr_Freq1)))),
        picdro(en_OF1, Protection_TOFreq_1, 0.0, output=Protection_proc_picdro_18),
        sampled_value(output=Protection_proc_select_19, source=(Protection_proc_picdro_18 > 0.5)),
        sampled_value(output=Protection_proc_select_20, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((f - Protection_HighThr_Freq2)))),
        picdro(en_OF2, Protection_TOFreq_2, 0.0, output=Protection_proc_picdro_21),
        sampled_value(output=Protection_proc_select_22, source=(Protection_proc_picdro_21 > 0.5)),
        sampled_value(output=Protection_proc_select_23, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((f - Protection_HighThr_FreqFast)))),
        picdro(en_OFFast, Protection_TOFreq_Fast, 0.0, output=Protection_proc_picdro_24),
        sampled_value(output=Protection_proc_select_25, source=(Protection_proc_picdro_24 > 0.5)),
        sampled_value(output=Protection_proc_select_26, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((Protection_LowThr_Freq1 - f)))),
        picdro(en_UF1, Protection_TUFreq_1, 0.0, output=Protection_proc_picdro_27),
        sampled_value(output=Protection_proc_select_28, source=(Protection_proc_picdro_27 > 0.5)),
        sampled_value(output=Protection_proc_select_29, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((Protection_LowThr_Freq2 - f)))),
        picdro(en_UF2, Protection_TUFreq_2, 0.0, output=Protection_proc_picdro_30),
        sampled_value(output=Protection_proc_select_31, source=(Protection_proc_picdro_30 > 0.5)),
        sampled_value(output=Protection_proc_select_32, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((Protection_LowThr_FreqFast - f)))),
        picdro(en_UFFast, Protection_TUFreq_Fast, 0.0, output=Protection_proc_picdro_33),
        sampled_value(output=Protection_proc_select_34, source=(Protection_proc_picdro_33 > 0.5)),
        sampled_value(output=Protection_proc_select_35, source=(1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - sym.heaviside((Trip_OF_1 - 0.5))) * (1.0 - sym.heaviside((Trip_OF_2 - 0.5)))))) * (1.0 - sym.heaviside((Trip_OF_Fast - 0.5)))))) * (1.0 - sym.heaviside((Trip_UF_1 - 0.5)))))) * (1.0 - sym.heaviside((Trip_UF_2 - 0.5)))))) * (1.0 - sym.heaviside((Trip_UF_Fast - 0.5)))))),
        sampled_value(output=Protection_proc_select_36, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((sym.abs(RoCoF_measured) - Protection_Limit_RoCoF)))),
        picdro(en_RoCoF, Protection_TRoCoF, 0.0, output=Protection_proc_picdro_37),
        sampled_value(output=Protection_proc_select_38, source=(Protection_proc_picdro_37 > 0.5)),
        sampled_value(output=Protection_proc_select_39, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((u_eval - Protection_HighThr_Voltage)))),
        picdro(en_OV, Protection_TOvolt, 0.0, output=Protection_proc_picdro_40),
        sampled_value(output=Protection_proc_select_41, source=(Protection_proc_picdro_40 > 0.5)),
        sampled_value(output=Protection_proc_select_42, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((u_eval - Protection_HighThr_VoltageFast)))),
        picdro(en_OVFast, Protection_TOvolt_Fast, 0.0, output=Protection_proc_picdro_43),
        sampled_value(output=Protection_proc_select_44, source=(Protection_proc_picdro_43 > 0.5)),
        sampled_value(output=Protection_proc_select_45, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((Protection_LowThr_Voltage - u_eval)))),
        picdro(en_UV, Protection_TUvolt, 0.0, output=Protection_proc_picdro_46),
        sampled_value(output=Protection_proc_select_47, source=(Protection_proc_picdro_46 > 0.5)),
        sampled_value(output=Protection_proc_select_48, source=(sym.heaviside((enable - 0.5)) * sym.heaviside((Protection_LowThr_VoltageFast - u_eval)))),
        picdro(en_UVFast, Protection_TUvolt_Fast, 0.0, output=Protection_proc_picdro_49),
        sampled_value(output=Protection_proc_select_50, source=(Protection_proc_picdro_49 > 0.5)),
        sampled_value(output=Protection_proc_select_51, source=(1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - sym.heaviside((Trip_OV - 0.5))) * (1.0 - sym.heaviside((Trip_OV_Fast - 0.5)))))) * (1.0 - sym.heaviside((Trip_UV - 0.5)))))) * (1.0 - sym.heaviside((Trip_UV_Fast - 0.5)))))),
        sampled_value(output=Protection_proc_select_52, source=(1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - sym.heaviside((LVRT_Alarm - 0.5))) * (1.0 - sym.heaviside((OVRT_Alarm - 0.5)))))) * (1.0 - sym.heaviside((Freq_Alarm - 0.5)))))) * (1.0 - sym.heaviside((RoCoF_Alarm - 0.5)))))) * (1.0 - sym.heaviside((Volt_Alarm - 0.5)))))),
        flipflop(Protection_OLVRT_Tripping, 0.0, output=Protection_proc_flipflop_53),
        flipflop(Protection_ACMonitor_Tripping, 0.0, output=Protection_proc_flipflop_54),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_protection_emt_template(vf=vf, name='Protection' if name is None else name)

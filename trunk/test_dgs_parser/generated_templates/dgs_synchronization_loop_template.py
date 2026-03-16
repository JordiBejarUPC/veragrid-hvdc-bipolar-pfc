# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\DGS_test_type_models.dgs

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
    Synchronization_Loop_GFOR_Damp = vf.add_var('Synchronization Loop__GFOR_Damp_' + name)
    Synchronization_Loop_GFOR_H = vf.add_var('Synchronization Loop__GFOR_H_' + name)
    Synchronization_Loop_GFOR_fnom = vf.add_var('Synchronization Loop__GFOR_fnom_' + name)
    Synchronization_Loop_K_fil_meas = vf.add_var('Synchronization Loop__K_fil_meas_' + name)
    Synchronization_Loop_tau_P = vf.add_var('Synchronization Loop__tau_P_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    P_capab_high = vf.add_var('P_capab_high_' + name)
    P_capab_low = vf.add_var('P_capab_low_' + name)
    Pmeas = vf.add_var('Pmeas_' + name)
    Pmeas_1 = vf.add_var('Pmeas_' + name)
    Pref_sat1 = vf.add_var('Pref_sat1_' + name)
    Pset = vf.add_var('Pset_' + name)
    Synchronization_Loop_xP_fil = vf.add_var('Synchronization Loop__xP_fil_' + name)
    Synchronization_Loop_xp_lim = vf.add_var('Synchronization Loop__xp_lim_' + name)
    Synchronization_Loop_xt = vf.add_var('Synchronization Loop__xt_' + name)
    Synchronization_Loop_xw = vf.add_var('Synchronization Loop__xw_' + name)
    cosdelta = vf.add_var('cosdelta_' + name)
    cosdelta_1 = vf.add_var('cosdelta_' + name)
    delta = vf.add_var('delta_' + name)
    delta_1 = vf.add_var('delta_' + name)
    flag_overload = vf.add_var('flag_overload_' + name)
    sindelta = vf.add_var('sindelta_' + name)
    sindelta_1 = vf.add_var('sindelta_' + name)
    w = vf.add_var('w_' + name)
    wref = vf.add_var('wref_' + name)
    wset = vf.add_var('wset_' + name)
    wset_1 = vf.add_var('wset_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        in_vars=[wset, wref, P_capab_high, P_capab_low, Pset, Pmeas, flag_overload],
        out_vars=[w, cosdelta, sindelta, Pref_sat1],
        name='Synchronization Loop'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Synchronization_Loop_GFOR_H: vf.add_const(None, name='GFOR_H'),
        Synchronization_Loop_K_fil_meas: vf.add_const(None, name='K_fil_meas'),
        Synchronization_Loop_tau_P: vf.add_const(None, name='tau_P'),
        Synchronization_Loop_GFOR_Damp: vf.add_const(None, name='GFOR_Damp'),
        Synchronization_Loop_GFOR_fnom: vf.add_const(None, name='GFOR_fnom'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Synchronization_Loop_xw: vf.add_const(0.0, name=''),
        Synchronization_Loop_xt: delta,
        Synchronization_Loop_xp_lim: Pmeas_1,
        Synchronization_Loop_xP_fil: Pmeas_1,
        delta_1: sym.atan2(sindelta_1, cosdelta_1),
        Pref_sat1: Pmeas_1,
        w: wset_1,
        wset: vf.add_const(1.0, name=''),
        Pset: Pmeas_1,
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_synchronization_loop_emt_template(vf=vf, name='Synchronization Loop' if name is None else name)

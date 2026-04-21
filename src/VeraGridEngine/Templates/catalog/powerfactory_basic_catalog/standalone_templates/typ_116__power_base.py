# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_power_base_116_emt_template(vf: VarFactory, name: str = 'Power_base__116') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Power_base_PN = vf.add_var('Power_base__PN_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Power_base_proc_select_1 = vf.add_var('Power_base__proc_select_1_' + name)
    Power_base_proc_selfix_0 = vf.add_var('Power_base__proc_selfix_0_' + name)
    cosn = vf.add_var('cosn_' + name)
    pelec = vf.add_var('pelec_' + name)
    pg = vf.add_var('pg_' + name)
    sgnn = vf.add_var('sgnn_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (pelec - ((Power_base_proc_select_1 * (((pg * sgnn) * cosn) / Power_base_PN)) + ((sym.Const(1.0) - Power_base_proc_select_1) * pg))),
        ],
        algebraic_vars=[pelec],
        in_vars=[pg, sgnn, cosn],
        out_vars=[pelec],
        name='Power_base'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Power_base_PN: vf.add_const(None, name='PN'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Power_base_proc_selfix_0: vf.add_const(0.0, name=''),
        Power_base_proc_select_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        pelec: ((Power_base_proc_selfix_0 * (((pg * sgnn) * cosn) / Power_base_PN)) + ((sym.Const(1.0) - Power_base_proc_selfix_0) * pg)),
    }
    templ.block.procedural_logic = [
        selfix((Power_base_PN > 0.0), output=Power_base_proc_selfix_0),
        sampled_value(output=Power_base_proc_select_1, source=(Power_base_PN > 0.0)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_power_base_116_emt_template(vf=vf, name='Power_base__116' if name is None else name)

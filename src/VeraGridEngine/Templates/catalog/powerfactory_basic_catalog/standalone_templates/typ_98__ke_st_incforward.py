# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import delay
from VeraGridEngine.enumerations import DeviceType

def get_ke_st_incforward_98_emt_template(vf: VarFactory, name: str = 'Ke^-sT _incforward__98') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Ke_sT_incforward_K = vf.add_var('Ke^-sT _incforward__K_' + name)
    Ke_sT_incforward_T = vf.add_var('Ke^-sT _incforward__T_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Ke_sT_incforward_proc_delay_0 = vf.add_var('Ke^-sT _incforward__proc_delay_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - (Ke_sT_incforward_K * Ke_sT_incforward_proc_delay_0)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Ke^-sT _incforward'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Ke_sT_incforward_K: vf.add_const(None, name='K'),
        Ke_sT_incforward_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Ke_sT_incforward_proc_delay_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: (Ke_sT_incforward_K * yi),
    }
    templ.block.procedural_logic = [
        delay(yi, Ke_sT_incforward_T, output=Ke_sT_incforward_proc_delay_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_ke_st_incforward_98_emt_template(vf=vf, name='Ke^-sT _incforward__98' if name is None else name)

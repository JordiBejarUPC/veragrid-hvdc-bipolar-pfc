# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import gradlim_const
from VeraGridEngine.enumerations import DeviceType

def get_gradlim_const_69_emt_template(vf: VarFactory, name: str = 'gradlim_const__69') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    gradlim_const_gradmax = vf.add_var('gradlim_const__gradmax_' + name)
    gradlim_const_gradmin = vf.add_var('gradlim_const__gradmin_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    gradlim_const_proc_gradlim_const_0 = vf.add_var('gradlim_const__proc_gradlim_const_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - gradlim_const_proc_gradlim_const_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='gradlim_const'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        gradlim_const_gradmax: vf.add_const(None, name='gradmax'),
        gradlim_const_gradmin: vf.add_const(None, name='gradmin'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        gradlim_const_proc_gradlim_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        gradlim_const(yi, gradlim_const_gradmin, gradlim_const_gradmax, output=gradlim_const_proc_gradlim_const_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_gradlim_const_69_emt_template(vf=vf, name='gradlim_const__69' if name is None else name)

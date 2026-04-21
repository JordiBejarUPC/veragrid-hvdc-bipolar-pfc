# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import movingavg
from VeraGridEngine.enumerations import DeviceType

def get_rms_value_542_emt_template(vf: VarFactory, name: str = 'RMS value__542') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    RMS_value_fn = vf.add_var('RMS value__fn_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    RMS_value_proc_movingavg_0 = vf.add_var('RMS value__proc_movingavg_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - sym.sqrt(((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - RMS_value_proc_movingavg_0))) + (RMS_value_proc_movingavg_0 * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - RMS_value_proc_movingavg_0))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='RMS value'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        RMS_value_fn: vf.add_const(None, name='fn'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        RMS_value_proc_movingavg_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        movingavg((yi * yi), ((1.0 / ((RMS_value_fn * sym.heaviside((RMS_value_fn - 10.0))) + (10.0 * (1 - sym.heaviside((RMS_value_fn - 10.0)))))) / 20.0), (1.0 / ((RMS_value_fn * sym.heaviside((RMS_value_fn - 10.0))) + (10.0 * (1 - sym.heaviside((RMS_value_fn - 10.0)))))), output=RMS_value_proc_movingavg_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_rms_value_542_emt_template(vf=vf, name='RMS value__542' if name is None else name)

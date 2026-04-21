# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_deadband_discontinuous_91_emt_template(vf: VarFactory, name: str = 'Deadband discontinuous__91') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Deadband_discontinuous_db = vf.add_var('Deadband discontinuous__db_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Deadband_discontinuous_proc_select_0 = vf.add_var('Deadband discontinuous__proc_select_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Deadband_discontinuous_proc_select_0 * yi) + ((sym.Const(1.0) - Deadband_discontinuous_proc_select_0) * sym.Const(0.0)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Deadband discontinuous'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Deadband_discontinuous_db: vf.add_const(None, name='db'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Deadband_discontinuous_proc_select_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Deadband_discontinuous_proc_select_0, source=(sym.abs(yi) > Deadband_discontinuous_db)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_deadband_discontinuous_91_emt_template(vf=vf, name='Deadband discontinuous__91' if name is None else name)

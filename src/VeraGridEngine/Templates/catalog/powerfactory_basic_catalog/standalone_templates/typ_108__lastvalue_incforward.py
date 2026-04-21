# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue
from VeraGridEngine.enumerations import DeviceType

def get_lastvalue_incforward_108_emt_template(vf: VarFactory, name: str = 'lastvalue _incforward__108') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    lastvalue_incforward_proc_lastvalue_0 = vf.add_var('lastvalue _incforward__proc_lastvalue_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - lastvalue_incforward_proc_lastvalue_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='lastvalue _incforward'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        lastvalue_incforward_proc_lastvalue_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: yi,
    }
    templ.block.procedural_logic = [
        lastvalue(yi, output=lastvalue_incforward_proc_lastvalue_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_lastvalue_incforward_108_emt_template(vf=vf, name='lastvalue _incforward__108' if name is None else name)

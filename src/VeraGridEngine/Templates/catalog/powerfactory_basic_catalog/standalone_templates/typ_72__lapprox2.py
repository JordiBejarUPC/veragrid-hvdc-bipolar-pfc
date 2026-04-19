# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_lapprox2_72_emt_template(vf: VarFactory, name: str = 'lapprox2__72') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    lapprox2_matrix_K = vf.add_var('lapprox2__matrix_K_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    col = vf.add_var('col_' + name)
    row = vf.add_var('row_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        in_vars=[row, col],
        out_vars=[yo],
        name='lapprox2'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        lapprox2_matrix_K: vf.add_const(None, name='matrix_K'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_lapprox2_72_emt_template(vf=vf, name='lapprox2__72' if name is None else name)

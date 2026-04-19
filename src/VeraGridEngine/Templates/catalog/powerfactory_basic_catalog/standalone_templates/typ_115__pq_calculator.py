# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_pq_calculator_115_emt_template(vf: VarFactory, name: str = 'PQ Calculator__115') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    P = vf.add_var('P_' + name)
    Q = vf.add_var('Q_' + name)
    ii = vf.add_var('ii_' + name)
    ir = vf.add_var('ir_' + name)
    ui = vf.add_var('ui_' + name)
    ur = vf.add_var('ur_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (P - ((ur * ir) + (ui * ii))),
            (Q - ((ui * ir) - (ur * ii))),
        ],
        algebraic_vars=[P, Q],
        in_vars=[ur, ui, ir, ii],
        out_vars=[P, Q],
        name='PQ Calculator'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_pq_calculator_115_emt_template(vf=vf, name='PQ Calculator__115' if name is None else name)

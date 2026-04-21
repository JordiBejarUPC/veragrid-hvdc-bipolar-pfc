# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_gear_box_404_emt_template(vf: VarFactory, name: str = 'Gear Box__404') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Gear_Box_Nratio = vf.add_var('Gear Box__Nratio_' + name)
    Gear_Box_RPM_syn = vf.add_var('Gear Box__RPM_syn_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    omega = vf.add_var('omega_' + name)
    speed = vf.add_var('speed_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (omega - (((((speed * Gear_Box_RPM_syn) / sym.Const(60.0)) * sym.Const(2.0)) * sym.Const(3.141592653589793)) / Gear_Box_Nratio)),
        ],
        algebraic_vars=[omega],
        in_vars=[speed],
        out_vars=[omega],
        name='Gear Box'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Gear_Box_Nratio: vf.add_const(None, name='Nratio'),
        Gear_Box_RPM_syn: vf.add_const(None, name='RPM_syn'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_gear_box_404_emt_template(vf=vf, name='Gear Box__404' if name is None else name)

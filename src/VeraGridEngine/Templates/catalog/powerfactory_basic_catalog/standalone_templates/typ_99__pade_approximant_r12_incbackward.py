# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_pade_approximant_r12_incbackward_99_emt_template(vf: VarFactory, name: str = 'Pade approximant R12 _incbackward__99') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Pade_approximant_R12_incbackward_Td = vf.add_var('Pade approximant R12 _incbackward__Td_' + name)

    # --- State Variables ---
    Pade_approximant_R12_incbackward_x1 = vf.add_var('Pade approximant R12 _incbackward__x1_' + name)
    Pade_approximant_R12_incbackward_x2 = vf.add_var('Pade approximant R12 _incbackward__x2_' + name)

    # --- Algebraic / Shared Variables ---
    Pade_approximant_R12_incbackward_A0 = vf.add_var('Pade approximant R12 _incbackward_A0_' + name)
    Pade_approximant_R12_incbackward_A1 = vf.add_var('Pade approximant R12 _incbackward_A1_' + name)
    Pade_approximant_R12_incbackward_A2 = vf.add_var('Pade approximant R12 _incbackward_A2_' + name)
    Pade_approximant_R12_incbackward_B0 = vf.add_var('Pade approximant R12 _incbackward_B0_' + name)
    Pade_approximant_R12_incbackward_B1 = vf.add_var('Pade approximant R12 _incbackward_B1_' + name)
    Pade_approximant_R12_incbackward_offset = vf.add_var('Pade approximant R12 _incbackward_offset_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Pade_approximant_R12_incbackward_x1 = vf.add_diff_var('d_Pade approximant R12 _incbackward__x1_' + name, base_var=Pade_approximant_R12_incbackward_x1)
    d_Pade_approximant_R12_incbackward_x2 = vf.add_diff_var('d_Pade approximant R12 _incbackward__x2_' + name, base_var=Pade_approximant_R12_incbackward_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            Pade_approximant_R12_incbackward_x2,
            (((-((Pade_approximant_R12_incbackward_A0 * Pade_approximant_R12_incbackward_x1) + (Pade_approximant_R12_incbackward_A1 * Pade_approximant_R12_incbackward_x2))) / Pade_approximant_R12_incbackward_A2) + ((yi - Pade_approximant_R12_incbackward_offset) / Pade_approximant_R12_incbackward_A2)),
        ],
        state_vars=[Pade_approximant_R12_incbackward_x1, Pade_approximant_R12_incbackward_x2],
        algebraic_eqs=[
            (yo - (((Pade_approximant_R12_incbackward_B0 * Pade_approximant_R12_incbackward_x1) + (Pade_approximant_R12_incbackward_B1 * Pade_approximant_R12_incbackward_x2)) + Pade_approximant_R12_incbackward_offset)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Pade approximant R12 _incbackward'
    )
    templ.block.diff_vars = [d_Pade_approximant_R12_incbackward_x1, d_Pade_approximant_R12_incbackward_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Pade_approximant_R12_incbackward_Td: vf.add_const(None, name='Td'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Pade_approximant_R12_incbackward_offset: yo,
        Pade_approximant_R12_incbackward_x1: vf.add_const(0.0, name=''),
        Pade_approximant_R12_incbackward_x2: vf.add_const(0.0, name=''),
        Pade_approximant_R12_incbackward_A0: vf.add_const(1.0, name=''),
        Pade_approximant_R12_incbackward_A1: (sym.Const(0.666666667) * ((Pade_approximant_R12_incbackward_Td * sym.heaviside((Pade_approximant_R12_incbackward_Td - sym.Const(0.0001)))) + (sym.Const(0.0001) * (sym.Const(1) - sym.heaviside((Pade_approximant_R12_incbackward_Td - sym.Const(0.0001))))))),
        Pade_approximant_R12_incbackward_A2: ((sym.Const(0.166666667) * ((Pade_approximant_R12_incbackward_Td * sym.heaviside((Pade_approximant_R12_incbackward_Td - sym.Const(0.0001)))) + (sym.Const(0.0001) * (sym.Const(1) - sym.heaviside((Pade_approximant_R12_incbackward_Td - sym.Const(0.0001))))))) * ((Pade_approximant_R12_incbackward_Td * sym.heaviside((Pade_approximant_R12_incbackward_Td - sym.Const(0.0001)))) + (sym.Const(0.0001) * (sym.Const(1) - sym.heaviside((Pade_approximant_R12_incbackward_Td - sym.Const(0.0001))))))),
        Pade_approximant_R12_incbackward_B0: vf.add_const(1.0, name=''),
        Pade_approximant_R12_incbackward_B1: ((-sym.Const(0.333333333)) * ((Pade_approximant_R12_incbackward_Td * sym.heaviside((Pade_approximant_R12_incbackward_Td - sym.Const(0.0001)))) + (sym.Const(0.0001) * (sym.Const(1) - sym.heaviside((Pade_approximant_R12_incbackward_Td - sym.Const(0.0001))))))),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_pade_approximant_r12_incbackward_99_emt_template(vf=vf, name='Pade approximant R12 _incbackward__99' if name is None else name)

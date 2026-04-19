# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_pt_pturb_407_emt_template(vf: VarFactory, name: str = 'Pt/Pturb__407') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Pt_Pturb_PN = vf.add_var('Pt/Pturb__PN_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Pt_Pturb_proc_select_1 = vf.add_var('Pt/Pturb__proc_select_1_' + name)
    Pt_Pturb_proc_selfix_0 = vf.add_var('Pt/Pturb__proc_selfix_0_' + name)
    cosn = vf.add_var('cosn_' + name)
    pt = vf.add_var('pt_' + name)
    pturb = vf.add_var('pturb_' + name)
    sgnn = vf.add_var('sgnn_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (pt - ((Pt_Pturb_proc_select_1 * ((pturb * Pt_Pturb_PN) / (sgnn * cosn))) + ((sym.Const(1.0) - Pt_Pturb_proc_select_1) * pturb))),
        ],
        algebraic_vars=[pt],
        in_vars=[pturb, sgnn, cosn],
        out_vars=[pt],
        name='Pt/Pturb'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Pt_Pturb_PN: vf.add_const(None, name='PN'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Pt_Pturb_proc_selfix_0: vf.add_const(0.0, name=''),
        Pt_Pturb_proc_select_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        pturb: ((Pt_Pturb_proc_selfix_0 * (((pt * sgnn) * cosn) / Pt_Pturb_PN)) + ((sym.Const(1.0) - Pt_Pturb_proc_selfix_0) * pt)),
    }
    templ.block.procedural_logic = [
        selfix((Pt_Pturb_PN > 0.0), output=Pt_Pturb_proc_selfix_0),
        sampled_value(output=Pt_Pturb_proc_select_1, source=(Pt_Pturb_PN > 0.0)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_pt_pturb_407_emt_template(vf=vf, name='Pt/Pturb__407' if name is None else name)

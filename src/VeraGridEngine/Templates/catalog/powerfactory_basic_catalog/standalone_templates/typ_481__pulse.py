# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import delay, picdro, sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_pulse_481_emt_template(vf: VarFactory, name: str = 'Pulse__481') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Pulse_K = vf.add_var('Pulse__K_' + name)
    Pulse_T1 = vf.add_var('Pulse__T1_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Pulse_proc_delay_2 = vf.add_var('Pulse__proc_delay_2_' + name)
    Pulse_proc_picdro_1 = vf.add_var('Pulse__proc_picdro_1_' + name)
    Pulse_proc_picdro_4 = vf.add_var('Pulse__proc_picdro_4_' + name)
    Pulse_proc_select_3 = vf.add_var('Pulse__proc_select_3_' + name)
    Pulse_proc_selfix_0 = vf.add_var('Pulse__proc_selfix_0_' + name)
    Pulse_y1 = vf.add_var('Pulse_y1_' + name)
    Pulse_y2 = vf.add_var('Pulse_y2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Pulse_y1 - Pulse_proc_picdro_1),
            (Pulse_y2 - ((Pulse_proc_select_3 * Pulse_proc_delay_2) + ((sym.Const(1.0) - Pulse_proc_select_3) * Pulse_y1))),
            (yo - Pulse_proc_picdro_4),
        ],
        algebraic_vars=[Pulse_y1, Pulse_y2, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Pulse'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Pulse_K: vf.add_const(None, name='K'),
        Pulse_T1: vf.add_const(None, name='T1'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Pulse_proc_selfix_0: vf.add_const(0.0, name=''),
        Pulse_proc_picdro_1: vf.add_const(0.0, name=''),
        Pulse_proc_delay_2: vf.add_const(0.0, name=''),
        Pulse_proc_select_3: vf.add_const(0.0, name=''),
        Pulse_proc_picdro_4: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Pulse_y1: ((Pulse_proc_selfix_0 * sym.Const(1.0)) + ((sym.Const(1.0) - Pulse_proc_selfix_0) * sym.Const(0.0))),
        Pulse_y2: Pulse_y1,
        yo: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((yi >= Pulse_K), output=Pulse_proc_selfix_0),
        picdro((yi >= Pulse_K), 0.0, 0.0, output=Pulse_proc_picdro_1),
        delay(Pulse_y1, Pulse_T1, output=Pulse_proc_delay_2),
        sampled_value(output=Pulse_proc_select_3, source=(Pulse_T1 > 0.0)),
        picdro((Pulse_y1 * (1.0 - Pulse_y2)), 0.001, 0.001, output=Pulse_proc_picdro_4),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_pulse_481_emt_template(vf=vf, name='Pulse__481' if name is None else name)

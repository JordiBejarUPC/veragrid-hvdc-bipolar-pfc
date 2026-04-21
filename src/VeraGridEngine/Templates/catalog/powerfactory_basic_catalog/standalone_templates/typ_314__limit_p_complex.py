# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_limit_p_complex_314_emt_template(vf: VarFactory, name: str = 'Limit [p] (complex)__314') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Limit_p_complex_MAG_MAX = vf.add_var('Limit [p] (complex)__MAG_MAX_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Limit_p_complex_proc_select_0 = vf.add_var('Limit [p] (complex)__proc_select_0_' + name)
    Limit_p_complex_mag = vf.add_var('Limit [p] (complex)_mag_' + name)
    Limit_p_complex_rescale_factor = vf.add_var('Limit [p] (complex)_rescale_factor_' + name)
    d = vf.add_var('d_' + name)
    q = vf.add_var('q_' + name)
    yo_d = vf.add_var('yo_d_' + name)
    yo_q = vf.add_var('yo_q_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Limit_p_complex_mag - sym.sqrt(((d * d) + (q * q)))),
            (Limit_p_complex_rescale_factor - ((Limit_p_complex_proc_select_0 * (Limit_p_complex_mag / Limit_p_complex_MAG_MAX)) + ((sym.Const(1.0) - Limit_p_complex_proc_select_0) * sym.Const(1.0)))),
            (yo_d - (d / Limit_p_complex_rescale_factor)),
            (yo_q - (q / Limit_p_complex_rescale_factor)),
        ],
        algebraic_vars=[Limit_p_complex_mag, Limit_p_complex_rescale_factor, yo_d, yo_q],
        in_vars=[d, q],
        out_vars=[yo_d, yo_q],
        name='Limit [p] (complex)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Limit_p_complex_MAG_MAX: vf.add_const(None, name='MAG_MAX'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Limit_p_complex_proc_select_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Limit_p_complex_proc_select_0, source=(Limit_p_complex_mag > Limit_p_complex_MAG_MAX)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_limit_p_complex_314_emt_template(vf=vf, name='Limit [p] (complex)__314' if name is None else name)

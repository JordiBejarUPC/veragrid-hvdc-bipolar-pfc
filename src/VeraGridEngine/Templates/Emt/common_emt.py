
from typing import Any, Sequence

from VeraGridEngine import get_stabilizer_emt
from VeraGridEngine.enumerations import BlockType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Templates.predefined_blocks import (
    constant,
    gain,
    adder,
    substract,
    product,
    divide,
    absolut,
    generic
)
from VeraGridEngine.Templates.Emt.generator_emt_type_template import (get_simple_generator_emt_template,
                                                                      get_exciter_emt,
                                                                      get_governor_emt,
                                                                      get_stabilizer_emt)
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import get_bergeron_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import (get_shunt_r_emt_template,
                                                                get_shunt_c_emt_template,
                                                                get_shunt_l_emt_template)
from VeraGridEngine.Templates.Emt.load_exponential_emt_template import get_exponential_load_emt
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template

def create_block_of_type(var_factory: VarFactory,
                         block_type: BlockType,
                         item_name: str = "") -> Block | None:
    """
    Create a Block appropriate for block_type.
    """
    # CONST (single output)
    if block_type == BlockType.CONST:
        blk = constant(var_factory, item_name)
        blk.name = item_name
        return blk

    # GAIN (single input -> single output)
    elif block_type == BlockType.GAIN:
        blk = gain(var_factory, item_name)
        blk.name = item_name
        return blk

    # SUM / ADDER (2 inputs)
    elif block_type == BlockType.SUM:
        blk = adder(var_factory, item_name)
        blk.name = item_name
        return blk

    # SUBSTRACT (2 inputs)
    elif block_type == BlockType.SUBSTR:
        blk = substract(var_factory, item_name)
        blk.name = item_name
        return blk

    # PRODUCT (2 inputs)
    elif block_type == BlockType.PRODUCT:
        blk = product(var_factory, item_name)
        blk.name = item_name
        return blk

    # DIVIDE (2 inputs)
    elif block_type == BlockType.DIVIDE:
        blk = divide(var_factory, item_name)
        blk.name = item_name
        return blk

    # ABSOLUT (single input -> single output)
    elif block_type == BlockType.ABS:
        blk = absolut(var_factory, item_name)
        blk.name = item_name
        return blk

    # EMT type GENERATOR
    elif block_type == BlockType.EMT_GENERATOR:
        blk = get_simple_generator_emt_template(var_factory).block
        blk.name = item_name
        return blk

    # Thevenin equivalent generator
    elif block_type == BlockType.EMT_THEVENIN:
        blk = get_generator_thevenin_rl_emt_template(var_factory).block
        blk.name = item_name
        return blk

    # GOVERNOR (governor with control)
    elif block_type == BlockType.GOV:
        blk = get_governor_emt(var_factory, item_name).block
        blk.name = item_name
        return blk

    # STABILIZER (stabilizer)
    elif block_type == BlockType.STAB:
        blk = get_stabilizer_emt(var_factory, item_name).block
        blk.name = item_name
        return blk

    # EXCITER (exciter)
    elif block_type == BlockType.EXCITER:
        blk = get_exciter_emt(var_factory, item_name).block
        blk.name = item_name
        return blk

    # LINE (line)
    elif block_type == BlockType.EMT_PI_LINE:
        blk = get_pi_line_emt_template(var_factory).block
        blk.name = item_name
        return blk
    elif block_type == BlockType.EMT_BERGERON_LINE:
        blk = get_bergeron_line_emt_template(var_factory).block
        blk.name = item_name
        return blk

    # LOAD (line)
    elif block_type == BlockType.R_LOAD:
        blk = get_shunt_r_emt_template(var_factory).block
        blk.name = item_name
        return blk
    elif block_type == BlockType.L_LOAD:
        blk = get_shunt_l_emt_template(var_factory).block
        blk.name = item_name
        return blk
    elif block_type == BlockType.C_LOAD:
        blk = get_shunt_c_emt_template(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.EXP_LOAD:
        blk = get_exponential_load_emt(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.ZIP_LOAD:
        blk = get_load_ZIP_emt_template(var_factory).block
        blk.name = item_name
        return blk

    elif block_type == BlockType.DC_LOAD:
        blk = get_dc_load_emt_template(var_factory).block
        blk.name = item_name
        return blk
    else:
        return None

def create_generic_block(var_factory: VarFactory,
                         state_inputs: int,
                         state_outputs: Sequence[str],
                         algebraic_inputs: int,
                         algebraic_outputs: Sequence[str]):
    """

    :param var_factory:
    :param state_inputs:
    :param state_outputs:
    :param algebraic_inputs:
    :param algebraic_outputs:
    :return:
    """
    blk = generic(var_factory, state_inputs,
                  state_outputs, algebraic_inputs,
                  algebraic_outputs)
    blk.name = "generic"
    return blk

from typing import Any, Sequence
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
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import (get_genqec,
                                                                      get_governor,
                                                                      get_stabilizer,
                                                                      get_exciter)


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
    if block_type == BlockType.GAIN:
        blk = gain(var_factory, item_name)
        blk.name = item_name
        return blk

    # SUM / ADDER (2 inputs)
    if block_type == BlockType.SUM:
        blk = adder(var_factory, item_name)
        blk.name = item_name
        return blk

    # SUBSTRACT (2 inputs)
    if block_type == BlockType.SUBSTR:
        blk = substract(var_factory, item_name)
        blk.name = item_name
        return blk

    # PRODUCT (2 inputs)
    if block_type == BlockType.PRODUCT:
        blk = product(var_factory, item_name)
        blk.name = item_name
        return blk

    # DIVIDE (2 inputs)
    if block_type == BlockType.DIVIDE:
        blk = divide(var_factory, item_name)
        blk.name = item_name
        return blk

    # ABSOLUT (single input -> single output)
    if block_type == BlockType.ABS:
        blk = absolut(var_factory, item_name)
        blk.name = item_name
        return blk

    # GENRAW (simple model)
    if block_type == BlockType.GENRAW:
        blk = get_genrow_rms_template(var_factory).block
        blk.name = item_name
        return blk

    # GENQEC (generator with saturation)
    if block_type == BlockType.GENQEC:
        blk = get_genqec(var_factory, item_name).block
        blk.name = item_name
        return blk

    # GOVERNOR (governor with control)
    if block_type == BlockType.GOV:
        blk = get_governor(var_factory, item_name).block
        blk.name = item_name
        return blk

    # STABILIZER (stabilizer)
    if block_type == BlockType.STAB:
        blk = get_stabilizer(var_factory, item_name).block
        blk.name = item_name
        return blk

    # EXCITER (exciter)
    if block_type == BlockType.EXCITER:
        blk = get_exciter(var_factory, item_name).block
        blk.name = item_name
        return blk

    # LINE (line)
    if block_type == BlockType.LINE:
        blk = get_line_rms_template(var_factory).block
        blk.name = item_name
        return blk

    # LOAD (line)
    if block_type == BlockType.LOAD:
        blk = get_load_rms_template(var_factory).block
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
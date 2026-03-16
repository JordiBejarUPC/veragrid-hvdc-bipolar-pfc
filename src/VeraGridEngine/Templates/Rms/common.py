
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
        return blk

    # GAIN (single input -> single output)
    if block_type == BlockType.GAIN:
        blk = gain(var_factory, item_name)
        return blk

    # SUM / ADDER (2 inputs)
    if block_type == BlockType.SUM:
        blk = adder(var_factory, item_name)
        return blk

    # SUBSTRACT (2 inputs)
    if block_type == BlockType.SUBSTR:
        blk = substract(var_factory, item_name)
        return blk

    # PRODUCT (2 inputs)
    if block_type == BlockType.PRODUCT:
        blk = product(var_factory, item_name)
        return blk

    # DIVIDE (2 inputs)
    if block_type == BlockType.DIVIDE:
        blk = divide(var_factory, item_name)
        return blk

    # ABSOLUT (single input -> single output)
    if block_type == BlockType.ABS:
        blk = absolut(var_factory, item_name)
        return blk

    # GENRAW (simple model)
    if block_type == BlockType.GENRAW:
        return get_genrow_rms_template(var_factory).block

    # GENQEC (generator with saturation)
    if block_type == BlockType.GENQEC:
        return get_genqec(var_factory, item_name).block

    # GOVERNOR (governor with control)
    if block_type == BlockType.GOV:
        return get_governor(var_factory, item_name).block

    # STABILIZER (stabilizer)
    if block_type == BlockType.STAB:
        return get_stabilizer(var_factory, item_name).block

    # EXCITER (exciter)
    if block_type == BlockType.EXCITER:
        return get_exciter(var_factory, item_name).block

    # LINE (line)
    if block_type == BlockType.LINE:
        return get_line_rms_template(var_factory).block

    # LOAD (line)
    if block_type == BlockType.LOAD:
        return get_load_rms_template(var_factory).block

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
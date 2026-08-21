# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List

import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_terminal_current_assembly import (
    assemble_emt_terminal_current_contributions,
)
from VeraGridEngine.Templates.Emt.dc_load_emt_template import (
    get_dc_load_emt_template,
)
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    EmtTerminalConductor,
    EmtTerminalCurrentContribution,
    EmtTerminalSide,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import VarPowerFlowReferenceType


def test_standard_dc_load_declares_hidden_emt_terminal_current() -> None:
    """Keep a native one-terminal EMT device on explicit KCL assembly.

    :return: None.
    """
    model: Block = get_dc_load_emt_template(vf=VarFactory()).block
    contributions: List[EmtTerminalCurrentContribution] = (
        model.dynamic_model_contract.emt_terminal_current_contributions
    )

    assert len(contributions) == 1
    assert contributions[0].get_terminal_side() is EmtTerminalSide.BUS
    assert contributions[0].get_conductor() is EmtTerminalConductor.DC


def test_single_bus_emt_contract_assembles_selected_current_without_ports() -> None:
    """Assemble one selected EMT current independently of visible ports.

    :return: None.
    """
    selected_current: Var = Var(name="selected_current")
    model: Block = Block(
        algebraic_vars=list((selected_current,)),
        algebraic_eqs=list((selected_current,)),
        out_vars=list(),
        external_mapping=dict(((VarPowerFlowReferenceType.i_A, selected_current),)),
    )
    model.dynamic_model_contract.emt_terminal_current_contributions = list((
        EmtTerminalCurrentContribution(
            terminal_side=EmtTerminalSide.BUS,
            conductor=EmtTerminalConductor.PHASE_A,
            current_reference=VarPowerFlowReferenceType.i_A,
        ),
    ))
    current_balance: Dict[int, List[Expr | Var | Const]] = dict({
        0: list((Const(0.0), Const(0.0), Const(0.0), Const(0.0))),
    })

    assemble_emt_terminal_current_contributions(
        model=model,
        current_balance=current_balance,
        bus_index=0,
        bus_is_dc=False,
    )
    restored_model: Block = Block.parse(data=model.to_dict())
    restored_contribution: EmtTerminalCurrentContribution = (
        restored_model.dynamic_model_contract.emt_terminal_current_contributions[0]
    )

    assert len(model.out_vars) == 0
    assert current_balance[0][1].eval(selected_current=0.3) == pytest.approx(0.3)
    assert restored_contribution.get_terminal_side() is EmtTerminalSide.BUS
    assert restored_contribution.get_conductor() is EmtTerminalConductor.PHASE_A


def test_two_terminal_emt_contract_uses_physical_dc_topology() -> None:
    """Assemble both DC branch terminals with the branch-current convention.

    :return: None.
    """
    from_current: Var = Var(name="from_current")
    to_current: Var = Var(name="to_current")
    model: Block = Block(
        algebraic_vars=list((from_current, to_current)),
        algebraic_eqs=list((from_current, to_current)),
        external_mapping=dict((
            (VarPowerFlowReferenceType.If_dc, from_current),
            (VarPowerFlowReferenceType.It_dc, to_current),
        )),
    )
    model.dynamic_model_contract.emt_terminal_current_contributions = list((
        EmtTerminalCurrentContribution(
            terminal_side=EmtTerminalSide.FROM,
            conductor=EmtTerminalConductor.DC,
            current_reference=VarPowerFlowReferenceType.If_dc,
        ),
        EmtTerminalCurrentContribution(
            terminal_side=EmtTerminalSide.TO,
            conductor=EmtTerminalConductor.DC,
            current_reference=VarPowerFlowReferenceType.It_dc,
        ),
    ))
    current_balance: Dict[int, List[Expr | Var | Const]] = dict({
        0: list((Const(0.0),)),
        1: list((Const(0.0),)),
    })

    assemble_emt_terminal_current_contributions(
        model=model,
        current_balance=current_balance,
        bus_from_index=0,
        bus_to_index=1,
        bus_from_is_dc=True,
        bus_to_is_dc=True,
    )

    assert current_balance[0][0].eval(from_current=0.2) == pytest.approx(-0.2)
    assert current_balance[1][0].eval(to_current=-0.19) == pytest.approx(0.19)


def test_emt_contract_rejects_bus_domain_mismatch_atomically() -> None:
    """Reject a DC current on an AC bus before changing any KCL entry.

    :return: None.
    """
    dc_current: Var = Var(name="dc_current")
    model: Block = Block(
        algebraic_vars=list((dc_current,)),
        algebraic_eqs=list((dc_current,)),
        external_mapping=dict(((VarPowerFlowReferenceType.Idc, dc_current),)),
    )
    model.dynamic_model_contract.emt_terminal_current_contributions = list((
        EmtTerminalCurrentContribution(
            terminal_side=EmtTerminalSide.BUS,
            conductor=EmtTerminalConductor.DC,
            current_reference=VarPowerFlowReferenceType.Idc,
        ),
    ))
    current_balance: Dict[int, List[Expr | Var | Const]] = dict({
        0: list((Const(0.0), Const(0.0), Const(0.0), Const(0.0))),
    })

    with pytest.raises(ValueError, match="connected bus domain"):
        assemble_emt_terminal_current_contributions(
            model=model,
            current_balance=current_balance,
            bus_index=0,
            bus_is_dc=False,
        )

    assert current_balance[0][0].eval() == pytest.approx(0.0)
    assert current_balance[0][1].eval() == pytest.approx(0.0)

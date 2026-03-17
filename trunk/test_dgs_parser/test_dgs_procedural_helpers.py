import unittest

from VeraGridEngine.IO.dgs.dgs_objects import BlkDef
from VeraGridEngine.IO.dgs.dgs_to_blocks import _build_block_from_parsed, _parse_blkdef, build_blkdef_statement_support_report
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Utils.procedural_logic import (
    AnalogFlipFlopLogic,
    FixedSampleLogic,
    FlipFlopLogic,
    PickupDropoffLogic,
    SampledValueLogic,
    aflipflop,
    build_boundary_updater_from_block,
    flipflop,
    lastvalue,
    picdro,
    reset,
    selfix,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = []


def _build_local_procedural_blkdef() -> BlkDef:
    blkdef = BlkDef()
    blkdef.ID = "proc_local"
    blkdef.loc_name = "ProcLocal"
    blkdef.inputs = []
    blkdef.outputs = ["yo"]
    blkdef.states = ["x"]
    blkdef.params = []
    blkdef.internals = ["sel", "lv", "ff", "pd"]
    blkdef.equations_raw = [
        "inc(x)=0.0;x.=0.0;sel=selfix(x>0.5,10.0,20.0);lv=lastvalue(x);"
        "ff=flipflop(x>0.5,x<0.1);pd=picdro(x>0.5,0.001,0.0015);"
        "yo=ff*lv + (1-ff)*pd;reset(x,x>0.9,3.0)"
    ]
    return blkdef


class TestDgsProceduralHelpers(unittest.TestCase):

    def test_helper_factories_build_human_readable_logic_entries(self) -> None:
        flag = Var("flag")
        x = Var("x")
        rst = Var("rst")
        val = Var("val")

        self.assertIsInstance(selfix(x > 0.5, output=flag), FixedSampleLogic)
        self.assertIsInstance(lastvalue(x, output=flag), SampledValueLogic)
        self.assertIsInstance(flipflop(x > 0.5, rst > 0.5, output=flag), FlipFlopLogic)
        self.assertIsInstance(aflipflop(x, x > 0.5, rst > 0.5, output=flag), AnalogFlipFlopLogic)
        self.assertIsInstance(picdro(x > 0.5, 0.01, 0.02, output=flag), PickupDropoffLogic)
        self.assertEqual(reset(x, rst, val).target_var_name, x.name)

    def test_parser_collects_procedural_helpers(self) -> None:
        parsed = _parse_blkdef(_build_local_procedural_blkdef(), dict())

        self.assertEqual(parsed.unsupported_lines, [])
        self.assertEqual(len(parsed.procedural_logic), 5)
        self.assertEqual(len(parsed.mode_dict), 4)

    def test_parser_collects_aflipflop_helper(self) -> None:
        blkdef = BlkDef()
        blkdef.ID = "proc_aflipflop"
        blkdef.loc_name = "ProcAflipFlop"
        blkdef.inputs = []
        blkdef.outputs = ["yo"]
        blkdef.states = ["x"]
        blkdef.params = []
        blkdef.internals = []
        blkdef.equations_raw = ["inc(x)=0.0;x.=0.0;yo=aflipflop(x,x>0.5,x<0.1)"]

        parsed = _parse_blkdef(blkdef, dict())

        self.assertEqual(parsed.unsupported_lines, [])
        self.assertEqual(len(parsed.procedural_logic), 1)
        self.assertIsInstance(parsed.procedural_logic[0], AnalogFlipFlopLogic)
        self.assertEqual(len(parsed.mode_dict), 1)

    def test_dgs_select_is_migrated_to_procedural_logic(self) -> None:
        blkdef = BlkDef()
        blkdef.ID = "select_migrated"
        blkdef.loc_name = "SelectMigrated"
        blkdef.inputs = ["u"]
        blkdef.outputs = ["yo"]
        blkdef.states = []
        blkdef.params = []
        blkdef.internals = []
        blkdef.equations_raw = ["yo = select(u > 0.5, 1.0, 0.0)"]

        parsed = _parse_blkdef(blkdef, dict())

        self.assertEqual(parsed.unsupported_lines, [])
        self.assertEqual(len(parsed.procedural_logic), 1)
        self.assertEqual(len(parsed.mode_dict), 1)

        report = build_blkdef_statement_support_report(blkdef)
        unsupported = [entry for entry in report if entry.status == "unsupported"]
        self.assertEqual(len(unsupported), 0)

    def test_rms_selfix_const_is_folded_as_true(self) -> None:
        blkdef = BlkDef()
        blkdef.ID = "rms_local"
        blkdef.loc_name = "RmsLocal"
        blkdef.inputs = []
        blkdef.outputs = ["yo"]
        blkdef.states = []
        blkdef.params = []
        blkdef.internals = ["wref"]
        blkdef.equations_raw = ["inc0(wref)=selfix_const(rms(),1.0,0.0);yo=wref"]

        parsed = _parse_blkdef(blkdef, dict())

        self.assertEqual(parsed.unsupported_lines, [])
        self.assertEqual(len(parsed.procedural_logic), 0)
        self.assertIsInstance(parsed.init_rhs["wref"], Const)
        self.assertEqual(parsed.init_rhs["wref"].value, 1.0)

    def test_runtime_updater_executes_stateful_helpers(self) -> None:
        parsed = _parse_blkdef(_build_local_procedural_blkdef(), dict())
        block = _build_block_from_parsed(parsed, dict())
        problem = GenericEmtProblem(sys_block=block, glob_time=Var("glob_time"))

        updater = build_boundary_updater_from_block(problem)
        self.assertIsNotNone(updater)
        assert updater is not None

        mode_name_to_idx = {
            var.name: problem.uid2idx_event_params[var.uid]
            for var in block.mode_dict.keys()
        }

        selector_logic = next(logic for logic in updater.logic_entries if isinstance(logic, FixedSampleLogic))
        sampled_logic = next(logic for logic in updater.logic_entries if isinstance(logic, SampledValueLogic))
        flipflop_logic = next(logic for logic in updater.logic_entries if isinstance(logic, FlipFlopLogic))
        picdro_logic = next(logic for logic in updater.logic_entries if isinstance(logic, PickupDropoffLogic))

        selector_idx = mode_name_to_idx[selector_logic.output_var_name]
        sampled_idx = mode_name_to_idx[sampled_logic.output_var_name]
        flipflop_idx = mode_name_to_idx[flipflop_logic.output_var_name]
        picdro_idx = mode_name_to_idx[picdro_logic.output_var_name]

        x = problem.get_x0().copy()
        x_idx = problem.get_var_idx(block.state_vars[0])
        params = problem.event_params_values.copy()

        x[x_idx] = 0.0
        updater.update(0.0, x, params)
        self.assertEqual(params[flipflop_idx], 0.0)
        self.assertEqual(params[picdro_idx], 0.0)

        x[x_idx] = 0.6
        updater.update(0.0, x, params)
        self.assertEqual(params[selector_idx], 0.0)
        self.assertEqual(params[flipflop_idx], 1.0)
        self.assertAlmostEqual(params[sampled_idx], 0.6)

        forced_time = updater.get_next_forced_event_time(0.0, 0.002)
        self.assertIsNotNone(forced_time)
        assert forced_time is not None
        self.assertAlmostEqual(forced_time, 0.001, places=7)

        updater.update(forced_time, x, params)
        self.assertEqual(params[picdro_idx], 1.0)

        x[x_idx] = 0.0
        updater.update(0.002, x, params)
        x[x_idx] = 1.0
        updater.update(0.003, x, params)
        self.assertEqual(x[x_idx], 3.0)


if __name__ == "__main__":
    unittest.main()

import os
import importlib.util
import tempfile
import unittest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    _blk_sum_slot_active_mode,
    _blk_sum_slot_mode,
    _blk_sum_slot_raw_mode,
    _parse_blkdef,
    _split_equation_statements,
    build_blkdef_statement_support_report,
    classify_dgs_statement,
    dgs_to_root_block,
    extract_named_block_subgraph,
    export_named_block_subgraph_to_python,
    export_named_block_subgraph_tree_to_python,
    export_root_elmcomp_template_to_python,
    export_root_slot_block_graphical_template_to_python,
    extract_elmcomp_direct_instances,
    extract_root_slot_block_graphical_tree,
    extract_root_slot_block_internal_only,
    extract_root_slot_block_internal_signal_tree,
)
from VeraGridEngine.IO.dgs.dgs_objects import BlkDef, BlkSum
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.enumerations import BlockScopeMode

DGS_TEST_FILE = r"C:\Users\andre\Documents\DGS_test_type_models.dgs"


@unittest.skipUnless(os.path.exists(DGS_TEST_FILE), "External DGS test file not available")
class TestDgsToBlocks(unittest.TestCase):

    class _DummyGrid:
        def __init__(self) -> None:
            self.emt_var_factory = VarFactory()

    @classmethod
    def setUpClass(cls) -> None:
        cls.result = dgs_to_root_block(DGS_TEST_FILE)

    def test_selects_grid_forming_converter_root(self) -> None:
        self.assertEqual(self.result.root_element.loc_name, "Grid Forming Converter")
        self.assertEqual(self.result.root_blkdef.blkdef.loc_name, "Grid Forming Frame")
        self.assertEqual(self.result.root_block.name, "Grid Forming Converter")

    def test_root_interface_is_extracted(self) -> None:
        self.assertEqual([v.name for v in self.result.root_block.in_vars], ["wset", "Pset"])
        self.assertGreater(len(self.result.root_block.algebraic_vars), 50)
        self.assertEqual(len(self.result.root_block.out_vars), 0)

    def test_simple_integrator_block_is_parsed(self) -> None:
        matches = [blk for blk in self.result.parsed_blocks.values() if blk.blkdef.loc_name == "1/2Hs"]
        self.assertEqual(len(matches), 1)
        blk = matches[0]

        self.assertEqual(blk.blkdef.loc_name, "1/2Hs")
        self.assertTrue(any(name in {"DP", "DP_full"} for name in blk.blkdef.inputs))
        self.assertIn("Dw", blk.blkdef.outputs)
        self.assertIn("xw", blk.blkdef.states)
        self.assertIn("H", blk.blkdef.params)
        self.assertIn("xw", blk.state_rhs)
        self.assertIn("Dw", blk.algebraic_rhs)

    def test_comments_and_powerfactory_procedural_lines_are_ignored(self) -> None:
        matches = [
            blk for blk in self.result.parsed_blocks.values()
            if any("lastvalue" in blob for blob in blk.blkdef.equations_raw)
        ]
        self.assertGreater(len(matches), 0)
        self.assertTrue(all(not any("lastvalue" in line for line in blk.unsupported_lines) for blk in matches))

    def test_inc0_only_applies_if_no_previous_initialization_exists(self) -> None:
        blkdef = BlkDef()
        blkdef.ID = "local"
        blkdef.loc_name = "Inc0Test"
        blkdef.outputs = ["yo"]
        blkdef.inputs = []
        blkdef.states = ["x"]
        blkdef.params = []
        blkdef.internals = []
        blkdef.equations_raw = [
            "inc0(x)=1.0;inc(x)=2.0;yo = x",
        ]

        parsed = _parse_blkdef(blkdef, dict())
        self.assertIn("x", parsed.init_rhs)
        self.assertEqual(parsed.init_rhs["x"].value, 2.0)

        blkdef2 = BlkDef()
        blkdef2.ID = "local2"
        blkdef2.loc_name = "Inc0Only"
        blkdef2.outputs = ["yo"]
        blkdef2.inputs = []
        blkdef2.states = ["x"]
        blkdef2.params = []
        blkdef2.internals = []
        blkdef2.equations_raw = [
            "inc0(x)=1.0;yo = x",
        ]

        parsed2 = _parse_blkdef(blkdef2, dict())
        self.assertIn("x", parsed2.init_rhs)
        self.assertEqual(parsed2.init_rhs["x"].value, 1.0)

    def test_equation_statement_splitter_preserves_vardef_strings(self) -> None:
        raw = ["vardef(xv) = 'pu';'Reactance of the virtual admittance';inc(x)=1.0;yo = x"]
        statements = _split_equation_statements(raw)
        self.assertIn("vardef(xv) = 'pu'", statements)
        self.assertIn("'Reactance of the virtual admittance'", statements)
        self.assertIn("inc(x)=1.0", statements)
        self.assertIn("yo = x", statements)

    def test_classify_statement_marks_vardef_as_ignored(self) -> None:
        kind, lhs = classify_dgs_statement("vardef(xv) = 'pu';'Reactance of the virtual admittance'")
        self.assertEqual(kind, "ignored")
        self.assertIsNone(lhs)
        kind2, lhs2 = classify_dgs_statement("'Reactance of the virtual admittance'")
        self.assertEqual(kind2, "ignored")
        self.assertIsNone(lhs2)

    def test_root_dependency_graph_is_nontrivial(self) -> None:
        graph = self.result.dependency_graph
        edge_count = sum(len(v) for v in graph.values())

        self.assertGreater(len(graph), 10)
        self.assertGreater(edge_count, 0)
        self.assertIn("Dw", self.result.producer_map)
        self.assertIn("Dw", self.result.consumer_map)

    def test_root_contains_many_reachable_children(self) -> None:
        self.assertGreater(len(self.result.root_block.children), 20)
        child_names = {child.name for child in self.result.root_block.children}
        self.assertIn("1/2Hs", child_names)
        self.assertIn("Synchronization Loop", child_names)
        self.assertIn("PCC Measurements", child_names)

    def test_can_extract_synchronization_loop_internal_only(self) -> None:
        subgraph = extract_named_block_subgraph(
            self.result,
            "Synchronization Loop",
            mode=BlockScopeMode.InternalOnly,
        )
        self.assertEqual(subgraph.selected_block.blkdef.loc_name, "Synchronization Loop")
        self.assertEqual(len(subgraph.node_ids), 1)
        self.assertEqual(subgraph.view_block.name, "Synchronization Loop")
        self.assertEqual(len(subgraph.view_block.children), 0)

    def test_can_extract_smart_admittance_internal_only(self) -> None:
        subgraph = extract_root_slot_block_internal_only(
            dgs_path=DGS_TEST_FILE,
            slot_name="Smart_Admittance",
            root_name="Grid Forming Converter",
        )
        self.assertIsNotNone(subgraph)
        assert subgraph is not None

        self.assertEqual(subgraph.selected_block.blkdef.loc_name, "Smart_Admittance")
        self.assertEqual(len(subgraph.node_ids), 1)
        self.assertEqual(subgraph.view_block.name, "Smart_Admittance")
        self.assertEqual(len(subgraph.view_block.children), 0)

    def test_can_export_smart_admittance_leaf_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree_target = os.path.join(tmp, "dgs_smart_admittance_tree.py")
            template_target = os.path.join(tmp, "dgs_smart_admittance_template.py")

            written_tree = export_named_block_subgraph_tree_to_python(
                dgs_path=DGS_TEST_FILE,
                output_path=tree_target,
                block_name="Smart_Admittance",
                mode=BlockScopeMode.InternalOnly,
            )
            written_template = export_named_block_subgraph_to_python(
                dgs_path=DGS_TEST_FILE,
                output_path=template_target,
                block_name="Smart_Admittance",
                mode=BlockScopeMode.InternalOnly,
            )

            self.assertTrue(os.path.exists(written_tree))
            self.assertTrue(os.path.exists(written_template))

            spec = importlib.util.spec_from_file_location("dgs_smart_admittance_template", written_template)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            vf = VarFactory()
            templ = module.get_template(vf)
            self.assertEqual(templ.block.name, "Smart_Admittance")
            self.assertEqual(len(templ.block.children), 0)
            self.assertTrue(hasattr(module, "get_smart_admittance_emt_template"))

    def test_smart_admittance_completeness_against_pf_export(self) -> None:
        subgraph = extract_root_slot_block_internal_only(
            dgs_path=DGS_TEST_FILE,
            slot_name="Smart_Admittance",
            root_name="Grid Forming Converter",
        )
        self.assertIsNotNone(subgraph)
        assert subgraph is not None

        parsed = subgraph.selected_block
        self.assertEqual(len(parsed.state_rhs), 4)
        self.assertGreaterEqual(len(parsed.algebraic_rhs), 80)
        self.assertGreaterEqual(len(parsed.init_rhs), 40)
        self.assertLessEqual(len(parsed.unsupported_lines), 40)
        self.assertTrue(all(line.startswith("vardef") or line.startswith("'") for line in parsed.unsupported_lines))

    def test_synchronization_loop_graphical_tree_has_no_spurious_external_blocks(self) -> None:
        graph_tree = extract_root_slot_block_graphical_tree(
            dgs_path=DGS_TEST_FILE,
            slot_name="Synchronization Loop",
            root_name="Grid Forming Converter",
        )
        self.assertIsNotNone(graph_tree)
        assert graph_tree is not None

        child_names = {child.name for child in graph_tree.view_block.children}
        forbidden_external = {
            "Smart_Admittance",
            "Q/Vac droop",
            "Current controller",
            "PCC Measurements",
            "Protection",
        }
        self.assertTrue(child_names.isdisjoint(forbidden_external))

    def test_support_report_for_synchronization_loop(self) -> None:
        subgraph = extract_root_slot_block_internal_only(
            dgs_path=DGS_TEST_FILE,
            slot_name="Synchronization Loop",
            root_name="Grid Forming Converter",
        )
        assert subgraph is not None

        report = build_blkdef_statement_support_report(subgraph.selected_block.blkdef)
        supported = [entry for entry in report if entry.status == "supported"]
        unsupported = [entry for entry in report if entry.status == "unsupported"]

        self.assertGreaterEqual(len(supported), 9)
        self.assertEqual(len(unsupported), 0)

    def test_support_report_for_smart_admittance(self) -> None:
        subgraph = extract_root_slot_block_internal_only(
            dgs_path=DGS_TEST_FILE,
            slot_name="Smart_Admittance",
            root_name="Grid Forming Converter",
        )
        assert subgraph is not None

        report = build_blkdef_statement_support_report(subgraph.selected_block.blkdef)
        supported = [entry for entry in report if entry.status == "supported"]
        ignored = [entry for entry in report if entry.status == "ignored"]
        unsupported = [entry for entry in report if entry.status == "unsupported"]

        self.assertGreaterEqual(len(supported), 120)
        self.assertGreaterEqual(len(ignored), 20)
        self.assertEqual(len(unsupported), 0)

    def test_support_report_for_protection(self) -> None:
        subgraph = extract_root_slot_block_internal_only(
            dgs_path=DGS_TEST_FILE,
            slot_name="Protection",
            root_name="Grid Forming Converter",
        )
        assert subgraph is not None

        report = build_blkdef_statement_support_report(subgraph.selected_block.blkdef)
        unsupported = [entry for entry in report if entry.status == "unsupported"]

        self.assertEqual(len(unsupported), 0)

    def test_root_elmcomp_instance_mapping_contains_synchronization_loop(self) -> None:
        circuit = DgsCircuit()
        circuit.parse_dgs(DGS_TEST_FILE)

        entries = extract_elmcomp_direct_instances(circuit, self.result.root_element)

        type_names = {entry.type_name for entry in entries}
        self.assertIn("Synchronization Loop", type_names)

        matched = [entry for entry in entries if entry.type_name == "Synchronization Loop"]
        self.assertEqual(len(matched), 1)

    def test_blk_sum_active_mode_is_authoritative(self) -> None:
        blk_sum = BlkSum()
        blk_sum.iInput0 = 1
        blk_sum.iInput0_act = 0
        blk_sum.iInput1 = 0
        blk_sum.iInput1_act = 1

        self.assertEqual(_blk_sum_slot_raw_mode(blk_sum, 0), 1)
        self.assertEqual(_blk_sum_slot_active_mode(blk_sum, 0), 0)
        self.assertEqual(_blk_sum_slot_mode(blk_sum, 0), 0)
        self.assertEqual(_blk_sum_slot_mode(blk_sum, 1), 1)

    def test_blk_sum_modes_match_active_modes_in_current_fixture(self) -> None:
        circuit = DgsCircuit()
        circuit.parse_dgs(DGS_TEST_FILE)

        for blk_sum in circuit.blksums:
            for slot in range(4):
                self.assertEqual(_blk_sum_slot_raw_mode(blk_sum, slot), _blk_sum_slot_active_mode(blk_sum, slot))

    def test_can_export_synchronization_loop_to_python_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree_target = os.path.join(tmp, "dgs_sync_loop_tree.py")
            template_target = os.path.join(tmp, "dgs_sync_loop_template.py")

            written_tree = export_named_block_subgraph_tree_to_python(
                dgs_path=DGS_TEST_FILE,
                output_path=tree_target,
                block_name="Synchronization Loop",
            )
            written_template = export_named_block_subgraph_to_python(
                dgs_path=DGS_TEST_FILE,
                output_path=template_target,
                block_name="Synchronization Loop",
            )

            self.assertTrue(os.path.exists(written_tree))
            self.assertTrue(os.path.exists(written_template))

            with open(written_tree, 'r', encoding='utf-8') as fh:
                generated_tree = fh.read()
            self.assertIn("BLOCK_DATA =", generated_tree)
            self.assertIn("def get_dependency_graph()", generated_tree)

            with open(written_template, 'r', encoding='utf-8') as fh:
                generated_template = fh.read()
            self.assertIn("templ.block = Block(", generated_template)
            self.assertNotIn("BLOCK_DATA =", generated_template)
            self.assertNotIn("def get_dependency_graph()", generated_template)
            self.assertNotIn("METADATA =", generated_template)

            spec = importlib.util.spec_from_file_location("dgs_sync_loop_template", written_template)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            vf = VarFactory()
            templ = module.get_template(vf)
            block = templ.block

            self.assertEqual(block.name, "Synchronization Loop")
            self.assertEqual(len(block.children), 0)

            self.assertTrue(hasattr(module, "get_synchronization_loop_emt_template"))

    def test_can_export_graphical_template_with_child_procedural_logic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            template_target = os.path.join(tmp, "dgs_sync_loop_graphical_template.py")

            written_template = export_root_slot_block_graphical_template_to_python(
                dgs_path=DGS_TEST_FILE,
                output_path=template_target,
                slot_name="Synchronization Loop",
                root_name="Grid Forming Converter",
            )

            self.assertTrue(os.path.exists(written_template))

            with open(written_template, 'r', encoding='utf-8') as fh:
                generated_template = fh.read()

            self.assertIn("PI_with_hold_and_reset_", generated_template)
            self.assertIn(".procedural_logic = [", generated_template)
            self.assertIn("lastvalue(", generated_template)
            self.assertIn("reset(", generated_template)
            self.assertIn(".connect(", generated_template)
            self.assertIn("name='Summation Point", generated_template)
            self.assertNotIn("name='From'", generated_template)
            self.assertNotIn("name='Goto'", generated_template)

            spec = importlib.util.spec_from_file_location("dgs_sync_loop_graphical_template", written_template)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            vf = VarFactory()
            templ = module.get_template(vf)
            child_by_name = {child.name: child for child in templ.block.children}
            self.assertIn("PI with hold and reset", child_by_name)
            self.assertGreater(len(child_by_name["PI with hold and reset"].procedural_logic), 0)
            self.assertTrue(any(child.name.startswith("Summation Point") for child in templ.block.children))
            self.assertTrue(all(not child.name.startswith("From") and not child.name.startswith("Goto") for child in templ.block.children))

    def test_can_export_q_vac_droop_graphical_template_with_sum_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            template_target = os.path.join(tmp, "dgs_q_vac_graphical_template.py")

            written_template = export_root_slot_block_graphical_template_to_python(
                dgs_path=DGS_TEST_FILE,
                output_path=template_target,
                slot_name="Q/Vac droop",
                root_name="Grid Forming Converter",
            )

            self.assertTrue(os.path.exists(written_template))

            with open(written_template, 'r', encoding='utf-8') as fh:
                generated_template = fh.read()

            self.assertIn("name='Summation Point'", generated_template)
            self.assertIn(".connect(", generated_template)
            self.assertNotIn("name='From'", generated_template)
            self.assertNotIn("name='Goto'", generated_template)

            spec = importlib.util.spec_from_file_location("dgs_q_vac_graphical_template", written_template)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            vf = VarFactory()
            templ = module.get_template(vf)
            sum_children = [child for child in templ.block.children if child.name.startswith("Summation Point")]
            self.assertGreaterEqual(len(sum_children), 5)
            self.assertTrue(all(not child.name.startswith("From") and not child.name.startswith("Goto") for child in templ.block.children))

    def test_can_export_pi_hold_template_with_top_level_procedural_logic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            template_target = os.path.join(tmp, "dgs_pi_hold_template.py")

            written_template = export_named_block_subgraph_to_python(
                dgs_path=DGS_TEST_FILE,
                output_path=template_target,
                block_name="PI with hold and reset",
            )

            self.assertTrue(os.path.exists(written_template))

            with open(written_template, 'r', encoding='utf-8') as fh:
                generated_template = fh.read()

            self.assertIn("templ.block.procedural_logic = [", generated_template)
            self.assertIn("lastvalue(", generated_template)
            self.assertIn("reset(", generated_template)

            spec = importlib.util.spec_from_file_location("dgs_pi_hold_template", written_template)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            vf = VarFactory()
            templ = module.get_template(vf)
            self.assertGreater(len(templ.block.procedural_logic), 0)

    def test_can_export_protection_template_with_procedural_logic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            template_target = os.path.join(tmp, "dgs_protection_template.py")

            written_template = export_named_block_subgraph_to_python(
                dgs_path=DGS_TEST_FILE,
                output_path=template_target,
                block_name="Protection",
            )

            self.assertTrue(os.path.exists(written_template))

            with open(written_template, 'r', encoding='utf-8') as fh:
                generated_template = fh.read()

            self.assertIn("templ.block.procedural_logic = [", generated_template)
            self.assertIn("picdro(", generated_template)
            self.assertIn("flipflop(", generated_template)
            self.assertIn("aflipflop(", generated_template)

            spec = importlib.util.spec_from_file_location("dgs_protection_template", written_template)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            vf = VarFactory()
            templ = module.get_template(vf)
            self.assertGreaterEqual(len(templ.block.procedural_logic), 10)

    def test_can_extract_synchronization_loop_internal_signal_tree(self) -> None:
        subgraph = extract_root_slot_block_internal_signal_tree(
            dgs_path=DGS_TEST_FILE,
            slot_name="Synchronization Loop",
            root_name="Grid Forming Converter",
        )

        self.assertIsNotNone(subgraph)
        assert subgraph is not None

        self.assertEqual(subgraph.selected_block.blkdef.loc_name, "Synchronization Loop")
        self.assertGreater(len(subgraph.node_ids), 1)

        child_names = {child.name for child in subgraph.view_block.children}
        self.assertIn("Synchronization Loop", child_names)

    def test_can_extract_synchronization_loop_graphical_tree_exact(self) -> None:
        graph_tree = extract_root_slot_block_graphical_tree(
            dgs_path=DGS_TEST_FILE,
            slot_name="Synchronization Loop",
            root_name="Grid Forming Converter",
        )
        self.assertIsNotNone(graph_tree)
        assert graph_tree is not None

        self.assertEqual(graph_tree.selected_block.blkdef.loc_name, "Synchronization Loop")
        child_names = {child.name for child in graph_tree.view_block.children}

        expected_internal = {
            "1/2Hs",
            "fn_to_wn",
            "Freeze_Gate",
            "angle integrator",
            "COS",
            "SIN",
            "PT1",
            "K",
            "C",
            "Limit_ss",
        }
        self.assertTrue(expected_internal.issubset(child_names))

        forbidden_external = {
            "Smart_Admittance",
            "Q/Vac droop",
            "Current controller",
            "PCC Measurements",
            "Protection",
        }
        self.assertTrue(child_names.isdisjoint(forbidden_external))

    def test_smart_admittance_graphical_tree_is_leaf(self) -> None:
        graph_tree = extract_root_slot_block_graphical_tree(
            dgs_path=DGS_TEST_FILE,
            slot_name="Smart_Admittance",
            root_name="Grid Forming Converter",
        )
        self.assertIsNotNone(graph_tree)
        assert graph_tree is not None

        self.assertEqual(graph_tree.selected_block.blkdef.loc_name, "Smart_Admittance")
        self.assertEqual(len(graph_tree.view_block.children), 0)


@unittest.skipUnless(os.path.exists(r"C:\Users\andre\Documents\NUACTIS_models.dgs"), "External NUACTIS DGS test file not available")
class TestNuactisDgsToBlocks(unittest.TestCase):

    def test_elmdsl_rows_expose_parameter_values(self) -> None:
        dgs_path: str = r"C:\Users\andre\Documents\NUACTIS_models.dgs"
        circuit = DgsCircuit()
        circuit.parse_dgs(dgs_path)

        outer_ctrl_p_instance = None
        for elm_dsl in circuit.elmdsls:
            if elm_dsl.loc_name == "Outer_control_P" and elm_dsl.typ_id == "7" and elm_dsl.outserv == 0:
                outer_ctrl_p_instance = elm_dsl
            else:
                pass

        self.assertIsNotNone(outer_ctrl_p_instance)
        assert outer_ctrl_p_instance is not None
        parameter_map = outer_ctrl_p_instance.get_parameter_map()
        self.assertEqual(parameter_map.get("P_ctrl_mode", None), 0.0)
        self.assertEqual(parameter_map.get("Kp", None), 1.3)
        self.assertEqual(parameter_map.get("Ki", None), 70.0)

    def test_exported_root_template_uses_instance_parameter_values(self) -> None:
        dgs_path: str = r"C:\Users\andre\Documents\NUACTIS_models.dgs"
        with tempfile.TemporaryDirectory() as tmp:
            template_target: str = os.path.join(tmp, "dgs_nuactis_master_pwm_template.py")

            written_template = export_root_elmcomp_template_to_python(
                dgs_path=dgs_path,
                output_path=template_target,
                root_name="MasterPWM_Model",
            )

            self.assertTrue(os.path.exists(written_template))

            spec = importlib.util.spec_from_file_location("dgs_nuactis_master_pwm_template", written_template)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            vf = VarFactory()
            templ = module.get_template(vf)
            child_by_name = {child.name: child for child in templ.block.children}
            self.assertIn("Outer_Ctrl_P", child_by_name)
            self.assertIn("Outer_Ctrl_Q", child_by_name)
            self.assertIn("Current_Limiter", child_by_name)
            self.assertNotIn("EPC_Control_Droop_VSC_MainFrame", child_by_name)

            outer_ctrl_p_block = child_by_name["Outer_Ctrl_P"]
            parameter_values_by_name = {const.name: const.value for const in outer_ctrl_p_block.event_dict.values()}
            self.assertEqual(parameter_values_by_name.get("P_ctrl_mode", None), 0.0)
            self.assertEqual(parameter_values_by_name.get("Kp", None), 1.3)
            self.assertEqual(parameter_values_by_name.get("Ki", None), 70.0)

            outer_ctrl_q_block = child_by_name["Outer_Ctrl_Q"]
            q_parameter_values_by_name = {const.name: const.value for const in outer_ctrl_q_block.event_dict.values()}
            self.assertEqual(q_parameter_values_by_name.get("iq_lim_min", None), -1.0)
            self.assertEqual(q_parameter_values_by_name.get("iq_lim_max", None), 1.0)

            current_limiter_block = child_by_name["Current_Limiter"]
            limiter_parameter_values_by_name = {const.name: const.value for const in current_limiter_block.event_dict.values()}
            self.assertEqual(limiter_parameter_values_by_name.get("i_max_1", None), 1.0)
            self.assertEqual(limiter_parameter_values_by_name.get("i_max_3", None), 1.0)


if __name__ == "__main__":
    unittest.main()

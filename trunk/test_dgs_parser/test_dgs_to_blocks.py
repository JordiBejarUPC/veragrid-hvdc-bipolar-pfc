import os
import importlib.util
import tempfile
import unittest
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    dgs_to_root_block,
    extract_named_block_subgraph,
    export_named_block_subgraph_to_python,
    export_named_block_subgraph_tree_to_python,
)

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
        self.assertEqual(str(self.result.root_element.typ_id).strip(), "46")
        self.assertEqual(self.result.root_blkdef.blkdef.loc_name, "Grid Forming Frame")
        self.assertEqual(self.result.root_block.name, "Grid Forming Converter")

    def test_root_interface_is_extracted(self) -> None:
        self.assertEqual([v.name for v in self.result.root_block.in_vars], ["wset", "Pset"])
        self.assertGreater(len(self.result.root_block.algebraic_vars), 50)
        self.assertEqual(len(self.result.root_block.out_vars), 0)

    def test_simple_integrator_block_is_parsed(self) -> None:
        blk = self.result.parsed_blocks["3"]
        self.assertEqual(blk.blkdef.loc_name, "1/2Hs")
        self.assertEqual(blk.blkdef.inputs, ["DP"])
        self.assertEqual(blk.blkdef.outputs, ["Dw"])
        self.assertEqual(blk.blkdef.states, ["xw"])
        self.assertEqual(blk.blkdef.params, ["H"])
        self.assertIn("xw", blk.state_rhs)
        self.assertIn("Dw", blk.algebraic_rhs)
        self.assertEqual(len(blk.unsupported_lines), 0)

    def test_comments_and_powerfactory_procedural_lines_are_ignored(self) -> None:
        blk = self.result.parsed_blocks["4"]
        self.assertEqual(blk.blkdef.loc_name, "Integrator + res + x0")
        self.assertIn("x", blk.state_rhs)
        self.assertIn("y", blk.algebraic_rhs)
        self.assertGreater(len(blk.unsupported_lines), 0)
        self.assertTrue(any("lastvalue" in line for line in blk.unsupported_lines))

    def test_root_dependency_graph_is_nontrivial(self) -> None:
        graph = self.result.dependency_graph
        self.assertIn("3", graph)
        self.assertGreater(len(graph["3"]), 0)
        self.assertIn("Dw", self.result.producer_map)
        self.assertIn("Dw", self.result.consumer_map)

    def test_root_contains_many_reachable_children(self) -> None:
        self.assertGreater(len(self.result.root_block.children), 20)
        child_names = {child.name for child in self.result.root_block.children}
        self.assertIn("1/2Hs", child_names)
        self.assertIn("Switch", child_names)
        self.assertIn("Grid Forming Frame", child_names)

    def test_can_extract_synchronization_loop_subgraph(self) -> None:
        subgraph = extract_named_block_subgraph(self.result, "Synchronization Loop")
        self.assertEqual(subgraph.selected_block.blkdef.loc_name, "Synchronization Loop")
        self.assertGreater(len(subgraph.node_ids), 3)
        child_names = {child.name for child in subgraph.view_block.children}
        self.assertIn("Synchronization Loop", child_names)
        self.assertIn("PCC Measurements", child_names)
        self.assertIn("Current controller", child_names)

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
            self.assertGreater(len(block.children), 3)
            self.assertTrue(hasattr(module, "get_synchronization_loop_emt_template"))


if __name__ == "__main__":
    unittest.main()

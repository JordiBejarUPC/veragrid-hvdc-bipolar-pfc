import importlib.util
import os
import tempfile
import unittest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    build_dgs_standalone_block_catalog,
    build_blkdef_statement_support_report,
    export_standalone_blkdef_to_python,
    list_dgs_blkref_catalog_occurrences,
)


BASE_CATALOG_DGS = r"C:\Users\andre\Documents\BASE_CATALOG.dgs"
PENDING_LOOKUP_TYPE_IDS = {
    "5", "6", "7", "8", "9",
    "14", "15", "16", "17", "18", "19", "20",
    "70", "71", "72", "73", "81", "82",
}


@unittest.skipUnless(os.path.exists(BASE_CATALOG_DGS), "External BASE_CATALOG.dgs file not available")
class TestBaseCatalogTemplates(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.circuit = DgsCircuit()
        cls.circuit.parse_dgs(BASE_CATALOG_DGS)
        cls.blkdef_by_id = {blk.ID: blk for blk in cls.circuit.blkdefs}
        cls.occurrences = list_dgs_blkref_catalog_occurrences(BASE_CATALOG_DGS)
        cls.full_catalog = build_dgs_standalone_block_catalog(BASE_CATALOG_DGS, isolated_only=False)
        cls.test_only_catalog = build_dgs_standalone_block_catalog(BASE_CATALOG_DGS, isolated_only=True)

    def test_occurrence_selector_separates_connected_frame_from_test_only_blocks(self) -> None:
        connected = [item for item in self.occurrences if item.connected]
        isolated = [item for item in self.occurrences if not item.connected]

        self.assertEqual(len(self.occurrences), 592)
        self.assertEqual(len(connected), 40)
        self.assertEqual(len(isolated), 552)

    def test_test_only_catalog_deduplicates_isolated_block_types(self) -> None:
        self.assertEqual(len(self.test_only_catalog), 551)
        self.assertTrue(all(item.connected_occurrence_count == 0 for item in self.test_only_catalog))
        self.assertTrue(all(item.isolated_occurrence_count == item.occurrence_count for item in self.test_only_catalog))

    def test_occurrence_based_filter_keeps_overlap_types_that_also_appear_in_connected_frame(self) -> None:
        full_by_id = {item.typ_id: item for item in self.full_catalog}
        test_only_by_id = {item.typ_id: item for item in self.test_only_catalog}

        self.assertIn("214", test_only_by_id)
        self.assertEqual(full_by_id["214"].connected_occurrence_count, 4)
        self.assertEqual(full_by_id["214"].isolated_occurrence_count, 1)
        self.assertEqual(test_only_by_id["214"].occurrence_count, 1)

    def test_test_only_catalog_entries_materialize_without_build_errors(self) -> None:
        failures = [item for item in self.test_only_catalog if item.build_error is not None]
        self.assertEqual(failures, [])

    def test_pending_lookup_blocks_are_exactly_the_generic_data_dependent_subset(self) -> None:
        pending = [item for item in self.test_only_catalog if item.unsupported_lines]

        self.assertEqual({item.typ_id for item in pending}, PENDING_LOOKUP_TYPE_IDS)
        self.assertEqual(len(pending), len(PENDING_LOOKUP_TYPE_IDS))
        self.assertTrue(all(item.build_error is None for item in pending))
        self.assertTrue(all(len(item.unsupported_lines) == 1 for item in pending))

    def test_pending_lookup_blocks_fail_only_on_lookup_helpers(self) -> None:
        expected_reasons = {
            "Unsupported PowerFactory helper 'lapprox'",
            "Unsupported function 'lapproxext'",
            "Unsupported function 'sapprox'",
            "Unsupported function 'lapprox2'",
            "Unsupported function 'sapprox2'",
            "Unsupported function 'invlapprox'",
        }

        for typ_id in sorted(PENDING_LOOKUP_TYPE_IDS):
            report = build_blkdef_statement_support_report(self.blkdef_by_id[typ_id])
            unsupported = [entry for entry in report if entry.status == "unsupported"]

            self.assertEqual(len(unsupported), 1)
            self.assertIn(unsupported[0].detail, expected_reasons)

    def test_editor_ready_subset_is_clean_before_future_editor_integration(self) -> None:
        editor_ready = [item for item in self.test_only_catalog if not item.unsupported_lines]

        self.assertEqual(len(editor_ready), len(self.test_only_catalog) - len(PENDING_LOOKUP_TYPE_IDS))
        self.assertEqual(len(editor_ready), 533)
        self.assertTrue(all(item.build_error is None for item in editor_ready))
        self.assertTrue(all(item.unsupported_lines == [] for item in editor_ready))

    def test_can_export_standalone_bool_comparator_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            template_target = os.path.join(tmp, "dgs_yi_equals_c_template.py")
            written = export_standalone_blkdef_to_python(
                dgs_path=BASE_CATALOG_DGS,
                output_path=template_target,
                block_id="21",
            )

            self.assertTrue(os.path.exists(written))

            spec = importlib.util.spec_from_file_location("dgs_yi_equals_c_template", written)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            templ = module.get_template(VarFactory())
            self.assertEqual(templ.block.name, "yi equals C")
            self.assertEqual(len(templ.block.children), 0)
            self.assertEqual(len(templ.block.procedural_logic), 1)


if __name__ == "__main__":
    unittest.main()

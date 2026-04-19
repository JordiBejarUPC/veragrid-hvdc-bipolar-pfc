from __future__ import annotations

import re
import unittest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_editor_ready_powerfactory_basic_catalog_descriptors
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_pending_powerfactory_basic_catalog_descriptors

from DynamicCatalog._catalog_support import build_manifest_path
from DynamicCatalog._catalog_support import build_pending_lookup_type_ids
from DynamicCatalog._catalog_support import build_templates_dir
from DynamicCatalog._catalog_support import find_template_path
from DynamicCatalog._catalog_support import import_template_module
from DynamicCatalog._catalog_support import manifest_entries


class TestPowerFactoryBasicCatalogReadiness(unittest.TestCase):
    """
    Validate that the shipped PowerFactory basic catalog is importable and editor-ready.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.entries = manifest_entries()
        cls.editor_ready_entries = [entry for entry in cls.entries if len(entry["unsupported_lines"]) == 0]
        cls.pending_entries = [entry for entry in cls.entries if len(entry["unsupported_lines"]) > 0]
        cls.ready_descriptors = list(get_editor_ready_powerfactory_basic_catalog_descriptors())
        cls.pending_descriptors = list(get_pending_powerfactory_basic_catalog_descriptors())

    def test_catalog_artifacts_exist(self) -> None:
        self.assertTrue(build_manifest_path().exists())
        self.assertTrue(build_templates_dir().exists())

    def test_pending_lookup_subset_is_frozen(self) -> None:
        pending_lookup_type_ids = build_pending_lookup_type_ids()
        self.assertEqual({entry["typ_id"] for entry in self.pending_entries}, set(pending_lookup_type_ids))
        self.assertEqual(len(self.pending_entries), len(pending_lookup_type_ids))
        self.assertTrue(all(entry["build_error"] is None for entry in self.pending_entries))
        self.assertTrue(all(len(entry["unsupported_lines"]) == 1 for entry in self.pending_entries))

    def test_editor_ready_subset_is_clean(self) -> None:
        self.assertEqual(len(self.ready_descriptors), 533)
        self.assertEqual(len(self.pending_descriptors), 18)
        self.assertEqual(len(self.editor_ready_entries), 533)
        self.assertTrue(all(entry["build_error"] is None for entry in self.editor_ready_entries))
        self.assertTrue(all(entry["unsupported_lines"] == [] for entry in self.editor_ready_entries))

    def test_every_catalog_entry_has_one_exported_template(self) -> None:
        for entry in self.entries:
            with self.subTest(typ_id=entry["typ_id"], name=entry["blkdef_name"]):
                self.assertTrue(find_template_path(entry["typ_id"]).exists())

    def test_editor_ready_descriptors_are_fully_categorized(self) -> None:
        for descriptor in self.ready_descriptors:
            with self.subTest(typ_id=descriptor.typ_id, label=descriptor.display_label):
                self.assertGreaterEqual(len(descriptor.category_path), 3)
                self.assertEqual(descriptor.category_path[0], "Native")
                self.assertNotEqual(descriptor.category_path[-1], "Other")

    def test_editor_ready_labels_do_not_expose_internal_typ_ids(self) -> None:
        for descriptor in self.ready_descriptors:
            with self.subTest(typ_id=descriptor.typ_id, label=descriptor.display_label):
                self.assertIsNone(re.search(r"\[\d+\]", descriptor.display_label))

    def test_editor_ready_labels_are_unique(self) -> None:
        labels = [descriptor.display_label for descriptor in self.ready_descriptors]
        self.assertEqual(len(labels), len(set(labels)))

    def test_constant_catalog_blocks_are_not_classified_as_controllers(self) -> None:
        descriptor_by_id = {descriptor.typ_id: descriptor for descriptor in self.ready_descriptors}
        for typ_id in ("53", "58", "59", "411"):
            with self.subTest(typ_id=typ_id, label=descriptor_by_id[typ_id].display_label):
                self.assertEqual(descriptor_by_id[typ_id].category_path[1:], ("Math and Functions", "Constants and Scaling"))

    def test_editor_ready_templates_materialize_as_executable_devices(self) -> None:
        for entry in self.editor_ready_entries:
            with self.subTest(typ_id=entry["typ_id"], name=entry["blkdef_name"]):
                module = import_template_module(entry["typ_id"])
                templ = module.get_template(VarFactory())

                self.assertEqual(len(templ.block.in_vars), len(entry["inputs"]))
                self.assertEqual(len(templ.block.out_vars), len(entry["outputs"]))
                self.assertEqual(len(templ.block.children), 0)

                declared_state_surface = (
                    len(templ.block.state_vars)
                    + len(templ.block.diff_vars)
                    + len(templ.block.init_eqs)
                    + len(templ.block.diff_init_eqs)
                )
                if len(entry["states"]) > 0:
                    self.assertGreater(declared_state_surface, 0)

                executable_content = (
                    len(templ.block.state_eqs)
                    + len(templ.block.algebraic_eqs)
                    + len(templ.block.init_eqs)
                    + len(templ.block.diff_init_eqs)
                    + len(templ.block.procedural_logic)
                )
                self.assertGreater(executable_content, 0)


if __name__ == "__main__":
    unittest.main()

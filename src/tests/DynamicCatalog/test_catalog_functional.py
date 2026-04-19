from __future__ import annotations

import unittest

from DynamicCatalog._catalog_functional_support import (
    DynamicFunctionalContract,
    FunctionalContract,
    TestDevicesCatalogFunctionalContractsHarness,
    build_dynamic_functional_contracts,
    build_functional_contracts,
)


class TestDevicesCatalogFunctionalContracts(unittest.TestCase):
    """Run the explicit functional contracts for the exported TEST-only catalog."""

    @classmethod
    def setUpClass(cls) -> None:
        """
        Construct the shared harness once for the whole functional suite.

        :return: None.
        """
        cls.harness = TestDevicesCatalogFunctionalContractsHarness()
        cls.harness.setUpClass()

    def test_functional_contracts_match_expected_behavior(self) -> None:
        """
        Validate every explicit static contract declared for the catalog.

        :return: None.
        """
        contract: FunctionalContract
        for contract in build_functional_contracts():
            with self.subTest(label=contract.label, typ_id=contract.typ_id):
                self.harness.evaluate_contract(contract)

    def test_dynamic_signal_and_timer_contracts_match_expected_behavior(self) -> None:
        """
        Validate every explicit dynamic contract declared for the catalog.

        :return: None.
        """
        contract: DynamicFunctionalContract
        for contract in build_dynamic_functional_contracts():
            with self.subTest(label=contract.label, typ_id=contract.typ_id):
                self.harness.simulate_dynamic_contract(contract)


if __name__ == "__main__":
    unittest.main()

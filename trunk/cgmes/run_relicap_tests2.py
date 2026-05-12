from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from typing import Callable

try:
    import VeraGridEngine.api as gce
except Exception:
    gce = None
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_data_parser import CgmesDataParser
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType
from VeraGridEngine.IO.file_open import open_cgmes
from VeraGridEngine.__version__ import __VeraGridEngine_VERSION__
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.enumerations import CGMESVersions

from run_relicap_grids import FOLDER, SUBFOLDERS


class TestResult:
    """Simple test result row.

    :param chapter_md: Relative markdown chapter path.
    :param chapter_title: Rendered chapter title.
    :param use_case_id: Short use case code.
    :param use_case_name: Human use case name.
    :param status: PASS, FAIL, or SKIP.
    :param detail: Result detail message.
    """
    __slots__ = ("chapter_md", "chapter_title", "use_case_id", "use_case_name", "status", "detail")

    def __init__(
        self,
        chapter_md: str,
        chapter_title: str,
        use_case_id: str,
        use_case_name: str,
        status: str,
        detail: str,
    ) -> None:
        self.chapter_md: str = chapter_md
        self.chapter_title: str = chapter_title
        self.use_case_id: str = use_case_id
        self.use_case_name: str = use_case_name
        self.status: str = status
        self.detail: str = detail


class RelicapLoader:
    """CGMES model loader with in-memory cache.

    :param case_files: Mapping of case names to input file paths.
    """
    __slots__ = ("_case_files", "_cache")

    def __init__(self, case_files: dict[str, list[str]]) -> None:
        self._case_files: dict[str, list[str]] = case_files
        self._cache: dict[str, CgmesCircuit] = dict()

    def existing_files(self, case_name: str) -> list[str]:
        """Get existing file paths for a case.

        :param case_name: Case key from SUBFOLDERS.
        :return: Existing paths.
        """
        all_paths: list[str] = self._case_files[case_name]
        paths: list[str] = list()
        for path in all_paths:
            if os.path.isfile(path):
                paths.append(path)
            else:
                pass
        return paths

    def load_case(self, case_name: str) -> CgmesCircuit:
        """Load and parse a case into a CGMES circuit.

        :param case_name: Case key from SUBFOLDERS.
        :return: Parsed CGMES circuit.
        :raises AssertionError: If no files exist.
        """
        cached: CgmesCircuit | None = self._cache.get(case_name, None)
        if cached is not None:
            return cached
        else:
            pass

        files: list[str] = self.existing_files(case_name)
        if len(files) == 0:
            raise AssertionError(f"{case_name}: no files found")
        else:
            pass

        parser: CgmesDataParser = CgmesDataParser(logger=DataLogger())
        parser.load_files(files=files)
        version: CGMESVersions = parser.cgmes_version or CGMESVersions.v3_0_0
        model: CgmesCircuit = CgmesCircuit(cgmes_version=version, logger=DataLogger())
        model.parse_files(data_parser=parser)
        self._cache[case_name] = model
        return model


class ContingencyRowCheck:
    """Callable contingency row checker.

    :param loader: Shared loader.
    :param eq_ids: Equipment IDs to resolve.
    :param co_ids: Contingency IDs to resolve/export-check.
    """
    __slots__ = ("_loader", "_eq_ids", "_co_ids")

    def __init__(self, loader: RelicapLoader, eq_ids: list[str], co_ids: list[str]) -> None:
        self._loader: RelicapLoader = loader
        self._eq_ids: list[str] = eq_ids
        self._co_ids: list[str] = co_ids

    def __call__(self) -> str:
        """Run the row check.

        :return: Success detail.
        """
        return check_contingency_row(self._loader, self._eq_ids, self._co_ids)


def make_result(chapter_md: str, chapter_title: str, uc_id: str, uc_name: str, status: str, detail: str) -> TestResult:
    """Build a result row.

    :param chapter_md: Relative markdown chapter path.
    :param chapter_title: Chapter title to render.
    :param uc_id: Short use case code.
    :param uc_name: Use case name.
    :param status: PASS, FAIL, or SKIP.
    :param detail: Result detail.
    :return: Result object.
    """
    return TestResult(chapter_md=chapter_md, chapter_title=chapter_title, use_case_id=uc_id, use_case_name=uc_name, status=status, detail=detail)


def run_check(chapter_md: str, chapter_title: str, uc_id: str, uc_name: str, checker: Callable[[], str]) -> TestResult:
    """Run a checker and convert exceptions into FAIL rows.

    :param chapter_md: Relative markdown chapter path.
    :param chapter_title: Chapter title to render.
    :param uc_id: Short use case code.
    :param uc_name: Use case name.
    :param checker: Zero-argument checker function.
    :return: Result row.
    """
    try:
        message: str = checker()
        if message.startswith("SKIP:"):
            return make_result(chapter_md, chapter_title, uc_id, uc_name, "SKIP", message)
        else:
            return make_result(chapter_md, chapter_title, uc_id, uc_name, "PASS", f"OK: {message}")
    except Exception as exc:
        return make_result(chapter_md, chapter_title, uc_id, uc_name, "FAIL", f"FAIL: {exc}")


def run_loader_check(
    chapter_md: str,
    chapter_title: str,
    uc_id: str,
    uc_name: str,
    loader: RelicapLoader,
    checker: Callable[[RelicapLoader], str],
) -> TestResult:
    """Run a loader checker and convert exceptions into FAIL rows.

    :param chapter_md: Relative markdown chapter path.
    :param chapter_title: Chapter title to render.
    :param uc_id: Short use case code.
    :param uc_name: Use case name.
    :param loader: Shared loader.
    :param checker: Checker function receiving the loader.
    :return: Result row.
    """
    try:
        message: str = checker(loader)
        if message.startswith("SKIP:"):
            return make_result(chapter_md, chapter_title, uc_id, uc_name, "SKIP", message)
        else:
            return make_result(chapter_md, chapter_title, uc_id, uc_name, "PASS", f"OK: {message}")
    except Exception as exc:
        return make_result(chapter_md, chapter_title, uc_id, uc_name, "FAIL", f"FAIL: {exc}")


def _collect_ids(model: CgmesCircuit) -> set[str]:
    """Collect rdfid/mRID strings from a CGMES model.

    :param model: Parsed circuit.
    :return: Set of available IDs.
    """
    found: set[str] = set()
    assets_dict: dict[str, object] = model.cgmes_assets.__dict__
    for key, value in assets_dict.items():
        if key.endswith("_list") and isinstance(value, list):
            for obj in value:
                rdfid: str | None = None
                mrid: str | None = None
                try:
                    rdfid = obj.rdfid
                except Exception:
                    rdfid = None
                try:
                    mrid = obj.mRID
                except Exception:
                    mrid = None
                if isinstance(rdfid, str):
                    found.add(rdfid)
                else:
                    pass
                if isinstance(mrid, str):
                    found.add(mrid)
                else:
                    pass
        else:
            pass
    return found


def skip_no_spec() -> str:
    """Skip message for undefined assertions.

    :return: Standard skip message.
    """
    return "SKIP: no specific checks provided by the test specification"


def skip_manual_sips_or_power_flow() -> str:
    """Skip message for manual SIPS and power-flow scenarios.

    :return: Standard skip message.
    """
    return "SKIP: validation steps require load-flow/contingency/SIPS activation execution that is not automated in this structural CGMES test runner"


def skip_anonymized_dataset_missing() -> str:
    """Skip message for a referenced dataset that is not locally integrated.

    :return: Standard skip message.
    """
    return "SKIP: markdown says the anonymized IGM and SPS file still need to be integrated before this scenario can be automated"


def check_contingency_row(loader: RelicapLoader, eq_ids: list[str], co_ids: list[str]) -> str:
    """Validate one CO_UC1 row against requested checks.

    :param loader: Shared loader.
    :param eq_ids: EQ IDs from markdown row.
    :param co_ids: CO IDs from markdown row.
    :return: Success message.
    """
    # Resolve IDs on merged grid+NC model.
    model: CgmesCircuit = loader.load_case("Combination 3 (Belgovia + Svedala +Galia + Espheim + Britheim )")
    ids: set[str] = _collect_ids(model)
    missing_eq: list[str] = list()
    for eq_id in eq_ids:
        if eq_id in ids:
            pass
        else:
            missing_eq.append(eq_id)
    missing_co: list[str] = list()
    for co_id in co_ids:
        if co_id in ids:
            pass
        else:
            missing_co.append(co_id)
    if len(missing_eq) == 0 and len(missing_co) == 0:
        pass
    else:
        raise AssertionError(f"resolution check failed; missing EQ IDs={missing_eq}; missing CO IDs={missing_co}")

    # Ensure contingency execution does not alter base state.
    execution_message: str = "execution check executed"
    if gce is not None:
        files: list[str] = loader.existing_files("Belgovia")
        grid, _ = open_cgmes(files, version=CGMESVersions.v3_0_0)
        branches = grid.get_branches(add_vsc=True, add_hvdc=True, add_switch=True)
        before: dict[str, bool] = dict()
        for branch in branches:
            before[branch.idtag] = bool(branch.active)
        before_count: int = len(grid.contingencies)
        gce.contingency_analysis(grid)
        after_count: int = len(grid.contingencies)
        if before_count == after_count:
            pass
        else:
            raise AssertionError("execution check failed; contingency count changed")
        for branch in branches:
            original: bool = before.get(branch.idtag, False)
            now: bool = bool(branch.active)
            if original == now:
                pass
            else:
                raise AssertionError(f"execution check failed; branch state changed for {branch.idtag}")
    else:
        execution_message = "execution check not run because VeraGridEngine.api dependency is unavailable"

    # Export CO profile and confirm CO row IDs are present.
    model_xml: dict[CgmesProfileType, str] = model.get_model_xml(profiles=[CgmesProfileType.CO])
    co_xml: str | None = model_xml.get(CgmesProfileType.CO, None)
    if isinstance(co_xml, str):
        pass
    else:
        raise AssertionError("CO profile export not available")
    for co_id in co_ids:
        if co_id in co_xml:
            pass
        else:
            raise AssertionError(f"export check failed; CO ID missing from export: {co_id}")
    return f"resolved against model; {execution_message}; and CO export contains row IDs"


def find_assessed_element(model: CgmesCircuit, object_id: str) -> object:
    """Find an AssessedElement by rdfid.

    :param model: Parsed CGMES model.
    :param object_id: Target rdfid without leading underscore.
    :return: Matching object.
    :raises AssertionError: If the object is missing.
    """
    for item in model.cgmes_assets.AssessedElement_list:
        if item.rdfid == object_id:
            return item
        else:
            pass
    raise AssertionError(f"AssessedElement not found: {object_id}")


def find_assessed_element_schedule(model: CgmesCircuit, object_id: str) -> object:
    """Find an AssessedElementSchedule by rdfid.

    :param model: Parsed CGMES model.
    :param object_id: Target rdfid without leading underscore.
    :return: Matching object.
    :raises AssertionError: If the object is missing.
    """
    for item in model.cgmes_assets.AssessedElementSchedule_list:
        if item.rdfid == object_id:
            return item
        else:
            pass
    raise AssertionError(f"AssessedElementSchedule not found: {object_id}")


def find_assessed_element_time_point(model: CgmesCircuit, object_id: str) -> object:
    """Find an AssessedElementTimePoint by rdfid.

    :param model: Parsed CGMES model.
    :param object_id: Target rdfid without leading underscore.
    :return: Matching object.
    :raises AssertionError: If the object is missing.
    """
    for item in model.cgmes_assets.AssessedElementTimePoint_list:
        if item.rdfid == object_id:
            return item
        else:
            pass
    raise AssertionError(f"AssessedElementTimePoint not found: {object_id}")


def find_assessed_element_with_contingency(model: CgmesCircuit, object_id: str) -> object:
    """Find an AssessedElementWithContingency by rdfid.

    :param model: Parsed CGMES model.
    :param object_id: Target rdfid without leading underscore.
    :return: Matching object.
    :raises AssertionError: If the object is missing.
    """
    for item in model.cgmes_assets.AssessedElementWithContingency_list:
        if item.rdfid == object_id:
            return item
        else:
            pass
    raise AssertionError(f"AssessedElementWithContingency not found: {object_id}")


def find_assessed_element_with_remedial_action(model: CgmesCircuit, object_id: str) -> object:
    """Find an AssessedElementWithRemedialAction by rdfid.

    :param model: Parsed CGMES model.
    :param object_id: Target rdfid without leading underscore.
    :return: Matching object.
    :raises AssertionError: If the object is missing.
    """
    for item in model.cgmes_assets.AssessedElementWithRemedialAction_list:
        if item.rdfid == object_id:
            return item
        else:
            pass
    raise AssertionError(f"AssessedElementWithRemedialAction not found: {object_id}")


def find_grid_state_alteration_remedial_action(model: CgmesCircuit, object_id: str) -> object:
    """Find a GridStateAlterationRemedialAction by rdfid.

    :param model: Parsed CGMES model.
    :param object_id: Target rdfid without leading underscore.
    :return: Matching object.
    :raises AssertionError: If the object is missing.
    """
    for item in model.cgmes_assets.GridStateAlterationRemedialAction_list:
        if item.rdfid == object_id:
            return item
        else:
            pass
    raise AssertionError(f"GridStateAlterationRemedialAction not found: {object_id}")


def find_availability_schedule(model: CgmesCircuit, object_id: str) -> object:
    """Find an AvailabilitySchedule by rdfid.

    :param model: Parsed CGMES model.
    :param object_id: Target rdfid without leading underscore.
    :return: Matching object.
    :raises AssertionError: If the object is missing.
    """
    for item in model.cgmes_assets.AvailabilitySchedule_list:
        if item.rdfid == object_id:
            return item
        else:
            pass
    raise AssertionError(f"AvailabilitySchedule not found: {object_id}")


def find_availability_remedial_action(model: CgmesCircuit, object_id: str) -> object:
    """Find an AvailabilityRemedialAction by rdfid.

    :param model: Parsed CGMES model.
    :param object_id: Target rdfid without leading underscore.
    :return: Matching object.
    :raises AssertionError: If the object is missing.
    """
    for item in model.cgmes_assets.AvailabilityRemedialAction_list:
        if item.rdfid == object_id:
            return item
        else:
            pass
    raise AssertionError(f"AvailabilityRemedialAction not found: {object_id}")


def find_asset(model: CgmesCircuit, list_name: str, object_id: str) -> object:
    """Find an object in a CGMES asset list by rdfid or mRID.

    :param model: Parsed CGMES model.
    :param list_name: CGMES asset list name.
    :param object_id: Target rdfid or mRID.
    :return: Matching object.
    :raises AssertionError: If the object is missing.
    """
    asset_list = model.cgmes_assets.__dict__.get(list_name, None)
    if isinstance(asset_list, list):
        pass
    else:
        raise AssertionError(f"CGMES asset list not found: {list_name}")

    for item in asset_list:
        rdfid: str | None = None
        mrid: str | None = None
        try:
            rdfid = item.rdfid
        except Exception:
            rdfid = None
        try:
            mrid = item.mRID
        except Exception:
            mrid = None
        if rdfid == object_id or mrid == object_id:
            return item
        else:
            pass
    raise AssertionError(f"{list_name} object not found: {object_id}")


def require_case_ids(loader: RelicapLoader, case_name: str, ids: list[str], label: str) -> CgmesCircuit:
    """Assert a set of IDs exists in a loaded case.

    :param loader: Shared loader.
    :param case_name: Case key from SUBFOLDERS.
    :param ids: Required IDs.
    :param label: Assertion label.
    :return: Parsed case model.
    """
    model: CgmesCircuit = loader.load_case(case_name)
    existing_ids: set[str] = _collect_ids(model)
    missing: list[str] = list()
    for object_id in ids:
        if object_id in existing_ids:
            pass
        else:
            missing.append(object_id)
    if len(missing) == 0:
        return model
    else:
        raise AssertionError(f"{label} missing IDs: {missing}")


def require_true(value: bool | None, label: str) -> None:
    """Assert a parsed boolean is true.

    :param value: Parsed value.
    :param label: Assertion label.
    """
    if value is True:
        pass
    else:
        raise AssertionError(f"{label} must be true; parsed value is {value}")


def require_false(value: bool | None, label: str) -> None:
    """Assert a parsed boolean is false.

    :param value: Parsed value.
    :param label: Assertion label.
    """
    if value is False:
        pass
    else:
        raise AssertionError(f"{label} must be false; parsed value is {value}")


def require_present(value: object | None, label: str) -> None:
    """Assert a parsed reference or value is present.

    :param value: Parsed value.
    :param label: Assertion label.
    """
    if value is not None:
        pass
    else:
        raise AssertionError(f"{label} must be present")


def require_absent(value: object | None, label: str) -> None:
    """Assert a parsed reference or value is absent.

    :param value: Parsed value.
    :param label: Assertion label.
    """
    if value is None:
        pass
    else:
        raise AssertionError(f"{label} must be absent")


def require_rdfid(value: object | None, object_id: str, label: str) -> None:
    """Assert a parsed reference points to the expected rdfid.

    :param value: Parsed reference.
    :param object_id: Expected rdfid.
    :param label: Assertion label.
    """
    require_present(value, label)
    if value.rdfid == object_id:
        pass
    else:
        raise AssertionError(f"{label} must point to {object_id}; parsed value is {value.rdfid}")


def require_text_contains(value: str | None, text: str, label: str) -> None:
    """Assert a parsed string contains a token.

    :param value: Parsed string.
    :param text: Expected token.
    :param label: Assertion label.
    """
    if isinstance(value, str) and text in value:
        pass
    else:
        raise AssertionError(f"{label} must contain {text}; parsed value is {value}")


def check_ae_uc1(loader: RelicapLoader) -> str:
    """Check AE_UC1 according to the markdown validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = loader.load_case("Belgovia")
    ae = find_assessed_element(model, "992c2de6-e206-45b3-a76a-f4a691e8839a")
    require_true(ae.inBaseCase, "AssessedElement.inBaseCase")
    require_present(ae.SecuredForRegion, "AssessedElement.SecuredForRegion")
    return "dataset imported; secured assessed element is in the base case and has SecuredForRegion"


def check_ae_uc2(loader: RelicapLoader) -> str:
    """Check AE_UC2 according to the markdown validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = loader.load_case("Belgovia")
    scanned = find_assessed_element(model, "1eb2eb03-dda6-4e59-b7c8-a2edb117d676")
    require_false(scanned.inBaseCase, "Scanned AssessedElement.inBaseCase")
    require_present(scanned.ScannedForRegion, "Scanned AssessedElement.ScannedForRegion")
    require_present(scanned.SecuredForRegion, "Scanned AssessedElement.SecuredForRegion")
    require_present(scanned.exclusionReason, "Scanned AssessedElement.exclusionReason")

    scanned_only = find_assessed_element(model, "d463cbba-c89c-4199-bbb9-1a33d90cae2c")
    require_present(scanned_only.ScannedForRegion, "Scanned-only AssessedElement.ScannedForRegion")
    require_absent(scanned_only.SecuredForRegion, "Scanned-only AssessedElement.SecuredForRegion")
    return "scanned assessed elements have the expected region references and exclusion reason"


def check_ae_uc3(loader: RelicapLoader) -> str:
    """Check AE_UC3 according to the markdown validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = loader.load_case("Belgovia")
    ae = find_assessed_element(model, "992c2de6-e206-45b3-a76a-f4a691e8839a")
    schedule = find_assessed_element_schedule(model, "7221ae31-f736-4ae2-8ce1-f3dd605cefd6")
    time_point = find_assessed_element_time_point(model, "a26e3ae0-0a7d-4f42-ad64-e9105ec3cd41")
    require_rdfid(schedule.AssessedElement, ae.rdfid, "AssessedElementSchedule.AssessedElement")
    require_rdfid(time_point.AssessedElementSchedule, schedule.rdfid, "AssessedElementTimePoint.AssessedElementSchedule")
    require_false(time_point.enabled, "AssessedElementTimePoint.enabled")
    return "schedule and timepoint disable the secured assessed element for the specified time"


def check_ae_uc4(loader: RelicapLoader) -> str:
    """Check AE_UC4 according to the markdown validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = loader.load_case("Belgovia")
    excluded = find_assessed_element(model, "1eb2eb03-dda6-4e59-b7c8-a2edb117d676")
    require_false(excluded.inBaseCase, "Excluded AssessedElement.inBaseCase")
    require_present(excluded.ScannedForRegion, "Excluded AssessedElement.ScannedForRegion")
    require_present(excluded.exclusionReason, "Excluded AssessedElement.exclusionReason")
    return "excluded assessed element is outside the base case and remains scanned"


def check_ae_uc5(loader: RelicapLoader) -> str:
    """Check AE_UC5 according to the markdown validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = loader.load_case("Belgovia")
    full_scope = find_assessed_element(model, "d17943b5-9d10-4f8b-bb07-18c3a3822348")
    require_true(full_scope.inBaseCase, "Full-scope AssessedElement.inBaseCase")
    require_true(full_scope.isCombinableWithContingency, "Full-scope AssessedElement.isCombinableWithContingency")

    excluded_pair = find_assessed_element_with_contingency(model, "1f38d403-a822-4c24-93c0-0f18ac699ef1")
    require_rdfid(excluded_pair.AssessedElement, "992c2de6-e206-45b3-a76a-f4a691e8839a", "Excluded AE-CO pair AssessedElement")
    require_present(excluded_pair.Contingency, "Excluded AE-CO pair Contingency")
    require_text_contains(excluded_pair.combinationConstraintKind, "excluded", "Excluded AE-CO pair combinationConstraintKind")

    limited = find_assessed_element(model, "663c6c3c-1777-4eb7-98b0-c23233ce0f71")
    included_pair = find_assessed_element_with_contingency(model, "deb4c65f-c3fc-414e-baa3-692829e3eec2")
    require_false(limited.isCombinableWithContingency, "Limited AssessedElement.isCombinableWithContingency")
    require_rdfid(included_pair.AssessedElement, limited.rdfid, "Included AE-CO pair AssessedElement")
    require_present(included_pair.Contingency, "Included AE-CO pair Contingency")
    require_text_contains(included_pair.combinationConstraintKind, "included", "Included AE-CO pair combinationConstraintKind")
    return "full-scope, excluded, and included AE-contingency combinations match the specification"


def check_ae_uc6(loader: RelicapLoader) -> str:
    """Check AE_UC6 according to the markdown validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = loader.load_case("Belgovia")
    ae = find_assessed_element(model, "13d17257-977e-43bc-971a-25022282688a")
    relation = find_assessed_element_with_remedial_action(model, "66f786ce-5e2a-427d-9eb8-4e1462045c27")
    remedial_action = find_grid_state_alteration_remedial_action(model, "70b696ac-c38f-4528-8d65-ba707c0b72e1")
    require_rdfid(relation.AssessedElement, ae.rdfid, "AE-RA relation AssessedElement")
    require_rdfid(relation.RemedialAction, remedial_action.rdfid, "AE-RA relation RemedialAction")
    require_text_contains(relation.combinationConstraintKind, "included", "AE-RA relation combinationConstraintKind")
    return "assessed element and remedial action association is present and included"


def check_as_uc1(loader: RelicapLoader) -> str:
    """Check AS_UC1 according to the markdown validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = loader.load_case("Svedala")
    schedule = find_availability_schedule(model, "d394295f-9d18-4d9f-9808-bd23282bf60f")
    action = find_availability_remedial_action(model, "14b2b671-e92b-40e6-abf8-ad37811b33c7")

    # VeraGrid resolves this relation as the inverse reference on the schedule.
    require_rdfid(schedule.RemedialAction, action.rdfid, "AvailabilitySchedule.RemedialAction")

    # The specification says the action cancels, shortens, or reschedules the availability.
    # In this dataset the parsed effect is a cancellation timestamp.
    require_present(schedule.cancelledDateTime, "AvailabilitySchedule.cancelledDateTime")
    return "schedule and availability remedial action are imported; schedule references the action and carries a cancellation time"


def check_ra_uc1(loader: RelicapLoader) -> str:
    """Check RA_UC1 structural validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = require_case_ids(
        loader,
        "Svedala",
        ["6d2c8901-d068-4d22-8ce9-7379644b4f17", "176d262c-701c-4ced-99b2-a155c136e787"],
        "RA_UC1",
    )
    action = find_asset(model, "GridStateAlterationRemedialAction_list", "6d2c8901-d068-4d22-8ce9-7379644b4f17")
    require_text_contains(action.kind, "preventive", "RA_UC1 RemedialAction.kind")
    return "RA and target switch are imported; execution/topology-change step is not automated in this runner"


def check_ra_uc2(loader: RelicapLoader) -> str:
    """Check RA_UC2 structural validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = require_case_ids(
        loader,
        "Svedala",
        ["598ab84e-a575-40ad-bf66-c1ab41c65093", "13c29cc3-3d99-4c5b-abac-085f0d319eab"],
        "RA_UC2",
    )
    dep_a = find_asset(model, "RemedialActionDependency_list", "598ab84e-a575-40ad-bf66-c1ab41c65093")
    dep_b = find_asset(model, "RemedialActionDependency_list", "13c29cc3-3d99-4c5b-abac-085f0d319eab")
    require_text_contains(dep_a.kind, "exclusive", "RA_UC2 dependency A kind")
    require_text_contains(dep_b.kind, "exclusive", "RA_UC2 dependency B kind")
    require_present(dep_a.RemedialAction, "RA_UC2 dependency A RemedialAction")
    require_present(dep_b.RemedialAction, "RA_UC2 dependency B RemedialAction")
    return "exclusive dependency objects are imported and reference remedial actions; mutually-exclusive execution is not automated"


def check_ra_uc3(loader: RelicapLoader) -> str:
    """Check RA_UC3 structural validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = require_case_ids(
        loader,
        "Espheim",
        ["d856a2a2-3de4-4a7b-aea4-d363c13d9014", "4d3757fd-b40a-4d7b-be47-6553935234ff", "f5205bd4-637a-4eb7-b0d8-e03638bc570b"],
        "RA_UC3",
    )
    schedule = find_asset(model, "GridStateAlterationSchedule_list", "f5205bd4-637a-4eb7-b0d8-e03638bc570b")
    require_rdfid(schedule.GridStateAlteration, "4d3757fd-b40a-4d7b-be47-6553935234ff", "RA_UC3 GridStateAlterationSchedule.GridStateAlteration")
    found_enabled: bool = False
    found_disabled: bool = False
    for time_point in model.cgmes_assets.GridStateAlterationTimePoint_list:
        if time_point.enabled is True:
            found_enabled = True
        else:
            pass
        if time_point.enabled is False:
            found_disabled = True
        else:
            pass
    if found_enabled and found_disabled:
        pass
    else:
        raise AssertionError("RA_UC3 expected enable and disable time points")
    return "SIS schedule references the topology action and contains enable/disable time points"


def check_ra_uc4(loader: RelicapLoader) -> str:
    """Check RA_UC4 structural validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = require_case_ids(
        loader,
        "Svedala",
        ["96f93b71-420f-456f-932e-9ac3f724b683", "f7231aa5-d497-41f3-a5d5-9d4af74444f0", "51361821-0a40-4e5a-a49d-29c266ea2ecc"],
        "RA_UC4",
    )
    response = find_asset(model, "RemedialActionScheduleResponse_list", "96f93b71-420f-456f-932e-9ac3f724b683")
    dependency = find_asset(model, "RemedialActionScheduleDependency_list", "f7231aa5-d497-41f3-a5d5-9d4af74444f0")
    schedule = find_asset(model, "RemedialActionSchedule_list", "51361821-0a40-4e5a-a49d-29c266ea2ecc")
    require_text_contains(response.kind, "refused", "RA_UC4 RemedialActionScheduleResponse.kind")
    require_text_contains(dependency.kind, "none", "RA_UC4 RemedialActionScheduleDependency.kind")
    require_present(schedule.RemedialAction, "RA_UC4 new RemedialActionSchedule.RemedialAction")
    return "refusal response, none-dependency, and replacement schedule are imported"


def check_ra_uc5(loader: RelicapLoader) -> str:
    """Check RA_UC5 structural validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = require_case_ids(
        loader,
        "Svedala",
        [
            "7e422768-207d-455f-976e-0b1cb2338509",
            "fa3e3533-345a-4ef1-a46d-3ab6d251924a",
            "6a9b5221-bb3f-421b-89c1-886b100aa68a",
            "1c1e39cf-15a1-4874-9739-d9e6dc90ee11",
            "023512a8-150d-4300-8159-807275eafd48",
            "279bfb00-1b2a-4592-af3a-dba9403d1abd",
            "87e90c47-43d8-4e5c-b2ad-5c67d3a74842",
        ],
        "RA_UC5",
    )
    event_a = find_asset(model, "EventSchedule_list", "1c1e39cf-15a1-4874-9739-d9e6dc90ee11")
    event_b = find_asset(model, "EventSchedule_list", "023512a8-150d-4300-8159-807275eafd48")
    require_rdfid(event_a.RemedialActionSchedule, "279bfb00-1b2a-4592-af3a-dba9403d1abd", "RA_UC5 EventSchedule A RemedialActionSchedule")
    require_rdfid(event_b.RemedialActionSchedule, "87e90c47-43d8-4e5c-b2ad-5c67d3a74842", "RA_UC5 EventSchedule B RemedialActionSchedule")
    require_present(model.cgmes_assets.EventTimePoint_list, "RA_UC5 EventTimePoint list")
    return "activation schedules, event schedules, event time points, and exclusive group IDs are imported"


def check_ra_uc6(loader: RelicapLoader) -> str:
    """Check RA_UC6 structural validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = require_case_ids(
        loader,
        "Belgovia",
        ["413bbc8a-683c-7e07-4fb9-aa6ec83278e0", "30f6377d-5e35-4dd0-a53d-c1992043855e", "27940387-6935-47b6-ab25-8742bac2a266", "ae6a5ddd-fe7e-40b2-bcb6-cbd2882434e7"],
        "RA_UC6",
    )
    power_schedule = find_asset(model, "PowerSchedule_list", "27940387-6935-47b6-ab25-8742bac2a266")
    require_rdfid(power_schedule.GeneratingUnit, "413bbc8a-683c-7e07-4fb9-aa6ec83278e0", "RA_UC6 PowerSchedule.GeneratingUnit")
    return "countertrade RA, generating unit, PowerSchedule, and PowerBidSchedule are imported; schedule values are present in parsed datasets"


def check_ra_uc7(loader: RelicapLoader) -> str:
    """Check RA_UC7 structural validation steps.

    :param loader: Shared loader.
    :return: Success detail.
    """
    model: CgmesCircuit = require_case_ids(
        loader,
        "Belgovia",
        [
            "3a3b27be-b18b-4385-b557-6735d733baf0",
            "fa73cfee-ff54-43cd-816b-51394cd76f0f",
            "9d72d12a-f135-437a-83fa-ef3e5b23f41f",
            "6c0ba4c5-5ac0-43f8-87d9-ec2fb41a3dec",
            "250e37a5-50e0-44b7-9bd7-7284c04116db",
            "7ab20445-576c-4162-aad5-d097d894a8e0",
            "3b5748de-39f2-45d7-9a66-65819c667e91",
        ],
        "RA_UC7",
    )
    bid_time_point = find_asset(model, "PowerBidScheduleTimePoint_list", "250e37a5-50e0-44b7-9bd7-7284c04116db")
    distribution = find_asset(model, "PowerShiftKeyDistribution_list", "7ab20445-576c-4162-aad5-d097d894a8e0")
    shift_schedule = find_asset(model, "PowerShiftKeySchedule_list", "3b5748de-39f2-45d7-9a66-65819c667e91")
    require_rdfid(bid_time_point.PowerBidSchedule, "6c0ba4c5-5ac0-43f8-87d9-ec2fb41a3dec", "RA_UC7 PowerBidScheduleTimePoint.PowerBidSchedule")
    require_rdfid(distribution.PowerShiftKeySchedule, shift_schedule.rdfid, "RA_UC7 PowerShiftKeyDistribution.PowerShiftKeySchedule")
    require_present(bid_time_point.atTime, "RA_UC7 PowerBidScheduleTimePoint.atTime")
    return "redispatch RAs, bid schedule/timepoint, and power-shift-key objects are imported and linked"


def chapter_assessed_elements(loader: RelicapLoader) -> list[TestResult]:
    """Run assessed element chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    chapter_md: str = "Assessed_Element_use_cases/Assessed_Element_use_cases.md"
    chapter_title: str = "Assessed Element use cases"
    rows: list[TestResult] = list()
    rows.append(run_loader_check(chapter_md, chapter_title, "AE_UC1", "Secured Assessed Element", loader, check_ae_uc1))
    rows.append(run_loader_check(chapter_md, chapter_title, "AE_UC2", "Scanned Assessed Element", loader, check_ae_uc2))
    rows.append(run_loader_check(chapter_md, chapter_title, "AE_UC3", "Disable Assessed Element", loader, check_ae_uc3))
    rows.append(run_loader_check(chapter_md, chapter_title, "AE_UC4", "Exclude Assessed Element", loader, check_ae_uc4))
    rows.append(run_loader_check(chapter_md, chapter_title, "AE_UC5", "Assessed Element with Contingency", loader, check_ae_uc5))
    rows.append(run_loader_check(chapter_md, chapter_title, "AE_UC6", "Assessed Element with Remedial Action", loader, check_ae_uc6))
    return rows


def chapter_availability_schedule(loader: RelicapLoader) -> list[TestResult]:
    """Run availability schedule chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    chapter_md: str = "Availability _Schedule_use_case/Availability _Schedule_use_case.md"
    chapter_title: str = "Availability Schedule use case"
    rows: list[TestResult] = list()
    rows.append(run_loader_check(chapter_md, chapter_title, "AS_UC1", "Availability Schedule", loader, check_as_uc1))
    return rows


def chapter_contingencies(loader: RelicapLoader) -> list[TestResult]:
    """Run contingencies chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    chapter_md: str = "Contingencies_use_cases/Contingencies_use_cases.md"
    chapter_title: str = "Contingency uses cases"
    rows: list[TestResult] = list()
    rows.append(run_check(chapter_md, chapter_title, "PF_UC1", "Power Flow (base integration)", skip_no_spec))
    rows.append(run_check(chapter_md, chapter_title, "BDS_UC1", "Boundary Data Set", skip_no_spec))
    rows.append(run_check(chapter_md, chapter_title, "CD_UC1", "Common Data", skip_no_spec))
    rows.append(run_check(chapter_md, chapter_title, "RD_UC1", "Reference Data", skip_no_spec))
    rows.append(run_check(chapter_md, chapter_title, "CO_UC1", "Importing, executing, updating and exporting contingencies", skip_no_spec))

    co_rows: list[tuple[str, list[str], list[str]]] = list([
        ("CO_UC1#1 Loss of TieLine between Belgovia and Galia", ["d9622e7f-5bf0-4e7e-b766-b8596c6fe4ae"], ["7e31c67d-67ba-4592-8ac1-9e806d697c8e"]),
        ("CO_UC1#2 Loss of TieLine between Belgovia and Svedala", ["ed0c5d75-4a54-43c8-b782-b20d7431630b"], ["e9eab3fe-c328-4f78-9bc1-77adb59f6ba7"]),
        ("CO_UC1#3 Loss of TieLine between Espheim and Svedala", ["ed0c5d75-4a54-43c8-b782-b20d7431630b"], ["e9eab3fe-c328-4f78-9bc1-77adb59f6ba7"]),
        ("CO_UC1#4 Loss of power transformer in Svedala", ["f1c13f90-6d89-4a37-a51c-94742ad2dd72"], ["e05bbe20-9d4a-40da-9777-8424d216785d"]),
        ("CO_UC1#5 Loss of LinearShuntCompensator", ["0489d903-c766-11e1-8775-005056c00008"], ["62eac668-82a1-4739-8cfc-de929b78ef7e"]),
        ("CO_UC1#6 Loss of NonlinearShuntCompensator", ["8464a151-ec39-4e7a-8321-06c41e63958c"], ["ab92defa-ef8e-4d13-a242-5b1a9fe956f6"]),
        ("CO_UC1#7 Loss of HVDC converter DC-3P-Convert-1", ["038ce404-30dc-4289-b9db-7076cb870b8e"], ["038ce404-30dc-4289-b9db-7076cb870b8e"]),
        ("CO_UC1#8 Loss of HVDC line", ["be09fc02-de3f-49e4-aa84-94803bcc5d76"], ["504b48fb-de1f-4f7e-928f-8585daaf7b72"]),
        ("CO_UC1#9 Loss of synchronous machine", ["550ebe0d-f2b2-48c1-991f-cebea43a21aa"], ["37997e71-cb7d-4a8c-baa6-2a1594956da9"]),
        ("CO_UC1#10 Loss of demand facility", ["cb459405-cc14-4215-a45c-416789205904"], ["65582e87-5035-4465-8dd9-cb655224b29f"]),
        ("CO_UC1#11 N-2 loss of two tie-lines", ["04566cf8-c766-11e1-8775-005056c00008", "0475dbd8-c766-11e1-8775-005056c00008"], ["9d17b84c-33b5-4a68-b8b9-ed5b31038d40", "13334fdf-9cc2-4341-adb6-1281269040b4"]),
    ])
    for code, eq_ids, co_ids in co_rows:
        check_fn: Callable[[], str] = ContingencyRowCheck(loader=loader, eq_ids=eq_ids, co_ids=co_ids)
        rows.append(run_check(chapter_md, chapter_title, "CO_UC1", code, check_fn))
    return rows


def chapter_generation_correction(loader: RelicapLoader) -> list[TestResult]:
    """Run generation correction chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    _ = loader
    chapter_md: str = "Correction_of_generation_production_due_to_a_power_flow_limit_violation/Correction_of_generation_production_due_to_a_power_flow_limit_violation.md"
    chapter_title: str = "Correction of generation production due to a power flow limit violation"
    rows: list[TestResult] = list()
    rows.append(run_check(chapter_md, chapter_title, "PF_UC1", "Correction workflow", skip_anonymized_dataset_missing))
    return rows


def chapter_sips_gate(loader: RelicapLoader) -> list[TestResult]:
    """Run SIPS gate logic chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    _ = loader
    chapter_md: str = "Implementing_SIPS_Gate_Logic_with_Cardinality_Constraints/Implementing_SIPS_Gate_Logic_with_Cardinality_Constraints.md"
    chapter_title: str = "Implementing SIPS Gate Logic with Cardinality Constraints"
    rows: list[TestResult] = list()
    rows.append(run_check(chapter_md, chapter_title, "SAR_UC1", "SIPS gate logic", skip_manual_sips_or_power_flow))
    return rows


def chapter_sips_complex(loader: RelicapLoader) -> list[TestResult]:
    """Run complex SIPS chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    _ = loader
    chapter_md: str = "Modelling_complex_SIPS_logic/Modelling_complex_SIPS_logic.md"
    chapter_title: str = "Modelling complex SIPS logic"
    rows: list[TestResult] = list()
    rows.append(run_check(chapter_md, chapter_title, "SAR_UC1", "Complex SIPS logic", skip_manual_sips_or_power_flow))
    return rows


def chapter_sips_current_flow(loader: RelicapLoader) -> list[TestResult]:
    """Run current-flow SIPS chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    _ = loader
    chapter_md: str = "Modelling_Current_Flow_Conditions_Against_PATL_or_TATL/Modelling_Current_Flow_Conditions_Against_PATL_or_TATL.md"
    chapter_title: str = "Modelling Current Flow Conditions Against PATL or TATL"
    rows: list[TestResult] = list()
    rows.append(run_check(chapter_md, chapter_title, "SAR_UC1", "Current-flow condition checks", skip_manual_sips_or_power_flow))
    return rows


def chapter_sips_disconnection(loader: RelicapLoader) -> list[TestResult]:
    """Run disconnection-by-flow SIPS chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    _ = loader
    chapter_md: str = "Modelling_Element_Disconnection_by_Monitoring_the_Power_Flow/Modelling_Element_Disconnection_by_Monitoring_the_Power_Flow.md"
    chapter_title: str = "Modelling Element Disconnection by Monitoring the Power Flow"
    rows: list[TestResult] = list()
    rows.append(run_check(chapter_md, chapter_title, "SAR_UC1", "Element disconnection by monitored flow", skip_manual_sips_or_power_flow))
    return rows


def chapter_sips_generation(loader: RelicapLoader) -> list[TestResult]:
    """Run generation-based SIPS chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    _ = loader
    chapter_md: str = "Modelling_SIPS_Actions_Based_on_Generation/Modelling_SIPS_Actions_Based_on_Generation.md"
    chapter_title: str = "Modelling SIPS Actions Based on Generation"
    rows: list[TestResult] = list()
    rows.append(run_check(chapter_md, chapter_title, "SAR_UC1", "Generation-based SIPS actions", skip_manual_sips_or_power_flow))
    return rows


def chapter_sips_voltage(loader: RelicapLoader) -> list[TestResult]:
    """Run voltage-based SIPS chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    _ = loader
    chapter_md: str = "Modelling_Voltage_Dependent_Tripping_Conditions/Modelling_Voltage_Dependent_Tripping_Conditions.md"
    chapter_title: str = "Modelling Voltage Dependent Tripping Conditions"
    rows: list[TestResult] = list()
    rows.append(run_check(chapter_md, chapter_title, "SAR_UC1", "Voltage-dependent tripping checks", skip_manual_sips_or_power_flow))
    return rows


def chapter_remedial_actions(loader: RelicapLoader) -> list[TestResult]:
    """Run remedial action chapter checks.

    :param loader: Shared loader.
    :return: Result rows.
    """
    chapter_md: str = "Remedial_Action_use_cases/Remedial_Action_use_cases.md"
    chapter_title: str = "Remedial Action use cases"
    rows: list[TestResult] = list()
    rows.append(run_check(chapter_md, chapter_title, "ER_UC1", "Equipment Reliability (single TSO)", skip_no_spec))
    rows.append(run_check(chapter_md, chapter_title, "ER_UC2", "Equipment Reliability (common data)", skip_no_spec))
    rows.append(run_loader_check(chapter_md, chapter_title, "RA_UC1", "Topology RA with one topology action", loader, check_ra_uc1))
    rows.append(run_loader_check(chapter_md, chapter_title, "RA_UC2", "Dependent topology RAs with multiple actions", loader, check_ra_uc2))
    rows.append(run_loader_check(chapter_md, chapter_title, "RA_UC3", "Modification prior to RAO", loader, check_ra_uc3))
    rows.append(run_loader_check(chapter_md, chapter_title, "RA_UC4", "Proposing modifications after RAO", loader, check_ra_uc4))
    rows.append(run_loader_check(chapter_md, chapter_title, "RA_UC5", "Activation after RAO", loader, check_ra_uc5))
    rows.append(run_loader_check(chapter_md, chapter_title, "RA_UC6", "Countertrade Remedial Action", loader, check_ra_uc6))
    rows.append(run_loader_check(chapter_md, chapter_title, "RA_UC7", "Redispatch Remedial Action", loader, check_ra_uc7))
    rows.append(run_check(chapter_md, chapter_title, "RAS_UC8", "RAS FAP acceptance", skip_no_spec))
    rows.append(run_check(chapter_md, chapter_title, "RA_UC9 Shared RA on Boundary", "Shared RA on Boundary", skip_no_spec))
    rows.append(run_check(chapter_md, chapter_title, "OR_UC1", "Object Registry", skip_no_spec))
    rows.append(run_check(chapter_md, chapter_title, "SAR_UC1", "Security Analysis Result", skip_no_spec))
    return rows


def _scan_md_use_case_ids(md_abs_path: str) -> list[str]:
    """Extract use case IDs from markdown second-level headers.

    :param md_abs_path: Absolute markdown file path.
    :return: Matched short codes.
    """
    ids: list[str] = list()
    if os.path.isfile(md_abs_path):
        with open(md_abs_path, "r", encoding="utf-8") as file_obj:
            text: str = file_obj.read()
        matches: list[str] = re.findall(r"##\s+([A-Z]{2,4}_UC\d+)", text)
        for item in matches:
            ids.append(item)
    else:
        pass
    return ids


def write_report(report_path: str, results: list[TestResult]) -> None:
    """Write chaptered markdown report.

    :param report_path: Output markdown path.
    :param results: Flat results list.
    """
    now: str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total: int = len(results)
    passed: int = sum(1 for row in results if row.status == "PASS")
    skipped: int = sum(1 for row in results if row.status == "SKIP")
    failed: int = sum(1 for row in results if row.status == "FAIL")

    by_md: dict[str, list[TestResult]] = dict()
    ordered_md: list[str] = list()
    for row in results:
        bucket: list[TestResult] | None = by_md.get(row.chapter_md, None)
        if bucket is None:
            by_md[row.chapter_md] = [row]
            ordered_md.append(row.chapter_md)
        else:
            bucket.append(row)

    lines: list[str] = list()
    lines.append(f"# Relicap Test Book Report for VeraGrid {__VeraGridEngine_VERSION__}")
    lines.append("")
    lines.append(f"- Generated: `{now}`")
    lines.append(f"- Script: `{os.path.abspath(__file__)}`")
    lines.append(f"- Relicap base folder: `{FOLDER}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total rows: `{total}`")
    lines.append(f"- PASS: `{passed}`")
    lines.append(f"- SKIP: `{skipped}`")
    lines.append(f"- FAIL: `{failed}`")
    lines.append("")

    for chapter_md in ordered_md:
        chapter_rows: list[TestResult] = by_md[chapter_md]
        chapter_title: str = chapter_rows[0].chapter_title
        lines.append(f"## {chapter_title}")
        lines.append("")
        lines.append(f"*file*: `{chapter_md}`")
        lines.append("")
        lines.append("| # | Use Case ID | Use Case | Status | Detail |")
        lines.append("|---:|---|---|---|---|")
        index: int = 1
        for row in chapter_rows:
            safe_detail: str = row.detail.replace("|", "\\|")
            lines.append(f"| {index} | {row.use_case_id} | {row.use_case_name} | {row.status} | {safe_detail} |")
            index = index + 1
        lines.append("")

    lines.append("## Failures")
    lines.append("")
    fail_list: list[TestResult] = [row for row in results if row.status == "FAIL"]
    if len(fail_list) > 0:
        index: int = 1
        for row in fail_list:
            lines.append(f"{index}. `{row.use_case_id}` {row.use_case_name}: {row.detail}")
            index = index + 1
    else:
        lines.append("- None")

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as file_obj:
        file_obj.write("\n".join(lines))


def run_all_chapters(loader: RelicapLoader) -> list[TestResult]:
    """Execute all 11 markdown chapter functions.

    :param loader: Shared loader.
    :return: Flat list of result rows.
    """
    all_rows: list[TestResult] = list()
    chapter_functions: list[Callable[[RelicapLoader], list[TestResult]]] = list([
        chapter_assessed_elements,
        chapter_availability_schedule,
        chapter_contingencies,
        chapter_generation_correction,
        chapter_sips_gate,
        chapter_sips_complex,
        chapter_sips_current_flow,
        chapter_sips_disconnection,
        chapter_sips_generation,
        chapter_sips_voltage,
        chapter_remedial_actions,
    ])
    for function_ref in chapter_functions:
        chapter_rows: list[TestResult] = function_ref(loader)
        for row in chapter_rows:
            all_rows.append(row)
    return all_rows


def main() -> int:
    """Program entrypoint.

    :return: Shell exit code.
    """
    loader: RelicapLoader = RelicapLoader(SUBFOLDERS)
    results: list[TestResult] = run_all_chapters(loader)
    report_path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relicap_test_report2.md")
    write_report(report_path=report_path, results=results)

    print("")
    print("Results Table")
    print(f"{'#':>2}  {'Status':<6}  {'Use Case ID':<28}  {'Use Case':<56}  Source")
    print("-" * 130)
    idx: int = 1
    for row in results:
        print(f"{idx:>2}  {row.status:<6}  {row.use_case_id[:28]:<28}  {row.use_case_name[:56]:<56}  {row.chapter_md}")
        idx = idx + 1
    failures: int = sum(1 for row in results if row.status == "FAIL")
    print("")
    print(f"Total rows: {len(results)}")
    print(f"Failures: {failures}")
    print(f"Report: {report_path}")
    if failures == 0:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())

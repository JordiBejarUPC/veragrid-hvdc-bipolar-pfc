from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import VeraGridEngine as vg
import VeraGridEngine.api as gce
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_data_parser import CgmesDataParser
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType
from VeraGridEngine.IO.file_open import open_cgmes
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.enumerations import CGMESVersions
from VeraGridEngine.__version__ import __VeraGridEngine_VERSION__

from run_relicap_grids import FOLDER, SUBFOLDERS

USE_CASES_ROOT = "/home/santi/Git/GitHub/relicapgrid/TestUseCases"


@dataclass
class ChapterResult:
    use_case_id: str
    name: str
    source_md: str
    ok: bool
    message: str
    status: str


class RelicapCgmesLoader:
    def __init__(self, case_files: dict[str, list[str]]):
        self.case_files = case_files
        self._cache: dict[str, CgmesCircuit] = {}
        self._co_exec_check_done: bool = False
        self._co_exec_check_ok: bool = False
        self._co_exec_check_message: str = "not executed"

    def load_case(self, case_name: str) -> CgmesCircuit:
        cached = self._cache.get(case_name)
        if cached is not None:
            return cached

        files = [path for path in self.case_files[case_name] if os.path.isfile(path)]
        if not files:
            raise AssertionError(f"{case_name}: no files found")

        parser = CgmesDataParser(logger=DataLogger())
        parser.load_files(files=files)
        version = parser.cgmes_version or CGMESVersions.v3_0_0

        model = CgmesCircuit(cgmes_version=version, logger=DataLogger())
        model.parse_files(data_parser=parser)

        self._cache[case_name] = model
        return model

    def get_existing_files(self, case_name: str) -> list[str]:
        files = [path for path in self.case_files[case_name] if os.path.isfile(path)]
        return files

    def case_file_stats(self, case_name: str) -> tuple[int, int]:
        files = self.case_files[case_name]
        existing = sum(1 for path in files if os.path.isfile(path))
        missing = len(files) - existing
        return existing, missing

    @staticmethod
    def find_object(model: CgmesCircuit, object_id: str):
        for list_name, object_list in model.cgmes_assets.__dict__.items():
            if list_name.endswith("_list") and isinstance(object_list, list):
                for obj in object_list:
                    if getattr(obj, "rdfid", None) == object_id or getattr(obj, "mRID", None) == object_id:
                        return list_name, obj
        return None, None


def _check_found(model: CgmesCircuit, object_id: str, label: str) -> object:
    list_name, obj = RelicapCgmesLoader.find_object(model, object_id)
    if obj is None:
        raise AssertionError(f"{label}: object {object_id} not found")
    return obj


def chapter_assessed_elements(loader: RelicapCgmesLoader) -> str:
    model = loader.load_case("Belgovia")

    ae_secured = _check_found(model, "992c2de6-e206-45b3-a76a-f4a691e8839a", "Secured AE")
    assert getattr(ae_secured, "inBaseCase", None) is True, "Secured AE must be in base case"

    ae_scanned = _check_found(model, "1eb2eb03-dda6-4e59-b7c8-a2edb117d676", "Scanned AE")
    assert getattr(ae_scanned, "inBaseCase", None) is False, "Scanned AE must not be in base case"
    assert getattr(ae_scanned, "ScannedForRegion", None) is not None, "Scanned AE must have ScannedForRegion"

    ae_scanned_only = _check_found(model, "d463cbba-c89c-4199-bbb9-1a33d90cae2c", "Scanned-only AE")
    assert getattr(ae_scanned_only, "ScannedForRegion", None) is not None, "Scanned-only AE must have ScannedForRegion"
    assert getattr(ae_scanned_only, "SecuredForRegion", None) is None, "Scanned-only AE must not have SecuredForRegion"

    _check_found(model, "7221ae31-f736-4ae2-8ce1-f3dd605cefd6", "AssessedElementSchedule")
    ae_timepoint = _check_found(model, "a26e3ae0-0a7d-4f42-ad64-e9105ec3cd41", "AssessedElementTimePoint")
    assert getattr(ae_timepoint, "enabled", None) is False, "AssessedElementTimePoint must disable AE"

    ae_full_scope = _check_found(model, "d17943b5-9d10-4f8b-bb07-18c3a3822348", "AE full scope")
    assert getattr(ae_full_scope, "isCombinableWithContingency", None) is True, "AE full scope must be combinable"
    ae_limited = _check_found(model, "663c6c3c-1777-4eb7-98b0-c23233ce0f71", "AE limited scope")
    assert getattr(ae_limited, "isCombinableWithContingency", None) is False, "AE limited scope must be non-combinable"
    _check_found(model, "1f38d403-a822-4c24-93c0-0f18ac699ef1", "Excluded AE-CO pair")
    _check_found(model, "deb4c65f-c3fc-414e-baa3-692829e3eec2", "Included AE-CO pair")

    ae_ra_link = _check_found(model, "66f786ce-5e2a-427d-9eb8-4e1462045c27", "AE-RA link")
    assert getattr(ae_ra_link, "AssessedElement", None) is not None, "AE-RA link needs AssessedElement"
    assert getattr(ae_ra_link, "RemedialAction", None) is not None, "AE-RA link needs RemedialAction"
    return "assessed element IDs and key flags are valid"


def chapter_availability_schedule(loader: RelicapCgmesLoader) -> str:
    model = loader.load_case("Svedala")
    _check_found(model, "d394295f-9d18-4d9f-9808-bd23282bf60f", "AvailabilitySchedule")
    _check_found(model, "14b2b671-e92b-40e6-abf8-ad37811b33c7", "AvailabilityRemedialAction")
    return "availability schedule and remedial action objects are present"


def chapter_contingencies(loader: RelicapCgmesLoader) -> str:
    model = loader.load_case("Belgovia")
    contingency_lists = [
        model.cgmes_assets.Contingency_list,
        model.cgmes_assets.OrdinaryContingency_list,
        model.cgmes_assets.ExceptionalContingency_list,
        model.cgmes_assets.OutOfRangeContingency_list,
    ]
    count = sum(len(lst) for lst in contingency_lists)
    assert count > 0, "No contingency objects found in Belgovia CO data"
    return f"found {count} contingency objects across CO classes"


def chapter_generation_correction(_: RelicapCgmesLoader) -> str:
    return "SKIP: markdown says anonymized IGM still needs integration"


def chapter_sips_gate_logic(_: RelicapCgmesLoader) -> str:
    return "SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance"


def chapter_sips_current_flow(_: RelicapCgmesLoader) -> str:
    return "SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance"


def chapter_sips_last_line(_: RelicapCgmesLoader) -> str:
    return "SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance"


def chapter_sips_generation(_: RelicapCgmesLoader) -> str:
    return "SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance"


def chapter_sips_voltage(_: RelicapCgmesLoader) -> str:
    return "SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance"


def chapter_sips_complex(_: RelicapCgmesLoader) -> str:
    return "SKIP: dedicated SIPS datasets referenced in markdown are not available in local instance"


def chapter_remedial_actions(loader: RelicapCgmesLoader) -> str:
    svedala = loader.load_case("Svedala")
    espheim = loader.load_case("Espheim")
    belgovia = loader.load_case("Belgovia")

    _check_found(svedala, "6d2c8901-d068-4d22-8ce9-7379644b4f17", "Topology RA")
    _check_found(svedala, "176d262c-701c-4ced-99b2-a155c136e787", "Topology Action")
    _check_found(svedala, "598ab84e-a575-40ad-bf66-c1ab41c65093", "RA dependency 1")
    _check_found(svedala, "13c29cc3-3d99-4c5b-abac-085f0d319eab", "RA dependency 2")
    _check_found(espheim, "d856a2a2-3de4-4a7b-aea4-d363c13d9014", "Espheim RA")
    _check_found(espheim, "4d3757fd-b40a-4d7b-be47-6553935234ff", "Espheim TopologyAction")
    _check_found(espheim, "f5205bd4-637a-4eb7-b0d8-e03638bc570b", "Espheim GridStateAlterationSchedule")

    _check_found(svedala, "96f93b71-420f-456f-932e-9ac3f724b683", "RAS refusal response")
    _check_found(svedala, "f7231aa5-d497-41f3-a5d5-9d4af74444f0", "RAS dependency")
    _check_found(svedala, "51361821-0a40-4e5a-a49d-29c266ea2ecc", "New RAS")
    _check_found(svedala, "7e422768-207d-455f-976e-0b1cb2338509", "Post-RAO topology RA 1")
    _check_found(svedala, "fa3e3533-345a-4ef1-a46d-3ab6d251924a", "Post-RAO topology RA 2")
    _check_found(svedala, "6a9b5221-bb3f-421b-89c1-886b100aa68a", "RA group")
    _check_found(svedala, "1c1e39cf-15a1-4874-9739-d9e6dc90ee11", "EventSchedule 1")
    _check_found(svedala, "023512a8-150d-4300-8159-807275eafd48", "EventSchedule 2")
    _check_found(svedala, "279bfb00-1b2a-4592-af3a-dba9403d1abd", "RAS 1")
    _check_found(svedala, "87e90c47-43d8-4e5c-b2ad-5c67d3a74842", "RAS 2")

    _check_found(belgovia, "30f6377d-5e35-4dd0-a53d-c1992043855e", "Countertrade RA")
    _check_found(belgovia, "27940387-6935-47b6-ab25-8742bac2a266", "PowerSchedule")
    _check_found(belgovia, "ae6a5ddd-fe7e-40b2-bcb6-cbd2882434e7", "PowerBidSchedule")
    _check_found(belgovia, "fa73cfee-ff54-43cd-816b-51394cd76f0f", "Redispatch RA variant 1")
    _check_found(belgovia, "9d72d12a-f135-437a-83fa-ef3e5b23f41f", "Redispatch RA variant 2")
    _check_found(belgovia, "7ab20445-576c-4162-aad5-d097d894a8e0", "PowerShiftKeyDistribution")
    _check_found(belgovia, "3b5748de-39f2-45d7-9a66-65819c667e91", "PowerShiftKeySchedule")
    return "remedial action IDs from markdown are present"


def remedial_uc1(loader: RelicapCgmesLoader) -> str:
    svedala = loader.load_case("Svedala")
    _check_found(svedala, "6d2c8901-d068-4d22-8ce9-7379644b4f17", "Topology RA")
    _check_found(svedala, "176d262c-701c-4ced-99b2-a155c136e787", "Topology Action")
    return "topology remedial action with one topology action exists"


def remedial_uc2(loader: RelicapCgmesLoader) -> str:
    svedala = loader.load_case("Svedala")
    _check_found(svedala, "598ab84e-a575-40ad-bf66-c1ab41c65093", "RA dependency 1")
    _check_found(svedala, "13c29cc3-3d99-4c5b-abac-085f0d319eab", "RA dependency 2")
    return "dependent topology remedial actions exist"


def remedial_uc3(loader: RelicapCgmesLoader) -> str:
    espheim = loader.load_case("Espheim")
    _check_found(espheim, "d856a2a2-3de4-4a7b-aea4-d363c13d9014", "Espheim RA")
    _check_found(espheim, "4d3757fd-b40a-4d7b-be47-6553935234ff", "Espheim TopologyAction")
    _check_found(espheim, "f5205bd4-637a-4eb7-b0d8-e03638bc570b", "Espheim GridStateAlterationSchedule")
    return "pre-RAO modification objects exist"


def remedial_uc4(loader: RelicapCgmesLoader) -> str:
    svedala = loader.load_case("Svedala")
    _check_found(svedala, "96f93b71-420f-456f-932e-9ac3f724b683", "RAS refusal response")
    _check_found(svedala, "f7231aa5-d497-41f3-a5d5-9d4af74444f0", "RAS dependency")
    _check_found(svedala, "51361821-0a40-4e5a-a49d-29c266ea2ecc", "New RAS")
    return "post-RAO proposal objects exist"


def remedial_uc5(loader: RelicapCgmesLoader) -> str:
    svedala = loader.load_case("Svedala")
    _check_found(svedala, "7e422768-207d-455f-976e-0b1cb2338509", "Post-RAO topology RA 1")
    _check_found(svedala, "fa3e3533-345a-4ef1-a46d-3ab6d251924a", "Post-RAO topology RA 2")
    _check_found(svedala, "6a9b5221-bb3f-421b-89c1-886b100aa68a", "RA group")
    _check_found(svedala, "1c1e39cf-15a1-4874-9739-d9e6dc90ee11", "EventSchedule 1")
    _check_found(svedala, "023512a8-150d-4300-8159-807275eafd48", "EventSchedule 2")
    _check_found(svedala, "279bfb00-1b2a-4592-af3a-dba9403d1abd", "RAS 1")
    _check_found(svedala, "87e90c47-43d8-4e5c-b2ad-5c67d3a74842", "RAS 2")
    return "post-RAO activation objects exist"


def remedial_uc6(loader: RelicapCgmesLoader) -> str:
    belgovia = loader.load_case("Belgovia")
    _check_found(belgovia, "30f6377d-5e35-4dd0-a53d-c1992043855e", "Countertrade RA")
    _check_found(belgovia, "27940387-6935-47b6-ab25-8742bac2a266", "PowerSchedule")
    _check_found(belgovia, "ae6a5ddd-fe7e-40b2-bcb6-cbd2882434e7", "PowerBidSchedule")
    return "countertrade remedial action objects exist"


def remedial_uc7(loader: RelicapCgmesLoader) -> str:
    belgovia = loader.load_case("Belgovia")
    _check_found(belgovia, "fa73cfee-ff54-43cd-816b-51394cd76f0f", "Redispatch RA variant 1")
    _check_found(belgovia, "9d72d12a-f135-437a-83fa-ef3e5b23f41f", "Redispatch RA variant 2")
    _check_found(belgovia, "7ab20445-576c-4162-aad5-d097d894a8e0", "PowerShiftKeyDistribution")
    _check_found(belgovia, "3b5748de-39f2-45d7-9a66-65819c667e91", "PowerShiftKeySchedule")
    return "redispatch remedial action objects exist"


def no_validator(_: RelicapCgmesLoader) -> str:
    return "SKIP: no specific checks provided by the test specification"


CO_UC1_ROWS: list[tuple[str, list[str], list[str]]] = list([
    ("Loss of TieLine between Belgovia and Galia", ["d9622e7f-5bf0-4e7e-b766-b8596c6fe4ae"], ["7e31c67d-67ba-4592-8ac1-9e806d697c8e"]),
    ("Loss of TieLine between Belgovia and Svedala", ["ed0c5d75-4a54-43c8-b782-b20d7431630b"], ["e9eab3fe-c328-4f78-9bc1-77adb59f6ba7"]),
    ("Loss of TieLine between Espheim and Svedala", ["ed0c5d75-4a54-43c8-b782-b20d7431630b"], ["e9eab3fe-c328-4f78-9bc1-77adb59f6ba7"]),
    ("Loss of power transformer in Svedala", ["f1c13f90-6d89-4a37-a51c-94742ad2dd72"], ["e05bbe20-9d4a-40da-9777-8424d216785d"]),
    ("Loss of LinearShuntCompensator", ["0489d903-c766-11e1-8775-005056c00008"], ["62eac668-82a1-4739-8cfc-de929b78ef7e"]),
    ("Loss of NonlinearShuntCompensator", ["8464a151-ec39-4e7a-8321-06c41e63958c"], ["ab92defa-ef8e-4d13-a242-5b1a9fe956f6"]),
    ("Loss of HVDC converter DC-3P-Convert-1", ["038ce404-30dc-4289-b9db-7076cb870b8e"], ["038ce404-30dc-4289-b9db-7076cb870b8e"]),
    ("Loss of HVDC line", ["be09fc02-de3f-49e4-aa84-94803bcc5d76"], ["504b48fb-de1f-4f7e-928f-8585daaf7b72"]),
    ("Loss of synchronous machine", ["550ebe0d-f2b2-48c1-991f-cebea43a21aa"], ["37997e71-cb7d-4a8c-baa6-2a1594956da9"]),
    ("Loss of demand facility", ["cb459405-cc14-4215-a45c-416789205904"], ["65582e87-5035-4465-8dd9-cb655224b29f"]),
    ("N-2 loss of two tie-lines", ["04566cf8-c766-11e1-8775-005056c00008", "0475dbd8-c766-11e1-8775-005056c00008"], ["9d17b84c-33b5-4a68-b8b9-ed5b31038d40", "13334fdf-9cc2-4341-adb6-1281269040b4"]),
])


class CoUc1RowValidator:
    __slots__ = ("_eq_ids", "_co_ids")

    def __init__(self, eq_ids: list[str], co_ids: list[str]) -> None:
        self._eq_ids: list[str] = eq_ids
        self._co_ids: list[str] = co_ids

    def __call__(self, loader: RelicapCgmesLoader) -> str:
        return run_co_uc1_row_check(loader, self._eq_ids, self._co_ids)


def _collect_mrid_strings(model: CgmesCircuit) -> set[str]:
    mrids: set[str] = set()
    for list_name, object_list in model.cgmes_assets.__dict__.items():
        if list_name.endswith("_list") and isinstance(object_list, list):
            for obj in object_list:
                rdfid = getattr(obj, "rdfid", None)
                if isinstance(rdfid, str):
                    mrids.add(rdfid)
                else:
                    pass
                m_rid = getattr(obj, "mRID", None)
                if isinstance(m_rid, str):
                    mrids.add(m_rid)
                else:
                    pass
        else:
            pass
    return mrids


def _check_co_profile_export_contains_ids(model: CgmesCircuit, ids_to_check: list[str]) -> tuple[bool, str]:
    model_xml = model.get_model_xml(profiles=[CgmesProfileType.CO])
    co_xml = model_xml.get(CgmesProfileType.CO, None)
    if isinstance(co_xml, str):
        pass
    else:
        return False, "CO profile XML export not available"

    missing_ids: list[str] = list()
    for item_id in ids_to_check:
        if item_id in co_xml:
            pass
        else:
            missing_ids.append(item_id)

    if len(missing_ids) == 0:
        return True, "CO profile export contains referenced CO IDs"
    else:
        return False, "CO profile export missing IDs: " + ", ".join(missing_ids)


def _check_co_execution_stability(loader: RelicapCgmesLoader) -> tuple[bool, str]:
    if loader._co_exec_check_done:
        return loader._co_exec_check_ok, loader._co_exec_check_message
    else:
        pass

    files = loader.get_existing_files("Belgovia")
    if len(files) == 0:
        loader._co_exec_check_done = True
        loader._co_exec_check_ok = False
        loader._co_exec_check_message = "Belgovia case files not found"
        return loader._co_exec_check_ok, loader._co_exec_check_message
    else:
        pass

    grid, _ = open_cgmes(files, version=CGMESVersions.v3_0_0)
    branches = grid.get_branches(add_vsc=True, add_hvdc=True, add_switch=True)
    base_branch_state: dict[str, bool] = dict()
    for branch in branches:
        base_branch_state[branch.idtag] = bool(branch.active)

    base_contingency_count = len(grid.contingencies)
    gce.contingency_analysis(grid)
    post_contingency_count = len(grid.contingencies)

    same_branch_state = True
    for branch in branches:
        if base_branch_state.get(branch.idtag, False) == bool(branch.active):
            pass
        else:
            same_branch_state = False

    same_contingency_count = (base_contingency_count == post_contingency_count)
    loader._co_exec_check_done = True
    loader._co_exec_check_ok = (same_branch_state and same_contingency_count)
    if loader._co_exec_check_ok:
        loader._co_exec_check_message = "contingency execution preserved base network state and contingency count"
    else:
        loader._co_exec_check_message = "contingency execution altered base network state or contingency count"
    return loader._co_exec_check_ok, loader._co_exec_check_message


def run_co_uc1_row_check(loader: RelicapCgmesLoader, eq_ids: list[str], co_ids: list[str]) -> str:
    model = loader.load_case("Combination 3 (Belgovia + Svedala +Galia + Espheim + Britheim )")
    all_mrids = _collect_mrid_strings(model)

    missing_eq: list[str] = list()
    for eq_id in eq_ids:
        if eq_id in all_mrids:
            pass
        else:
            missing_eq.append(eq_id)

    missing_co: list[str] = list()
    for co_id in co_ids:
        if co_id in all_mrids:
            pass
        else:
            missing_co.append(co_id)

    if len(missing_eq) == 0 and len(missing_co) == 0:
        pass
    else:
        raise AssertionError(
            "resolution check failed; missing EQ IDs: "
            + ", ".join(missing_eq)
            + " ; missing CO IDs: "
            + ", ".join(missing_co)
        )

    stable_ok, stable_msg = _check_co_execution_stability(loader)
    if stable_ok:
        pass
    else:
        raise AssertionError("execution stability check failed; " + stable_msg)

    export_ok, export_msg = _check_co_profile_export_contains_ids(model, co_ids)
    if export_ok:
        pass
    else:
        raise AssertionError("CO export/content check failed; " + export_msg)

    return "resolved+executed+exported checks passed for row"

USE_CASE_CATALOG: list[tuple[str, str, str, Callable[[RelicapCgmesLoader], str]]] = list([
    ("PF_UC1", "Power Flow Base Validation", "Contingencies_use_cases/Contingencies_use_cases.md", chapter_contingencies),
    ("BDS_UC1", "Boundary Dataset Structure", "Contingencies_use_cases/Contingencies_use_cases.md", no_validator),
    ("CD_UC1", "Common Data Validation", "Contingencies_use_cases/Contingencies_use_cases.md", no_validator),
    ("RD_UC1", "Regional Dataset Validation", "Contingencies_use_cases/Contingencies_use_cases.md", no_validator),
    ("CO_UC1", "Contingencies use cases", "Contingencies_use_cases/Contingencies_use_cases.md", chapter_contingencies),
    ("ER_UC1", "Equipment Reliability Variant 1", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", no_validator),
    ("ER_UC2", "Equipment Reliability Variant 2", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", no_validator),
    ("RA_UC1", "Topology RA with one action", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", remedial_uc1),
    ("RA_UC2", "Dependent topology RAs", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", remedial_uc2),
    ("RA_UC3", "Pre-RAO topology RA modification", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", remedial_uc3),
    ("RA_UC4", "Post-RAO topology RA proposal", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", remedial_uc4),
    ("RA_UC5", "Post-RAO topology RA activation", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", remedial_uc5),
    ("RA_UC6", "Countertrade RA", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", remedial_uc6),
    ("RA_UC7", "Redispatch RA", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", remedial_uc7),
    ("RAS_UC8", "Remedial Action Schedule handling", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", remedial_uc4),
    ("RA_UC9 Shared RA on Boundary", "Shared RA on Boundary", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", no_validator),
    ("AS_UC1", "Availability Schedule", "Availability _Schedule_use_case/Availability _Schedule_use_case.md", chapter_availability_schedule),
    ("AE_UC1", "Secured Assessed Element", "Assessed_Element_use_cases/Assessed_Element_use_cases.md", chapter_assessed_elements),
    ("AE_UC2", "Scanned Assessed Element", "Assessed_Element_use_cases/Assessed_Element_use_cases.md", chapter_assessed_elements),
    ("AE_UC3", "Disable Assessed Element", "Assessed_Element_use_cases/Assessed_Element_use_cases.md", chapter_assessed_elements),
    ("AE_UC4", "Exclude Assessed Element", "Assessed_Element_use_cases/Assessed_Element_use_cases.md", chapter_assessed_elements),
    ("AE_UC5", "Assessed Element with Contingency", "Assessed_Element_use_cases/Assessed_Element_use_cases.md", chapter_assessed_elements),
    ("AE_UC6", "Assessed Element with Remedial Action", "Assessed_Element_use_cases/Assessed_Element_use_cases.md", chapter_assessed_elements),
    ("OR_UC1", "Operational Rules Validation", "Remedial_Action_use_cases/Remedial_Action_use_cases.md", no_validator),
    ("SAR_UC1", "Special Automation / SIPS Rules", "Implementing_SIPS_Gate_Logic_with_Cardinality_Constraints/Implementing_SIPS_Gate_Logic_with_Cardinality_Constraints.md", chapter_sips_gate_logic),
    ("PF_UC1", "Correction of generation production due to a power flow limit violation", "Correction_of_generation_production_due_to_a_power_flow_limit_violation/Correction_of_generation_production_due_to_a_power_flow_limit_violation.md", chapter_generation_correction),
    ("SAR_UC1", "Modelling complex SIPS logic", "Modelling_complex_SIPS_logic/Modelling_complex_SIPS_logic.md", chapter_sips_complex),
    ("SAR_UC1", "Modelling Current Flow Conditions Against PATL or TATL", "Modelling_Current_Flow_Conditions_Against_PATL_or_TATL/Modelling_Current_Flow_Conditions_Against_PATL_or_TATL.md", chapter_sips_current_flow),
    ("SAR_UC1", "Modelling Element Disconnection by Monitoring the Power Flow", "Modelling_Element_Disconnection_by_Monitoring_the_Power_Flow/Modelling_Element_Disconnection_by_Monitoring_the_Power_Flow.md", chapter_sips_last_line),
    ("SAR_UC1", "Modelling SIPS Actions Based on Generation", "Modelling_SIPS_Actions_Based_on_Generation/Modelling_SIPS_Actions_Based_on_Generation.md", chapter_sips_generation),
    ("SAR_UC1", "Modelling Voltage Dependent Tripping Conditions", "Modelling_Voltage_Dependent_Tripping_Conditions/Modelling_Voltage_Dependent_Tripping_Conditions.md", chapter_sips_voltage),
])

for contingency_name, eq_ids, co_ids in CO_UC1_ROWS:
    display_name = "Contingency row: " + contingency_name
    function_ref = CoUc1RowValidator(eq_ids=eq_ids, co_ids=co_ids)
    USE_CASE_CATALOG.append(
        (
            "CO_UC1",
            display_name,
            "Contingencies_use_cases/Contingencies_use_cases.md",
            function_ref,
        )
    )


def run_chapter(
    use_case_id: str,
    name: str,
    source_md: str,
    fn: Callable[[RelicapCgmesLoader], str],
    loader: RelicapCgmesLoader,
) -> ChapterResult:
    try:
        msg = fn(loader)
        if msg.startswith("SKIP:"):
            return ChapterResult(use_case_id=use_case_id, name=name, source_md=source_md, ok=True, message=msg, status="SKIP")
        return ChapterResult(use_case_id=use_case_id, name=name, source_md=source_md, ok=True, message=f"OK: {msg}", status="PASS")
    except Exception as exc:
        return ChapterResult(use_case_id=use_case_id, name=name, source_md=source_md, ok=False, message=f"FAIL: {exc}", status="FAIL")


def write_report(report_path: str, results: list[ChapterResult], loader: RelicapCgmesLoader) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    skipped = sum(1 for r in results if r.status == "SKIP")
    failed = sum(1 for r in results if r.status == "FAIL")

    case_names = sorted(set(["Belgovia", "Espheim", "Svedala"]))
    case_lines = []
    for case_name in case_names:
        existing, missing = loader.case_file_stats(case_name)
        case_lines.append(f"- `{case_name}`: existing files `{existing}`, missing files `{missing}`")

    def _read_group_title_from_md(rel_md_path: str) -> str:
        abs_md_path = os.path.join(USE_CASES_ROOT, rel_md_path)
        if os.path.isfile(abs_md_path):
            with open(abs_md_path, "r", encoding="utf-8") as file_obj:
                lines = file_obj.read().splitlines()
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
                else:
                    pass
            return os.path.splitext(os.path.basename(rel_md_path))[0]
        else:
            return os.path.splitext(os.path.basename(rel_md_path))[0]

    source_order: list[str] = list()
    source_groups: dict[str, list[ChapterResult]] = dict()
    for result in results:
        grouped = source_groups.get(result.source_md, None)
        if grouped is None:
            source_groups[result.source_md] = [result]
            source_order.append(result.source_md)
        else:
            grouped.append(result)

    lines = [
        f"# Relicap Test Book Report for VeraGrid {__VeraGridEngine_VERSION__}",
        "",
        f"- Generated: `{now}`",
        f"- Script: `{os.path.abspath(__file__)}`",
        f"- Relicap base folder: `{FOLDER}`",
        "",
        "## Summary",
        "",
        f"- Total chapters: `{total}`",
        f"- PASS: `{passed}`",
        f"- SKIP: `{skipped}`",
        f"- FAIL: `{failed}`",
        "",
        "## Dataset Coverage (loaded cases)",
        "",
        *case_lines,
        "",
    ]

    for source_md in source_order:
        grouped_results = source_groups[source_md]
        group_title = _read_group_title_from_md(source_md)
        lines.append("")
        lines.append(f"## {group_title}")
        lines.append("")
        lines.append(f"*file*: `{source_md}`")
        lines.append("")
        lines.append("| # | Use Case ID | Use Case | Status | Detail |")
        lines.append("|---:|---|---|---|---|")
        for idx, result in enumerate(grouped_results, start=1):
            detail = result.message.replace("|", "\\|")
            lines.append(f"| {idx} | {result.use_case_id} | {result.name} | {result.status} | {detail} |")

    lines.append("")
    lines.append("## Failure Details")
    lines.append("")
    failures = [r for r in results if r.status == "FAIL"]
    if failures:
        for idx, fail in enumerate(failures, start=1):
            lines.append(f"{idx}. {fail.name}: {fail.message}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `SKIP` means the chapter was recognized but cannot be fully executed with currently available local datasets.")
    lines.append("- Chapters mapped to SIPS use cases currently return `SKIP` until the referenced SIPS datasets are available in the local instance.")

    report_dir = os.path.dirname(report_path)
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    loader = RelicapCgmesLoader(SUBFOLDERS)
    results: list[ChapterResult] = []

    for use_case_id, use_case_name, source_md, fn in USE_CASE_CATALOG:
        result = run_chapter(use_case_id, use_case_name, source_md, fn, loader)
        results.append(result)
        print(f"[{result.status}] {result.use_case_id} :: {result.name}")
        print(f"  Source: {result.source_md}")
        print(f"  {result.message}")

    print("")
    print("Results Table")
    header = f"{'#':>2}  {'Status':<6}  {'Use Case ID':<28}  {'Use Case':<44}  {'Source MD':<68}  Detail"
    print(header)
    print("-" * len(header))
    for idx, result in enumerate(results, start=1):
        print(
            f"{idx:>2}  {result.status:<6}  {result.use_case_id[:28]:<28}  {result.name[:44]:<44}  {result.source_md[:68]:<68}  {result.message}"
        )

    failures = [r for r in results if not r.ok]
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relicap_test_report.md")
    write_report(report_path, results, loader)
    print("")
    print(f"Total chapters: {len(results)}")
    print(f"Failures: {len(failures)}")
    print(f"Report: {report_path}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

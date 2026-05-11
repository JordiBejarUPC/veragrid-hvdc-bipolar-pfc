# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, Tuple, Type, TypeAlias

from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.acdc_converter_action import ACDCConverterAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.activity import Activity
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.agent import Agent
from VeraGridEngine.IO.cim.cgmes.ncp.devices.market.area_dispatchable_unit import AreaDispatchableUnit
from VeraGridEngine.IO.cim.cgmes.ncp.devices.assessment.assessed_element import AssessedElement
from VeraGridEngine.IO.cim.cgmes.ncp.devices.assessment.assessed_element_schedule import AssessedElementSchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.assessment.assessed_element_time_point import AssessedElementTimePoint
from VeraGridEngine.IO.cim.cgmes.ncp.devices.assessment.assessed_element_with_contingency import AssessedElementWithContingency
from VeraGridEngine.IO.cim.cgmes.ncp.devices.assessment.assessed_element_with_remedial_action import AssessedElementWithRemedialAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.assessment import Assessment
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.availability_container import AvailabilityContainer
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.availability_equipment import AvailabilityEquipment
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.availability_power_system_function import AvailabilityPowerSystemFunction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.availability_remedial_action import AvailabilityRemedialAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.availability_schedule import AvailabilitySchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.results.base_case_power_flow_result import BaseCasePowerFlowResult
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.base_irregular_time_series import BaseIrregularTimeSeries
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.base_time_series import BaseTimeSeries
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.bidding_zone import BiddingZone
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.bidding_zone_border import BiddingZoneBorder
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.boundary_frame import BoundaryFrame
from VeraGridEngine.IO.cim.cgmes.ncp.devices.assessment.calculation_based_impact_assessment_matrix import CalculationBasedImpactAssessmentMatrix
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.capacity_calculation_region import CapacityCalculationRegion
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.circuit import Circuit
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.circuit_share import CircuitShare
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.collection import Collection
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.concept_scheme import ConceptScheme
from VeraGridEngine.IO.cim.cgmes.ncp.devices.contingency.contingency import Contingency
from VeraGridEngine.IO.cim.cgmes.ncp.devices.contingency.contingency_element import ContingencyElement
from VeraGridEngine.IO.cim.cgmes.ncp.devices.contingency.contingency_equipment import ContingencyEquipment
from VeraGridEngine.IO.cim.cgmes.ncp.devices.contingency.contingency_power_flow_result import ContingencyPowerFlowResult
from VeraGridEngine.IO.cim.cgmes.ncp.devices.contingency.contingency_with_remedial_action import ContingencyWithRemedialAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.coordinated_capacity_calculator import CoordinatedCapacityCalculator
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.countertrade_remedial_action import CountertradeRemedialAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.countertrade_schedule_action import CountertradeScheduleAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.assessment.cross_border_relevance import CrossBorderRelevance
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.current_limit_schedule import CurrentLimitSchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.current_limit_time_point import CurrentLimitTimePoint
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.dataset import Dataset
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.entity import Entity
from VeraGridEngine.IO.cim.cgmes.ncp.devices.market.equivalent_generating_unit import EquivalentGeneratingUnit
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.equivalent_injection_action import EquivalentInjectionAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.event_schedule import EventSchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.event_time_point import EventTimePoint
from VeraGridEngine.IO.cim.cgmes.ncp.devices.contingency.exceptional_contingency import ExceptionalContingency
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.frame import Frame
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.function_input_variable import FunctionInputVariable
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.gate import Gate
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.gate_input_pin import GateInputPin
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.generic_value_schedule import GenericValueSchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.generic_value_time_point import GenericValueTimePoint
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.geometry import Geometry
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.grid_state_alteration import GridStateAlteration
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.grid_state_alteration_collection import GridStateAlterationCollection
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.grid_state_alteration_remedial_action import GridStateAlterationRemedialAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.grid_state_alteration_schedule import GridStateAlterationSchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.grid_state_alteration_time_point import GridStateAlterationTimePoint
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.grid_state_intensity_schedule import GridStateIntensitySchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.assessment.impact_assessment_matrix import ImpactAssessmentMatrix
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.infeed_limit import InfeedLimit
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.infeed_terminal import InfeedTerminal
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.license_document import LicenseDocument
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.line_circuit import LineCircuit
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.load_action import LoadAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.load_frequency_control_area import LoadFrequencyControlArea
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.load_frequency_control_block import LoadFrequencyControlBlock
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.model import Model
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.modeling import Modeling
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.name import Name
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.name_type import NameType
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.naming_authority import NamingAuthority
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.object_type import ObjectType
from VeraGridEngine.IO.cim.cgmes.ncp.devices.contingency.ordinary_contingency import OrdinaryContingency
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.ordinary_power_transfer_corridor import OrdinaryPowerTransferCorridor
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.organisation import Organisation
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.organisation_role import OrganisationRole
from VeraGridEngine.IO.cim.cgmes.ncp.devices.contingency.out_of_range_contingency import OutOfRangeContingency
from VeraGridEngine.IO.cim.cgmes.ncp.devices.assessment.outcome_value import OutcomeValue
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.participation_factor_time_point import ParticipationFactorTimePoint
from VeraGridEngine.IO.cim.cgmes.ncp.devices.contingency.pin_contingency import PinContingency
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.pin_equipment_tripping import PinEquipmentTripping
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.pin_gate import PinGate
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.pin_operational_limit import PinOperationalLimit
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.pin_terminal import PinTerminal
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.power_bid_dependency import PowerBidDependency
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.power_bid_schedule import PowerBidSchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.power_bid_schedule_time_point import PowerBidScheduleTimePoint
from VeraGridEngine.IO.cim.cgmes.ncp.devices.results.power_flow_result import PowerFlowResult
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.power_remedial_action import PowerRemedialAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.power_schedule import PowerSchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.power_schedule_action import PowerScheduleAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.power_shift_key_distribution import PowerShiftKeyDistribution
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.power_shift_key_schedule import PowerShiftKeySchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.power_shift_key_strategy import PowerShiftKeyStrategy
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.power_system_organisation_role import PowerSystemOrganisationRole
from VeraGridEngine.IO.cim.cgmes.ncp.devices.schedules.power_time_point import PowerTimePoint
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.power_transfer_corridor import PowerTransferCorridor
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.power_transformer_circuit import PowerTransformerCircuit
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.quantity_value import QuantityValue
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.range_constraint import RangeConstraint
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.redispatch_remedial_action import RedispatchRemedialAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.region import Region
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.regulating_control_action import RegulatingControlAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.remedial_action import RemedialAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.remedial_action_dependency import RemedialActionDependency
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.remedial_action_group import RemedialActionGroup
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.remedial_action_outcome_value import RemedialActionOutcomeValue
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.remedial_action_schedule import RemedialActionSchedule
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.remedial_action_schedule_dependency import RemedialActionScheduleDependency
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.remedial_action_schedule_outcome_value import RemedialActionScheduleOutcomeValue
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.remedial_action_schedule_response import RemedialActionScheduleResponse
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.remedial_action_scheme import RemedialActionScheme
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.rights_statement import RightsStatement
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.rotating_machine_action import RotatingMachineAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.scheduling_area import SchedulingArea
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.scheme_remedial_action import SchemeRemedialAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.security_coordinator import SecurityCoordinator
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.semantic_asset import SemanticAsset
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.set_point_action import SetPointAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.core.shunt_compensator_modification import ShuntCompensatorModification
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.stage import Stage
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.stage_trigger import StageTrigger
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.static_property_range import StaticPropertyRange
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.static_var_compensator_action import StaticVarCompensatorAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.supported_profile_collection import SupportedProfileCollection
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.synchronous_area import SynchronousArea
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.system_operation_coordinator import SystemOperationCoordinator
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.system_operator import SystemOperator
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.tap_position_action import TapPositionAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.geography.tie_corridor import TieCorridor
from VeraGridEngine.IO.cim.cgmes.ncp.devices.actions.topology_action import TopologyAction
from VeraGridEngine.IO.cim.cgmes.ncp.devices.organisation.transmission_system_operator import TransmissionSystemOperator
from VeraGridEngine.IO.cim.cgmes.ncp.devices.remedial.trigger_condition import TriggerCondition
from VeraGridEngine.IO.cim.cgmes.ncp.devices.metadata.verification import Verification
from VeraGridEngine.IO.cim.cgmes.ncp.devices.operations.voltage_angle_limit import VoltageAngleLimit


NCP_ASSETS: TypeAlias = (
    ACDCConverterAction |
    Activity |
    Agent |
    AreaDispatchableUnit |
    AssessedElement |
    AssessedElementSchedule |
    AssessedElementTimePoint |
    AssessedElementWithContingency |
    AssessedElementWithRemedialAction |
    Assessment |
    AvailabilityContainer |
    AvailabilityEquipment |
    AvailabilityPowerSystemFunction |
    AvailabilityRemedialAction |
    AvailabilitySchedule |
    BaseCasePowerFlowResult |
    BaseIrregularTimeSeries |
    BaseTimeSeries |
    BiddingZone |
    BiddingZoneBorder |
    BoundaryFrame |
    CalculationBasedImpactAssessmentMatrix |
    CapacityCalculationRegion |
    Circuit |
    CircuitShare |
    Collection |
    ConceptScheme |
    Contingency |
    ContingencyElement |
    ContingencyEquipment |
    ContingencyPowerFlowResult |
    ContingencyWithRemedialAction |
    CoordinatedCapacityCalculator |
    CountertradeRemedialAction |
    CountertradeScheduleAction |
    CrossBorderRelevance |
    CurrentLimitSchedule |
    CurrentLimitTimePoint |
    Dataset |
    Entity |
    EquivalentGeneratingUnit |
    EquivalentInjectionAction |
    EventSchedule |
    EventTimePoint |
    ExceptionalContingency |
    Frame |
    FunctionInputVariable |
    Gate |
    GateInputPin |
    GenericValueSchedule |
    GenericValueTimePoint |
    Geometry |
    GridStateAlteration |
    GridStateAlterationCollection |
    GridStateAlterationRemedialAction |
    GridStateAlterationSchedule |
    GridStateAlterationTimePoint |
    GridStateIntensitySchedule |
    ImpactAssessmentMatrix |
    InfeedLimit |
    InfeedTerminal |
    LicenseDocument |
    LineCircuit |
    LoadAction |
    LoadFrequencyControlArea |
    LoadFrequencyControlBlock |
    Model |
    Modeling |
    Name |
    NameType |
    NamingAuthority |
    ObjectType |
    OrdinaryContingency |
    OrdinaryPowerTransferCorridor |
    Organisation |
    OrganisationRole |
    OutOfRangeContingency |
    OutcomeValue |
    ParticipationFactorTimePoint |
    PinContingency |
    PinEquipmentTripping |
    PinGate |
    PinOperationalLimit |
    PinTerminal |
    PowerBidDependency |
    PowerBidSchedule |
    PowerBidScheduleTimePoint |
    PowerFlowResult |
    PowerRemedialAction |
    PowerSchedule |
    PowerScheduleAction |
    PowerShiftKeyDistribution |
    PowerShiftKeySchedule |
    PowerShiftKeyStrategy |
    PowerSystemOrganisationRole |
    PowerTimePoint |
    PowerTransferCorridor |
    PowerTransformerCircuit |
    QuantityValue |
    RangeConstraint |
    RedispatchRemedialAction |
    Region |
    RegulatingControlAction |
    RemedialAction |
    RemedialActionDependency |
    RemedialActionGroup |
    RemedialActionOutcomeValue |
    RemedialActionSchedule |
    RemedialActionScheduleDependency |
    RemedialActionScheduleOutcomeValue |
    RemedialActionScheduleResponse |
    RemedialActionScheme |
    RightsStatement |
    RotatingMachineAction |
    SchedulingArea |
    SchemeRemedialAction |
    SecurityCoordinator |
    SemanticAsset |
    SetPointAction |
    ShuntCompensatorModification |
    Stage |
    StageTrigger |
    StaticPropertyRange |
    StaticVarCompensatorAction |
    SupportedProfileCollection |
    SynchronousArea |
    SystemOperationCoordinator |
    SystemOperator |
    TapPositionAction |
    TieCorridor |
    TopologyAction |
    TransmissionSystemOperator |
    TriggerCondition |
    Verification |
    VoltageAngleLimit 
)


class NcpAssets:
    """Container exposing NCP class and inverse-association dictionaries."""

    def __init__(self):
        """Initialize NCP assets."""
        self.class_dict: Dict[str, Type] = {
            'ACDCConverterAction': ACDCConverterAction,
            'Activity': Activity,
            'Agent': Agent,
            'AreaDispatchableUnit': AreaDispatchableUnit,
            'AssessedElement': AssessedElement,
            'AssessedElementSchedule': AssessedElementSchedule,
            'AssessedElementTimePoint': AssessedElementTimePoint,
            'AssessedElementWithContingency': AssessedElementWithContingency,
            'AssessedElementWithRemedialAction': AssessedElementWithRemedialAction,
            'Assessment': Assessment,
            'AvailabilityContainer': AvailabilityContainer,
            'AvailabilityEquipment': AvailabilityEquipment,
            'AvailabilityPowerSystemFunction': AvailabilityPowerSystemFunction,
            'AvailabilityRemedialAction': AvailabilityRemedialAction,
            'AvailabilitySchedule': AvailabilitySchedule,
            'BaseCasePowerFlowResult': BaseCasePowerFlowResult,
            'BaseIrregularTimeSeries': BaseIrregularTimeSeries,
            'BaseTimeSeries': BaseTimeSeries,
            'BiddingZone': BiddingZone,
            'BiddingZoneBorder': BiddingZoneBorder,
            'BoundaryFrame': BoundaryFrame,
            'CalculationBasedImpactAssessmentMatrix': CalculationBasedImpactAssessmentMatrix,
            'CapacityCalculationRegion': CapacityCalculationRegion,
            'Circuit': Circuit,
            'CircuitShare': CircuitShare,
            'Collection': Collection,
            'ConceptScheme': ConceptScheme,
            'Contingency': Contingency,
            'ContingencyElement': ContingencyElement,
            'ContingencyEquipment': ContingencyEquipment,
            'ContingencyPowerFlowResult': ContingencyPowerFlowResult,
            'ContingencyWithRemedialAction': ContingencyWithRemedialAction,
            'CoordinatedCapacityCalculator': CoordinatedCapacityCalculator,
            'CountertradeRemedialAction': CountertradeRemedialAction,
            'CountertradeScheduleAction': CountertradeScheduleAction,
            'CrossBorderRelevance': CrossBorderRelevance,
            'CurrentLimitSchedule': CurrentLimitSchedule,
            'CurrentLimitTimePoint': CurrentLimitTimePoint,
            'Dataset': Dataset,
            'Entity': Entity,
            'EquivalentGeneratingUnit': EquivalentGeneratingUnit,
            'EquivalentInjectionAction': EquivalentInjectionAction,
            'EventSchedule': EventSchedule,
            'EventTimePoint': EventTimePoint,
            'ExceptionalContingency': ExceptionalContingency,
            'Frame': Frame,
            'FunctionInputVariable': FunctionInputVariable,
            'Gate': Gate,
            'GateInputPin': GateInputPin,
            'GenericValueSchedule': GenericValueSchedule,
            'GenericValueTimePoint': GenericValueTimePoint,
            'Geometry': Geometry,
            'GridStateAlteration': GridStateAlteration,
            'GridStateAlterationCollection': GridStateAlterationCollection,
            'GridStateAlterationRemedialAction': GridStateAlterationRemedialAction,
            'GridStateAlterationSchedule': GridStateAlterationSchedule,
            'GridStateAlterationTimePoint': GridStateAlterationTimePoint,
            'GridStateIntensitySchedule': GridStateIntensitySchedule,
            'ImpactAssessmentMatrix': ImpactAssessmentMatrix,
            'InfeedLimit': InfeedLimit,
            'InfeedTerminal': InfeedTerminal,
            'LicenseDocument': LicenseDocument,
            'LineCircuit': LineCircuit,
            'LoadAction': LoadAction,
            'LoadFrequencyControlArea': LoadFrequencyControlArea,
            'LoadFrequencyControlBlock': LoadFrequencyControlBlock,
            'Model': Model,
            'Modeling': Modeling,
            'Name': Name,
            'NameType': NameType,
            'NamingAuthority': NamingAuthority,
            'ObjectType': ObjectType,
            'OrdinaryContingency': OrdinaryContingency,
            'OrdinaryPowerTransferCorridor': OrdinaryPowerTransferCorridor,
            'Organisation': Organisation,
            'OrganisationRole': OrganisationRole,
            'OutOfRangeContingency': OutOfRangeContingency,
            'OutcomeValue': OutcomeValue,
            'ParticipationFactorTimePoint': ParticipationFactorTimePoint,
            'PinContingency': PinContingency,
            'PinEquipmentTripping': PinEquipmentTripping,
            'PinGate': PinGate,
            'PinOperationalLimit': PinOperationalLimit,
            'PinTerminal': PinTerminal,
            'PowerBidDependency': PowerBidDependency,
            'PowerBidSchedule': PowerBidSchedule,
            'PowerBidScheduleTimePoint': PowerBidScheduleTimePoint,
            'PowerFlowResult': PowerFlowResult,
            'PowerRemedialAction': PowerRemedialAction,
            'PowerSchedule': PowerSchedule,
            'PowerScheduleAction': PowerScheduleAction,
            'PowerShiftKeyDistribution': PowerShiftKeyDistribution,
            'PowerShiftKeySchedule': PowerShiftKeySchedule,
            'PowerShiftKeyStrategy': PowerShiftKeyStrategy,
            'PowerSystemOrganisationRole': PowerSystemOrganisationRole,
            'PowerTimePoint': PowerTimePoint,
            'PowerTransferCorridor': PowerTransferCorridor,
            'PowerTransformerCircuit': PowerTransformerCircuit,
            'QuantityValue': QuantityValue,
            'RangeConstraint': RangeConstraint,
            'RedispatchRemedialAction': RedispatchRemedialAction,
            'Region': Region,
            'RegulatingControlAction': RegulatingControlAction,
            'RemedialAction': RemedialAction,
            'RemedialActionDependency': RemedialActionDependency,
            'RemedialActionGroup': RemedialActionGroup,
            'RemedialActionOutcomeValue': RemedialActionOutcomeValue,
            'RemedialActionSchedule': RemedialActionSchedule,
            'RemedialActionScheduleDependency': RemedialActionScheduleDependency,
            'RemedialActionScheduleOutcomeValue': RemedialActionScheduleOutcomeValue,
            'RemedialActionScheduleResponse': RemedialActionScheduleResponse,
            'RemedialActionScheme': RemedialActionScheme,
            'RightsStatement': RightsStatement,
            'RotatingMachineAction': RotatingMachineAction,
            'SchedulingArea': SchedulingArea,
            'SchemeRemedialAction': SchemeRemedialAction,
            'SecurityCoordinator': SecurityCoordinator,
            'SemanticAsset': SemanticAsset,
            'SetPointAction': SetPointAction,
            'ShuntCompensatorModification': ShuntCompensatorModification,
            'Stage': Stage,
            'StageTrigger': StageTrigger,
            'StaticPropertyRange': StaticPropertyRange,
            'StaticVarCompensatorAction': StaticVarCompensatorAction,
            'SupportedProfileCollection': SupportedProfileCollection,
            'SynchronousArea': SynchronousArea,
            'SystemOperationCoordinator': SystemOperationCoordinator,
            'SystemOperator': SystemOperator,
            'TapPositionAction': TapPositionAction,
            'TieCorridor': TieCorridor,
            'TopologyAction': TopologyAction,
            'TransmissionSystemOperator': TransmissionSystemOperator,
            'TriggerCondition': TriggerCondition,
            'Verification': Verification,
            'VoltageAngleLimit': VoltageAngleLimit,
        }
        self.association_inverse_dict: Dict[Tuple[str, str], str] = dict()
        self.ACDCConverterAction_list = list()
        self.Activity_list = list()
        self.Agent_list = list()
        self.AreaDispatchableUnit_list = list()
        self.AssessedElement_list = list()
        self.AssessedElementSchedule_list = list()
        self.AssessedElementTimePoint_list = list()
        self.AssessedElementWithContingency_list = list()
        self.AssessedElementWithRemedialAction_list = list()
        self.Assessment_list = list()
        self.AvailabilityContainer_list = list()
        self.AvailabilityEquipment_list = list()
        self.AvailabilityPowerSystemFunction_list = list()
        self.AvailabilityRemedialAction_list = list()
        self.AvailabilitySchedule_list = list()
        self.BaseCasePowerFlowResult_list = list()
        self.BaseIrregularTimeSeries_list = list()
        self.BaseTimeSeries_list = list()
        self.BiddingZone_list = list()
        self.BiddingZoneBorder_list = list()
        self.BoundaryFrame_list = list()
        self.CalculationBasedImpactAssessmentMatrix_list = list()
        self.CapacityCalculationRegion_list = list()
        self.Circuit_list = list()
        self.CircuitShare_list = list()
        self.Collection_list = list()
        self.ConceptScheme_list = list()
        self.Contingency_list = list()
        self.ContingencyElement_list = list()
        self.ContingencyEquipment_list = list()
        self.ContingencyPowerFlowResult_list = list()
        self.ContingencyWithRemedialAction_list = list()
        self.CoordinatedCapacityCalculator_list = list()
        self.CountertradeRemedialAction_list = list()
        self.CountertradeScheduleAction_list = list()
        self.CrossBorderRelevance_list = list()
        self.CurrentLimitSchedule_list = list()
        self.CurrentLimitTimePoint_list = list()
        self.Dataset_list = list()
        self.Entity_list = list()
        self.EquivalentGeneratingUnit_list = list()
        self.EquivalentInjectionAction_list = list()
        self.EventSchedule_list = list()
        self.EventTimePoint_list = list()
        self.ExceptionalContingency_list = list()
        self.Frame_list = list()
        self.FunctionInputVariable_list = list()
        self.Gate_list = list()
        self.GateInputPin_list = list()
        self.GenericValueSchedule_list = list()
        self.GenericValueTimePoint_list = list()
        self.Geometry_list = list()
        self.GridStateAlteration_list = list()
        self.GridStateAlterationCollection_list = list()
        self.GridStateAlterationRemedialAction_list = list()
        self.GridStateAlterationSchedule_list = list()
        self.GridStateAlterationTimePoint_list = list()
        self.GridStateIntensitySchedule_list = list()
        self.ImpactAssessmentMatrix_list = list()
        self.InfeedLimit_list = list()
        self.InfeedTerminal_list = list()
        self.LicenseDocument_list = list()
        self.LineCircuit_list = list()
        self.LoadAction_list = list()
        self.LoadFrequencyControlArea_list = list()
        self.LoadFrequencyControlBlock_list = list()
        self.Model_list = list()
        self.Modeling_list = list()
        self.Name_list = list()
        self.NameType_list = list()
        self.NamingAuthority_list = list()
        self.ObjectType_list = list()
        self.OrdinaryContingency_list = list()
        self.OrdinaryPowerTransferCorridor_list = list()
        self.Organisation_list = list()
        self.OrganisationRole_list = list()
        self.OutOfRangeContingency_list = list()
        self.OutcomeValue_list = list()
        self.ParticipationFactorTimePoint_list = list()
        self.PinContingency_list = list()
        self.PinEquipmentTripping_list = list()
        self.PinGate_list = list()
        self.PinOperationalLimit_list = list()
        self.PinTerminal_list = list()
        self.PowerBidDependency_list = list()
        self.PowerBidSchedule_list = list()
        self.PowerBidScheduleTimePoint_list = list()
        self.PowerFlowResult_list = list()
        self.PowerRemedialAction_list = list()
        self.PowerSchedule_list = list()
        self.PowerScheduleAction_list = list()
        self.PowerShiftKeyDistribution_list = list()
        self.PowerShiftKeySchedule_list = list()
        self.PowerShiftKeyStrategy_list = list()
        self.PowerSystemOrganisationRole_list = list()
        self.PowerTimePoint_list = list()
        self.PowerTransferCorridor_list = list()
        self.PowerTransformerCircuit_list = list()
        self.QuantityValue_list = list()
        self.RangeConstraint_list = list()
        self.RedispatchRemedialAction_list = list()
        self.Region_list = list()
        self.RegulatingControlAction_list = list()
        self.RemedialAction_list = list()
        self.RemedialActionDependency_list = list()
        self.RemedialActionGroup_list = list()
        self.RemedialActionOutcomeValue_list = list()
        self.RemedialActionSchedule_list = list()
        self.RemedialActionScheduleDependency_list = list()
        self.RemedialActionScheduleOutcomeValue_list = list()
        self.RemedialActionScheduleResponse_list = list()
        self.RemedialActionScheme_list = list()
        self.RightsStatement_list = list()
        self.RotatingMachineAction_list = list()
        self.SchedulingArea_list = list()
        self.SchemeRemedialAction_list = list()
        self.SecurityCoordinator_list = list()
        self.SemanticAsset_list = list()
        self.SetPointAction_list = list()
        self.ShuntCompensatorModification_list = list()
        self.Stage_list = list()
        self.StageTrigger_list = list()
        self.StaticPropertyRange_list = list()
        self.StaticVarCompensatorAction_list = list()
        self.SupportedProfileCollection_list = list()
        self.SynchronousArea_list = list()
        self.SystemOperationCoordinator_list = list()
        self.SystemOperator_list = list()
        self.TapPositionAction_list = list()
        self.TieCorridor_list = list()
        self.TopologyAction_list = list()
        self.TransmissionSystemOperator_list = list()
        self.TriggerCondition_list = list()
        self.Verification_list = list()
        self.VoltageAngleLimit_list = list()

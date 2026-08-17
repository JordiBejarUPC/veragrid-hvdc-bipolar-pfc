# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import ast
import math
import pprint
import re
from enum import IntEnum
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_discrete_event import (
    DgsDiscreteEventAction,
    DgsDiscreteEventCommand,
    parse_dgs_discrete_event_statement,
)
from VeraGridEngine.IO.dgs.dgs_objects import BlkDef, BlkDiv, BlkFrom, BlkGoto, BlkMul, BlkRef, BlkSlot, BlkSum, BlkSwt, ElmComp, ElmDsl, ElmSvs, DGSElement, StaCubic, StaSwitch
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.procedural_logic import (
    HardSaturationLogic,
    AnalogFlipFlopLogic,
    FixedSampleLogic,
    FlipFlopLogic,
    GradientLimiterLogic,
    MovingAverageLogic,
    ProceduralLogicBase,
    PickupDropoffLogic,
    ResetOnRisingEdgeLogic,
    SampledValueLogic,
    TimeDelayLogic,
    clone_procedural_logic_entries,
)
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.Symbolic.symbolic import (BinOp, CmpOp, Comparison, Const, Expr, Func, Func2, UnOp, Var, abs,
                                                    acos, asin, atan, cos, exp, floor, hard_sat, heaviside, log, max,
                                                    min, sin, sqrt, tan)
from VeraGridEngine.enumerations import DeviceType, SampledValueEvaluationMode, BlockScopeMode
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType
from VeraGridEngine.enumerations import VarPowerFlowReferenceType


STRICT_PROCEDURAL_LOGIC_ONLY: bool = True

DgsParameterValue = float | int | bool | str | complex | None
DgsParameterValues = Dict[str, DgsParameterValue]
SymbolReplacementKey = Var | Const | str
SymbolReplacementValue = Expr | Const
SymbolReplacementMap = Dict[SymbolReplacementKey, SymbolReplacementValue]


class DgsGraphicalConnectorKind(IntEnum):
    """PowerFactory graphical connector category stored in ``BlkSig``.

    The node index is local to one category, so a normal input, a lower-limit
    input and an upper-limit input can all legitimately use node index zero.
    """

    Input = 1
    Output = 2
    LowerLimitInput = 3
    UpperLimitInput = 4


def _build_blkdef_runtime_input_names(blkdef: BlkDef) -> List[str]:
    """Return every executable input pin in deterministic runtime order.

    :param blkdef: PowerFactory block definition.
    :return: Normal, lower-limit and upper-limit input names.
    """
    input_names: List[str] = list()
    input_groups: List[List[str]] = list([
        blkdef.inputs,
        blkdef.lower_limit_inputs,
        blkdef.upper_limit_inputs,
    ])
    input_group: List[str]
    input_name: str
    for input_group in input_groups:
        for input_name in input_group:
            if input_name in input_names:
                pass
            else:
                input_names.append(input_name)
        else:
            pass
    else:
        pass
    return input_names


def _get_blkdef_input_names_for_connector(
        blkdef: BlkDef,
        connector_kind: DgsGraphicalConnectorKind,
) -> List[str]:
    """Return the input-name vector addressed by one connector category.

    :param blkdef: PowerFactory block definition.
    :param connector_kind: Exact BlkSig connector category.
    :return: Category-local ordered input names.
    """
    if connector_kind == DgsGraphicalConnectorKind.Input:
        input_names: List[str] = list(blkdef.inputs)
    elif connector_kind == DgsGraphicalConnectorKind.LowerLimitInput:
        input_names = list(blkdef.lower_limit_inputs)
    elif connector_kind == DgsGraphicalConnectorKind.UpperLimitInput:
        input_names = list(blkdef.upper_limit_inputs)
    else:
        input_names = list()
    return input_names


def _parse_dgs_graphical_connector_kind(
        connector_code: int,
) -> DgsGraphicalConnectorKind | None:
    """Convert one raw DGS connector code without raising on vendor extensions.

    :param connector_code: Integer stored in ``iconfrom`` or ``iconto``.
    :return: Known connector category, or ``None``.
    """
    connector_kind: DgsGraphicalConnectorKind | None
    if connector_code == int(DgsGraphicalConnectorKind.Input):
        connector_kind = DgsGraphicalConnectorKind.Input
    elif connector_code == int(DgsGraphicalConnectorKind.Output):
        connector_kind = DgsGraphicalConnectorKind.Output
    elif connector_code == int(DgsGraphicalConnectorKind.LowerLimitInput):
        connector_kind = DgsGraphicalConnectorKind.LowerLimitInput
    elif connector_code == int(DgsGraphicalConnectorKind.UpperLimitInput):
        connector_kind = DgsGraphicalConnectorKind.UpperLimitInput
    else:
        connector_kind = None
    return connector_kind


def _parse_effective_graphical_connector_kind(
        connector_code: int,
        endpoint_node: object | None,
        is_source_endpoint: bool,
) -> DgsGraphicalConnectorKind | None:
    """Resolve connector codes used by native graphical operators.

    PowerFactory exports ``BlkDiv``, ``BlkMul``, ``BlkSum`` and ``BlkSwt``
    cables with connector category zero. Direction then comes exclusively from
    whether the operator appears in ``pnodfrom`` or ``pnodto``. Other
    graphical nodes retain their explicit one-based connector categories.

    :param connector_code: Raw ``iconfrom`` or ``iconto`` value.
    :param endpoint_node: Parsed node at the corresponding cable endpoint.
    :param is_source_endpoint: Whether the endpoint is stored in ``pnodfrom``.
    :return: Effective connector category, or ``None`` when still unknown.
    """
    parsed_kind: DgsGraphicalConnectorKind | None = (
        _parse_dgs_graphical_connector_kind(connector_code=connector_code)
    )
    if parsed_kind is not None:
        result: DgsGraphicalConnectorKind | None = parsed_kind
    else:
        if isinstance(endpoint_node, (BlkDiv, BlkMul, BlkSum, BlkSwt)):
            if is_source_endpoint:
                result = DgsGraphicalConnectorKind.Output
            else:
                result = DgsGraphicalConnectorKind.Input
        else:
            result = None
    return result


def _resolve_graphical_runtime_output_index(
        endpoint_node: object | None,
        graphical_output_index: int,
        runtime_output_count: int,
) -> int | None:
    """Map one exported graphical output pin to a compact runtime output.

    Native PowerFactory operators expose their result after their input pins,
    so a divider with two inputs can export its only output as local pin two.
    VeraGrid stores outputs in their own compact vector. Other block types keep
    their ordinary zero-based output index unchanged.

    :param endpoint_node: Parsed graphical source node.
    :param graphical_output_index: Local ``inodfrom`` value from ``BlkSig``.
    :param runtime_output_count: Number of materialized runtime outputs.
    :return: Compact runtime output index, or ``None`` when unresolved.
    """
    if 0 <= graphical_output_index < runtime_output_count:
        runtime_output_index: int | None = graphical_output_index
    else:
        if (
                isinstance(endpoint_node, (BlkDiv, BlkMul, BlkSum, BlkSwt))
                and runtime_output_count > 0
        ):
            runtime_output_index = 0
        else:
            runtime_output_index = None
    return runtime_output_index


def _build_blkdef_runtime_input_index_by_connector(
        blkdef: BlkDef,
) -> Dict[Tuple[DgsGraphicalConnectorKind, int], int]:
    """Map category-local graphical pin indices to runtime input indices.

    :param blkdef: PowerFactory block definition.
    :return: Runtime input index keyed by connector category and local index.
    """
    runtime_input_names: List[str] = _build_blkdef_runtime_input_names(
        blkdef=blkdef,
    )
    runtime_index_by_connector: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        int,
    ] = dict()
    connector_kinds: List[DgsGraphicalConnectorKind] = list([
        DgsGraphicalConnectorKind.Input,
        DgsGraphicalConnectorKind.LowerLimitInput,
        DgsGraphicalConnectorKind.UpperLimitInput,
    ])
    connector_kind: DgsGraphicalConnectorKind
    for connector_kind in connector_kinds:
        connector_input_names: List[str] = _get_blkdef_input_names_for_connector(
            blkdef=blkdef,
            connector_kind=connector_kind,
        )
        connector_input_index: int
        for connector_input_index in range(len(connector_input_names)):
            connector_input_name: str = connector_input_names[
                connector_input_index
            ]
            if connector_input_name in runtime_input_names:
                runtime_index_by_connector[
                    (connector_kind, connector_input_index)
                ] = runtime_input_names.index(connector_input_name)
            else:
                pass
        else:
            pass
    else:
        pass
    return runtime_index_by_connector

def _safe_name(name: str) -> str:
    cleaned: str = re.sub(r"[^0-9a-zA-Z_]", "_", name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if cleaned == "":
        cleaned = "unnamed"
    if cleaned[0].isdigit():
        cleaned = f"v_{cleaned}"
    return cleaned


def _symbol_name_length_sort_key(name: str) -> int:
    """
    Return the length used to order literal DGS symbol replacements.

    Longer names must be replaced before their prefixes so the PowerFactory
    expression keeps the same token selection as the original parser.

    :param name: Original PowerFactory symbol name.
    :return: Symbol-name length.
    """
    return len(name)


def _symbol_replacement_length_sort_key(replacement: Tuple[str, str]) -> int:
    """
    Return the original-name length for one cached symbol replacement.

    :param replacement: Original and Python-safe symbol-name pair.
    :return: Original symbol-name length.
    """
    return len(replacement[0])


def _var_name_sort_key(var: Var) -> str:
    """
    Return the deterministic sort key for one symbolic variable.

    :param var: Symbolic variable.
    :returns: Variable-name sort key.
    """
    return var.name


def _parsed_block_name_pair(block_id: str, parsed: "ParsedDgsBlockDefinition") -> tuple[str, str, "ParsedDgsBlockDefinition"]:
    """
    Build a sortable tuple for one parsed block item.

    :param block_id: Parsed block identifier.
    :param parsed: Parsed block definition.
    :returns: Sortable tuple by block display name.
    """
    return parsed.blkdef.loc_name, block_id, parsed


def _standalone_catalog_entry_typ_id_sort_key(entry: "DgsStandaloneBlockCatalogEntry") -> int:
    """
    Return the integer sort key of one standalone catalog entry.

    :param entry: Standalone catalog entry.
    :returns: Integer typ_id sort key.
    """
    return int(entry.typ_id)


def _collect_composite_child_interface(children: List[Block]) -> Tuple[List[Var], List[Var]]:
    """
    Collect the visible composite interface from a list of child blocks.

    Imported DGS roots often have no explicit top-level input/output declaration in
    the source block type even though their children clearly expose reusable ports.
    The composite interface therefore has to be synthesized from the ordered union of
    the child input and output variables.

    :param children: Ordered child blocks of the composite root.
    :return: Pair ``(input_vars, output_vars)``.
    """
    input_vars_by_uid: Dict[int, Var] = dict()
    output_vars_by_uid: Dict[int, Var] = dict()
    child_block: Block
    input_var: Var
    output_var: Var

    for child_block in children:
        # Preserve the child order so the generated composite block ports stay
        # deterministic across imports and persisted template regenerations.
        for input_var in child_block.in_vars:
            if input_var.uid in input_vars_by_uid:
                pass
            else:
                input_vars_by_uid[input_var.uid] = input_var

        for output_var in child_block.out_vars:
            if output_var.uid in output_vars_by_uid:
                pass
            else:
                output_vars_by_uid[output_var.uid] = output_var

    return list(input_vars_by_uid.values()), list(output_vars_by_uid.values())


def _apply_composite_child_interface_if_missing(block: Block) -> None:
    """
    Synthesize the root composite interface when it is missing.

    :param block: Candidate composite root block.
    :return: None.
    """
    input_vars: List[Var]
    output_vars: List[Var]

    if len(block.children) == 0:
        return
    else:
        pass

    if len(block.in_vars) > 0 or len(block.out_vars) > 0:
        return
    else:
        pass

    input_vars, output_vars = _collect_composite_child_interface(block.children)
    block.in_vars = input_vars
    block.out_vars = output_vars


def _sort_candidate_names_with_preferred_first(names: List[str], preferred_name: str) -> None:
    """
    Sort candidate names alphabetically while keeping one preferred name first.

    :param names: Candidate-name list to sort in place.
    :param preferred_name: Preferred name when present.
    :returns: None.
    """
    names.sort()
    if preferred_name in names:
        names.remove(preferred_name)
        names.insert(0, preferred_name)
    else:
        pass


def _split_symbol_blob(raw: str) -> List[str]:
    values: List[str] = list()
    token: List[str] = list()

    for ch in raw:
        if ch in {',', ';'}:
            item = ''.join(token).strip()
            if item:
                values.append(item)
            token = list()
        else:
            token.append(ch)

    item = ''.join(token).strip()
    if item:
        values.append(item)

    return values


def _strip_dgs_inline_comment(raw: str) -> str:
    """
    Remove one PowerFactory DSL comment outside quoted text.

    PowerFactory comments extend to the end of one physical ``sAddEquat``
    field. Removing them before continuation folding preserves the following
    ``&`` field as executable code instead of accidentally discarding it.

    :param raw: One physical exported equation field.
    :return: Field content before the first unquoted comment marker.
    """
    characters: List[str] = list()
    in_single_quote: bool = False
    in_double_quote: bool = False
    character: str

    for character in raw:
        if character == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            characters.append(character)
        elif character == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            characters.append(character)
        else:
            if character == "!" and not in_single_quote and not in_double_quote:
                break
            else:
                characters.append(character)

    return "".join(characters).rstrip()


def _split_equation_statements(raw_equations: Iterable[str]) -> List[str]:
    normalized_blobs: List[str] = list()
    raw_blob: str

    # PowerFactory writes long DSL expressions into consecutive sAddEquat
    # fields and prefixes every continuation field with ``&``. Fold those
    # physical records first so the expression parser sees one logical equation.
    for raw_blob in raw_equations:
        comment_free_blob: str = _strip_dgs_inline_comment(raw=raw_blob)
        stripped_blob: str = comment_free_blob.strip()
        if stripped_blob == "":
            pass
        else:
            if stripped_blob.startswith("&") and len(normalized_blobs) > 0:
                normalized_blobs[-1] = (
                    normalized_blobs[-1]
                    + " "
                    + stripped_blob[1:].strip()
                )
            else:
                normalized_blobs.append(comment_free_blob)

    statements: List[str] = list()

    for blob in normalized_blobs:
        token: List[str] = list()
        in_single_quote: bool = False
        in_double_quote: bool = False

        for ch in blob:
            if ch == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                token.append(ch)
            elif ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                token.append(ch)
            elif ch == ';' and not in_single_quote and not in_double_quote:
                stmt = ''.join(token).split('!', 1)[0].strip().strip('"')
                if stmt != "" and not stmt.startswith('!'):
                    statements.append(stmt)
                token = list()
            else:
                token.append(ch)

        stmt = ''.join(token).split('!', 1)[0].strip().strip('"')
        if stmt != "" and not stmt.startswith('!'):
            statements.append(stmt)

    return statements


def classify_dgs_statement(statement: str) -> tuple[str, str | None]:
    """
    Classify a single DGS equation statement.

    :param statement: One normalized statement.
    :return: Pair ``(kind, lhs_name_or_none)``.
    """
    stmt = statement.strip()

    if stmt == "" or stmt.startswith('!'):
        return 'ignored', None

    if (stmt.startswith("'") and stmt.endswith("'")) or (stmt.startswith('"') and stmt.endswith('"')):
        return 'ignored', None

    if stmt.startswith('vardef('):
        return 'ignored', None

    if re.match(r"^\[[^\]]+\]\s*=\s*(['\"].*['\"])?$", stmt) is not None:
        # Bracket declarations assign engineering units to a previously
        # declared symbol; they are metadata, not executable equations.
        return 'ignored', None

    limit_match = re.match(r'^limfix\((?P<lhs>[^\)]+)\)\s*=\s*(?P<rhs>.+)$', stmt)
    if limit_match is not None:
        return 'limfix', limit_match.group('lhs').strip()

    init_match = re.match(r'^(?P<kind>inc0?|inc)\((?P<lhs>[^\)]+)\)\s*=\s*(?P<rhs>.+)$', stmt)
    if init_match is not None:
        return init_match.group('kind').strip(), init_match.group('lhs').strip()

    diff_match = re.match(r'^(?P<lhs>.+?)\.\s*=\s*(?P<rhs>.+)$', stmt)
    if diff_match is not None:
        return 'state', diff_match.group('lhs').strip()

    if re.match(r'^reset\s*\(.+\)\s*$', stmt) is not None:
        return 'procedural', None

    if stmt.startswith("event("):
        return "discrete_event", None

    alg_match = re.match(r'^(?P<lhs>[^=]+?)\s*=\s*(?P<rhs>.+)$', stmt)
    if alg_match is not None:
        return 'algebraic', alg_match.group('lhs').strip()

    return 'unsupported', None


def _build_statement_report_entry(index: int,
                                  statement: str,
                                  kind: str,
                                  lhs: str | None,
                                  status: str,
                                  detail: str) -> DgsStatementReportEntry:
    """
    Build one DGS statement report entry.

    :param index: 1-based statement index.
    :param statement: Normalized source statement.
    :param kind: Statement kind.
    :param lhs: Left-hand side symbol when available.
    :param status: Statement status.
    :param detail: Additional detail.
    :returns: Statement report entry.
    """
    return DgsStatementReportEntry(index, statement, kind, lhs, status, detail)


def _extract_rhs_text_for_support_report(kind: str, statement: str) -> str | None:
    """
    Extract the right-hand side text for one supported statement shape.

    :param kind: Statement kind.
    :param statement: Normalized source statement.
    :returns: Right-hand side text when the shape is supported.
    """
    rhs_text: str | None = None

    if kind in {'inc', 'inc0'}:
        match = re.match(r'^(?P<kind>inc0?|inc)\((?P<lhs>[^\)]+)\)\s*=\s*(?P<rhs>.+)$', statement)
        if match is not None:
            rhs_text = match.group('rhs').strip()
        else:
            pass
    elif kind == 'state':
        match = re.match(r'^(?P<lhs>.+?)\.\s*=\s*(?P<rhs>.+)$', statement)
        if match is not None:
            rhs_text = match.group('rhs').strip()
        else:
            pass
    elif kind == 'algebraic':
        match = re.match(r'^(?P<lhs>[^=]+?)\s*=\s*(?P<rhs>.+)$', statement)
        if match is not None:
            rhs_text = match.group('rhs').strip()
        else:
            pass
    else:
        pass

    return rhs_text


def _extract_limfix_spec(statement: str) -> tuple[str, str] | None:
    """Return the target and literal interval of one ``limfix`` declaration."""
    match = re.match(r'^limfix\((?P<lhs>[^\)]+)\)\s*=\s*(?P<rhs>.+)$', statement.strip())
    if match is None:
        return None
    return match.group('lhs').strip(), match.group('rhs').strip()


def _ensure_support_report_lhs_symbol(lhs: str | None,
                                      blkdef: BlkDef,
                                      symbol_table: Dict[str, Var],
                                      parser: "DgsExpressionParser") -> None:
    """
    Ensure the left-hand side symbol exists in the parser symbol table.

    :param lhs: Left-hand side symbol when available.
    :param blkdef: Source block definition.
    :param symbol_table: Parser symbol table.
    :param parser: DGS expression parser.
    :returns: None.
    """
    if lhs is not None and lhs not in symbol_table:
        symbol_table[lhs] = Var(name=f"{blkdef.loc_name}__{lhs}")
        parser._replacement_map[_safe_name(lhs)] = lhs
    else:
        pass


def _build_procedural_support_report_entry(index: int,
                                           statement: str,
                                           kind: str,
                                           lhs: str | None,
                                           parser: "DgsExpressionParser") -> DgsStatementReportEntry:
    """
    Build the report entry for one procedural statement.

    :param index: 1-based statement index.
    :param statement: Normalized source statement.
    :param kind: Statement kind.
    :param lhs: Left-hand side symbol when available.
    :param parser: DGS expression parser.
    :returns: Statement report entry.
    """
    try:
        parser.parse_procedural_statement(statement)
    except UnsupportedDgsExpression as exc:
        return _build_statement_report_entry(index, statement, kind, lhs, 'unsupported', str(exc))

    return _build_statement_report_entry(index, statement, kind, lhs, 'supported', 'parsed successfully')


def _build_nonprocedural_support_report_entry(index: int,
                                              statement: str,
                                              kind: str,
                                              lhs: str | None,
                                              blkdef: BlkDef,
                                              symbol_table: Dict[str, Var],
                                              parser: "DgsExpressionParser",
                                              init_seen: Set[str]) -> DgsStatementReportEntry:
    """
    Build the report entry for one non-procedural statement.

    :param index: 1-based statement index.
    :param statement: Normalized source statement.
    :param kind: Statement kind.
    :param lhs: Left-hand side symbol when available.
    :param blkdef: Source block definition.
    :param symbol_table: Parser symbol table.
    :param parser: DGS expression parser.
    :param init_seen: Initialization surfaces already assigned by ``inc0`` or ``inc``.
    :returns: Statement report entry.
    """
    rhs_text: str | None = _extract_rhs_text_for_support_report(kind, statement)

    if rhs_text is None:
        if kind in {'inc', 'inc0', 'state', 'algebraic'}:
            return _build_statement_report_entry(index, statement, kind, lhs, 'unsupported', 'could not isolate RHS')
        else:
            return _build_statement_report_entry(index, statement, kind, lhs, 'unsupported', 'statement shape unsupported')

    _ensure_support_report_lhs_symbol(lhs, blkdef, symbol_table, parser)

    try:
        rhs_expr = parser.parse(rhs_text)
    except UnsupportedDgsExpression as exc:
        return _build_statement_report_entry(index, statement, kind, lhs, 'unsupported', str(exc))

    if isinstance(rhs_expr, Comparison):
        rhs_expr = rhs_expr.to_expression()
    else:
        pass

    if kind == 'inc0' and lhs is not None and lhs in init_seen:
        return _build_statement_report_entry(index, statement, kind, lhs, 'ignored', 'inc0 skipped because init already exists')
    else:
        pass

    if kind in {'inc', 'inc0'} and lhs is not None:
        init_seen.add(lhs)
    else:
        pass

    return _build_statement_report_entry(index, statement, kind, lhs, 'supported', 'parsed successfully')


def build_blkdef_statement_support_report(blkdef: BlkDef) -> List[DgsStatementReportEntry]:
    """
    Build a line-by-line support report for one DGS block definition.

    :param blkdef: Block definition to inspect.
    :return: Ordered support report entries.
    """
    shared_signals: Dict[str, Var] = dict()
    symbol_table, _state_vars, _state_var_map, _diff_var_map, _param_var_map = _build_symbol_table(blkdef, shared_signals)
    _predeclare_statement_lhs_symbols(blkdef, symbol_table)
    parser = DgsExpressionParser(
        symbol_table,
        block_name=blkdef.loc_name,
        dsl_level=blkdef.level,
    )

    report: List[DgsStatementReportEntry] = list()
    init_seen: Set[str] = set()

    for idx, stmt in enumerate(_split_equation_statements(blkdef.equations_raw), start=1):
        kind, lhs = classify_dgs_statement(stmt)
        entry: DgsStatementReportEntry

        if kind == 'ignored':
            entry = _build_statement_report_entry(idx, stmt, kind, lhs, 'ignored', 'ignored by parser policy')
        elif kind == 'procedural':
            entry = _build_procedural_support_report_entry(idx, stmt, kind, lhs, parser)
        elif kind == "discrete_event":
            discrete_action: DgsDiscreteEventAction | None = (
                parse_dgs_discrete_event_statement(statement=stmt)
            )
            if discrete_action is None:
                entry = _build_statement_report_entry(
                    idx,
                    stmt,
                    kind,
                    lhs,
                    "unsupported",
                    "Unsupported or incomplete discrete event command.",
                )
            else:
                entry = _build_statement_report_entry(
                    idx,
                    stmt,
                    kind,
                    lhs,
                    "supported",
                    "Deferred typed switch action parsed successfully.",
                )
        elif kind == 'limfix':
            declaration = _extract_limfix_spec(stmt)
            if declaration is None:
                entry = _build_statement_report_entry(
                    idx, stmt, kind, lhs, 'unsupported', 'malformed fixed-limit declaration'
                )
            else:
                entry = _build_statement_report_entry(
                    idx, stmt, kind, lhs, 'supported', 'fixed-limit metadata preserved literally'
                )
        else:
            entry = _build_nonprocedural_support_report_entry(idx, stmt, kind, lhs, blkdef, symbol_table, parser, init_seen)

        report.append(entry)

    return report


def summarize_blkdef_support_report(entries: List[DgsStatementReportEntry]) -> Dict[str, int]:
    """
    Count statuses and statement kinds from a support report.

    :param entries: Statement report entries.
    :return: Summary counters.
    """
    summary: Dict[str, int] = dict()
    summary['supported'] = 0
    summary['unsupported'] = 0
    summary['ignored'] = 0
    summary['state'] = 0
    summary['algebraic'] = 0
    summary['inc'] = 0
    summary['inc0'] = 0
    summary['procedural'] = 0
    summary['limfix'] = 0
    summary["discrete_event"] = 0

    for entry in entries:
        summary[entry.status] = summary.get(entry.status, 0) + 1
        summary[entry.kind] = summary.get(entry.kind, 0) + 1

    return summary


def _comparison_to_expr(obj: Expr | Comparison) -> Expr:
    if isinstance(obj, Comparison):
        return obj.to_expression()
    return obj

class ElmCompInstanceEntry:
    """
    One direct instance declared inside an ElmComp through pblk/pelm.

    :param slot_id: Slot identifier.
    :param slot_name: Slot display name.
    :param element_id: Instantiated element identifier.
    :param element_name: Instantiated element display name.
    :param element_kind: Element kind, for example ElmDsl or ElmComp.
    :param type_id: Underlying BlkDef identifier if available.
    :param type_name: Underlying BlkDef display name if available.
    :param slot_index: Ordinal index of the paired pblk/pelm relation.
    :param slot_element: Raw BlkSlot compatible-element reference.
    :param slot_filter: Raw BlkSlot model filter text.
    :param powerfactory_astable_integration: Native per-model RMS integration selector.
    """

    __slots__ = (
        "slot_id",
        "slot_name",
        "element_id",
        "element_name",
        "element_kind",
        "type_id",
        "type_name",
        "parameter_values",
        "slot_index",
        "slot_element",
        "slot_filter",
        "powerfactory_astable_integration",
    )

    def __init__(
        self,
        slot_id: str | None,
        slot_name: str | None,
        element_id: str | None,
        element_name: str | None,
        element_kind: str | None,
        type_id: str | None,
        type_name: str | None,
        parameter_values: DgsParameterValues | None = None,
        slot_index: int | None = None,
        slot_element: str | None = None,
        slot_filter: str | None = None,
        powerfactory_astable_integration: bool = False,
    ) -> None:
        """
        Store one exact composite slot relation.

        :param slot_id: Slot identifier.
        :param slot_name: Slot display name.
        :param element_id: Instantiated element identifier.
        :param element_name: Instantiated element display name.
        :param element_kind: Instantiated DGS class.
        :param type_id: Dynamic BlkDef identifier, when applicable.
        :param type_name: Dynamic BlkDef display name, when applicable.
        :param parameter_values: Instance parameter values.
        :param slot_index: Ordinal pblk/pelm index.
        :param slot_element: Raw BlkSlot compatible-element reference.
        :param slot_filter: Raw BlkSlot model filter text.
        :param powerfactory_astable_integration: Native per-model RMS integration selector.
        :return: None.
        """
        self.slot_id: str | None = slot_id
        self.slot_name: str | None = slot_name
        self.element_id: str | None = element_id
        self.element_name: str | None = element_name
        self.element_kind: str | None = element_kind
        self.type_id: str | None = type_id
        self.type_name: str | None = type_name
        self.parameter_values: DgsParameterValues = dict(parameter_values or {})
        self.slot_index: int | None = slot_index
        self.slot_element: str | None = slot_element
        self.slot_filter: str | None = slot_filter
        self.powerfactory_astable_integration: bool = bool(
            powerfactory_astable_integration
        )


class DgsBlockInstanceSelection:
    """
    Selection result for a block resolved from the root ElmComp slots.

    :param instance_entry: Matched root instance entry.
    :param parsed_block: Parsed block definition associated to the entry.
    """

    __slots__ = ("instance_entry", "parsed_block")

    def __init__(
        self,
        instance_entry: ElmCompInstanceEntry,
        parsed_block: "ParsedDgsBlockDefinition",
    ) -> None:
        self.instance_entry: ElmCompInstanceEntry = instance_entry
        self.parsed_block: ParsedDgsBlockDefinition = parsed_block

class UnsupportedDgsExpression(Exception):
    pass


def _split_top_level_dsl_operator(expr: str, token: str) -> Tuple[str, str] | None:
    depth: int = 0
    text = expr.strip()
    token_len = len(token)
    idx: int = 0

    while idx <= len(text) - token_len:
        ch = text[idx]
        if ch == '(':
            depth += 1
            idx += 1
        elif ch == ')':
            depth = max(0, depth - 1)
            idx += 1
        else:
            if depth == 0 and text[idx:idx + token_len].lower() == token:
                left = text[:idx].strip()
                right = text[idx + token_len:].strip()
                if left and right:
                    return left, right
                else:
                    return None
            else:
                idx += 1

    return None


def _predeclare_statement_lhs_symbols(blkdef: BlkDef, symbol_table: Dict[str, Var]) -> None:
    for stmt in _split_equation_statements(blkdef.equations_raw):
        kind, lhs = classify_dgs_statement(stmt)
        if kind in {'inc', 'inc0', 'state', 'algebraic'} and lhs is not None and lhs not in symbol_table:
            symbol_table[lhs] = Var(name=f"{blkdef.loc_name}__{lhs}")


class DgsExpressionParser(ast.NodeVisitor):
    def __init__(self,
                 symbol_table: Dict[str, Var],
                 block_name: str = "",
                 simulation_domain: str = "emt",
                 dsl_level: int = 7) -> None:
        """Create one PowerFactory DSL expression parser.

        :param symbol_table: Exact DGS symbols available to expressions.
        :param block_name: Human-readable source block name.
        :param simulation_domain: Target VeraGrid simulation domain.
        :param dsl_level: PowerFactory DSL compatibility level.
        :return: None.
        """
        self.symbol_table: Dict[str, Var] = symbol_table
        self.block_name: str = block_name
        self.simulation_domain: str = simulation_domain
        self.dsl_level: int = dsl_level
        self._replacement_map: Dict[str, str] = dict()
        self._symbol_replacements: List[Tuple[str, str]] = list()
        original_name: str
        ordered_symbol_names: List[str] = sorted(
            symbol_table.keys(),
            key=_symbol_name_length_sort_key,
            reverse=True,
        )
        for original_name in ordered_symbol_names:
            safe_name: str = _safe_name(original_name)
            self._replacement_map[safe_name] = original_name
            self._symbol_replacements.append((original_name, safe_name))
        self._procedural_mode_defaults: Dict[Var, Expr | Const] = dict()
        self._procedural_logic_entries: List[ProceduralLogicBase] = list()
        self._procedural_dependency_names: Set[str] = set()
        self._procedural_counter: int = 0
        self._time_var: Var | None = None
        # PowerFactory's limstate helpers constrain the referenced state, not
        # only the displayed output. Preserve those bounds until all equations
        # have been parsed because the state equation can precede the helper.
        self._state_limits_by_uid: Dict[int, Tuple[Expr, Expr]] = dict()

    @property
    def procedural_mode_defaults(self) -> Dict[Var, Expr | Const]:
        return self._procedural_mode_defaults

    @property
    def procedural_logic_entries(self) -> List[ProceduralLogicBase]:
        return self._procedural_logic_entries

    @property
    def procedural_dependency_names(self) -> Set[str]:
        """
        Return source symbols consumed by retained runtime procedural logic.

        :return: Exact PowerFactory symbol names required while time advances.
        """
        return set(self._procedural_dependency_names)

    @property
    def state_limits_by_uid(self) -> Dict[int, Tuple[Expr, Expr]]:
        """
        Return PowerFactory state limits discovered in symbolic helpers.

        :return: Lower and upper expressions keyed by referenced state UID.
        """
        return dict(self._state_limits_by_uid)

    def _new_procedural_mode_var(self, prefix: str) -> Var:
        base_name: str = f"{self.block_name}__proc_{prefix}_{self._procedural_counter}" if self.block_name else f"proc_{prefix}_{self._procedural_counter}"
        self._procedural_counter += 1
        var: Var = Var(name=base_name)
        self.symbol_table[base_name] = var
        safe_name: str = _safe_name(base_name)
        self._replacement_map[safe_name] = base_name
        self._symbol_replacements.append((base_name, safe_name))
        self._symbol_replacements.sort(
            key=_symbol_replacement_length_sort_key,
            reverse=True,
        )
        self._procedural_mode_defaults[var] = Const(0.0)
        return var

    def apply_explicit_latch_initialization_defaults(
            self,
            algebraic_rhs: Dict[str, Expr],
            init_rhs: Dict[str, Expr],
    ) -> None:
        """Transfer exported ``inc()`` values to retained latch modes.

        PowerFactory commonly declares ``output=flipflop(...)`` followed by an
        explicit ``inc(output)=...``. The algebraic output mirrors the retained
        procedural mode, so initializing only the algebraic shell would be
        overwritten on the first procedural update. Seeding the exact mode from
        the same DGS expression preserves the declared latch memory.

        :param algebraic_rhs: Runtime algebraic assignments by target name.
        :param init_rhs: Exported initialization assignments by target name.
        :return: None.
        """
        procedural_entry: ProceduralLogicBase
        initialization_target_name: str
        initialization_expression: Expr
        runtime_expression: Expr | None

        # Only stateful latch helpers consume an explicit retained startup
        # value; selectors and sampled-value helpers already derive theirs from
        # the operating-point source expression.
        for initialization_target_name, initialization_expression in (
                init_rhs.items()
        ):
            runtime_expression = algebraic_rhs.get(
                initialization_target_name,
                None,
            )
            if (
                    isinstance(runtime_expression, Var)
            ):
                for procedural_entry in self._procedural_logic_entries:
                    if (
                            isinstance(procedural_entry, FlipFlopLogic)
                            and procedural_entry.output_var_name
                            == runtime_expression.name
                    ):
                        # Mark only binary latches whose retained state is
                        # explicitly owned by this DGS ``inc()`` assignment.
                        self._procedural_mode_defaults[runtime_expression] = (
                            initialization_expression
                        )
                        procedural_entry.use_mode_default_at_initialization = (
                            True
                        )
                    else:
                        pass
                else:
                    pass
            else:
                pass
        else:
            pass

    def _get_time_var(self) -> Var:
        if self._time_var is None:
            self._time_var = Var(name='glob_time')
        return self._time_var

    def parse_procedural_statement(self, statement: str) -> None:
        try:
            tree = ast.parse(self.preprocess(statement), mode='eval')
        except SyntaxError as exc:
            raise UnsupportedDgsExpression(str(exc)) from exc

        node = tree.body
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise UnsupportedDgsExpression("Unsupported procedural statement")

        if node.func.id != 'reset' or len(node.args) != 3:
            raise UnsupportedDgsExpression(f"Unsupported procedural helper '{node.func.id}'")

        target_node = node.args[0]
        if not isinstance(target_node, ast.Name):
            raise UnsupportedDgsExpression("reset target must be a DSL variable name")

        target_original = self._replacement_map.get(target_node.id)
        if target_original is None or target_original not in self.symbol_table:
            raise UnsupportedDgsExpression(f"Unknown reset target '{target_node.id}'")

        target_var = self.symbol_table[target_original]
        reset_expr = self.visit(node.args[1])
        value_expr = self.visit(node.args[2])

        self._procedural_logic_entries.append(
            ResetOnRisingEdgeLogic(
                target_var_name=target_var.name,
                reset_expr=reset_expr,
                value_expr=value_expr,
                name=f"{target_var.name}_reset",
            )
        )

    def preprocess(self, expr: str) -> str:
        """
        Convert one PowerFactory DSL expression into Python syntax.

        Symbol replacements are literal operations. Precomputing their stable
        longest-first order avoids rebuilding and compiling thousands of
        regular expressions while preserving the former substitution order.

        :param expr: Raw PowerFactory DSL expression.
        :return: Expression accepted by Python's AST parser.
        """
        text: str = expr.strip()
        # PowerFactory uses braces only as explicit logical grouping delimiters.
        # Python parses braces as set/dict literals, which previously caused valid
        # derivative equations with nested anti-windup logic to be discarded.
        text = text.replace('{', '(')
        text = text.replace('}', ')')
        text = text.replace('^', '**')
        text = text.replace('.and.', ' and ')
        text = text.replace('.or.', ' or ')
        text = text.replace('.not.', ' not ')
        text = text.replace('<>', '!=')
        text = re.sub(r'(?<![<>=!])=(?!=)', '==', text)

        original_name: str
        safe_name: str
        for original_name, safe_name in self._symbol_replacements:
            # The original regular expression was an escaped literal, so
            # ``str.replace`` has the same matching semantics without regex.
            text = text.replace(original_name, safe_name)

        return text

    def parse(self, expr: str) -> Expr | Comparison:
        for token in ['.nor.', '.nand.', '.eor.']:
            split_parts = _split_top_level_dsl_operator(expr, token)
            if split_parts is not None:
                left_raw, right_raw = split_parts
                left_expr = _comparison_to_expr(self.parse(left_raw))
                right_expr = _comparison_to_expr(self.parse(right_raw))

                if token == '.nor.':
                    return (Const(1.0) - left_expr) * (Const(1.0) - right_expr)
                if token == '.nand.':
                    return Const(1.0) - left_expr * right_expr
                return left_expr + right_expr - Const(2.0) * left_expr * right_expr

        try:
            tree = ast.parse(self.preprocess(expr), mode='eval')
        except SyntaxError as exc:
            raise UnsupportedDgsExpression(str(exc)) from exc
        return self.visit(tree.body)

    def visit_Name(self, node: ast.Name) -> Expr:
        original: str | None = self._replacement_map.get(node.id)
        if original is None or original not in self.symbol_table:
            raise UnsupportedDgsExpression(f"Unknown symbol '{node.id}'")
        return self.symbol_table[original]

    def visit_Constant(self, node: ast.Constant) -> Expr:
        if isinstance(node.value, (int, float)):
            return Const(float(node.value))
        raise UnsupportedDgsExpression(f"Unsupported constant '{node.value}'")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Expr:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.Not):
            return Const(1.0) - _comparison_to_expr(operand)
        raise UnsupportedDgsExpression(ast.dump(node))

    def visit_BinOp(self, node: ast.BinOp) -> Expr:
        # PowerFactory DSL uses comparisons as 0/1 numeric expressions in some
        # arithmetic formulas, so normalize them before composing the symbolic
        # arithmetic tree.
        left = _comparison_to_expr(self.visit(node.left))
        right = _comparison_to_expr(self.visit(node.right))
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            # PowerFactory DSL regularizes an exact zero divisor to 1e-6. This
            # makes a zero-time step generator active immediately after t=0
            # without producing a startup NaN in the complete DAE.
            return Func2("dgs_divide", left, right)
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise UnsupportedDgsExpression(ast.dump(node))

    def visit_Compare(self, node: ast.Compare) -> Comparison:
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise UnsupportedDgsExpression("Only simple comparisons are supported")
        left = self.visit(node.left)
        right = self.visit(node.comparators[0])
        op = node.ops[0]
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Eq):
            # ``Var.__eq__`` intentionally compares variable identity when both
            # operands are variables.  A DGS equality is always a symbolic
            # relation, including ``var_a == var_b``.
            return Comparison(left, CmpOp.EQ, right)
        if isinstance(op, ast.NotEq):
            return Const(1.0) - Comparison(left, CmpOp.EQ, right).to_expression()
        raise UnsupportedDgsExpression(ast.dump(node))

    def visit_BoolOp(self, node: ast.BoolOp) -> Expr:
        values = [_comparison_to_expr(self.visit(v)) for v in node.values]
        if isinstance(node.op, ast.And):
            result = values[0]
            for value in values[1:]:
                result = result * value
            return result
        if isinstance(node.op, ast.Or):
            result = values[0]
            for value in values[1:]:
                result = Const(1.0) - (Const(1.0) - result) * (Const(1.0) - value)
            return result
        raise UnsupportedDgsExpression(ast.dump(node))

    def visit_Call(self, node: ast.Call) -> Expr:
        if not isinstance(node.func, ast.Name):
            raise UnsupportedDgsExpression(ast.dump(node))

        name = node.func.id
        args: List[Expr | Comparison] = [self.visit(arg) for arg in node.args]
        procedural_helper_names: Set[str] = set([
            "select",
            "select_const",
            "ifelse",
            "selfix",
            "selfix_const",
            "lastvalue",
            "delay",
            "movingavg",
            "gradlim_const",
            "flipflop",
            "aflipflop",
            "picdro",
            "picdro_const",
        ])
        if name in procedural_helper_names:
            procedural_arg: Expr | Comparison
            procedural_expr: Expr
            procedural_var: Var
            for procedural_arg in args:
                procedural_expr = _comparison_to_expr(procedural_arg)
                for procedural_var in procedural_expr.get_vars():
                    self._procedural_dependency_names.add(procedural_var.name)
        else:
            pass

        if name == 'sin' and len(args) == 1:
            return sin(args[0])
        if name == 'cos' and len(args) == 1:
            return cos(args[0])
        if name == 'tan' and len(args) == 1:
            return tan(args[0])
        if name == 'asin' and len(args) == 1:
            return asin(args[0])
        if name == 'acos' and len(args) == 1:
            return acos(args[0])
        if name == 'atan' and len(args) == 1:
            return atan(args[0])
        if name == 'sqrt' and len(args) == 1:
            return sqrt(args[0])
        if name == 'abs' and len(args) == 1:
            return abs(args[0])
        if name == 'pow' and len(args) == 2:
            # PowerFactory accepts both ``a ^ b`` and ``pow(a, b)``.  Python's
            # AST represents the latter as a function call, so translate it to
            # the same symbolic power node used by the infix form.
            power_base: Expr = _comparison_to_expr(args[0])
            power_exponent: Expr = _comparison_to_expr(args[1])
            return power_base ** power_exponent
        if name == 'exp' and len(args) == 1:
            return exp(args[0])
        if name == 'log' and len(args) == 1:
            return log(args[0])
        if name == 'atan2' and len(args) == 2:
            return Func2('atan2', args[0], args[1])
        if name == 'modulo' and len(args) == 2:
            modulo_value: Expr = _comparison_to_expr(args[0])
            modulo_base: Expr = _comparison_to_expr(args[1])
            return modulo_value - floor(modulo_value / modulo_base) * modulo_base
        if name == 'max' and len(args) >= 2:
            maximum_expr: Expr = _comparison_to_expr(args[0])
            maximum_arg: Expr | Comparison
            for maximum_arg in args[1:]:
                maximum_expr = max(
                    maximum_expr,
                    _comparison_to_expr(maximum_arg),
                )
            return maximum_expr
        if name == 'min' and len(args) >= 2:
            minimum_expr: Expr = _comparison_to_expr(args[0])
            minimum_arg: Expr | Comparison
            for minimum_arg in args[1:]:
                minimum_expr = min(
                    minimum_expr,
                    _comparison_to_expr(minimum_arg),
                )
            return minimum_expr
        if name == 'sqr' and len(args) == 1:
            return args[0] * args[0]
        if name in {'lim', 'lim_const'} and len(args) == 3:
            return hard_sat(args[0], args[1], args[2])
        if name in {'limstate', 'limstate_const'} and len(args) == 3:
            limited_expr: Expr = _comparison_to_expr(args[0])
            lower_limit_expr: Expr = _comparison_to_expr(args[1])
            upper_limit_expr: Expr = _comparison_to_expr(args[2])
            if isinstance(limited_expr, Var):
                existing_limits: Tuple[Expr, Expr] | None = (
                    self._state_limits_by_uid.get(limited_expr.uid, None)
                )
                if existing_limits is None:
                    # The derivative is transformed after the complete block
                    # is parsed, so source statement order cannot lose limits.
                    self._state_limits_by_uid[limited_expr.uid] = (
                        lower_limit_expr,
                        upper_limit_expr,
                    )
                else:
                    # Repeated limstate reads describe the same state contract;
                    # retain the first declaration deterministically.
                    pass
                if self.dsl_level >= 7:
                    # Level 7 constrains the state at initialization as well,
                    # so the output can expose the already-limited state
                    # identity without adding a second algebraic limiter.
                    return limited_expr
                else:
                    # Legacy DSL levels permit ``inc(x)`` to remain outside
                    # the bounds while the limstate output is clipped. This is
                    # used by GB governor models whose level-4 startup states
                    # deliberately sit beyond the visible valve range.
                    return hard_sat(
                        limited_expr,
                        lower_limit_expr,
                        upper_limit_expr,
                    )
            else:
                # A non-state expression still has ordinary saturation
                # semantics, but there is no derivative to constrain.
                return hard_sat(
                    limited_expr,
                    lower_limit_expr,
                    upper_limit_expr,
                )
        if name in {'select', 'select_const', 'ifelse'} and len(args) == 3:
            if isinstance(args[0], Const) and args[0].value is not None:
                return args[1] if float(args[0].value) > 0.5 else args[2]
            else:
                pass

            selector = self._new_procedural_mode_var(name)
            # PowerFactory selector guards are logical signals encoded as
            # numeric 0/1 values. Use the midpoint as a stable decision
            # boundary so Newton noise around zero cannot spuriously select
            # the true branch. Signed -1/+1 guards retain the same meaning.
            selector_source: Expr = heaviside(
                _comparison_to_expr(args[0]) - Const(0.5)
            )
            # A sampled selector has the condition's value at t=0. Seeding the
            # procedural output from that exact expression lets explicit
            # initialization evaluate downstream assignments with the same
            # branch that the first runtime update will retain.
            # The internal blend must receive a strict 0/1 mask; retaining a
            # raw signed guard would extrapolate both branches.
            self._procedural_mode_defaults[selector] = selector_source
            self._procedural_logic_entries.append(
                SampledValueLogic(
                    output_var_name=selector.name,
                    source_expr=selector_source,
                    name=selector.name,
                    evaluation_mode=(
                        SampledValueEvaluationMode.ImplicitIterate
                    ),
                )
            )

            # The selected branches can themselves be comparisons. DGS treats
            # those branches as numeric 0/1 expressions, so convert them before
            # blending both sides with the sampled selector flag.
            when_true_expr: Expr = _comparison_to_expr(args[1])
            when_false_expr: Expr = _comparison_to_expr(args[2])
            return selector * when_true_expr + (Const(1.0) - selector) * when_false_expr
        if name in {'selfix', 'selfix_const'} and len(args) == 3:
            if isinstance(args[0], Const) and args[0].value is not None:
                return args[1] if float(args[0].value) > 0.5 else args[2]
            selector = self._new_procedural_mode_var(name)
            # ``selfix`` samples its condition once, therefore its startup
            # event parameter is the exported condition rather than zero.
            self._procedural_mode_defaults[selector] = _comparison_to_expr(args[0])
            self._procedural_logic_entries.append(
                FixedSampleLogic(
                    output_var_name=selector.name,
                    condition_expr=args[0],
                    name=selector.name,
                )
            )

            # DGS control models also use relational branches inside retained
            # selectors, so materialize those relations as symbolic 0/1 values
            # before building the blended expression.
            when_true_expr = _comparison_to_expr(args[1])
            when_false_expr = _comparison_to_expr(args[2])
            return selector * when_true_expr + (Const(1.0) - selector) * when_false_expr
        if name == 'lastvalue' and len(args) == 1:
            sampled = self._new_procedural_mode_var(name)
            # At the initial instant there is no previous accepted sample, so
            # PowerFactory initializes ``lastvalue`` from its source.
            self._procedural_mode_defaults[sampled] = _comparison_to_expr(args[0])
            self._procedural_logic_entries.append(
                SampledValueLogic(
                    output_var_name=sampled.name,
                    source_expr=args[0],
                    name=sampled.name,
                    evaluation_mode=(
                        SampledValueEvaluationMode.AcceptedBoundary
                    ),
                )
            )
            return sampled
        if name == 'delay' and len(args) == 2:
            delayed = self._new_procedural_mode_var(name)
            # The delay history starts with the operating-point source sample.
            self._procedural_mode_defaults[delayed] = _comparison_to_expr(args[0])
            self._procedural_logic_entries.append(
                TimeDelayLogic(
                    output_var_name=delayed.name,
                    source_expr=args[0],
                    delay_expr=args[1],
                    name=delayed.name,
                )
            )
            return delayed
        if name == 'movingavg' and len(args) == 3:
            averaged = self._new_procedural_mode_var(name)
            # A moving average with no prior history starts from its only
            # available source sample at the operating point.
            self._procedural_mode_defaults[averaged] = _comparison_to_expr(args[0])
            self._procedural_logic_entries.append(
                MovingAverageLogic(
                    output_var_name=averaged.name,
                    source_expr=args[0],
                    delay_expr=args[1],
                    window_expr=args[2],
                    name=averaged.name,
                )
            )
            return averaged
        if name == 'gradlim_const' and len(args) == 3:
            limited = self._new_procedural_mode_var(name)
            # A gradient limiter constrains changes after t=0; its retained
            # startup value is the unmodified source operating point.
            self._procedural_mode_defaults[limited] = _comparison_to_expr(args[0])
            self._procedural_logic_entries.append(
                GradientLimiterLogic(
                    output_var_name=limited.name,
                    source_expr=args[0],
                    lower_rate_expr=args[1],
                    upper_rate_expr=args[2],
                    name=limited.name,
                )
            )
            return limited
        if name == 'flipflop' and len(args) == 2:
            latch = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                FlipFlopLogic(
                    output_var_name=latch.name,
                    set_expr=args[0],
                    reset_expr=args[1],
                    name=latch.name,
                )
            )
            return latch
        if name == 'aflipflop' and len(args) == 3:
            latch = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                AnalogFlipFlopLogic(
                    output_var_name=latch.name,
                    input_expr=args[0],
                    set_expr=args[1],
                    reset_expr=args[2],
                    name=latch.name,
                )
            )
            return latch
        if name in {'picdro', 'picdro_const'} and len(args) == 3:
            latch = self._new_procedural_mode_var(name)
            self._procedural_logic_entries.append(
                PickupDropoffLogic(
                    output_var_name=latch.name,
                    bool_expr=args[0],
                    pickup_delay_expr=args[1],
                    drop_delay_expr=args[2],
                    name=latch.name,
                )
            )
            return latch
        if name == 'pi' and len(args) == 0:
            return Const(math.pi)
        if name == 'twopi' and len(args) == 0:
            return Const(2.0 * math.pi)
        if name == 'time' and len(args) == 0:
            return self._get_time_var()
        if name == 'rms' and len(args) == 0:
            return Const(1.0)

        if name in {'inc', 'reset', 'lapprox', 'vardef'}:
            raise UnsupportedDgsExpression(f"Unsupported PowerFactory helper '{name}'")

        raise UnsupportedDgsExpression(f"Unsupported function '{name}'")

    def generic_visit(self, node: ast.AST):
        raise UnsupportedDgsExpression(ast.dump(node))


class ParsedDgsBlockDefinition:
    """
    Parsed symbolic representation of one DGS block definition.
    """

    __slots__ = (
        "blkdef",
        "symbol_table",
        "state_rhs",
        "state_limits_by_uid",
        "algebraic_rhs",
        "init_rhs",
        "inc0_signal_names",
        "mode_dict",
        "procedural_logic",
        "discrete_event_actions",
        "fixed_limit_specs",
        "unsupported_lines",
        "signal_dependencies",
        "procedural_dependency_names",
    )

    def __init__(self,
                 blkdef: BlkDef,
                 symbol_table: Dict[str, Var],
                 state_rhs: Dict[str, Expr],
                 state_limits_by_uid: Dict[int, Tuple[Expr, Expr]],
                 algebraic_rhs: Dict[str, Expr],
                 init_rhs: Dict[str, Expr],
                 inc0_signal_names: Set[str],
                 mode_dict: Dict[Var, Expr | Const],
                 procedural_logic: List[ProceduralLogicBase],
                 discrete_event_actions: List[DgsDiscreteEventAction],
                 fixed_limit_specs: Dict[str, str],
                 unsupported_lines: List[str],
                 signal_dependencies: Dict[str, Set[str]],
                 procedural_dependency_names: Set[str]) -> None:
        """
        Store one parsed DGS block definition.

        :param blkdef: Source block definition.
        :param symbol_table: Symbol table used during parsing.
        :param state_rhs: Differential equations by state name.
        :param state_limits_by_uid: Limited-state bounds keyed by parsed state UID.
        :param algebraic_rhs: Algebraic equations by signal name.
        :param init_rhs: Initialization equations by signal name.
        :param inc0_signal_names: Boundary signals declared with ``inc0()``.
        :param mode_dict: Procedural runtime defaults.
        :param procedural_logic: Retained procedural logic entries.
        :param discrete_event_actions: Deferred typed equipment actions.
        :param fixed_limit_specs: Literal ``limfix`` declarations by parameter name.
        :param unsupported_lines: Unsupported source statements.
        :param signal_dependencies: Signal dependency graph.
        :param procedural_dependency_names: Symbols consumed by runtime logic.
        :returns: None.
        """
        self.blkdef = blkdef
        self.symbol_table = symbol_table
        self.state_rhs = state_rhs
        self.state_limits_by_uid = state_limits_by_uid
        self.algebraic_rhs = algebraic_rhs
        self.init_rhs = init_rhs
        self.inc0_signal_names = inc0_signal_names
        self.mode_dict = mode_dict
        self.procedural_logic = procedural_logic
        self.discrete_event_actions = discrete_event_actions
        self.fixed_limit_specs = fixed_limit_specs
        self.unsupported_lines = unsupported_lines
        self.signal_dependencies = signal_dependencies
        self.procedural_dependency_names = procedural_dependency_names


class DgsRootBlockResult:
    """
    Root DGS block parse result.
    """

    __slots__ = (
        "root_block",
        "root_blkdef",
        "root_element",
        "parsed_blocks",
        "dependency_graph",
        "producer_map",
        "consumer_map",
    )

    def __init__(self,
                 root_block: Block,
                 root_blkdef: ParsedDgsBlockDefinition,
                 root_element: ElmComp,
                 parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
                 dependency_graph: Dict[str, Set[str]],
                 producer_map: Dict[str, Set[str]],
                 consumer_map: Dict[str, Set[str]]) -> None:
        """
        Store the root DGS parse result.

        :param root_block: Root symbolic block.
        :param root_blkdef: Root parsed block definition.
        :param root_element: Root ElmComp element.
        :param parsed_blocks: Parsed blocks by identifier.
        :param dependency_graph: Dependency graph between parsed blocks.
        :param producer_map: Producers by signal name.
        :param consumer_map: Consumers by signal name.
        :returns: None.
        """
        self.root_block = root_block
        self.root_blkdef = root_blkdef
        self.root_element = root_element
        self.parsed_blocks = parsed_blocks
        self.dependency_graph = dependency_graph
        self.producer_map = producer_map
        self.consumer_map = consumer_map


class DgsBlockSubgraphResult:
    """
    Selected DGS block subgraph result.
    """

    __slots__ = (
        "selected_block",
        "view_block",
        "node_ids",
        "dependency_graph",
        "upstream",
        "downstream",
    )

    def __init__(self,
                 selected_block: ParsedDgsBlockDefinition,
                 view_block: Block,
                 node_ids: Set[str],
                 dependency_graph: Dict[str, Set[str]],
                 upstream: Dict[str, Set[str]],
                 downstream: Dict[str, Set[str]]) -> None:
        """
        Store one selected DGS block subgraph.

        :param selected_block: Selected parsed block definition.
        :param view_block: View block built for export or analysis.
        :param node_ids: Node identifiers in the subgraph.
        :param dependency_graph: Dependency graph restricted to the subgraph.
        :param upstream: Upstream closure graph.
        :param downstream: Downstream closure graph.
        :returns: None.
        """
        self.selected_block = selected_block
        self.view_block = view_block
        self.node_ids = node_ids
        self.dependency_graph = dependency_graph
        self.upstream = upstream
        self.downstream = downstream


class GraphicConnectionInstruction:
    """
    One resolved graphical connection instruction used during template export.
    """

    __slots__ = (
        "consumer_node_id",
        "consumer_input_name",
        "source_kind",
        "consumer_input_index",
        "source_output_name",
        "source_output_index",
        "source_node_id",
        "source_root_name",
    )

    def __init__(self,
                 consumer_node_id: str,
                 consumer_input_name: str,
                 source_kind: str,
                 consumer_input_index: int | None = None,
                 source_output_name: str | None = None,
                 source_output_index: int | None = None,
                 source_node_id: str | None = None,
                 source_root_name: str | None = None) -> None:
        """
        Store one resolved graphical connection instruction.

        :param consumer_node_id: Consumer node identifier.
        :param consumer_input_name: Consumer input name.
        :param source_kind: Source-kind discriminator.
        :param consumer_input_index: Consumer input index.
        :param source_output_name: Source output name.
        :param source_output_index: Source output index.
        :param source_node_id: Source node identifier.
        :param source_root_name: Source root-input name.
        :returns: None.
        """
        self.consumer_node_id = consumer_node_id
        self.consumer_input_name = consumer_input_name
        self.source_kind = source_kind
        self.consumer_input_index = consumer_input_index
        self.source_output_name = source_output_name
        self.source_output_index = source_output_index
        self.source_node_id = source_node_id
        self.source_root_name = source_root_name


class DgsGraphicTreeResult:
    """
    Graphical internal tree reconstruction result.

    :param selected_block: Parsed selected block definition.
    :param view_block: Reconstructed block tree view.
    :param node_ids: Internal graphical node identifiers.
    :param adjacency: Undirected adjacency between graphical nodes.
    :param node_labels: Display label per graphical node.
    :param node_kinds: DGS object kind per graphical node.
    """

    __slots__ = (
        "selected_block",
        "view_block",
        "node_ids",
        "adjacency",
        "node_labels",
        "node_kinds",
        "child_node_ids",
        "connections",
    )

    def __init__(
        self,
        selected_block: ParsedDgsBlockDefinition,
        view_block: Block,
        node_ids: Set[str],
        adjacency: Dict[str, Set[str]],
        node_labels: Dict[str, str],
        node_kinds: Dict[str, str],
        child_node_ids: List[str],
        connections: List[GraphicConnectionInstruction],
    ) -> None:
        self.selected_block = selected_block
        self.view_block = view_block
        self.node_ids = node_ids
        self.adjacency = adjacency
        self.node_labels = node_labels
        self.node_kinds = node_kinds
        self.child_node_ids = child_node_ids
        self.connections = connections


class DgsGraphicalParseContext:
    """Immutable indexes shared by every graphical slot in one DGS file."""

    __slots__ = (
        "adjacency",
        "node_by_id",
        "node_signals",
        "element_by_id",
    )

    def __init__(
            self,
            adjacency: Dict[str, Set[str]],
            node_by_id: Dict[str, object],
            node_signals: Dict[str, Set[str]],
            element_by_id: Dict[str, object],
    ) -> None:
        """Store precomputed DGS graphical indexes.

        :param adjacency: Undirected BlkSig adjacency by node FID.
        :param node_by_id: Graphical DGS objects indexed by FID.
        :param node_signals: Exact cable labels attached to each node.
        :param element_by_id: All parsed DGS elements indexed by FID.
        :return: None.
        """
        self.adjacency = adjacency
        self.node_by_id = node_by_id
        self.node_signals = node_signals
        self.element_by_id = element_by_id


class DgsDirectRootBuildResult:
    """Root block plus exact reusable direct-child materializations."""

    __slots__ = (
        "root_block",
        "child_block_by_slot_id",
        "graphical_slot_ids",
    )

    def __init__(
            self,
            root_block: Block,
            child_block_by_slot_id: Dict[str, Block],
            graphical_slot_ids: Set[str],
    ) -> None:
        """Store one direct-root build result.

        :param root_block: Complete direct ElmComp runtime block.
        :param child_block_by_slot_id: Owned children keyed by exact slot FID.
        :param graphical_slot_ids: Slots materialized from BlkRef/BlkSig trees.
        :return: None.
        """
        self.root_block = root_block
        self.child_block_by_slot_id = child_block_by_slot_id
        self.graphical_slot_ids = graphical_slot_ids


class DgsStatementReportEntry:
    """
    One line-by-line parsing report entry for a DGS block statement.

    :param index: 1-based statement index.
    :type index: int
    :param statement: Original normalized statement.
    :type statement: str
    :param kind: Classified statement kind.
    :type kind: str
    :param lhs: Left-hand side symbol when available.
    :type lhs: str | None
    :param status: Parsing result status.
    :type status: str
    :param detail: Additional explanation.
    :type detail: str
    """

    __slots__ = ("index", "statement", "kind", "lhs", "status", "detail")

    def __init__(
        self,
        index: int,
        statement: str,
        kind: str,
        lhs: str | None,
        status: str,
        detail: str,
    ) -> None:
        self.index = index
        self.statement = statement
        self.kind = kind
        self.lhs = lhs
        self.status = status
        self.detail = detail


class DgsStandaloneBlockOccurrence:
    """
    One standalone block occurrence extracted from a DGS catalog.
    """

    __slots__ = ("blkref_id", "typ_id", "blkdef_name", "sample_display_name", "connected")

    def __init__(self,
                 blkref_id: str,
                 typ_id: str,
                 blkdef_name: str,
                 sample_display_name: str,
                 connected: bool) -> None:
        """
        Store one standalone block occurrence.

        :param blkref_id: BlkRef identifier.
        :param typ_id: Referenced BlkDef identifier.
        :param blkdef_name: Referenced BlkDef display name.
        :param sample_display_name: Human-facing occurrence label.
        :param connected: Whether the occurrence belongs to a connected graphical component.
        :returns: None.
        """
        self.blkref_id = blkref_id
        self.typ_id = typ_id
        self.blkdef_name = blkdef_name
        self.sample_display_name = sample_display_name
        self.connected = connected


class DgsStandaloneBlockCatalogEntry:
    """
    Aggregated standalone block catalog entry built from DGS occurrences.
    """

    __slots__ = (
        "typ_id",
        "blkdef_name",
        "sample_display_name",
        "occurrence_count",
        "isolated_occurrence_count",
        "connected_occurrence_count",
        "unsupported_lines",
        "build_error",
    )

    def __init__(self,
                 typ_id: str,
                 blkdef_name: str,
                 sample_display_name: str,
                 occurrence_count: int,
                 isolated_occurrence_count: int,
                 connected_occurrence_count: int,
                 unsupported_lines: List[str],
                 build_error: str | None) -> None:
        """
        Store one aggregated standalone block catalog entry.

        :param typ_id: Referenced BlkDef identifier.
        :param blkdef_name: Referenced BlkDef display name.
        :param sample_display_name: Representative human-facing occurrence label.
        :param occurrence_count: Number of occurrences included in this view.
        :param isolated_occurrence_count: Number of isolated occurrences included in this view.
        :param connected_occurrence_count: Number of connected occurrences included in this view.
        :param unsupported_lines: Unsupported DGS source statements.
        :param build_error: Build error when materialization fails.
        :returns: None.
        """
        self.typ_id = typ_id
        self.blkdef_name = blkdef_name
        self.sample_display_name = sample_display_name
        self.occurrence_count = occurrence_count
        self.isolated_occurrence_count = isolated_occurrence_count
        self.connected_occurrence_count = connected_occurrence_count
        self.unsupported_lines = unsupported_lines
        self.build_error = build_error


def _graph_to_serializable(graph: Dict[str, Set[str]]) -> Dict[str, List[str]]:
    serializable_graph: Dict[str, List[str]] = dict()
    key: str
    values: Set[str]
    for key, values in graph.items():
        serializable_graph[key] = sorted(values)
    return serializable_graph


def _append_to_string_set_map(mapping: Dict[str, Set[str]], key: str, value: str) -> None:
    """
    Append one string value into one ``dict[str, set[str]]`` map.

    :param mapping: Target mapping.
    :param key: Mapping key.
    :param value: Value to append.
    :returns: None.
    """
    if key not in mapping:
        mapping[key] = set()
    else:
        pass
    mapping[key].add(value)


def _filter_graph_edges_to_node_ids(graph: Dict[str, Set[str]], node_ids: Set[str]) -> Dict[str, Set[str]]:
    """
    Filter one graph so every adjacency set only contains nodes inside ``node_ids``.

    :param graph: Source graph.
    :param node_ids: Allowed node identifiers.
    :returns: Filtered graph.
    """
    filtered_graph: Dict[str, Set[str]] = dict()
    node_id: str
    for node_id in node_ids:
        filtered_graph[node_id] = set()
        dst: str
        for dst in graph.get(node_id, set()):
            if dst in node_ids:
                filtered_graph[node_id].add(dst)
            else:
                pass
    return filtered_graph


def _build_reverse_neighbor_subset(graph: Dict[str, Set[str]], node_id: str, node_ids: Set[str]) -> Set[str]:
    """
    Build the reverse-neighbor subset of one node restricted to ``node_ids``.

    :param graph: Source reverse graph.
    :param node_id: Node identifier.
    :param node_ids: Allowed node identifiers.
    :returns: Filtered reverse-neighbor set.
    """
    filtered_neighbors: Set[str] = set()
    src: str
    for src in graph.get(node_id, set()):
        if src in node_ids:
            filtered_neighbors.add(src)
        else:
            pass
    return filtered_neighbors


def _build_expr_signal_name_set(expr: Expr) -> Set[str]:
    """
    Build the set of variable names referenced by one expression.

    :param expr: Symbolic expression.
    :returns: Referenced variable names.
    """
    names: Set[str] = set()
    var: Var
    for var in expr.get_vars():
        names.add(var.name)
    return names


def _build_name_to_var_map(vars_list: List[Var]) -> Dict[str, Var]:
    """
    Build a variable lookup by name.

    :param vars_list: Variable list.
    :returns: Variable lookup by name.
    """
    mapping: Dict[str, Var] = dict()
    var: Var
    for var in vars_list:
        mapping[var.name] = var
    return mapping


def _collect_uid_set_from_blocks(block: Block, attribute_name: str) -> Set[int]:
    """
    Collect the uid set of one block variable attribute across one block tree.

    :param block: Root block.
    :param attribute_name: Block attribute name containing variables.
    :returns: Variable uid set.
    """
    uid_set: Set[int] = set()
    item: Block
    vars_list: List[Var]
    var: Var
    for item in _iter_blocks_recursive(block):
        if attribute_name == "state_vars":
            vars_list = item.state_vars
        elif attribute_name == "diff_vars":
            vars_list = item.diff_vars
        else:
            raise ValueError(f"Unsupported block variable attribute '{attribute_name}'")
        for var in vars_list:
            uid_set.add(var.uid)
    return uid_set


def _collect_parameter_uid_set_from_blocks(block: Block) -> Set[int]:
    """
    Collect the uid set of parameter variables across one block tree.

    :param block: Root block.
    :returns: Parameter variable uid set.
    """
    uid_set: Set[int] = set()
    item: Block
    var: Var
    for item in _iter_blocks_recursive(block):
        for var in item.event_dict.keys():
            uid_set.add(var.uid)
        for var in item.parameters.keys():
            uid_set.add(var.uid)
    return uid_set


def _build_filtered_neighbor_set(graph: Dict[str, Set[str]], node_id: str, node_ids: Set[str]) -> Set[str]:
    """
    Build the neighbor subset of one node restricted to ``node_ids``.

    :param graph: Source graph.
    :param node_id: Node identifier.
    :param node_ids: Allowed node identifiers.
    :returns: Filtered neighbor set.
    """
    filtered_neighbors: Set[str] = set()
    dst: str
    for dst in graph.get(node_id, set()):
        if dst in node_ids:
            filtered_neighbors.add(dst)
        else:
            pass
    return filtered_neighbors


def _build_instance_entry_lookup_by_slot_name(entries: List[ElmCompInstanceEntry]) -> Dict[str, ElmCompInstanceEntry]:
    """
    Build the direct-instance lookup by slot name.

    :param entries: Direct instance entries.
    :returns: Instance lookup by slot name.
    """
    mapping: Dict[str, ElmCompInstanceEntry] = dict()
    entry: ElmCompInstanceEntry
    for entry in entries:
        if entry.slot_name is not None:
            mapping[entry.slot_name] = entry
        else:
            pass
    return mapping


def _build_instance_entry_lookup_by_type_name(entries: List[ElmCompInstanceEntry]) -> Dict[str, ElmCompInstanceEntry]:
    """
    Build the direct-instance lookup by type name.

    :param entries: Direct instance entries.
    :returns: Instance lookup by type name.
    """
    mapping: Dict[str, ElmCompInstanceEntry] = dict()
    entry: ElmCompInstanceEntry
    for entry in entries:
        if entry.type_name is not None:
            mapping[entry.type_name] = entry
        else:
            pass
    return mapping


def _build_instance_entry_lookup_by_element_name(entries: List[ElmCompInstanceEntry]) -> Dict[str, ElmCompInstanceEntry]:
    """
    Build the direct-instance lookup by instantiated element display name.

    :param entries: Direct instance entries.
    :return: Instance lookup by element display name.
    """
    mapping: Dict[str, ElmCompInstanceEntry] = dict()
    entry: ElmCompInstanceEntry

    for entry in entries:
        if entry.element_name is None:
            pass
        else:
            mapping[entry.element_name] = entry

    return mapping


def _disjoint_set_find(parent: Dict[str, str], name: str) -> str:
    """
    Return the representative of one disjoint-set name.

    :param parent: Disjoint-set parent map.
    :param name: Queried element name.
    :returns: Representative name.
    """
    if name not in parent:
        parent[name] = name
    else:
        pass

    root: str = parent[name]
    while root != parent[root]:
        parent[root] = parent[parent[root]]
        root = parent[root]

    return root


def _disjoint_set_union(parent: Dict[str, str], left_name: str, right_name: str) -> None:
    """
    Union two disjoint-set names.

    :param parent: Disjoint-set parent map.
    :param left_name: Left element name.
    :param right_name: Right element name.
    :returns: None.
    """
    left_root: str = _disjoint_set_find(parent, left_name)
    right_root: str = _disjoint_set_find(parent, right_name)

    if left_root != right_root:
        parent[right_root] = left_root
    else:
        pass


def _normalize_graph_signal_name(name: str) -> str:
    text = name.strip().strip('"')
    text = re.sub(r'\(\d+\)$', '', text).strip()
    return text


def _normalize_dgs_pointer_id(pointer_value: object | None) -> str:
    """Normalize a parsed DGS pointer without turning ``None`` into a FID.

    :param pointer_value: Parsed pointer value or a DGS empty placeholder.
    :return: Trimmed FID, or an empty string when no object is referenced.
    """
    if pointer_value is None:
        pointer_id: str = ""
    elif isinstance(pointer_value, str):
        stripped_pointer_id: str = pointer_value.strip()
        if stripped_pointer_id in {"", "*"}:
            pointer_id = ""
        else:
            pointer_id = stripped_pointer_id
    else:
        pointer_id = str(pointer_value).strip()
    return pointer_id


def _normalize_graph_interface_stem(name: str) -> str:
    """Normalize a graphical boundary label for split-wire matching.

    PowerFactory appends underscores to private wire segments connected to a
    public macro port, for example ``EFD_`` feeding ``EFD``. The underscore is
    stripped only for boundary-candidate comparison; internal graph signal
    identities remain untouched.

    :param name: Raw or already normalized graphical signal label.
    :return: Boundary-comparison stem.
    """
    normalized_name: str = _normalize_graph_signal_name(name=name)
    return normalized_name.rstrip("_")


def _iter_blocks_recursive(block: Block) -> Iterable[Block]:
    """Yield a block tree depth-first without consuming call-stack depth.

    :param block: Root symbolic block.
    :return: Depth-first block iterator.
    """
    traversal_stack: List[Block] = list([block])
    visited_block_identities: Set[int] = set()

    while len(traversal_stack) > 0:
        current_block: Block = traversal_stack.pop()
        current_identity: int = id(current_block)
        if current_identity in visited_block_identities:
            pass
        else:
            visited_block_identities.add(current_identity)
            yield current_block
            child_block: Block
            for child_block in reversed(current_block.children):
                traversal_stack.append(child_block)


def _make_identifier_map(
        block: Block,
        vars_by_uid: Dict[int, Var] | None = None,
) -> Dict[int, str]:
    """
    Allocate globally unique Python identifiers for one symbolic block tree.

    A per-base counter is not sufficient because a semantic name such as
    ``x_1`` can collide with the suffix allocated for the second ``x``.  The
    generated humanized module uses one Python namespace, so every accepted
    candidate must be reserved globally before the next variable is handled.

    :param block: Symbolic block tree to inspect.
    :param vars_by_uid: Optional variables already collected from the complete
        tree. Callers outside the DGS emitter may omit them.
    :return: Python identifier indexed by symbolic variable uid.
    """
    if vars_by_uid is None:
        collected_vars_by_uid: Dict[int, Var] = dict()
        collected_consts_by_uid: Dict[int, Const] = dict()
        _collect_block_vars_recursive(
            block=block,
            vars_out=collected_vars_by_uid,
            consts_out=collected_consts_by_uid,
        )
    else:
        collected_vars_by_uid = vars_by_uid

    # A reloaded humanized module carries the exact alias selected when it was
    # emitted. Preserve that alias-to-variable identity because several valid
    # PowerFactory composites contain distinct signals with the same semantic
    # name. Re-numbering equal names from traversal order can silently swap
    # controller ports while still producing syntactically valid Python.
    raw_persisted_mapping: object | None = block.__dict__.get(
        "dgs_persisted_identifier_by_uid",
        None,
    )
    if isinstance(raw_persisted_mapping, dict):
        persisted_mapping: Dict[int, str] = dict()
        persisted_mapping_valid: bool = True
        raw_uid: object
        raw_identifier: object
        for raw_uid, raw_identifier in raw_persisted_mapping.items():
            if isinstance(raw_uid, int) and isinstance(raw_identifier, str):
                persisted_mapping[raw_uid] = raw_identifier
            else:
                persisted_mapping_valid = False

        persisted_identifiers: Set[str] = set(persisted_mapping.values())
        mapping_covers_surface: bool = (
            set(persisted_mapping.keys()) == set(collected_vars_by_uid.keys())
            and len(persisted_identifiers) == len(persisted_mapping)
        )
        if persisted_mapping_valid and mapping_covers_surface:
            return persisted_mapping
        else:
            pass
    else:
        pass

    next_suffix_by_base: Dict[str, int] = dict()
    used_identifiers: Set[str] = set()
    mapping: Dict[int, str] = dict()
    var_obj: Var
    for var_obj in sorted(collected_vars_by_uid.values(), key=_var_name_sort_key):
        base_identifier: str = _safe_name(var_obj.name)
        suffix_index: int = next_suffix_by_base.get(base_identifier, 0)
        if suffix_index == 0:
            candidate_identifier: str = base_identifier
        else:
            candidate_identifier = f"{base_identifier}_{suffix_index}"

        # Resolve collisions against every prior semantic base and every prior
        # generated suffix.  This is the key invariant of the executable
        # humanized catalogue namespace.
        while candidate_identifier in used_identifiers:
            suffix_index += 1
            candidate_identifier = f"{base_identifier}_{suffix_index}"

        used_identifiers.add(candidate_identifier)
        next_suffix_by_base[base_identifier] = suffix_index + 1
        mapping[var_obj.uid] = candidate_identifier

    return mapping


def _expr_to_python_iterative(
        expr: Expr,
        identifier_map: Dict[int, str],
        natural_constants: bool,
) -> str:
    """Emit executable Python for one expression with an explicit stack.

    :param expr: Symbolic expression root.
    :param identifier_map: Python identifiers indexed by symbolic UID.
    :param natural_constants: Emit plain scalar constants when ``True``.
    :return: Executable human-readable Python expression.
    """
    rendered_by_identity_and_mode: Dict[Tuple[int, bool], str] = dict()
    traversal_stack: List[Tuple[Expr, bool, bool]] = list([
        (expr, False, natural_constants),
    ])

    while len(traversal_stack) > 0:
        current_expr, children_are_ready, current_natural_mode = (
            traversal_stack.pop()
        )
        current_key: Tuple[int, bool] = (
            id(current_expr),
            current_natural_mode,
        )

        if current_key in rendered_by_identity_and_mode:
            pass
        elif isinstance(current_expr, Var):
            rendered_by_identity_and_mode[current_key] = identifier_map[
                current_expr.uid
            ]
        elif isinstance(current_expr, Const):
            if current_natural_mode:
                rendered_by_identity_and_mode[current_key] = repr(
                    current_expr.value
                )
            else:
                rendered_by_identity_and_mode[current_key] = (
                    f"sym.Const({repr(current_expr.value)})"
                )
        elif children_are_ready:
            if isinstance(current_expr, Func2):
                first_key: Tuple[int, bool] = (
                    id(current_expr.arg1),
                    current_natural_mode,
                )
                second_key: Tuple[int, bool] = (
                    id(current_expr.arg2),
                    current_natural_mode,
                )
                rendered_by_identity_and_mode[current_key] = (
                    f"sym.{current_expr.name}("
                    f"{rendered_by_identity_and_mode[first_key]}, "
                    f"{rendered_by_identity_and_mode[second_key]})"
                )
            elif isinstance(current_expr, BinOp):
                left_key: Tuple[int, bool] = (
                    id(current_expr.left),
                    current_natural_mode,
                )
                right_key: Tuple[int, bool] = (
                    id(current_expr.right),
                    current_natural_mode,
                )
                rendered_by_identity_and_mode[current_key] = (
                    f"({rendered_by_identity_and_mode[left_key]} "
                    f"{current_expr.op} "
                    f"{rendered_by_identity_and_mode[right_key]})"
                )
            elif isinstance(current_expr, UnOp):
                operand_key: Tuple[int, bool] = (
                    id(current_expr.operand),
                    False,
                )
                rendered_by_identity_and_mode[current_key] = (
                    f"({current_expr.op}"
                    f"{rendered_by_identity_and_mode[operand_key]})"
                )
            elif isinstance(current_expr, Func):
                argument_key: Tuple[int, bool] = (
                    id(current_expr.arg),
                    current_natural_mode,
                )
                rendered_by_identity_and_mode[current_key] = (
                    f"sym.{current_expr.op}("
                    f"{rendered_by_identity_and_mode[argument_key]})"
                )
            else:
                raise TypeError(
                    "Unsupported expression type for Python export: "
                    f"{type(current_expr).__name__}"
                )
        else:
            traversal_stack.append(
                (current_expr, True, current_natural_mode)
            )
            if isinstance(current_expr, Func2):
                traversal_stack.append(
                    (current_expr.arg2, False, current_natural_mode)
                )
                traversal_stack.append(
                    (current_expr.arg1, False, current_natural_mode)
                )
            elif isinstance(current_expr, BinOp):
                traversal_stack.append(
                    (current_expr.right, False, current_natural_mode)
                )
                traversal_stack.append(
                    (current_expr.left, False, current_natural_mode)
                )
            elif isinstance(current_expr, UnOp):
                # Natural export intentionally preserves a unary subtree as
                # explicit symbolic constants, matching the historical text.
                traversal_stack.append((current_expr.operand, False, False))
            elif isinstance(current_expr, Func):
                traversal_stack.append(
                    (current_expr.arg, False, current_natural_mode)
                )
            else:
                raise TypeError(
                    "Unsupported expression type for Python export: "
                    f"{type(current_expr).__name__}"
                )

    return rendered_by_identity_and_mode[(id(expr), natural_constants)]


def _expr_to_python(expr: Expr, identifier_map: Dict[int, str]) -> str:
    """Emit explicit-symbolic Python without recursion.

    :param expr: Symbolic expression root.
    :param identifier_map: Python identifiers indexed by symbolic UID.
    :return: Executable Python expression.
    """
    return _expr_to_python_iterative(
        expr=expr,
        identifier_map=identifier_map,
        natural_constants=False,
    )


def _const_or_expr_to_python(value: Expr | Const, identifier_map: Dict[int, str]) -> str:
    if isinstance(value, Const):
        return f"vf.add_const({repr(value.value)}, name={repr(value.name)})"
    return _expr_to_python(value, identifier_map)


def _collect_left_associative_operands(
        expr: Expr,
        operator: str,
) -> List[Expr]:
    """Collect one left-associated binary chain without changing its tree.

    Python evaluates ``+``, ``-``, ``*`` and ``/`` from left to right. A tree
    such as ``((a + b) + c)`` can therefore be printed as three aligned terms
    while reconstructing the same symbolic node order. Right-nested branches
    remain individual operands and retain their explicit parentheses.

    :param expr: Candidate binary expression root.
    :param operator: Left-associative operator being expanded.
    :return: Ordered operands that reproduce the original expression tree.
    """
    operands: List[Expr] = list()
    pending_left_nodes: List[Expr] = list()
    current_expr: Expr = expr

    while isinstance(current_expr, BinOp) and current_expr.op == operator:
        pending_left_nodes.append(current_expr.right)
        current_expr = current_expr.left
    else:
        pass

    operands.append(current_expr)
    pending_index: int
    for pending_index in range(len(pending_left_nodes) - 1, -1, -1):
        operands.append(pending_left_nodes[pending_index])
    else:
        pass
    return operands


def _expr_to_humanized_python_lines(
        expr: Expr,
        identifier_map: Dict[int, str],
        indentation: int,
        maximum_line_length: int = 112,
) -> List[str]:
    """Render one symbolic expression as width-bounded executable Python.

    Short equations retain the compact standard-template style. Large DGS
    equations are expanded along their symbolic tree so OEM reviewers can
    follow every operation without horizontal scrolling. Parentheses make
    the inserted newlines semantically neutral for Python and preserve the
    exact symbolic round-trip.

    :param expr: Symbolic expression to serialize.
    :param identifier_map: Python identifier indexed by symbolic variable uid.
    :param indentation: Number of leading spaces for the expression root.
    :param maximum_line_length: Preferred maximum generated source-line width.
    :return: Executable Python source lines including leading indentation.
    """
    indentation_text: str = " " * indentation
    compact_text: str = _expr_to_python(expr=expr, identifier_map=identifier_map)
    compact_line_fits: bool = indentation + len(compact_text) <= maximum_line_length

    if compact_line_fits:
        result_lines: List[str] = list((indentation_text + compact_text,))
    elif isinstance(expr, BinOp):
        # Binary operations are written one operand per visual branch. This
        # mirrors the algebraic tree and retains explicit grouping.
        child_indentation: int = indentation + 4 if indentation < 48 else 48
        result_lines = list((indentation_text + "(",))
        left_associative_operator: bool = expr.op in list(("+", "-", "*", "/"))
        if left_associative_operator:
            operands: List[Expr] = _collect_left_associative_operands(
                expr=expr,
                operator=expr.op,
            )
        else:
            operands = list((expr.left, expr.right))

        first_operand_lines: List[str] = _expr_to_humanized_python_lines(
            expr=operands[0],
            identifier_map=identifier_map,
            indentation=child_indentation,
            maximum_line_length=maximum_line_length,
        )
        result_lines.extend(first_operand_lines)
        operand_index: int
        for operand_index in range(1, len(operands)):
            operand_lines: List[str] = _expr_to_humanized_python_lines(
                expr=operands[operand_index],
                identifier_map=identifier_map,
                indentation=child_indentation,
                maximum_line_length=maximum_line_length,
            )
            operand_lines[0] = (
                (" " * child_indentation)
                + str(expr.op)
                + " "
                + operand_lines[0].lstrip()
            )
            result_lines.extend(operand_lines)
        else:
            pass
        result_lines.append(indentation_text + ")")
    elif isinstance(expr, Func2):
        # Two-argument symbolic functions use conventional Python call
        # formatting, keeping each potentially complex argument independent.
        child_indentation = indentation + 4 if indentation < 48 else 48
        first_argument_lines: List[str] = _expr_to_humanized_python_lines(
            expr=expr.arg1,
            identifier_map=identifier_map,
            indentation=child_indentation,
            maximum_line_length=maximum_line_length,
        )
        second_argument_lines: List[str] = _expr_to_humanized_python_lines(
            expr=expr.arg2,
            identifier_map=identifier_map,
            indentation=child_indentation,
            maximum_line_length=maximum_line_length,
        )
        first_argument_lines[-1] = first_argument_lines[-1] + ","
        second_argument_lines[-1] = second_argument_lines[-1] + ","
        result_lines = list((indentation_text + f"sym.{expr.name}(",))
        result_lines.extend(first_argument_lines)
        result_lines.extend(second_argument_lines)
        result_lines.append(indentation_text + ")")
    elif isinstance(expr, Func):
        # Unary symbolic functions follow the same readable call layout.
        child_indentation = indentation + 4 if indentation < 48 else 48
        argument_lines: List[str] = _expr_to_humanized_python_lines(
            expr=expr.arg,
            identifier_map=identifier_map,
            indentation=child_indentation,
            maximum_line_length=maximum_line_length,
        )
        argument_lines[-1] = argument_lines[-1] + ","
        result_lines = list((indentation_text + f"sym.{expr.op}(",))
        result_lines.extend(argument_lines)
        result_lines.append(indentation_text + ")")
    elif isinstance(expr, UnOp):
        # Keep unary operations explicitly symbolic; folding a negative
        # constant in Python would change the reconstructed expression tree.
        child_indentation = indentation + 4 if indentation < 48 else 48
        operand_lines: List[str] = _expr_to_humanized_python_lines(
            expr=expr.operand,
            identifier_map=identifier_map,
            indentation=child_indentation,
            maximum_line_length=maximum_line_length,
        )
        operand_lines[0] = (
            (" " * child_indentation)
            + str(expr.op)
            + operand_lines[0].lstrip()
        )
        result_lines = list((indentation_text + "(",))
        result_lines.extend(operand_lines)
        result_lines.append(indentation_text + ")")
    else:
        # Variable names are intentionally never truncated because they carry
        # the humanized PowerFactory signal identity used during debugging.
        result_lines = list((indentation_text + compact_text,))

    return result_lines


def _append_humanized_expression(
        lines: List[str],
        prefix: str,
        expr: Expr | Const,
        identifier_map: Dict[int, str],
        indentation: int,
        suffix: str = ",",
        maximum_line_length: int = 112,
) -> None:
    """Append one compact or expanded expression to generated source code.

    :param lines: Generated module lines updated in place.
    :param prefix: Source text placed before the expression, such as a mapping key.
    :param expr: Symbolic value to serialize.
    :param identifier_map: Python identifier indexed by symbolic variable uid.
    :param indentation: Number of spaces before the prefix and expression root.
    :param suffix: Source text appended after the expression.
    :param maximum_line_length: Preferred maximum generated source-line width.
    :return: None.
    """
    compact_text: str = _const_or_expr_to_python(
        value=expr,
        identifier_map=identifier_map,
    )
    compact_line_length: int = indentation + len(prefix) + len(compact_text) + len(suffix)

    if compact_line_length <= maximum_line_length or isinstance(expr, Const):
        lines.append((" " * indentation) + prefix + compact_text + suffix)
    else:
        # Align the expression root with its mapping/list indentation. The
        # prefix remains on the opening line and subsequent branches use the
        # formatter's four-space structural indentation.
        expression_lines: List[str] = _expr_to_humanized_python_lines(
            expr=expr,
            identifier_map=identifier_map,
            indentation=indentation,
            maximum_line_length=maximum_line_length,
        )
        expression_lines[0] = (
            (" " * indentation)
            + prefix
            + expression_lines[0].lstrip()
        )
        expression_lines[-1] = expression_lines[-1] + suffix
        lines.extend(expression_lines)


def _expr_like_to_humanized_python_lines(
        expr: Expr | Comparison | float | int | bool,
        identifier_map: Dict[int, str],
        indentation: int,
        maximum_line_length: int = 112,
) -> List[str]:
    """Render an expression-like procedural argument as readable Python.

    :param expr: Symbolic expression, comparison or primitive argument.
    :param identifier_map: Python identifier indexed by symbolic variable uid.
    :param indentation: Number of leading spaces for the argument root.
    :param maximum_line_length: Preferred maximum generated source-line width.
    :return: Executable Python lines including leading indentation.
    """
    indentation_text: str = " " * indentation
    compact_text: str = _expr_like_to_python(
        expr=expr,
        identifier_map=identifier_map,
    )
    compact_line_fits: bool = indentation + len(compact_text) <= maximum_line_length

    if compact_line_fits:
        result_lines: List[str] = list((indentation_text + compact_text,))
    elif isinstance(expr, Comparison):
        comparison_name_by_operator: Dict[CmpOp, str] = dict()
        comparison_name_by_operator[CmpOp.EQ] = "EQ"
        comparison_name_by_operator[CmpOp.LE] = "LE"
        comparison_name_by_operator[CmpOp.GE] = "GE"
        comparison_name_by_operator[CmpOp.LT] = "LT"
        comparison_name_by_operator[CmpOp.GT] = "GT"
        child_indentation: int = indentation + 4 if indentation < 48 else 48
        lhs_lines: List[str] = _expr_like_to_humanized_python_lines(
            expr=expr.lhs,
            identifier_map=identifier_map,
            indentation=child_indentation,
            maximum_line_length=maximum_line_length,
        )
        lhs_lines[0] = (
            (" " * child_indentation)
            + "lhs="
            + lhs_lines[0].lstrip()
        )
        lhs_lines[-1] = lhs_lines[-1] + ","
        rhs_lines: List[str] = _expr_like_to_humanized_python_lines(
            expr=expr.rhs,
            identifier_map=identifier_map,
            indentation=child_indentation,
            maximum_line_length=maximum_line_length,
        )
        rhs_lines[0] = (
            (" " * child_indentation)
            + "rhs="
            + rhs_lines[0].lstrip()
        )
        rhs_lines[-1] = rhs_lines[-1] + ","
        result_lines = list((indentation_text + "sym.Comparison(",))
        result_lines.extend(lhs_lines)
        result_lines.append(
            (" " * child_indentation)
            + "op=sym.CmpOp."
            + comparison_name_by_operator[expr.op]
            + ","
        )
        result_lines.extend(rhs_lines)
        result_lines.append(indentation_text + ")")
    else:
        if isinstance(expr, Expr):
            result_lines = _expr_to_humanized_python_lines(
                expr=expr,
                identifier_map=identifier_map,
                indentation=indentation,
                maximum_line_length=maximum_line_length,
            )
        else:
            result_lines = list((indentation_text + compact_text,))
    return result_lines


def _append_humanized_expr_like_argument(
        lines: List[str],
        prefix: str,
        expr: Expr | Comparison | float | int | bool,
        identifier_map: Dict[int, str],
        indentation: int,
        suffix: str = ",",
        maximum_line_length: int = 112,
) -> None:
    """Append one formatted procedural-function argument.

    :param lines: Generated module lines updated in place.
    :param prefix: Keyword prefix or empty text for a positional argument.
    :param expr: Symbolic expression, comparison or primitive argument.
    :param identifier_map: Python identifier indexed by symbolic variable uid.
    :param indentation: Number of spaces before the argument.
    :param suffix: Source text appended after the argument.
    :param maximum_line_length: Preferred maximum generated source-line width.
    :return: None.
    """
    argument_lines: List[str] = _expr_like_to_humanized_python_lines(
        expr=expr,
        identifier_map=identifier_map,
        indentation=indentation,
        maximum_line_length=maximum_line_length,
    )
    argument_lines[0] = (
        (" " * indentation)
        + prefix
        + argument_lines[0].lstrip()
    )
    argument_lines[-1] = argument_lines[-1] + suffix
    lines.extend(argument_lines)


def _metadata_value_to_compact_python(value: object) -> str:
    """Serialize primitive nested metadata with explicit Python constructors.

    :param value: Primitive, list or dictionary metadata value.
    :return: Compact executable Python expression.
    """
    if isinstance(value, list):
        item_expressions: List[str] = list()
        item: object
        for item in value:
            item_expressions.append(_metadata_value_to_compact_python(value=item))
        else:
            pass
        result: str = "list([" + ", ".join(item_expressions) + "])"
    elif isinstance(value, dict):
        pair_expressions: List[str] = list()
        key: object
        item_value: object
        for key, item_value in value.items():
            pair_expressions.append(
                "("
                + _metadata_value_to_compact_python(value=key)
                + ", "
                + _metadata_value_to_compact_python(value=item_value)
                + ")"
            )
        else:
            pass
        result = "dict([" + ", ".join(pair_expressions) + "])"
    else:
        if value is None or isinstance(value, (str, int, float, bool)):
            result = repr(value)
        else:
            # Adapter metadata is primitive by contract. Unexpected objects
            # remain inspectable strings instead of executable object magic.
            result = repr(str(value))
    return result


def _metadata_value_to_humanized_python_lines(
        value: object,
        indentation: int,
        maximum_line_length: int = 112,
) -> List[str]:
    """Render nested DGS metadata as readable executable Python lines.

    :param value: Primitive, list or dictionary metadata value.
    :param indentation: Number of leading spaces for the value root.
    :param maximum_line_length: Preferred maximum generated source-line width.
    :return: Executable Python lines including leading indentation.
    """
    indentation_text: str = " " * indentation
    compact_text: str = _metadata_value_to_compact_python(value=value)
    compact_line_fits: bool = indentation + len(compact_text) <= maximum_line_length

    if compact_line_fits:
        result_lines: List[str] = list((indentation_text + compact_text,))
    elif isinstance(value, list):
        # Lists expose one logical metadata record per line group, making
        # equipment-slot provenance directly reviewable in generated modules.
        child_indentation: int = indentation + 4
        result_lines = list((indentation_text + "list([",))
        item: object
        for item in value:
            item_lines: List[str] = _metadata_value_to_humanized_python_lines(
                value=item,
                indentation=child_indentation,
                maximum_line_length=maximum_line_length,
            )
            item_lines[-1] = item_lines[-1] + ","
            result_lines.extend(item_lines)
        else:
            pass
        result_lines.append(indentation_text + "])")
    elif isinstance(value, dict):
        # Dictionary pairs use explicit tuple records so source order and
        # constructor intent stay evident to reviewers and static analysis.
        pair_indentation: int = indentation + 4
        pair_value_indentation: int = indentation + 8
        result_lines = list((indentation_text + "dict([",))
        key: object
        item_value: object
        for key, item_value in value.items():
            result_lines.append((" " * pair_indentation) + "(")
            key_lines: List[str] = _metadata_value_to_humanized_python_lines(
                value=key,
                indentation=pair_value_indentation,
                maximum_line_length=maximum_line_length,
            )
            key_lines[-1] = key_lines[-1] + ","
            result_lines.extend(key_lines)
            value_lines: List[str] = _metadata_value_to_humanized_python_lines(
                value=item_value,
                indentation=pair_value_indentation,
                maximum_line_length=maximum_line_length,
            )
            value_lines[-1] = value_lines[-1] + ","
            result_lines.extend(value_lines)
            result_lines.append((" " * pair_indentation) + "),")
        else:
            pass
        result_lines.append(indentation_text + "])")
    else:
        # Long primitive values are retained intact because truncation would
        # corrupt exact DGS identifiers or signal names.
        result_lines = list((indentation_text + compact_text,))
    return result_lines


def _append_humanized_metadata_assignment(
        lines: List[str],
        prefix: str,
        value: object,
        indentation: int,
        maximum_line_length: int = 112,
) -> None:
    """Append one typed assignment for compact or expanded DGS metadata.

    :param lines: Generated module lines updated in place.
    :param prefix: Assignment text placed before the metadata value.
    :param value: Primitive nested metadata value.
    :param indentation: Number of spaces before the assignment.
    :param maximum_line_length: Preferred maximum generated source-line width.
    :return: None.
    """
    compact_text: str = _metadata_value_to_compact_python(value=value)
    compact_line_length: int = indentation + len(prefix) + len(compact_text)

    if compact_line_length <= maximum_line_length:
        lines.append((" " * indentation) + prefix + compact_text)
    else:
        # An outer grouping lets the assignment span lines while the nested
        # constructor remains standalone, aligned and executable.
        lines.append((" " * indentation) + prefix + "(")
        value_lines: List[str] = _metadata_value_to_humanized_python_lines(
            value=value,
            indentation=indentation + 4,
            maximum_line_length=maximum_line_length,
        )
        lines.extend(value_lines)
        lines.append((" " * indentation) + ")")


def _append_humanized_identifier_list(
        lines: List[str],
        prefix: str,
        identifiers: List[str],
        indentation: int,
        suffix: str,
        maximum_line_length: int = 112,
) -> None:
    """Append a compact or vertical list of executable identifiers.

    :param lines: Generated module lines updated in place.
    :param prefix: Assignment or constructor-argument text before the list.
    :param identifiers: Ordered Python identifiers retained without quoting.
    :param indentation: Number of spaces before the prefix.
    :param suffix: Source text appended after the closing bracket.
    :param maximum_line_length: Preferred maximum generated source-line width.
    :return: None.
    """
    compact_text: str = "[" + ", ".join(identifiers) + "]"
    compact_line_length: int = indentation + len(prefix) + len(compact_text) + len(suffix)

    if compact_line_length <= maximum_line_length:
        lines.append((" " * indentation) + prefix + compact_text + suffix)
    else:
        # Long model interfaces are much easier to diff when each signal owns
        # one stable line in its original source order.
        lines.append((" " * indentation) + prefix + "[")
        identifier: str
        for identifier in identifiers:
            lines.append((" " * (indentation + 4)) + identifier + ",")
        else:
            pass
        lines.append((" " * indentation) + "]" + suffix)


def _expr_to_python_natural(expr: Expr, identifier_map: Dict[int, str]) -> str:
    """Emit natural-scalar Python without recursion.

    :param expr: Symbolic expression root.
    :param identifier_map: Python identifiers indexed by symbolic UID.
    :return: Executable Python expression.
    """
    return _expr_to_python_iterative(
        expr=expr,
        identifier_map=identifier_map,
        natural_constants=True,
    )


def _expr_like_to_python(
        expr: Expr | Comparison | float | int | bool,
        identifier_map: Dict[int, str],
) -> str:
    if isinstance(expr, Comparison):
        cmp_name_by_op: Dict[CmpOp, str] = dict()
        cmp_name_by_op[CmpOp.EQ] = "EQ"
        cmp_name_by_op[CmpOp.LE] = "LE"
        cmp_name_by_op[CmpOp.GE] = "GE"
        cmp_name_by_op[CmpOp.LT] = "LT"
        cmp_name_by_op[CmpOp.GT] = "GT"

        rhs: str
        if isinstance(expr.rhs, UnOp):
            # Preserve unary symbolic constants as ``-sym.Const(...)``.  Plain
            # ``(-99999.0)`` is executed by Python as a scalar and would change
            # the symbolic tree after loading the humanized template.
            rhs = _expr_to_python(expr.rhs, identifier_map)
        else:
            if isinstance(expr.rhs, Expr):
                rhs = _expr_to_python_natural(expr.rhs, identifier_map)
            else:
                rhs = repr(expr.rhs)

        lhs: str
        if isinstance(expr.lhs, UnOp):
            lhs = _expr_to_python(expr.lhs, identifier_map)
        else:
            lhs = _expr_to_python_natural(expr.lhs, identifier_map)

        return (
            f"sym.Comparison(lhs={lhs}, "
            f"op=sym.CmpOp.{cmp_name_by_op[expr.op]}, rhs={rhs})"
        )
    else:
        if isinstance(expr, UnOp):
            return _expr_to_python(expr, identifier_map)
        else:
            if isinstance(expr, Expr):
                return _expr_to_python_natural(expr, identifier_map)
            else:
                return repr(expr)


def _iter_block_local_vars(block: Block) -> List[Var]:
    vars_found: List[Var] = list()
    vars_found.extend(block.state_vars)
    vars_found.extend(block.algebraic_vars)
    vars_found.extend(block.diff_vars)
    vars_found.extend(block.in_vars)
    vars_found.extend(block.out_vars)
    vars_found.extend(list(block.event_dict.keys()))
    vars_found.extend(list(block.mode_dict.keys()))
    return vars_found


def _find_local_var_by_name(block: Block, var_name: str) -> Var:
    for var in _iter_block_local_vars(block):
        if var.name == var_name:
            return var
    raise KeyError(f"Variable '{var_name}' not found in block '{block.name}'")


def _procedural_logic_import_names(block: Block) -> List[str]:
    names: Set[str] = set()
    for item in _iter_blocks_recursive(block):
        for logic in item.procedural_logic:
            if isinstance(logic, FixedSampleLogic):
                names.add("selfix")
            elif isinstance(logic, SampledValueLogic):
                if (
                        logic.evaluation_mode
                        == SampledValueEvaluationMode.ImplicitIterate
                ):
                    names.add("sampled_value")
                else:
                    names.add("lastvalue")
            elif isinstance(logic, FlipFlopLogic):
                names.add("flipflop")
            elif isinstance(logic, AnalogFlipFlopLogic):
                names.add("aflipflop")
            elif isinstance(logic, PickupDropoffLogic):
                names.add("picdro")
            elif isinstance(logic, TimeDelayLogic):
                names.add("delay")
            elif isinstance(logic, MovingAverageLogic):
                names.add("movingavg")
            elif isinstance(logic, GradientLimiterLogic):
                names.add("gradlim_const")
            elif isinstance(logic, HardSaturationLogic):
                names.add("hard_saturation")
            elif isinstance(logic, ResetOnRisingEdgeLogic):
                names.add("reset")
            else:
                pass
    return sorted(names)


def _procedural_logic_entry_to_python(logic: ProceduralLogicBase, block: Block, identifier_map: Dict[int, str]) -> str:
    if isinstance(logic, FixedSampleLogic):
        output_var = _find_local_var_by_name(block, logic.output_var_name)
        text = f"selfix({_expr_like_to_python(logic.condition_expr, identifier_map)}, output={identifier_map[output_var.uid]})"
        if logic.name != "" and logic.name != logic.output_var_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        return text

    if isinstance(logic, SampledValueLogic):
        output_var = _find_local_var_by_name(block, logic.output_var_name)
        if (
                logic.evaluation_mode
                == SampledValueEvaluationMode.ImplicitIterate
        ):
            text = f"sampled_value(output={identifier_map[output_var.uid]}, source={_expr_like_to_python(logic.source_expr, identifier_map)})"
        else:
            text = f"lastvalue({_expr_like_to_python(logic.source_expr, identifier_map)}, output={identifier_map[output_var.uid]})"
        if logic.name != "" and logic.name != logic.output_var_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        return text

    if isinstance(logic, FlipFlopLogic):
        output_var = _find_local_var_by_name(block, logic.output_var_name)
        text = (
            f"flipflop({_expr_like_to_python(logic.set_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.reset_expr, identifier_map)}, output={identifier_map[output_var.uid]})"
        )
        if logic.name != "" and logic.name != logic.output_var_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        else:
            pass
        if logic.use_mode_default_at_initialization:
            text = (
                text[:-1]
                + ", use_mode_default_at_initialization=True)"
            )
        else:
            pass
        return text

    if isinstance(logic, AnalogFlipFlopLogic):
        output_var = _find_local_var_by_name(block, logic.output_var_name)
        text = (
            f"aflipflop({_expr_like_to_python(logic.input_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.set_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.reset_expr, identifier_map)}, output={identifier_map[output_var.uid]})"
        )
        if logic.name != "" and logic.name != logic.output_var_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        return text

    if isinstance(logic, PickupDropoffLogic):
        output_var = _find_local_var_by_name(block, logic.output_var_name)
        text = (
            f"picdro({_expr_like_to_python(logic.bool_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.pickup_delay_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.drop_delay_expr, identifier_map)}, output={identifier_map[output_var.uid]})"
        )
        if logic.name != "" and logic.name != logic.output_var_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        return text

    if isinstance(logic, TimeDelayLogic):
        output_var = _find_local_var_by_name(block, logic.output_var_name)
        text = (
            f"delay({_expr_like_to_python(logic.source_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.delay_expr, identifier_map)}, output={identifier_map[output_var.uid]})"
        )
        if logic.name != "" and logic.name != logic.output_var_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        return text

    if isinstance(logic, MovingAverageLogic):
        output_var = _find_local_var_by_name(block, logic.output_var_name)
        text = (
            f"movingavg({_expr_like_to_python(logic.source_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.delay_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.window_expr, identifier_map)}, output={identifier_map[output_var.uid]})"
        )
        if logic.name != "" and logic.name != logic.output_var_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        return text

    if isinstance(logic, GradientLimiterLogic):
        output_var = _find_local_var_by_name(block, logic.output_var_name)
        text = (
            f"gradlim_const({_expr_like_to_python(logic.source_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.lower_rate_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.upper_rate_expr, identifier_map)}, output={identifier_map[output_var.uid]})"
        )
        if logic.name != "" and logic.name != logic.output_var_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        return text

    if isinstance(logic, HardSaturationLogic):
        output_var = _find_local_var_by_name(block, logic.output_var_name)
        text = (
            f"hard_saturation(output={identifier_map[output_var.uid]}, "
            f"u={_expr_like_to_python(logic.u_expr, identifier_map)}, "
            f"u_min={_expr_like_to_python(logic.u_min_expr, identifier_map)}, "
            f"u_max={_expr_like_to_python(logic.u_max_expr, identifier_map)})"
        )
        if logic.name != "" and logic.name != logic.output_var_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        return text

    if isinstance(logic, ResetOnRisingEdgeLogic):
        target_var = _find_local_var_by_name(block, logic.target_var_name)
        default_name = f"{logic.target_var_name}_reset"
        text = (
            f"reset({identifier_map[target_var.uid]}, "
            f"{_expr_like_to_python(logic.reset_expr, identifier_map)}, "
            f"{_expr_like_to_python(logic.value_expr, identifier_map)})"
        )
        if logic.name != "" and logic.name != default_name:
            text = text[:-1] + f", name={repr(logic.name)})"
        return text

    raise TypeError(f"Unsupported procedural logic export type: {type(logic).__name__}")


def _append_humanized_procedural_logic_entry(
        lines: List[str],
        logic: ProceduralLogicBase,
        block: Block,
        identifier_map: Dict[int, str],
        indentation: int = 8,
        maximum_line_length: int = 112,
) -> None:
    """Append one procedural instruction in compact or vertical call form.

    :param lines: Generated module lines updated in place.
    :param logic: Typed procedural instruction to serialize.
    :param block: Owning symbolic block used for output-variable lookup.
    :param identifier_map: Python identifier indexed by symbolic variable uid.
    :param indentation: Number of spaces before the call.
    :param maximum_line_length: Preferred maximum generated source-line width.
    :return: None.
    """
    compact_text: str = _procedural_logic_entry_to_python(
        logic=logic,
        block=block,
        identifier_map=identifier_map,
    )
    compact_line_fits: bool = (
        indentation + len(compact_text) + 1 <= maximum_line_length
    )

    if compact_line_fits:
        lines.append((" " * indentation) + compact_text + ",")
    else:
        argument_indentation: int = indentation + 4
        if isinstance(logic, FixedSampleLogic):
            output_var: Var = _find_local_var_by_name(block, logic.output_var_name)
            lines.append((" " * indentation) + "selfix(")
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.condition_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            lines.append(
                (" " * argument_indentation)
                + "output="
                + identifier_map[output_var.uid]
                + ","
            )
            if logic.name != "" and logic.name != logic.output_var_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        elif isinstance(logic, SampledValueLogic):
            output_var = _find_local_var_by_name(block, logic.output_var_name)
            uses_sampled_value: bool = (
                logic.evaluation_mode
                == SampledValueEvaluationMode.ImplicitIterate
            )
            if uses_sampled_value:
                lines.append((" " * indentation) + "sampled_value(")
                lines.append(
                    (" " * argument_indentation)
                    + "output="
                    + identifier_map[output_var.uid]
                    + ","
                )
                _append_humanized_expr_like_argument(
                    lines=lines,
                    prefix="source=",
                    expr=logic.source_expr,
                    identifier_map=identifier_map,
                    indentation=argument_indentation,
                )
            else:
                lines.append((" " * indentation) + "lastvalue(")
                _append_humanized_expr_like_argument(
                    lines=lines,
                    prefix="",
                    expr=logic.source_expr,
                    identifier_map=identifier_map,
                    indentation=argument_indentation,
                )
                lines.append(
                    (" " * argument_indentation)
                    + "output="
                    + identifier_map[output_var.uid]
                    + ","
                )
            if logic.name != "" and logic.name != logic.output_var_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        elif isinstance(logic, FlipFlopLogic):
            output_var = _find_local_var_by_name(block, logic.output_var_name)
            lines.append((" " * indentation) + "flipflop(")
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.set_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.reset_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            lines.append(
                (" " * argument_indentation)
                + "output="
                + identifier_map[output_var.uid]
                + ","
            )
            if logic.name != "" and logic.name != logic.output_var_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            if logic.use_mode_default_at_initialization:
                lines.append(
                    (" " * argument_indentation)
                    + "use_mode_default_at_initialization=True,"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        elif isinstance(logic, AnalogFlipFlopLogic):
            output_var = _find_local_var_by_name(block, logic.output_var_name)
            lines.append((" " * indentation) + "aflipflop(")
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.input_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.set_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.reset_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            lines.append(
                (" " * argument_indentation)
                + "output="
                + identifier_map[output_var.uid]
                + ","
            )
            if logic.name != "" and logic.name != logic.output_var_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        elif isinstance(logic, PickupDropoffLogic):
            output_var = _find_local_var_by_name(block, logic.output_var_name)
            lines.append((" " * indentation) + "picdro(")
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.bool_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.pickup_delay_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.drop_delay_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            lines.append(
                (" " * argument_indentation)
                + "output="
                + identifier_map[output_var.uid]
                + ","
            )
            if logic.name != "" and logic.name != logic.output_var_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        elif isinstance(logic, TimeDelayLogic):
            output_var = _find_local_var_by_name(block, logic.output_var_name)
            lines.append((" " * indentation) + "delay(")
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.source_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.delay_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            lines.append(
                (" " * argument_indentation)
                + "output="
                + identifier_map[output_var.uid]
                + ","
            )
            if logic.name != "" and logic.name != logic.output_var_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        elif isinstance(logic, MovingAverageLogic):
            output_var = _find_local_var_by_name(block, logic.output_var_name)
            lines.append((" " * indentation) + "movingavg(")
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.source_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.delay_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.window_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            lines.append(
                (" " * argument_indentation)
                + "output="
                + identifier_map[output_var.uid]
                + ","
            )
            if logic.name != "" and logic.name != logic.output_var_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        elif isinstance(logic, GradientLimiterLogic):
            output_var = _find_local_var_by_name(block, logic.output_var_name)
            lines.append((" " * indentation) + "gradlim_const(")
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.source_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.lower_rate_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.upper_rate_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            lines.append(
                (" " * argument_indentation)
                + "output="
                + identifier_map[output_var.uid]
                + ","
            )
            if logic.name != "" and logic.name != logic.output_var_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        elif isinstance(logic, HardSaturationLogic):
            output_var = _find_local_var_by_name(block, logic.output_var_name)
            lines.append((" " * indentation) + "hard_saturation(")
            lines.append(
                (" " * argument_indentation)
                + "output="
                + identifier_map[output_var.uid]
                + ","
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="u=",
                expr=logic.u_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="u_min=",
                expr=logic.u_min_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="u_max=",
                expr=logic.u_max_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            if logic.name != "" and logic.name != logic.output_var_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        elif isinstance(logic, ResetOnRisingEdgeLogic):
            target_var: Var = _find_local_var_by_name(block, logic.target_var_name)
            lines.append((" " * indentation) + "reset(")
            lines.append(
                (" " * argument_indentation)
                + identifier_map[target_var.uid]
                + ","
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.reset_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            _append_humanized_expr_like_argument(
                lines=lines,
                prefix="",
                expr=logic.value_expr,
                identifier_map=identifier_map,
                indentation=argument_indentation,
            )
            default_name: str = f"{logic.target_var_name}_reset"
            if logic.name != "" and logic.name != default_name:
                lines.append(
                    (" " * argument_indentation)
                    + f"name={logic.name!r},"
                )
            else:
                pass
            lines.append((" " * indentation) + "),")
        else:
            raise TypeError(
                f"Unsupported procedural logic export type: {type(logic).__name__}"
            )


def _emit_block_code(
    block: Block,
    identifier_map: Dict[int, str],
    block_var_name: str,
    lines: List[str],
    child_ref_names: Dict[int, str],
) -> None:
    if block.startup_initializer is None:
        pass
    else:
        raise TypeError(
            f"Block '{block.name}' uses a startup initializer that cannot be "
            "represented by the canonical Python template emitter"
        )

    lines.append(f"    {block_var_name} = Block(")
    if block.state_eqs:
        lines.append("        state_eqs=[")
        for eq in block.state_eqs:
            _append_humanized_expression(
                lines=lines,
                prefix="",
                expr=eq,
                identifier_map=identifier_map,
                indentation=12,
            )
        lines.append("        ],")
    else:
        pass
    if block.state_vars:
        _append_humanized_identifier_list(
            lines=lines,
            prefix="state_vars=",
            identifiers=list((identifier_map[var.uid] for var in block.state_vars)),
            indentation=8,
            suffix=",",
        )
    else:
        pass
    if len(block.state_limits) > 0:
        # Keep limited-integrator contracts readable in generated catalogue
        # modules.  Bounds remain symbolic expressions, matching the format of
        # standard-model equations and allowing parameterized DGS limits.
        lines.append("        state_limits={")
        for state_var, limit_pair in block.state_limits.items():
            lines.append(f"            {identifier_map[state_var.uid]}: (")
            _append_humanized_expression(
                lines=lines,
                prefix="",
                expr=limit_pair[0],
                identifier_map=identifier_map,
                indentation=16,
            )
            _append_humanized_expression(
                lines=lines,
                prefix="",
                expr=limit_pair[1],
                identifier_map=identifier_map,
                indentation=16,
            )
            lines.append("            ),")
        lines.append("        },")
    else:
        pass
    if block.algebraic_eqs:
        lines.append("        algebraic_eqs=[")
        for eq in block.algebraic_eqs:
            _append_humanized_expression(
                lines=lines,
                prefix="",
                expr=eq,
                identifier_map=identifier_map,
                indentation=12,
            )
        lines.append("        ],")
    else:
        pass
    if block.algebraic_vars:
        _append_humanized_identifier_list(
            lines=lines,
            prefix="algebraic_vars=",
            identifiers=list((identifier_map[var.uid] for var in block.algebraic_vars)),
            indentation=8,
            suffix=",",
        )
    else:
        pass
    if block.inequalities:
        lines.append("        inequalities=[")
        for inequality in block.inequalities:
            lines.append(f"            {_expr_like_to_python(inequality, identifier_map)},")
        lines.append("        ],")
    else:
        pass
    if block.differential_eqs:
        lines.append("        differential_eqs=[")
        for differential_eq in block.differential_eqs:
            _append_humanized_expression(
                lines=lines,
                prefix="",
                expr=differential_eq,
                identifier_map=identifier_map,
                indentation=12,
            )
        lines.append("        ],")
    else:
        pass
    if block.children:
        _append_humanized_identifier_list(
            lines=lines,
            prefix="children=",
            identifiers=list((child_ref_names[id(child)] for child in block.children)),
            indentation=8,
            suffix=",",
        )
    else:
        pass
    if block.in_vars:
        _append_humanized_identifier_list(
            lines=lines,
            prefix="in_vars=",
            identifiers=list((identifier_map[var.uid] for var in block.in_vars)),
            indentation=8,
            suffix=",",
        )
    else:
        pass
    if block.out_vars:
        _append_humanized_identifier_list(
            lines=lines,
            prefix="out_vars=",
            identifiers=list((identifier_map[var.uid] for var in block.out_vars)),
            indentation=8,
            suffix=",",
        )
    else:
        pass
    lines.append(f"        is_decomposable={repr(bool(block.is_decomposable))},")
    lines.append(f"        name={repr(block.name)},")
    lines.append("    )")

    # Native meter binding must retain the exact PowerFactory graph endpoint
    # after the human-readable catalogue module is reloaded. Equal port names
    # in different slots are not a signal identity, so textual lookup alone is
    # insufficient for a safe runtime connection.
    raw_slot_id: object | None = block.__dict__.get("dgs_slot_id", None)
    if isinstance(raw_slot_id, str) and raw_slot_id != "":
        lines.append(
            f'    {block_var_name}.__dict__["dgs_slot_id"] = {raw_slot_id!r}'
        )
    else:
        pass

    raw_element_id: object | None = block.__dict__.get("dgs_element_id", None)
    if isinstance(raw_element_id, str) and raw_element_id != "":
        lines.append(
            f'    {block_var_name}.__dict__["dgs_element_id"] = {raw_element_id!r}'
        )
    else:
        pass

    raw_astable_integration: object | None = block.__dict__.get(
        "dgs_powerfactory_astable_integration",
        None,
    )
    if isinstance(raw_astable_integration, bool):
        lines.append(
            f'    {block_var_name}.__dict__["dgs_powerfactory_astable_integration"] = '
            + repr(raw_astable_integration)
        )
    else:
        pass

    raw_slot_interfaces: object | None = block.__dict__.get(
        "dgs_direct_slot_interfaces",
        None,
    )
    if isinstance(raw_slot_interfaces, list):
        lines.append("    # --- Native PowerFactory Slot Provenance ---")
        _append_humanized_metadata_assignment(
            lines=lines,
            prefix=f'{block_var_name}.__dict__["dgs_direct_slot_interfaces"] = ',
            value=raw_slot_interfaces,
            indentation=4,
        )
    else:
        pass

    raw_unresolved_graphical_inputs: object | None = block.__dict__.get(
        "dgs_unresolved_graphical_input_names",
        None,
    )
    if (
            isinstance(raw_unresolved_graphical_inputs, list)
            and len(raw_unresolved_graphical_inputs) > 0
    ):
        lines.append("    # --- Incomplete Source DGS Graphical Topology ---")
        _append_humanized_metadata_assignment(
            lines=lines,
            prefix=(
                f'{block_var_name}.__dict__'
                '["dgs_unresolved_graphical_input_names"] = '
            ),
            value=raw_unresolved_graphical_inputs,
            indentation=4,
        )
    else:
        pass

    raw_disconnected_graphical_inputs: object | None = block.__dict__.get(
        "dgs_disconnected_graphical_input_names",
        None,
    )
    if (
            isinstance(raw_disconnected_graphical_inputs, list)
            and len(raw_disconnected_graphical_inputs) > 0
    ):
        lines.append("    # --- Intentional PowerFactory Disconnected Inputs ---")
        _append_humanized_metadata_assignment(
            lines=lines,
            prefix=(
                f'{block_var_name}.__dict__'
                '["dgs_disconnected_graphical_input_names"] = '
            ),
            value=raw_disconnected_graphical_inputs,
            indentation=4,
        )
    else:
        pass

    if block.diff_vars:
        _append_humanized_identifier_list(
            lines=lines,
            prefix=f"{block_var_name}.diff_vars = ",
            identifiers=list((identifier_map[var.uid] for var in block.diff_vars)),
            indentation=4,
            suffix="",
        )
    else:
        pass

    if block.reformulated_vars:
        _append_humanized_identifier_list(
            lines=lines,
            prefix=f"{block_var_name}.reformulated_vars = ",
            identifiers=list((identifier_map[var.uid] for var in block.reformulated_vars)),
            indentation=4,
            suffix="",
        )
    else:
        pass

    if block.parameters:
        lines.append(f"    # --- Static Parameters ---")
        lines.append(f"    {block_var_name}.parameters = {{")
        for key, value in block.parameters.items():
            _append_humanized_expression(
                lines=lines,
                prefix=f"{identifier_map[key.uid]}: ",
                expr=value,
                identifier_map=identifier_map,
                indentation=8,
            )
        lines.append("    }")
    else:
        pass

    if block.event_dict:
        lines.append(f"    # --- Parameter Values ---")
        lines.append(f"    {block_var_name}.event_dict = {{")
        for key, value in block.event_dict.items():
            _append_humanized_expression(
                lines=lines,
                prefix=f"{identifier_map[key.uid]}: ",
                expr=value,
                identifier_map=identifier_map,
                indentation=8,
            )
        lines.append("    }")
    else:
        pass

    if block.mode_dict:
        lines.append(f"    # --- Retained Runtime Modes ---")
        lines.append(f"    {block_var_name}.mode_dict = {{")
        for key, value in block.mode_dict.items():
            _append_humanized_expression(
                lines=lines,
                prefix=f"{identifier_map[key.uid]}: ",
                expr=value,
                identifier_map=identifier_map,
                indentation=8,
            )
        lines.append("    }")
    else:
        pass

    if block.init_eqs:
        lines.append(f"    # --- Initial Equations and Guesses ---")
        lines.append(f"    {block_var_name}.init_eqs = {{")
        for key, value in block.init_eqs.items():
            _append_humanized_expression(
                lines=lines,
                prefix=f"{identifier_map[key.uid]}: ",
                expr=value,
                identifier_map=identifier_map,
                indentation=8,
            )
        lines.append("    }")
    else:
        pass

    raw_explicit_initialization_uids: object | None = block.__dict__.get(
        "dgs_explicit_initialization_uids",
        None,
    )
    if isinstance(raw_explicit_initialization_uids, set):
        explicit_initialization_identifiers: List[str] = list()
        explicit_uid: object
        for explicit_uid in raw_explicit_initialization_uids:
            if isinstance(explicit_uid, int) and explicit_uid in identifier_map:
                explicit_initialization_identifiers.append(
                    f"{identifier_map[explicit_uid]}.uid"
                )
            else:
                pass
        if len(explicit_initialization_identifiers) > 0:
            lines.append("    # --- Explicit PowerFactory Initialization Ownership ---")
            lines.append(
                f'    {block_var_name}.__dict__["dgs_explicit_initialization_uids"] = set(['
            )
            for explicit_identifier in sorted(explicit_initialization_identifiers):
                lines.append(f"        {explicit_identifier},")
            lines.append("    ])")
        else:
            pass
    else:
        pass

    raw_runtime_helper_names: object | None = block.__dict__.get(
        "runtime_post_update_helper_names",
        None,
    )
    if isinstance(raw_runtime_helper_names, list):
        persisted_runtime_helper_names: List[str] = list()
        raw_runtime_helper_name: object
        for raw_runtime_helper_name in raw_runtime_helper_names:
            if (
                    isinstance(raw_runtime_helper_name, str)
                    and raw_runtime_helper_name != ""
            ):
                persisted_runtime_helper_names.append(raw_runtime_helper_name)
            else:
                pass
        else:
            pass
        if len(persisted_runtime_helper_names) > 0:
            lines.append("    # --- Procedural Algebraic Closure ---")
            _append_humanized_metadata_assignment(
                lines=lines,
                prefix=f'{block_var_name}.__dict__["runtime_post_update_helper_names"] = ',
                value=persisted_runtime_helper_names,
                indentation=4,
            )
        else:
            pass
    else:
        pass

    raw_initial_polish_uids: object | None = block.__dict__.get(
        "startup_initial_reduced_polish_var_uids",
        None,
    )
    if isinstance(raw_initial_polish_uids, list):
        cloned_initial_polish_uids: List[int] = list()
        raw_initial_polish_uid: object
        for raw_initial_polish_uid in raw_initial_polish_uids:
            if (
                    isinstance(raw_initial_polish_uid, int)
                    and raw_initial_polish_uid in created_vars
            ):
                # Runtime materialization gives every device a fresh symbolic
                # identity. Translate the declaration with that same mapping
                # so the startup solver never targets a catalogue prototype.
                cloned_initial_polish_uids.append(
                    created_vars[raw_initial_polish_uid].uid
                )
            else:
                pass
        else:
            pass
        cloned.__dict__["startup_initial_reduced_polish_var_uids"] = (
            cloned_initial_polish_uids
        )
    else:
        pass

    raw_runtime_helper_uids: object | None = block.__dict__.get(
        "runtime_post_update_helper_var_uids",
        None,
    )
    if isinstance(raw_runtime_helper_uids, list):
        persisted_runtime_helper_identifiers: List[str] = list()
        raw_runtime_helper_uid: object
        for raw_runtime_helper_uid in raw_runtime_helper_uids:
            if (
                    isinstance(raw_runtime_helper_uid, int)
                    and raw_runtime_helper_uid in identifier_map
            ):
                persisted_runtime_helper_identifiers.append(
                    f"{identifier_map[raw_runtime_helper_uid]}.uid"
                )
            else:
                pass
        else:
            pass
        if len(persisted_runtime_helper_identifiers) > 0:
            lines.append("    # --- Exact Procedural Helper Identity ---")
            lines.append(
                f'    {block_var_name}.__dict__["runtime_post_update_helper_var_uids"] = list(['
            )
            persisted_runtime_helper_identifier: str
            for persisted_runtime_helper_identifier in persisted_runtime_helper_identifiers:
                lines.append(
                    f"        {persisted_runtime_helper_identifier},"
                )
            else:
                pass
            lines.append("    ])")
        else:
            pass
    else:
        pass

    if block.diff_init_eqs:
        lines.append(f"    # --- Differential Initial Equations ---")
        lines.append(f"    {block_var_name}.diff_init_eqs = {{")
        for key, value in block.diff_init_eqs.items():
            _append_humanized_expression(
                lines=lines,
                prefix=f"{identifier_map[key.uid]}: ",
                expr=value,
                identifier_map=identifier_map,
                indentation=8,
            )
        lines.append("    }")
    else:
        pass

    if block.init_values:
        lines.append(f"    # --- Initial Values ---")
        lines.append(f"    {block_var_name}.init_values = {{")
        for key, value in block.init_values.items():
            _append_humanized_expression(
                lines=lines,
                prefix=f"{identifier_map[key.uid]}: ",
                expr=value,
                identifier_map=identifier_map,
                indentation=8,
            )
        lines.append("    }")
    else:
        pass

    if block.discrete_eqs:
        lines.append(f"    # --- Discrete Equations ---")
        lines.append(f"    {block_var_name}.discrete_eqs = {{")
        for key, value in block.discrete_eqs.items():
            _append_humanized_expression(
                lines=lines,
                prefix=f"{identifier_map[key.uid]}: ",
                expr=value,
                identifier_map=identifier_map,
                indentation=8,
            )
        lines.append("    }")
    else:
        pass

    raw_discrete_actions: object | None = block.__dict__.get(
        "dgs_discrete_event_actions",
        None,
    )
    if isinstance(raw_discrete_actions, list) and len(raw_discrete_actions) > 0:
        lines.append("    # --- Deferred Physical Equipment Actions ---")
        lines.append(
            f'    {block_var_name}.__dict__["dgs_discrete_event_actions"] = ['
        )
        raw_discrete_action: object
        for raw_discrete_action in raw_discrete_actions:
            if isinstance(raw_discrete_action, DgsDiscreteEventAction):
                lines.append("        DgsDiscreteEventAction(")
                lines.append(
                    "            trigger_signal_name="
                    f"{raw_discrete_action.get_trigger_signal_name()!r},"
                )
                lines.append(
                    "            trigger_expression="
                    f"{raw_discrete_action.get_trigger_expression()!r},"
                )
                lines.append(
                    "            target_slot_name="
                    f"{raw_discrete_action.get_target_slot_name()!r},"
                )
                lines.append(
                    f"            event_name={raw_discrete_action.get_event_name()!r},"
                )
                lines.append(
                    "            command=DgsDiscreteEventCommand."
                    f"{raw_discrete_action.get_command().name},"
                )
                lines.append(
                    "            delay_expression="
                    f"{raw_discrete_action.get_delay_expression()!r},"
                )
                lines.append(
                    "            source_statement="
                    f"{raw_discrete_action.get_source_statement()!r},"
                )
                lines.append(
                    "            root_dgs_id="
                    f"{raw_discrete_action.get_root_dgs_id()!r},"
                )
                lines.append(
                    "            target_element_dgs_id="
                    f"{raw_discrete_action.get_target_element_dgs_id()!r},"
                )
                lines.append(
                    "            actuated_device_dgs_id="
                    f"{raw_discrete_action.get_actuated_device_dgs_id()!r},"
                )
                lines.append(
                    "            actuated_terminal_index="
                    f"{raw_discrete_action.get_actuated_terminal_index()!r},"
                )
                symbolic_guard_expression: Expr | None = (
                    raw_discrete_action.get_symbolic_guard_expression()
                )
                symbolic_trigger_expression: Expr | None = (
                    raw_discrete_action.get_symbolic_trigger_expression()
                )
                symbolic_delay_expression: Expr | None = (
                    raw_discrete_action.get_symbolic_delay_expression()
                )
                if symbolic_guard_expression is None:
                    lines.append("            symbolic_guard_expression=None,")
                else:
                    lines.append(
                        "            symbolic_guard_expression="
                        + _const_or_expr_to_python(
                            symbolic_guard_expression,
                            identifier_map,
                        )
                        + ","
                    )
                if symbolic_trigger_expression is None:
                    lines.append("            symbolic_trigger_expression=None,")
                else:
                    lines.append(
                        "            symbolic_trigger_expression="
                        + _const_or_expr_to_python(
                            symbolic_trigger_expression,
                            identifier_map,
                        )
                        + ","
                    )
                if symbolic_delay_expression is None:
                    lines.append("            symbolic_delay_expression=None,")
                else:
                    lines.append(
                        "            symbolic_delay_expression="
                        + _const_or_expr_to_python(
                            symbolic_delay_expression,
                            identifier_map,
                        )
                        + ","
                    )
                lines.append("        ),")
            else:
                pass
        lines.append("    ]")
    else:
        pass

    if block.post_init_seed_eqs:
        lines.append(f"    # --- Post-Initialization Seed Equations ---")
        lines.append(f"    {block_var_name}.post_init_seed_eqs = {{")
        for key, value in block.post_init_seed_eqs.items():
            _append_humanized_expression(
                lines=lines,
                prefix=f"{identifier_map[key.uid]}: ",
                expr=value,
                identifier_map=identifier_map,
                indentation=8,
            )
        lines.append("    }")
    else:
        pass

    if block.boolean_guards:
        lines.append(f"    # --- Boolean Guards ---")
        lines.append(f"    {block_var_name}.boolean_guards = {{")
        for key, value in block.boolean_guards.items():
            lines.append(f"        {identifier_map[key.uid]}: {_expr_like_to_python(value, identifier_map)},")
        lines.append("    }")
    else:
        pass

    if block.external_mapping:
        lines.append(f"    # --- Power Flow External Mapping ---")
        lines.append(f"    {block_var_name}.external_mapping = {{")
        for key, value in block.external_mapping.items():
            if value is None:
                lines.append(f"        VarPowerFlowReferenceType.{key.name}: None,")
            else:
                lines.append(f"        VarPowerFlowReferenceType.{key.name}: {identifier_map[value.uid]},")
        lines.append("    }")
    else:
        pass

    if block.api_obj_mapping:
        lines.append(f"    # --- API Object Parameter Mapping ---")
        lines.append(f"    {block_var_name}.api_obj_mapping = {{")
        for key, value in block.api_obj_mapping.items():
            if value is None:
                lines.append(f"        ParamPowerFlowReferenceType.{key.name}: None,")
            else:
                lines.append(f"        ParamPowerFlowReferenceType.{key.name}: {identifier_map[value.uid]},")
        lines.append("    }")
    else:
        pass

    if block.procedural_logic:
        lines.append(f"    {block_var_name}.procedural_logic = [")
        for logic in block.procedural_logic:
            _append_humanized_procedural_logic_entry(
                lines=lines,
                logic=logic,
                block=block,
                identifier_map=identifier_map,
            )
        lines.append("    ]")
    else:
        pass

    diagram_data: Dict[str, object] = block.diagram.to_dict()
    diagram_has_content: bool = bool(
        len(block.diagram.node_data) > 0 or len(block.diagram.con_data) > 0
    )
    if diagram_has_content:
        lines.append(f"    # --- Human-Readable Diagram ---")
        lines.append(f"    {block_var_name}.diagram.parse({pprint.pformat(diagram_data, sort_dicts=True)})")
    else:
        pass


class _TemplateModuleVariableGroups:
    """
    Variable groups used by the DGS template emitter.
    """

    __slots__ = ("param_vars", "state_vars", "algebraic_vars", "diff_vars")

    def __init__(self,
                 param_vars: List[Var],
                 state_vars: List[Var],
                 algebraic_vars: List[Var],
                 diff_vars: List[Var]) -> None:
        """
        Store the variable groups used by one emitted template module.

        :param param_vars: Runtime parameter variables.
        :param state_vars: State variables.
        :param algebraic_vars: Algebraic/shared variables.
        :param diff_vars: Differential variables.
        :returns: None.
        """
        self.param_vars = param_vars
        self.state_vars = state_vars
        self.algebraic_vars = algebraic_vars
        self.diff_vars = diff_vars


def _build_template_module_variable_groups(
        block: Block,
        vars_by_uid: Dict[int, Var] | None = None,
) -> _TemplateModuleVariableGroups:
    """
    Build the variable groups required by the template emitter.

    :param block: Root block to emit.
    :param vars_by_uid: Optional variables already collected from the complete
        tree. Callers outside the DGS emitter may omit them.
    :returns: Variable groups used during emission.
    """
    if vars_by_uid is None:
        collected_vars_by_uid: Dict[int, Var] = dict()
        collected_consts_by_uid: Dict[int, Const] = dict()
        _collect_block_vars_recursive(
            block=block,
            vars_out=collected_vars_by_uid,
            consts_out=collected_consts_by_uid,
        )
    else:
        collected_vars_by_uid = vars_by_uid
    all_vars: List[Var] = list(collected_vars_by_uid.values())
    state_uids: Set[int] = _collect_uid_set_from_blocks(block, "state_vars")
    diff_uids: Set[int] = _collect_uid_set_from_blocks(block, "diff_vars")
    param_uids: Set[int] = _collect_parameter_uid_set_from_blocks(block)

    state_vars: List[Var] = [v for v in all_vars if v.uid in state_uids and v.uid not in diff_uids]
    diff_vars: List[Var] = [v for v in all_vars if v.uid in diff_uids]
    param_vars: List[Var] = [v for v in all_vars if v.uid in param_uids and v.uid not in diff_uids]
    algebraic_vars: List[Var] = [
        v for v in all_vars
        if v.uid not in state_uids and v.uid not in diff_uids and v.uid not in param_uids
    ]

    return _TemplateModuleVariableGroups(
        param_vars=param_vars,
        state_vars=state_vars,
        algebraic_vars=algebraic_vars,
        diff_vars=diff_vars,
    )


class DgsTemplateModuleEmitter:
    """
    Structured emitter for one standalone EMT template module.
    """

    __slots__ = (
        "result",
        "subgraph",
        "dgs_path",
        "block",
        "identifier_map",
        "resolved_template_name",
        "func_base_name",
        "has_procedural_logic",
        "has_dgs_discrete_events",
        "procedural_import_names",
        "variable_groups",
        "child_ref_names_by_node",
        "child_ref_names",
    )

    def __init__(self,
                 result: DgsRootBlockResult,
                 subgraph: DgsBlockSubgraphResult,
                 dgs_path: str,
                 template_name: str | None = None) -> None:
        """
        Build the standalone EMT template emitter.

        :param result: Root parse result.
        :param subgraph: Selected block subgraph.
        :param dgs_path: Source DGS path.
        :param template_name: Optional explicit template name.
        :returns: None.
        """
        self.result = result
        self.subgraph = subgraph
        self.dgs_path = dgs_path
        self.block = subgraph.view_block
        # Both the identifier allocator and the declaration grouper require the
        # same complete symbolic surface. Collect it once because large OEM
        # composites contain deeply repeated expression trees.
        all_variables_by_uid: Dict[int, Var] = dict()
        all_constants_by_uid: Dict[int, Const] = dict()
        _collect_block_vars_recursive(
            block=self.block,
            vars_out=all_variables_by_uid,
            consts_out=all_constants_by_uid,
        )
        self.identifier_map = _make_identifier_map(
            block=self.block,
            vars_by_uid=all_variables_by_uid,
        )
        self.resolved_template_name = template_name if template_name is not None else subgraph.selected_block.blkdef.loc_name
        self.func_base_name = _safe_name(self.resolved_template_name).lower()
        self.has_procedural_logic = any(len(item.procedural_logic) > 0 for item in _iter_blocks_recursive(self.block))
        self.has_dgs_discrete_events: bool = False
        event_block: Block
        for event_block in _iter_blocks_recursive(self.block):
            raw_actions: object | None = event_block.__dict__.get(
                "dgs_discrete_event_actions",
                None,
            )
            if isinstance(raw_actions, list) and len(raw_actions) > 0:
                self.has_dgs_discrete_events = True
            else:
                pass
        self.procedural_import_names = _procedural_logic_import_names(self.block)
        self.variable_groups = _build_template_module_variable_groups(
            block=self.block,
            vars_by_uid=all_variables_by_uid,
        )
        self.child_ref_names_by_node = self._build_child_ref_names_by_node()
        self.child_ref_names = self._build_child_ref_names()

    def render(self) -> str:
        """
        Render the standalone EMT template module.

        :returns: Python module text.
        """
        lines: List[str] = list()
        self._append_header(lines)
        self._append_imports(lines)
        self._append_source_metadata(lines)
        self._append_template_function(lines)
        self._append_template_wrapper(lines)
        return "\n".join(lines) + "\n"

    def _append_header(self, lines: List[str]) -> None:
        """
        Append the module header.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---")
        lines.append(f"# Source: {self.dgs_path}")
        lines.append("")

    def _append_imports(self, lines: List[str]) -> None:
        """
        Append the import block.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory")
        lines.append("from VeraGridEngine.Utils.Symbolic import symbolic as sym")
        lines.append("from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate")
        if isinstance(self.subgraph, DgsGraphicTreeResult) and len(self.subgraph.connections) > 0:
            lines.append("from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block")
        else:
            lines.append("from VeraGridEngine.Utils.Symbolic.block import Block")

        if self.has_procedural_logic:
            lines.append("from VeraGridEngine.Utils.procedural_logic import " + ", ".join(self.procedural_import_names))
        else:
            pass

        if self.has_dgs_discrete_events:
            lines.append(
                "from VeraGridEngine.IO.dgs.dgs_discrete_event import "
                "DgsDiscreteEventAction, DgsDiscreteEventCommand"
            )
        else:
            pass

        lines.append("from VeraGridEngine.enumerations import DeviceType")
        lines.append("")

    def _append_source_metadata(self, lines: List[str]) -> None:
        """Preserve non-executable DGS declarations needed for audit/tooling."""
        fixed_limit_specs: Dict[str, Dict[str, object]] = dict()
        for block_id in sorted(self.subgraph.node_ids):
            parsed = self.result.parsed_blocks.get(block_id)
            if parsed is not None and parsed.fixed_limit_specs:
                fixed_limit_specs[str(block_id)] = {
                    "block_name": parsed.blkdef.loc_name,
                    "limits": dict(sorted(parsed.fixed_limit_specs.items())),
                }
        metadata_repr = pprint.pformat(fixed_limit_specs, width=120, sort_dicts=True)
        lines.append(f"DGS_FIXED_LIMIT_SPECS = {metadata_repr}")
        lines.append("")
        lines.append("")

    def _append_template_function(self, lines: List[str]) -> None:
        """
        Append the main EMT template builder function.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append(
            f"def get_{self.func_base_name}_emt_template(vf: VarFactory, name: str = {repr(self.resolved_template_name)}) -> EmtModelTemplate:"
        )
        lines.append("    templ = EmtModelTemplate()")
        lines.append("    templ.tpe = DeviceType.NoDevice")
        lines.append("    templ.name = name")
        lines.append("")
        self._append_variable_declarations(lines)
        lines.append("    # --- Block Assembly ---")
        self._append_child_blocks(lines)
        self._append_graphical_connections(lines)
        _emit_block_code(self.block, self.identifier_map, "templ.block", lines, self.child_ref_names)
        lines.append("    templ.block.name = name")
        lines.append("")
        lines.append("    return templ")
        lines.append("")

    def _append_variable_declarations(self, lines: List[str]) -> None:
        """
        Append grouped variable declarations.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("    # --- Parameters ---")
        var: Var
        for var in sorted(self.variable_groups.param_vars, key=_var_name_sort_key):
            lines.append(f"    {self.identifier_map[var.uid]} = vf.add_var({repr(var.name + '_')} + name)")

        lines.append("")
        lines.append("    # --- State Variables ---")
        for var in sorted(self.variable_groups.state_vars, key=_var_name_sort_key):
            lines.append(f"    {self.identifier_map[var.uid]} = vf.add_var({repr(var.name + '_')} + name)")

        lines.append("")
        lines.append("    # --- Algebraic / Shared Variables ---")
        for var in sorted(self.variable_groups.algebraic_vars, key=_var_name_sort_key):
            lines.append(f"    {self.identifier_map[var.uid]} = vf.add_var({repr(var.name + '_')} + name)")

        lines.append("")
        lines.append("    # --- Derivative Variables ---")
        for var in sorted(self.variable_groups.diff_vars, key=_var_name_sort_key):
            base_name: str = self.identifier_map[var.base_var.uid]
            lines.append(f"    {self.identifier_map[var.uid]} = vf.add_diff_var({repr(var.name + '_')} + name, base_var={base_name})")

        lines.append("")

    def _append_child_blocks(self, lines: List[str]) -> None:
        """
        Append emitted child blocks.

        :param lines: Output line buffer.
        :returns: None.
        """
        child: Block
        for child in self.block.children:
            _emit_block_code(child, self.identifier_map, self.child_ref_names[id(child)], lines, self.child_ref_names)
            lines.append("")

    def _append_graphical_connections(self, lines: List[str]) -> None:
        """
        Append the explicit graphical connection instructions when available.

        :param lines: Output line buffer.
        :returns: None.
        """
        if isinstance(self.subgraph, DgsGraphicTreeResult) and len(self.subgraph.connections) > 0:
            lines.append("    # --- Graphical Connections (resolved from From/To) ---")
            item: GraphicConnectionInstruction
            for item in self.subgraph.connections:
                consumer_ref: str = self.child_ref_names_by_node[item.consumer_node_id]
                if item.source_kind == "block_output" and item.source_node_id is not None and item.source_output_index is not None and item.consumer_input_index is not None:
                    producer_ref: str = self.child_ref_names_by_node[item.source_node_id]
                    lines.append(
                        f"    {consumer_ref}.connect([{consumer_ref}.in_vars[{item.consumer_input_index}]], "
                        f"[{producer_ref}.out_vars[{item.source_output_index}]])"
                    )
                elif item.source_kind == "root_input" and item.source_root_name is not None and item.consumer_input_index is not None:
                    lines.append(
                        f"    {consumer_ref}.connect([{consumer_ref}.in_vars[{item.consumer_input_index}]], "
                        f"[{self.identifier_map[find_name_in_block(item.source_root_name, self.block).uid]}])"
                    )
                else:
                    pass

            lines.append("")
        else:
            pass

    def _append_template_wrapper(self, lines: List[str]) -> None:
        """
        Append the stable ``get_template`` wrapper.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:")
        lines.append(
            f"    return get_{self.func_base_name}_emt_template(vf=vf, name={repr(self.resolved_template_name)} if name is None else name)"
        )

    def _build_child_ref_names_by_node(self) -> Dict[str, str]:
        """
        Build the reference-name lookup by graphical node id.

        :returns: Child reference name by node id.
        """
        child_ref_names_by_node: Dict[str, str] = dict()
        if isinstance(self.subgraph, DgsGraphicTreeResult):
            idx: int
            node_id: str
            for idx, node_id in enumerate(self.subgraph.child_node_ids):
                child_ref_names_by_node[node_id] = f"{_safe_name(self.block.children[idx].name)}_{idx}"
        else:
            pass

        return child_ref_names_by_node

    def _build_child_ref_names(self) -> Dict[int, str]:
        """
        Build the child reference-name lookup by block identity.

        :returns: Child reference name by block identity.
        """
        child_ref_names: Dict[int, str] = dict()
        idx: int
        child: Block

        if isinstance(self.subgraph, DgsGraphicTreeResult):
            for idx, child in enumerate(self.block.children):
                node_id: str = self.subgraph.child_node_ids[idx]
                child_ref_names[id(child)] = self.child_ref_names_by_node.get(node_id, f"{_safe_name(child.name)}_{idx}")
        else:
            for idx, child in enumerate(self.block.children):
                child_ref_names[id(child)] = f"{_safe_name(child.name)}_{idx}"

        return child_ref_names


def _emit_template_style_module(
    result: DgsRootBlockResult,
    subgraph: DgsBlockSubgraphResult,
    dgs_path: str,
    template_name: str | None = None,
) -> str:
    emitter = DgsTemplateModuleEmitter(result=result, subgraph=subgraph, dgs_path=dgs_path, template_name=template_name)
    return emitter.render()


class DgsBlockTreeModuleEmitter:
    """
    Structured emitter for one serialized DGS block-tree module.
    """

    __slots__ = ("result", "subgraph", "dgs_path")

    def __init__(self,
                 result: DgsRootBlockResult,
                 subgraph: DgsBlockSubgraphResult,
                 dgs_path: str) -> None:
        """
        Build the serialized block-tree emitter.

        :param result: Root parse result.
        :param subgraph: Selected block subgraph.
        :param dgs_path: Source DGS path.
        :returns: None.
        """
        self.result = result
        self.subgraph = subgraph
        self.dgs_path = dgs_path

    def render(self) -> str:
        """
        Render the serialized block-tree module.

        :returns: Python module text.
        """
        lines: List[str] = list()
        self._append_header(lines)
        self._append_imports(lines)
        self._append_serialized_constants(lines)
        self._append_accessors(lines)
        return "\n".join(lines) + "\n"

    def _append_header(self, lines: List[str]) -> None:
        """
        Append the module header.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("# Auto-generated DGS block tree export.")
        lines.append(f"# Source: {self.dgs_path}")
        lines.append("")

    def _append_imports(self, lines: List[str]) -> None:
        """
        Append the import block.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("from VeraGridEngine.Utils.Symbolic.block import Block")
        lines.append("")
        lines.append("")

    def _append_serialized_constants(self, lines: List[str]) -> None:
        """
        Append the serialized block-tree constants.

        :param lines: Output line buffer.
        :returns: None.
        """
        block_data_repr: str = pprint.pformat(self.subgraph.view_block.to_dict(), width=120, sort_dicts=False)
        graph_repr: str = pprint.pformat(_graph_to_serializable(self.subgraph.dependency_graph), width=120, sort_dicts=False)
        upstream_repr: str = pprint.pformat(_graph_to_serializable(self.subgraph.upstream), width=120, sort_dicts=False)
        downstream_repr: str = pprint.pformat(_graph_to_serializable(self.subgraph.downstream), width=120, sort_dicts=False)

        metadata: Dict[str, object] = dict()
        metadata["dgs_path"] = str(self.dgs_path)
        metadata["root_element_name"] = self.result.root_element.loc_name
        metadata["root_element_typ_id"] = self.result.root_element.typ_id
        metadata["root_blkdef_id"] = self.result.root_blkdef.blkdef.ID
        metadata["root_blkdef_name"] = self.result.root_blkdef.blkdef.loc_name
        metadata["selected_block_id"] = self.subgraph.selected_block.blkdef.ID
        metadata["selected_block_name"] = self.subgraph.selected_block.blkdef.loc_name
        metadata["selected_inputs"] = self.subgraph.selected_block.blkdef.inputs
        metadata["selected_outputs"] = self.subgraph.selected_block.blkdef.outputs
        metadata["selected_states"] = self.subgraph.selected_block.blkdef.states
        metadata["selected_params"] = self.subgraph.selected_block.blkdef.params
        metadata["fixed_limit_specs"] = self.subgraph.selected_block.fixed_limit_specs
        metadata["unsupported_lines"] = self.subgraph.selected_block.unsupported_lines
        metadata["child_block_names"] = sorted(child.name for child in self.subgraph.view_block.children)
        metadata["node_ids"] = sorted(self.subgraph.node_ids)
        metadata_repr: str = pprint.pformat(metadata, width=120, sort_dicts=False)

        lines.append(f"BLOCK_DATA = {block_data_repr}")
        lines.append("")
        lines.append(f"DEPENDENCY_GRAPH = {graph_repr}")
        lines.append("")
        lines.append(f"UPSTREAM_GRAPH = {upstream_repr}")
        lines.append("")
        lines.append(f"DOWNSTREAM_GRAPH = {downstream_repr}")
        lines.append("")
        lines.append(f"METADATA = {metadata_repr}")
        lines.append("")
        lines.append("")

    def _append_accessors(self, lines: List[str]) -> None:
        """
        Append the public accessor functions.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("def get_block() -> Block:")
        lines.append("    return Block.parse(BLOCK_DATA)")
        lines.append("")
        lines.append("")
        lines.append("def get_dependency_graph() -> dict:")
        lines.append("    return DEPENDENCY_GRAPH")
        lines.append("")
        lines.append("")
        lines.append("def get_upstream_graph() -> dict:")
        lines.append("    return UPSTREAM_GRAPH")
        lines.append("")
        lines.append("")
        lines.append("def get_downstream_graph() -> dict:")
        lines.append("    return DOWNSTREAM_GRAPH")
        lines.append("")
        lines.append("")
        lines.append("def get_metadata() -> dict:")
        lines.append("    return METADATA")


class DgsGraphicalTreeModuleEmitter:
    """
    Structured emitter for one serialized graphical-tree module.
    """

    __slots__ = ("result", "graph_tree", "dgs_path")

    def __init__(self,
                 result: DgsRootBlockResult,
                 graph_tree: DgsGraphicTreeResult,
                 dgs_path: str) -> None:
        """
        Build the serialized graphical-tree emitter.

        :param result: Root parse result.
        :param graph_tree: Graphical tree result.
        :param dgs_path: Source DGS path.
        :returns: None.
        """
        self.result = result
        self.graph_tree = graph_tree
        self.dgs_path = dgs_path

    def render(self) -> str:
        """
        Render the serialized graphical-tree module.

        :returns: Python module text.
        """
        lines: List[str] = list()
        self._append_header(lines)
        self._append_imports(lines)
        self._append_serialized_constants(lines)
        self._append_accessors(lines)
        return "\n".join(lines) + "\n"

    def _append_header(self, lines: List[str]) -> None:
        """
        Append the module header.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("# Auto-generated DGS graphical block tree export.")
        lines.append(f"# Source: {self.dgs_path}")
        lines.append("")

    def _append_imports(self, lines: List[str]) -> None:
        """
        Append the import block.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("from VeraGridEngine.Utils.Symbolic.block import Block")
        lines.append("")
        lines.append("")

    def _append_serialized_constants(self, lines: List[str]) -> None:
        """
        Append the serialized graphical-tree constants.

        :param lines: Output line buffer.
        :returns: None.
        """
        block_data_repr: str = pprint.pformat(self.graph_tree.view_block.to_dict(), width=120, sort_dicts=False)
        graph_repr: str = pprint.pformat(_graph_to_serializable(self.graph_tree.adjacency), width=120, sort_dicts=False)

        metadata: Dict[str, object] = dict()
        metadata["dgs_path"] = str(self.dgs_path)
        metadata["root_element_name"] = self.result.root_element.loc_name
        metadata["root_element_typ_id"] = self.result.root_element.typ_id
        metadata["selected_block_id"] = self.graph_tree.selected_block.blkdef.ID
        metadata["selected_block_name"] = self.graph_tree.selected_block.blkdef.loc_name
        metadata["node_ids"] = sorted(self.graph_tree.node_ids)
        metadata["node_labels"] = self.graph_tree.node_labels
        metadata["node_kinds"] = self.graph_tree.node_kinds
        metadata_repr: str = pprint.pformat(metadata, width=120, sort_dicts=False)

        lines.append(f"BLOCK_DATA = {block_data_repr}")
        lines.append("")
        lines.append(f"GRAPHICAL_ADJACENCY = {graph_repr}")
        lines.append("")
        lines.append(f"METADATA = {metadata_repr}")
        lines.append("")
        lines.append("")

    def _append_accessors(self, lines: List[str]) -> None:
        """
        Append the public accessor functions.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("def get_block() -> Block:")
        lines.append("    return Block.parse(BLOCK_DATA)")
        lines.append("")
        lines.append("")
        lines.append("def get_graphical_adjacency() -> dict:")
        lines.append("    return GRAPHICAL_ADJACENCY")
        lines.append("")
        lines.append("")
        lines.append("def get_metadata() -> dict:")
        lines.append("    return METADATA")


def _emit_tree_style_module(
    result: DgsRootBlockResult,
    subgraph: DgsBlockSubgraphResult,
    dgs_path: str,
) -> str:
    emitter = DgsBlockTreeModuleEmitter(result=result, subgraph=subgraph, dgs_path=dgs_path)
    return emitter.render()


def _clone_const_or_expr_with_var_factory(value: Const | Expr, vf: VarFactory) -> Const | Expr:
    """
    Clone one expression-like value while recreating constants through the target factory.

    :param value: Source expression-like value.
    :param vf: Target variable factory.
    :returns: Cloned constant or original expression.
    """
    if isinstance(value, Const):
        return vf.add_const(value=value.value, name=value.name)
    else:
        return value


def _collect_one_block_vars(
        block: Block,
        vars_out: Dict[int, Var],
        consts_out: Dict[int, Const],
) -> None:
    """Collect variables and constants owned by one symbolic block.

    :param block: Block inspected without descending into its children.
    :param vars_out: Variable lookup updated by exact UID.
    :param consts_out: Constant lookup updated by exact UID.
    :return: None.
    """
    var_lists = [block.state_vars, block.algebraic_vars, block.diff_vars, block.reformulated_vars, block.in_vars, block.out_vars]
    for var_list in var_lists:
        for var in var_list:
            vars_out[var.uid] = var

    dict_like = [
        block.event_dict,
        block.mode_dict,
        block.init_eqs,
        block.diff_init_eqs,
        block.parameters,
        block.init_values,
        block.discrete_eqs,
        block.post_init_seed_eqs,
        block.boolean_guards,
    ]
    for mapping in dict_like:
        for key, value in mapping.items():
            if isinstance(key, Var):
                vars_out[key.uid] = key
            if isinstance(value, Var):
                vars_out[value.uid] = value
            if isinstance(value, Const):
                consts_out[value.uid] = value
            if isinstance(value, Expr):
                for var in value.get_vars():
                    vars_out[var.uid] = var
            else:
                if isinstance(value, Comparison):
                    for var in value.to_expression().get_vars():
                        vars_out[var.uid] = var
                else:
                    pass

    # Limited-state bounds can depend on signals or parameters that do not
    # otherwise occur in a displayed output equation. Include them in the
    # materialization graph so generated templates never lose those symbols.
    state_var: Var
    limit_pair: Tuple[Expr, Expr]
    for state_var, limit_pair in block.state_limits.items():
        vars_out[state_var.uid] = state_var
        limit_expr: Expr
        for limit_expr in limit_pair:
            limit_var: Var
            for limit_var in limit_expr.get_vars():
                vars_out[limit_var.uid] = limit_var

    expr_lists = [
        block.state_eqs,
        block.algebraic_eqs,
        block.inequalities,
        block.differential_eqs,
    ]
    for expr_list in expr_lists:
        for expr in expr_list:
            if isinstance(expr, Expr):
                for var in expr.get_vars():
                    vars_out[var.uid] = var
            else:
                if isinstance(expr, Comparison):
                    for var in expr.to_expression().get_vars():
                        vars_out[var.uid] = var
                else:
                    pass

    for mapped_var in block.external_mapping.values():
        if mapped_var is None:
            pass
        else:
            vars_out[mapped_var.uid] = mapped_var

    for mapped_var in block.api_obj_mapping.values():
        if mapped_var is None:
            pass
        else:
            vars_out[mapped_var.uid] = mapped_var

    for logic in block.procedural_logic:
        if isinstance(logic, FixedSampleLogic):
            output_var: Var = _find_local_var_by_name(block, logic.output_var_name)
            vars_out[output_var.uid] = output_var
            if isinstance(logic.condition_expr, Comparison):
                for var in logic.condition_expr.to_expression().get_vars():
                    vars_out[var.uid] = var
            else:
                if isinstance(logic.condition_expr, Expr):
                    for var in logic.condition_expr.get_vars():
                        vars_out[var.uid] = var
                else:
                    pass
        else:
            if isinstance(logic, SampledValueLogic):
                output_var = _find_local_var_by_name(block, logic.output_var_name)
                vars_out[output_var.uid] = output_var
                if isinstance(logic.source_expr, Comparison):
                    for var in logic.source_expr.to_expression().get_vars():
                        vars_out[var.uid] = var
                else:
                    if isinstance(logic.source_expr, Expr):
                        for var in logic.source_expr.get_vars():
                            vars_out[var.uid] = var
                    else:
                        pass
            else:
                if isinstance(logic, FlipFlopLogic):
                    output_var = _find_local_var_by_name(block, logic.output_var_name)
                    vars_out[output_var.uid] = output_var
                    for expr_like in [logic.set_expr, logic.reset_expr]:
                        if isinstance(expr_like, Comparison):
                            for var in expr_like.to_expression().get_vars():
                                vars_out[var.uid] = var
                        else:
                            if isinstance(expr_like, Expr):
                                for var in expr_like.get_vars():
                                    vars_out[var.uid] = var
                            else:
                                pass
                else:
                    if isinstance(logic, AnalogFlipFlopLogic):
                        output_var = _find_local_var_by_name(block, logic.output_var_name)
                        vars_out[output_var.uid] = output_var
                        for expr_like in [logic.input_expr, logic.set_expr, logic.reset_expr]:
                            if isinstance(expr_like, Comparison):
                                for var in expr_like.to_expression().get_vars():
                                    vars_out[var.uid] = var
                            else:
                                if isinstance(expr_like, Expr):
                                    for var in expr_like.get_vars():
                                        vars_out[var.uid] = var
                                else:
                                    pass
                    else:
                        if isinstance(logic, PickupDropoffLogic):
                            output_var = _find_local_var_by_name(block, logic.output_var_name)
                            vars_out[output_var.uid] = output_var
                            for expr_like in [logic.bool_expr, logic.pickup_delay_expr, logic.drop_delay_expr]:
                                if isinstance(expr_like, Comparison):
                                    for var in expr_like.to_expression().get_vars():
                                        vars_out[var.uid] = var
                                else:
                                    if isinstance(expr_like, Expr):
                                        for var in expr_like.get_vars():
                                            vars_out[var.uid] = var
                                    else:
                                        pass
                        else:
                            if isinstance(logic, ResetOnRisingEdgeLogic):
                                target_var: Var = _find_local_var_by_name(block, logic.target_var_name)
                                vars_out[target_var.uid] = target_var
                                for expr_like in [logic.reset_expr, logic.value_expr]:
                                    if isinstance(expr_like, Comparison):
                                        for var in expr_like.to_expression().get_vars():
                                            vars_out[var.uid] = var
                                    else:
                                        if isinstance(expr_like, Expr):
                                            for var in expr_like.get_vars():
                                                vars_out[var.uid] = var
                                        else:
                                            pass
                            else:
                                if isinstance(logic, TimeDelayLogic):
                                    output_var = _find_local_var_by_name(block, logic.output_var_name)
                                    vars_out[output_var.uid] = output_var
                                    for expr_like in [logic.source_expr, logic.delay_expr]:
                                        if isinstance(expr_like, Comparison):
                                            for var in expr_like.to_expression().get_vars():
                                                vars_out[var.uid] = var
                                        else:
                                            if isinstance(expr_like, Expr):
                                                for var in expr_like.get_vars():
                                                    vars_out[var.uid] = var
                                            else:
                                                pass
                                else:
                                    if isinstance(logic, MovingAverageLogic):
                                        output_var = _find_local_var_by_name(block, logic.output_var_name)
                                        vars_out[output_var.uid] = output_var
                                        for expr_like in [logic.source_expr, logic.delay_expr, logic.window_expr]:
                                            if isinstance(expr_like, Comparison):
                                                for var in expr_like.to_expression().get_vars():
                                                    vars_out[var.uid] = var
                                            else:
                                                if isinstance(expr_like, Expr):
                                                    for var in expr_like.get_vars():
                                                        vars_out[var.uid] = var
                                                else:
                                                    pass
                                    else:
                                        if isinstance(logic, GradientLimiterLogic):
                                            output_var = _find_local_var_by_name(block, logic.output_var_name)
                                            vars_out[output_var.uid] = output_var
                                            for expr_like in [logic.source_expr, logic.lower_rate_expr, logic.upper_rate_expr]:
                                                if isinstance(expr_like, Comparison):
                                                    for var in expr_like.to_expression().get_vars():
                                                        vars_out[var.uid] = var
                                                else:
                                                    if isinstance(expr_like, Expr):
                                                        for var in expr_like.get_vars():
                                                            vars_out[var.uid] = var
                                                    else:
                                                        pass
                                        else:
                                            if isinstance(logic, HardSaturationLogic):
                                                output_var = _find_local_var_by_name(block, logic.output_var_name)
                                                vars_out[output_var.uid] = output_var
                                                for expr_like in [logic.u_expr, logic.u_min_expr, logic.u_max_expr]:
                                                    if isinstance(expr_like, Comparison):
                                                        for var in expr_like.to_expression().get_vars():
                                                            vars_out[var.uid] = var
                                                    else:
                                                        if isinstance(expr_like, Expr):
                                                            for var in expr_like.get_vars():
                                                                vars_out[var.uid] = var
                                                        else:
                                                            pass
                                            else:
                                                pass

    # Deferred actions can reference parameters or boundary signals used only
    # by the event command. Include them in materialization and humanized-code
    # identifier allocation even when no ordinary DAE equation reads them.
    raw_discrete_actions: object | None = block.__dict__.get(
        "dgs_discrete_event_actions",
        None,
    )
    if isinstance(raw_discrete_actions, list):
        raw_discrete_action: object
        for raw_discrete_action in raw_discrete_actions:
            if isinstance(raw_discrete_action, DgsDiscreteEventAction):
                event_expressions: List[Expr | None] = list([
                    raw_discrete_action.get_symbolic_guard_expression(),
                    raw_discrete_action.get_symbolic_trigger_expression(),
                    raw_discrete_action.get_symbolic_delay_expression(),
                ])
                event_expression: Expr | None
                event_variable: Var
                for event_expression in event_expressions:
                    if event_expression is None:
                        pass
                    else:
                        for event_variable in event_expression.get_vars():
                            vars_out[event_variable.uid] = event_variable
            else:
                pass
    else:
        pass

def _collect_block_vars_recursive(
        block: Block,
        vars_out: Dict[int, Var],
        consts_out: Dict[int, Const],
) -> None:
    """Collect one complete block tree without consuming call-stack depth.

    The historical function name remains stable for its callers, while the
    implementation uses an explicit depth-first stack so deeply nested OEM
    graphical templates can still be emitted as human-readable Python.

    :param block: Root symbolic block.
    :param vars_out: Variable lookup updated by exact UID.
    :param consts_out: Constant lookup updated by exact UID.
    :return: None.
    """
    traversal_stack: List[Block] = list([block])
    visited_block_identities: Set[int] = set()

    while len(traversal_stack) > 0:
        current_block: Block = traversal_stack.pop()
        current_identity: int = id(current_block)
        if current_identity in visited_block_identities:
            pass
        else:
            visited_block_identities.add(current_identity)
            _collect_one_block_vars(
                block=current_block,
                vars_out=vars_out,
                consts_out=consts_out,
            )
            child_block: Block
            for child_block in reversed(current_block.children):
                traversal_stack.append(child_block)


def _clone_block_with_var_factory_recursive(block: Block,
                                            name: str,
                                            created_vars: Dict[int, Var],
                                            var_mapping: SymbolReplacementMap,
                                            vf: VarFactory) -> Block:
    """
    Clone one block recursively using the target variable factory and remapping.

    :param block: Source block.
    :param name: Runtime suffix.
    :param created_vars: Created variables by source uid.
    :param var_mapping: Symbol remapping used for substitution.
    :param vf: Target variable factory.
    :returns: Cloned block.
    """
    cloned = Block(name=f"{block.name}_{name}")
    cloned.state_vars = [created_vars[v.uid] for v in block.state_vars]
    cloned.algebraic_vars = [created_vars[v.uid] for v in block.algebraic_vars]
    cloned.diff_vars = [created_vars[v.uid] for v in block.diff_vars]
    cloned.in_vars = [created_vars[v.uid] for v in block.in_vars]
    cloned.out_vars = [created_vars[v.uid] for v in block.out_vars]

    cloned.state_eqs = [expr.subs(var_mapping) for expr in block.state_eqs]
    cloned.state_limits = dict()
    state_var: Var
    limit_pair: Tuple[Expr, Expr]
    for state_var, limit_pair in block.state_limits.items():
        cloned.state_limits[created_vars[state_var.uid]] = (
            limit_pair[0].subs(var_mapping),
            limit_pair[1].subs(var_mapping),
        )
    cloned.algebraic_eqs = [expr.subs(var_mapping) for expr in block.algebraic_eqs]
    cloned.differential_eqs = [expr.subs(var_mapping) for expr in block.differential_eqs]

    cloned.event_dict = dict()
    key_var: Var
    value_expr: Expr | Const
    for key_var, value_expr in block.event_dict.items():
        cloned.event_dict[created_vars[key_var.uid]] = _clone_const_or_expr_with_var_factory(
            value_expr.subs(var_mapping) if isinstance(value_expr, Expr) else value_expr,
            vf,
        )

    cloned.mode_dict = dict()
    for key_var, value_expr in block.mode_dict.items():
        cloned.mode_dict[created_vars[key_var.uid]] = value_expr.subs(var_mapping) if isinstance(value_expr, Expr) else value_expr

    cloned.init_eqs = dict()
    for key_var, value_expr in block.init_eqs.items():
        cloned.init_eqs[created_vars[key_var.uid]] = value_expr.subs(var_mapping)

    # Late startup assignments are executable symbolic structure, not optional
    # catalogue decoration. Remap them with the same per-device variables so
    # native BlkSum and physical adapter closures survive mass materialization.
    cloned.post_init_seed_eqs = dict()
    for key_var, value_expr in block.post_init_seed_eqs.items():
        cloned.post_init_seed_eqs[created_vars[key_var.uid]] = (
            value_expr.subs(var_mapping)
        )

    string_list_metadata_names: Tuple[str, ...] = (
        "dgs_disconnected_graphical_input_names",
        "dgs_unresolved_graphical_input_names",
        "runtime_post_update_helper_names",
        "runtime_equipment_shell_sync_names",
        "runtime_measurement_shell_sync_names",
        "startup_final_init_replay_var_names",
        "startup_initial_reduced_polish_var_names",
    )
    string_list_metadata_name: str
    raw_string_list_metadata: object | None
    metadata_item: object
    cloned_metadata_items: List[str]
    for string_list_metadata_name in string_list_metadata_names:
        raw_string_list_metadata = block.__dict__.get(
            string_list_metadata_name,
            None,
        )
        if isinstance(raw_string_list_metadata, list):
            cloned_metadata_items = list()
            for metadata_item in raw_string_list_metadata:
                if isinstance(metadata_item, str):
                    cloned_metadata_items.append(metadata_item)
                else:
                    pass
            else:
                pass
            cloned.__dict__[string_list_metadata_name] = cloned_metadata_items
        else:
            pass
    else:
        pass

    raw_astable_integration: object | None = block.__dict__.get(
        "dgs_powerfactory_astable_integration",
        None,
    )
    if isinstance(raw_astable_integration, bool):
        cloned.__dict__["dgs_powerfactory_astable_integration"] = (
            raw_astable_integration
        )
    else:
        pass

    raw_equipment_shell_uids: object | None = block.__dict__.get(
        "runtime_equipment_shell_sync_var_uids",
        None,
    )
    if isinstance(raw_equipment_shell_uids, list):
        cloned_equipment_shell_uids: List[int] = list()
        raw_equipment_shell_uid: object
        for raw_equipment_shell_uid in raw_equipment_shell_uids:
            if (
                    isinstance(raw_equipment_shell_uid, int)
                    and raw_equipment_shell_uid in created_vars
            ):
                cloned_equipment_shell_uids.append(
                    created_vars[raw_equipment_shell_uid].uid
                )
            else:
                pass
        else:
            pass
        cloned.__dict__["runtime_equipment_shell_sync_var_uids"] = (
            cloned_equipment_shell_uids
        )
    else:
        pass

    raw_runtime_helper_uids: object | None = block.__dict__.get(
        "runtime_post_update_helper_var_uids",
        None,
    )
    if isinstance(raw_runtime_helper_uids, list):
        cloned_runtime_helper_uids: List[int] = list()
        raw_runtime_helper_uid: object
        for raw_runtime_helper_uid in raw_runtime_helper_uids:
            if (
                    isinstance(raw_runtime_helper_uid, int)
                    and raw_runtime_helper_uid in created_vars
            ):
                cloned_runtime_helper_uids.append(
                    created_vars[raw_runtime_helper_uid].uid
                )
            else:
                pass
        else:
            pass
        cloned.__dict__["runtime_post_update_helper_var_uids"] = (
            cloned_runtime_helper_uids
        )
    else:
        pass

    raw_explicit_initialization_uids: object | None = block.__dict__.get(
        "dgs_explicit_initialization_uids",
        None,
    )
    if isinstance(raw_explicit_initialization_uids, set):
        cloned_explicit_initialization_uids: Set[int] = set()
        raw_explicit_uid: object
        for raw_explicit_uid in raw_explicit_initialization_uids:
            if isinstance(raw_explicit_uid, int) and raw_explicit_uid in created_vars:
                cloned_explicit_initialization_uids.add(
                    created_vars[raw_explicit_uid].uid
                )
            else:
                pass
        cloned.__dict__["dgs_explicit_initialization_uids"] = (
            cloned_explicit_initialization_uids
        )
    else:
        pass

    cloned.diff_init_eqs = dict()
    for key_var, value_expr in block.diff_init_eqs.items():
        cloned.diff_init_eqs[created_vars[key_var.uid]] = value_expr.subs(var_mapping)

    cloned.parameters = dict()
    for key_var, value_expr in block.parameters.items():
        cloned.parameters[created_vars[key_var.uid]] = _clone_const_or_expr_with_var_factory(value_expr, vf)

    cloned.init_values = dict()
    for key_var, value_expr in block.init_values.items():
        cloned.init_values[created_vars[key_var.uid]] = _clone_const_or_expr_with_var_factory(value_expr, vf)
    cloned.procedural_logic = clone_procedural_logic_entries(block.procedural_logic, var_mapping)
    raw_discrete_actions: object | None = block.__dict__.get(
        "dgs_discrete_event_actions",
        None,
    )
    if isinstance(raw_discrete_actions, list):
        cloned_actions: List[DgsDiscreteEventAction] = list()
        raw_discrete_action: object
        for raw_discrete_action in raw_discrete_actions:
            if isinstance(raw_discrete_action, DgsDiscreteEventAction):
                cloned_actions.append(
                    _substitute_dgs_discrete_event_symbolic_expressions(
                        action=raw_discrete_action,
                        var_mapping=var_mapping,
                    )
                )
            else:
                pass
        cloned.__dict__["dgs_discrete_event_actions"] = cloned_actions
    else:
        pass
    cloned.children = [
        _clone_block_with_var_factory_recursive(child, name, created_vars, var_mapping, vf)
        for child in block.children
    ]
    return cloned


def materialize_block_with_var_factory(block_data: dict | Block, vf: VarFactory, name: str) -> Block:
    """
    Recreate a serialized block using the target VarFactory and a runtime suffix.

    :param block_data: Serialized block dict or an already-built Block.
    :param vf: VarFactory-like object exposing add_var/add_diff_var/add_const.
    :param name: Runtime suffix used to make names unique.
    :return: Materialized Block.
    """
    source_block = Block.parse(block_data) if isinstance(block_data, dict) else block_data.copy()

    vars_out: Dict[int, Var] = dict()
    consts_out: Dict[int, Const] = dict()
    _collect_block_vars_recursive(source_block, vars_out, consts_out)

    var_mapping: SymbolReplacementMap = dict()
    created_vars: Dict[int, Var] = dict()

    non_diff_vars = [var for var in vars_out.values() if var.base_var is None]
    diff_vars = [var for var in vars_out.values() if var.base_var is not None]

    for var in sorted(non_diff_vars, key=_var_name_sort_key):
        new_var = vf.add_var(f"{var.name}_{name}")
        created_vars[var.uid] = new_var
        var_mapping[var] = new_var
        var_mapping[var.name] = new_var

    for var in sorted(diff_vars, key=_var_name_sort_key):
        base_var = created_vars[var.base_var.uid]
        new_var = vf.add_diff_var(f"{var.name}_{name}", base_var=base_var)
        created_vars[var.uid] = new_var
        var_mapping[var] = new_var
        var_mapping[var.name] = new_var

    for const in consts_out.values():
        new_const = vf.add_const(value=const.value, name=const.name)
        var_mapping[const] = new_const

    return _clone_block_with_var_factory_recursive(source_block, name, created_vars, var_mapping, vf)


def _build_symbol_table(
    blkdef: BlkDef,
    shared_signals: Dict[str, Var],
) -> Tuple[Dict[str, Var], List[Var], Dict[str, Var], Dict[str, Var], Dict[str, Var]]:
    symbol_table: Dict[str, Var] = dict()
    runtime_input_names: List[str] = _build_blkdef_runtime_input_names(
        blkdef=blkdef,
    )
    shared_names: Set[str] = set(runtime_input_names + blkdef.outputs)

    for name in shared_names:
        if name not in shared_signals:
            shared_signals[name] = Var(name=name)
        symbol_table[name] = shared_signals[name]

    # Internal algebraic symbols belong to one concrete block instance, not to the whole composite signal namespace.
    # Sharing them across repeated direct instances collapses distinct controls into one variable and over-constrains
    # the flattened RMS system.

    state_vars: List[Var] = list()
    state_var_map: Dict[str, Var] = dict()
    diff_var_map: Dict[str, Var] = dict()
    param_var_map: Dict[str, Var] = dict()

    # PowerFactory exposes helper signals that are neither public pins nor
    # states through ``sInternal``. They still belong to the concrete block
    # instance and must exist before any right-hand side is parsed. Omitting
    # them silently discarded otherwise valid graphical primitives such as
    # limited-PI anti-windup guards and their saturated output equations.
    internal_name: str
    for internal_name in blkdef.internals:
        if internal_name not in symbol_table:
            symbol_table[internal_name] = Var(
                name=f"{blkdef.loc_name}__{internal_name}"
            )
        else:
            # A vendor definition may repeat a public/state name in its
            # internal declaration. The more specific public contract wins.
            pass

    for state_name in blkdef.states:
        state_var = Var(name=f"{blkdef.loc_name}__{state_name}")
        diff_var = Var(name=f"d_{blkdef.loc_name}__{state_name}", base_var=state_var)
        symbol_table[state_name] = state_var
        state_vars.append(state_var)
        state_var_map[state_name] = state_var
        diff_var_map[state_name] = diff_var

    for param_name in blkdef.params:
        param_var = Var(name=f"{blkdef.loc_name}__{param_name}")
        symbol_table[param_name] = param_var
        param_var_map[param_name] = param_var

    return symbol_table, state_vars, state_var_map, diff_var_map, param_var_map


def _parse_blkdef(blkdef: BlkDef,
                  shared_signals: Dict[str, Var],
                  simulation_domain: str = "emt") -> ParsedDgsBlockDefinition:
    symbol_table, state_vars, state_var_map, diff_var_map, _param_var_map = _build_symbol_table(blkdef, shared_signals)
    _predeclare_statement_lhs_symbols(blkdef, symbol_table)
    parser = DgsExpressionParser(
        symbol_table,
        block_name=blkdef.loc_name,
        simulation_domain=simulation_domain,
        dsl_level=blkdef.level,
    )

    state_rhs: Dict[str, Expr] = dict()
    algebraic_rhs: Dict[str, Expr] = dict()
    init_rhs: Dict[str, Expr] = dict()
    inc0_signal_names: Set[str] = set()
    fixed_limit_specs: Dict[str, str] = dict()
    unsupported_lines: List[str] = list()
    discrete_event_actions: List[DgsDiscreteEventAction] = list()
    signal_dependencies: Dict[str, Set[str]] = dict()

    for stmt in _split_equation_statements(blkdef.equations_raw):
        stmt_kind, lhs_hint = classify_dgs_statement(stmt)

        if stmt_kind == 'ignored':
            pass
        elif stmt_kind == 'procedural':
            try:
                parser.parse_procedural_statement(stmt)
            except UnsupportedDgsExpression:
                unsupported_lines.append(stmt)
            else:
                signal_dependencies[stmt] = set()
        elif stmt_kind == "discrete_event":
            discrete_action: DgsDiscreteEventAction | None = (
                parse_dgs_discrete_event_statement(statement=stmt)
            )
            if discrete_action is None:
                unsupported_lines.append(stmt)
            else:
                executable_action: DgsDiscreteEventAction = (
                    _attach_dgs_discrete_event_symbolic_expressions(
                        action=discrete_action,
                        parser=parser,
                    )
                )
                discrete_event_actions.append(executable_action)
                signal_dependencies[stmt] = set()
        elif stmt_kind == 'limfix':
            declaration = _extract_limfix_spec(stmt)
            if declaration is None:
                unsupported_lines.append(stmt)
            else:
                parameter_name, literal_spec = declaration
                fixed_limit_specs[parameter_name] = literal_spec
                signal_dependencies[f"limfix({parameter_name})"] = set()
        else:
            rhs_text: str | None = _extract_rhs_text_for_support_report(stmt_kind, stmt)

            if rhs_text is None:
                unsupported_lines.append(stmt)
            else:
                lhs_name: str | None = lhs_hint
                _ensure_support_report_lhs_symbol(lhs_name, blkdef, symbol_table, parser)

                try:
                    rhs_expr = parser.parse(rhs_text)
                except UnsupportedDgsExpression:
                    unsupported_lines.append(stmt)
                else:
                    if isinstance(rhs_expr, Comparison):
                        rhs_expr = rhs_expr.to_expression()
                    else:
                        pass

                    if stmt_kind == 'state':
                        if isinstance(rhs_expr, Expr):
                            assert lhs_name is not None
                            state_rhs[lhs_name] = rhs_expr
                            signal_dependencies[lhs_name] = _build_expr_signal_name_set(rhs_expr)
                        else:
                            unsupported_lines.append(stmt)
                    elif stmt_kind in {'inc', 'inc0'}:
                        assert lhs_name is not None
                        if stmt_kind == 'inc0' and lhs_name in init_rhs:
                            pass
                        else:
                            init_rhs[lhs_name] = rhs_expr
                            if stmt_kind == 'inc0':
                                inc0_signal_names.add(lhs_name)
                            else:
                                # A later ``inc()`` is the authoritative
                                # initialization assignment for this signal.
                                inc0_signal_names.discard(lhs_name)
                            signal_dependencies[f"{stmt_kind}({lhs_name})"] = _build_expr_signal_name_set(rhs_expr)
                    elif stmt_kind == 'algebraic':
                        assert lhs_name is not None
                        algebraic_rhs[lhs_name] = rhs_expr
                        signal_dependencies[lhs_name] = _build_expr_signal_name_set(rhs_expr)
                    else:
                        unsupported_lines.append(stmt)

    # ``limstate`` is commonly read by a later algebraic assignment, while its
    # differential equation appears earlier in the DGS source. Preserve the
    # collected bounds as an explicit integration contract after the complete
    # block has been parsed. The time integrator, not the symbolic derivative,
    # owns projection at a crossing because only it knows the accepted previous
    # state and the effective time step.
    parser.apply_explicit_latch_initialization_defaults(
        algebraic_rhs=algebraic_rhs,
        init_rhs=init_rhs,
    )
    state_limits_by_uid: Dict[int, Tuple[Expr, Expr]] = (
        parser.state_limits_by_uid
    )

    return ParsedDgsBlockDefinition(
        blkdef=blkdef,
        symbol_table=dict(symbol_table),
        state_rhs=state_rhs,
        state_limits_by_uid=state_limits_by_uid,
        algebraic_rhs=algebraic_rhs,
        init_rhs=init_rhs,
        inc0_signal_names=inc0_signal_names,
        mode_dict=dict(parser.procedural_mode_defaults),
        procedural_logic=list(parser.procedural_logic_entries),
        discrete_event_actions=discrete_event_actions,
        fixed_limit_specs=fixed_limit_specs,
        unsupported_lines=unsupported_lines,
        signal_dependencies=signal_dependencies,
        procedural_dependency_names=parser.procedural_dependency_names,
    )


def _attach_dgs_discrete_event_symbolic_expressions(
        action: DgsDiscreteEventAction,
        parser: DgsExpressionParser,
) -> DgsDiscreteEventAction:
    """Parse one deferred action's guard, trigger and delay in block scope.

    :param action: Raw typed action produced from the PowerFactory statement.
    :param parser: Existing block-scoped expression parser and symbol table.
    :return: Executable action, or the original action if one expression is unsupported.
    """

    try:
        parsed_guard: Expr | Comparison = parser.parse(
            action.get_trigger_signal_name()
        )
        parsed_trigger: Expr | Comparison = parser.parse(
            action.get_trigger_expression()
        )
        parsed_delay: Expr | Comparison = parser.parse(
            action.get_delay_expression()
        )
    except UnsupportedDgsExpression:
        # Partial model support is deliberate: retain the original action for
        # diagnostics even when this one event cannot yet execute.
        result: DgsDiscreteEventAction = action
    else:
        guard_expression: Expr = _comparison_to_expr(parsed_guard)
        trigger_expression: Expr = _comparison_to_expr(parsed_trigger)
        delay_expression: Expr = _comparison_to_expr(parsed_delay)
        result = action.with_symbolic_expressions(
            guard_expression=guard_expression,
            trigger_expression=trigger_expression,
            delay_expression=delay_expression,
        )

    return result


def _substitute_dgs_discrete_event_symbolic_expressions(
        action: DgsDiscreteEventAction,
        var_mapping: SymbolReplacementMap,
) -> DgsDiscreteEventAction:
    """Rebind event expressions from a generic ``BlkDef`` to one instance.

    :param action: Parsed generic block action.
    :param var_mapping: Exact generic-to-instance symbolic substitution map.
    :return: Action whose expressions reference only materialized instance UIDs.
    """

    guard_expression: Expr | None = action.get_symbolic_guard_expression()
    trigger_expression: Expr | None = action.get_symbolic_trigger_expression()
    delay_expression: Expr | None = action.get_symbolic_delay_expression()
    if (
            guard_expression is None
            or trigger_expression is None
            or delay_expression is None
    ):
        result: DgsDiscreteEventAction = action
    else:
        result = action.with_symbolic_expressions(
            guard_expression=guard_expression.subs(var_mapping),
            trigger_expression=trigger_expression.subs(var_mapping),
            delay_expression=delay_expression.subs(var_mapping),
        )

    return result


def _score_root_candidate(blkdef: ParsedDgsBlockDefinition) -> Tuple[int, int, int, int, int]:
    return (
        len(_build_blkdef_runtime_input_names(blkdef=blkdef.blkdef)),
        len(blkdef.blkdef.outputs),
        len(blkdef.blkdef.states),
        len(blkdef.algebraic_rhs) + len(blkdef.state_rhs),
        len(blkdef.blkdef.internals),
    )


def _select_root_element(
        circuit: DgsCircuit,
        parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
        root_name: str | None,
        root_typ_id: str | None,
        root_dgs_id: str | None = None,
) -> Tuple[ElmComp, ParsedDgsBlockDefinition]:
    candidates: List[ElmComp] = list(circuit.elmcomps)
    if root_dgs_id is not None:
        candidates = [elm for elm in candidates if str(elm.ID).strip() == str(root_dgs_id).strip()]
    else:
        pass

    if root_name is not None:
        candidates = [elm for elm in candidates if elm.loc_name == root_name]
    else:
        pass

    if root_typ_id is not None:
        candidates = [elm for elm in candidates if str(elm.typ_id).strip() == str(root_typ_id).strip()]
    else:
        pass

    if not candidates:
        raise ValueError("No matching ElmComp root candidate found in the DGS file")

    best_element: ElmComp | None = None
    best_block: ParsedDgsBlockDefinition | None = None
    best_score: Tuple[int, int, int, int, int] | None = None

    for elm in candidates:
        blk = parsed_blocks.get(str(elm.typ_id).strip())
        if blk is None:
            pass
        else:
            score = _score_root_candidate(blk)
            if best_score is None or score > best_score:
                best_element = elm
                best_block = blk
                best_score = score
            else:
                pass

    if best_element is None or best_block is None:
        raise ValueError("No ElmComp candidate could be resolved to a parsed BlkDef")

    return best_element, best_block


def _collect_reachable_blocks(root_blkdef: ParsedDgsBlockDefinition, parsed_blocks: Dict[str, ParsedDgsBlockDefinition]) -> Dict[str, ParsedDgsBlockDefinition]:
    root_input_names: List[str] = _build_blkdef_runtime_input_names(
        blkdef=root_blkdef.blkdef,
    )
    frontier: Set[str] = set(
        root_input_names
        + root_blkdef.blkdef.outputs
        + root_blkdef.blkdef.internals
    )
    reachable: Dict[str, ParsedDgsBlockDefinition] = dict()
    changed = True

    while changed:
        changed = False
        for block_id, parsed in parsed_blocks.items():
            if block_id == root_blkdef.blkdef.ID or block_id in reachable:
                pass
            else:
                parsed_input_names: List[str] = _build_blkdef_runtime_input_names(
                    blkdef=parsed.blkdef,
                )
                io_names = set(
                    parsed_input_names
                    + parsed.blkdef.outputs
                    + parsed.blkdef.internals
                )
                if io_names & frontier:
                    reachable[block_id] = parsed
                    frontier |= io_names
                    changed = True
                else:
                    pass

    return reachable

def _collect_internal_candidate_blocks(
    selected_block: ParsedDgsBlockDefinition,
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
) -> Dict[str, ParsedDgsBlockDefinition]:
    """
    Collect candidate internal blocks for a selected composite block using only
    signal-name overlap and dependency closure.

    :param selected_block: Selected composite parsed block.
    :param parsed_blocks: All parsed blocks.
    :return: Internal candidate blocks keyed by block identifier.
    """
    seed_signals: Set[str] = set()
    seed_signals |= set(
        _build_blkdef_runtime_input_names(blkdef=selected_block.blkdef)
    )
    seed_signals |= set(selected_block.blkdef.outputs)
    seed_signals |= set(selected_block.blkdef.internals)

    reachable: Dict[str, ParsedDgsBlockDefinition] = dict()
    frontier_signals: Set[str] = set(seed_signals)

    changed: bool = True
    while changed:
        changed = False

        for block_id, parsed in parsed_blocks.items():
            if block_id == selected_block.blkdef.ID:
                pass
            elif block_id in reachable:
                pass
            else:
                block_signals: Set[str] = set()
                block_signals |= set(
                    _build_blkdef_runtime_input_names(blkdef=parsed.blkdef)
                )
                block_signals |= set(parsed.blkdef.outputs)
                block_signals |= set(parsed.blkdef.internals)

                if len(block_signals & frontier_signals) > 0:
                    reachable[block_id] = parsed
                    frontier_signals |= block_signals
                    changed = True
                else:
                    pass

    return reachable

def _score_internal_candidate(
    selected_block: ParsedDgsBlockDefinition,
    candidate_block: ParsedDgsBlockDefinition,
) -> int:
    """
    Score how likely a block is to belong to the internal structure of a selected block.

    :param selected_block: Selected composite block.
    :param candidate_block: Candidate internal block.
    :return: Integer score.
    """
    selected_inputs: Set[str] = set(
        _build_blkdef_runtime_input_names(blkdef=selected_block.blkdef)
    )
    selected_outputs: Set[str] = set(selected_block.blkdef.outputs)
    selected_internals: Set[str] = set(selected_block.blkdef.internals)

    candidate_inputs: Set[str] = set(
        _build_blkdef_runtime_input_names(blkdef=candidate_block.blkdef)
    )
    candidate_outputs: Set[str] = set(candidate_block.blkdef.outputs)
    candidate_internals: Set[str] = set(candidate_block.blkdef.internals)

    score: int = 0

    score += 4 * len(candidate_inputs & selected_inputs)
    score += 4 * len(candidate_outputs & selected_outputs)
    score += 3 * len(candidate_outputs & selected_internals)
    score += 3 * len(candidate_inputs & selected_internals)
    score += 2 * len(candidate_internals & selected_internals)
    score += 1 * len(candidate_internals & selected_inputs)
    score += 1 * len(candidate_internals & selected_outputs)

    return score

def _filter_internal_candidates(
    selected_block: ParsedDgsBlockDefinition,
    candidates: Dict[str, ParsedDgsBlockDefinition],
    min_score: int = 2,
) -> Dict[str, ParsedDgsBlockDefinition]:
    """
    Filter candidate internal blocks using signal-overlap scoring.

    :param selected_block: Selected composite block.
    :param candidates: Candidate blocks.
    :param min_score: Minimum score to keep.
    :return: Filtered candidate blocks.
    """
    filtered: Dict[str, ParsedDgsBlockDefinition] = dict()

    for block_id, parsed in candidates.items():
        score: int = _score_internal_candidate(selected_block, parsed)
        if score >= min_score:
            filtered[block_id] = parsed
        else:
            pass

    return filtered

def _parameter_values_by_type_id(entries: Iterable[ElmCompInstanceEntry],
                                 keep_first_on_duplicates: bool = False) -> Dict[str, DgsParameterValues]:
    """
    Build a unique parameter lookup keyed by block-definition identifier.

    :param entries: Direct instance entries extracted from one ElmComp.
    :param keep_first_on_duplicates: Keep the first occurrence when one type appears several times.
    :return: Parameter values keyed by BlkDef identifier when the type appears only once.
    """
    parameter_values_by_type: Dict[str, DgsParameterValues] = dict()
    duplicated_type_ids: Set[str] = set()

    for entry in entries:
        # We only propagate values when one block type appears once inside the parent ElmComp.
        if entry.type_id is None or len(entry.parameter_values) == 0:
            pass
        else:
            if entry.type_id in parameter_values_by_type:
                if keep_first_on_duplicates:
                    pass
                else:
                    duplicated_type_ids.add(entry.type_id)
            else:
                parameter_values_by_type[entry.type_id] = dict(entry.parameter_values)

    if keep_first_on_duplicates:
        pass
    else:
        for type_id in duplicated_type_ids:
            parameter_values_by_type.pop(type_id, None)

    return parameter_values_by_type


def _resolve_graphical_blkref_parameter_values(
        reference: BlkRef,
        definition: BlkDef,
        parent_parameter_values: DgsParameterValues,
        fallback_parameter_values: DgsParameterValues | None,
) -> DgsParameterValues:
    """Resolve one graphical primitive's parameter aliases against its parent.

    PowerFactory graphical references store parameter bindings positionally.
    Tokens may be numeric literals or names of parameters owned by the enclosing
    ``ElmDsl``. Upper/lower limiter parameters use separate vectors, just as
    their graphical input pins use separate connector categories.

    :param reference: Concrete graphical ``BlkRef`` occurrence.
    :param definition: Referenced primitive definition.
    :param parent_parameter_values: Numeric values of the enclosing DSL instance.
    :param fallback_parameter_values: Optional exact nested-instance values.
    :return: Concrete primitive parameter values keyed by definition name.
    """
    resolved_values: DgsParameterValues = dict(
        fallback_parameter_values or dict()
    )
    regular_parameter_names: List[str] = list()
    parameter_name: str
    for parameter_name in definition.params:
        if (
                parameter_name in definition.upper_limit_params
                or parameter_name in definition.lower_limit_params
        ):
            pass
        else:
            regular_parameter_names.append(parameter_name)
    else:
        pass

    parameter_groups: List[Tuple[List[str], List[str | None]]] = list([
        (regular_parameter_names, reference.params),
        (
            definition.upper_limit_params,
            reference.upper_limit_parameter_values,
        ),
        (
            definition.lower_limit_params,
            reference.lower_limit_parameter_values,
        ),
    ])
    parameter_group: Tuple[List[str], List[str | None]]
    for parameter_group in parameter_groups:
        parameter_names: List[str] = parameter_group[0]
        parameter_tokens: List[str | None] = parameter_group[1]
        parameter_index: int
        for parameter_index in range(len(parameter_names)):
            if parameter_index >= len(parameter_tokens):
                pass
            else:
                parameter_token: str | None = parameter_tokens[parameter_index]
                if parameter_token is None:
                    pass
                else:
                    parent_value: DgsParameterValue = (
                        parent_parameter_values.get(parameter_token, None)
                    )
                    if parent_value is not None:
                        resolved_value: DgsParameterValue = parent_value
                    else:
                        try:
                            resolved_value = float(
                                parameter_token.replace(",", ".")
                            )
                        except ValueError:
                            # Keep the unresolved binding explicit. A later
                            # validator can report the exact primitive/name;
                            # inventing a numeric fallback would change physics.
                            resolved_value = None
                    resolved_values[parameter_names[parameter_index]] = (
                        resolved_value
                    )
        else:
            pass
    else:
        pass
    return resolved_values


def _build_clipped_linear_lookup_expression(
        input_var: Var,
        x_points: List[float],
        y_points: List[float],
) -> Expr:
    """Build a clipped piecewise-linear expression from explicit points.

    The DGS ``lapprox`` helper is a data-dependent primitive. Open-standard
    tables whose protected PowerFactory defaults are omitted from ``oarrmat``
    can still be represented exactly once their canonical point set has been
    identified from the graphical parameter binding.

    :param input_var: Lookup abscissa.
    :param x_points: Strictly increasing abscissa points.
    :param y_points: Ordinate values aligned with ``x_points``.
    :return: Symbolic clipped linear interpolation expression.
    """
    point_count: int = len(x_points)
    point_index: int
    clamped_input: Expr
    result_expression: Expr = Const(0.0)

    if point_count == len(y_points) and point_count >= 2:
        pass
    else:
        raise ValueError("A lookup table requires at least two aligned points")

    for point_index in range(point_count - 1):
        if x_points[point_index + 1] > x_points[point_index]:
            pass
        else:
            raise ValueError("Lookup abscissa points must be strictly increasing")
    else:
        pass

    # PowerFactory's standard VDL blocks retain the endpoint value outside the
    # declared range, so clamp before selecting the active linear segment.
    clamped_input = hard_sat(
        input_var,
        Const(float(x_points[0])),
        Const(float(x_points[point_count - 1])),
    )
    for point_index in range(point_count - 1):
        x_left: Const = Const(float(x_points[point_index]))
        x_right: Const = Const(float(x_points[point_index + 1]))
        y_left: Const = Const(float(y_points[point_index]))
        y_right: Const = Const(float(y_points[point_index + 1]))
        segment_expression: Expr = y_left + (
            (y_right - y_left)
            * (clamped_input - x_left)
            / (x_right - x_left)
        )
        lower_selector: Expr = Comparison(
            lhs=clamped_input,
            op=CmpOp.GE,
            rhs=x_left,
        ).to_expression()
        if point_index == point_count - 2:
            segment_selector: Expr = lower_selector
        else:
            upper_selector: Expr = Comparison(
                lhs=clamped_input,
                op=CmpOp.LT,
                rhs=x_right,
            ).to_expression()
            segment_selector = lower_selector * upper_selector
        result_expression = result_expression + segment_selector * segment_expression
    else:
        pass
    return result_expression


def _restore_open_standard_vdl_lookup(
        block: Block,
        parsed: ParsedDgsBlockDefinition,
        reference: BlkRef,
) -> bool:
    """Restore one protected WECC VDL lookup from its canonical DGS binding.

    PowerFactory exports the public ``lapprox`` contract of its protected WECC
    VDL primitive but omits the built-in default array from ``oarrmat``. The
    enclosing graphical reference still exposes the canonical array role, so
    the corresponding open-standard table can be materialized without using
    equipment names, FIDs, or GB-specific values.

    :param block: Materialized graphical child updated in place.
    :param parsed: Parsed VDL block definition.
    :param reference: Exact graphical occurrence and parent-parameter binding.
    :return: ``True`` when an open-standard lookup was restored.
    """
    definition: BlkDef = parsed.blkdef
    unsupported_lines: List[str] = list(parsed.unsupported_lines)
    parameter_tokens: List[str | None] = list(reference.params)
    contract_matches: bool = (
        len(block.algebraic_eqs) == 0
        and definition.inputs == list(["yi"])
        and definition.outputs == list(["yo"])
        and definition.params in (list(["array_vdl"]), list(["oarray_vdl"]))
        and len(unsupported_lines) == 1
        and "lapprox" in unsupported_lines[0]
        and len(parameter_tokens) == 1
    )
    if contract_matches:
        pass
    else:
        return False

    source_token: str | None = parameter_tokens[0]
    if source_token in {"array_vdl1", "array_vdl2", "oarray_vdlq"}:
        # The published REEC_C curves and the REEC_D reactive-current curve
        # retain unity across their complete voltage range.
        lookup_expression: Expr = Const(1.0)
        lookup_role: str = str(source_token)
    elif source_token == "oarray_vdlp":
        # The published REEC_D active-current curve is shared by the standard
        # wind/PV family and is already shipped by VeraGrid's WECC templates.
        x_points: List[float] = list([0.0, 0.5, 0.9, 1.1])
        y_points: List[float] = list([0.0, 0.0, 1.0, 1.0])
        lookup_expression = _build_clipped_linear_lookup_expression(
            input_var=block.in_vars[0],
            x_points=x_points,
            y_points=y_points,
        )
        lookup_role = source_token
    else:
        # Unknown or explicitly customized arrays remain partial until their
        # Matrix rows are present in the DGS; no physical fallback is invented.
        return False

    output_var: Var = block.out_vars[0]
    block.algebraic_vars = list([output_var])
    block.algebraic_eqs = list([output_var - lookup_expression])
    # PowerFactory evaluates the protected lookup at initialization as well as
    # at runtime.  The restored standard equation therefore owns the same
    # directed t=0 seed; otherwise its default zero survives until global
    # Newton and introduces a fictitious current-command discontinuity.
    block.init_eqs = dict([(output_var, lookup_expression)])
    block.post_init_seed_eqs = dict([(output_var, lookup_expression)])
    block.event_dict = dict()
    block.__dict__["dgs_open_standard_lookup_role"] = lookup_role
    return True


def _get_dgs_block_symbol_table(block: Block) -> Dict[str, Var]:
    """Return the raw-name symbolic table retained during DGS materialization.

    :param block: Materialized DGS block.
    :return: Valid raw DGS names mapped to their runtime variables.
    """
    result: Dict[str, Var] = dict()
    raw_symbol_table: object | None = block.__dict__.get(
        "dgs_symbol_table",
        None,
    )
    raw_name: object
    raw_var: object

    if isinstance(raw_symbol_table, dict):
        for raw_name, raw_var in raw_symbol_table.items():
            if isinstance(raw_name, str) and isinstance(raw_var, Var):
                result[raw_name] = raw_var
            else:
                pass
        else:
            pass
    else:
        pass
    return result


def _connect_graphical_blkref_owned_aliases(
        reference: BlkRef,
        definition: BlkDef,
        parent_block: Block,
        child_block: Block,
) -> None:
    """Apply positional ``sStates`` and ``sIntern`` graphical bindings.

    PowerFactory stores state and internal-signal ownership on each ``BlkRef``
    separately from ordinary ``BlkSig`` cables. Ignoring those vectors creates
    duplicate variables with the same display label and disconnects child
    initialization equations from their parent DSL model.

    :param reference: Concrete graphical primitive occurrence.
    :param definition: Referenced primitive definition.
    :param parent_block: Materialized enclosing DSL block.
    :param child_block: Materialized graphical primitive updated in place.
    :return: None.
    """
    parent_symbols: Dict[str, Var] = _get_dgs_block_symbol_table(
        block=parent_block,
    )
    child_symbols: Dict[str, Var] = _get_dgs_block_symbol_table(
        block=child_block,
    )
    alias_groups: List[Tuple[List[str], List[str]]] = list([
        (definition.states, reference.states),
        (definition.internals, reference.internals),
    ])
    alias_group: Tuple[List[str], List[str]]
    definition_names: List[str]
    reference_names: List[str]
    alias_index: int

    for alias_group in alias_groups:
        definition_names = alias_group[0]
        reference_names = alias_group[1]
        for alias_index in range(len(definition_names)):
            if alias_index >= len(reference_names):
                pass
            else:
                definition_name: str = definition_names[alias_index]
                reference_name: str = reference_names[alias_index].strip()
                parent_var: Var | None = parent_symbols.get(
                    reference_name,
                    None,
                )
                child_var: Var | None = child_symbols.get(
                    definition_name,
                    None,
                )
                if (
                        reference_name in {"", "*"}
                        or parent_var is None
                        or child_var is None
                ):
                    pass
                else:
                    child_is_produced: bool = (
                        child_var in child_block.state_vars
                        or child_var in child_block.algebraic_vars
                    )
                    child_block.update_model(child_var, parent_var)
                    child_symbols[definition_name] = parent_var

                    # An init-only parent internal consumed by a child is a
                    # held runtime signal in PowerFactory. Promote its exact
                    # exported initializer instead of inventing a zero value.
                    parent_initializer: Expr | None = parent_block.init_eqs.get(
                        parent_var,
                        None,
                    )
                    parent_is_runtime_owned: bool = (
                        parent_var in parent_block.state_vars
                        or parent_var in parent_block.algebraic_vars
                        or parent_var in parent_block.event_dict
                        or parent_var in parent_block.mode_dict
                        or parent_var in parent_block.parameters
                    )
                    if (
                            child_is_produced
                            or parent_initializer is None
                            or parent_is_runtime_owned
                    ):
                        pass
                    else:
                        parent_block.event_dict[parent_var] = parent_initializer
        else:
            pass
    else:
        pass
    child_block.__dict__["dgs_symbol_table"] = child_symbols


def _connect_graphical_parent_internal_signals(
        selected_block: ParsedDgsBlockDefinition,
        parent_block: Block,
        child_blocks: Dict[str, Block],
        child_input_index_by_connector: Dict[
            str,
            Dict[Tuple[DgsGraphicalConnectorKind, int], int],
        ],
        graphical_signals: List[BlkSig],
        connections: List[GraphicConnectionInstruction],
        routed_source_signal_names: Set[str] | None = None,
        node_by_id: Dict[str, object] | None = None,
) -> None:
    """Bind parent ``inc()`` dependencies to exact graphical cable values.

    PowerFactory stores a macro's initialization equations on the parent
    ``BlkDef`` while the value can be produced or consumed by a graphical
    primitive. A ``BlkSig`` with an empty producer is an explicitly
    disconnected input and therefore has PowerFactory's zero input value.

    :param selected_block: Parsed parent graphical block definition.
    :param parent_block: Materialized parent block updated in place.
    :param child_blocks: Materialized graphical children keyed by FID.
    :param child_input_index_by_connector: Runtime input index by graphical
        connector category and category-local port index.
    :param graphical_signals: Exact DGS graphical cables.
    :param connections: Successfully resolved non-empty cable connections.
    :param routed_source_signal_names: Names read by a graphical ``BlkFrom``;
        a blank endpoint with one of these names denotes missing exported
        operator topology rather than an intentionally disconnected input.
    :param node_by_id: Parsed graphical nodes used to interpret native
        zero-category operator connectors.
    :return: None.
    """
    parent_symbols: Dict[str, Var] = _get_dgs_block_symbol_table(
        block=parent_block,
    )
    parent_internal_names: Set[str] = set(
        selected_block.blkdef.internals
    )
    resolved_internal_names: Set[str] = set()
    disconnected_input_names: Set[str] = set()
    unresolved_input_names: Set[str] = set()
    active_routed_source_signal_names: Set[str]
    if routed_source_signal_names is None:
        active_routed_source_signal_names = set()
    else:
        active_routed_source_signal_names = set(routed_source_signal_names)
    connected_consumer_keys: Set[Tuple[str, int]] = set()
    instruction: GraphicConnectionInstruction
    graphical_signal: BlkSig

    # Record concrete resolved consumers first so split wires routed through
    # From/Goto nodes are never misclassified as disconnected inputs.
    for instruction in connections:
        if instruction.consumer_input_index is None:
            pass
        else:
            connected_consumer_keys.add((
                instruction.consumer_node_id,
                instruction.consumer_input_index,
            ))
    else:
        pass

    # A cable with a concrete child output is the authoritative producer for
    # an identically named parent internal used by an ``inc()`` expression.
    for graphical_signal in graphical_signals:
        signal_name: str = _normalize_graph_signal_name(
            name=graphical_signal.loc_name,
        )
        source_node_id: str = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodfrom,
        )
        source_connector_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(graphical_signal.iconfrom),
                endpoint_node=(
                    None
                    if node_by_id is None
                    else node_by_id.get(source_node_id, None)
                ),
                is_source_endpoint=True,
            )
        )
        source_block: Block | None = child_blocks.get(
            source_node_id,
            None,
        )
        raw_source_output_index: int = int(graphical_signal.inodfrom)
        source_output_index: int | None = (
            _resolve_graphical_runtime_output_index(
                endpoint_node=(
                    None
                    if node_by_id is None
                    else node_by_id.get(source_node_id, None)
                ),
                graphical_output_index=raw_source_output_index,
                runtime_output_count=(
                    0 if source_block is None else len(source_block.out_vars)
                ),
            )
        )
        parent_internal_var: Var | None = parent_symbols.get(
            signal_name,
            None,
        )
        if (
                signal_name not in parent_internal_names
                or signal_name in resolved_internal_names
                or source_block is None
                or source_connector_kind != DgsGraphicalConnectorKind.Output
                or source_output_index is None
                or parent_internal_var is None
        ):
            pass
        else:
            source_output_var: Var = source_block.out_vars[source_output_index]
            parent_block.update_model(
                parent_internal_var,
                source_output_var,
            )
            parent_symbols[signal_name] = source_output_var
            resolved_internal_names.add(signal_name)
    else:
        pass

    # Only a blank producer on an otherwise unresolved exact consumer pin is
    # the PowerFactory zero-input contract. The same variable then anchors the
    # parent's initialization dependency and the child's runtime input.
    for graphical_signal in graphical_signals:
        signal_name = _normalize_graph_signal_name(
            name=graphical_signal.loc_name,
        )
        source_node_id = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodfrom,
        )
        consumer_node_id: str = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodto,
        )
        consumer_connector_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(graphical_signal.iconto),
                endpoint_node=(
                    None
                    if node_by_id is None
                    else node_by_id.get(consumer_node_id, None)
                ),
                is_source_endpoint=False,
            )
        )
        if consumer_connector_kind is None:
            consumer_runtime_index: int | None = None
        else:
            consumer_runtime_index = child_input_index_by_connector.get(
                consumer_node_id,
                dict(),
            ).get(
                (
                    consumer_connector_kind,
                    int(graphical_signal.inodto),
                ),
                None,
            )
        consumer_block: Block | None = child_blocks.get(
            consumer_node_id,
            None,
        )
        parent_internal_var = parent_symbols.get(signal_name, None)
        if consumer_runtime_index is None:
            consumer_key: Tuple[str, int] | None = None
        else:
            consumer_key = (consumer_node_id, consumer_runtime_index)
        if (
                signal_name not in parent_internal_names
                or signal_name in resolved_internal_names
                or source_node_id != ""
                or consumer_block is None
                or consumer_runtime_index is None
                or consumer_runtime_index < 0
                or consumer_runtime_index >= len(consumer_block.in_vars)
                or consumer_key in connected_consumer_keys
                or parent_internal_var is None
        ):
            pass
        else:
            if signal_name in active_routed_source_signal_names:
                # A BlkFrom reads the same named signal elsewhere in the
                # diagram, proving that it is live. If its producer pointer is
                # blank, the export omitted a native graphical operator class;
                # retaining it as unresolved is safer than fabricating zero.
                unresolved_input_names.add(signal_name)
            else:
                consumer_input_var: Var = consumer_block.in_vars[
                    consumer_runtime_index
                ]
                parent_block.update_model(
                    parent_internal_var,
                    consumer_input_var,
                )
                parent_symbols[signal_name] = consumer_input_var
                consumer_block.event_dict[consumer_input_var] = Const(0.0)
                resolved_internal_names.add(signal_name)
                disconnected_input_names.add(signal_name)
    else:
        pass
    parent_block.__dict__["dgs_symbol_table"] = parent_symbols
    parent_block.__dict__["dgs_resolved_graphical_internal_names"] = sorted(
        resolved_internal_names
    )
    parent_block.__dict__["dgs_disconnected_graphical_input_names"] = sorted(
        disconnected_input_names
    )
    parent_block.__dict__["dgs_unresolved_graphical_input_names"] = sorted(
        unresolved_input_names
    )


def _collect_required_init_signal_names(
    parsed: ParsedDgsBlockDefinition,
    runtime_signal_names: Set[str],
) -> Set[str]:
    """
    Collect the transitive PowerFactory initialization scratch variables.

    PowerFactory ``inc()`` equations may define intermediate values used only
    while initializing a runtime state, algebraic signal or interface value.
    Those intermediates must be evaluated in dependency order, but they must
    not become permanent DAE unknowns. Starting from the concrete runtime
    signals and following only other ``inc()`` definitions retains the required
    scratch graph while still dropping unrelated source metadata.

    :param parsed: Parsed DGS block definition.
    :param runtime_signal_names: State, algebraic and interface signal names.
    :return: Initialization left-hand sides required by the runtime contract.
    """
    required_names: Set[str] = set()
    symbol_name_by_uid: Dict[int, str] = dict()
    symbol_name: str
    symbol_var: Var
    candidate_name: str
    candidate_expr: Expr
    dependency_var: Var

    # Build an identity-safe reverse lookup because scratch variables may have
    # humanized symbolic names that differ from their raw DGS identifiers.
    for symbol_name, symbol_var in parsed.symbol_table.items():
        symbol_name_by_uid[symbol_var.uid] = symbol_name

    runtime_dependency_names: Set[str] = _collect_runtime_dependency_signal_names(
        parsed=parsed,
    )
    for candidate_name in parsed.init_rhs.keys():
        if (
            candidate_name in runtime_signal_names
            or candidate_name in runtime_dependency_names
        ):
            required_names.add(candidate_name)
        else:
            candidate_symbol_var: Var | None = parsed.symbol_table.get(
                candidate_name,
                None,
            )
            if (
                candidate_symbol_var is not None
                and candidate_symbol_var.name in parsed.procedural_dependency_names
            ):
                # Held ``inc()`` values consumed by procedural logic are part
                # of the runtime contract even without an algebraic equation.
                required_names.add(candidate_name)
            else:
                pass

    # Expand to a fixed point over ``inc()`` dependencies. The graph is finite
    # because every discovered name must be a key in the parsed init mapping.
    changed: bool = True
    while changed:
        changed = False
        for candidate_name, candidate_expr in parsed.init_rhs.items():
            if candidate_name in required_names:
                for dependency_var in candidate_expr.get_vars():
                    dependency_name: str | None = symbol_name_by_uid.get(
                        dependency_var.uid,
                        None,
                    )
                    if (
                        dependency_name is not None
                        and dependency_name in parsed.init_rhs
                        and dependency_name not in required_names
                    ):
                        required_names.add(dependency_name)
                        changed = True
                    else:
                        pass
            else:
                pass

    return required_names


def _collect_runtime_dependency_signal_names(
    parsed: ParsedDgsBlockDefinition,
) -> Set[str]:
    """
    Collect raw DGS symbols read by differential or algebraic runtime equations.

    :param parsed: Parsed DGS block definition.
    :return: Exact semantic symbols required while the simulation advances.
    """
    symbol_name_by_uid: Dict[int, str] = dict()
    symbol_name: str
    symbol_var: Var
    runtime_dependency_names: Set[str] = set()
    runtime_expressions: List[Expr] = list(parsed.state_rhs.values())
    runtime_expressions.extend(parsed.algebraic_rhs.values())
    runtime_expression: Expr
    dependency_var: Var

    for symbol_name, symbol_var in parsed.symbol_table.items():
        symbol_name_by_uid[symbol_var.uid] = symbol_name

    for runtime_expression in runtime_expressions:
        for dependency_var in runtime_expression.get_vars():
            dependency_name: str | None = symbol_name_by_uid.get(
                dependency_var.uid,
                None,
            )
            if dependency_name is None:
                pass
            else:
                runtime_dependency_names.add(dependency_name)

    return runtime_dependency_names


def _build_block_from_parsed(
    parsed: ParsedDgsBlockDefinition,
    shared_signals: Dict[str, Var],
    parameter_values: DgsParameterValues | None = None,
    additional_required_init_signal_names: Set[str] | None = None,
) -> Block:
    """
    Materialize one parsed DGS block into a runtime Block.

    :param parsed: Parsed DGS block definition.
    :param shared_signals: Shared signal table reused across sibling blocks.
    :param parameter_values: Optional instance values obtained from ElmDsl rows.
    :param additional_required_init_signal_names: Initialization signals used
        by a surrounding graphical composition but not by the standalone DSL.
    :return: Runtime block ready to be composed or exported.
    """
    symbol_table, state_vars, _state_map, diff_var_map, param_var_map = _build_symbol_table(parsed.blkdef, shared_signals)

    for name, old_var in parsed.symbol_table.items():
        if name not in symbol_table:
            symbol_table[name] = Var(name=old_var.name)

    var_mapping: SymbolReplacementMap = dict()
    for name, old_var in parsed.symbol_table.items():
        new_var = symbol_table.get(name, None)
        if new_var is not None:
            var_mapping[old_var] = new_var
            var_mapping[old_var.name] = new_var

    algebraic_pairs: List[Tuple[Var, Expr]] = list()
    used_alg_names: Set[str] = set()
    for lhs_name, rhs_expr in parsed.algebraic_rhs.items():
        if lhs_name in symbol_table:
            lhs_var = symbol_table[lhs_name]
        else:
            lhs_var = Var(name=f"{parsed.blkdef.loc_name}__{lhs_name}")
            symbol_table[lhs_name] = lhs_var

        old_lhs_var = parsed.symbol_table.get(lhs_name, None)
        if old_lhs_var is not None:
            var_mapping[old_lhs_var] = lhs_var
            var_mapping[old_lhs_var.name] = lhs_var

        algebraic_pairs.append((lhs_var, lhs_var - rhs_expr.subs(var_mapping)))
        used_alg_names.add(lhs_name)

    algebraic_vars: List[Var] = [pair[0] for pair in algebraic_pairs]
    algebraic_eqs: List[Expr] = [pair[1] for pair in algebraic_pairs]

    state_eqs: List[Expr] = list()
    state_limits: Dict[Var, Tuple[Expr, Expr]] = dict()
    effective_state_vars: List[Var] = list()
    effective_diff_vars: List[Var] = list()
    for state_name in parsed.blkdef.states:
        if state_name in parsed.state_rhs:
            runtime_state_var: Var = symbol_table[state_name]
            effective_state_vars.append(runtime_state_var)
            effective_diff_vars.append(diff_var_map[state_name])
            state_eqs.append(parsed.state_rhs[state_name].subs(var_mapping))
            parsed_state_var: Var | None = parsed.symbol_table.get(state_name, None)
            parsed_limit_pair: Tuple[Expr, Expr] | None
            if parsed_state_var is None:
                parsed_limit_pair = None
            else:
                parsed_limit_pair = parsed.state_limits_by_uid.get(
                    parsed_state_var.uid,
                    None,
                )
            if parsed_limit_pair is None:
                pass
            else:
                state_limits[runtime_state_var] = (
                    parsed_limit_pair[0].subs(var_mapping),
                    parsed_limit_pair[1].subs(var_mapping),
                )

    # The BlkDef stores the parameter names, while the ElmDsl instance stores the concrete numbers.
    resolved_parameter_values: DgsParameterValues = dict(parameter_values or {})
    event_dict: Dict[Var, Expr | Const] = dict()
    param_name: str
    param_var: Var
    for param_name, param_var in param_var_map.items():
        event_dict[param_var] = Const(resolved_parameter_values.get(param_name, None), name=param_name)

    init_eqs: Dict[Var, Expr] = dict()
    explicit_initialization_uids: Set[int] = set()
    solved_signal_names: Set[str] = set(parsed.blkdef.states)
    solved_signal_names.update(parsed.algebraic_rhs.keys())
    runtime_input_names: List[str] = _build_blkdef_runtime_input_names(
        blkdef=parsed.blkdef,
    )
    boundary_signal_names: Set[str] = set(runtime_input_names)
    boundary_signal_names.update(parsed.blkdef.outputs)
    runtime_signal_names: Set[str] = set(solved_signal_names)
    runtime_signal_names.update(boundary_signal_names)
    required_init_signal_names: Set[str] = _collect_required_init_signal_names(
        parsed=parsed,
        runtime_signal_names=runtime_signal_names,
    )
    if additional_required_init_signal_names is None:
        pass
    else:
        # A graphical parent can own held values consumed only by a nested
        # primitive. They are invisible to the standalone DSL dependency graph
        # but remain authoritative PowerFactory ``inc()`` assignments.
        required_init_signal_names.update(
            additional_required_init_signal_names
        )
    runtime_dependency_signal_names: Set[str] = (
        _collect_runtime_dependency_signal_names(parsed=parsed)
    )
    for lhs_name, rhs_expr in parsed.init_rhs.items():
        # PowerFactory permits ``inc()`` declarations for internal signals whose
        # runtime assignment uses a helper that is not materialized by this
        # parser. Retain only the transitive scratch graph needed to initialize
        # a concrete runtime signal; unrelated source metadata remains dropped.
        if lhs_name in required_init_signal_names:
            lhs_var: Var
            if lhs_name in symbol_table:
                lhs_var = symbol_table[lhs_name]
            else:
                lhs_var = Var(name=f"{parsed.blkdef.loc_name}__{lhs_name}")
                symbol_table[lhs_name] = lhs_var

            old_lhs_var = parsed.symbol_table.get(lhs_name, None)
            if old_lhs_var is not None:
                var_mapping[old_lhs_var] = lhs_var
                var_mapping[old_lhs_var.name] = lhs_var
            else:
                pass

            resolved_init_expr: Expr = rhs_expr.subs(var_mapping)
            if lhs_name in solved_signal_names:
                init_eqs[lhs_var] = resolved_init_expr
                if lhs_name in parsed.inc0_signal_names:
                    # ``inc0()`` is a soft local fallback even when its target
                    # is a solved output.  A connected downstream ``inc()`` may
                    # back-propagate the physical operating point through this
                    # cable and must therefore outrank the producer fallback.
                    pass
                else:
                    explicit_initialization_uids.add(lhs_var.uid)
            else:
                if lhs_name in boundary_signal_names:
                    if lhs_name in parsed.inc0_signal_names:
                        # An unconnected PowerFactory input initialized with
                        # ``inc0()`` is a runtime boundary parameter, not a DAE
                        # unknown. Root normalization removes this fallback if
                        # a sibling provides the actual producer equation.
                        event_dict[lhs_var] = resolved_init_expr
                    else:
                        # ``inc()`` on a connected input is a consumer-side
                        # initialization constraint. Retaining it by UID lets
                        # the graphical BlkSig substitution anchor the producer
                        # cable instead of silently discarding the condition.
                        # Keep a provisional held boundary value as well: root
                        # normalization removes it when a producer exists,
                        # while genuinely unconnected procedural commands need
                        # it throughout the simulation.
                        init_eqs[lhs_var] = resolved_init_expr
                        explicit_initialization_uids.add(lhs_var.uid)
                        event_dict[lhs_var] = resolved_init_expr
                else:
                    if (
                        lhs_var.name in parsed.procedural_dependency_names
                        or lhs_name in runtime_dependency_signal_names
                    ):
                        # A source consumed by retained procedural logic must
                        # survive after explicit initialization. PowerFactory
                        # uses ``inc()`` without a runtime assignment for these
                        # held values, so represent them as event parameters.
                        event_dict[lhs_var] = resolved_init_expr
                    else:
                        # Pure init-only auxiliaries live in the explicit
                        # initializer scratch map and never enlarge the DAE.
                        init_eqs[lhs_var] = resolved_init_expr
                        explicit_initialization_uids.add(lhs_var.uid)
        else:
            pass

    # PowerFactory algebraic statements are directed assignments even when no
    # explicit ``inc()`` statement is exported. Their RHS therefore provides a
    # valid startup seed whenever it does not directly depend on its own LHS.
    # Retaining these seeds prevents singular first residual evaluations such
    # as a normalized division whose denominator is another algebraic output.
    for lhs_name, rhs_expr in parsed.algebraic_rhs.items():
        algebraic_var: Var | None = symbol_table.get(lhs_name, None)
        if algebraic_var is None or algebraic_var in init_eqs:
            pass
        else:
            resolved_algebraic_rhs: Expr = rhs_expr.subs(var_mapping)
            dependency_uids: Set[int] = set(
                dependency_var.uid
                for dependency_var in resolved_algebraic_rhs.get_vars()
            )
            if algebraic_var.uid in dependency_uids:
                pass
            else:
                init_eqs[algebraic_var] = resolved_algebraic_rhs

    mode_dict: Dict[Var, Expr | Const] = dict()
    for mode_var, rhs_expr in parsed.mode_dict.items():
        mapped_var = var_mapping.get(mode_var, None)
        if not isinstance(mapped_var, Var):
            mapped_var = symbol_table.get(mode_var.name, None)
        if not isinstance(mapped_var, Var):
            mapped_var = Var(name=mode_var.name)
            symbol_table[mode_var.name] = mapped_var
        mode_dict[mapped_var] = rhs_expr.subs(var_mapping) if isinstance(rhs_expr, Expr) else rhs_expr

    procedural_logic = clone_procedural_logic_entries(parsed.procedural_logic, var_mapping)

    # Algebraic assignments that read retained procedural outputs or mutable
    # runtime parameters need one directed refresh after those values advance.
    # Record the exact prefixed LHS names here so the RMS boundary layer can
    # close a parameter-to-selector-to-output chain at one physical time without
    # replaying unrelated physical equipment equations.
    procedural_mode_uids: Set[int] = set(
        procedural_var.uid for procedural_var in mode_dict.keys()
    )
    procedural_dependency_uids: Set[int] = set(procedural_mode_uids)
    runtime_parameter_var: Var
    for runtime_parameter_var in event_dict.keys():
        procedural_dependency_uids.add(runtime_parameter_var.uid)
    else:
        pass
    procedural_helper_names: List[str] = list()
    procedural_helper_uids: List[int] = list()
    algebraic_pair: Tuple[Var, Expr]
    procedural_closure_pass: int
    # A procedural output can feed several directed algebraic assignments
    # before reaching a public controller output. Compute a bounded transitive
    # closure so one runtime boundary update reproduces PowerFactory's same-time
    # assignment graph instead of introducing one transport step per helper.
    for procedural_closure_pass in range(8):
        for algebraic_pair in algebraic_pairs:
            algebraic_target: Var = algebraic_pair[0]
            algebraic_equation: Expr = algebraic_pair[1]
            equation_uses_procedural_mode: bool = False
            equation_variable: Var
            for equation_variable in algebraic_equation.get_vars():
                if equation_variable.uid in procedural_dependency_uids:
                    equation_uses_procedural_mode = True
                else:
                    pass
            else:
                pass
            if equation_uses_procedural_mode:
                if algebraic_target.uid in procedural_dependency_uids:
                    pass
                else:
                    procedural_dependency_uids.add(algebraic_target.uid)
                    procedural_helper_names.append(algebraic_target.name)
                    procedural_helper_uids.append(algebraic_target.uid)
            else:
                pass
        else:
            pass
    else:
        pass

    result_block: Block = Block(
        name=parsed.blkdef.loc_name,
        state_vars=effective_state_vars,
        state_eqs=state_eqs,
        state_limits=state_limits,
        diff_vars=effective_diff_vars,
        algebraic_vars=algebraic_vars,
        algebraic_eqs=algebraic_eqs,
        in_vars=[
            shared_signals[name]
            for name in runtime_input_names
            if name in shared_signals
        ],
        out_vars=[shared_signals[name] for name in parsed.blkdef.outputs if name in shared_signals],
        event_dict=event_dict,
        mode_dict=mode_dict,
        init_eqs=init_eqs,
        procedural_logic=procedural_logic,
    )
    result_block.__dict__["runtime_post_update_helper_names"] = list(
        procedural_helper_names
    )
    result_block.__dict__["runtime_post_update_helper_var_uids"] = list(
        procedural_helper_uids
    )
    # Retain the exact raw-name identities until the graphical parent applies
    # BlkRef state/internal ownership vectors. Humanized variable names alone
    # cannot recover this positional relationship without ambiguity.
    result_block.__dict__["dgs_symbol_table"] = dict(symbol_table)
    if len(parsed.discrete_event_actions) > 0:
        materialized_actions: List[DgsDiscreteEventAction] = list()
        parsed_action: DgsDiscreteEventAction
        for parsed_action in parsed.discrete_event_actions:
            materialized_actions.append(
                _substitute_dgs_discrete_event_symbolic_expressions(
                    action=parsed_action,
                    var_mapping=var_mapping,
                )
            )
        result_block.__dict__["dgs_discrete_event_actions"] = materialized_actions
    else:
        pass
    # Preserve which seeds came from an authoritative PowerFactory ``inc()``
    # statement. ``inc0()`` and algebraic RHS seeds remain useful fallbacks,
    # while a consumer-side explicit initialization owns a connected cable when
    # direct graphical blocks are later flattened.
    result_block.__dict__["dgs_explicit_initialization_uids"] = set(
        explicit_initialization_uids
    )
    return result_block


def _remove_produced_signal_fallbacks(root_block: Block) -> None:
    """
    Remove boundary defaults for signals solved by the composed DAE.

    Child blocks are materialized independently, so an input initialized by
    ``inc0()`` first becomes a safe event-parameter fallback. Once siblings are
    composed, any shared signal that is also a state or algebraic unknown must be
    owned exclusively by its producer equation.

    :param root_block: Composed DGS root block.
    :return: None.
    """
    solved_variable_uids: Set[int] = set()
    child_block: Block
    solved_var: Var
    event_var: Var

    for child_block in root_block.get_all_blocks():
        for solved_var in child_block.state_vars:
            solved_variable_uids.add(solved_var.uid)
        for solved_var in child_block.algebraic_vars:
            solved_variable_uids.add(solved_var.uid)

    for child_block in root_block.get_all_blocks():
        event_vars: List[Var] = list(child_block.event_dict.keys())
        for event_var in event_vars:
            if event_var.uid in solved_variable_uids:
                child_block.event_dict.pop(event_var, None)
            else:
                pass


def _build_dependency_graph(parsed_blocks: Dict[str, ParsedDgsBlockDefinition]) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Dict[str, Set[str]]]:
    producer_map: Dict[str, Set[str]] = dict()
    consumer_map: Dict[str, Set[str]] = dict()

    for block_id, parsed in parsed_blocks.items():
        produced_names = set(parsed.blkdef.outputs) | set(parsed.algebraic_rhs.keys()) | set(parsed.state_rhs.keys())
        for name in produced_names:
            _append_to_string_set_map(producer_map, name, block_id)

        for dep_names in parsed.signal_dependencies.values():
            for name in dep_names:
                _append_to_string_set_map(consumer_map, name, block_id)

    dependency_graph: Dict[str, Set[str]] = dict()
    block_id: str
    for block_id in parsed_blocks.keys():
        dependency_graph[block_id] = set()

    for signal_name, producers in producer_map.items():
        consumers = consumer_map.get(signal_name, set())
        for producer in producers:
            for consumer in consumers:
                if producer != consumer:
                    dependency_graph[producer].add(consumer)

    return dependency_graph, producer_map, consumer_map


def parse_dgs_block_definitions_from_context(
        circuit: DgsCircuit,
) -> Dict[str, ParsedDgsBlockDefinition]:
    """Parse every block definition once for a shared DGS import context.

    :param circuit: Already parsed DGS circuit.
    :return: Parsed block definitions indexed by exact DGS FID.
    """
    shared_signals: Dict[str, Var] = dict()
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = dict()
    blk: BlkDef

    for blk in circuit.blkdefs:
        parsed_blocks[blk.ID] = _parse_blkdef(blk, shared_signals)
    return parsed_blocks


def dgs_to_root_block_from_context(
        circuit: DgsCircuit,
        parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
        root_name: str = "Grid Forming Converter",
        root_typ_id: str | None = None,
        root_dgs_id: str | None = None,
) -> DgsRootBlockResult:
    """Materialize one root from an already parsed massive-import context.

    :param circuit: Shared parsed DGS circuit.
    :param parsed_blocks: Shared parsed block-definition lookup.
    :param root_name: Root ElmComp display name.
    :param root_typ_id: Optional exact frame type FID.
    :param root_dgs_id: Optional exact root ElmComp FID.
    :return: Parsed root hierarchy and dependency context.
    """
    shared_signals: Dict[str, Var] = dict()

    root_element, root_blkdef = _select_root_element(
        circuit=circuit,
        parsed_blocks=parsed_blocks,
        root_name=root_name,
        root_typ_id=root_typ_id,
        root_dgs_id=root_dgs_id,
    )
    reachable_blocks = _collect_reachable_blocks(root_blkdef, parsed_blocks)
    direct_instance_entries: List[ElmCompInstanceEntry] = (
        extract_elmcomp_direct_instances(circuit, root_element)
    )
    parameter_values_by_type_id = _parameter_values_by_type_id(
        direct_instance_entries,
        keep_first_on_duplicates=True,
    )

    child_blocks: List[Block] = list()
    ordered_reachable_blocks: List[tuple[str, str, ParsedDgsBlockDefinition]] = [
        _parsed_block_name_pair(block_id, parsed)
        for block_id, parsed in reachable_blocks.items()
    ]
    ordered_reachable_blocks.sort()
    _block_name: str
    _block_id: str
    parsed: ParsedDgsBlockDefinition
    for _block_name, _block_id, parsed in ordered_reachable_blocks:
        child_blocks.append(
            _build_block_from_parsed(parsed, shared_signals, parameter_values=parameter_values_by_type_id.get(parsed.blkdef.ID, None))
        )

    root_block = Block(
        name=root_element.loc_name,
        children=child_blocks,
        in_vars=[
            shared_signals[name]
            for name in _build_blkdef_runtime_input_names(
                blkdef=root_blkdef.blkdef,
            )
            if name in shared_signals
        ],
        out_vars=[shared_signals[name] for name in root_blkdef.blkdef.outputs if name in shared_signals],
        algebraic_vars=[shared_signals[name] for name in root_blkdef.blkdef.internals if name in shared_signals],
    )

    # Some imported DGS composites do not declare the root interface explicitly.
    # Expose the ordered child-port union so the imported template can be wired as
    # one reusable block in the editor and in device assignments.
    _apply_composite_child_interface_if_missing(root_block)
    _remove_produced_signal_fallbacks(root_block=root_block)

    combined_blocks: Dict[str, ParsedDgsBlockDefinition] = dict()
    combined_blocks[root_blkdef.blkdef.ID] = root_blkdef
    for block_id, parsed in reachable_blocks.items():
        combined_blocks[block_id] = parsed

    # The exact ElmComp pblk/pelm relation is authoritative even when an older
    # DGS export does not expose enough signal names to recover the child by
    # dependency closure.  Preserve every referenced BlkDef so the direct-root
    # builder and the massive slot catalogue can materialize the real equations.
    direct_instance_entry: ElmCompInstanceEntry
    for direct_instance_entry in direct_instance_entries:
        direct_type_id: str | None = direct_instance_entry.type_id
        if direct_type_id is None or direct_type_id not in parsed_blocks:
            pass
        else:
            combined_blocks[direct_type_id] = parsed_blocks[direct_type_id]
    # Graphical macros reference primitive definitions by BlkRef.typ_id rather
    # than by signal-name dependency. Index those already parsed definitions
    # once in the root context so every slot lookup remains an O(1) identity
    # lookup instead of reparsing the complete DGS block library.
    graphical_reference: BlkRef
    for graphical_reference in circuit.blkrefs:
        graphical_type_id: str = str(graphical_reference.typ_id)
        if graphical_type_id in parsed_blocks:
            combined_blocks[graphical_type_id] = parsed_blocks[graphical_type_id]
        else:
            pass
    dependency_graph, producer_map, consumer_map = _build_dependency_graph(combined_blocks)

    return DgsRootBlockResult(
        root_block=root_block,
        root_blkdef=root_blkdef,
        root_element=root_element,
        parsed_blocks=combined_blocks,
        dependency_graph=dependency_graph,
        producer_map=producer_map,
        consumer_map=consumer_map,
    )


def dgs_to_root_block(
        path: str,
        root_name: str = "Grid Forming Converter",
        root_typ_id: str | None = None,
        root_dgs_id: str | None = None,
) -> DgsRootBlockResult:
    """Parse one DGS file and materialize one selected composite root.

    :param path: Source DGS path.
    :param root_name: Root ElmComp display name.
    :param root_typ_id: Optional exact frame type FID.
    :param root_dgs_id: Optional exact root ElmComp FID.
    :return: Parsed root hierarchy and dependency context.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path)
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_context(circuit=circuit)
    )
    return dgs_to_root_block_from_context(
        circuit=circuit,
        parsed_blocks=parsed_blocks,
        root_name=root_name,
        root_typ_id=root_typ_id,
        root_dgs_id=root_dgs_id,
    )


def _build_direct_root_elmcomp_block(
    circuit: DgsCircuit,
    result: DgsRootBlockResult,
    graphical_context: DgsGraphicalParseContext | None = None,
) -> DgsDirectRootBuildResult:
    """
    Build a root ElmComp block using only its direct DGS child instances.

    :param circuit: Parsed DGS circuit.
    :param result: Root selection result.
    :param graphical_context: Optional shared graphical indexes.
    :return: Root runtime block and reusable exact direct children.
    """
    shared_signals: Dict[str, Var] = dict()
    root_signal_names: List[str] = list()
    for root_var in result.root_block.in_vars:
        root_signal_names.append(root_var.name)
    for root_var in result.root_block.out_vars:
        root_signal_names.append(root_var.name)
    for root_var in result.root_block.algebraic_vars:
        root_signal_names.append(root_var.name)

    for signal_name in root_signal_names:
        if signal_name not in shared_signals:
            shared_signals[signal_name] = Var(name=signal_name)
        else:
            pass

    child_blocks: List[Block] = list()
    slot_interface_specs: List[Dict[str, object]] = list()
    child_block_by_slot_id: Dict[str, Block] = dict()
    graphical_slot_ids: Set[str] = set()
    element_by_id: Dict[str, object] = _build_dgs_element_index(circuit=circuit)
    direct_entries = extract_elmcomp_direct_instances(circuit, result.root_element)
    for entry in direct_entries:
        incoming_signals: List[str]
        outgoing_signals: List[str]
        source_element: object | None = element_by_id.get(
            entry.element_id or "",
            None,
        )
        slot_interface_spec: Dict[str, object] = dict()

        incoming_signals, outgoing_signals = get_blkslot_signal_interface(circuit, entry.slot_id)
        slot_interface_spec["slot_id"] = entry.slot_id
        slot_interface_spec["slot_name"] = entry.slot_name
        slot_interface_spec["element_id"] = entry.element_id
        slot_interface_spec["element_name"] = entry.element_name
        slot_interface_spec["element_kind"] = entry.element_kind
        slot_interface_spec["type_id"] = entry.type_id
        slot_interface_spec["type_name"] = entry.type_name
        slot_interface_spec["slot_element"] = entry.slot_element
        slot_interface_spec["slot_filter"] = entry.slot_filter
        slot_interface_spec["powerfactory_astable_integration"] = (
            entry.powerfactory_astable_integration
        )
        slot_interface_spec["incoming_signals"] = list(incoming_signals)
        slot_interface_spec["outgoing_signals"] = list(outgoing_signals)

        if isinstance(source_element, ElmSvs):
            # The physical ElmSvs equations are built into PowerFactory and do
            # not appear as a BlkDef. Retain their exact equipment constants on
            # the human-readable frame metadata so the DGS-only runtime adapter
            # can reconstruct the same TCR/capacitor boundary without querying
            # the PowerFactory API or inferring values from the static case.
            slot_interface_spec["svs_qreact_mvar"] = float(source_element.tcrmax)
            slot_interface_spec["svs_qcap_mvar"] = float(source_element.qmin)
            slot_interface_spec["svs_qfixcap_mvar"] = float(source_element.Qfixcap)
            slot_interface_spec["svs_nxcap"] = int(source_element.nxcap)
            slot_interface_spec["svs_nfixcap"] = int(source_element.nfixcap)
        else:
            pass
        slot_interface_specs.append(slot_interface_spec)

        if entry.type_id is None:
            pass
        else:
            parsed_block = result.parsed_blocks.get(entry.type_id, None)
            if parsed_block is None:
                pass
            else:
                source_owner_id: str = ""
                if isinstance(source_element, ElmDsl):
                    source_owner_value: object | None = source_element.fold_id
                    if source_owner_value is None:
                        source_owner_id = ""
                    else:
                        source_owner_id = str(source_owner_value).strip()
                else:
                    pass
                is_foreign_dynamic_reference: bool = (
                    isinstance(source_element, ElmDsl)
                    and source_owner_id != ""
                    and source_owner_id != result.root_element.ID
                )

                if is_foreign_dynamic_reference:
                    # A foreign ElmDsl slot is a cross-composite signal
                    # reference. Its equations execute once in the owning root
                    # and must not be cloned into the consuming device model.
                    pass
                else:
                    # A macro BlkDef stores its initialization and interface,
                    # while its runtime equations live in the connected
                    # BlkRef/BlkSig graphical tree. Materialize that exact tree
                    # first so a DGS root never degrades an AVR, governor or PSS
                    # to an equation-free interface shell.
                    graphical_tree: DgsGraphicTreeResult | None = (
                        extract_root_slot_block_graphical_tree_from_context(
                            circuit=circuit,
                            result=result,
                            slot_name=str(entry.slot_name or entry.type_name or ""),
                            slot_dgs_id=entry.slot_id,
                            graphical_context=graphical_context,
                        )
                    )
                    if graphical_tree is None:
                        # Formula-based BlkDefs and exports without graphical
                        # nodes remain complete through the semantic parser.
                        instance_signals: Dict[str, Var] = dict()
                        child_block = _build_block_from_parsed(
                            parsed_block,
                            instance_signals,
                            parameter_values=entry.parameter_values,
                        )
                    else:
                        child_block = graphical_tree.view_block
                        if entry.slot_id is None:
                            pass
                        else:
                            graphical_slot_ids.add(entry.slot_id)
                    child_block.__dict__["dgs_element_id"] = entry.element_id
                    child_block.__dict__["dgs_slot_id"] = entry.slot_id
                    child_block.__dict__[
                        "dgs_powerfactory_astable_integration"
                    ] = entry.powerfactory_astable_integration
                    child_blocks.append(child_block)
                    if entry.slot_id is None:
                        pass
                    else:
                        child_block_by_slot_id[entry.slot_id] = child_block

    _connect_direct_elmcomp_children_by_graph(
        circuit=circuit,
        child_block_by_slot_id=child_block_by_slot_id,
    )

    produced_variable_uids: Set[int] = set()
    child_block: Block
    produced_var: Var
    for child_block in child_blocks:
        for produced_var in child_block.state_vars:
            produced_variable_uids.add(produced_var.uid)
        for produced_var in child_block.algebraic_vars:
            produced_variable_uids.add(produced_var.uid)

    root_input_vars: List[Var] = list()
    root_input_uids: Set[int] = set()
    root_input_var: Var
    for root_input_var in result.root_block.in_vars:
        shared_root_input: Var | None = shared_signals.get(
            root_input_var.name,
            None,
        )
        if shared_root_input is None or shared_root_input.uid in root_input_uids:
            pass
        else:
            root_input_vars.append(shared_root_input)
            root_input_uids.add(shared_root_input.uid)

    # Flattening retains only the root interface. Expose every unresolved child
    # input there so a later native-meter or cross-composite binding can resolve
    # it by exact symbolic name without declaring it as a DAE unknown.
    for child_block in child_blocks:
        for root_input_var in child_block.in_vars:
            if (
                root_input_var.uid in produced_variable_uids
                or root_input_var.uid in root_input_uids
            ):
                pass
            else:
                root_input_vars.append(root_input_var)
                root_input_uids.add(root_input_var.uid)

    root_block: Block = Block(
        name=result.root_element.loc_name,
        children=child_blocks,
        in_vars=root_input_vars,
        out_vars=[shared_signals[var.name] for var in result.root_block.out_vars if var.name in shared_signals],
        # ElmComp frame internals are a wiring namespace, not independent DAE
        # unknowns. Owned child equations, native meters and electrical adapters
        # register the concrete variables that survive at runtime.
        algebraic_vars=list(),
    )
    root_block.__dict__["dgs_direct_slot_interfaces"] = slot_interface_specs

    # Resolve deferred equipment commands while every authoritative DGS pointer
    # is still available. The runtime can then target a physical branch by FID
    # without retaining the full source file or falling back to display names.
    _resolve_dgs_discrete_event_targets(
        root_block=root_block,
        root_dgs_id=str(result.root_element.ID),
        direct_entries=direct_entries,
        element_by_id=element_by_id,
    )

    # Keep the direct-root export path aligned with the main parsed root behavior.
    _apply_composite_child_interface_if_missing(root_block)
    _remove_produced_signal_fallbacks(root_block=root_block)
    return DgsDirectRootBuildResult(
        root_block=root_block,
        child_block_by_slot_id=child_block_by_slot_id,
        graphical_slot_ids=graphical_slot_ids,
    )


def _resolve_dgs_discrete_event_targets(
        root_block: Block,
        root_dgs_id: str,
        direct_entries: List[ElmCompInstanceEntry],
        element_by_id: Dict[str, object],
) -> None:
    """Attach exact DGS equipment identities to deferred switch actions.

    PowerFactory actions address a composite slot. The slot points to a
    ``StaSwitch`` or ``ElmCoup``; a cubicle switch then points through
    ``fold_id`` to ``StaCubic.obj_id`` and ``obj_bus``. Preserving that full
    chain avoids ambiguous name matching and identifies the exact equipment end.

    :param root_block: Materialized composite block containing deferred actions.
    :param root_dgs_id: Owning ``ElmComp`` FID.
    :param direct_entries: Exact direct slot occurrences of the composite.
    :param element_by_id: Parsed DGS object index keyed by FID.
    :return: ``None``.
    """

    target_element_id_by_slot_name: Dict[str, str] = dict()
    direct_entry: ElmCompInstanceEntry
    for direct_entry in direct_entries:
        if direct_entry.element_id is None or direct_entry.slot_name is None:
            pass
        else:
            target_element_id_by_slot_name[direct_entry.slot_name] = str(
                direct_entry.element_id
            )

    blocks_to_visit: List[Block] = list([root_block])
    block_index: int = 0
    while block_index < len(blocks_to_visit):
        current_block: Block = blocks_to_visit[block_index]
        block_index += 1
        child_block: Block
        for child_block in current_block.children:
            blocks_to_visit.append(child_block)

        raw_actions: object | None = current_block.__dict__.get(
            "dgs_discrete_event_actions",
            None,
        )
        if isinstance(raw_actions, list):
            resolved_actions: List[DgsDiscreteEventAction] = list()
            raw_action: object
            for raw_action in raw_actions:
                if isinstance(raw_action, DgsDiscreteEventAction):
                    target_element_id: str | None = target_element_id_by_slot_name.get(
                        raw_action.get_target_slot_name(),
                        None,
                    )
                    target_element: object | None = element_by_id.get(
                        target_element_id or "",
                        None,
                    )
                    actuated_device_id: str | None
                    actuated_terminal_index: int | None
                    if isinstance(target_element, StaSwitch):
                        target_cubicle: object | None = element_by_id.get(
                            str(target_element.fold_id),
                            None,
                        )
                        if isinstance(target_cubicle, StaCubic):
                            actuated_device_id = str(target_cubicle.obj_id)
                            actuated_terminal_index = int(target_cubicle.obj_bus)
                        else:
                            actuated_device_id = None
                            actuated_terminal_index = None
                    else:
                        if target_element_id is None:
                            actuated_device_id = None
                            actuated_terminal_index = None
                        else:
                            # A direct ``ElmCoup`` slot already identifies the
                            # physical switching device without a cubicle hop.
                            actuated_device_id = target_element_id
                            actuated_terminal_index = None

                    if (
                            target_element_id is not None
                            and actuated_device_id is not None
                    ):
                        resolved_action: DgsDiscreteEventAction = (
                            raw_action.with_target_resolution(
                                root_dgs_id=root_dgs_id,
                                target_element_dgs_id=target_element_id,
                                actuated_device_dgs_id=actuated_device_id,
                                actuated_terminal_index=actuated_terminal_index,
                            )
                        )
                        resolved_actions.append(resolved_action)
                    else:
                        # Empty breaker slots remain valid deferred metadata. A
                        # later executor will diagnose and skip them explicitly.
                        resolved_actions.append(raw_action)
                else:
                    pass
            current_block.__dict__["dgs_discrete_event_actions"] = resolved_actions
        else:
            pass


def _build_runtime_interface_var_map(block: Block) -> Dict[str, Var]:
    """
    Index the current scalar input and output variables of one runtime block.

    :param block: Runtime block before or during graphical connection.
    :return: Variable lookup keyed by exact PowerFactory interface symbol.
    """
    variable_by_name: Dict[str, Var] = dict()
    variable: Var
    variable_lists: List[List[Var]] = [block.in_vars, block.out_vars]
    variable_list: List[Var]

    for variable_list in variable_lists:
        for variable in variable_list:
            if variable.name in variable_by_name:
                pass
            else:
                variable_by_name[variable.name] = variable

    return variable_by_name


def _connect_direct_elmcomp_children_by_graph(
    circuit: DgsCircuit,
    child_block_by_slot_id: Dict[str, Block],
) -> None:
    """
    Reproduce direct ElmComp wiring from exact BlkSig endpoints and port indices.

    Display labels are documentation and may differ from the producer and
    consumer symbol names. Therefore the authoritative contract is the pair of
    slot FIDs plus ``inodfrom``/``inodto``. Vector ports are connected component
    by component in the order exported by ``cOutput`` and ``cInput``.

    :param circuit: Parsed DGS circuit containing the graphical connections.
    :param child_block_by_slot_id: Runtime children indexed by BlkSlot FID.
    :return: None.
    """
    slot_by_id: Dict[str, BlkSlot] = dict()
    slot: BlkSlot
    signal: BlkSig

    for slot in circuit.blkslots:
        slot_by_id[slot.ID] = slot

    for signal in circuit.blksigs:
        producer_slot_id: str = str(signal.pnodfrom).strip()
        consumer_slot_id: str = str(signal.pnodto).strip()
        producer_block: Block | None = child_block_by_slot_id.get(
            producer_slot_id,
            None,
        )
        consumer_block: Block | None = child_block_by_slot_id.get(
            consumer_slot_id,
            None,
        )
        producer_slot: BlkSlot | None = slot_by_id.get(producer_slot_id, None)
        consumer_slot: BlkSlot | None = slot_by_id.get(consumer_slot_id, None)

        if (
            producer_block is None
            or consumer_block is None
            or producer_slot is None
            or consumer_slot is None
        ):
            pass
        else:
            producer_port_index: int = int(signal.inodfrom)
            consumer_port_index: int = int(signal.inodto)
            producer_ports: List[str] = producer_slot.outputs
            consumer_ports: List[str] = consumer_slot.inputs

            if (
                producer_port_index < 0
                or producer_port_index >= len(producer_ports)
                or consumer_port_index < 0
                or consumer_port_index >= len(consumer_ports)
            ):
                pass
            else:
                producer_components: List[str] = [
                    component.strip()
                    for component in producer_ports[producer_port_index].split(";")
                    if component.strip() != ""
                ]
                consumer_components: List[str] = [
                    component.strip()
                    for component in consumer_ports[consumer_port_index].split(";")
                    if component.strip() != ""
                ]

                # A scalar or vector cable is valid only when both graphical
                # endpoints declare the same component count. Ambiguous
                # broadcasts are left untouched instead of being guessed.
                if len(producer_components) != len(consumer_components):
                    pass
                else:
                    producer_vars: Dict[str, Var] = _build_runtime_interface_var_map(
                        block=producer_block,
                    )
                    consumer_vars: Dict[str, Var] = _build_runtime_interface_var_map(
                        block=consumer_block,
                    )
                    component_index: int
                    for component_index in range(len(producer_components)):
                        producer_var: Var | None = producer_vars.get(
                            producer_components[component_index],
                            None,
                        )
                        consumer_var: Var | None = consumer_vars.get(
                            consumer_components[component_index],
                            None,
                        )
                        if producer_var is None or consumer_var is None:
                            pass
                        else:
                            consumer_block.connect(
                                vars_to_subs=[consumer_var],
                                incoming_vars=[producer_var],
                            )


def build_direct_root_elmcomp_block_from_context(
        circuit: DgsCircuit,
        result: DgsRootBlockResult,
        graphical_context: DgsGraphicalParseContext | None = None,
) -> Block:
    """
    Build one root ElmComp runtime block using its direct child instances.

    Unlike ``dgs_to_root_block()``, this helper preserves repeated direct child
    instances of the same ``BlkDef`` and injects the concrete ``ElmDsl`` instance
    parameter values for each occurrence.

    :param circuit: Parsed DGS circuit.
    :param result: Parsed root selection result.
    :param graphical_context: Optional shared graphical indexes.
    :return: Runtime root block built from direct child instances.
    """
    build_result: DgsDirectRootBuildResult = _build_direct_root_elmcomp_block(
        circuit=circuit,
        result=result,
        graphical_context=graphical_context,
    )
    return build_result.root_block


def build_direct_root_elmcomp_result_from_context(
        circuit: DgsCircuit,
        result: DgsRootBlockResult,
        graphical_context: DgsGraphicalParseContext | None = None,
) -> DgsDirectRootBuildResult:
    """Build a root and expose reusable direct-child materializations.

    :param circuit: Parsed DGS circuit.
    :param result: Parsed root selection result.
    :param graphical_context: Optional shared graphical indexes.
    :return: Complete root and exact child lookup.
    """
    return _build_direct_root_elmcomp_block(
        circuit=circuit,
        result=result,
        graphical_context=graphical_context,
    )


def build_direct_root_elmcomp_block_from_dgs(
        dgs_path: str,
        root_name: str,
        root_typ_id: str | None = None,
) -> Block:
    """
    Build one root ElmComp runtime block directly from one DGS file.

    :param dgs_path: Source DGS path.
    :param root_name: Root ElmComp display name.
    :param root_typ_id: Optional exact root typ_id.
    :return: Runtime root block built from direct child instances.
    """
    circuit: DgsCircuit = DgsCircuit()
    result: DgsRootBlockResult

    circuit.parse_dgs(dgs_path)
    result = dgs_to_root_block(path=dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    return build_direct_root_elmcomp_block_from_context(circuit=circuit, result=result)

def _build_dgs_element_index(circuit: DgsCircuit) -> dict[str, object]:
    """
    Build a flat DGS object index by identifier.

    :param circuit: Parsed DGS circuit.
    :return: Dictionary from identifier to object.
    """
    element_by_id: dict[str, object] = dict()

    element_list: list[DGSElement]
    element_obj: DGSElement

    # ElmComp.pelm may reference either a dynamic child or the physical network
    # device controlled by the composite model.  Index every parsed DGS class so
    # source context is never discarded merely because it is not an ElmDsl.
    for element_list in circuit._CLASS_TO_LIST.values():
        for element_obj in element_list:
            if element_obj.ID == "":
                pass
            else:
                element_by_id[element_obj.ID] = element_obj

    return element_by_id


def _build_blkdef_index(circuit: DgsCircuit) -> dict[str, BlkDef]:
    """
    Build a BlkDef index by identifier.

    :param circuit: Parsed DGS circuit.
    :return: Dictionary from BlkDef identifier to BlkDef.
    """
    blkdef_by_id: dict[str, BlkDef] = dict()

    for blkdef in circuit.blkdefs:
        blkdef_by_id[blkdef.ID] = blkdef

    return blkdef_by_id


def _build_graphic_node_index(circuit: DgsCircuit) -> dict[str, object]:
    """
    Build index of graphical-model DGS nodes by identifier.

    :param circuit: Parsed DGS circuit.
    :return: Mapping from node id to graphic object.
    """
    node_by_id: dict[str, object] = dict()

    for obj in circuit.blkdefs:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkdivs:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkrefs:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkslots:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkfroms:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkgotos:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkmuls:
        node_by_id[obj.ID] = obj
    for obj in circuit.blksums:
        node_by_id[obj.ID] = obj
    for obj in circuit.blkswts:
        node_by_id[obj.ID] = obj

    return node_by_id


def _build_standalone_block_occurrence(blkref: BlkRef,
                                       blkdef_by_id: dict[str, BlkDef],
                                       adjacency: dict[str, set[str]]) -> DgsStandaloneBlockOccurrence | None:
    """
    Build one standalone block occurrence from one BlkRef object.

    :param blkref: Source BlkRef occurrence.
    :param blkdef_by_id: BlkDef lookup by identifier.
    :param adjacency: Graphical adjacency by node id.
    :returns: Standalone block occurrence or None when the BlkRef is invalid.
    """
    if blkref.typ_id not in blkdef_by_id:
        return None
    else:
        blkdef: BlkDef = blkdef_by_id[blkref.typ_id]
        component: set[str] = _graphic_connected_component(adjacency, blkref.ID)
        connected: bool = len(component) > 1
        sample_display_name: str = blkref.cdisName if blkref.cdisName != '' else blkdef.loc_name
        return DgsStandaloneBlockOccurrence(
            blkref_id=blkref.ID,
            typ_id=blkref.typ_id,
            blkdef_name=blkdef.loc_name,
            sample_display_name=sample_display_name,
            connected=connected,
        )


def _extract_typ_id_from_catalog_module_filename(module_filename: str) -> str | None:
    """
    Extract the typ_id prefix from one catalog module filename.

    :param module_filename: Catalog module filename.
    :returns: Extracted typ_id or None when the filename does not match the expected pattern.
    """
    match_obj = re.fullmatch(r"typ_(\d+)__.+\.py", module_filename)
    if match_obj is None:
        return None
    else:
        return match_obj.group(1)


def _build_catalog_entry_info_by_typ_id() -> Dict[str, tuple[Sequence[str], str | None]]:
    """
    Build the standalone catalog metadata lookup by typ_id from the shipped basic block catalog.

    :returns: Unsupported-lines and build-error tuple by typ_id.
    """
    from VeraGridEngine.Templates.BasicBlockCatalog import get_basic_block_catalog_descriptors

    info_by_typ_id: Dict[str, tuple[Sequence[str], str | None]] = dict()
    descriptor: object
    for descriptor in get_basic_block_catalog_descriptors():
        module_filename: str = descriptor.module_filename
        typ_id: str | None = _extract_typ_id_from_catalog_module_filename(module_filename)
        if typ_id is None:
            pass
        else:
            info_by_typ_id[typ_id] = (tuple(descriptor.unsupported_lines), None)

    return info_by_typ_id


def list_dgs_blkref_catalog_occurrences(dgs_path: str) -> List[DgsStandaloneBlockOccurrence]:
    """
    List every BlkRef occurrence that belongs to the standalone DGS block catalog.

    :param dgs_path: Source DGS file.
    :returns: Standalone block occurrences.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)
    return list_dgs_blkref_catalog_occurrences_from_context(circuit=circuit)


def list_dgs_blkref_catalog_occurrences_from_context(
        circuit: DgsCircuit,
) -> List[DgsStandaloneBlockOccurrence]:
    """List standalone ``BlkRef`` occurrences from one parsed DGS context.

    Reusing the already parsed circuit is essential for massive imports: parsing
    the complete ASCII DGS once per block definition needlessly multiplies both
    runtime and peak memory.

    :param circuit: Already parsed DGS circuit.
    :return: Standalone block occurrences.
    """
    adjacency: dict[str, set[str]] = _build_blksig_adjacency(circuit)
    blkdef_by_id: dict[str, BlkDef] = _build_blkdef_index(circuit)
    occurrences: List[DgsStandaloneBlockOccurrence] = list()
    blkref: BlkRef

    for blkref in circuit.blkrefs:
        occurrence: DgsStandaloneBlockOccurrence | None = _build_standalone_block_occurrence(blkref, blkdef_by_id, adjacency)
        if occurrence is None:
            pass
        else:
            occurrences.append(occurrence)

    return occurrences


def _build_standalone_catalog_entry(typ_id: str,
                                    occurrences: List[DgsStandaloneBlockOccurrence],
                                    parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
                                    catalog_info_by_typ_id: Dict[str, tuple[Sequence[str], str | None]]) -> DgsStandaloneBlockCatalogEntry:
    """
    Build one aggregated standalone block catalog entry.

    :param typ_id: Referenced BlkDef identifier.
    :param occurrences: Occurrences for the given type id.
    :param parsed_blocks: Parsed blocks by identifier.
    :returns: Aggregated catalog entry.
    """
    parsed_block: ParsedDgsBlockDefinition = parsed_blocks[typ_id]
    build_error: str | None = None
    unsupported_lines: List[str] = list(parsed_block.unsupported_lines)

    if typ_id in catalog_info_by_typ_id:
        stored_unsupported_lines, stored_build_error = catalog_info_by_typ_id[typ_id]
        lookup_helpers = (
            "invlapprox(", "lapprox(", "lapproxext(",
            "lapprox2(", "sapprox(", "sapprox2(",
        )
        parser_lookup_lines = [
            line for line in _split_equation_statements(parsed_block.blkdef.equations_raw)
            if any(helper in line.lower() for helper in lookup_helpers)
        ]
        # Generated descriptors may intentionally replace other source
        # diagnostics, but must not advertise unsupported lookup functions as
        # editor-ready.
        stored_lines = list(stored_unsupported_lines)
        if parser_lookup_lines:
            stored_lines = [
                line for line in stored_lines
                if line != "template_has_no_executable_content"
            ]
        unsupported_lines = list(dict.fromkeys((*stored_lines, *parser_lookup_lines)))
        build_error = stored_build_error
    else:
        shared_signals: Dict[str, Var] = dict()
        try:
            _build_block_from_parsed(parsed_block, shared_signals)
        except Exception as exc:
            build_error = str(exc)

    connected_occurrence_count: int = 0
    isolated_occurrence_count: int = 0
    occurrence: DgsStandaloneBlockOccurrence
    for occurrence in occurrences:
        if occurrence.connected:
            connected_occurrence_count += 1
        else:
            isolated_occurrence_count += 1

    return DgsStandaloneBlockCatalogEntry(
        typ_id=typ_id,
        blkdef_name=parsed_block.blkdef.loc_name,
        sample_display_name=occurrences[0].sample_display_name,
        occurrence_count=len(occurrences),
        isolated_occurrence_count=isolated_occurrence_count,
        connected_occurrence_count=connected_occurrence_count,
        unsupported_lines=unsupported_lines,
        build_error=build_error,
    )


def build_dgs_standalone_block_catalog_from_context(
        circuit: DgsCircuit,
        parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
        isolated_only: bool = True,
) -> List[DgsStandaloneBlockCatalogEntry]:
    """Build the standalone block catalogue from one parsed DGS context.

    :param circuit: Already parsed DGS circuit.
    :param parsed_blocks: Block definitions parsed once from ``circuit``.
    :param isolated_only: Keep only isolated occurrences when ``True``.
    :return: Aggregated catalogue entries.
    """
    catalog_info_by_typ_id: Dict[str, tuple[Sequence[str], str | None]] = (
        _build_catalog_entry_info_by_typ_id()
    )
    occurrences: List[DgsStandaloneBlockOccurrence] = (
        list_dgs_blkref_catalog_occurrences_from_context(circuit=circuit)
    )
    occurrences_by_typ_id: Dict[str, List[DgsStandaloneBlockOccurrence]] = dict()
    occurrence: DgsStandaloneBlockOccurrence
    for occurrence in occurrences:
        if isolated_only and occurrence.connected:
            pass
        else:
            if occurrence.typ_id not in occurrences_by_typ_id:
                occurrences_by_typ_id[occurrence.typ_id] = list()
            else:
                pass
            occurrences_by_typ_id[occurrence.typ_id].append(occurrence)

    entries: List[DgsStandaloneBlockCatalogEntry] = list()
    typ_id: str
    grouped_occurrences: List[DgsStandaloneBlockOccurrence]
    for typ_id, grouped_occurrences in occurrences_by_typ_id.items():
        entries.append(
            _build_standalone_catalog_entry(
                typ_id=typ_id,
                occurrences=grouped_occurrences,
                parsed_blocks=parsed_blocks,
                catalog_info_by_typ_id=catalog_info_by_typ_id,
            )
        )

    entries.sort(key=_standalone_catalog_entry_typ_id_sort_key)
    return entries


def build_dgs_standalone_block_catalog(
        dgs_path: str,
        isolated_only: bool = True,
) -> List[DgsStandaloneBlockCatalogEntry]:
    """
    Build the aggregated standalone DGS block catalog.

    :param dgs_path: Source DGS file.
    :param isolated_only: Keep only isolated occurrences when ``True``.
    :returns: Aggregated catalog entries.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_context(circuit=circuit)
    )
    return build_dgs_standalone_block_catalog_from_context(
        circuit=circuit,
        parsed_blocks=parsed_blocks,
        isolated_only=isolated_only,
    )


def build_standalone_blkdef_emt_template(
        dgs_path: str,
        typ_id: str,
        template_name: str | None = None,
) -> EmtModelTemplate:
    """
    Materialize one standalone DGS ``BlkDef`` as an EMT template.

    :param dgs_path: Source DGS file.
    :param typ_id: Standalone ``BlkDef`` identifier.
    :param template_name: Optional overriding template name.
    :return: Materialized EMT template.
    """
    circuit: DgsCircuit = DgsCircuit()
    shared_signals: Dict[str, Var] = dict()
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = dict()
    blkdef: BlkDef
    parsed_block: ParsedDgsBlockDefinition
    runtime_block: Block
    template: EmtModelTemplate = EmtModelTemplate()

    circuit.parse_dgs(dgs_path)

    for blkdef in circuit.blkdefs:
        parsed_blocks[blkdef.ID] = _parse_blkdef(blkdef, shared_signals)

    if typ_id in parsed_blocks:
        parsed_block = parsed_blocks[typ_id]
    else:
        raise ValueError(f"Standalone DGS block id '{typ_id}' was not found in '{dgs_path}'")

    return build_standalone_blkdef_emt_template_from_parsed_block(parsed_block=parsed_block, template_name=template_name)


def build_standalone_blkdef_emt_template_from_parsed_block(
        parsed_block: ParsedDgsBlockDefinition,
        template_name: str | None = None,
) -> EmtModelTemplate:
    """
    Materialize one standalone parsed ``BlkDef`` as an EMT template.

    :param parsed_block: Parsed standalone block definition.
    :param template_name: Optional overriding template name.
    :return: Materialized EMT template.
    """
    runtime_block: Block = _build_block_from_parsed(parsed_block, dict())
    template: EmtModelTemplate = EmtModelTemplate()

    runtime_block.name = parsed_block.blkdef.loc_name
    template.tpe = DeviceType.NoDevice

    if template_name is None:
        template.name = parsed_block.blkdef.loc_name
    else:
        template.name = str(template_name)

    template.block = runtime_block
    return template


def export_standalone_blkdef_to_python(dgs_path: str, output_path: str, block_id: str) -> Path:
    """
    Export one standalone BlkDef leaf as a Python EMT template module.

    :param dgs_path: Source DGS file.
    :param output_path: Destination `.py` file.
    :param block_id: Exact BlkDef identifier.
    :returns: Path to the generated Python module.
    """
    circuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)
    blkdef_by_id: dict[str, BlkDef] = _build_blkdef_index(circuit)

    if block_id not in blkdef_by_id:
        raise ValueError(f"Standalone BlkDef id '{block_id}' not found")
    else:
        pass

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    shared_signals: Dict[str, Var] = dict()
    parsed_block: ParsedDgsBlockDefinition = _parse_blkdef(blkdef_by_id[block_id], shared_signals)
    runtime_block: Block = _build_block_from_parsed(parsed_block, dict())
    root_element: ElmComp = ElmComp()
    root_element.loc_name = parsed_block.blkdef.loc_name
    root_element.typ_id = parsed_block.blkdef.ID
    root_result = DgsRootBlockResult(
        root_block=runtime_block,
        root_blkdef=parsed_block,
        root_element=root_element,
        parsed_blocks={parsed_block.blkdef.ID: parsed_block},
        dependency_graph=dict(),
        producer_map=dict(),
        consumer_map=dict(),
    )
    subgraph = DgsBlockSubgraphResult(
        selected_block=parsed_block,
        view_block=runtime_block,
        node_ids=set([parsed_block.blkdef.ID]),
        dependency_graph=dict(),
        upstream=dict(),
        downstream=dict(),
    )

    module_text = _emit_template_style_module(root_result, subgraph, dgs_path)
    out_path.write_text(module_text, encoding="utf-8")
    return out_path


def build_graphic_node_index(circuit: DgsCircuit) -> Dict[str, object]:
    """
    Build a public index of graphical DGS nodes by identifier.

    :param circuit: Parsed DGS circuit.
    :return: Mapping from node id to graphical object.
    """
    return _build_graphic_node_index(circuit)


def _build_blksig_adjacency(circuit: DgsCircuit) -> dict[str, set[str]]:
    """
    Build undirected adjacency graph over graphical nodes connected by BlkSig.

    :param circuit: Parsed DGS circuit.
    :return: Undirected adjacency map.
    """
    adjacency: dict[str, set[str]] = dict()

    for sig in circuit.blksigs:
        src = sig.pnodfrom.strip() if isinstance(sig.pnodfrom, str) else ''
        dst = sig.pnodto.strip() if isinstance(sig.pnodto, str) else ''

        if src == '' or dst == '':
            pass
        else:
            _append_to_string_set_map(adjacency, src, dst)
            _append_to_string_set_map(adjacency, dst, src)

    return adjacency


def _graphic_connected_component(adjacency: dict[str, set[str]], root_id: str) -> set[str]:
    """
    Return the connected component of a root graphical node.

    :param adjacency: Undirected graphical adjacency.
    :param root_id: Root node identifier.
    :return: Connected component node ids.
    """
    visited: set[str] = set()
    frontier: list[str] = [root_id]

    while frontier:
        node_id = frontier.pop()
        if node_id in visited:
            pass
        else:
            visited.add(node_id)
            for nxt in adjacency.get(node_id, set()):
                if nxt not in visited:
                    frontier.append(nxt)
                else:
                    pass

    return visited


def _graphic_node_label(node: object) -> str:
    """
    Return a human-readable label for a graphical node.

    :param node: DGS graphical node.
    :return: Display label.
    """
    if isinstance(node, BlkRef):
        return node.cdisName if node.cdisName != '' else node.typ_id
    if isinstance(node, BlkSum):
        return node.loc_name
    if isinstance(node, BlkDiv):
        return node.loc_name if node.loc_name != '' else 'Division'
    if isinstance(node, BlkMul):
        return node.loc_name if node.loc_name != '' else 'Multiplication'
    if isinstance(node, BlkSwt):
        return node.loc_name if node.loc_name != '' else 'Switch'
    if isinstance(node, BlkFrom):
        return node.loc_name
    if isinstance(node, BlkGoto):
        return node.loc_name
    if isinstance(node, BlkSlot):
        return node.loc_name
    if isinstance(node, BlkDef):
        return node.loc_name
    return str(node)


def _graphic_node_kind(node: object) -> str:
    """
    Return a short kind label for a graphical node.

    :param node: DGS graphical node.
    :return: Kind label.
    """
    if isinstance(node, BlkRef):
        return 'BlkRef'
    if isinstance(node, BlkSum):
        return 'BlkSum'
    if isinstance(node, BlkDiv):
        return 'BlkDiv'
    if isinstance(node, BlkMul):
        return 'BlkMul'
    if isinstance(node, BlkSwt):
        return 'BlkSwt'
    if isinstance(node, BlkFrom):
        return 'BlkFrom'
    if isinstance(node, BlkGoto):
        return 'BlkGoto'
    if isinstance(node, BlkSlot):
        return 'BlkSlot'
    if isinstance(node, BlkDef):
        return 'BlkDef'
    return type(node).__name__


def _graphic_node_to_block(
    node_id: str,
    node: object,
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition],
) -> Block:
    """
    Convert one graphical node into a lightweight Block for visualization.

    :param node_id: Node identifier.
    :param node: Graphical node object.
    :param parsed_blocks: Parsed block definitions.
    :return: Visualization block.
    """
    if isinstance(node, BlkRef):
        parsed = parsed_blocks.get(node.typ_id)
        if parsed is not None:
            blk = _build_block_from_parsed(parsed, dict())
            blk.name = _graphic_node_label(node)
            return blk

    blk = Block(name=_graphic_node_label(node))
    return blk


def _build_graphic_node_signal_map(circuit: DgsCircuit) -> dict[str, set[str]]:
    """
    Collect normalized signal labels attached to each graphical node through BlkSig and BlkFrom definitions.

    :param circuit: Parsed DGS circuit.
    :return: Mapping from node id to normalized signal labels.
    """
    node_signals: dict[str, set[str]] = dict()

    for sig in circuit.blksigs:
        sig_name = _normalize_graph_signal_name(sig.loc_name)
        if sig_name == '':
            pass
        else:
            if isinstance(sig.pnodfrom, str) and sig.pnodfrom.strip() != '':
                _append_to_string_set_map(node_signals, sig.pnodfrom.strip(), sig_name)
            else:
                pass

            if isinstance(sig.pnodto, str) and sig.pnodto.strip() != '':
                _append_to_string_set_map(node_signals, sig.pnodto.strip(), sig_name)
            else:
                pass

    for blk_from in circuit.blkfroms:
        for sig_name in blk_from.signals:
            clean = _normalize_graph_signal_name(sig_name)
            if clean != '':
                _append_to_string_set_map(node_signals, blk_from.ID, clean)

    for blk_goto in circuit.blkgotos:
        for sig_name in blk_goto.signals:
            clean = _normalize_graph_signal_name(sig_name)
            if clean != '':
                _append_to_string_set_map(node_signals, blk_goto.ID, clean)
            else:
                pass
        else:
            pass

    return node_signals


def _collect_routed_graphical_source_signal_names(
        node_ids: Set[str],
        node_by_id: Dict[str, object],
        node_signals: Dict[str, Set[str]],
) -> Set[str]:
    """Collect signal names read by native graphical ``BlkFrom`` nodes.

    A blank ``BlkSig.pnodfrom`` is normally an intentional zero-valued pin.
    If a ``BlkFrom`` elsewhere reads the same exact signal, however, the signal
    is live and the blank pointer proves that an operator node was omitted from
    the DGS definition. This distinction prevents silent zero substitution.

    :param node_ids: Graphical component identifiers.
    :param node_by_id: Parsed graphical object lookup.
    :param node_signals: Normalized signal names attached to each node.
    :return: Live routed signal names in the selected component.
    """
    routed_signal_names: Set[str] = set()
    node_id: str
    for node_id in node_ids:
        if isinstance(node_by_id.get(node_id, None), BlkFrom):
            routed_signal_names.update(node_signals.get(node_id, set()))
        else:
            pass
    else:
        pass
    return routed_signal_names


def build_dgs_graphical_parse_context(
        circuit: DgsCircuit,
) -> DgsGraphicalParseContext:
    """Build graphical indexes once for a massive DGS import.

    :param circuit: Already parsed DGS circuit.
    :return: Shared immutable graphical parse context.
    """
    return DgsGraphicalParseContext(
        adjacency=_build_blksig_adjacency(circuit=circuit),
        node_by_id=_build_graphic_node_index(circuit=circuit),
        node_signals=_build_graphic_node_signal_map(circuit=circuit),
        element_by_id=_build_dgs_element_index(circuit=circuit),
    )


def get_blkslot_signal_interface(circuit: DgsCircuit, slot_id: str | None) -> Tuple[List[str], List[str]]:
    """
    Return the normalized incoming and outgoing signal names attached to one ``BlkSlot``.

    :param circuit: Parsed DGS circuit.
    :param slot_id: Target ``BlkSlot`` identifier.
    :return: Pair ``(incoming_signals, outgoing_signals)``.
    """
    incoming: Set[str] = set()
    outgoing: Set[str] = set()
    sig: BlkSig
    slot_key: str

    if slot_id is None:
        return list(), list()
    else:
        slot_key = str(slot_id).strip()

    if slot_key == '':
        return list(), list()
    else:
        pass

    for sig in circuit.blksigs:
        sig_name = _normalize_graph_signal_name(sig.loc_name)
        if sig_name == '':
            pass
        else:
            if str(sig.pnodto).strip() == slot_key:
                incoming.add(sig_name)
            else:
                pass

            if str(sig.pnodfrom).strip() == slot_key:
                outgoing.add(sig_name)
            else:
                pass

    return sorted(incoming), sorted(outgoing)


def _build_graph_signal_alias_map(
    node_ids: Set[str],
    node_by_id: Dict[str, object],
    node_signals: Dict[str, Set[str]],
) -> Dict[str, Set[str]]:
    parent: Dict[str, str] = dict()

    for node_id in node_ids:
        node = node_by_id.get(node_id)
        if isinstance(node, (BlkFrom, BlkGoto)):
            aliases = sorted(node_signals.get(node_id, set()))
            if len(aliases) < 2:
                pass
            else:
                head = aliases[0]
                for alias in aliases[1:]:
                    _disjoint_set_union(parent, head, alias)
        else:
            pass

    groups: Dict[str, Set[str]] = dict()
    for signal_names in node_signals.values():
        for sig in signal_names:
            root = _disjoint_set_find(parent, sig)
            _append_to_string_set_map(groups, root, sig)

    alias_map: Dict[str, Set[str]] = dict()
    for group in groups.values():
        for sig in group:
            alias_map[sig] = set(group)

    return alias_map


def _build_augmented_graphical_adjacency(
    node_ids: Set[str],
    adjacency: Dict[str, Set[str]],
    node_by_id: Dict[str, object],
    node_signals: Dict[str, Set[str]],
    alias_map: Dict[str, Set[str]],
) -> Dict[str, Set[str]]:
    expanded: Dict[str, Set[str]] = dict()
    node_id: str
    for node_id in node_ids:
        expanded[node_id] = _build_filtered_neighbor_set(adjacency, node_id, node_ids)

    routing_nodes: List[str] = [
        node_id for node_id in node_ids
        if isinstance(node_by_id.get(node_id), (BlkFrom, BlkGoto))
    ]

    for idx, left_id in enumerate(routing_nodes):
        left_aliases: Set[str] = set()
        for sig in node_signals.get(left_id, set()):
            left_aliases |= alias_map.get(sig, {sig})

        if len(left_aliases) == 0:
            pass
        else:
            for right_id in routing_nodes[idx + 1:]:
                right_aliases: Set[str] = set()
                for sig in node_signals.get(right_id, set()):
                    right_aliases |= alias_map.get(sig, {sig})

                if len(left_aliases & right_aliases) == 0:
                    pass
                else:
                    _append_to_string_set_map(expanded, left_id, right_id)
                    _append_to_string_set_map(expanded, right_id, left_id)

    return expanded


def _graph_distance(adjacency: Dict[str, Set[str]], start_node: str, target_node: str) -> int:
    if start_node == target_node:
        return 0

    visited: Set[str] = set()
    frontier: List[Tuple[str, int]] = [(start_node, 0)]

    while frontier:
        node_id, dist = frontier.pop(0)
        if node_id in visited:
            pass
        else:
            visited.add(node_id)

            for nxt in adjacency.get(node_id, set()):
                if nxt == target_node:
                    return dist + 1
                elif nxt not in visited:
                    frontier.append((nxt, dist + 1))
                else:
                    pass

    return 10**9


def _node_signal_aliases(node_id: str, node_signals: Dict[str, Set[str]], alias_map: Dict[str, Set[str]]) -> Set[str]:
    aliases: Set[str] = set()
    for sig in node_signals.get(node_id, set()):
        aliases |= alias_map.get(sig, {sig})
    return aliases


def _resolve_graphic_block_connections(
    selected_block: ParsedDgsBlockDefinition,
    child_node_ids: List[str],
    child_blocks: Dict[str, Block],
    child_input_specs: Dict[str, List[str]],
    child_input_index_by_connector: Dict[
        str,
        Dict[Tuple[DgsGraphicalConnectorKind, int], int],
    ],
    child_output_specs: Dict[str, List[str]],
    graphical_signals: List[BlkSig],
    adjacency: Dict[str, Set[str]],
    node_by_id: Dict[str, object],
    node_signals: Dict[str, Set[str]],
    alias_map: Dict[str, Set[str]],
    root_runtime_block: Block,
) -> Tuple[List[GraphicConnectionInstruction], List[Var]]:
    """Resolve graphical cables by endpoint identity, then by signal aliases.

    ``BlkSig`` connector categories are authoritative because PowerFactory
    stores ordinary, lower-limit and upper-limit pins in independent index
    spaces. Signal text remains a fallback for routes passing through
    ``BlkFrom``/``BlkGoto`` nodes.

    :param selected_block: Parsed graphical macro definition.
    :param child_node_ids: Exact graphical child identifiers.
    :param child_blocks: Runtime blocks keyed by graphical node identifier.
    :param child_input_specs: Runtime input names by child identifier.
    :param child_input_index_by_connector: Runtime indices by connector tuple.
    :param child_output_specs: Output names by child identifier.
    :param graphical_signals: Exact DGS graphical cables.
    :param adjacency: Augmented graphical adjacency.
    :param node_by_id: Graphical object index retained for diagnostics.
    :param node_signals: Signal labels attached to graphical nodes.
    :param alias_map: Equivalent graphical signal labels.
    :param root_runtime_block: Runtime representation of the macro boundary.
    :return: Connection instructions and resolved macro outputs.
    """
    _ = node_by_id
    producer_entries: List[Tuple[str, str, Var]] = list()
    root_signal_vars = _build_name_to_var_map(
        list(root_runtime_block.in_vars)
        + list(root_runtime_block.out_vars)
        + list(root_runtime_block.algebraic_vars)
        + list(root_runtime_block.state_vars)
    )

    for node_id in child_node_ids:
        block = child_blocks[node_id]
        for output_index, output_name in enumerate(child_output_specs.get(node_id, list())):
            if output_index < len(block.out_vars):
                producer_entries.append((node_id, output_name, block.out_vars[output_index]))

    connections: List[GraphicConnectionInstruction] = list()
    connected_consumer_inputs: Set[Tuple[str, int]] = set()
    explicitly_disconnected_consumer_inputs: Set[Tuple[str, int]] = set()
    routed_aliases_by_consumer_input: Dict[Tuple[str, int], Set[str]] = dict()
    routed_aliases_by_producer_output: Dict[Tuple[str, int], Set[str]] = dict()
    root_node_id: str = str(selected_block.blkdef.ID)
    root_runtime_input_names: List[str] = _build_blkdef_runtime_input_names(
        blkdef=selected_block.blkdef,
    )
    root_input_index_by_connector: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        int,
    ] = _build_blkdef_runtime_input_index_by_connector(
        blkdef=selected_block.blkdef,
    )
    concrete_source_signal_names: Set[str] = set()
    routed_source_signal_names: Set[str] = (
        _collect_routed_graphical_source_signal_names(
            node_ids=set(adjacency.keys()),
            node_by_id=node_by_id,
            node_signals=node_signals,
        )
    )
    graphical_signal: BlkSig

    # A split cable can contain one blank fragment and one concrete producer
    # fragment with the same label. Record those labels before classifying any
    # blank endpoint as a genuinely disconnected PowerFactory input.
    for graphical_signal in graphical_signals:
        concrete_source_node_id: str = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodfrom,
        )
        concrete_source_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(graphical_signal.iconfrom),
                endpoint_node=node_by_id.get(concrete_source_node_id, None),
                is_source_endpoint=True,
            )
        )
        if (
                concrete_source_node_id in child_blocks
                and concrete_source_kind == DgsGraphicalConnectorKind.Output
        ):
            concrete_source_signal_names.add(
                _normalize_graph_signal_name(
                    name=graphical_signal.loc_name,
                )
            )
        elif concrete_source_node_id == root_node_id:
            concrete_source_signal_names.add(
                _normalize_graph_signal_name(
                    name=graphical_signal.loc_name,
                )
            )
        else:
            pass
    else:
        pass

    # First reproduce every direct cable from its exact graphical endpoints.
    # This is the only lossless path for visually hidden limiter pins because
    # each special connector category starts its own local index at zero.
    for graphical_signal in graphical_signals:
        source_node_id: str = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodfrom,
        )
        consumer_node_id: str = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodto,
        )
        consumer_connector_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(graphical_signal.iconto),
                endpoint_node=node_by_id.get(consumer_node_id, None),
                is_source_endpoint=False,
            )
        )
        source_connector_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(graphical_signal.iconfrom),
                endpoint_node=node_by_id.get(source_node_id, None),
                is_source_endpoint=True,
            )
        )
        explicit_signal_name: str = _normalize_graph_signal_name(
            name=graphical_signal.loc_name,
        )

        # Retain semantic labels per exact primitive output. A graphical block
        # can have many input and output cables, so node-wide labels would make
        # one generic ``yo`` appear to produce every signal touching the node.
        if (
                source_node_id in child_blocks
                and source_connector_kind == DgsGraphicalConnectorKind.Output
        ):
            routed_source_output_names: List[str] = child_output_specs.get(
                source_node_id,
                list(),
            )
            routed_source_output_index: int | None = (
                _resolve_graphical_runtime_output_index(
                    endpoint_node=node_by_id.get(source_node_id, None),
                    graphical_output_index=int(graphical_signal.inodfrom),
                    runtime_output_count=len(routed_source_output_names),
                )
            )
            if routed_source_output_index is None:
                pass
            else:
                routed_source_key: Tuple[str, int] = (
                    source_node_id,
                    routed_source_output_index,
                )
                routed_source_aliases: Set[str] = (
                    routed_aliases_by_producer_output.get(
                        routed_source_key,
                        set(),
                    )
                )
                routed_source_aliases.update(
                    alias_map.get(explicit_signal_name, {explicit_signal_name})
                )
                routed_aliases_by_producer_output[routed_source_key] = (
                    routed_source_aliases
                )
        else:
            pass

        # A concrete consumer endpoint with no producer and no matching split
        # producer fragment is explicitly disconnected. Preserve that fact so
        # the later semantic-name fallback cannot attach a homonymous signal
        # from another branch of the same graphical macro.
        if consumer_connector_kind is None:
            explicit_consumer_runtime_index: int | None = None
        else:
            explicit_consumer_runtime_index = (
                child_input_index_by_connector.get(
                    consumer_node_id,
                    dict(),
                ).get(
                    (
                        consumer_connector_kind,
                        int(graphical_signal.inodto),
                    ),
                    None,
                )
            )
        if (
                consumer_node_id in child_blocks
                and source_node_id == ""
                and explicit_consumer_runtime_index is not None
                and explicit_signal_name not in concrete_source_signal_names
                and explicit_signal_name not in routed_source_signal_names
        ):
            explicitly_disconnected_consumer_inputs.add((
                consumer_node_id,
                explicit_consumer_runtime_index,
            ))
        else:
            pass

        if (
                consumer_node_id in child_blocks
                and consumer_connector_kind in {
                    DgsGraphicalConnectorKind.Input,
                    DgsGraphicalConnectorKind.LowerLimitInput,
                    DgsGraphicalConnectorKind.UpperLimitInput,
                }
        ):
            consumer_runtime_index: int | None = (
                child_input_index_by_connector.get(
                    consumer_node_id,
                    dict(),
                ).get(
                    (
                        consumer_connector_kind,
                        int(graphical_signal.inodto),
                    ),
                    None,
                )
                if consumer_connector_kind is not None
                else None
            )
            if consumer_runtime_index is None:
                pass
            else:
                consumer_key: Tuple[str, int] = (
                    consumer_node_id,
                    consumer_runtime_index,
                )
                # A BlkFrom/BlkGoto cable often reaches a primitive port named
                # only ``yi``. Preserve the exact cable and routing-node labels
                # so the later fallback follows the native named route instead
                # of searching for an unrelated producer also called ``yi``.
                routed_aliases: Set[str] = (
                    routed_aliases_by_consumer_input.get(
                        consumer_key,
                        set(),
                    )
                )
                routed_aliases.update(
                    alias_map.get(explicit_signal_name, {explicit_signal_name})
                )
                if isinstance(
                        node_by_id.get(source_node_id, None),
                        (BlkFrom, BlkGoto),
                ):
                    routed_aliases.update(
                        _node_signal_aliases(
                            node_id=source_node_id,
                            node_signals=node_signals,
                            alias_map=alias_map,
                        )
                    )
                else:
                    pass
                routed_aliases_by_consumer_input[consumer_key] = routed_aliases
                if consumer_key in connected_consumer_inputs:
                    pass
                elif (
                        source_node_id in child_blocks
                        and source_connector_kind
                        == DgsGraphicalConnectorKind.Output
                ):
                    source_output_names: List[str] = child_output_specs.get(
                        source_node_id,
                        list(),
                    )
                    source_output_index: int | None = (
                        _resolve_graphical_runtime_output_index(
                            endpoint_node=node_by_id.get(source_node_id, None),
                            graphical_output_index=int(graphical_signal.inodfrom),
                            runtime_output_count=len(source_output_names),
                        )
                    )
                    if source_output_index is None:
                        pass
                    else:
                        consumer_input_names: List[str] = child_input_specs.get(
                            consumer_node_id,
                            list(),
                        )
                        connections.append(
                            GraphicConnectionInstruction(
                                consumer_node_id=consumer_node_id,
                                consumer_input_name=consumer_input_names[
                                    consumer_runtime_index
                                ],
                                source_kind="block_output",
                                consumer_input_index=consumer_runtime_index,
                                source_node_id=source_node_id,
                                source_output_name=source_output_names[
                                    source_output_index
                                ],
                                source_output_index=source_output_index,
                            )
                        )
                        connected_consumer_inputs.add(consumer_key)
                elif source_node_id == root_node_id:
                    root_runtime_input_index: int | None
                    graphical_root_input_name: str = (
                        _normalize_graph_signal_name(
                            name=graphical_signal.loc_name,
                        )
                    )
                    if source_connector_kind is None:
                        root_runtime_input_index = None
                    else:
                        root_runtime_input_index = (
                            root_input_index_by_connector.get(
                                (
                                    source_connector_kind,
                                    int(graphical_signal.inodfrom),
                                ),
                                None,
                            )
                        )
                    source_root_name: str | None
                    if graphical_root_input_name in root_signal_vars:
                        # Macro pin ordinals can retain holes for hidden or
                        # removed ports that are absent from compact ``cInput``.
                        # The cable label is the exact boundary symbol and is
                        # therefore authoritative when it names a live port.
                        source_root_name = graphical_root_input_name
                    else:
                        if (
                                root_runtime_input_index is None
                                or root_runtime_input_index
                                >= len(root_runtime_input_names)
                        ):
                            source_root_name = None
                        else:
                            source_root_name = root_runtime_input_names[
                                root_runtime_input_index
                            ]
                    if (
                            source_root_name is None
                            or source_root_name not in root_signal_vars
                    ):
                        pass
                    else:
                        consumer_input_names = child_input_specs.get(
                            consumer_node_id,
                            list(),
                        )
                        connections.append(
                            GraphicConnectionInstruction(
                                consumer_node_id=consumer_node_id,
                                consumer_input_name=consumer_input_names[
                                    consumer_runtime_index
                                ],
                                source_kind="root_input",
                                consumer_input_index=consumer_runtime_index,
                                source_root_name=source_root_name,
                            )
                        )
                        connected_consumer_inputs.add(consumer_key)
                else:
                    pass
        else:
            pass

    for consumer_node_id in child_node_ids:
        for input_index, input_name in enumerate(child_input_specs.get(consumer_node_id, list())):
            consumer_key = (consumer_node_id, input_index)
            if consumer_key in connected_consumer_inputs:
                pass
            elif consumer_key in explicitly_disconnected_consumer_inputs:
                pass
            else:
                generic_input_aliases: Set[str] = set(
                    alias_map.get(input_name, {input_name})
                )
                routed_input_aliases: Set[str] = set(
                    routed_aliases_by_consumer_input.get(
                        consumer_key,
                        set(),
                    )
                )
                # The label carried by an exact DGS cable outranks the generic
                # primitive pin name. This matters for BlkFrom/BlkGoto routes:
                # a port called ``yi`` can be graphically connected to
                # ``Vt_filt`` while a nearer, unrelated primitive also exports
                # ``yi``. Mixing both alias sets lets graph distance select the
                # wrong arithmetic operand even though the DGS route is exact.
                if len(routed_input_aliases) > 0:
                    input_aliases: Set[str] = routed_input_aliases
                else:
                    input_aliases = generic_input_aliases
                candidates: List[Tuple[int, int, str, str]] = list()

                for producer_node_id, output_name, _out_var in producer_entries:
                    # Primitive outputs are commonly named ``yo`` even though
                    # their outgoing cable carries a semantic signal such as
                    # ``Vt_filt``. Both identities belong to this exact node.
                    producer_aliases: Set[str] = set(
                        alias_map.get(output_name, {output_name})
                    )
                    producer_output_index: int = child_output_specs.get(
                        producer_node_id,
                        list(),
                    ).index(output_name)
                    producer_aliases.update(
                        routed_aliases_by_producer_output.get(
                            (producer_node_id, producer_output_index),
                            set(),
                        )
                    )
                    if producer_node_id == consumer_node_id:
                        pass
                    elif len(input_aliases & producer_aliases) == 0:
                        pass
                    else:
                        distance = _graph_distance(adjacency, consumer_node_id, producer_node_id)
                        exact_score = 0 if output_name == input_name else 1
                        candidates.append((exact_score, distance, producer_node_id, output_name))

                if len(candidates) > 0:
                    candidates.sort()
                    best = candidates[0]
                    connections.append(
                        GraphicConnectionInstruction(
                            consumer_node_id=consumer_node_id,
                            consumer_input_name=input_name,
                            source_kind="block_output",
                            consumer_input_index=input_index,
                            source_node_id=best[2],
                            source_output_name=best[3],
                            source_output_index=child_output_specs.get(best[2], list()).index(best[3]),
                        )
                    )
                else:
                    root_candidates = [name for name in root_signal_vars.keys() if len(alias_map.get(name, {name}) & input_aliases) > 0]
                    if len(root_candidates) > 0:
                        _sort_candidate_names_with_preferred_first(root_candidates, input_name)
                        connections.append(
                            GraphicConnectionInstruction(
                                consumer_node_id=consumer_node_id,
                                consumer_input_name=input_name,
                                source_kind="root_input",
                                consumer_input_index=input_index,
                                source_root_name=root_candidates[0],
                            )
                        )
                    else:
                        pass

    resolved_outputs: List[Var] = list()
    producer_wire_entries: List[Tuple[str, str, Var]] = list()
    root_boundary_labels_by_index: Dict[int, Set[str]] = dict()
    graphical_signal: BlkSig
    for graphical_signal in graphical_signals:
        source_node_id = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodfrom,
        )
        consumer_node_id = _normalize_dgs_pointer_id(
            pointer_value=graphical_signal.pnodto,
        )
        source_connector_kind = _parse_effective_graphical_connector_kind(
            connector_code=int(graphical_signal.iconfrom),
            endpoint_node=node_by_id.get(source_node_id, None),
            is_source_endpoint=True,
        )
        consumer_connector_kind = _parse_effective_graphical_connector_kind(
            connector_code=int(graphical_signal.iconto),
            endpoint_node=node_by_id.get(consumer_node_id, None),
            is_source_endpoint=False,
        )
        graphical_label: str = _normalize_graph_signal_name(
            name=graphical_signal.loc_name,
        )
        if (
                source_node_id in child_blocks
                and source_connector_kind == DgsGraphicalConnectorKind.Output
        ):
            producer_block: Block = child_blocks[source_node_id]
            producer_output_index: int | None = (
                _resolve_graphical_runtime_output_index(
                    endpoint_node=node_by_id.get(source_node_id, None),
                    graphical_output_index=int(graphical_signal.inodfrom),
                    runtime_output_count=len(producer_block.out_vars),
                )
            )
            if producer_output_index is None:
                pass
            else:
                producer_wire_entries.append((
                    graphical_label,
                    source_node_id,
                    producer_block.out_vars[producer_output_index],
                ))
        else:
            pass

        if (
                consumer_node_id == root_node_id
                and consumer_connector_kind == DgsGraphicalConnectorKind.Output
        ):
            root_boundary_index: int = int(graphical_signal.inodto)
            if root_boundary_index not in root_boundary_labels_by_index:
                root_boundary_labels_by_index[root_boundary_index] = set()
            else:
                pass
            root_boundary_labels_by_index[root_boundary_index].add(
                graphical_label
            )
        else:
            pass
    else:
        pass

    root_output_index: int
    for root_output_index in range(len(root_runtime_block.out_vars)):
        output_var: Var = root_runtime_block.out_vars[root_output_index]
        output_name = output_var.name
        output_aliases = alias_map.get(output_name, {output_name})
        output_candidates: List[Tuple[int, int, str, Var]] = list()
        for producer_node_id, producer_output_name, out_var in producer_entries:
            if len(output_aliases & alias_map.get(producer_output_name, {producer_output_name})) == 0:
                pass
            else:
                distance = _graph_distance(adjacency, producer_node_id, selected_block.blkdef.ID)
                exact_score = 0 if producer_output_name == output_name else 1
                output_candidates.append((exact_score, distance, producer_node_id, out_var))

        if len(output_candidates) > 0:
            output_candidates.sort()
            resolved_outputs.append(output_candidates[0][3])
        else:
            # A macro output can be exported as two wire fragments with blank
            # intermediate endpoints. Port indices identify the boundary and
            # the private/public label stems identify the producer without
            # globally joining unrelated blank endpoints.
            boundary_labels: Set[str] = root_boundary_labels_by_index.get(
                root_output_index,
                set(),
            )
            boundary_stems: Set[str] = set()
            boundary_label: str
            for boundary_label in boundary_labels:
                boundary_stems.add(
                    _normalize_graph_interface_stem(name=boundary_label)
                )
            else:
                pass
            split_wire_candidates: List[Tuple[int, int, str, Var]] = list()
            producer_wire_entry: Tuple[str, str, Var]
            for producer_wire_entry in producer_wire_entries:
                producer_label: str = producer_wire_entry[0]
                producer_node_id = producer_wire_entry[1]
                producer_var: Var = producer_wire_entry[2]
                producer_stem: str = _normalize_graph_interface_stem(
                    name=producer_label,
                )
                if producer_stem not in boundary_stems or producer_stem == "":
                    pass
                else:
                    split_wire_exact_score: int = (
                        0 if producer_label in boundary_labels else 1
                    )
                    split_wire_distance: int = _graph_distance(
                        adjacency,
                        producer_node_id,
                        selected_block.blkdef.ID,
                    )
                    split_wire_candidates.append((
                        split_wire_exact_score,
                        split_wire_distance,
                        producer_node_id,
                        producer_var,
                    ))
            else:
                pass
            if len(split_wire_candidates) == 0:
                resolved_outputs.append(output_var)
            else:
                split_wire_candidates.sort()
                resolved_outputs.append(split_wire_candidates[0][3])

    return connections, resolved_outputs


def _blk_sum_slot_raw_mode(blk_sum: BlkSum, slot: int) -> int:
    if slot == 0:
        return int(blk_sum.iInput0)
    if slot == 1:
        return int(blk_sum.iInput1)
    if slot == 2:
        return int(blk_sum.iInput2)
    if slot == 3:
        return int(blk_sum.iInput3)
    return 2


def get_blk_sum_slot_raw_mode(blk_sum: BlkSum, slot: int) -> int:
    """
    Return the raw sign/mode code stored in a BlkSum input slot.

    :param blk_sum: DGS sum block.
    :param slot: Input slot index.
    :return: Raw DGS slot mode.
    """
    return _blk_sum_slot_raw_mode(blk_sum, slot)


def _blk_sum_slot_active_mode(blk_sum: BlkSum, slot: int) -> int:
    if slot == 0:
        return int(blk_sum.iInput0_act)
    if slot == 1:
        return int(blk_sum.iInput1_act)
    if slot == 2:
        return int(blk_sum.iInput2_act)
    if slot == 3:
        return int(blk_sum.iInput3_act)
    return 2


def get_blk_sum_slot_active_mode(blk_sum: BlkSum, slot: int) -> int:
    """
    Return the active sign/mode code stored in a BlkSum input slot.

    :param blk_sum: DGS sum block.
    :param slot: Input slot index.
    :return: Active DGS slot mode.
    """
    return _blk_sum_slot_active_mode(blk_sum, slot)


def _blk_sum_slot_mode(blk_sum: BlkSum, slot: int) -> int:
    active_mode = _blk_sum_slot_active_mode(blk_sum, slot)
    if active_mode in {0, 1, 2}:
        return active_mode
    return _blk_sum_slot_raw_mode(blk_sum, slot)


def _blk_sum_signal_specs(
    blk_sum: BlkSum,
    circuit: DgsCircuit,
) -> Tuple[List[Tuple[str, float]], List[str]]:
    incoming_by_slot: Dict[int, str] = dict()
    outgoing_signals: List[str] = list()

    for sig in circuit.blksigs:
        clean = _normalize_graph_signal_name(sig.loc_name)
        if clean == '':
            pass
        else:
            if sig.pnodto == blk_sum.ID:
                incoming_by_slot[int(sig.inodto)] = clean
            else:
                pass
            if sig.pnodfrom == blk_sum.ID:
                outgoing_signals.append(clean)
            else:
                pass

    input_terms: List[Tuple[str, float]] = list()
    for slot in range(4):
        sig_name = incoming_by_slot.get(slot, None)
        if sig_name is None:
            pass
        else:
            mode = _blk_sum_slot_mode(blk_sum, slot)
            if mode == 2:
                pass
            else:
                coeff = 1.0 if mode == 0 else -1.0
                input_terms.append((sig_name, coeff))

    outputs: List[str] = list()
    for sig_name in outgoing_signals:
        if sig_name not in outputs:
            outputs.append(sig_name)

    return input_terms, outputs


def get_blk_sum_signal_specs(
    blk_sum: BlkSum,
    circuit: DgsCircuit,
) -> Tuple[List[Tuple[str, float]], List[str]]:
    """
    Return the effective input terms and outputs of a DGS sum block.

    :param blk_sum: DGS sum block.
    :param circuit: Parsed DGS circuit.
    :return: Tuple with signed input terms and output signal names.
    """
    return _blk_sum_signal_specs(blk_sum, circuit)


def _build_sum_block_from_graphic_node(blk_sum: BlkSum, circuit: DgsCircuit) -> Tuple[Block, List[str], List[str]]:
    input_terms, outputs = _blk_sum_signal_specs(blk_sum, circuit)

    if len(outputs) == 0:
        output_name = _safe_name(blk_sum.loc_name if blk_sum.loc_name != '' else blk_sum.ID)
        outputs = [output_name]

    out_var = Var(name=outputs[0])
    in_vars: List[Var] = list()
    rhs: Expr = Const(0.0)
    input_names: List[str] = list()

    for input_name, coeff in input_terms:
        in_var = Var(name=input_name)
        in_vars.append(in_var)
        input_names.append(input_name)
        rhs = rhs + (Const(coeff) * in_var)

    block = Block(
        algebraic_eqs=[out_var - rhs],
        algebraic_vars=[out_var],
        in_vars=in_vars,
        out_vars=[out_var],
        # ``BlkSum`` has no accompanying BlkDef ``inc()`` surface. Replay its
        # exact directed assignment once the graphical cables and physical
        # measurements are final so every exported sum starts consistently.
        post_init_seed_eqs=dict([(out_var, rhs)]),
        name=blk_sum.loc_name if blk_sum.loc_name != '' else 'Sum',
    )
    return block, input_names, outputs


def _build_sum_runtime_input_index_by_connector(
        blk_sum: BlkSum,
        circuit: DgsCircuit,
) -> Dict[Tuple[DgsGraphicalConnectorKind, int], int]:
    """Map sparse native summation ports to compact runtime inputs.

    PowerFactory retains four raw ``BlkSum`` slots and can disable any of
    them. VeraGrid omits disabled slots from ``Block.in_vars``, so raw
    ``inodto`` values must be compacted in the same active-slot order used by
    :func:`_build_sum_block_from_graphic_node`.

    :param blk_sum: Native graphical summation node.
    :param circuit: Parsed DGS circuit containing its cables.
    :return: Runtime input indices keyed by ordinary connector and raw slot.
    """
    incoming_slots: Set[int] = set()
    signal: BlkSig
    for signal in circuit.blksigs:
        if (
                _normalize_dgs_pointer_id(signal.pnodto) == str(blk_sum.ID)
                and _normalize_graph_signal_name(signal.loc_name) != ""
        ):
            incoming_slots.add(int(signal.inodto))
        else:
            pass
    else:
        pass

    result: Dict[Tuple[DgsGraphicalConnectorKind, int], int] = dict()
    runtime_input_index: int = 0
    raw_slot_index: int
    for raw_slot_index in range(4):
        slot_is_executable: bool = (
            raw_slot_index in incoming_slots
            and _blk_sum_slot_mode(blk_sum, raw_slot_index) != 2
        )
        if slot_is_executable:
            result[
                (DgsGraphicalConnectorKind.Input, raw_slot_index)
            ] = runtime_input_index
            runtime_input_index += 1
        else:
            pass
    else:
        pass
    return result


def _collect_graphical_operator_signal_specs(
        node: BlkMul | BlkDiv | BlkSwt,
        circuit: DgsCircuit,
) -> Tuple[List[Tuple[int, str]], List[Tuple[int, str]]]:
    """Collect ordered ordinary inputs and outputs for one native operator.

    PowerFactory stores the executable ports on ``BlkSig`` rather than on
    ``BlkMul`` and ``BlkDiv`` themselves. Keeping the raw connector indices
    makes the reconstruction independent of cable labels and diagram layout.

    :param node: Exact parsed graphical operator.
    :param circuit: Parsed DGS circuit containing the signal rows.
    :return: Ordered ``(port index, signal name)`` input/output pairs.
    """
    incoming_by_index: Dict[int, str] = dict()
    outgoing_by_index: Dict[int, str] = dict()
    node_id: str = str(node.ID)
    signal: BlkSig

    # Connector direction and local port index are the lossless operator API.
    for signal in circuit.blksigs:
        signal_name: str = _normalize_graph_signal_name(name=signal.loc_name)
        source_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(signal.iconfrom),
                endpoint_node=node,
                is_source_endpoint=True,
            )
        )
        target_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(signal.iconto),
                endpoint_node=node,
                is_source_endpoint=False,
            )
        )
        if (
                _normalize_dgs_pointer_id(signal.pnodto) == node_id
                and target_kind == DgsGraphicalConnectorKind.Input
                and signal_name != ''
        ):
            incoming_by_index[int(signal.inodto)] = signal_name
        else:
            pass
        if (
                _normalize_dgs_pointer_id(signal.pnodfrom) == node_id
                and source_kind == DgsGraphicalConnectorKind.Output
                and signal_name != ''
        ):
            outgoing_by_index[int(signal.inodfrom)] = signal_name
        else:
            pass
    else:
        pass

    incoming_signals: List[Tuple[int, str]] = sorted(incoming_by_index.items())
    outgoing_signals: List[Tuple[int, str]] = sorted(outgoing_by_index.items())
    return incoming_signals, outgoing_signals


def _build_graphical_arithmetic_block(
        node: BlkMul | BlkDiv,
        circuit: DgsCircuit,
) -> Tuple[
    Block,
    List[str],
    List[str],
    Dict[Tuple[DgsGraphicalConnectorKind, int], int],
]:
    """Materialize a native PowerFactory product or division node.

    A multiplier returns the product of every ordered input. A divider uses
    port zero as numerator and divides it successively by the remaining ports,
    matching PowerFactory's graphical numerator/denominator ordering. Multiple
    output dots expose the same operator result.

    :param node: Parsed ``BlkMul`` or ``BlkDiv`` node.
    :param circuit: Parsed DGS circuit containing its signal rows.
    :return: Runtime block, input names, output names and exact input-port map.
    """
    incoming_signals: List[Tuple[int, str]]
    outgoing_signals: List[Tuple[int, str]]
    incoming_signals, outgoing_signals = _collect_graphical_operator_signal_specs(
        node=node,
        circuit=circuit,
    )
    input_vars: List[Var] = list()
    input_names: List[str] = list()
    input_index_by_connector: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        int,
    ] = dict()
    input_port_index: int
    input_name: str

    # Compact runtime inputs while retaining the original graphical port map.
    for input_port_index, input_name in incoming_signals:
        runtime_input_index: int = len(input_vars)
        input_vars.append(Var(name=input_name))
        input_names.append(input_name)
        input_index_by_connector[
            (DgsGraphicalConnectorKind.Input, input_port_index)
        ] = runtime_input_index
    else:
        pass

    if len(input_vars) == 0:
        operator_rhs: Expr = Const(0.0)
    else:
        operator_rhs = input_vars[0]
        following_input: Var
        for following_input in input_vars[1:]:
            if isinstance(node, BlkMul):
                operator_rhs = operator_rhs * following_input
            else:
                operator_rhs = dgs_divide(operator_rhs, following_input)
        else:
            pass

    output_names: List[str] = list()
    output_vars: List[Var] = list()
    output_port_index: int
    output_name: str
    for output_port_index, output_name in outgoing_signals:
        _ = output_port_index
        if output_name in output_names:
            pass
        else:
            output_names.append(output_name)
            output_vars.append(Var(name=output_name))
    else:
        pass
    if len(output_vars) == 0:
        fallback_output_name: str = _safe_name(
            node.loc_name if node.loc_name != '' else node.ID
        )
        output_names.append(fallback_output_name)
        output_vars.append(Var(name=fallback_output_name))
    else:
        pass

    algebraic_equations: List[Expr] = list()
    post_init_seed_eqs: Dict[Var, Expr] = dict()
    output_var: Var
    for output_var in output_vars:
        algebraic_equations.append(output_var - operator_rhs)
        post_init_seed_eqs[output_var] = operator_rhs
    else:
        pass

    operator_name: str
    if node.loc_name != '':
        operator_name = node.loc_name
    else:
        if isinstance(node, BlkMul):
            operator_name = 'Multiplication'
        else:
            operator_name = 'Division'
    block: Block = Block(
        algebraic_eqs=algebraic_equations,
        algebraic_vars=output_vars,
        in_vars=input_vars,
        out_vars=output_vars,
        post_init_seed_eqs=post_init_seed_eqs,
        name=operator_name,
    )
    return block, input_names, output_names, input_index_by_connector


def _build_graphical_switch_block(
        node: BlkSwt,
        circuit: DgsCircuit,
) -> Tuple[
    Block,
    List[str],
    List[str],
    Dict[Tuple[DgsGraphicalConnectorKind, int], int],
]:
    """Materialize a native PowerFactory two-input graphical switch.

    PowerFactory uses the top node as the control signal: values up to 0.5
    retain the default position and larger values change position. ``iNeg``
    inverts that zero/default position. The top connector is exported as the
    upper-limit connector category; a third ordinary port is accepted for
    backward-compatible DGS variants.

    :param node: Parsed native switch node.
    :param circuit: Parsed DGS circuit containing its signal rows.
    :return: Runtime block, input names, output names and exact input-port map.
    """
    data_inputs_by_port: Dict[int, str] = dict()
    control_inputs_by_port: Dict[Tuple[DgsGraphicalConnectorKind, int], str] = dict()
    outputs_by_port: Dict[int, str] = dict()
    signal: BlkSig
    for signal in circuit.blksigs:
        signal_name: str = _normalize_graph_signal_name(name=signal.loc_name)
        source_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(signal.iconfrom),
                endpoint_node=node,
                is_source_endpoint=True,
            )
        )
        target_kind: DgsGraphicalConnectorKind | None = (
            _parse_effective_graphical_connector_kind(
                connector_code=int(signal.iconto),
                endpoint_node=node,
                is_source_endpoint=False,
            )
        )
        if (
                _normalize_dgs_pointer_id(signal.pnodto) == node.ID
                and signal_name != ''
        ):
            if target_kind == DgsGraphicalConnectorKind.Input:
                data_inputs_by_port[int(signal.inodto)] = signal_name
            else:
                if target_kind in {
                    DgsGraphicalConnectorKind.UpperLimitInput,
                    DgsGraphicalConnectorKind.LowerLimitInput,
                }:
                    control_inputs_by_port[
                        (target_kind, int(signal.inodto))
                    ] = signal_name
                else:
                    pass
        else:
            pass
        if (
                _normalize_dgs_pointer_id(signal.pnodfrom) == node.ID
                and source_kind == DgsGraphicalConnectorKind.Output
                and signal_name != ''
        ):
            outputs_by_port[int(signal.inodfrom)] = signal_name
        else:
            pass
    else:
        pass

    ordered_data_inputs: List[Tuple[int, str]] = sorted(data_inputs_by_port.items())
    if len(control_inputs_by_port) > 0:
        ordered_control_inputs: List[
            Tuple[Tuple[DgsGraphicalConnectorKind, int], str]
        ] = sorted(control_inputs_by_port.items())
        control_connector: Tuple[DgsGraphicalConnectorKind, int] = (
            ordered_control_inputs[0][0]
        )
        control_name: str = ordered_control_inputs[0][1]
    else:
        if len(ordered_data_inputs) > 2:
            control_port: int
            control_port, control_name = ordered_data_inputs.pop()
            control_connector = (DgsGraphicalConnectorKind.Input, control_port)
        else:
            control_name = ''
            control_connector = (DgsGraphicalConnectorKind.UpperLimitInput, 0)

    input_vars: List[Var] = list()
    data_input_vars: List[Var] = list()
    input_names: List[str] = list()
    input_index_by_connector: Dict[
        Tuple[DgsGraphicalConnectorKind, int],
        int,
    ] = dict()
    data_port: int
    data_name: str
    for data_port, data_name in ordered_data_inputs[:2]:
        input_index_by_connector[
            (DgsGraphicalConnectorKind.Input, data_port)
        ] = len(input_vars)
        data_input_var: Var = Var(name=data_name)
        input_vars.append(data_input_var)
        data_input_vars.append(data_input_var)
        input_names.append(data_name)
    else:
        pass
    if control_name == '':
        control_expression: Expr = Const(0.0)
    else:
        input_index_by_connector[control_connector] = len(input_vars)
        control_var: Var = Var(name=control_name)
        input_vars.append(control_var)
        input_names.append(control_name)
        control_expression = control_var

    if len(data_input_vars) == 0:
        default_expression: Expr = Const(0.0)
        changed_expression: Expr = Const(0.0)
    else:
        default_expression = data_input_vars[0]
        if len(data_input_vars) >= 2:
            changed_expression = data_input_vars[1]
        else:
            changed_expression = default_expression
    if int(node.iNeg) == 0:
        pass
    else:
        swapped_expression: Expr = default_expression
        default_expression = changed_expression
        changed_expression = swapped_expression
    switched_position: Expr = heaviside(control_expression - Const(0.5))
    switch_rhs: Expr = (
        (Const(1.0) - switched_position) * default_expression
        + switched_position * changed_expression
    )

    ordered_outputs: List[Tuple[int, str]] = sorted(outputs_by_port.items())
    if len(ordered_outputs) == 0:
        output_name: str = _safe_name(
            node.loc_name if node.loc_name != '' else node.ID
        )
    else:
        output_name = ordered_outputs[0][1]
    output_var: Var = Var(name=output_name)
    block_name: str = node.loc_name if node.loc_name != '' else 'Switch'
    block: Block = Block(
        algebraic_eqs=list([output_var - switch_rhs]),
        algebraic_vars=list([output_var]),
        in_vars=input_vars,
        out_vars=list([output_var]),
        post_init_seed_eqs=dict([(output_var, switch_rhs)]),
        name=block_name,
    )
    return block, input_names, list([output_name]), input_index_by_connector


def extract_elmcomp_direct_instances(
    circuit: DgsCircuit,
    root_element: ElmComp,
) -> list[ElmCompInstanceEntry]:
    """
    Extract direct root instances from ElmComp pblk/pelm relations.

    :param circuit: Parsed DGS circuit.
    :param root_element: Root ElmComp.
    :return: Direct instance list.
    """
    element_by_id: dict[str, object] = _build_dgs_element_index(circuit)
    blkdef_by_id: dict[str, BlkDef] = _build_blkdef_index(circuit)

    entries: list[ElmCompInstanceEntry] = list()

    len_pblk: int = len(root_element.pblk)
    len_pelm: int = len(root_element.pelm)

    if len_pblk >= len_pelm:
        n_pairs: int = len_pblk
    else:
        n_pairs = len_pelm

    for idx in range(n_pairs):
        if idx < len_pblk:
            slot_id: str | None = root_element.pblk[idx]
        else:
            slot_id = None
        if idx < len_pelm:
            element_id: str | None = root_element.pelm[idx]
        else:
            element_id = None

        slot_name: str | None = None
        element_name: str | None = None
        element_kind: str | None = None
        type_id: str | None = None
        type_name: str | None = None
        parameter_values: DgsParameterValues = dict()
        slot_element: str | None = None
        slot_filter: str | None = None
        powerfactory_astable_integration: bool = False

        if slot_id is not None:
            slot_obj: object | None = element_by_id.get(slot_id, None)
            if isinstance(slot_obj, BlkSlot):
                slot_name = slot_obj.loc_name
                slot_element = slot_obj.element
                slot_filter = slot_obj.filtmod
            elif isinstance(slot_obj, DGSElement):
                slot_name = slot_obj.loc_name
                slot_element = None
                slot_filter = None
            else:
                slot_name = None
                slot_element = None
                slot_filter = None
        else:
            slot_name = None
            slot_element = None
            slot_filter = None

        if element_id is not None:
            element_obj: object | None = element_by_id.get(element_id, None)
            if isinstance(element_obj, ElmDsl):
                element_name = element_obj.loc_name
                element_kind = "ElmDsl"
                if element_obj.typ_id != "":
                    type_id = element_obj.typ_id
                else:
                    type_id = None
                parameter_values = element_obj.get_parameter_map()
                powerfactory_astable_integration = bool(
                    int(element_obj.iAstabint) == 1
                )
            elif isinstance(element_obj, ElmComp):
                element_name = element_obj.loc_name
                element_kind = "ElmComp"
                if element_obj.typ_id != "":
                    type_id = element_obj.typ_id
                else:
                    type_id = None
                parameter_values = dict()
            elif isinstance(element_obj, DGSElement):
                # Preserve physical or otherwise non-DSL pElm references as
                # provenance.  Their typ_id is an electrical type reference,
                # not a BlkDef, so it must not enter dynamic-block resolution.
                element_name = element_obj.loc_name
                element_kind = element_obj.element_type
                type_id = None
                parameter_values = dict()
            else:
                element_name = None
                element_kind = None
                type_id = None
                parameter_values = dict()
        else:
            element_name = None
            element_kind = None
            type_id = None
            parameter_values = dict()

        if type_id is not None:
            blkdef_obj: BlkDef | None = blkdef_by_id.get(type_id, None)
            if blkdef_obj is not None:
                type_name = blkdef_obj.loc_name
            else:
                type_name = None
        else:
            type_name = None

        if slot_name is None:
            if type_name is not None:
                slot_name = type_name
            else:
                slot_name = element_name
        else:
            pass

        entry = ElmCompInstanceEntry(
            slot_id=slot_id,
            slot_name=slot_name,
            element_id=element_id,
            element_name=element_name,
            element_kind=element_kind,
            type_id=type_id,
            type_name=type_name,
            parameter_values=parameter_values,
            slot_index=idx,
            slot_element=slot_element,
            slot_filter=slot_filter,
            powerfactory_astable_integration=(
                powerfactory_astable_integration
            ),
        )

        entries.append(entry)

    return entries

def select_block_instance_from_root(
    circuit: DgsCircuit,
    result: DgsRootBlockResult,
    slot_name: str,
    slot_dgs_id: str | None = None,
) -> DgsBlockInstanceSelection | None:
    """
    Resolve a parsed block from the explicit root ElmComp slot mapping.

    :param circuit: Parsed DGS circuit.
    :param result: Root block parsing result.
    :param slot_name: Slot name in the root ElmComp.
    :param slot_dgs_id: Optional exact BlkSlot FID.
    :return: Block selection or None.
    """
    entries: list[ElmCompInstanceEntry] = extract_elmcomp_direct_instances(circuit, result.root_element)

    selected_entry: ElmCompInstanceEntry | None = None

    for entry in entries:
        if selected_entry is None:
            if slot_dgs_id is None:
                if entry.slot_name == slot_name or entry.type_name == slot_name:
                    selected_entry = entry
                else:
                    pass
            else:
                if entry.slot_id == slot_dgs_id:
                    selected_entry = entry
                else:
                    pass
        else:
            pass

    if selected_entry is None:
        return None
    else:
        pass

    if selected_entry.type_id is None:
        return None
    else:
        pass

    parsed_block: ParsedDgsBlockDefinition | None = result.parsed_blocks.get(selected_entry.type_id, None)

    if parsed_block is None:
        return None
    else:
        selection = DgsBlockInstanceSelection(
            instance_entry=selected_entry,
            parsed_block=parsed_block,
        )
        return selection



def _reverse_dependency_graph(graph: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    reverse_graph: Dict[str, Set[str]] = dict()
    node_id: str
    for node_id in graph.keys():
        reverse_graph[node_id] = set()
    for src, dsts in graph.items():
        for dst in dsts:
            _append_to_string_set_map(reverse_graph, dst, src)
    return reverse_graph


def _closure_from_node(graph: Dict[str, Set[str]], start_node: str) -> Set[str]:
    visited: Set[str] = set()
    frontier: List[str] = [start_node]

    while frontier:
        node = frontier.pop()
        if node in visited:
            pass
        else:
            visited.add(node)
            for nxt in graph.get(node, set()):
                if nxt not in visited:
                    frontier.append(nxt)
                else:
                    pass

    return visited


def _select_named_block(parsed_blocks: Dict[str, ParsedDgsBlockDefinition], block_name: str, block_id: str | None = None) -> Tuple[str, ParsedDgsBlockDefinition]:
    if block_id is not None:
        selected = parsed_blocks.get(block_id)
        if selected is None:
            raise ValueError(f"Block id '{block_id}' not found")
        if selected.blkdef.loc_name != block_name:
            raise ValueError(f"Block id '{block_id}' does not match block name '{block_name}'")
        return block_id, selected

    candidates = [(bid, parsed) for bid, parsed in parsed_blocks.items() if parsed.blkdef.loc_name == block_name]
    if not candidates:
        raise ValueError(f"Block name '{block_name}' not found")

    best_candidate: Tuple[str, ParsedDgsBlockDefinition] | None = None
    best_score: Tuple[int, int, int, int, int] | None = None
    candidate: Tuple[str, ParsedDgsBlockDefinition]
    for candidate in candidates:
        score = _score_root_candidate(candidate[1])
        if best_score is None or score > best_score:
            best_candidate = candidate
            best_score = score
        else:
            pass

    if best_candidate is None:
        raise ValueError(f"Block name '{block_name}' not found")
    else:
        return best_candidate


def extract_named_block_subgraph(
    result: DgsRootBlockResult,
    block_name: str,
    block_id: str | None = None,
    mode: BlockScopeMode = BlockScopeMode.InternalOnly) -> DgsBlockSubgraphResult:

    selected_id, selected_block = _select_named_block(result.parsed_blocks, block_name, block_id)
    reverse_graph: Dict[str, Set[str]] = _reverse_dependency_graph(result.dependency_graph)

    node_ids: Set[str] = set()
    node_ids.add(selected_id)

    upstream: Dict[str, Set[str]] = dict()
    downstream: Dict[str, Set[str]] = dict()

    if mode == BlockScopeMode.DownstreamOnly:
        downstream_nodes: Set[str] = _closure_from_node(result.dependency_graph, selected_id)
        node_ids |= downstream_nodes
    elif mode == BlockScopeMode.UpstreamOnly:
        upstream_nodes: Set[str] = _closure_from_node(reverse_graph, selected_id)
        node_ids |= upstream_nodes
    elif mode == BlockScopeMode.FullDependency:
        upstream_nodes = _closure_from_node(reverse_graph, selected_id)
        downstream_nodes = _closure_from_node(result.dependency_graph, selected_id)
        node_ids |= upstream_nodes
        node_ids |= downstream_nodes
    else:
        pass

    sub_children: List[Block] = list()
    shared_signals: Dict[str, Var] = dict()
    ordered_node_ids: List[tuple[str, str]] = list()
    node_id: str
    for node_id in node_ids:
        ordered_node_ids.append((result.parsed_blocks[node_id].blkdef.loc_name, node_id))
    ordered_node_ids.sort()

    _node_label: str
    for _node_label, node_id in ordered_node_ids:
        sub_children.append(_build_block_from_parsed(result.parsed_blocks[node_id], shared_signals))

    for node_id in node_ids:
        if mode == BlockScopeMode.DownstreamOnly:
            downstream[node_id] = _build_filtered_neighbor_set(result.dependency_graph, node_id, node_ids)
        elif mode == BlockScopeMode.UpstreamOnly:
            upstream[node_id] = _build_reverse_neighbor_subset(reverse_graph, node_id, node_ids)
        elif mode == BlockScopeMode.FullDependency:
            upstream[node_id] = _build_reverse_neighbor_subset(reverse_graph, node_id, node_ids)
            downstream[node_id] = _build_filtered_neighbor_set(result.dependency_graph, node_id, node_ids)
        else:
            pass

    selected_runtime_block = _build_block_from_parsed(selected_block, shared_signals)

    if mode == BlockScopeMode.InternalOnly:
        view_block = selected_runtime_block
        view_block.name = selected_block.blkdef.loc_name
    else:
        view_block_name = f"{selected_block.blkdef.loc_name}_{str(mode)}"
        view_block = Block(
            name=view_block_name,
            children=sub_children,
            in_vars=selected_runtime_block.in_vars,
            out_vars=selected_runtime_block.out_vars,
            algebraic_vars=selected_runtime_block.algebraic_vars,
        )

    subgraph = _filter_graph_edges_to_node_ids(result.dependency_graph, node_ids)

    return DgsBlockSubgraphResult(
        selected_block=selected_block,
        view_block=view_block,
        node_ids=node_ids,
        dependency_graph=subgraph,
        upstream=upstream,
        downstream=downstream,
    )

def extract_named_block_internal_only(
    result: DgsRootBlockResult,
    block_name: str,
    block_id: str | None = None,
) -> DgsBlockSubgraphResult:
    """
    Extract only the selected block without any dependency closure.

    :param result: Root block parsing result.
    :param block_name: Target block name.
    :param block_id: Optional exact block identifier.
    :return: Minimal block subgraph result.
    """
    return extract_named_block_subgraph(
        result=result,
        block_name=block_name,
        block_id=block_id,
        mode=BlockScopeMode.InternalOnly,
    )

def extract_root_slot_block_internal_only(
    dgs_path: str,
    slot_name: str,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
) -> DgsBlockSubgraphResult | None:
    """
    Extract the block associated to a root ElmComp slot and keep only that block.

    :param dgs_path: Source DGS path.
    :param slot_name: Root slot name.
    :param root_name: Root ElmComp name.
    :param root_typ_id: Optional root type identifier.
    :return: Internal-only block subgraph or None.
    """
    circuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)

    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    selection: DgsBlockInstanceSelection | None = select_block_instance_from_root(
        circuit=circuit,
        result=result,
        slot_name=slot_name,
    )

    if selection is None:
        return None
    else:
        return extract_named_block_internal_only(
            result=result,
            block_name=selection.parsed_block.blkdef.loc_name,
            block_id=selection.parsed_block.blkdef.ID,
        )

def extract_root_slot_block_internal_signal_tree(
    dgs_path: str,
    slot_name: str,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
) -> DgsBlockSubgraphResult | None:
    """
    Extract an internal hierarchy approximation for a selected root slot using
    signal-name matching only.

    :param dgs_path: Source DGS path.
    :param slot_name: Root slot name or type name fallback.
    :param root_name: Root ElmComp name.
    :param root_typ_id: Optional root type identifier.
    :return: Subgraph result or None.
    """
    circuit = DgsCircuit()
    circuit.parse_dgs(dgs_path)

    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    selection: DgsBlockInstanceSelection | None = select_block_instance_from_root(
        circuit=circuit,
        result=result,
        slot_name=slot_name,
    )

    if selection is None:
        return None
    else:
        pass

    candidates: Dict[str, ParsedDgsBlockDefinition] = _collect_internal_candidate_blocks(
        selected_block=selection.parsed_block,
        parsed_blocks=result.parsed_blocks,
    )

    filtered: Dict[str, ParsedDgsBlockDefinition] = _filter_internal_candidates(
        selected_block=selection.parsed_block,
        candidates=candidates,
        min_score=2,
    )

    node_ids: Set[str] = set()
    node_ids.add(selection.parsed_block.blkdef.ID)
    node_ids |= set(filtered.keys())

    reverse_graph: Dict[str, Set[str]] = _reverse_dependency_graph(result.dependency_graph)
    upstream: Dict[str, Set[str]] = dict()
    downstream: Dict[str, Set[str]] = dict()

    for node_id in node_ids:
        upstream[node_id] = _build_reverse_neighbor_subset(reverse_graph, node_id, node_ids)
        downstream[node_id] = _build_filtered_neighbor_set(result.dependency_graph, node_id, node_ids)

    shared_signals: Dict[str, Var] = dict()
    sub_children: List[Block] = list()
    element_by_id = _build_dgs_element_index(circuit)
    selected_element_obj = element_by_id.get(selection.instance_entry.element_id or "", None)
    nested_parameter_values_by_type_id: Dict[str, DgsParameterValues] = dict()
    if isinstance(selected_element_obj, ElmComp):
        nested_parameter_values_by_type_id = _parameter_values_by_type_id(extract_elmcomp_direct_instances(circuit, selected_element_obj))

    ordered_ids: List[str] = list(node_ids)
    ordered_ids.sort()

    for node_id in ordered_ids:
        parsed = result.parsed_blocks[node_id]
        parameter_values = selection.instance_entry.parameter_values if node_id == selection.parsed_block.blkdef.ID else nested_parameter_values_by_type_id.get(parsed.blkdef.ID, None)
        sub_children.append(_build_block_from_parsed(parsed, shared_signals, parameter_values=parameter_values))

    selected_runtime_block: Block = _build_block_from_parsed(
        selection.parsed_block,
        shared_signals,
        parameter_values=selection.instance_entry.parameter_values,
    )

    view_block = Block(
        name=f"{selection.parsed_block.blkdef.loc_name}_InternalSignalTree",
        children=sub_children,
        in_vars=selected_runtime_block.in_vars,
        out_vars=selected_runtime_block.out_vars,
        algebraic_vars=selected_runtime_block.algebraic_vars,
    )

    local_graph: Dict[str, Set[str]] = _filter_graph_edges_to_node_ids(result.dependency_graph, node_ids)

    return DgsBlockSubgraphResult(
        selected_block=selection.parsed_block,
        node_ids=node_ids,
        dependency_graph=local_graph,
        upstream=upstream,
        downstream=downstream,
        view_block=view_block,
    )


def extract_root_slot_block_graphical_tree(
    dgs_path: str,
    slot_name: str,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
) -> DgsGraphicTreeResult | None:
    """
    Extract the exact graphical internal tree of a root slot using BlkRef/BlkSig/BlkSum structures.

    :param dgs_path: Source DGS path.
    :param slot_name: Root slot name or type-name fallback.
    :param root_name: Root ElmComp name.
    :param root_typ_id: Optional root type identifier.
    :return: Graphical tree result or None.
    """
    circuit: DgsCircuit = DgsCircuit()
    result: DgsRootBlockResult

    circuit.parse_dgs(dgs_path)
    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    return extract_root_slot_block_graphical_tree_from_context(circuit=circuit, result=result, slot_name=slot_name)


def extract_root_slot_block_graphical_tree_from_context(
        circuit: DgsCircuit,
        result: DgsRootBlockResult,
        slot_name: str,
        slot_dgs_id: str | None = None,
        graphical_context: DgsGraphicalParseContext | None = None,
) -> DgsGraphicTreeResult | None:
    """
    Extract the exact graphical internal tree of one root slot using one prepared context.

    :param circuit: Parsed DGS circuit reused across many slot lookups.
    :param result: Parsed root block result reused across many slot lookups.
    :param slot_name: Root slot name or type-name fallback.
    :param slot_dgs_id: Optional exact BlkSlot FID.
    :param graphical_context: Optional shared graphical indexes.
    :return: Graphical tree result or None.
    """
    selection: DgsBlockInstanceSelection | None = select_block_instance_from_root(
        circuit=circuit,
        result=result,
        slot_name=slot_name,
        slot_dgs_id=slot_dgs_id,
    )

    if selection is None or selection.instance_entry.type_id is None:
        return None
    else:
        pass

    if graphical_context is None:
        active_graphical_context: DgsGraphicalParseContext = (
            build_dgs_graphical_parse_context(circuit=circuit)
        )
    else:
        active_graphical_context = graphical_context
    adjacency: Dict[str, Set[str]] = active_graphical_context.adjacency
    root_node_id = str(selection.instance_entry.type_id)
    explicit_component = _graphic_connected_component(adjacency, root_node_id)

    node_by_id: Dict[str, object] = active_graphical_context.node_by_id
    node_signals: Dict[str, Set[str]] = active_graphical_context.node_signals
    # BlkSig endpoints are the authoritative graphical ownership relation.
    # Signal labels such as ``K``, ``yi`` and ``yo`` are intentionally reused
    # by unrelated diagrams, so using them to pull disconnected nodes into a
    # component contaminates one controller with primitives from another.
    node_ids: Set[str] = explicit_component
    node_labels: dict[str, str] = dict()
    node_kinds: dict[str, str] = dict()
    child_blocks: list[Block] = list()
    child_blocks_by_node: dict[str, Block] = dict()
    child_input_specs: dict[str, List[str]] = dict()
    child_input_index_by_connector: Dict[
        str,
        Dict[Tuple[DgsGraphicalConnectorKind, int], int],
    ] = dict()
    child_output_specs: dict[str, List[str]] = dict()
    child_node_ids: list[str] = list()

    alias_map = _build_graph_signal_alias_map(node_ids, node_by_id, node_signals)
    local_adj = _build_augmented_graphical_adjacency(node_ids, adjacency, node_by_id, node_signals, alias_map)
    element_by_id: Dict[str, object] = active_graphical_context.element_by_id
    selected_element_obj = element_by_id.get(selection.instance_entry.element_id or "", None)
    nested_entries_by_label: Dict[str, ElmCompInstanceEntry] = dict()
    nested_entries_by_type_name: Dict[str, ElmCompInstanceEntry] = dict()
    nested_parameter_values_by_type_id: Dict[str, DgsParameterValues] = dict()
    if isinstance(selected_element_obj, ElmComp):
        nested_entries = extract_elmcomp_direct_instances(circuit, selected_element_obj)
        nested_entries_by_label = _build_instance_entry_lookup_by_slot_name(nested_entries)
        nested_entries_by_type_name = _build_instance_entry_lookup_by_type_name(nested_entries)
        nested_parameter_values_by_type_id = _parameter_values_by_type_id(nested_entries)

    ordered_node_ids: list[tuple[str, str]] = list()
    for node_id in node_ids:
        ordered_node_ids.append((_graphic_node_label(node_by_id.get(node_id, node_id)), node_id))
    ordered_node_ids.sort()

    # Materialize the parent first because each graphical BlkRef can bind its
    # private states/internals positionally to this exact DSL occurrence.
    graphical_required_init_names: Set[str] = set(
        selection.parsed_block.init_rhs.keys()
    )
    selected_runtime_block: Block = _build_block_from_parsed(
        parsed=selection.parsed_block,
        shared_signals=dict(),
        parameter_values=selection.instance_entry.parameter_values,
        additional_required_init_signal_names=graphical_required_init_names,
    )

    _node_label: str
    for _node_label, node_id in ordered_node_ids:
        node_obj = node_by_id.get(node_id)
        if node_obj is None:
            pass
        else:
            node_labels[node_id] = _graphic_node_label(node_obj)
            node_kinds[node_id] = _graphic_node_kind(node_obj)

            if node_id == root_node_id:
                pass
            elif isinstance(node_obj, BlkRef):
                parsed = result.parsed_blocks.get(node_obj.typ_id, None)
                if parsed is None:
                    pass
                else:
                    instance_entry = nested_entries_by_label.get(node_obj.cdisName, None)
                    if instance_entry is None:
                        instance_entry = nested_entries_by_type_name.get(parsed.blkdef.loc_name, None)
                    else:
                        pass

                    parameter_values = nested_parameter_values_by_type_id.get(parsed.blkdef.ID, None)
                    if instance_entry is not None and len(instance_entry.parameter_values) > 0:
                        parameter_values = instance_entry.parameter_values
                    else:
                        pass

                    # The graphical occurrence owns the final primitive
                    # binding. Resolve literals and parent-parameter aliases
                    # after any nested-instance fallback so repeated blocks of
                    # one type retain their distinct K/T/limit values.
                    parameter_values = _resolve_graphical_blkref_parameter_values(
                        reference=node_obj,
                        definition=parsed.blkdef,
                        parent_parameter_values=(
                            selection.instance_entry.parameter_values
                        ),
                        fallback_parameter_values=parameter_values,
                    )

                    blk = _build_block_from_parsed(
                        parsed,
                        dict(),
                        parameter_values=parameter_values,
                    )
                    # Protected WECC VDL primitives expose their exact standard
                    # role through the graphical parameter alias even when
                    # PowerFactory omits the built-in table from ``oarrmat``.
                    # Restore that public standard before cable substitution so
                    # the produced ``yo`` signal participates in graph wiring.
                    _restore_open_standard_vdl_lookup(
                        block=blk,
                        parsed=parsed,
                        reference=node_obj,
                    )
                    _connect_graphical_blkref_owned_aliases(
                        reference=node_obj,
                        definition=parsed.blkdef,
                        parent_block=selected_runtime_block,
                        child_block=blk,
                    )
                    blk.name = _graphic_node_label(node_obj)
                    child_blocks.append(blk)
                    child_blocks_by_node[node_id] = blk
                    child_input_specs[node_id] = (
                        _build_blkdef_runtime_input_names(blkdef=parsed.blkdef)
                    )
                    child_input_index_by_connector[node_id] = (
                        _build_blkdef_runtime_input_index_by_connector(
                            blkdef=parsed.blkdef,
                        )
                    )
                    child_output_specs[node_id] = list(parsed.blkdef.outputs)
                    child_node_ids.append(node_id)
            elif isinstance(node_obj, BlkSum):
                blk, input_specs, output_specs = _build_sum_block_from_graphic_node(node_obj, circuit)
                child_blocks.append(blk)
                child_blocks_by_node[node_id] = blk
                child_input_specs[node_id] = input_specs
                # Compact the native four-slot surface while retaining exact
                # raw-port identity across disabled summation inputs.
                child_input_index_by_connector[node_id] = (
                    _build_sum_runtime_input_index_by_connector(
                        blk_sum=node_obj,
                        circuit=circuit,
                    )
                )
                child_output_specs[node_id] = output_specs
                child_node_ids.append(node_id)
            elif isinstance(node_obj, (BlkMul, BlkDiv)):
                arithmetic_input_index_by_connector: Dict[
                    Tuple[DgsGraphicalConnectorKind, int],
                    int,
                ]
                (
                    blk,
                    input_specs,
                    output_specs,
                    arithmetic_input_index_by_connector,
                ) = _build_graphical_arithmetic_block(
                    node=node_obj,
                    circuit=circuit,
                )
                child_blocks.append(blk)
                child_blocks_by_node[node_id] = blk
                child_input_specs[node_id] = input_specs
                child_input_index_by_connector[node_id] = (
                    arithmetic_input_index_by_connector
                )
                child_output_specs[node_id] = output_specs
                child_node_ids.append(node_id)
            elif isinstance(node_obj, BlkSwt):
                switch_input_index_by_connector: Dict[
                    Tuple[DgsGraphicalConnectorKind, int],
                    int,
                ]
                (
                    blk,
                    input_specs,
                    output_specs,
                    switch_input_index_by_connector,
                ) = _build_graphical_switch_block(
                    node=node_obj,
                    circuit=circuit,
                )
                child_blocks.append(blk)
                child_blocks_by_node[node_id] = blk
                child_input_specs[node_id] = input_specs
                child_input_index_by_connector[node_id] = (
                    switch_input_index_by_connector
                )
                child_output_specs[node_id] = output_specs
                child_node_ids.append(node_id)
            else:
                pass

    connections, resolved_outputs = _resolve_graphic_block_connections(
        selected_block=selection.parsed_block,
        child_node_ids=child_node_ids,
        child_blocks=child_blocks_by_node,
        child_input_specs=child_input_specs,
        child_input_index_by_connector=child_input_index_by_connector,
        child_output_specs=child_output_specs,
        graphical_signals=circuit.blksigs,
        adjacency=local_adj,
        node_by_id=node_by_id,
        node_signals=node_signals,
        alias_map=alias_map,
        root_runtime_block=selected_runtime_block,
    )

    # Root-output cables select the child variable that actually produces each
    # exported signal. Apply the same identity to parent initialization and
    # procedural expressions before the graphical shell is assembled; merely
    # replacing ``out_vars`` would leave inc(EFD)=... attached to a dead UID.
    original_root_outputs: List[Var] = list(selected_runtime_block.out_vars)
    resolved_output_count_by_uid: Dict[int, int] = dict()
    counted_resolved_output: Var
    for counted_resolved_output in resolved_outputs:
        resolved_output_count_by_uid[counted_resolved_output.uid] = (
            resolved_output_count_by_uid.get(
                counted_resolved_output.uid,
                0,
            )
            + 1
        )
    else:
        pass
    root_output_index: int
    for root_output_index in range(len(original_root_outputs)):
        if root_output_index >= len(resolved_outputs):
            pass
        else:
            original_root_output: Var = original_root_outputs[root_output_index]
            resolved_root_output: Var = resolved_outputs[root_output_index]
            if original_root_output.uid == resolved_root_output.uid:
                pass
            else:
                selected_runtime_block.update_model(
                    original_root_output,
                    resolved_root_output,
                )
                if (
                        resolved_output_count_by_uid.get(
                            resolved_root_output.uid,
                            0,
                        ) == 1
                ):
                    # The public macro pin is the human-facing name of this
                    # unique produced value. Keep the producer UID/equation and
                    # promote only its label so persisted Python exposes
                    # ``idref``/``EFD`` instead of a private ``yo`` helper.
                    resolved_root_output.name = original_root_output.name
                else:
                    # One internal value can feed multiple public aliases. A
                    # single Var cannot hold several names, so retain its
                    # private label rather than selecting an arbitrary alias.
                    pass
    else:
        pass

    child_lookup: dict[str, Block] = dict()
    node_id = ""
    for node_id in child_node_ids:
        child_lookup[node_id] = child_blocks_by_node[node_id]
    root_in_lookup = _build_name_to_var_map(list(selected_runtime_block.in_vars))
    for instruction in connections:
        consumer_block = child_lookup[instruction.consumer_node_id]
        if instruction.consumer_input_index is None or instruction.consumer_input_index >= len(consumer_block.in_vars):
            pass
        else:
            consumer_var = consumer_block.in_vars[instruction.consumer_input_index]

            if instruction.source_kind == "block_output" and instruction.source_node_id is not None and instruction.source_output_index is not None:
                producer_block = child_lookup[instruction.source_node_id]
                if instruction.source_output_index < len(producer_block.out_vars):
                    consumer_block.connect([consumer_var], [producer_block.out_vars[instruction.source_output_index]])
                else:
                    pass
            elif instruction.source_kind == "root_input" and instruction.source_root_name is not None:
                root_var = root_in_lookup.get(instruction.source_root_name, None)
                if root_var is not None:
                    consumer_block.connect([consumer_var], [root_var])
                else:
                    pass
            else:
                pass

    # Reconnect parent ``inc()`` dependencies after the child cables have
    # acquired their final identities. This also installs zero only for exact
    # graphical pins whose DGS producer endpoint is empty.
    _connect_graphical_parent_internal_signals(
        selected_block=selection.parsed_block,
        parent_block=selected_runtime_block,
        child_blocks=child_lookup,
        child_input_index_by_connector=child_input_index_by_connector,
        graphical_signals=circuit.blksigs,
        connections=connections,
        routed_source_signal_names=(
            _collect_routed_graphical_source_signal_names(
                node_ids=node_ids,
                node_by_id=node_by_id,
                node_signals=node_signals,
            )
        ),
        node_by_id=node_by_id,
    )

    if len(child_blocks) == 0:
        # A formula-based BlkDef can share numeric FIDs with graphical nodes or
        # appear as a one-node graphical component.  In that case the exact
        # tree has no children and the semantic equation block itself is the
        # complete view; replacing it with an empty shell would silently erase
        # the imported dynamics.
        view_block: Block = selected_runtime_block
    else:
        raw_parent_explicit_uids: object | None = (
            selected_runtime_block.__dict__.get(
                "dgs_explicit_initialization_uids",
                None,
            )
        )
        if isinstance(raw_parent_explicit_uids, set):
            parent_explicit_uids: Set[int] = set()
            raw_explicit_uid: object
            for raw_explicit_uid in raw_parent_explicit_uids:
                if isinstance(raw_explicit_uid, int):
                    parent_explicit_uids.add(raw_explicit_uid)
                else:
                    pass
            else:
                pass
        else:
            parent_explicit_uids = set()
        graphical_parent_init_eqs: Dict[Var, Expr] = dict()
        parent_init_var: Var
        parent_init_expr: Expr
        for parent_init_var, parent_init_expr in selected_runtime_block.init_eqs.items():
            if parent_init_var.uid in parent_explicit_uids:
                graphical_parent_init_eqs[parent_init_var] = parent_init_expr
            else:
                # Directed runtime assignments already live in the graphical
                # child tree. Their synthesized startup seeds must not retain
                # dead parent-shell variables alongside the real graph.
                pass
        else:
            pass
        # The graphical children are authoritative for runtime state and
        # algebraic equations, but the enclosing DSL still owns its inc()/mode
        # contract. Preserve that boundary metadata: dropping it disconnects
        # sample-and-hold internals such as REEC_D Vref even though sIntern has
        # correctly unified the child and parent variable identities.
        view_block = Block(
            name=selection.parsed_block.blkdef.loc_name,
            children=child_blocks,
            in_vars=selected_runtime_block.in_vars,
            out_vars=resolved_outputs,
            parameters=selected_runtime_block.parameters,
            init_values=selected_runtime_block.init_values,
            init_eqs=graphical_parent_init_eqs,
            diff_init_eqs=selected_runtime_block.diff_init_eqs,
            discrete_eqs=selected_runtime_block.discrete_eqs,
            post_init_seed_eqs=selected_runtime_block.post_init_seed_eqs,
            event_dict=selected_runtime_block.event_dict,
            mode_dict=selected_runtime_block.mode_dict,
            boolean_guards=selected_runtime_block.boolean_guards,
            procedural_logic=selected_runtime_block.procedural_logic,
            startup_initializer=selected_runtime_block.startup_initializer,
            external_mapping=selected_runtime_block.external_mapping,
            api_obj_mapping=selected_runtime_block.api_obj_mapping,
        )
        view_block.__dict__["dgs_explicit_initialization_uids"] = set(
            selected_runtime_block.__dict__.get(
                "dgs_explicit_initialization_uids",
                set(),
            )
        )
        view_block.__dict__["runtime_post_update_helper_names"] = list(
            selected_runtime_block.__dict__.get(
                "runtime_post_update_helper_names",
                list(),
            )
        )
        view_block.__dict__["runtime_post_update_helper_var_uids"] = list(
            selected_runtime_block.__dict__.get(
                "runtime_post_update_helper_var_uids",
                list(),
            )
        )
        view_block.__dict__["dgs_resolved_graphical_internal_names"] = list(
            selected_runtime_block.__dict__.get(
                "dgs_resolved_graphical_internal_names",
                list(),
            )
        )
        view_block.__dict__["dgs_disconnected_graphical_input_names"] = list(
            selected_runtime_block.__dict__.get(
                "dgs_disconnected_graphical_input_names",
                list(),
            )
        )
        view_block.__dict__["dgs_unresolved_graphical_input_names"] = list(
            selected_runtime_block.__dict__.get(
                "dgs_unresolved_graphical_input_names",
                list(),
            )
        )
        raw_discrete_actions: object | None = selected_runtime_block.__dict__.get(
            "dgs_discrete_event_actions",
            None,
        )
        if isinstance(raw_discrete_actions, list):
            view_block.__dict__["dgs_discrete_event_actions"] = list(
                raw_discrete_actions
            )
        else:
            pass

    return DgsGraphicTreeResult(
        selected_block=selection.parsed_block,
        view_block=view_block,
        node_ids=node_ids,
        adjacency=local_adj,
        node_labels=node_labels,
        node_kinds=node_kinds,
        child_node_ids=child_node_ids,
        connections=connections,
    )

def export_named_block_subgraph_to_python(
    dgs_path: str,
    output_path: str,
    block_name: str,
    *,
    block_id: str | None = None,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
    mode: BlockScopeMode = BlockScopeMode.InternalOnly,
) -> Path:
    """
    Export a selected DGS block subgraph as a standalone Python module.

    :param dgs_path: Source DGS file.
    :param output_path: Destination `.py` file.
    :param block_name: Target block name inside the parsed DGS library.
    :param block_id: Optional exact DGS block identifier.
    :param root_name: Root ElmComp display name.
    :param root_typ_id: Optional exact root typ_id.
    :return: Path to the generated Python module.
    """
    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    subgraph = extract_named_block_subgraph(
        result,
        block_name=block_name,
        block_id=block_id,
        mode=mode,
    )

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    module_text = _emit_template_style_module(result, subgraph, dgs_path)

    out_path.write_text(module_text, encoding="utf-8")
    return out_path


def export_named_block_subgraph_tree_to_python(
    dgs_path: str,
    output_path: str,
    block_name: str,
    *,
    block_id: str | None = None,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
    mode: BlockScopeMode = BlockScopeMode.InternalOnly,
) -> Path:
    """
    Export a selected DGS block subgraph as a serialized block-tree Python module.
    """
    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    subgraph = extract_named_block_subgraph(
        result,
        block_name=block_name,
        block_id=block_id,
        mode=mode,
    )

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    module_text = _emit_tree_style_module(result, subgraph, dgs_path)
    out_path.write_text(module_text, encoding="utf-8")
    return out_path

def export_root_slot_block_internal_signal_tree_to_python(
    dgs_path: str,
    output_path: str,
    slot_name: str,
    *,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
) -> Path:
    """
    Export a root-slot internal signal-tree approximation as a serialized block-tree module.

    :param dgs_path: Source DGS file.
    :param output_path: Destination `.py` file.
    :param slot_name: Root slot name or type-name fallback.
    :param root_name: Root ElmComp display name.
    :param root_typ_id: Optional exact root typ_id.
    :return: Path to the generated Python module.
    """
    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    subgraph = extract_root_slot_block_internal_signal_tree(
        dgs_path=dgs_path,
        slot_name=slot_name,
        root_name=root_name,
        root_typ_id=root_typ_id,
    )

    if subgraph is None:
        raise ValueError(f"Could not resolve internal signal tree for slot '{slot_name}'")
    else:
        pass

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    module_text = _emit_tree_style_module(result, subgraph, dgs_path)
    out_path.write_text(module_text, encoding="utf-8")
    return out_path


def export_root_slot_block_graphical_tree_to_python(
    dgs_path: str,
    output_path: str,
    slot_name: str,
    *,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
) -> Path:
    """
    Export the exact graphical internal tree of a root slot as a serialized block-tree module.

    :param dgs_path: Source DGS file.
    :param output_path: Destination `.py` file.
    :param slot_name: Root slot name.
    :param root_name: Root ElmComp display name.
    :param root_typ_id: Optional root type identifier.
    :return: Path to the generated Python module.
    """
    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    graph_tree = extract_root_slot_block_graphical_tree(
        dgs_path=dgs_path,
        slot_name=slot_name,
        root_name=root_name,
        root_typ_id=root_typ_id,
    )

    if graph_tree is None:
        raise ValueError(f"Could not resolve graphical tree for slot '{slot_name}'")

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    emitter = DgsGraphicalTreeModuleEmitter(result=result, graph_tree=graph_tree, dgs_path=dgs_path)
    module_text = emitter.render()

    out_path.write_text(module_text, encoding="utf-8")
    return out_path


def export_root_slot_block_graphical_template_to_python(
    dgs_path: str,
    output_path: str,
    slot_name: str,
    *,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
) -> Path:
    """
    Export the exact graphical tree of a root slot as a standalone EMT template module.

    :param dgs_path: Source DGS file.
    :param output_path: Destination `.py` file.
    :param slot_name: Root slot name.
    :param root_name: Root ElmComp display name.
    :param root_typ_id: Optional exact root typ_id.
    :return: Path to the generated Python module.
    """
    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    graph_tree = extract_root_slot_block_graphical_tree(
        dgs_path=dgs_path,
        slot_name=slot_name,
        root_name=root_name,
        root_typ_id=root_typ_id,
    )
    if graph_tree is None:
        raise ValueError(f"Could not extract graphical tree for slot '{slot_name}'")

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    module_text = _emit_template_style_module(result, graph_tree, dgs_path)

    out_path.write_text(module_text, encoding="utf-8")
    return out_path


def export_root_elmcomp_template_to_python(
    dgs_path: str,
    output_path: str,
    root_name: str,
    *,
    root_typ_id: str | None = None,
) -> Path:
    """
    Export one root ElmComp as a standalone EMT template module.

    :param dgs_path: Source DGS file.
    :param output_path: Destination `.py` file.
    :param root_name: Root ElmComp display name.
    :param root_typ_id: Optional exact root typ_id.
    :return: Path to the generated Python module.
    """
    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)

    # Persist the complete parsed root hierarchy instead of only the direct ElmDsl
    # slots so reopening the imported template matches the in-memory root import.
    root_subgraph = DgsBlockSubgraphResult(
        selected_block=result.root_blkdef,
        view_block=result.root_block,
        node_ids=set(result.dependency_graph.keys()),
        dependency_graph=result.dependency_graph,
        upstream=dict(),
        downstream=dict(),
    )

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    module_text = _emit_template_style_module(
        result,
        root_subgraph,
        dgs_path,
        template_name=result.root_element.loc_name,
    )
    out_path.write_text(module_text, encoding="utf-8")
    return out_path

def export_root_slot_block_internal_signal_template_to_python(
    dgs_path: str,
    output_path: str,
    slot_name: str,
    *,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
) -> Path:
    """
    Export a root-slot internal signal-tree approximation as an EMT template module.

    :param dgs_path: Source DGS file.
    :param output_path: Destination `.py` file.
    :param slot_name: Root slot name or type-name fallback.
    :param root_name: Root ElmComp display name.
    :param root_typ_id: Optional exact root typ_id.
    :return: Path to the generated Python module.
    """
    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    subgraph = extract_root_slot_block_internal_signal_tree(
        dgs_path=dgs_path,
        slot_name=slot_name,
        root_name=root_name,
        root_typ_id=root_typ_id,
    )

    if subgraph is None:
        raise ValueError(f"Could not resolve internal signal tree for slot '{slot_name}'")
    else:
        pass

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    module_text = _emit_template_style_module(result, subgraph, dgs_path)
    out_path.write_text(module_text, encoding="utf-8")
    return out_path

# D12 devel_dynamics compatibility surface preserved during integration.
def _rescue_graphic_internal_nodes(
    selected_block: ParsedDgsBlockDefinition,
    node_by_id: dict[str, object],
    node_signals: dict[str, set[str]],
    explicit_component: set[str],
) -> set[str]:
    """
    Rescue disconnected graphical nodes whose signal labels belong to the selected composite universe.

    :param selected_block: Selected parsed block.
    :param node_by_id: Graphic-node index.
    :param node_signals: Signal labels per node.
    :param explicit_component: Nodes already obtained from explicit BlkSig connectivity.
    :return: Additional rescued node ids.
    """
    universe = _selected_block_signal_universe(selected_block)
    rescued: set[str] = set()

    for node_id, node in node_by_id.items():
        if node_id in explicit_component:
            pass
        elif not isinstance(node, (BlkRef, BlkFrom, BlkGoto, BlkSum)):
            pass
        else:
            sigs = node_signals.get(node_id, set())
            if sigs & universe:
                rescued.add(node_id)
            else:
                pass

    return rescued

def _selected_block_signal_universe(parsed_block: ParsedDgsBlockDefinition) -> set[str]:
    """
    Return the relevant signal universe of a selected composite block.

    :param parsed_block: Parsed composite block definition.
    :return: Signal-name universe.
    """
    return set(parsed_block.blkdef.inputs) | set(parsed_block.blkdef.outputs) | set(parsed_block.blkdef.internals) | set(parsed_block.blkdef.states)

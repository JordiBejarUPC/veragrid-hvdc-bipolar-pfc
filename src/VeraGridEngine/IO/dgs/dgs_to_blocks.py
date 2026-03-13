# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import ast
import math
import pprint
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import BlkDef, ElmComp
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Comparison, Const, Expr, Func2, Var, abs, cos, exp, hard_sat, log, max, min, sin, sqrt


def _safe_name(name: str) -> str:
    cleaned: str = re.sub(r"[^0-9a-zA-Z_]", "_", name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if cleaned == "":
        cleaned = "unnamed"
    if cleaned[0].isdigit():
        cleaned = f"v_{cleaned}"
    return cleaned


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


def _split_equation_statements(raw_equations: Iterable[str]) -> List[str]:
    statements: List[str] = list()

    for blob in raw_equations:
        for part in blob.split(';'):
            stmt = part.split('!', 1)[0].strip().strip('"')
            if stmt == "" or stmt.startswith('!'):
                continue
            statements.append(stmt)

    return statements


def _comparison_to_expr(obj: Expr | Comparison) -> Expr:
    if isinstance(obj, Comparison):
        return obj.to_expression()
    return obj


class UnsupportedDgsExpression(Exception):
    pass


class DgsExpressionParser(ast.NodeVisitor):
    def __init__(self, symbol_table: Dict[str, Var]):
        self.symbol_table = symbol_table
        self._replacement_map: Dict[str, str] = {_safe_name(name): name for name in symbol_table.keys()}

    def preprocess(self, expr: str) -> str:
        text: str = expr.strip()
        text = text.replace('^', '**')
        text = text.replace('.and.', ' and ')
        text = text.replace('.or.', ' or ')
        text = text.replace('.not.', ' not ')

        replacements: List[Tuple[str, str]] = list()
        for name in sorted(self.symbol_table.keys(), key=len, reverse=True):
            replacements.append((name, _safe_name(name)))

        for original, safe in replacements:
            text = re.sub(re.escape(original), safe, text)

        return text

    def parse(self, expr: str) -> Expr | Comparison:
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
        raise UnsupportedDgsExpression(ast.dump(node))

    def visit_BinOp(self, node: ast.BinOp) -> Expr:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
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
            return left == right
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
        args = [self.visit(arg) for arg in node.args]

        if name == 'sin' and len(args) == 1:
            return sin(args[0])
        if name == 'cos' and len(args) == 1:
            return cos(args[0])
        if name == 'sqrt' and len(args) == 1:
            return sqrt(args[0])
        if name == 'abs' and len(args) == 1:
            return abs(args[0])
        if name == 'exp' and len(args) == 1:
            return exp(args[0])
        if name == 'log' and len(args) == 1:
            return log(args[0])
        if name == 'atan2' and len(args) == 2:
            return Func2('atan2', args[0], args[1])
        if name == 'max' and len(args) == 2:
            return max(args[0], args[1])
        if name == 'min' and len(args) == 2:
            return min(args[0], args[1])
        if name == 'sqr' and len(args) == 1:
            return args[0] * args[0]
        if name in {'lim', 'lim_const'} and len(args) == 3:
            return hard_sat(args[0], args[1], args[2])
        if name in {'select', 'select_const'} and len(args) == 3:
            cond = _comparison_to_expr(args[0])
            return cond * args[1] + (Const(1.0) - cond) * args[2]
        if name == 'pi' and len(args) == 0:
            return Const(math.pi)
        if name == 'twopi' and len(args) == 0:
            return Const(2.0 * math.pi)

        if name in {'inc', 'lastvalue', 'reset', 'flipflop', 'lapprox', 'vardef'}:
            raise UnsupportedDgsExpression(f"Unsupported PowerFactory helper '{name}'")

        raise UnsupportedDgsExpression(f"Unsupported function '{name}'")

    def generic_visit(self, node: ast.AST):
        raise UnsupportedDgsExpression(ast.dump(node))


@dataclass
class ParsedDgsBlockDefinition:
    blkdef: BlkDef
    state_rhs: Dict[str, Expr]
    algebraic_rhs: Dict[str, Expr]
    unsupported_lines: List[str]
    signal_dependencies: Dict[str, Set[str]]


@dataclass
class DgsRootBlockResult:
    root_block: Block
    root_blkdef: ParsedDgsBlockDefinition
    root_element: ElmComp
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition]
    dependency_graph: Dict[str, Set[str]]
    producer_map: Dict[str, Set[str]]
    consumer_map: Dict[str, Set[str]]


@dataclass
class DgsBlockSubgraphResult:
    selected_block: ParsedDgsBlockDefinition
    view_block: Block
    node_ids: Set[str]
    dependency_graph: Dict[str, Set[str]]
    upstream: Dict[str, Set[str]]
    downstream: Dict[str, Set[str]]


def _graph_to_serializable(graph: Dict[str, Set[str]]) -> Dict[str, List[str]]:
    return {key: sorted(values) for key, values in graph.items()}


def _iter_blocks_recursive(block: Block) -> Iterable[Block]:
    yield block
    for child in block.children:
        yield from _iter_blocks_recursive(child)


def _make_identifier_map(block: Block) -> Dict[int, str]:
    vars_out: Dict[int, Var] = dict()
    consts_out: Dict[int, Const] = dict()
    _collect_block_vars_recursive(block, vars_out, consts_out)

    used: Dict[str, int] = dict()
    mapping: Dict[int, str] = dict()
    for var in sorted(vars_out.values(), key=lambda item: item.name):
        base = _safe_name(var.name)
        count = used.get(base, 0)
        used[base] = count + 1
        mapping[var.uid] = base if count == 0 else f"{base}_{count}"
    return mapping


def _expr_to_python(expr: Expr, identifier_map: Dict[int, str]) -> str:
    if isinstance(expr, Var):
        return identifier_map[expr.uid]
    if isinstance(expr, Const):
        return f"sym.Const({repr(expr.value)})"
    if isinstance(expr, Func2):
        return f"sym.{expr.name}({_expr_to_python(expr.arg1, identifier_map)}, {_expr_to_python(expr.arg2, identifier_map)})"
    from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, UnOp, Func
    if isinstance(expr, BinOp):
        return f"({_expr_to_python(expr.left, identifier_map)} {expr.op} {_expr_to_python(expr.right, identifier_map)})"
    if isinstance(expr, UnOp):
        return f"({expr.op}{_expr_to_python(expr.operand, identifier_map)})"
    if isinstance(expr, Func):
        return f"sym.{expr.op}({_expr_to_python(expr.arg, identifier_map)})"
    raise TypeError(f"Unsupported expression type for Python export: {type(expr).__name__}")


def _const_or_expr_to_python(value: Expr | Const, identifier_map: Dict[int, str]) -> str:
    if isinstance(value, Const):
        return f"vf.add_const({repr(value.value)}, name={repr(value.name)})"
    return _expr_to_python(value, identifier_map)


def _emit_block_code(
    block: Block,
    identifier_map: Dict[int, str],
    block_var_name: str,
    lines: List[str],
    child_ref_names: Dict[int, str],
) -> None:
    lines.append(f"    {block_var_name} = Block(")
    if block.state_eqs:
        lines.append("        state_eqs=[")
        for eq in block.state_eqs:
            lines.append(f"            {_expr_to_python(eq, identifier_map)},")
        lines.append("        ],")
        lines.append("        state_vars=[" + ", ".join(identifier_map[v.uid] for v in block.state_vars) + "],")
    if block.algebraic_eqs:
        lines.append("        algebraic_eqs=[")
        for eq in block.algebraic_eqs:
            lines.append(f"            {_expr_to_python(eq, identifier_map)},")
        lines.append("        ],")
        lines.append("        algebraic_vars=[" + ", ".join(identifier_map[v.uid] for v in block.algebraic_vars) + "],")
    if block.children:
        lines.append("        children=[" + ", ".join(child_ref_names[id(child)] for child in block.children) + "],")
    if block.in_vars:
        lines.append("        in_vars=[" + ", ".join(identifier_map[v.uid] for v in block.in_vars) + "],")
    if block.out_vars:
        lines.append("        out_vars=[" + ", ".join(identifier_map[v.uid] for v in block.out_vars) + "],")
    lines.append(f"        name={repr(block.name)}")
    lines.append("    )")

    if block.diff_vars:
        lines.append(f"    {block_var_name}.diff_vars = [" + ", ".join(identifier_map[v.uid] for v in block.diff_vars) + "]")

    if block.event_dict:
        lines.append(f"    {block_var_name}.event_dict = {{")
        for key, value in block.event_dict.items():
            lines.append(f"        {identifier_map[key.uid]}: {_const_or_expr_to_python(value, identifier_map)},")
        lines.append("    }")

    if block.init_eqs:
        lines.append(f"    {block_var_name}.init_eqs = {{")
        for key, value in block.init_eqs.items():
            lines.append(f"        {identifier_map[key.uid]}: {_const_or_expr_to_python(value, identifier_map)},")
        lines.append("    }")

    if block.diff_init_eqs:
        lines.append(f"    {block_var_name}.diff_init_eqs = {{")
        for key, value in block.diff_init_eqs.items():
            lines.append(f"        {identifier_map[key.uid]}: {_const_or_expr_to_python(value, identifier_map)},")
        lines.append("    }")


def _emit_template_style_module(
    result: DgsRootBlockResult,
    subgraph: DgsBlockSubgraphResult,
    dgs_path: str,
) -> str:
    block = subgraph.view_block
    identifier_map = _make_identifier_map(block)
    func_base_name = _safe_name(subgraph.selected_block.blkdef.loc_name).lower()

    vars_out: Dict[int, Var] = dict()
    consts_out: Dict[int, Const] = dict()
    _collect_block_vars_recursive(block, vars_out, consts_out)

    all_vars = list(vars_out.values())
    state_uids = {v.uid for b in _iter_blocks_recursive(block) for v in b.state_vars}
    diff_uids = {v.uid for b in _iter_blocks_recursive(block) for v in b.diff_vars}
    param_uids = {k.uid for b in _iter_blocks_recursive(block) for k in b.event_dict.keys()} | {k.uid for b in _iter_blocks_recursive(block) for k in b.parameters.keys()}

    state_vars = [v for v in all_vars if v.uid in state_uids and v.uid not in diff_uids]
    diff_vars = [v for v in all_vars if v.uid in diff_uids]
    param_vars = [v for v in all_vars if v.uid in param_uids and v.uid not in diff_uids]
    algebraic_vars = [
        v for v in all_vars
        if v.uid not in state_uids and v.uid not in diff_uids and v.uid not in param_uids
    ]

    lines: List[str] = list()
    lines.append("# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---")
    lines.append(f"# Source: {dgs_path}")
    lines.append("")
    lines.append("from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory")
    lines.append("from VeraGridEngine.Utils.Symbolic import symbolic as sym")
    lines.append("from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate")
    lines.append("from VeraGridEngine.Utils.Symbolic.block import Block")
    lines.append("from VeraGridEngine.enumerations import DeviceType")
    lines.append("")
    lines.append(f"def get_{func_base_name}_emt_template(vf: VarFactory, name: str = {repr(subgraph.selected_block.blkdef.loc_name)}) -> EmtModelTemplate:")
    lines.append("    templ = EmtModelTemplate()")
    lines.append("    templ.tpe = DeviceType.NoDevice")
    lines.append("    templ.name = name")
    lines.append("")
    lines.append("    # --- Parameters ---")
    for var in sorted(param_vars, key=lambda item: item.name):
        lines.append(f"    {identifier_map[var.uid]} = vf.add_var({repr(var.name + '_')} + name)")
    lines.append("")
    lines.append("    # --- State Variables ---")
    for var in sorted(state_vars, key=lambda item: item.name):
        lines.append(f"    {identifier_map[var.uid]} = vf.add_var({repr(var.name + '_')} + name)")
    lines.append("")
    lines.append("    # --- Algebraic / Shared Variables ---")
    for var in sorted(algebraic_vars, key=lambda item: item.name):
        lines.append(f"    {identifier_map[var.uid]} = vf.add_var({repr(var.name + '_')} + name)")
    lines.append("")
    lines.append("    # --- Derivative Variables ---")
    for var in sorted(diff_vars, key=lambda item: item.name):
        base_name = identifier_map[var.base_var.uid]
        lines.append(f"    {identifier_map[var.uid]} = vf.add_diff_var({repr(var.name + '_')} + name, base_var={base_name})")
    lines.append("")
    lines.append("    # --- Block Assembly ---")
    child_ref_names: Dict[int, str] = {
        id(child): f"{_safe_name(child.name)}_{idx}"
        for idx, child in enumerate(block.children)
    }
    for child in block.children:
        _emit_block_code(child, identifier_map, child_ref_names[id(child)], lines, child_ref_names)
        lines.append("")
    _emit_block_code(block, identifier_map, "templ.block", lines, child_ref_names)
    lines.append("    templ.block.name = name")
    lines.append("")
    lines.append("    return templ")
    lines.append("")
    lines.append("def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:")
    lines.append(f"    return get_{func_base_name}_emt_template(vf=vf, name={repr(subgraph.selected_block.blkdef.loc_name)} if name is None else name)")

    return "\n".join(lines) + "\n"


def _emit_tree_style_module(
    result: DgsRootBlockResult,
    subgraph: DgsBlockSubgraphResult,
    dgs_path: str,
) -> str:
    block_data_repr = pprint.pformat(subgraph.view_block.to_dict(), width=120, sort_dicts=False)
    graph_repr = pprint.pformat(_graph_to_serializable(subgraph.dependency_graph), width=120, sort_dicts=False)
    upstream_repr = pprint.pformat(_graph_to_serializable(subgraph.upstream), width=120, sort_dicts=False)
    downstream_repr = pprint.pformat(_graph_to_serializable(subgraph.downstream), width=120, sort_dicts=False)
    metadata_repr = pprint.pformat({
        "dgs_path": str(dgs_path),
        "root_element_name": result.root_element.loc_name,
        "root_element_typ_id": result.root_element.typ_id,
        "root_blkdef_id": result.root_blkdef.blkdef.ID,
        "root_blkdef_name": result.root_blkdef.blkdef.loc_name,
        "selected_block_id": subgraph.selected_block.blkdef.ID,
        "selected_block_name": subgraph.selected_block.blkdef.loc_name,
        "selected_inputs": subgraph.selected_block.blkdef.inputs,
        "selected_outputs": subgraph.selected_block.blkdef.outputs,
        "selected_states": subgraph.selected_block.blkdef.states,
        "selected_params": subgraph.selected_block.blkdef.params,
        "unsupported_lines": subgraph.selected_block.unsupported_lines,
        "child_block_names": sorted(child.name for child in subgraph.view_block.children),
        "node_ids": sorted(subgraph.node_ids),
    }, width=120, sort_dicts=False)

    return f'''# Auto-generated DGS block tree export.
# Source: {dgs_path}

from VeraGridEngine.Utils.Symbolic.block import Block


BLOCK_DATA = {block_data_repr}

DEPENDENCY_GRAPH = {graph_repr}

UPSTREAM_GRAPH = {upstream_repr}

DOWNSTREAM_GRAPH = {downstream_repr}

METADATA = {metadata_repr}


def get_block() -> Block:
    return Block.parse(BLOCK_DATA)


def get_dependency_graph() -> dict:
    return DEPENDENCY_GRAPH


def get_upstream_graph() -> dict:
    return UPSTREAM_GRAPH


def get_downstream_graph() -> dict:
    return DOWNSTREAM_GRAPH


def get_metadata() -> dict:
    return METADATA
'''


def _clone_const_with_factory(value: Const | Expr, const_factory: callable) -> Const | Expr:
    if isinstance(value, Const):
        return const_factory(value=value.value, name=value.name)
    return value


def _collect_block_vars_recursive(block: Block, vars_out: Dict[int, Var], consts_out: Dict[int, Const]) -> None:
    var_lists = [block.state_vars, block.algebraic_vars, block.diff_vars, block.in_vars, block.out_vars]
    for var_list in var_lists:
        for var in var_list:
            vars_out[var.uid] = var

    dict_like = [block.event_dict, block.mode_dict, block.init_eqs, block.diff_init_eqs, block.parameters, block.init_values]
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

    expr_lists = [block.state_eqs, block.algebraic_eqs, block.differential_eqs]
    for expr_list in expr_lists:
        for expr in expr_list:
            if isinstance(expr, Expr):
                for var in expr.get_vars():
                    vars_out[var.uid] = var

    for child in block.children:
        _collect_block_vars_recursive(child, vars_out, consts_out)


def materialize_block_with_var_factory(block_data: dict | Block, vf: Any, name: str) -> Block:
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

    var_mapping: Dict[Any, Expr] = dict()
    created_vars: Dict[int, Var] = dict()
    created_consts: Dict[int, Const] = dict()

    non_diff_vars = [var for var in vars_out.values() if var.base_var is None]
    diff_vars = [var for var in vars_out.values() if var.base_var is not None]

    for var in sorted(non_diff_vars, key=lambda item: item.name):
        new_var = vf.add_var(f"{var.name}_{name}")
        created_vars[var.uid] = new_var
        var_mapping[var] = new_var
        var_mapping[var.name] = new_var

    for var in sorted(diff_vars, key=lambda item: item.name):
        base_var = created_vars[var.base_var.uid]
        new_var = vf.add_diff_var(f"{var.name}_{name}", base_var=base_var)
        created_vars[var.uid] = new_var
        var_mapping[var] = new_var
        var_mapping[var.name] = new_var

    for const in consts_out.values():
        new_const = vf.add_const(value=const.value, name=const.name)
        created_consts[const.uid] = new_const
        var_mapping[const] = new_const

    def clone_block_recursive(block: Block) -> Block:
        cloned = Block(name=f"{block.name}_{name}")
        cloned.state_vars = [created_vars[v.uid] for v in block.state_vars]
        cloned.algebraic_vars = [created_vars[v.uid] for v in block.algebraic_vars]
        cloned.diff_vars = [created_vars[v.uid] for v in block.diff_vars]
        cloned.in_vars = [created_vars[v.uid] for v in block.in_vars]
        cloned.out_vars = [created_vars[v.uid] for v in block.out_vars]

        cloned.state_eqs = [expr.subs(var_mapping) for expr in block.state_eqs]
        cloned.algebraic_eqs = [expr.subs(var_mapping) for expr in block.algebraic_eqs]
        cloned.differential_eqs = [expr.subs(var_mapping) for expr in block.differential_eqs]

        cloned.event_dict = {created_vars[k.uid]: _clone_const_with_factory(v.subs(var_mapping) if isinstance(v, Expr) else v, vf.add_const) for k, v in block.event_dict.items()}
        cloned.mode_dict = {created_vars[k.uid]: (v.subs(var_mapping) if isinstance(v, Expr) else v) for k, v in block.mode_dict.items()}
        cloned.init_eqs = {created_vars[k.uid]: v.subs(var_mapping) for k, v in block.init_eqs.items()}
        cloned.diff_init_eqs = {created_vars[k.uid]: v.subs(var_mapping) for k, v in block.diff_init_eqs.items()}
        cloned.parameters = {created_vars[k.uid]: _clone_const_with_factory(v, vf.add_const) for k, v in block.parameters.items()}
        cloned.init_values = {created_vars[k.uid]: _clone_const_with_factory(v, vf.add_const) for k, v in block.init_values.items()}
        cloned.children = [clone_block_recursive(child) for child in block.children]
        return cloned

    return clone_block_recursive(source_block)


def _build_symbol_table(
    blkdef: BlkDef,
    shared_signals: Dict[str, Var],
) -> Tuple[Dict[str, Var], List[Var], Dict[str, Var], Dict[str, Var], Dict[str, Var]]:
    symbol_table: Dict[str, Var] = dict()
    shared_names: Set[str] = set(blkdef.inputs + blkdef.outputs + blkdef.internals)

    for name in shared_names:
        if name not in shared_signals:
            shared_signals[name] = Var(name=name)
        symbol_table[name] = shared_signals[name]

    state_vars: List[Var] = list()
    state_var_map: Dict[str, Var] = dict()
    diff_var_map: Dict[str, Var] = dict()
    param_var_map: Dict[str, Var] = dict()

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


def _parse_blkdef(blkdef: BlkDef, shared_signals: Dict[str, Var]) -> ParsedDgsBlockDefinition:
    symbol_table, state_vars, state_var_map, diff_var_map, _param_var_map = _build_symbol_table(blkdef, shared_signals)
    parser = DgsExpressionParser(symbol_table)

    state_rhs: Dict[str, Expr] = dict()
    algebraic_rhs: Dict[str, Expr] = dict()
    unsupported_lines: List[str] = list()
    signal_dependencies: Dict[str, Set[str]] = dict()

    for stmt in _split_equation_statements(blkdef.equations_raw):
        if stmt.startswith('!'):
            continue

        diff_match = re.match(r'^(?P<lhs>.+?)\.\s*=\s*(?P<rhs>.+)$', stmt)
        alg_match = re.match(r'^(?P<lhs>[^=]+?)\s*=\s*(?P<rhs>.+)$', stmt)

        if diff_match is not None:
            lhs_name = diff_match.group('lhs').strip()
            rhs_text = diff_match.group('rhs').strip()
            try:
                rhs_expr = parser.parse(rhs_text)
            except UnsupportedDgsExpression:
                unsupported_lines.append(stmt)
                continue

            if not isinstance(rhs_expr, Expr):
                unsupported_lines.append(stmt)
                continue

            state_rhs[lhs_name] = rhs_expr
            signal_dependencies[lhs_name] = {v.name for v in rhs_expr.get_vars()}
        elif alg_match is not None:
            lhs_name = alg_match.group('lhs').strip()
            rhs_text = alg_match.group('rhs').strip()
            try:
                rhs_expr = parser.parse(rhs_text)
            except UnsupportedDgsExpression:
                unsupported_lines.append(stmt)
                continue

            if isinstance(rhs_expr, Comparison):
                rhs_expr = rhs_expr.to_expression()

            algebraic_rhs[lhs_name] = rhs_expr
            signal_dependencies[lhs_name] = {v.name for v in rhs_expr.get_vars()}
        else:
            unsupported_lines.append(stmt)

    return ParsedDgsBlockDefinition(
        blkdef=blkdef,
        state_rhs=state_rhs,
        algebraic_rhs=algebraic_rhs,
        unsupported_lines=unsupported_lines,
        signal_dependencies=signal_dependencies,
    )


def _score_root_candidate(blkdef: ParsedDgsBlockDefinition) -> Tuple[int, int, int, int, int]:
    return (
        len(blkdef.blkdef.inputs),
        len(blkdef.blkdef.outputs),
        len(blkdef.blkdef.states),
        len(blkdef.algebraic_rhs) + len(blkdef.state_rhs),
        len(blkdef.blkdef.internals),
    )


def _select_root_element(circuit: DgsCircuit, parsed_blocks: Dict[str, ParsedDgsBlockDefinition], root_name: str | None, root_typ_id: str | None) -> Tuple[ElmComp, ParsedDgsBlockDefinition]:
    candidates: List[ElmComp] = list(circuit.elmcomps)
    if root_name is not None:
        candidates = [elm for elm in candidates if elm.loc_name == root_name]

    if root_typ_id is not None:
        candidates = [elm for elm in candidates if str(elm.typ_id).strip() == str(root_typ_id).strip()]

    if not candidates:
        raise ValueError("No matching ElmComp root candidate found in the DGS file")

    best_element: ElmComp | None = None
    best_block: ParsedDgsBlockDefinition | None = None
    best_score: Tuple[int, int, int, int, int] | None = None

    for elm in candidates:
        blk = parsed_blocks.get(str(elm.typ_id).strip())
        if blk is None:
            continue
        score = _score_root_candidate(blk)
        if best_score is None or score > best_score:
            best_element = elm
            best_block = blk
            best_score = score

    if best_element is None or best_block is None:
        raise ValueError("No ElmComp candidate could be resolved to a parsed BlkDef")

    return best_element, best_block


def _collect_reachable_blocks(root_blkdef: ParsedDgsBlockDefinition, parsed_blocks: Dict[str, ParsedDgsBlockDefinition]) -> Dict[str, ParsedDgsBlockDefinition]:
    frontier: Set[str] = set(root_blkdef.blkdef.inputs + root_blkdef.blkdef.outputs + root_blkdef.blkdef.internals)
    reachable: Dict[str, ParsedDgsBlockDefinition] = dict()
    changed = True

    while changed:
        changed = False
        for block_id, parsed in parsed_blocks.items():
            if block_id == root_blkdef.blkdef.ID or block_id in reachable:
                continue
            io_names = set(parsed.blkdef.inputs + parsed.blkdef.outputs + parsed.blkdef.internals)
            if io_names & frontier:
                reachable[block_id] = parsed
                frontier |= io_names
                changed = True

    return reachable


def _build_block_from_parsed(parsed: ParsedDgsBlockDefinition, shared_signals: Dict[str, Var]) -> Block:
    symbol_table, state_vars, _state_map, diff_var_map, param_var_map = _build_symbol_table(parsed.blkdef, shared_signals)

    algebraic_pairs: List[Tuple[Var, Expr]] = list()
    used_alg_names: Set[str] = set()
    for lhs_name, rhs_expr in parsed.algebraic_rhs.items():
        if lhs_name in symbol_table:
            lhs_var = symbol_table[lhs_name]
        else:
            lhs_var = Var(name=f"{parsed.blkdef.loc_name}__{lhs_name}")
            symbol_table[lhs_name] = lhs_var
        algebraic_pairs.append((lhs_var, lhs_var - rhs_expr))
        used_alg_names.add(lhs_name)

    algebraic_vars: List[Var] = [pair[0] for pair in algebraic_pairs]
    algebraic_eqs: List[Expr] = [pair[1] for pair in algebraic_pairs]

    state_eqs: List[Expr] = list()
    effective_state_vars: List[Var] = list()
    effective_diff_vars: List[Var] = list()
    for state_name in parsed.blkdef.states:
        if state_name in parsed.state_rhs:
            effective_state_vars.append(symbol_table[state_name])
            effective_diff_vars.append(diff_var_map[state_name])
            state_eqs.append(parsed.state_rhs[state_name])

    event_dict: Dict[Var, Const] = {param_var: Const(None, name=param_name) for param_name, param_var in param_var_map.items()}

    return Block(
        name=parsed.blkdef.loc_name,
        state_vars=effective_state_vars,
        state_eqs=state_eqs,
        diff_vars=effective_diff_vars,
        algebraic_vars=algebraic_vars,
        algebraic_eqs=algebraic_eqs,
        in_vars=[shared_signals[name] for name in parsed.blkdef.inputs if name in shared_signals],
        out_vars=[shared_signals[name] for name in parsed.blkdef.outputs if name in shared_signals],
        event_dict=event_dict,
    )


def _build_dependency_graph(parsed_blocks: Dict[str, ParsedDgsBlockDefinition]) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Dict[str, Set[str]]]:
    producer_map: Dict[str, Set[str]] = dict()
    consumer_map: Dict[str, Set[str]] = dict()

    for block_id, parsed in parsed_blocks.items():
        produced_names = set(parsed.blkdef.outputs) | set(parsed.algebraic_rhs.keys()) | set(parsed.state_rhs.keys())
        for name in produced_names:
            producer_map.setdefault(name, set()).add(block_id)

        for dep_names in parsed.signal_dependencies.values():
            for name in dep_names:
                consumer_map.setdefault(name, set()).add(block_id)

    dependency_graph: Dict[str, Set[str]] = {block_id: set() for block_id in parsed_blocks.keys()}

    for signal_name, producers in producer_map.items():
        consumers = consumer_map.get(signal_name, set())
        for producer in producers:
            for consumer in consumers:
                if producer != consumer:
                    dependency_graph[producer].add(consumer)

    return dependency_graph, producer_map, consumer_map


def dgs_to_root_block(path: str, root_name: str = "Grid Forming Converter", root_typ_id: str | None = None) -> DgsRootBlockResult:
    circuit = DgsCircuit()
    circuit.parse_dgs(path)

    shared_signals: Dict[str, Var] = dict()
    parsed_blocks: Dict[str, ParsedDgsBlockDefinition] = {
        blk.ID: _parse_blkdef(blk, shared_signals)
        for blk in circuit.blkdefs
    }

    root_element, root_blkdef = _select_root_element(circuit, parsed_blocks, root_name=root_name, root_typ_id=root_typ_id)
    reachable_blocks = _collect_reachable_blocks(root_blkdef, parsed_blocks)

    child_blocks: List[Block] = [
        _build_block_from_parsed(parsed, shared_signals)
        for _, parsed in sorted(reachable_blocks.items(), key=lambda item: item[1].blkdef.loc_name)
    ]

    root_block = Block(
        name=root_element.loc_name,
        children=child_blocks,
        in_vars=[shared_signals[name] for name in root_blkdef.blkdef.inputs if name in shared_signals],
        out_vars=[shared_signals[name] for name in root_blkdef.blkdef.outputs if name in shared_signals],
        algebraic_vars=[shared_signals[name] for name in root_blkdef.blkdef.internals if name in shared_signals],
    )

    combined_blocks: Dict[str, ParsedDgsBlockDefinition] = {root_blkdef.blkdef.ID: root_blkdef, **reachable_blocks}
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


def _reverse_dependency_graph(graph: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    reverse_graph: Dict[str, Set[str]] = {node_id: set() for node_id in graph.keys()}
    for src, dsts in graph.items():
        for dst in dsts:
            reverse_graph.setdefault(dst, set()).add(src)
    return reverse_graph


def _closure_from_node(graph: Dict[str, Set[str]], start_node: str) -> Set[str]:
    visited: Set[str] = set()
    frontier: List[str] = [start_node]

    while frontier:
        node = frontier.pop()
        if node in visited:
            continue
        visited.add(node)
        for nxt in graph.get(node, set()):
            if nxt not in visited:
                frontier.append(nxt)

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

    candidates.sort(key=lambda item: _score_root_candidate(item[1]), reverse=True)
    return candidates[0]


def extract_named_block_subgraph(
    result: DgsRootBlockResult,
    block_name: str,
    block_id: str | None = None,
    include_upstream: bool = True,
    include_downstream: bool = True,
) -> DgsBlockSubgraphResult:
    selected_id, selected_block = _select_named_block(result.parsed_blocks, block_name, block_id)
    reverse_graph = _reverse_dependency_graph(result.dependency_graph)

    node_ids: Set[str] = {selected_id}
    upstream: Dict[str, Set[str]] = dict()
    downstream: Dict[str, Set[str]] = dict()

    if include_upstream:
        upstream_nodes = _closure_from_node(reverse_graph, selected_id)
        node_ids |= upstream_nodes
    if include_downstream:
        downstream_nodes = _closure_from_node(result.dependency_graph, selected_id)
        node_ids |= downstream_nodes

    sub_children: List[Block] = list()
    shared_signals: Dict[str, Var] = dict()
    for node_id in sorted(node_ids, key=lambda nid: result.parsed_blocks[nid].blkdef.loc_name):
        sub_children.append(_build_block_from_parsed(result.parsed_blocks[node_id], shared_signals))

    for node_id in node_ids:
        if include_upstream:
            upstream[node_id] = {src for src in reverse_graph.get(node_id, set()) if src in node_ids}
        if include_downstream:
            downstream[node_id] = {dst for dst in result.dependency_graph.get(node_id, set()) if dst in node_ids}

    selected_runtime_block = _build_block_from_parsed(selected_block, shared_signals)

    view_block = Block(
        name=f"{selected_block.blkdef.loc_name}_subgraph",
        children=sub_children,
        in_vars=selected_runtime_block.in_vars,
        out_vars=selected_runtime_block.out_vars,
        algebraic_vars=selected_runtime_block.algebraic_vars,
    )

    subgraph = {node_id: {dst for dst in result.dependency_graph.get(node_id, set()) if dst in node_ids} for node_id in node_ids}

    return DgsBlockSubgraphResult(
        selected_block=selected_block,
        view_block=view_block,
        node_ids=node_ids,
        dependency_graph=subgraph,
        upstream=upstream,
        downstream=downstream,
    )


def export_named_block_subgraph_to_python(
    dgs_path: str,
    output_path: str,
    block_name: str,
    *,
    block_id: str | None = None,
    root_name: str = "Grid Forming Converter",
    root_typ_id: str | None = None,
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
    subgraph = extract_named_block_subgraph(result, block_name=block_name, block_id=block_id)

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
) -> Path:
    """
    Export a selected DGS block subgraph as a serialized block-tree Python module.
    """
    result = dgs_to_root_block(dgs_path, root_name=root_name, root_typ_id=root_typ_id)
    subgraph = extract_named_block_subgraph(result, block_name=block_name, block_id=block_id)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    module_text = _emit_tree_style_module(result, subgraph, dgs_path)
    out_path.write_text(module_text, encoding="utf-8")
    return out_path

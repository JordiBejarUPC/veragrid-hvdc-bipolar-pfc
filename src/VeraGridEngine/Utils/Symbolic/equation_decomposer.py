from __future__ import annotations

from typing import List, Tuple, Dict, Optional, Any
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagram


class EquationDecomposer:
    """
    Decomposes a Block containing algebraic_eqs and state_eqs
    into a hierarchical Block with children representing basic operations
    (gain, sum, product, divide, etc.) connected as a block diagram.

    This is the inverse of Block.unify_blocks(). Instead of flattening
    child blocks into a single equation set, it takes a monolithic block
    of equations and produces a tree of simple operation blocks that can
    be visually rendered in the DynamicBlockEditorGUI.
    """

    def __init__(self, var_factory: VarFactory):
        self.vf = var_factory
        self._counter: int = 0
        self._expr_cache: Dict[int, Tuple[sym.Var, List[Block]]] = {}
        self._param_uids: set = set()
        self._orig_block: Block | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decompose(self, block: Block) -> Block:
        """
        Decompose a block's equations into child operation blocks.

        Returns a new Block with ``children`` and a populated
        ``BlockDiagram`` suitable for the graphical editor.
        """
        self._counter = 0
        self._expr_cache.clear()
        self._orig_block = block

        self._collect_parameter_uids(block)

        child_blocks: List[Block] = []
        processed_vars: Dict[int, sym.Var] = {}

        for v in block.in_vars:
            processed_vars[v.non_mutable_uid] = v

        for v in block.out_vars:
            processed_vars[v.non_mutable_uid] = v

        eq_order = self._topological_sort_block(block)
        var_to_block_output: Dict[int, sym.Var] = {}

        for eq_key, var, eq in eq_order:
            if eq_key.startswith("alg_"):
                rhs = self._extract_rhs(eq, var)
                if rhs is None:
                    continue
                result_var, blocks = self._decompose_expr(rhs)
                if not blocks and result_var is not var:
                    if isinstance(rhs, sym.Var) and result_var.non_mutable_uid == rhs.non_mutable_uid:
                        pass_through = self._make_pass_through(var, result_var)
                        child_blocks.append(pass_through)
                        var_to_block_output[var.non_mutable_uid] = var
                    else:
                        pass
                elif blocks:
                    last_output = self._remap_last_output(blocks, result_var, var)
                    var_to_block_output[var.non_mutable_uid] = var
                    child_blocks.extend(blocks)
                else:
                    var_to_block_output[var.non_mutable_uid] = result_var

            elif eq_key.startswith("state_"):
                rhs = eq
                result_var, blocks = self._decompose_expr(rhs)
                if not blocks:
                    int_blk = Block(
                        state_vars=[var],
                        state_eqs=[result_var],
                        name="integrator",
                    )
                    child_blocks.append(int_blk)
                else:
                    child_blocks.extend(blocks)
                    int_blk = Block(
                        state_vars=[var],
                        state_eqs=[result_var],
                        name="integrator",
                    )
                    child_blocks.append(int_blk)
                var_to_block_output[var.non_mutable_uid] = var

        diagram = self._build_diagram(child_blocks, block)

        new_event_dict = dict(block.event_dict) if block.event_dict else {}
        new_mode_dict = dict(block.mode_dict) if block.mode_dict else {}
        new_parameters = dict(block.parameters) if block.parameters else {}
        new_init_eqs = dict(block.init_eqs) if block.init_eqs else {}
        new_init_values = dict(block.init_values) if block.init_values else {}
        new_diff_init_eqs = dict(block.diff_init_eqs) if block.diff_init_eqs else {}

        result = Block(
            name=block.name,
            children=child_blocks,
            in_vars=list(block.in_vars),
            out_vars=list(block.out_vars),
            event_dict=new_event_dict,
            mode_dict=new_mode_dict,
            parameters=new_parameters,
            init_eqs=new_init_eqs,
            init_values=new_init_values,
            diff_init_eqs=new_diff_init_eqs,
            external_mapping=dict(block.external_mapping) if block.external_mapping else None,
            api_obj_mapping=dict(block.api_obj_mapping) if block.api_obj_mapping else None,
        )
        result.uid = block.uid
        result.diagram = diagram

        return result

    # ------------------------------------------------------------------
    # Parameter collection
    # ------------------------------------------------------------------

    def _collect_parameter_uids(self, block: Block) -> None:
        self._param_uids.clear()
        for p in block.event_dict or {}:
            self._param_uids.add(p.non_mutable_uid)
        for p in block.mode_dict or {}:
            self._param_uids.add(p.non_mutable_uid)
        for p in block.parameters or {}:
            self._param_uids.add(p.non_mutable_uid)

    def _is_parameter(self, expr: sym.Expr) -> bool:
        if isinstance(expr, sym.Var):
            return expr.non_mutable_uid in self._param_uids
        return False

    def _is_in_var(self, var: sym.Var) -> bool:
        if self._orig_block is None:
            return False
        for v in self._orig_block.in_vars:
            if v.non_mutable_uid == var.non_mutable_uid:
                return True
        return False

    # ------------------------------------------------------------------
    # Naming helpers
    # ------------------------------------------------------------------

    def _new_name(self, prefix: str = "x") -> str:
        self._counter += 1
        return f"_{prefix}_{self._counter}"

    def _new_var(self, prefix: str = "x") -> sym.Var:
        return self.vf.add_var(self._new_name(prefix))

    # ------------------------------------------------------------------
    # Topological sort of equations
    # ------------------------------------------------------------------

    def _topological_sort_block(self, block: Block) -> List[Tuple[str, sym.Var, sym.Expr]]:
        entries: List[Tuple[str, sym.Var, sym.Expr]] = []
        for i, var in enumerate(block.algebraic_vars):
            eq = block.algebraic_eqs[i]
            entries.append((f"alg_{i}", var, eq))
        for i, var in enumerate(block.state_vars):
            eq = block.state_eqs[i]
            entries.append((f"state_{i}", var, eq))

        eq_deps: Dict[str, List[int]] = {}  # eq_key -> [dep_var_uids]
        var_defined_by: Dict[int, str] = {}

        for eq_key, var, eq in entries:
            rhs = eq
            if eq_key.startswith("alg_"):
                extracted = self._extract_rhs(eq, var)
                if extracted is not None:
                    rhs = extracted
            all_vars = rhs.get_vars()
            deps = [
                v.non_mutable_uid for v in all_vars
                if v.non_mutable_uid != var.non_mutable_uid
            ]
            eq_deps[eq_key] = deps
            var_defined_by[var.non_mutable_uid] = eq_key

        adj: Dict[str, set] = {}
        for eq_key, dep_uids in eq_deps.items():
            deps: set = set()
            for uid in dep_uids:
                if uid in var_defined_by:
                    deps.add(var_defined_by[uid])
            adj[eq_key] = deps

        in_degree = {k: len(v) for k, v in adj.items()}
        queue = [k for k, v in in_degree.items() if v == 0]
        sorted_keys: List[str] = []

        while queue:
            node = queue.pop(0)
            sorted_keys.append(node)
            for other_key, other_deps in adj.items():
                if node in other_deps:
                    in_degree[other_key] -= 1
                    if in_degree[other_key] == 0:
                        queue.append(other_key)

        remaining = set(eq_deps.keys()) - set(sorted_keys)
        sorted_keys.extend(remaining)

        key_to_entry = {e[0]: e for e in entries}
        return [key_to_entry[k] for k in sorted_keys if k in key_to_entry]

    # ------------------------------------------------------------------
    # RHS extraction
    # ------------------------------------------------------------------

    def _extract_rhs(self, eq: sym.Expr, defined_var: sym.Var) -> sym.Expr | None:
        if isinstance(eq, sym.BinOp) and eq.op == "-":
            if isinstance(eq.left, sym.Var) and eq.left.non_mutable_uid == defined_var.non_mutable_uid:
                return eq.right
            if isinstance(eq.right, sym.Var) and eq.right.non_mutable_uid == defined_var.non_mutable_uid:
                return eq.left
        return None

    # ------------------------------------------------------------------
    # Expression decomposition (core)
    # ------------------------------------------------------------------

    def _decompose_expr(self, expr: sym.Expr) -> Tuple[sym.Var, List[Block]]:
        cache_key = expr.uid
        if cache_key in self._expr_cache:
            return self._expr_cache[cache_key]

        result: Tuple[sym.Var, List[Block]]

        if isinstance(expr, sym.Var):
            result = (expr, [])

        elif isinstance(expr, sym.Const):
            y = self._new_var("const")
            blk = Block(
                algebraic_vars=[y],
                algebraic_eqs=[y - expr],
                out_vars=[y],
                name="const",
            )
            result = (y, [blk])

        elif isinstance(expr, sym.BinOp):
            result = self._decompose_binop(expr)

        elif isinstance(expr, sym.UnOp):
            result = self._decompose_unop(expr)

        elif isinstance(expr, sym.Func):
            result = self._decompose_func(expr)

        elif isinstance(expr, sym.Func2):
            result = self._decompose_func2(expr)

        else:
            raise TypeError(f"Unsupported expression type: {type(expr)}")

        self._expr_cache[cache_key] = result
        return result

    def _decompose_binop(self, expr: sym.BinOp) -> Tuple[sym.Var, List[Block]]:
        if expr.op == "*":
            return self._decompose_mul(expr)

        left_is_const = isinstance(expr.left, sym.Const)
        right_is_const = isinstance(expr.right, sym.Const)

        if left_is_const:
            left_val: sym.Expr = expr.left
            left_blocks = []
        else:
            left_v, left_blocks = self._decompose_expr(expr.left)
            left_val = left_v

        if right_is_const:
            right_val: sym.Expr = expr.right
            right_blocks = []
        else:
            right_v, right_blocks = self._decompose_expr(expr.right)
            right_val = right_v

        all_blocks = left_blocks + right_blocks

        in_vars: List[sym.Var] = []
        if not left_is_const:
            in_vars.append(left_v)
        if not right_is_const:
            in_vars.append(right_v)

        if expr.op == "+":
            y = self._new_var("sum")
            blk = Block(
                algebraic_vars=[y],
                algebraic_eqs=[y - (left_val + right_val)],
                in_vars=in_vars,
                out_vars=[y],
                name="sum",
            )
            all_blocks.append(blk)
            return (y, all_blocks)

        elif expr.op == "-":
            y = self._new_var("sub")
            blk = Block(
                algebraic_vars=[y],
                algebraic_eqs=[y - (left_val - right_val)],
                in_vars=in_vars,
                out_vars=[y],
                name="substraction",
            )
            all_blocks.append(blk)
            return (y, all_blocks)

        elif expr.op == "/":
            y = self._new_var("div")
            blk = Block(
                algebraic_vars=[y],
                algebraic_eqs=[y - (left_val / right_val)],
                in_vars=in_vars,
                out_vars=[y],
                name="divide",
            )
            all_blocks.append(blk)
            return (y, all_blocks)

        elif expr.op == "**":
            y = self._new_var("pow")
            blk = Block(
                algebraic_vars=[y],
                algebraic_eqs=[y - (left_val ** right_val)],
                in_vars=in_vars,
                out_vars=[y],
                name="power",
            )
            all_blocks.append(blk)
            return (y, all_blocks)

        else:
            raise ValueError(f"Unsupported binary operator: {expr.op}")

    def _decompose_mul(self, expr: sym.BinOp) -> Tuple[sym.Var, List[Block]]:
        if isinstance(expr.right, sym.Const):
            inner_var, inner_blocks = self._decompose_expr(expr.left)
            gain_var = self._new_var("gain")
            gain_param = self.vf.add_var(self._new_name("gain_p"))
            blk = Block(
                algebraic_vars=[gain_var],
                algebraic_eqs=[gain_var - (inner_var * gain_param)],
                in_vars=[inner_var],
                out_vars=[gain_var],
                event_dict={gain_param: sym.Const(expr.right.value)},
                name="gain",
            )
            return (gain_var, inner_blocks + [blk])

        if isinstance(expr.left, sym.Const):
            inner_var, inner_blocks = self._decompose_expr(expr.right)
            gain_var = self._new_var("gain")
            gain_param = self.vf.add_var(self._new_name("gain_p"))
            blk = Block(
                algebraic_vars=[gain_var],
                algebraic_eqs=[gain_var - (gain_param * inner_var)],
                in_vars=[inner_var],
                out_vars=[gain_var],
                event_dict={gain_param: sym.Const(expr.left.value)},
                name="gain",
            )
            return (gain_var, inner_blocks + [blk])

        if isinstance(expr.right, sym.Var) and self._is_parameter(expr.right):
            inner_var, inner_blocks = self._decompose_expr(expr.left)
            gain_var = self._new_var("gain")
            blk = Block(
                algebraic_vars=[gain_var],
                algebraic_eqs=[gain_var - (inner_var * expr.right)],
                in_vars=[inner_var],
                out_vars=[gain_var],
                event_dict={expr.right: sym.Const(0.0)},
                name="gain",
            )
            return (gain_var, inner_blocks + [blk])

        if isinstance(expr.left, sym.Var) and self._is_parameter(expr.left):
            inner_var, inner_blocks = self._decompose_expr(expr.right)
            gain_var = self._new_var("gain")
            blk = Block(
                algebraic_vars=[gain_var],
                algebraic_eqs=[gain_var - (expr.left * inner_var)],
                in_vars=[inner_var],
                out_vars=[gain_var],
                event_dict={expr.left: sym.Const(0.0)},
                name="gain",
            )
            return (gain_var, inner_blocks + [blk])

        left_var, left_blocks = self._decompose_expr(expr.left)
        right_var, right_blocks = self._decompose_expr(expr.right)
        prod_var = self._new_var("prod")
        blk = Block(
            algebraic_vars=[prod_var],
            algebraic_eqs=[prod_var - (left_var * right_var)],
            in_vars=[left_var, right_var],
            out_vars=[prod_var],
            name="product",
        )
        return (prod_var, left_blocks + right_blocks + [blk])

    def _decompose_unop(self, expr: sym.UnOp) -> Tuple[sym.Var, List[Block]]:
        inner_var, inner_blocks = self._decompose_expr(expr.operand)
        if expr.op == "-":
            y = self._new_var("neg")
            neg_param = self.vf.add_var(self._new_name("neg_gain"))
            blk = Block(
                algebraic_vars=[y],
                algebraic_eqs=[y - (neg_param * inner_var)],
                in_vars=[inner_var],
                out_vars=[y],
                event_dict={neg_param: sym.Const(-1.0)},
                name="gain",
            )
            return (y, inner_blocks + [blk])
        else:
            raise ValueError(f"Unsupported unary operator: {expr.op}")

    def _decompose_func(self, expr: sym.Func) -> Tuple[sym.Var, List[Block]]:
        inner_var, inner_blocks = self._decompose_expr(expr.arg)
        y = self._new_var(expr.op)

        func_map = {
            "sin": sym.sin, "cos": sym.cos, "tan": sym.tan,
            "exp": sym.exp, "log": sym.log, "sqrt": sym.sqrt,
            "abs": sym.abs, "asin": sym.asin, "acos": sym.acos,
            "atan": sym.atan, "sinh": sym.sinh, "cosh": sym.cosh,
            "floor": sym.floor, "ceil": sym.ceil,
        }

        if expr.op in func_map:
            f = func_map[expr.op]
            blk = Block(
                algebraic_vars=[y],
                algebraic_eqs=[y - f(inner_var)],
                in_vars=[inner_var],
                out_vars=[y],
                name=expr.op,
            )
            return (y, inner_blocks + [blk])
        else:
            raise ValueError(f"Unsupported function: {expr.op}")

    def _decompose_func2(self, expr: sym.Func2) -> Tuple[sym.Var, List[Block]]:
        left_var, left_blocks = self._decompose_expr(expr.arg1)
        right_var, right_blocks = self._decompose_expr(expr.arg2)
        y = self._new_var(expr.name)

        func2_map = {"atan2": sym.atan2, "min": sym.min, "max": sym.max}

        if expr.name in func2_map:
            f = func2_map[expr.name]
            blk = Block(
                algebraic_vars=[y],
                algebraic_eqs=[y - f(left_var, right_var)],
                in_vars=[left_var, right_var],
                out_vars=[y],
                name=expr.name,
            )
            return (y, left_blocks + right_blocks + [blk])
        else:
            raise ValueError(f"Unsupported function: {expr.name}")

    # ------------------------------------------------------------------
    # Output remapping
    # ------------------------------------------------------------------

    def _remap_last_output(self, blocks: List[Block], current_output: sym.Var, target_output: sym.Var) -> sym.Var:
        if not blocks:
            return current_output
        last = blocks[-1]
        if current_output is not target_output:
            last.update_equations(current_output, target_output)
            last.update_variables(current_output, target_output)
            for i, v in enumerate(last.algebraic_vars):
                if v.non_mutable_uid == current_output.non_mutable_uid:
                    last.algebraic_vars[i] = target_output
            for i, v in enumerate(last.out_vars):
                if v.non_mutable_uid == current_output.non_mutable_uid:
                    last.out_vars[i] = target_output
        return target_output

    def _make_pass_through(self, target_var: sym.Var, source_var: sym.Var) -> Block:
        return Block(
            algebraic_vars=[target_var],
            algebraic_eqs=[target_var - source_var],
            in_vars=[source_var],
            out_vars=[target_var],
            name="passthrough",
        )

    # ------------------------------------------------------------------
    # BlockDiagram construction
    # ------------------------------------------------------------------

    def _build_diagram(self, children: List[Block], parent: Block) -> BlockDiagram:
        diagram = BlockDiagram()

        if not children:
            return diagram

        block_uid_to_idx: Dict[int, int] = {}
        for i, blk in enumerate(children):
            block_uid_to_idx[blk.uid] = i

        var_to_producer_block: Dict[int, int] = {}
        for i, blk in enumerate(children):
            for v in blk.algebraic_vars:
                var_to_producer_block[v.non_mutable_uid] = i
            for v in blk.state_vars:
                var_to_producer_block[v.non_mutable_uid] = i
            for v in blk.out_vars:
                var_to_producer_block[v.non_mutable_uid] = i

        dep_graph: Dict[int, set] = {i: set() for i in range(len(children))}
        for i, blk in enumerate(children):
            for in_var in blk.in_vars:
                producer = var_to_producer_block.get(in_var.non_mutable_uid)
                if producer is not None and producer != i:
                    dep_graph[i].add(producer)
            for state_eq in blk.state_eqs or []:
                for v in state_eq.get_vars():
                    producer = var_to_producer_block.get(v.non_mutable_uid)
                    if producer is not None and producer != i:
                        dep_graph[i].add(producer)

        layers = self._assign_layers(dep_graph)

        SPACING_X = 220.0
        SPACING_Y = 140.0
        START_X = 80.0
        START_Y = 60.0

        positions: Dict[int, Tuple[float, float]] = {}
        for layer_idx, layer_items in enumerate(layers):
            for pos_idx, blk_idx in enumerate(layer_items):
                x = START_X + layer_idx * SPACING_X
                y = START_Y + pos_idx * SPACING_Y
                positions[blk_idx] = (x, y)

        for i, blk in enumerate(children):
            x, y = positions.get(i, (START_X, START_Y))
            diagram.add_node(
                name=blk.name if blk.name else f"block_{i}",
                x=x,
                y=y,
                tpe="",
                device_uid=blk.uid,
            )

        con_uid_counter = 0
        for i, blk in enumerate(children):
            for port_idx, in_var in enumerate(blk.in_vars):
                producer = var_to_producer_block.get(in_var.non_mutable_uid)
                if producer is not None and producer != i:
                    src_port_idx = self._find_output_port(children[producer], in_var)
                    if src_port_idx is not None:
                        con_uid_counter += 1
                        diagram.add_branch(
                            connectionitem_uid=con_uid_counter,
                            device_uid_from=children[producer].uid,
                            device_uid_to=blk.uid,
                            port_number_from=src_port_idx,
                            port_number_to=port_idx,
                            color="#587291",
                        )

            for port_idx, state_eq in enumerate(blk.state_eqs or []):
                for v in state_eq.get_vars():
                    producer = var_to_producer_block.get(v.non_mutable_uid)
                    if producer is not None and producer != i:
                        src_port_idx = self._find_output_port(children[producer], v)
                        if src_port_idx is not None:
                            needed_input_port = self._find_or_create_input_port(blk, v)
                            if needed_input_port is not None:
                                con_uid_counter += 1
                                diagram.add_branch(
                                    connectionitem_uid=con_uid_counter,
                                    device_uid_from=children[producer].uid,
                                    device_uid_to=blk.uid,
                                    port_number_from=src_port_idx,
                                    port_number_to=needed_input_port,
                                    color="#587291",
                                )

        return diagram

    def _assign_layers(self, dep_graph: Dict[int, set]) -> List[List[int]]:
        remaining = set(dep_graph.keys())
        in_degree = {k: len(v) for k, v in dep_graph.items()}
        layers: List[List[int]] = []

        while remaining:
            current_layer = [n for n in remaining if in_degree.get(n, 0) == 0]
            if not current_layer:
                current_layer = [min(remaining)]
            layers.append(sorted(current_layer))
            for n in current_layer:
                remaining.remove(n)
                for other in remaining:
                    if n in dep_graph.get(other, set()):
                        in_degree[other] = max(0, in_degree[other] - 1)

        return layers

    def _find_output_port(self, blk: Block, var: sym.Var) -> int | None:
        for i, v in enumerate(blk.out_vars):
            if v.non_mutable_uid == var.non_mutable_uid:
                return i
        for i, v in enumerate(blk.algebraic_vars):
            if v.non_mutable_uid == var.non_mutable_uid:
                if i < len(blk.out_vars if blk.out_vars else []):
                    return i
                return i
        for i, v in enumerate(blk.state_vars):
            if v.non_mutable_uid == var.non_mutable_uid:
                return i
        return None

    def _find_or_create_input_port(self, blk: Block, var: sym.Var) -> int | None:
        for i, v in enumerate(blk.in_vars):
            if v.non_mutable_uid == var.non_mutable_uid:
                return i
        blk.in_vars.append(var)
        return len(blk.in_vars) - 1

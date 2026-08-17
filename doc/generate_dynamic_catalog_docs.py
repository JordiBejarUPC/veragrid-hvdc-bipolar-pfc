# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Generate one auditable Markdown page per Basic Block Catalog template."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.BasicBlockCatalog import (
    BasicBlockTemplateDescriptor,
    get_editor_ready_basic_block_catalog_descriptors,
    load_basic_block_catalog_template,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.latex_printer import symbolic_to_latex
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var, get_expression_vars


def escape_markdown_table_text(value: str) -> str:
    """Escape text before placing it inside a Markdown table cell.

    :param value: Raw text.
    :return: Markdown-safe table text.
    """
    result: str = value.replace("|", "\\|").replace("\n", " ").strip()
    return result


def build_category_explanation(category_path: Sequence[str]) -> str:
    """Return a category-specific explanation of a catalogue block's role.

    :param category_path: Hierarchical library category.
    :return: Human-readable purpose sentence.
    """
    category_text: str = " ".join(category_path).lower()
    if "arithmetic" in category_text:
        result: str = "It performs a scalar arithmetic transformation on its input signals."
    elif "array" in category_text or "matrix" in category_text or "lookup" in category_text:
        result = "It evaluates tabulated or array-based data using the selected lookup formulation."
    elif "continuous" in category_text:
        result = "It represents a continuous-time dynamic operation, including any declared internal states."
    elif "control" in category_text or "measurement" in category_text:
        result = "It processes measurement or control signals for use inside a dynamic control model."
    elif "logic" in category_text or "event" in category_text:
        result = "It implements logical or event-driven signal behaviour."
    elif "limit" in category_text or "nonlinear" in category_text:
        result = "It applies the declared limiting or nonlinear relation to its input signals."
    elif "math" in category_text:
        result = "It evaluates the mathematical function identified by the block name."
    elif "transform" in category_text:
        result = "It converts signals between the coordinate systems or units identified by the block name."
    elif "complex" in category_text:
        result = "It processes real and imaginary components of complex-valued signals."
    elif "waveform" in category_text or "time" in category_text:
        result = "It generates or evaluates a time-dependent waveform."
    elif "mechanical" in category_text or "drive train" in category_text:
        result = "It represents a mechanical or drive-train relation used by rotating-machine models."
    else:
        result = "It implements the symbolic signal relation identified by its catalogue definition."
    return result


def append_interface_rows(lines: list[str], category: str, names: Sequence[str], meaning: str) -> None:
    """Append one group of interface rows to a Markdown document.

    :param lines: Document lines being assembled.
    :param category: Interface category label.
    :param names: Symbol names in this category.
    :param meaning: Meaning shared by the symbols.
    :return: None.
    """
    name: str
    for name in names:
        safe_name: str = escape_markdown_table_text(name)
        lines.append(f"| {category} | `{safe_name}` | {meaning} | model-dependent |")


def append_equation(lines: list[str], latex: str) -> None:
    """Append one display equation to a Markdown document.

    :param lines: Document lines being assembled.
    :param latex: Equation body without display delimiters.
    :return: None.
    """
    lines.append("$$")
    lines.append(latex)
    lines.append("$$")
    lines.append("")


def build_readable_variable(variable: Var, block_name: str) -> Var:
    """Build a documentation-only variable without generated name affixes.

    :param variable: Runtime variable emitted by the catalogue builder.
    :param block_name: Generated block name used as prefix and suffix.
    :return: Detached variable with a compact documentation name.
    """
    readable_name: str = variable.name
    suffix: str = "_" + block_name
    block_name_head: str
    block_name_separator: str
    block_name_tail: str
    block_name_head, block_name_separator, block_name_tail = block_name.rpartition("__")
    if len(block_name_separator) > 0 and block_name_tail.isdigit():
        base_block_name: str = block_name_head
    else:
        base_block_name = block_name
    prefix: str = base_block_name + "__"
    if readable_name.endswith(suffix):
        readable_name = readable_name[:-len(suffix)]
    else:
        pass
    if readable_name.startswith(prefix):
        readable_name = readable_name[len(prefix):]
    else:
        pass
    result: Var = Var(readable_name)
    return result


def build_readable_expression(expression: Expr, block_name: str) -> Expr:
    """Replace generated runtime variable names in one documentation equation.

    :param expression: Runtime symbolic expression.
    :param block_name: Generated block name used as prefix and suffix.
    :return: Equivalent expression with compact variable names.
    """
    replacements: dict[Var, Var] = dict()
    expression_variable: Var
    for expression_variable in get_expression_vars(expression):
        replacements[expression_variable] = build_readable_variable(expression_variable, block_name)
    if len(replacements) > 0:
        result: Expr = expression.subs(replacements)
    else:
        result = expression
    return result


def append_block_equations(lines: list[str], block: Block) -> int:
    """Append the symbolic equations directly owned by one block.

    :param lines: Document lines being assembled.
    :param block: Symbolic block whose equations are documented.
    :return: Number of equations appended.
    """
    equation_count: int = 0
    equation_index: int
    equation: Expr
    state_variable: Var
    differential_variable: Var
    init_variable: Var
    init_expression: Expr

    for equation_index, equation in enumerate(block.state_eqs):
        readable_equation: Expr = build_readable_expression(equation, block.name)
        if equation_index < len(block.state_vars):
            state_variable = block.state_vars[equation_index]
            readable_state_variable: Var = build_readable_variable(state_variable, block.name)
            append_equation(
                lines,
                "\\frac{d " + symbolic_to_latex(readable_state_variable) + "}{dt} = "
                + symbolic_to_latex(readable_equation),
            )
        else:
            append_equation(lines, "0 = " + symbolic_to_latex(readable_equation))
        equation_count += 1

    for equation in block.algebraic_eqs:
        readable_equation = build_readable_expression(equation, block.name)
        append_equation(lines, "0 = " + symbolic_to_latex(readable_equation))
        equation_count += 1

    for equation_index, equation in enumerate(block.differential_eqs):
        readable_equation = build_readable_expression(equation, block.name)
        if equation_index < len(block.diff_vars):
            differential_variable = block.diff_vars[equation_index]
            readable_differential_variable: Var = build_readable_variable(differential_variable, block.name)
            append_equation(
                lines,
                symbolic_to_latex(readable_differential_variable) + " = "
                + symbolic_to_latex(readable_equation),
            )
        else:
            append_equation(lines, "0 = " + symbolic_to_latex(readable_equation))
        equation_count += 1

    for init_variable, init_expression in block.init_eqs.items():
        readable_init_variable: Var = build_readable_variable(init_variable, block.name)
        readable_init_expression: Expr = build_readable_expression(init_expression, block.name)
        append_equation(
            lines,
            symbolic_to_latex(readable_init_variable) + "(t_0) = "
            + symbolic_to_latex(readable_init_expression),
        )
        equation_count += 1

    return equation_count


def build_catalogue_markdown(descriptor: BasicBlockTemplateDescriptor,
                             template: EmtModelTemplate) -> str:
    """Build one complete Markdown page for a catalogue template.

    :param descriptor: Static catalogue description.
    :param template: Materialized symbolic template.
    :return: Markdown document.
    """
    lines: list[str] = list()
    category_label: str = " / ".join(descriptor.category_path)
    source_name: str = descriptor.blkdef_name.strip()
    title: str = descriptor.display_label.strip()
    if len(title) == 0:
        title = source_name
    else:
        pass

    lines.append("# " + title)
    lines.append("")
    lines.append(
        f"This is Basic Block Catalog type `{descriptor.typ_id}` (`{escape_markdown_table_text(source_name)}`). "
        + build_category_explanation(descriptor.category_path)
    )
    lines.append("")
    lines.append("## Behaviour")
    lines.append("")
    lines.append(f"- Library location: `{escape_markdown_table_text(category_label)}`.")
    lines.append(f"- Inputs: {len(descriptor.inputs)}.")
    lines.append(f"- Outputs: {len(descriptor.outputs)}.")
    lines.append(f"- Declared states: {len(descriptor.states)}.")
    lines.append(f"- Configurable parameters: {len(descriptor.params)}.")
    if len(descriptor.unsupported_lines) == 0:
        lines.append("- The imported definition is fully supported by the Dynamic Editor catalogue.")
    else:
        lines.append("- The catalogue importer reports unsupported source statements; inspect validation before use.")
    lines.append("")
    lines.append("## Characteristic equations")
    lines.append("")

    equation_count: int = 0
    child_block: Block
    for child_block in template.block.get_all_blocks():
        equation_count += append_block_equations(lines, child_block)
    if equation_count == 0:
        lines.append(
            "This block has no continuous DAE equation. Its behaviour is defined by its event, mode, "
            "lookup, or procedural logic fields."
        )
        lines.append("")
    else:
        pass

    lines.append("## Interface table")
    lines.append("")
    lines.append("| Category | Name | Meaning | Units |")
    lines.append("| --- | --- | --- | --- |")
    append_interface_rows(lines, "Input", descriptor.inputs, "Input signal consumed by the block")
    append_interface_rows(lines, "Output", descriptor.outputs, "Output signal produced by the block")
    append_interface_rows(lines, "State", descriptor.states, "Internal dynamic state")
    append_interface_rows(lines, "Parameter", descriptor.params, "Configurable model parameter")
    if len(descriptor.inputs) + len(descriptor.outputs) + len(descriptor.states) + len(descriptor.params) == 0:
        lines.append("| Internal | — | The block has no externally declared symbolic interface | — |")
    else:
        pass

    lines.append("")
    lines.append("## Editing notes")
    lines.append("")
    lines.append(
        "Use General options for numeric parameter values and the DAE tab for symbolic variables and equations. "
        "Changing an Output flag only controls whether a variable is exported; it does not remove the variable "
        "from the model."
    )
    lines.append("")
    return "\n".join(lines)


def generate_catalogue_documentation(repository_root: Path) -> int:
    """Generate every per-template catalogue Markdown file.

    :param repository_root: VeraGrid repository root.
    :return: Number of generated pages.
    """
    output_directory: Path = (
        repository_root / "doc" / "md_source" / "dyn_templates" / "library" / "catalog"
    )
    output_directory.mkdir(parents=True, exist_ok=True)

    generated_count: int = 0
    descriptor: BasicBlockTemplateDescriptor
    for descriptor in get_editor_ready_basic_block_catalog_descriptors():
        template: EmtModelTemplate = load_basic_block_catalog_template(
            descriptor=descriptor,
            var_factory=VarFactory(),
        )
        markdown: str = build_catalogue_markdown(descriptor=descriptor, template=template)
        output_path: Path = output_directory / f"typ_{descriptor.typ_id}.md"
        output_path.write_text(markdown, encoding="utf-8")
        generated_count += 1
    return generated_count


def main() -> None:
    """Generate documentation relative to this repository checkout.

    :return: None.
    """
    repository_root: Path = Path(__file__).resolve().parents[1]
    generated_count: int = generate_catalogue_documentation(repository_root=repository_root)
    print(f"Generated {generated_count} Basic Block Catalog Markdown pages.")


if __name__ == "__main__":
    main()
else:
    pass

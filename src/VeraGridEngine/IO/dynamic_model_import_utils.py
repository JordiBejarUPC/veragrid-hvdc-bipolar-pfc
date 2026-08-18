# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


def sanitize_dynamic_model_file_stem(text: str) -> str:
    """Convert one dynamic-model display name into a filesystem-safe stem.

    :param text: Source display name.
    :return: Filesystem-safe stem.
    """
    safe_characters: list[str] = list()
    character: str

    for character in text:
        if character.isalnum() or character in {"_", "-"}:
            safe_characters.append(character)
        else:
            safe_characters.append("_")

    return "".join(safe_characters).strip("_")


def dynamic_model_value_to_python_syntax(value: object) -> str:
    """Serialize primitive nested metadata as executable Python.

    :param value: Primitive, list or dictionary metadata value.
    :return: Compact executable Python expression.
    """
    if isinstance(value, list):
        item_expressions: list[str] = [
            dynamic_model_value_to_python_syntax(value=item)
            for item in value
        ]
        return "list([" + ", ".join(item_expressions) + "])"
    if isinstance(value, dict):
        pair_expressions: list[str] = [
            "("
            + dynamic_model_value_to_python_syntax(value=key)
            + ", "
            + dynamic_model_value_to_python_syntax(value=item_value)
            + ")"
            for key, item_value in value.items()
        ]
        return "dict([" + ", ".join(pair_expressions) + "])"
    if value is None or isinstance(value, (str, int, float, bool)):
        return repr(value)
    return repr(str(value))


def dynamic_model_value_to_python_syntax_lines(
        value: object,
        indentation: int,
        maximum_line_length: int = 112,
) -> list[str]:
    """Render primitive nested metadata as readable executable lines.

    :param value: Primitive, list or dictionary metadata value.
    :param indentation: Number of leading spaces for the value root.
    :param maximum_line_length: Preferred maximum source-line width.
    :return: Executable Python lines including leading indentation.
    """
    indentation_text: str = " " * indentation
    compact_text: str = dynamic_model_value_to_python_syntax(value=value)

    if indentation + len(compact_text) <= maximum_line_length:
        return [indentation_text + compact_text]
    if isinstance(value, list):
        result_lines: list[str] = [indentation_text + "list(["]
        for item in value:
            item_lines: list[str] = dynamic_model_value_to_python_syntax_lines(
                value=item,
                indentation=indentation + 4,
                maximum_line_length=maximum_line_length,
            )
            item_lines[-1] += ","
            result_lines.extend(item_lines)
        result_lines.append(indentation_text + "])")
        return result_lines
    if isinstance(value, dict):
        result_lines = [indentation_text + "dict(["]
        for key, item_value in value.items():
            result_lines.append((" " * (indentation + 4)) + "(")
            key_lines: list[str] = dynamic_model_value_to_python_syntax_lines(
                value=key,
                indentation=indentation + 8,
                maximum_line_length=maximum_line_length,
            )
            key_lines[-1] += ","
            result_lines.extend(key_lines)
            value_lines: list[str] = dynamic_model_value_to_python_syntax_lines(
                value=item_value,
                indentation=indentation + 8,
                maximum_line_length=maximum_line_length,
            )
            value_lines[-1] += ","
            result_lines.extend(value_lines)
            result_lines.append((" " * (indentation + 4)) + "),")
        result_lines.append(indentation_text + "])")
        return result_lines
    return [indentation_text + compact_text]


def append_python_syntax_assignment(
        lines: list[str],
        prefix: str,
        value: object,
        indentation: int,
        maximum_line_length: int = 112,
) -> None:
    """Append one readable assignment for primitive dynamic-model metadata.

    :param lines: Generated source lines updated in place.
    :param prefix: Assignment text before the metadata value.
    :param value: Primitive nested metadata value.
    :param indentation: Number of spaces before the assignment.
    :param maximum_line_length: Preferred maximum source-line width.
    :return: None.
    """
    compact_text: str = dynamic_model_value_to_python_syntax(value=value)
    compact_line_length: int = indentation + len(prefix) + len(compact_text)

    if compact_line_length <= maximum_line_length:
        lines.append((" " * indentation) + prefix + compact_text)
    else:
        lines.append((" " * indentation) + prefix + "(")
        lines.extend(
            dynamic_model_value_to_python_syntax_lines(
                value=value,
                indentation=indentation + 4,
                maximum_line_length=maximum_line_length,
            )
        )
        lines.append((" " * indentation) + ")")

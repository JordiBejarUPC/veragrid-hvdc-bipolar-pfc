# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

"""
Deterministic retrieval helpers for the VeraGrid AI agent.

This module implements a first RAG layer based on lexical retrieval. The goal is
to ground local and remote LLMs with:

1. Static VeraGrid source-code references.
2. Live runtime records built from the current application state.
"""

import os
import re
from enum import Enum
from importlib.resources import files
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from VeraGrid.Gui.Main.SubClasses.simulations import SimulationsMain


class QueryIntent(Enum):
    """
    Query intent used to balance code and runtime retrieval.
    """

    CODE = "code"
    RUNTIME = "runtime"
    MIXED = "mixed"


class RetrievalDocument:
    """
    One indexed static-program document.

    :param source_path: Relative source path.
    :param title: Human-readable document title.
    :param content: Indexed document content.
    :param keywords: Search keywords extracted from the symbol and path.
    :param kind: Document kind identifier.
    """

    __slots__ = (
        "source_path",
        "title",
        "content",
        "keywords",
        "kind",
    )

    def __init__(
        self,
        source_path: str,
        title: str,
        content: str,
        keywords: list[str],
        kind: str,
    ) -> None:
        """
        Store one static-program document.

        :param source_path: Relative source path.
        :param title: Human-readable document title.
        :param content: Indexed document content.
        :param keywords: Search keywords extracted from the symbol and path.
        :param kind: Document kind identifier.
        """
        self.source_path: str = source_path
        self.title: str = title
        self.content: str = content
        self.keywords: list[str] = keywords
        self.kind: str = kind


class RetrievalHit:
    """
    Search hit returned from the static-program index.

    :param document: Matched document.
    :param score: Retrieval score.
    :param excerpt: Compact excerpt used in the prompt.
    """

    __slots__ = (
        "document",
        "score",
        "excerpt",
    )

    def __init__(self, document: RetrievalDocument, score: int, excerpt: str) -> None:
        """
        Store one search hit.

        :param document: Matched document.
        :param score: Retrieval score.
        :param excerpt: Compact excerpt used in the prompt.
        """
        self.document: RetrievalDocument = document
        self.score: int = score
        self.excerpt: str = excerpt


class RuntimeKnowledgeRecord:
    """
    One runtime record extracted from the VeraGrid application state.

    :param category: Runtime category.
    :param title: Human-readable record title.
    :param content: Searchable record content.
    """

    __slots__ = (
        "category",
        "title",
        "content",
    )

    def __init__(self, category: str, title: str, content: str) -> None:
        """
        Store one runtime record.

        :param category: Runtime category.
        :param title: Human-readable record title.
        :param content: Searchable record content.
        """
        self.category: str = category
        self.title: str = title
        self.content: str = content


class RuntimeRetrievalHit:
    """
    Search hit returned from the runtime snapshot.

    :param record: Matched runtime record.
    :param score: Retrieval score.
    :param excerpt: Compact excerpt used in the prompt.
    """

    __slots__ = (
        "record",
        "score",
        "excerpt",
    )

    def __init__(self, record: RuntimeKnowledgeRecord, score: int, excerpt: str) -> None:
        """
        Store one runtime search hit.

        :param record: Matched runtime record.
        :param score: Retrieval score.
        :param excerpt: Compact excerpt used in the prompt.
        """
        self.record: RuntimeKnowledgeRecord = record
        self.score: int = score
        self.excerpt: str = excerpt


class RuntimeKnowledgeSnapshot:
    """
    Searchable snapshot of the current VeraGrid runtime state.

    :param records: Searchable runtime records.
    """

    __slots__ = ("_records",)

    def __init__(self, records: list[RuntimeKnowledgeRecord]) -> None:
        """
        Store the runtime records.

        :param records: Searchable runtime records.
        """
        self._records: list[RuntimeKnowledgeRecord] = records

    def get_first_record_by_category(self, category: str) -> Optional[RuntimeKnowledgeRecord]:
        """
        Return the first runtime record of a given category.

        :param category: Runtime category.
        :returns: Matching record or None.
        """
        index: int = 0

        while index < len(self._records):
            if self._records[index].category == category:
                return self._records[index]
            else:
                pass
            index += 1

        return None

    def get_records_by_category(self, category: str, limit: int) -> list[RuntimeKnowledgeRecord]:
        """
        Return runtime records for one category.

        :param category: Runtime category.
        :param limit: Maximum record count.
        :returns: Matching records.
        """
        records: list[RuntimeKnowledgeRecord] = list()
        index: int = 0

        while index < len(self._records):
            if self._records[index].category == category:
                records.append(self._records[index])
                if len(records) >= limit:
                    index = len(self._records)
                else:
                    pass
            else:
                pass
            index += 1

        return records

    def search(self, query: str, top_k: int) -> list[RuntimeRetrievalHit]:
        """
        Search the runtime snapshot with lexical scoring.

        :param query: User query.
        :param top_k: Maximum hit count.
        :returns: Ordered runtime hits.
        """
        normalized_query: str = normalize_search_text(query)
        query_tokens: list[str] = tokenize_search_text(query)
        hits: list[RuntimeRetrievalHit] = list()
        index: int = 0

        while index < len(self._records):
            record: RuntimeKnowledgeRecord = self._records[index]
            score: int = score_search_document(
                title_text=record.title,
                content_text=record.content,
                keyword_tokens=list(),
                normalized_query=normalized_query,
                query_tokens=query_tokens,
            )

            if score > 0:
                hits.append(
                    RuntimeRetrievalHit(
                        record=record,
                        score=score,
                        excerpt=build_excerpt_from_text(record.content, query_tokens, 240),
                    )
                )
            else:
                pass
            index += 1

        hits.sort(key=sort_runtime_hits)
        return hits[:top_k]


class ProgramKnowledgeIndex:
    """
    Lexical program index over VeraGrid source files.

    :param package_name: Knowledge package name.
    """

    __slots__ = (
        "_package_name",
        "_documents",
        "_is_built",
    )

    def __init__(self, package_name: str) -> None:
        """
        Store the knowledge package and defer index construction.

        :param package_name: Knowledge package name.
        """
        self._package_name: str = package_name
        self._documents: list[RetrievalDocument] = list()
        self._is_built: bool = False

    def ensure_built(self) -> None:
        """
        Build the packaged knowledge index on first use.

        :returns: Nothing.
        """
        if self._is_built:
            pass
        else:
            self._documents = build_program_documents_from_package(self._package_name)
            self._is_built = True

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        """
        Search the indexed VeraGrid knowledge documents.

        :param query: User query.
        :param top_k: Maximum hit count.
        :returns: Ordered search hits.
        """
        normalized_query: str = normalize_search_text(query)
        query_tokens: list[str] = tokenize_search_text(query)
        hits: list[RetrievalHit] = list()
        index: int = 0

        self.ensure_built()

        while index < len(self._documents):
            document: RetrievalDocument = self._documents[index]
            score: int = score_search_document(
                title_text=document.title,
                content_text=document.content,
                keyword_tokens=document.keywords,
                normalized_query=normalized_query,
                query_tokens=query_tokens,
            )

            if score > 0:
                hits.append(
                    RetrievalHit(
                        document=document,
                        score=score,
                        excerpt=build_excerpt_from_text(document.content, query_tokens, 280),
                    )
                )
            else:
                pass
            index += 1

        hits.sort(key=sort_program_hits)
        return hits[:top_k]


def sort_program_hits(hit: RetrievalHit) -> tuple[int, str, str]:
    """
    Build the sorting key for static-program hits.

    :param hit: Search hit.
    :returns: Sorting key.
    """
    return (-hit.score, hit.document.source_path, hit.document.title)


def sort_runtime_hits(hit: RuntimeRetrievalHit) -> tuple[int, str, str]:
    """
    Build the sorting key for runtime hits.

    :param hit: Search hit.
    :returns: Sorting key.
    """
    return (-hit.score, hit.record.category, hit.record.title)


def normalize_search_text(text: str) -> str:
    """
    Normalize text for lexical matching.

    :param text: Raw text.
    :returns: Normalized text.
    """
    return re.sub(r"[^a-z0-9_]+", " ", text.lower())


def tokenize_search_text(text: str) -> list[str]:
    """
    Tokenize text for lexical matching.

    :param text: Raw text.
    :returns: Normalized tokens.
    """
    normalized_text: str = normalize_search_text(text)
    raw_tokens: list[str] = normalized_text.split()
    tokens: list[str] = list()
    index: int = 0

    while index < len(raw_tokens):
        token: str = raw_tokens[index].strip()
        if len(token) > 1:
            tokens.append(token)
        else:
            pass
        index += 1

    return tokens


def score_search_document(
    title_text: str,
    content_text: str,
    keyword_tokens: list[str],
    normalized_query: str,
    query_tokens: list[str],
) -> int:
    """
    Score one document using deterministic lexical weights.

    :param title_text: Document title.
    :param content_text: Document content.
    :param keyword_tokens: Document keywords.
    :param normalized_query: Normalized query string.
    :param query_tokens: Query tokens.
    :returns: Integer score.
    """
    normalized_title: str = normalize_search_text(title_text)
    normalized_content: str = normalize_search_text(content_text)
    score: int = 0
    index: int = 0

    if len(normalized_query.strip()) > 0:
        if normalized_query in normalized_title:
            score += 20
        else:
            pass

        if normalized_query in normalized_content:
            score += 8
        else:
            pass
    else:
        pass

    while index < len(query_tokens):
        token: str = query_tokens[index]
        if token in normalized_title:
            score += 8
        else:
            pass

        if token in keyword_tokens:
            score += 10
        else:
            pass

        if token in normalized_content:
            score += 3
        else:
            pass
        index += 1

    return score


def build_excerpt_from_text(text: str, query_tokens: list[str], max_chars: int) -> str:
    """
    Build a compact excerpt centered on a matching line.

    :param text: Source text.
    :param query_tokens: Query tokens.
    :param max_chars: Excerpt length cap.
    :returns: Compact excerpt.
    """
    lines: list[str] = text.splitlines()
    index: int = 0
    fallback_excerpt: str = " ".join(text.strip().split())

    while index < len(lines):
        line_text: str = lines[index].strip()
        lower_line_text: str = line_text.lower()
        token_index: int = 0

        while token_index < len(query_tokens):
            if query_tokens[token_index] in lower_line_text:
                compact_line: str = " ".join(line_text.split())
                if len(compact_line) > max_chars:
                    return compact_line[:max_chars].rstrip() + "..."
                else:
                    return compact_line
            else:
                pass
            token_index += 1
        index += 1

    if len(fallback_excerpt) > max_chars:
        return fallback_excerpt[:max_chars].rstrip() + "..."
    else:
        return fallback_excerpt


def build_default_knowledge_package_name() -> str:
    """
    Build the default knowledge package for the static program index.

    :returns: Knowledge package name.
    """
    return "VeraGrid.Gui.AiAgent.knowledge"


def build_program_documents_from_package(package_name: str) -> list[RetrievalDocument]:
    """
    Build the static-program documents from packaged markdown knowledge files.

    :param package_name: Knowledge package name.
    :returns: Indexed documents.
    """
    documents: list[RetrievalDocument] = list()
    resource_entries: list[Any] = list(files(package_name).iterdir())
    resource_index: int = 0

    while resource_index < len(resource_entries):
        resource_entry: Any = resource_entries[resource_index]
        resource_name: str = str(resource_entry.name)
        if resource_name.endswith(".md"):
            documents.extend(build_markdown_documents_from_resource(resource_name, resource_entry.read_text(encoding="utf-8")))
        else:
            pass
        resource_index += 1

    return documents


def build_markdown_documents_from_resource(
    resource_name: str,
    source_text: str,
) -> list[RetrievalDocument]:
    """
    Build heading-level documents from one packaged markdown resource.

    :param resource_name: Markdown resource name.
    :param source_text: Markdown text.
    :returns: Indexed documents.
    """
    documents: list[RetrievalDocument] = list()
    lines: list[str] = source_text.splitlines()
    current_heading: str = resource_name
    current_lines: list[str] = list()
    index: int = 0

    while index < len(lines):
        line_text: str = lines[index]
        if line_text.startswith("#"):
            if len(current_lines) > 0:
                section_text: str = "\n".join(current_lines).strip()
                if len(section_text) > 0:
                    documents.append(
                        RetrievalDocument(
                            source_path=resource_name,
                            title=f"{resource_name}::{current_heading}",
                            content=section_text,
                            keywords=tokenize_search_text(f"{resource_name} {current_heading}"),
                            kind="knowledge_section",
                        )
                    )
                else:
                    pass
            else:
                pass

            current_heading = line_text.lstrip("#").strip()
            current_lines = list()
        else:
            current_lines.append(line_text)
        index += 1

    final_section_text: str = "\n".join(current_lines).strip()
    if len(final_section_text) > 0:
        documents.append(
            RetrievalDocument(
                source_path=resource_name,
                title=f"{resource_name}::{current_heading}",
                content=final_section_text,
                keywords=tokenize_search_text(f"{resource_name} {current_heading}"),
                kind="knowledge_section",
            )
        )
    else:
        pass

    return documents


def classify_query_intent(query: str) -> QueryIntent:
    """
    Classify the user query into code, runtime or mixed intent.

    :param query: User query.
    :returns: Query intent.
    """
    normalized_query: str = normalize_search_text(query)
    code_tokens: list[str] = list()
    runtime_tokens: list[str] = list()
    index: int = 0
    has_code_token: bool = False
    has_runtime_token: bool = False

    code_tokens.extend(
        [
            "class",
            "function",
            "method",
            "module",
            "import",
            "file",
            "path",
            "ui",
            "dialog",
            "widget",
            "source",
            "code",
            "python",
        ]
    )
    runtime_tokens.extend(
        [
            "bus",
            "line",
            "load",
            "generator",
            "grid",
            "case",
            "model",
            "current",
            "study",
            "solver",
            "project",
            "selection",
            "selected",
            "diagram",
            "branch",
            "result",
            "session",
            "network",
        ]
    )

    while index < len(code_tokens):
        if code_tokens[index] in normalized_query:
            has_code_token = True
        else:
            pass
        index += 1

    index = 0
    while index < len(runtime_tokens):
        if runtime_tokens[index] in normalized_query:
            has_runtime_token = True
        else:
            pass
        index += 1

    if has_code_token and has_runtime_token:
        return QueryIntent.MIXED
    else:
        if has_code_token:
            return QueryIntent.CODE
        else:
            if has_runtime_token:
                return QueryIntent.RUNTIME
            else:
                return QueryIntent.MIXED


def build_device_field_lines(device: Any) -> list[str]:
    """
    Build ``field: value`` lines from a VeraGrid editable device.

    :param device: VeraGrid device.
    :returns: Field lines.
    """
    headers: list[str] = list(device.get_headers())
    values: list[object] = list(device.get_save_data())
    lines: list[str] = list()
    index: int = 0
    item_count: int = min(len(headers), len(values))

    lines.append(f"idtag: {device.idtag}")
    lines.append(f"name: {device.name}")
    lines.append(f"code: {device.code}")
    lines.append(f"type_name: {device.type_name}")

    while index < item_count:
        serialized_value: Optional[str] = serialize_runtime_value(values[index])

        if serialized_value is None:
            pass
        else:
            lines.append(f"{headers[index]}: {serialized_value}")
        index += 1

    return lines


def serialize_runtime_value(value: object) -> Optional[str]:
    """
    Serialize one runtime value into prompt-safe text.

    :param value: Runtime value.
    :returns: Serialized text or None when the value should be skipped.
    """
    if value is None:
        return "None"
    else:
        pass

    if isinstance(value, (str, int, float, bool)):
        return str(value)
    else:
        pass

    # Skip opaque Python object reprs, which only add noise to the prompt.
    serialized_text: str = str(value)
    if " object at 0x" in serialized_text:
        return None
    else:
        if len(serialized_text) > 80:
            return serialized_text[:80].rstrip() + "..."
        else:
            return serialized_text


def build_runtime_record_from_device(device: Any, category: str) -> RuntimeKnowledgeRecord:
    """
    Build one runtime record from a VeraGrid device.

    :param device: VeraGrid device.
    :param category: Runtime category.
    :returns: Runtime record.
    """
    title: str = f"{category}: {device.type_name} {device.name}"
    lines: list[str] = build_device_field_lines(device)

    if category == "bus":
        lines.append(f"nominal_voltage_kv: {device.Vnom}")
    else:
        pass

    if category == "line":
        if device.bus_from is None:
            pass
        else:
            lines.append(f"bus_from_name: {device.bus_from.name}")

        if device.bus_to is None:
            pass
        else:
            lines.append(f"bus_to_name: {device.bus_to.name}")
    else:
        pass

    if (category == "load") or (category == "generator"):
        if device.bus is None:
            pass
        else:
            lines.append(f"bus_name: {device.bus.name}")
    else:
        pass

    return RuntimeKnowledgeRecord(
        category=category,
        title=title,
        content="\n".join(lines),
    )


def build_runtime_knowledge_snapshot(app: "SimulationsMain") -> RuntimeKnowledgeSnapshot:
    """
    Build a live runtime snapshot from the current VeraGrid application.

    :param app: VeraGrid main window.
    :returns: Runtime snapshot.
    """
    records: list[RuntimeKnowledgeRecord] = list()
    selected_devices: list[Any] = app.get_selected_devices()
    selected_bus_tuples: list[tuple[int, Any, object | None]] = app.get_diagram_selected_buses()
    buses: list[Any] = list(app.circuit.get_buses())
    lines: list[Any] = list(app.circuit.get_lines())
    loads: list[Any] = list(app.circuit.get_loads())
    generators: list[Any] = list(app.circuit.get_generators())
    drivers: list[Any] = list(app.session.get_available_drivers())
    summary_lines: list[str] = list()
    index: int = 0

    summary_lines.append(f"project_name: {app.circuit.name}")
    summary_lines.append(f"active_study: {app.ui.available_results_to_color_comboBox.currentText().strip()}")
    summary_lines.append(f"solver_name: {app.ui.engineComboBox.currentText().strip()}")
    summary_lines.append(f"bus_count: {app.circuit.get_bus_number()}")
    summary_lines.append(
        f"branch_count: {app.circuit.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True)}"
    )
    summary_lines.append(f"load_count: {app.circuit.get_loads_number()}")
    summary_lines.append(f"generator_count: {app.circuit.get_generators_number()}")
    summary_lines.append(f"selected_device_count: {len(selected_devices)}")
    summary_lines.append(f"selected_bus_count: {len(selected_bus_tuples)}")
    summary_lines.append(f"sample_bus_names: {build_sample_names(buses, 8)}")
    summary_lines.append(f"sample_line_names: {build_sample_names(lines, 8)}")
    summary_lines.append(f"sample_load_names: {build_sample_names(loads, 8)}")
    summary_lines.append(f"sample_generator_names: {build_sample_names(generators, 8)}")
    records.append(
        RuntimeKnowledgeRecord(
            category="project_summary",
            title="project_summary: active VeraGrid session",
            content="\n".join(summary_lines),
        )
    )

    index = 0
    while index < len(selected_devices):
        records.append(build_runtime_record_from_device(selected_devices[index], "selected_device"))
        index += 1

    index = 0
    while index < len(selected_bus_tuples):
        _, bus, _ = selected_bus_tuples[index]
        records.append(build_runtime_record_from_device(bus, "selected_bus"))
        index += 1

    index = 0
    while index < len(buses):
        records.append(build_runtime_record_from_device(buses[index], "bus"))
        index += 1

    index = 0
    while index < len(lines):
        records.append(build_runtime_record_from_device(lines[index], "line"))
        index += 1

    index = 0
    while index < len(loads):
        records.append(build_runtime_record_from_device(loads[index], "load"))
        index += 1

    index = 0
    while index < len(generators):
        records.append(build_runtime_record_from_device(generators[index], "generator"))
        index += 1

    index = 0
    while index < len(drivers):
        driver: Any = drivers[index]
        driver_lines: list[str] = list()
        driver_lines.append(f"driver_name: {driver.name}")
        driver_lines.append(f"driver_type: {driver.tpe.value}")
        driver_lines.append(f"has_results: {driver.results is not None}")
        records.append(
            RuntimeKnowledgeRecord(
                category="study",
                title=f"study: {driver.tpe.value}",
                content="\n".join(driver_lines),
            )
        )
        index += 1

    return RuntimeKnowledgeSnapshot(records=records)


def build_sample_names(devices: list[Any], limit: int) -> str:
    """
    Build a compact comma-separated name sample for one device collection.

    :param devices: Device list.
    :param limit: Maximum name count.
    :returns: Sample-name string.
    """
    names: list[str] = list()
    index: int = 0

    while index < len(devices):
        if len(names) >= limit:
            index = len(devices)
        else:
            names.append(str(devices[index].name))
        index += 1

    if len(names) > 0:
        return ", ".join(names)
    else:
        return "none"


def build_retrieved_context_text(
    query: str,
    program_index: ProgramKnowledgeIndex,
    runtime_snapshot: Optional[RuntimeKnowledgeSnapshot],
) -> str:
    """
    Build the compact retrieved-context block injected before generation.

    :param query: User query.
    :param program_index: Static program index.
    :param runtime_snapshot: Optional runtime snapshot.
    :returns: Retrieved-context block.
    """
    intent: QueryIntent = classify_query_intent(query)
    program_hits: list[RetrievalHit] = list()
    runtime_hits: list[RuntimeRetrievalHit] = list()
    lines: list[str] = list()
    index: int = 0
    summary_query_tokens: list[str] = tokenize_search_text(query)
    is_summary_request: bool = False
    token_index: int = 0

    while token_index < len(summary_query_tokens):
        if summary_query_tokens[token_index] in ["summary", "summarize", "overview", "describe", "grid", "model"]:
            is_summary_request = True
        else:
            pass
        token_index += 1

    if intent == QueryIntent.CODE:
        program_hits = program_index.search(query=query, top_k=6)
    else:
        if intent == QueryIntent.RUNTIME:
            program_hits = list()
        else:
            program_hits = program_index.search(query=query, top_k=4)

    if runtime_snapshot is None:
        runtime_hits = list()
    else:
        if intent == QueryIntent.CODE:
            runtime_hits = runtime_snapshot.search(query=query, top_k=2)
        else:
            if intent == QueryIntent.RUNTIME:
                runtime_hits = runtime_snapshot.search(query=query, top_k=8)
            else:
                runtime_hits = runtime_snapshot.search(query=query, top_k=5)

    if (len(program_hits) == 0) and (len(runtime_hits) == 0) and (runtime_snapshot is None):
        return ""
    else:
        pass

    lines.append("Retrieved VeraGrid references for this question:")
    lines.append(f"Query intent: {intent.value}")

    if runtime_snapshot is None:
        pass
    else:
        project_summary_record: Optional[RuntimeKnowledgeRecord] = runtime_snapshot.get_first_record_by_category(
            "project_summary"
        )
        selected_records: list[RuntimeKnowledgeRecord] = list()

        if project_summary_record is None:
            pass
        else:
            lines.append("Current loaded grid summary:")
            lines.append("When the user says 'given grid', 'current grid', or 'loaded grid',")
            lines.append("they refer to this active VeraGrid session.")
            lines.append(project_summary_record.content)

        if is_summary_request:
            selected_records.extend(runtime_snapshot.get_records_by_category("selected_device", 3))
            selected_records.extend(runtime_snapshot.get_records_by_category("selected_bus", 3))

            if len(selected_records) > 0:
                lines.append("Current explicit selection:")
                index = 0
                while index < len(selected_records):
                    lines.append(f"- {selected_records[index].title}")
                    index += 1
            else:
                pass

    if len(program_hits) > 0:
        lines.append("Static program references:")
        index = 0
        while index < len(program_hits):
            hit: RetrievalHit = program_hits[index]
            lines.append(
                f"- {hit.document.title} [{hit.document.kind}]"
            )
            lines.append(f"  path: {hit.document.source_path}")
            lines.append(f"  excerpt: {hit.excerpt}")
            index += 1
    else:
        pass

    if len(runtime_hits) > 0:
        if is_summary_request:
            pass
        else:
            lines.append("Live runtime references:")
            index = 0
            while index < len(runtime_hits):
                hit = runtime_hits[index]
                lines.append(f"- {hit.record.title} [{hit.record.category}]")
                lines.append(f"  excerpt: {hit.excerpt}")
                index += 1
    else:
        pass

    lines.append("Use these references as grounding only. Do not mention retrieval, prompts, code, or internal context unless the user explicitly asks for them.")
    return "\n".join(lines)

"""Isolated local PageIndex retrieval proof of concept."""

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from backend.models.search import (
    SearchDocument,
    SearchHit,
    SearchReference,
    SearchRequest,
    SearchResult,
    SearchWarning,
)
from backend.services.pageindex.adapter import PageIndexAdapter
from backend.services.pageindex.local_reasoner import (
    LocalPageIndexNode,
    LocalPageIndexReasoner,
    LocalReasonerUnavailableError,
    SelectionValidationError,
    validate_selections,
)


class LocalPageIndexClient(Protocol):
    """Read-only primitives supplied by a locally loaded PageIndex workspace."""

    def get_document(self, doc_id: str) -> str:
        ...

    def get_document_structure(self, doc_id: str) -> str:
        ...

    def get_page_content(self, doc_id: str, pages: str) -> str:
        ...


class LocalPageIndexAdapter:
    """Map read-only local PageIndex primitives into normalized search results."""

    def __init__(
        self,
        client: LocalPageIndexClient,
        reasoner: LocalPageIndexReasoner,
        *,
        pageindex_document_id: str,
        stable_document_id: str,
        max_depth: int = 3,
        max_nodes: int = 100,
        max_serialized_chars: int = 12000,
        max_results: int = 3,
    ) -> None:
        self._client = client
        self._reasoner = reasoner
        self._pageindex_document_id = pageindex_document_id
        self._stable_document_id = stable_document_id
        self._max_depth = max_depth
        self._max_nodes = max_nodes
        self._max_serialized_chars = max_serialized_chars
        self._max_results = max_results

    def retrieve(self, request: SearchRequest) -> SearchResult:
        """Retrieve from an existing local index without indexing or mutation."""
        try:
            document = self._decode_object(
                self._client.get_document(self._pageindex_document_id)
            )
        except ModuleNotFoundError:
            return self._warning_result("pageindex_not_installed", "PageIndex is not installed.")
        except FileNotFoundError:
            return self._warning_result("pageindex_index_missing", "PageIndex index is missing.")
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._warning_result("pageindex_index_corrupt", "PageIndex metadata is corrupt.")

        if document.get("error"):
            return self._warning_result(
                "pageindex_document_not_indexed", str(document["error"])
            )

        try:
            structure = self._decode_list(
                self._client.get_document_structure(self._pageindex_document_id)
            )
        except FileNotFoundError:
            return self._warning_result("pageindex_index_missing", "PageIndex index is missing.")
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._warning_result("pageindex_index_corrupt", "PageIndex tree is corrupt.")
        if structure and isinstance(structure[0], Mapping) and structure[0].get("error"):
            return self._warning_result(
                "pageindex_document_not_indexed", str(structure[0]["error"])
            )

        try:
            nodes = self._prune_nodes(self._normalize_nodes(structure), request.query)
        except ValueError:
            return self._warning_result("pageindex_index_corrupt", "PageIndex tree is corrupt.")
        try:
            raw_selections = self._reasoner.select_nodes(
                request.query, nodes, self._max_results
            )
            selections = validate_selections(
                raw_selections, nodes=nodes, max_results=self._max_results
            )
        except LocalReasonerUnavailableError as error:
            return self._warning_result("pageindex_reasoner_unavailable", str(error))
        except SelectionValidationError as error:
            return self._warning_result("pageindex_reasoner_invalid_output", str(error))

        hits: list[SearchHit] = []
        warnings: list[SearchWarning] = []
        node_by_id = {node.node_id: node for node in nodes}
        for selection in selections:
            node = node_by_id[selection.node_id]
            start_index = selection.start_index or node.start_index
            end_index = selection.end_index or node.end_index
            if start_index is None or end_index is None:
                warnings.append(
                    self._warning("pageindex_content_unavailable", "Selected node has no range.")
                )
                continue
            try:
                content = self._decode_list(
                    self._client.get_page_content(
                        self._pageindex_document_id, f"{start_index}-{end_index}"
                    )
                )
            except (FileNotFoundError, TypeError, ValueError, json.JSONDecodeError):
                warnings.append(
                    self._warning(
                        "pageindex_content_unavailable", "Selected content is unavailable."
                    )
                )
                continue
            if not content or not all(isinstance(item, Mapping) for item in content):
                warnings.append(
                    self._warning(
                        "pageindex_content_unavailable", "Selected content is unavailable."
                    )
                )
                continue
            text = "\n\n".join(
                str(item.get("content", "")) for item in content if item.get("content")
            )
            if not text:
                warnings.append(
                    self._warning(
                        "pageindex_content_unavailable", "Selected content is unavailable."
                    )
                )
                continue
            metadata = {
                "stable_document_id": self._stable_document_id,
                "pageindex_document_id": self._pageindex_document_id,
                "node_id": node.node_id,
                "section_title": node.title,
                "start_index": start_index,
                "end_index": end_index,
                "tree_path": node.tree_path,
                "confidence": selection.confidence,
                "relevance_reason": selection.relevance_reason,
            }
            document_id = f"{self._stable_document_id}:section:{start_index}-{end_index}"
            hits.append(
                SearchHit(
                    document=SearchDocument(
                        id=document_id,
                        content=text,
                        source_type="pageindex_local",
                        metadata=metadata,
                    ),
                    references=(
                        SearchReference(
                            document_id=document_id,
                            title=node.title,
                            source=self._stable_document_id,
                            location=self._pageindex_document_id,
                            page=start_index,
                            section=node.title,
                            citation_label=f"{node.title} ({start_index}-{end_index})",
                        ),
                    ),
                    strategy="pageindex",
                    metadata=metadata,
                )
            )
        return SearchResult(
            hits=tuple(hits),
            warnings=tuple(warnings),
            strategy="pageindex",
            total_hits=len(hits),
            metadata={
                "stable_document_id": self._stable_document_id,
                "pageindex_document_id": self._pageindex_document_id,
            },
        )

    @staticmethod
    def _decode_object(value: str) -> Mapping[str, Any]:
        decoded = json.loads(value)
        if not isinstance(decoded, Mapping):
            raise ValueError("Expected JSON object.")
        return decoded

    @staticmethod
    def _decode_list(value: str) -> list[Any]:
        decoded = json.loads(value)
        if not isinstance(decoded, list):
            raise ValueError("Expected JSON list.")
        return decoded

    def _normalize_nodes(self, structure: Sequence[Any]) -> tuple[LocalPageIndexNode, ...]:
        nodes: list[LocalPageIndexNode] = []

        def visit(raw_nodes: Sequence[Any], path: tuple[str, ...], depth: int) -> None:
            for raw_node in raw_nodes:
                if not isinstance(raw_node, Mapping):
                    raise ValueError("PageIndex tree node is invalid.")
                node_id = raw_node.get("node_id")
                title = raw_node.get("title")
                if not isinstance(node_id, str) or not isinstance(title, str):
                    raise ValueError("PageIndex tree node is missing identity.")
                start_index = raw_node.get("start_index", raw_node.get("line_num"))
                end_index = raw_node.get("end_index", start_index)
                if (
                    isinstance(start_index, bool)
                    or isinstance(end_index, bool)
                    or not isinstance(start_index, int)
                    or not isinstance(end_index, int)
                    or start_index > end_index
                ):
                    raise ValueError("PageIndex tree node range is invalid.")
                node_path = path + (title,)
                nodes.append(
                    LocalPageIndexNode(
                        node_id=node_id,
                        title=title,
                        summary=str(raw_node.get("summary", "")),
                        start_index=start_index,
                        end_index=end_index,
                        tree_path=node_path,
                        depth=depth,
                    )
                )
                children = raw_node.get("nodes", [])
                if not isinstance(children, list):
                    raise ValueError("PageIndex tree children are invalid.")
                visit(children, node_path, depth + 1)

        visit(structure, (), 0)
        return tuple(nodes)

    def _prune_nodes(
        self, nodes: Sequence[LocalPageIndexNode], query: str
    ) -> tuple[LocalPageIndexNode, ...]:
        depth_limited = tuple(
            node
            for node in nodes
            if node.depth <= self._max_depth
        )
        query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        lexical_matches = tuple(
            node
            for node in depth_limited
            if query_tokens.intersection(
                re.findall(r"[a-z0-9]+", f"{node.title} {node.summary}".lower())
            )
        )
        candidates = lexical_matches or depth_limited

        pruned: list[LocalPageIndexNode] = []
        serialized_chars = 0
        for node in candidates:
            if len(pruned) == self._max_nodes:
                break
            node_size = len(
                json.dumps(
                    {
                        "node_id": node.node_id,
                        "title": node.title,
                        "summary": node.summary,
                        "start_index": node.start_index,
                        "end_index": node.end_index,
                        "tree_path": node.tree_path,
                    },
                    ensure_ascii=False,
                )
            )
            if pruned and serialized_chars + node_size > self._max_serialized_chars:
                break
            if not pruned and node_size > self._max_serialized_chars:
                break
            pruned.append(node)
            serialized_chars += node_size
        return tuple(pruned)

    @staticmethod
    def _warning(code: str, message: str) -> SearchWarning:
        return SearchWarning(
            code=code, message=message, source="pageindex", strategy="pageindex"
        )

    def _warning_result(self, code: str, message: str) -> SearchResult:
        return SearchResult(
            warnings=(self._warning(code, message),),
            strategy="pageindex",
            total_hits=0,
            metadata={
                "stable_document_id": self._stable_document_id,
                "pageindex_document_id": self._pageindex_document_id,
            },
        )

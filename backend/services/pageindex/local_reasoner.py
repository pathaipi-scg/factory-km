"""Local reasoning boundary for PageIndex tree selection."""

import json
import re
import ipaddress
import socket
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LocalPageIndexNode:
    """Normalized, text-free PageIndex tree node for local reasoning."""

    node_id: str
    title: str
    summary: str = ""
    start_index: int | None = None
    end_index: int | None = None
    tree_path: tuple[str, ...] = ()
    depth: int = 0


@dataclass(frozen=True)
class NodeSelection:
    """Validated local-reasoner selection of a PageIndex node."""

    node_id: str
    relevance_reason: str
    start_index: int | None
    end_index: int | None
    confidence: float


class SelectionValidationError(ValueError):
    """Raised when a reasoner response violates the selection contract."""


class LocalReasonerUnavailableError(RuntimeError):
    """Raised when the configured approved local reasoner is unavailable."""


@runtime_checkable
class LocalPageIndexReasoner(Protocol):
    """Select relevant PageIndex nodes without generating a final answer."""

    def select_nodes(
        self,
        query: str,
        nodes: Sequence[LocalPageIndexNode],
        max_results: int,
    ) -> Mapping[str, Any]:
        """Return strict JSON-shaped node selections."""
        ...


def validate_selections(
    output: object,
    *,
    nodes: Sequence[LocalPageIndexNode],
    max_results: int,
) -> tuple[NodeSelection, ...]:
    """Validate the strict JSON-shaped result returned by a local reasoner."""
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError as error:
            raise SelectionValidationError("Reasoner output is not valid JSON.") from error

    if not isinstance(output, Mapping) or set(output) != {"selections"}:
        raise SelectionValidationError("Reasoner output must contain only 'selections'.")
    raw_selections = output["selections"]
    if not isinstance(raw_selections, list) or len(raw_selections) > max_results:
        raise SelectionValidationError("Reasoner selection count is invalid.")

    known_nodes = {node.node_id: node for node in nodes}
    selected_node_ids: set[str] = set()
    selections: list[NodeSelection] = []
    required_fields = {"node_id", "relevance_reason", "confidence"}
    optional_fields = {"start_index", "end_index"}
    for raw_selection in raw_selections:
        if not isinstance(raw_selection, Mapping):
            raise SelectionValidationError("Each selection must be an object.")
        if not required_fields.issubset(raw_selection) or not set(raw_selection).issubset(
            required_fields | optional_fields
        ):
            raise SelectionValidationError("Selection fields are invalid.")

        node_id = raw_selection["node_id"]
        reason = raw_selection["relevance_reason"]
        confidence = raw_selection["confidence"]
        if not isinstance(node_id, str) or node_id not in known_nodes:
            raise SelectionValidationError("Selection contains an unknown node_id.")
        if node_id in selected_node_ids:
            raise SelectionValidationError("Selection contains a duplicate node_id.")
        if not isinstance(reason, str):
            raise SelectionValidationError("Selection relevance_reason must be a string.")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise SelectionValidationError("Selection confidence must be numeric.")
        if not 0 <= float(confidence) <= 1:
            raise SelectionValidationError("Selection confidence must be between 0 and 1.")

        start_index = raw_selection.get("start_index")
        end_index = raw_selection.get("end_index")
        if (start_index is None) != (end_index is None):
            raise SelectionValidationError("Selection ranges require both start and end.")
        if start_index is not None:
            if (
                isinstance(start_index, bool)
                or isinstance(end_index, bool)
                or not isinstance(start_index, int)
                or not isinstance(end_index, int)
                or start_index > end_index
            ):
                raise SelectionValidationError("Selection range is invalid.")
            node = known_nodes[node_id]
            if (
                node.start_index is not None
                and node.end_index is not None
                and not (node.start_index <= start_index <= end_index <= node.end_index)
            ):
                raise SelectionValidationError("Selection range is outside the selected node.")

        selections.append(
            NodeSelection(
                node_id=node_id,
                relevance_reason=reason,
                start_index=start_index,
                end_index=end_index,
                confidence=float(confidence),
            )
        )
        selected_node_ids.add(node_id)
    return tuple(selections)


class DeterministicLocalPageIndexReasoner:
    """Keyword-only reasoner for isolated local PoC tests."""

    def select_nodes(
        self,
        query: str,
        nodes: Sequence[LocalPageIndexNode],
        max_results: int,
    ) -> Mapping[str, Any]:
        query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        selections = []
        for node in nodes:
            node_tokens = set(
                re.findall(r"[a-z0-9]+", f"{node.title} {node.summary}".lower())
            )
            if not query_tokens.intersection(node_tokens):
                continue
            selections.append(
                {
                    "node_id": node.node_id,
                    "relevance_reason": "Matched query keywords in the section title or summary.",
                    "start_index": node.start_index,
                    "end_index": node.end_index,
                    "confidence": 1.0,
                }
            )
            if len(selections) == max_results:
                break
        return {"selections": selections}


class OpenAICompatibleLocalReasoner:
    """Select PageIndex nodes through one explicitly configured local endpoint."""

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        timeout: float,
        maximum_results: int,
        approved_hosts: Sequence[str] = (),
    ) -> None:
        self._endpoint = self._validate_endpoint(endpoint, approved_hosts)
        if not model.strip():
            raise ValueError("A local model name is required.")
        if timeout <= 0:
            raise ValueError("Local reasoner timeout must be positive.")
        if maximum_results <= 0:
            raise ValueError("Local reasoner maximum_results must be positive.")
        self._model = model
        self._timeout = timeout
        self._maximum_results = maximum_results

    def select_nodes(
        self,
        query: str,
        nodes: Sequence[LocalPageIndexNode],
        max_results: int,
    ) -> Mapping[str, Any]:
        """Request strict node selections from the configured local model only."""
        limit = min(max_results, self._maximum_results)
        node_payload = [
            {
                "node_id": node.node_id,
                "title": node.title,
                "summary": node.summary,
                "start_index": node.start_index,
                "end_index": node.end_index,
                "depth": node.depth,
            }
            for node in nodes
        ]
        request_payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Select relevant document nodes only. Return JSON with exactly "
                        "one key, selections. Every selection must contain node_id, "
                        "relevance_reason, start_index, end_index, and confidence. "
                        "Do not use Markdown fences. Do not answer the user question."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "nodes": node_payload,
                            "max_results": limit,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
        }
        body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                response_body = response.read().decode("utf-8")
        except (URLError, TimeoutError, socket.timeout) as error:
            raise LocalReasonerUnavailableError(
                f"Configured local reasoner is unavailable: {error}"
            ) from error

        try:
            response_data = json.loads(response_body)
            content = response_data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("Model response content is not a string.")
            selections = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise SelectionValidationError("Reasoner output is not valid strict JSON.") from error

        validate_selections(selections, nodes=nodes, max_results=limit)
        return selections

    @staticmethod
    def _validate_endpoint(endpoint: str, approved_hosts: Sequence[str]) -> str:
        if not endpoint or not endpoint.strip():
            raise ValueError("A local reasoner endpoint is required.")
        parsed = urlparse(endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Local reasoner endpoint is invalid.")

        host = parsed.hostname.lower()
        allowlist = {allowed.lower() for allowed in approved_hosts}
        is_loopback = host == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        if not is_loopback and host not in allowlist:
            raise ValueError("Local reasoner endpoint host is not approved.")
        return endpoint

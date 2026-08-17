"""Read-only logical API client for OpcTagManager canonical lookup."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.config.opc_tag_manager import OpcTagManagerSettings


class OpcTagManagerClientError(RuntimeError):
    """Safe integration failure that never falls back to filesystem access."""


class OpcTagManagerClient:
    def __init__(self, settings: OpcTagManagerSettings | None = None,
                 opener: Callable[..., Any] = urlopen) -> None:
        self.settings = settings or OpcTagManagerSettings.from_environment()
        self._opener = opener

    def supplier_candidates(self, **signals: str) -> list[dict[str, Any]]:
        return self._candidates("/api/suppliers/candidates", signals, "SUP_")

    def contact_candidates(self, **signals: str) -> list[dict[str, Any]]:
        return self._candidates("/api/contacts/candidates", signals, "CNT_", id_key="contact_id")

    def equipment_part_candidates(self, **signals: str) -> list[dict[str, Any]]:
        return self._candidates("/api/equipment-parts/candidates", signals, "EPT_")

    def supplier_equipment_parts(self, supplier_resource_id: str) -> list[dict[str, Any]]:
        self._logical_id(supplier_resource_id, "SUP_")
        return self._list(f"/api/suppliers/{supplier_resource_id}/equipment-parts", "equipment_parts")

    def resource_relationships(self, source_resource_id: str) -> list[dict[str, Any]]:
        self._logical_id(source_resource_id, ("SUP_", "EPT_"))
        return self._list(f"/api/resource-relationships/{source_resource_id}", "relationships")

    def _candidates(self, path: str, signals: dict[str, str], prefix: str, id_key: str = "resource_id") -> list[dict[str, Any]]:
        query = {key: value for key, value in signals.items() if isinstance(value, str) and value.strip()}
        values = self._list(f"{path}?{urlencode(query)}", "candidates")
        for item in values: self._logical_id(item.get(id_key), prefix)
        return values

    def _list(self, path: str, key: str) -> list[dict[str, Any]]:
        request = Request(f"{self.settings.base_url}{path}", method="GET", headers={"Accept": "application/json"})
        try:
            with self._opener(request, timeout=self.settings.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise OpcTagManagerClientError(f"OpcTagManager returned HTTP {error.code}.") from error
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise OpcTagManagerClientError("OpcTagManager lookup failed.") from error
        if not isinstance(payload, dict) or payload.get("success") is not True or not isinstance(payload.get(key), list):
            raise OpcTagManagerClientError("OpcTagManager returned a malformed response.")
        values = payload[key]
        if any(not isinstance(item, dict) for item in values) or self._contains_physical_path(values):
            raise OpcTagManagerClientError("OpcTagManager returned an unsafe response.")
        return values

    @staticmethod
    def _logical_id(value: Any, prefix: str | tuple[str, ...]) -> str:
        prefixes = (prefix,) if isinstance(prefix, str) else prefix
        if not isinstance(value, str) or not value.startswith(prefixes) or "\\" in value or "/" in value:
            raise OpcTagManagerClientError("OpcTagManager returned an invalid logical identity.")
        return value

    @classmethod
    def _contains_physical_path(cls, value: Any) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = str(key).casefold()
                if normalized in {"filesystem_path", "vault_path", "absolute_path", "active_file", "filename"}: return True
                if cls._contains_physical_path(item): return True
        elif isinstance(value, list): return any(cls._contains_physical_path(item) for item in value)
        elif isinstance(value, str):
            return value.startswith("\\\\") or (len(value) > 2 and value[1:3] in {":\\", ":/"})
        return False

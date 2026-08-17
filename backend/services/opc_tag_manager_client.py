"""Read-only logical API client for OpcTagManager canonical lookup."""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.config.opc_tag_manager import OpcTagManagerSettings


class OpcTagManagerClientError(RuntimeError):
    """Safe integration failure that never falls back to filesystem access."""
    def __init__(self, message: str, *, status_code: int | None = None, retriable: bool = False) -> None:
        super().__init__(message); self.status_code=status_code; self.retriable=retriable


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

    def get_canonical_state(self, canonical_id: str) -> dict[str, Any]:
        self._logical_id(canonical_id, ("SUP_","CNT_","EPT_","MAN_","DWG_","QUO_","DOC_"))
        return self._object(f"/api/canonical/{canonical_id}", "state")

    def search_opc_tags(self, query: str, limit: int = 25, include_inactive: bool = False) -> list[dict[str, Any]]:
        if not isinstance(query,str) or not query.strip() or not 1 <= limit <= 100: raise OpcTagManagerClientError("OPC Tag search input is invalid.")
        return self._list(f"/api/opc-tags/search?{urlencode({'q':query,'limit':limit,'include_inactive':str(include_inactive).lower()})}","tags")

    def link_resource_relationship(self, source_resource_id: str, target_resource_id: str) -> dict[str, Any]:
        self._logical_id(source_resource_id,("SUP_","EPT_")); self._logical_id(target_resource_id,("MAN_","DWG_","QUO_","DOC_"))
        return self._json_write("/api/resource-relationships/link",{"source_resource_id":source_resource_id,"target_resource_id":target_resource_id})

    def link_tag_resource(self, kepware_path: str, resource_id: str) -> dict[str, Any]:
        parts=kepware_path.split("/")
        if len(parts)<3 or any(not part for part in parts): raise OpcTagManagerClientError("KepwarePath is invalid.")
        self._logical_id(resource_id,("EPT_","MAN_","DWG_","QUO_","DOC_"))
        return self._json_write("/api/tag-resources/link",{"channel":parts[0],"device":parts[1],"group_path":parts[2:-1],"tag_name":parts[-1],"resource_id":resource_id})

    def create_canonical_resource(self, *, resource_type: str, display_name: str, source_sha256: str,
                                  source_document_id: str, original_filename: str, content: bytes,
                                  extraction_run_id: str | None = None, review_id: str | None = None) -> dict[str, Any]:
        if resource_type not in {"Manual","Drawing","Quotation","GeneralDocument"}: raise OpcTagManagerClientError("Canonical Resource type is not allowed.")
        fields={"resource_type":resource_type,"display_name":display_name,"source_sha256":source_sha256,
                "source_document_id":source_document_id,"source_application":"Factory-KM"}
        if extraction_run_id:fields["extraction_run_id"]=extraction_run_id
        if review_id:fields["review_id"]=review_id
        boundary=f"factorykm-{uuid.uuid4().hex}"; body=bytearray()
        for key,value in fields.items(): body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
        safe_name=original_filename.replace('"','')
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{safe_name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode());body.extend(content);body.extend(f"\r\n--{boundary}--\r\n".encode())
        return self._request(Request(f"{self.settings.base_url}/api/integration/resources",data=bytes(body),method="POST",headers={"Accept":"application/json","Content-Type":f"multipart/form-data; boundary={boundary}"}),allow_file_metadata=True)

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

    def _object(self,path:str,key:str)->dict[str,Any]:
        payload=self._request(Request(f"{self.settings.base_url}{path}",method="GET",headers={"Accept":"application/json"}))
        value=payload.get(key)
        if not isinstance(value,dict) or self._contains_physical_path(value):raise OpcTagManagerClientError("OpcTagManager returned an unsafe response.")
        return value

    def _json_write(self,path:str,payload:dict[str,Any])->dict[str,Any]:
        data=json.dumps(payload,separators=(",",":")).encode()
        return self._request(Request(f"{self.settings.base_url}{path}",data=data,method="POST",headers={"Accept":"application/json","Content-Type":"application/json"}),allow_file_metadata=True)

    def _request(self,request:Request,allow_file_metadata:bool=False)->dict[str,Any]:
        try:
            with self._opener(request,timeout=self.settings.timeout_seconds) as response:payload=json.loads(response.read().decode("utf-8"))
        except HTTPError as error:raise OpcTagManagerClientError(f"OpcTagManager returned HTTP {error.code}.",status_code=error.code,retriable=error.code>=500) from error
        except (URLError,TimeoutError,OSError) as error:raise OpcTagManagerClientError("OpcTagManager transport failed.",retriable=True) from error
        except json.JSONDecodeError as error:raise OpcTagManagerClientError("OpcTagManager returned malformed JSON.") from error
        unsafe=self._contains_absolute_path(payload) if allow_file_metadata else self._contains_physical_path(payload)
        if not isinstance(payload,dict) or payload.get("success") is not True or unsafe:raise OpcTagManagerClientError("OpcTagManager returned an unsafe or unsuccessful response.")
        return self._without_file_metadata(payload) if allow_file_metadata else payload

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

    @classmethod
    def _contains_absolute_path(cls,value:Any)->bool:
        if isinstance(value,dict):
            return any(str(key).casefold() in {"filesystem_path","vault_path","absolute_path"} or cls._contains_absolute_path(item) for key,item in value.items())
        if isinstance(value,list):return any(cls._contains_absolute_path(item) for item in value)
        return isinstance(value,str) and (value.startswith("\\\\") or (len(value)>2 and value[1:3] in {":\\",":/"}))

    @classmethod
    def _without_file_metadata(cls,value:Any)->Any:
        if isinstance(value,dict):return {key:cls._without_file_metadata(item) for key,item in value.items() if str(key).casefold() not in {"active_file","filename","original_filename"}}
        if isinstance(value,list):return [cls._without_file_metadata(item) for item in value]
        return value

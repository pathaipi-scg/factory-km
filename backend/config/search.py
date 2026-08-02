"""Environment-backed configuration for the active search strategy."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class SearchSettings:
    """Search strategy settings for Ask-KM."""

    mode: str = "folder"
    pageindex_workspace_path: str = ""
    pageindex_document_id: str = ""
    pageindex_stable_document_id: str = ""
    pageindex_reasoner_endpoint: str = ""
    pageindex_reasoner_model: str = "local-pageindex"
    pageindex_reasoner_timeout_seconds: float = 30.0
    pageindex_reasoner_allowed_hosts: tuple[str, ...] = ()

    @classmethod
    def from_environment(cls) -> "SearchSettings":
        """Create search settings from the process environment."""
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        mode = os.environ.get("KM_SEARCH_MODE", "folder").strip().lower()
        if mode not in {"folder", "pageindex"}:
            raise ValueError("KM_SEARCH_MODE must be 'folder' or 'pageindex'")
        allowed_hosts = tuple(
            host.strip()
            for host in os.environ.get(
                "PAGEINDEX_REASONER_ALLOWED_HOSTS", ""
            ).split(",")
            if host.strip()
        )
        return cls(
            mode=mode,
            pageindex_workspace_path=os.environ.get(
                "PAGEINDEX_WORKSPACE_PATH", ""
            ).strip(),
            pageindex_document_id=os.environ.get(
                "PAGEINDEX_DOCUMENT_ID", ""
            ).strip(),
            pageindex_stable_document_id=os.environ.get(
                "PAGEINDEX_STABLE_DOCUMENT_ID", ""
            ).strip(),
            pageindex_reasoner_endpoint=os.environ.get(
                "PAGEINDEX_REASONER_ENDPOINT", ""
            ).strip(),
            pageindex_reasoner_model=os.environ.get(
                "PAGEINDEX_REASONER_MODEL", "local-pageindex"
            ).strip(),
            pageindex_reasoner_timeout_seconds=float(
                os.environ.get("PAGEINDEX_REASONER_TIMEOUT_SECONDS", "30")
            ),
            pageindex_reasoner_allowed_hosts=allowed_hosts,
        )

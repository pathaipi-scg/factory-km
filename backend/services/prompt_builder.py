"""Compatibility prompt formatting for normalized search results."""

from backend.models.search import SearchResult


class PromptBuilder:
    """Build the legacy Folder Search context expected by the chat flow."""

    @staticmethod
    def build_context(result: SearchResult) -> str:
        """Format normalized hits as the existing Folder Search context."""
        candidates = []
        for index, hit in enumerate(result.hits, start=1):
            metadata = hit.document.metadata
            kind = (
                "สรุป (summary)"
                if metadata.get("kind") == "summary"
                else "เอกสารเทรน (ฉบับเต็ม)"
            )
            header = (
                f"=== เอกสารที่ {index} ===\n"
                f"Source_File: {metadata.get('source_file') or '-'} | "
                f"ประเภท: {kind}\n"
                f"Category: {metadata.get('category') or '-'} | "
                f"Machine: {metadata.get('machine') or '-'} | "
                f"KM_ID: {metadata.get('km_id') or '-'}"
            )
            candidates.append(f"{header}\n\n{hit.document.content}")

        return "\n\n---\n\n".join(candidates)

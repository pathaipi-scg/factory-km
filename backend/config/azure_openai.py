"""Environment-backed configuration for the Azure OpenAI provider."""

from dataclasses import dataclass
import os
from urllib.parse import urlencode


@dataclass(frozen=True)
class AzureOpenAISettings:
    """Connection settings for the Azure OpenAI Responses API."""

    endpoint: str
    api_key: str
    deployment: str
    api_version: str
    timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "AzureOpenAISettings":
        """Create settings from the process environment."""
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        if not endpoint or not api_key:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be configured"
            )

        return cls(
            endpoint=endpoint,
            api_key=api_key,
            deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini"),
            api_version=os.environ.get(
                "AZURE_OPENAI_API_VERSION", "2025-04-01-preview"
            ),
            timeout_seconds=float(os.environ.get("AZURE_OPENAI_TIMEOUT_SECONDS", "60")),
        )

    @property
    def responses_url(self) -> str:
        """Return the configured Azure OpenAI Responses API URL."""
        query = urlencode({"api-version": self.api_version})
        return f"{self.endpoint.rstrip('/')}/openai/responses?{query}"

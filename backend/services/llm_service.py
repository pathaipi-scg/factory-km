"""Provider-agnostic service for generating an LLM answer from context."""

from __future__ import annotations

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.config.azure_openai import AzureOpenAISettings


class LLMProvider(Protocol):
    """Contract implemented by LLM providers."""

    def generate(self, *, context: str, question: str) -> str:
        """Generate text from the supplied context and question."""


class AzureOpenAIError(RuntimeError):
    """Raised when Azure OpenAI cannot provide a usable response."""


class AzureOpenAIProvider:
    """Azure OpenAI Responses API implementation of ``LLMProvider``."""

    def __init__(self, settings: AzureOpenAISettings) -> None:
        self._settings = settings

    def generate(self, *, context: str, question: str) -> str:
        """Call Azure OpenAI and return its generated text."""
        payload = json.dumps(
            {
                "model": self._settings.deployment,
                "input": self._build_input(context=context, question=question),
            }
        ).encode("utf-8")
        request = Request(
            self._settings.responses_url,
            data=payload,
            method="POST",
            headers={
                "api-key": self._settings.api_key,
                "Content-Type": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=self._settings.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise AzureOpenAIError(f"Azure OpenAI returned HTTP {error.code}") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise AzureOpenAIError("Azure OpenAI request failed") from error

        try:
            return response_data["output"][0]["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as error:
            raise AzureOpenAIError("Azure OpenAI response did not contain text") from error

    @staticmethod
    def _build_input(*, context: str, question: str) -> str:
        return (
            "คุณคือ KM Assistant ของโรงงาน\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION:\n{question}\n\n"
            "กติกา:\n"
            "- ใช้ข้อมูลจาก CONTEXT เท่านั้น\n"
            "- ถ้าไม่มีข้อมูลให้ตอบว่า ไม่พบข้อมูลใน KM"
        )


class LLMService:
    """Delegate context-and-question generation to the configured LLM provider."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or AzureOpenAIProvider(
            AzureOpenAISettings.from_environment()
        )

    def generate(self, *, context: str, question: str) -> str:
        """Return the provider's generated text."""
        return self._provider.generate(context=context, question=question)

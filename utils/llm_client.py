from __future__ import annotations

import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    """Minimal chat-completions client for DeepSeek and compatible APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: int = 60,
    ) -> None:
        load_dotenv()
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")).rstrip("/")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-v4-flash")
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", "10000"))
        self.temperature = (
            temperature
            if temperature is not None
            else float(os.getenv("LLM_TEMPERATURE", "0.2"))
        )
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("LLM_API_KEY or DEEPSEEK_API_KEY is required")

    def create_message(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **extra_body: Any,
    ) -> dict[str, Any]:
        selected_model = model or self.model
        logger.info("Calling LLM model=%s max_tokens=%s", selected_model, max_tokens or self.max_tokens)

        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature if temperature is None else temperature,
            "stream": False,
        }
        payload.update(extra_body)

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def complete_prompt(self, prompt: str, system: str | None = None, **kwargs: Any) -> str:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.create_message(messages=messages, **kwargs)
        return extract_text(response)


def extract_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def get_llm_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient()


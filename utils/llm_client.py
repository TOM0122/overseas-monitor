from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class LLMCompletion:
    text: str
    model: str
    latency_seconds: float
    usage: dict[str, Any] = field(default_factory=dict)
    raw_finish_reason: str | None = None


class OpenAICompatibleClient:
    """Minimal chat-completions client for DeepSeek and compatible APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
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
        self.timeout = timeout if timeout is not None else int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        self.max_retries = max_retries if max_retries is not None else int(os.getenv("LLM_MAX_RETRIES", "1"))
        self.last_completion: LLMCompletion | None = None

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
        if not response.ok:
            # 记录状态码 + response 摘要，绝不打印 API key。
            logger.error(
                "LLM HTTP error status=%s body=%s",
                response.status_code,
                _safe_body(response.text),
            )
            response.raise_for_status()
        return response.json()

    def complete(self, prompt: str, system: str | None = None, **kwargs: Any) -> LLMCompletion:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                response = self.create_message(messages=messages, **kwargs)
            except Exception as exc:  # noqa: BLE001 - retry wrapper
                last_error = exc
                logger.warning("LLM call attempt %s failed: %s", attempt + 1, exc)
                continue
            latency = time.monotonic() - started
            completion = LLMCompletion(
                text=extract_text(response),
                model=response.get("model") or self.model,
                latency_seconds=round(latency, 3),
                usage=response.get("usage") or {},
                raw_finish_reason=_finish_reason(response),
            )
            self.last_completion = completion
            return completion

        assert last_error is not None
        raise last_error

    def complete_prompt(self, prompt: str, system: str | None = None, **kwargs: Any) -> str:
        return self.complete(prompt, system=system, **kwargs).text


def extract_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def _finish_reason(response: dict[str, Any]) -> str | None:
    choices = response.get("choices") or []
    return choices[0].get("finish_reason") if choices else None


def _safe_body(text: str, limit: int = 300) -> str:
    body = (text or "")[:limit]
    return body.replace("\n", " ")


def get_llm_client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient()

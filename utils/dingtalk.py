from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from typing import Any
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class DingTalkWebhookClient:
    """DingTalk custom robot webhook client."""

    def __init__(
        self,
        webhook_url: str | None = None,
        secret: str | None = None,
        timeout: int = 15,
    ) -> None:
        load_dotenv()
        self.webhook_url = webhook_url or os.getenv("DINGTALK_WEBHOOK_URL")
        self.secret = secret if secret is not None else os.getenv("DINGTALK_WEBHOOK_SECRET", "")
        self.timeout = timeout

        if not self.webhook_url:
            raise ValueError("DINGTALK_WEBHOOK_URL is required")

    def send_markdown(self, title: str, markdown: str) -> dict[str, Any]:
        """Send markdown content to a DingTalk group."""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": markdown,
            },
        }
        return self._post(payload)

    def send_text(self, text: str) -> dict[str, Any]:
        """Send a simple text message. Useful for smoke tests."""
        payload = {
            "msgtype": "text",
            "text": {"content": text},
        }
        return self._post(payload)

    def _signed_webhook_url(self) -> str:
        if not self.secret:
            return self.webhook_url

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}".encode("utf-8")
        digest = hmac.new(self.secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
        sign = quote_plus(base64.b64encode(digest).decode("utf-8"))
        separator = "&" if "?" in self.webhook_url else "?"
        return f"{self.webhook_url}{separator}timestamp={timestamp}&sign={sign}"

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        logger.info("Sending message to DingTalk webhook")
        response = requests.post(self._signed_webhook_url(), json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("errcode") not in (None, 0):
            raise RuntimeError(f"DingTalk webhook returned error: {data}")
        return data


def get_dingtalk_client() -> DingTalkWebhookClient:
    return DingTalkWebhookClient()


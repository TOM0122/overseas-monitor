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


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _normalize_markdown(text: str) -> str:
    """钉钉 markdown 轻量归一化：去行尾空白、折叠多余空行、去首尾空行，
    并确保表格块前后各有一个空行（否则钉钉不会把它渲染成表格）。"""
    # 1) 去行尾空白 + 折叠多余空行
    collapsed: list[str] = []
    blank_run = 0
    for line in (raw.rstrip() for raw in text.splitlines()):
        if line == "":
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        collapsed.append(line)
    # 2) 表格块前后补空行（钉钉渲染要求；LLM 常把表格紧贴标题/文字）
    out: list[str] = []
    for line in collapsed:
        prev = out[-1] if out else ""
        if _is_table_line(line) and prev != "" and not _is_table_line(prev):
            out.append("")
        elif line != "" and not _is_table_line(line) and out and _is_table_line(out[-1]):
            out.append("")
        out.append(line)
    return "\n".join(out).strip()


def _truncate_for_dingtalk(text: str, max_bytes: int) -> str:
    """按 UTF-8 字节预算截断，尽量按整行切，并追加截断提示。"""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    notice = "\n\n---\n（内容过长，已截断；完整数据见数据库）"
    budget = max_bytes - len(notice.encode("utf-8"))
    if budget <= 0:
        return notice.strip()
    truncated = encoded[:budget].decode("utf-8", errors="ignore")
    newline = truncated.rfind("\n")
    if newline >= len(truncated) // 2:
        truncated = truncated[:newline]
    return truncated.rstrip() + notice


class DingTalkWebhookClient:
    """DingTalk custom robot webhook client."""

    def __init__(
        self,
        webhook_url: str | None = None,
        secret: str | None = None,
        timeout: int = 15,
        markdown_max_bytes: int | None = None,
    ) -> None:
        load_dotenv()
        self.webhook_url = webhook_url or os.getenv("DINGTALK_WEBHOOK_URL")
        self.secret = secret if secret is not None else os.getenv("DINGTALK_WEBHOOK_SECRET", "")
        self.timeout = timeout
        self.markdown_max_bytes = (
            markdown_max_bytes
            if markdown_max_bytes is not None
            else int(os.getenv("DINGTALK_MARKDOWN_MAX_BYTES", "19000"))
        )

        if not self.webhook_url:
            raise ValueError("DINGTALK_WEBHOOK_URL is required")

    def send_markdown(self, title: str, markdown: str) -> dict[str, Any]:
        """Send markdown content to a DingTalk group.

        返回结构：ok / errcode / errmsg / truncated / original_bytes / final_bytes。
        推送失败不抛异常（由调用方看 ok 决定），便于把结果记进 agent_runs。
        """
        markdown = _normalize_markdown(markdown)
        original_bytes = len(markdown.encode("utf-8"))
        truncated = original_bytes > self.markdown_max_bytes
        if truncated:
            logger.warning(
                "DingTalk markdown %s bytes exceeds limit %s, truncating",
                original_bytes,
                self.markdown_max_bytes,
            )
            markdown = _truncate_for_dingtalk(markdown, self.markdown_max_bytes)
        final_bytes = len(markdown.encode("utf-8"))
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": markdown},
        }
        result = self._post_classified(payload)
        result.update(
            {"truncated": truncated, "original_bytes": original_bytes, "final_bytes": final_bytes}
        )
        return result

    def _post_classified(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(self._signed_webhook_url(), json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.exception("DingTalk send failed")
            return {"ok": False, "errcode": None, "errmsg": str(exc)[:200]}
        errcode = data.get("errcode")
        ok = errcode in (None, 0)
        if not ok:
            # 常见：安全关键词未命中（文案需含「竞品监控」）会返回非 0 errcode。
            logger.error("DingTalk returned errcode=%s errmsg=%s", errcode, data.get("errmsg"))
        return {"ok": ok, "errcode": errcode, "errmsg": data.get("errmsg")}

    def send_text(self, text: str) -> dict[str, Any]:
        """Send a simple text message. Useful for smoke tests."""
        if len(text.encode("utf-8")) > self.markdown_max_bytes:
            logger.warning("DingTalk text exceeds limit, truncating")
            text = _truncate_for_dingtalk(text, self.markdown_max_bytes)
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

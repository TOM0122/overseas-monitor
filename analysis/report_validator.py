"""Deterministic guardrails for the LLM-generated daily report.

The report is pushed to a DingTalk group, so it must be structurally sound and
must not invent URLs or reference data sources that no longer exist (the project
is off-site-only; Keepa / Amazon BSR / Top30 were removed).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

REQUIRED_SECTIONS = ("## 一、总览", "## 二、站外每日发现", "## 三、建议", "## 四、注意")

# 站内监控历史关键词：offsite-only 版本禁止出现（除非它们真的存在于输入 payload）。
FORBIDDEN_ONSITE_KEYWORDS = ("Keepa", "Amazon Best Sellers", "BSR", "Top30")

# 幻觉句式：当前 payload 不含这些维度，出现即可疑。
HALLUCINATION_PHRASES = ("根据历史销量", "站内排名", "Amazon 榜单", "库存")

_MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
_TITLE = re.compile(r"竞品监控日报.*\d{4}-\d{2}-\d{2}")


@dataclass
class ReportValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_report(markdown: str, payload: dict[str, Any]) -> ReportValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not markdown or not markdown.strip():
        return ReportValidationResult(ok=False, errors=["报告为空"])

    for section in REQUIRED_SECTIONS:
        if section not in markdown:
            errors.append(f"缺少必需段落：{section}")

    if not _TITLE.search(markdown):
        errors.append("缺少主标题行（竞品监控日报 · YYYY-MM-DD）")

    max_bytes = int(os.getenv("DINGTALK_MARKDOWN_MAX_BYTES", "19000"))
    n_bytes = len(markdown.encode("utf-8"))
    if n_bytes > max_bytes:
        warnings.append(f"报告 {n_bytes} 字节超过 {max_bytes}，将由钉钉截断处理")

    whitelist = _collect_payload_urls(payload)
    for url in _MARKDOWN_LINK.findall(markdown):
        if not _url_allowed(url, whitelist):
            errors.append(f"出现 payload 之外的链接：{url}")

    lower = markdown.lower()
    payload_text = _payload_text(payload).lower()
    for kw in FORBIDDEN_ONSITE_KEYWORDS:
        if kw.lower() in lower and kw.lower() not in payload_text:
            errors.append(f"出现已停用的站内监控关键词：{kw}")

    for phrase in HALLUCINATION_PHRASES:
        if phrase in markdown and phrase not in payload_text:
            warnings.append(f"疑似幻觉句式：{phrase}")

    return ReportValidationResult(ok=not errors, errors=errors, warnings=warnings)


def _collect_payload_urls(payload: Any) -> set[str]:
    urls: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str) and node.startswith("http"):
            urls.add(_url_core(node))

    walk(payload)
    return urls


def _url_core(url: str) -> str:
    """scheme://host/path，去掉 query/fragment，便于容忍 LLM 缩短链接。"""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")


def _url_allowed(url: str, whitelist: set[str]) -> bool:
    core = _url_core(url)
    # 容忍 LLM 把长链接截短：报告链接是白名单某条的前缀，或反之，都算合法。
    return any(w.startswith(core) or core.startswith(w) for w in whitelist)


def _payload_text(payload: Any) -> str:
    try:
        import json

        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return str(payload)

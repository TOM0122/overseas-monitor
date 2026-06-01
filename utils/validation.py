from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _positive_number(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if num > 0 else None


def _percent(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if 0 <= num <= 100 else None


def _non_negative_int(value: Any) -> int | None:
    try:
        num = int(float(value))
    except (TypeError, ValueError):
        return None
    return num if num >= 0 else None


# 字段 -> 归一化函数。值未通过校验则置为 None（保留该行其它字段）。
_FIELD_RULES: dict[str, Callable[[Any], Any]] = {
    "price": _positive_number,
    "original_price": _positive_number,
    "buy_box_price": _positive_number,
    "discount_pct": _percent,
    "thumbs_up": _non_negative_int,
    "comments_count": _non_negative_int,
    "review_count": _non_negative_int,
    "bsr": _non_negative_int,
    "rank": _non_negative_int,
}


def sanitize_rows(
    table: str,
    rows: list[dict[str, Any]],
    key_fields: list[str],
) -> list[dict[str, Any]]:
    """入库前校验：丢弃缺主键的行；把不合理数值字段置为 None。

    每表打印一行数据质量摘要，便于在 Railway 日志中巡检。
    """
    clean: list[dict[str, Any]] = []
    dropped = 0
    nulled: dict[str, int] = {}
    for row in rows:
        if any(row.get(k) in (None, "") for k in key_fields):
            dropped += 1
            continue
        for field_name, rule in _FIELD_RULES.items():
            if field_name not in row or row[field_name] is None:
                continue
            coerced = rule(row[field_name])
            if coerced is None:
                nulled[field_name] = nulled.get(field_name, 0) + 1
            row[field_name] = coerced
        clean.append(row)

    if dropped or nulled:
        logger.warning(
            "Data quality [%s]: kept=%s dropped_missing_key=%s nulled_fields=%s",
            table, len(clean), dropped, nulled,
        )
    else:
        logger.info("Data quality [%s]: kept=%s, no issues", table, len(clean))
    return clean

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class QualityMetric:
    name: str
    current: int
    baseline_avg: float
    baseline_days: int
    minimum_expected: int


def build_data_quality_alerts(
    *,
    report_date: date,
    tz: ZoneInfo,
    today_offsite: list[dict[str, Any]],
    history_offsite: list[dict[str, Any]],
    drop_ratio: float = 0.4,
) -> list[str]:
    """Return deterministic data-quality alerts for source volume drops.

    A metric alerts only when today's value is both below its absolute minimum and
    below the configured fraction of the historical daily average.
    """
    metrics = build_quality_metrics(
        report_date=report_date,
        tz=tz,
        today_offsite=today_offsite,
        history_offsite=history_offsite,
    )
    alerts = []
    for metric in metrics:
        if should_alert(metric, drop_ratio=drop_ratio):
            alerts.append(
                (
                    f"{metric.name}: 今日 {metric.current}，"
                    f"{metric.baseline_days}日均值 {metric.baseline_avg:.1f}，"
                    f"低于阈值 {drop_ratio:.0%}"
                )
            )
    alerts.extend(build_ratio_alerts(today_offsite, history_offsite))
    return alerts


def build_ratio_alerts(
    today_offsite: list[dict[str, Any]],
    history_offsite: list[dict[str, Any]],
) -> list[str]:
    """比例型 / 新鲜度 / 相似度告警。刻意保守，避免低流量日误报。"""
    alerts: list[str] = []
    min_sample = int(os.getenv("DATA_QUALITY_MIN_SAMPLE", "10"))
    unknown_ratio_max = float(os.getenv("DATA_QUALITY_UNKNOWN_BRAND_RATIO", "0.85"))
    null_price_ratio_max = float(os.getenv("DATA_QUALITY_NULL_PRICE_RATIO", "0.7"))
    dup_ratio_max = float(os.getenv("DATA_QUALITY_DUP_RATIO", "0.3"))
    title_unique_min = float(os.getenv("DATA_QUALITY_TITLE_UNIQUE_MIN_RATIO", "0.5"))

    sources = sorted({row.get("source") or "slickdeals" for row in today_offsite})
    for source in sources:
        rows = [r for r in today_offsite if (r.get("source") or "slickdeals") == source]
        n = len(rows)
        if n < min_sample:
            continue  # 样本太少，比例不稳，跳过避免误报

        unknown = sum(1 for r in rows if not (clean_value(r.get("brand")) and clean_value(r.get("brand")) != "unknown"))
        if unknown / n > unknown_ratio_max:
            alerts.append(f"{source} unknown 品牌比例 {unknown / n:.0%}（{unknown}/{n}）异常偏高，疑似品牌解析退化")

        null_price = sum(1 for r in rows if _price_or_none(r.get("price")) is None)
        if null_price / n > null_price_ratio_max:
            alerts.append(f"{source} 价格缺失比例 {null_price / n:.0%}（{null_price}/{n}）异常偏高")

        keys = [str(r.get("deal_id") or r.get("url") or "") for r in rows if (r.get("deal_id") or r.get("url"))]
        dup = len(keys) - len(set(keys))
        if keys and dup / len(keys) > dup_ratio_max:
            alerts.append(f"{source} 重复 Deal 比例 {dup / len(keys):.0%}（{dup}/{len(keys)}）异常偏高")

        top = [clean_value(r.get("title")) for r in rows[:20] if clean_value(r.get("title"))]
        if len(top) >= min_sample and len(set(top)) / len(top) < title_unique_min:
            alerts.append(
                f"{source} 前 {len(top)} 条标题唯一率仅 {len(set(top)) / len(top):.0%}，疑似 parser 抓错区域"
            )

    # source freshness：历史有数据但今天完全没有。
    history_sources = {row.get("source") or "slickdeals" for row in history_offsite}
    today_sources = {row.get("source") or "slickdeals" for row in today_offsite}
    for source in sorted(history_sources - today_sources):
        alerts.append(f"{source} 今日 0 条数据，但历史有数据，疑似抓取失败")
    return alerts


def _price_or_none(value: Any) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def build_quality_metrics(
    *,
    report_date: date,
    tz: ZoneInfo,
    today_offsite: list[dict[str, Any]],
    history_offsite: list[dict[str, Any]],
) -> list[QualityMetric]:
    sources = sorted({row.get("source") or "slickdeals" for row in today_offsite + history_offsite})
    metrics: list[QualityMetric] = []
    for window_days in (7, 14):
        for source in sources:
            today_source = [row for row in today_offsite if (row.get("source") or "slickdeals") == source]
            history_source = [row for row in history_offsite if (row.get("source") or "slickdeals") == source]
            metrics.extend(
                [
                    QualityMetric(
                        name=f"{source} Deal 数",
                        current=len(today_source),
                        baseline_avg=average_daily_count(history_source, "scraped_at", report_date, tz, days=window_days),
                        baseline_days=window_days,
                        minimum_expected=2 if source == "slickdeals" else 1,
                    ),
                    QualityMetric(
                        name=f"{source} 品牌数",
                        current=count_known_brands(today_source),
                        baseline_avg=average_daily_distinct(
                            history_source,
                            "scraped_at",
                            "brand",
                            report_date,
                            tz,
                            days=window_days,
                        ),
                        baseline_days=window_days,
                        minimum_expected=1,
                    ),
                    QualityMetric(
                        name=f"{source} 有效价格数",
                        current=count_positive_prices(today_source),
                        baseline_avg=average_daily_positive_price_count(
                            history_source,
                            "scraped_at",
                            report_date,
                            tz,
                            days=window_days,
                        ),
                        baseline_days=window_days,
                        minimum_expected=1,
                    ),
                ]
            )
    return metrics


def should_alert(metric: QualityMetric, *, drop_ratio: float) -> bool:
    if metric.baseline_avg <= 0:
        return False
    return metric.current < metric.minimum_expected and metric.current < metric.baseline_avg * drop_ratio


def average_daily_count(
    rows: Iterable[dict[str, Any]],
    timestamp_field: str,
    report_date: date,
    tz: ZoneInfo,
    *,
    days: int = 14,
) -> float:
    buckets = daily_buckets(rows, timestamp_field, report_date, tz, days=days)
    return round(sum(len(items) for items in buckets.values()) / days, 4)


def average_daily_distinct(
    rows: Iterable[dict[str, Any]],
    timestamp_field: str,
    value_field: str,
    report_date: date,
    tz: ZoneInfo,
    *,
    days: int = 14,
) -> float:
    buckets = daily_buckets(rows, timestamp_field, report_date, tz, days=days)
    total = 0
    for items in buckets.values():
        total += len({clean_value(item.get(value_field)) for item in items if clean_value(item.get(value_field))})
    return round(total / days, 4)


def average_daily_positive_price_count(
    rows: Iterable[dict[str, Any]],
    timestamp_field: str,
    report_date: date,
    tz: ZoneInfo,
    *,
    days: int = 14,
) -> float:
    buckets = daily_buckets(rows, timestamp_field, report_date, tz, days=days)
    return round(sum(count_positive_prices(items) for items in buckets.values()) / days, 4)


def daily_buckets(
    rows: Iterable[dict[str, Any]],
    timestamp_field: str,
    report_date: date,
    tz: ZoneInfo,
    *,
    days: int,
) -> dict[date, list[dict[str, Any]]]:
    start_day = report_date - timedelta(days=days)
    buckets = {start_day + timedelta(days=offset): [] for offset in range(days)}
    for row in rows:
        local_day = local_date(row.get(timestamp_field), tz)
        if local_day in buckets:
            buckets[local_day].append(row)
    return buckets


def local_date(value: Any, tz: ZoneInfo) -> date | None:
    parsed = parse_datetime(value)
    return parsed.astimezone(tz).date() if parsed else None


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def count_known_brands(rows: Iterable[dict[str, Any]]) -> int:
    return len({brand for row in rows if (brand := clean_value(row.get("brand"))) and brand != "unknown"})


def count_positive_prices(rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        try:
            price = float(row.get("price"))
        except (TypeError, ValueError):
            continue
        if price > 0:
            count += 1
    return count


def clean_value(value: Any) -> str:
    return str(value or "").strip().lower()

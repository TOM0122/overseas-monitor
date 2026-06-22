from __future__ import annotations

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
    return alerts


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

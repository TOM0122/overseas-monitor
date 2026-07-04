from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from analysis import analyzer
from scrapers import hip2save_scraper, slickdeals_scraper
from utils.data_quality import build_data_quality_alerts
from utils.db import get_repository
from utils.dingtalk import get_dingtalk_client
from utils.run_tracker import RunTracker

# 这些步骤若成功但返回 0 条记录，视为异常并告警。
CRITICAL_EMPTY_STEPS = {"slickdeals_scraper"}


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    count: int | None = None
    duration_seconds: float | None = None
    partial: bool = False
    partial_reason: str | None = None


def configure_logging() -> None:
    load_dotenv()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


def run_step(name: str, func: Callable[[], Any], *, run_id: str) -> StepResult:
    logger = logging.getLogger(__name__)
    logger.info("run=%s Starting step: %s", run_id, name)
    started = time.monotonic()
    try:
        result = func()
        duration = time.monotonic() - started
        count = len(result) if isinstance(result, list) else None
        partial = bool(getattr(result, "partial", False))
        partial_reason = getattr(result, "partial_reason", None)
        detail = f"{count} records" if count is not None else "completed"
        logger.info("run=%s Finished step: %s (%s, %.1fs)", run_id, name, detail, duration)
        return StepResult(
            name=name, ok=True, detail=detail, count=count,
            duration_seconds=duration, partial=partial, partial_reason=partial_reason,
        )
    except Exception as exc:
        duration = time.monotonic() - started
        logger.exception("run=%s Step failed: %s", run_id, name)
        return StepResult(name=name, ok=False, detail=str(exc), count=None, duration_seconds=duration)


def send_pipeline_alert(
    failed: list[StepResult],
    empty_critical: list[StepResult],
    summary: str,
    data_quality_alerts: list[str] | None = None,
) -> None:
    logger = logging.getLogger(__name__)
    # 注意：文本需包含钉钉机器人「自定义关键词」安全设置允许的词（与日报一致，如「竞品监控」），否则会被钉钉拦截。
    lines = ["竞品监控 Pipeline 告警", ""]
    if failed:
        lines.append("失败步骤：")
        lines += [f"- {r.name}: {r.detail}" for r in failed]
    if empty_critical:
        lines.append("关键步骤 0 条数据：")
        lines += [f"- {r.name}" for r in empty_critical]
    if data_quality_alerts:
        lines.append("数据质量异常：")
        lines += [f"- {alert}" for alert in data_quality_alerts]
    lines += ["", f"汇总：{summary}"]
    try:
        get_dingtalk_client().send_text("\n".join(lines))
        logger.info("Sent pipeline alert to DingTalk")
    except Exception:
        # 告警失败不能再让进程崩溃，记录即可。
        logger.exception("Failed to send pipeline alert to DingTalk")


def collect_data_quality_alerts() -> list[str]:
    load_dotenv()
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Shanghai"))
    report_date = datetime.now(tz).date()
    today_start_utc, today_end_utc = analyzer.local_day_bounds_utc(report_date, tz)
    history_start_utc = today_start_utc - timedelta(days=14)
    offsite_category = os.getenv("ANALYSIS_OFFSITE_CATEGORY", "fan")
    drop_ratio = float(os.getenv("DATA_QUALITY_DROP_RATIO", "0.4"))

    repository = get_repository()
    today_offsite = repository.fetch_slickdeals_deals_between(
        today_start_utc,
        today_end_utc,
        category=offsite_category,
    )
    history_offsite = repository.fetch_slickdeals_deals_between(
        history_start_utc,
        today_start_utc,
        category=offsite_category,
    )
    return build_data_quality_alerts(
        report_date=report_date,
        tz=tz,
        today_offsite=today_offsite,
        history_offsite=history_offsite,
        drop_ratio=drop_ratio,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run overseas monitor daily pipeline")
    parser.add_argument("--slickdeals-limit", type=int, default=20, help="Max deals per keyword")
    parser.add_argument("--skip-slickdeals", action="store_true", help="Skip Slickdeals scraping")
    parser.add_argument("--skip-hip2save", action="store_true", help="Skip hip2save scraping")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip report generation and push")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run steps in dry-run mode where supported; no database writes or DingTalk push",
    )
    return parser.parse_args()


def build_run_tracker(dry_run: bool) -> RunTracker:
    """dry-run 或建库失败时，tracker 自动降级为内存记录，不影响主流程。"""
    logger = logging.getLogger(__name__)
    tz_name = os.getenv("TIMEZONE", "Asia/Shanghai")
    report_date = datetime.now(ZoneInfo(tz_name)).date().isoformat()
    repository = None
    if not dry_run:
        try:
            repository = get_repository()
        except Exception:
            logger.exception("Repository unavailable; agent run will not be persisted")
    return RunTracker(
        repository=repository,
        trigger_type=os.getenv("RUN_TRIGGER_TYPE", "cron"),
        timezone_name=tz_name,
        report_date=report_date,
        enabled=not dry_run,
    )


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    args = parse_args()

    if args.slickdeals_limit <= 0:
        raise ValueError("--slickdeals-limit must be greater than 0")

    tracker = build_run_tracker(args.dry_run)
    tracker.start()
    logger.info("Agent run started run=%s dry_run=%s", tracker.run_id, args.dry_run)

    results: list[StepResult] = []
    steps: list[tuple[str, bool, Callable[[], Any]]] = [
        (
            "slickdeals_scraper",
            args.skip_slickdeals,
            lambda: slickdeals_scraper.run(limit=args.slickdeals_limit, dry_run=args.dry_run),
        ),
        (
            "hip2save_scraper",
            args.skip_hip2save,
            lambda: hip2save_scraper.run(limit=args.slickdeals_limit, dry_run=args.dry_run),
        ),
        (
            "daily_analyzer",
            args.skip_analysis,
            lambda: analyzer.run(dry_run=args.dry_run, no_push=args.dry_run),
        ),
    ]

    for name, skipped, func in steps:
        if skipped:
            tracker.record_step(name, status="skipped")
            logger.info("run=%s Skipping step: %s", tracker.run_id, name)
            continue
        step = run_step(name, func, run_id=tracker.run_id)
        results.append(step)
        tracker.record_step(
            name,
            status="ok" if step.ok else "failed",
            count=step.count,
            duration_seconds=step.duration_seconds,
            error=None if step.ok else step.detail,
            partial=step.partial,
            partial_reason=step.partial_reason,
        )

    summary = ", ".join(
        f"{r.name}={'ok' if r.ok else 'failed'} ({r.detail})" for r in results
    ) or "no steps selected"
    logger.info("run=%s Pipeline summary: %s", tracker.run_id, summary)

    failed = [r for r in results if not r.ok]
    empty_critical = [r for r in results if r.ok and r.name in CRITICAL_EMPTY_STEPS and r.count == 0]
    data_quality_alerts: list[str] = []

    # dry-run 不告警（无写库无推送）。
    if not args.dry_run:
        try:
            data_quality_alerts = collect_data_quality_alerts()
        except Exception:
            logger.exception("Failed to collect data quality alerts")
        if failed or empty_critical or data_quality_alerts:
            send_pipeline_alert(failed, empty_critical, summary, data_quality_alerts)

    tracker.record_quality_alerts(data_quality_alerts)
    status = tracker.finish()
    logger.info("Agent run finished run=%s status=%s", tracker.run_id, status)

    if empty_critical:
        logger.warning("Critical steps returned 0 records: %s", [r.name for r in empty_critical])
    if data_quality_alerts:
        logger.warning("Data quality alerts: %s", data_quality_alerts)
    if failed:
        logger.error("Pipeline finished with %s failed step(s)", len(failed))
        if not args.dry_run:
            sys.exit(1)


if __name__ == "__main__":
    main()

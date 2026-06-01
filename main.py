from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from analysis import analyzer
from scrapers import amazon_bestseller_scraper, hip2save_scraper, keepa_fetcher, slickdeals_scraper
from utils.dingtalk import get_dingtalk_client

# 这些步骤若成功但返回 0 条记录，视为异常并告警。
CRITICAL_EMPTY_STEPS = {"slickdeals_scraper", "keepa_fetcher", "amazon_bestseller_scraper"}


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    count: int | None = None


def configure_logging() -> None:
    load_dotenv()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


def run_step(name: str, func: Callable[[], Any]) -> StepResult:
    logger = logging.getLogger(__name__)
    logger.info("Starting step: %s", name)
    try:
        result = func()
        count = len(result) if isinstance(result, list) else None
        detail = f"{count} records" if count is not None else "completed"
        logger.info("Finished step: %s (%s)", name, detail)
        return StepResult(name=name, ok=True, detail=detail, count=count)
    except Exception as exc:
        logger.exception("Step failed: %s", name)
        return StepResult(name=name, ok=False, detail=str(exc), count=None)


def send_pipeline_alert(
    failed: list[StepResult],
    empty_critical: list[StepResult],
    summary: str,
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
    lines += ["", f"汇总：{summary}"]
    try:
        get_dingtalk_client().send_text("\n".join(lines))
        logger.info("Sent pipeline alert to DingTalk")
    except Exception:
        # 告警失败不能再让进程崩溃，记录即可。
        logger.exception("Failed to send pipeline alert to DingTalk")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run overseas monitor daily pipeline")
    parser.add_argument("--slickdeals-limit", type=int, default=20, help="Max deals per keyword")
    parser.add_argument("--skip-slickdeals", action="store_true", help="Skip Slickdeals scraping")
    parser.add_argument("--skip-hip2save", action="store_true", help="Skip hip2save scraping")
    parser.add_argument("--skip-keepa", action="store_true", help="Skip Keepa fetching")
    parser.add_argument("--skip-bestsellers", action="store_true", help="Skip Amazon best-seller ranking fetch")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip report generation and push")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run steps in dry-run mode where supported; no database writes or DingTalk push",
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    args = parse_args()

    if args.slickdeals_limit <= 0:
        raise ValueError("--slickdeals-limit must be greater than 0")

    results: list[StepResult] = []

    if not args.skip_slickdeals:
        results.append(
            run_step(
                "slickdeals_scraper",
                lambda: slickdeals_scraper.run(
                    limit=args.slickdeals_limit,
                    dry_run=args.dry_run,
                ),
            )
        )

    if not args.skip_hip2save:
        results.append(
            run_step(
                "hip2save_scraper",
                lambda: hip2save_scraper.run(
                    limit=args.slickdeals_limit,
                    dry_run=args.dry_run,
                ),
            )
        )

    if not args.skip_keepa:
        results.append(
            run_step(
                "keepa_fetcher",
                lambda: keepa_fetcher.run(dry_run=args.dry_run),
            )
        )

    if not args.skip_bestsellers:
        results.append(
            run_step(
                "amazon_bestseller_scraper",
                lambda: amazon_bestseller_scraper.run(dry_run=args.dry_run),
            )
        )

    if not args.skip_analysis:
        results.append(
            run_step(
                "daily_analyzer",
                lambda: analyzer.run(
                    dry_run=args.dry_run,
                    no_push=args.dry_run,
                ),
            )
        )

    summary = ", ".join(
        f"{r.name}={'ok' if r.ok else 'failed'} ({r.detail})" for r in results
    ) or "no steps selected"
    logger.info("Pipeline summary: %s", summary)

    failed = [r for r in results if not r.ok]
    empty_critical = [r for r in results if r.ok and r.name in CRITICAL_EMPTY_STEPS and r.count == 0]

    # dry-run 不告警（无写库无推送）。
    if not args.dry_run and (failed or empty_critical):
        send_pipeline_alert(failed, empty_critical, summary)

    if empty_critical:
        logger.warning("Critical steps returned 0 records: %s", [r.name for r in empty_critical])
    if failed:
        logger.error("Pipeline finished with %s failed step(s)", len(failed))
        if not args.dry_run:
            sys.exit(1)


if __name__ == "__main__":
    main()

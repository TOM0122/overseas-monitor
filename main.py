from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from analysis import analyzer
from scrapers import hip2save_scraper, keepa_fetcher, slickdeals_scraper


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""


def configure_logging() -> None:
    load_dotenv()
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def run_step(name: str, func: Callable[[], Any]) -> StepResult:
    logger = logging.getLogger(__name__)
    logger.info("Starting step: %s", name)
    try:
        result = func()
        count = len(result) if isinstance(result, list) else None
        detail = f"{count} records" if count is not None else "completed"
        logger.info("Finished step: %s (%s)", name, detail)
        return StepResult(name=name, ok=True, detail=detail)
    except Exception as exc:
        logger.exception("Step failed: %s", name)
        return StepResult(name=name, ok=False, detail=str(exc))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run overseas monitor daily pipeline")
    parser.add_argument("--slickdeals-limit", type=int, default=20, help="Max deals per keyword")
    parser.add_argument("--skip-slickdeals", action="store_true", help="Skip Slickdeals scraping")
    parser.add_argument("--skip-hip2save", action="store_true", help="Skip hip2save scraping")
    parser.add_argument("--skip-keepa", action="store_true", help="Skip Keepa fetching")
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

    failed = [result for result in results if not result.ok]
    logger.info(
        "Pipeline summary: %s",
        ", ".join(
            f"{result.name}={'ok' if result.ok else 'failed'} ({result.detail})"
            for result in results
        )
        or "no steps selected",
    )
    if failed:
        logger.error("Pipeline finished with %s failed step(s)", len(failed))


if __name__ == "__main__":
    main()

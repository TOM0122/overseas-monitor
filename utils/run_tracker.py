from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StepRecord:
    name: str
    status: str  # "ok" / "failed" / "skipped"
    count: int | None = None
    duration_seconds: float | None = None
    error: str | None = None
    partial: bool = False
    partial_reason: str | None = None


class RunTracker:
    """把一次 pipeline 运行持久化到 agent_runs 表。

    追踪层绝不能拖垮业务：任何 DB 失败只记日志并降级为内存记录。
    dry-run 时 enabled=False，完全不触库。
    """

    def __init__(
        self,
        *,
        repository: Any = None,
        trigger_type: str = "cron",
        timezone_name: str | None = None,
        report_date: str | None = None,
        enabled: bool = True,
    ) -> None:
        self.run_id = str(uuid.uuid4())
        self._repository = repository
        self.enabled = bool(enabled and repository is not None)
        self.trigger_type = trigger_type
        self.timezone_name = timezone_name
        self.report_date = report_date
        self.steps: list[StepRecord] = []
        self.quality_alerts: list[str] = []
        self.source_counts: dict[str, Any] = {}
        self.llm_info: dict[str, Any] = {}
        self.push_result: dict[str, Any] = {}
        self.report_markdown: str | None = None
        self.status = "running"

    # ---- lifecycle -------------------------------------------------

    def start(self) -> None:
        self._persist(
            {
                "id": self.run_id,
                "started_at": _utcnow(),
                "status": "running",
                "trigger_type": self.trigger_type,
                "timezone": self.timezone_name,
                "report_date": self.report_date,
            },
            insert=True,
        )

    def finish(self, *, error_summary: str | None = None) -> str:
        ok = [s for s in self.steps if s.status == "ok"]
        failed = [s for s in self.steps if s.status == "failed"]
        if failed and ok:
            self.status = "partial_success"
        elif failed:
            self.status = "failed"
        else:
            self.status = "success"
        if error_summary is None and failed:
            error_summary = "; ".join(f"{s.name}: {s.error}" for s in failed)[:1000]
        self._persist(
            {
                "ended_at": _utcnow(),
                "status": self.status,
                "step_results": [asdict(s) for s in self.steps],
                "source_counts": self.source_counts,
                "quality_alerts": self.quality_alerts,
                "llm_info": self.llm_info,
                "report_markdown": self.report_markdown,
                "push_result": self.push_result,
                "error_summary": error_summary,
            }
        )
        return self.status

    # ---- recorders --------------------------------------------------

    def record_step(
        self,
        name: str,
        *,
        status: str,
        count: int | None = None,
        duration_seconds: float | None = None,
        error: str | None = None,
        partial: bool = False,
        partial_reason: str | None = None,
    ) -> None:
        self.steps.append(
            StepRecord(
                name=name,
                status=status,
                count=count,
                duration_seconds=round(duration_seconds, 3) if duration_seconds is not None else None,
                error=error,
                partial=partial,
                partial_reason=partial_reason,
            )
        )
        if count is not None:
            self.source_counts[name] = count

    def record_quality_alerts(self, alerts: list[str]) -> None:
        self.quality_alerts = list(alerts or [])

    def record_llm_info(self, **info: Any) -> None:
        self.llm_info.update({k: v for k, v in info.items() if v is not None})

    def record_push_result(self, result: dict[str, Any]) -> None:
        self.push_result = dict(result or {})

    def set_report_markdown(self, markdown: str | None) -> None:
        self.report_markdown = markdown

    # ---- persistence -------------------------------------------------

    def _persist(self, values: dict[str, Any], *, insert: bool = False) -> None:
        if not self.enabled:
            return
        try:
            if insert:
                self._repository.insert_agent_run(values)
            else:
                self._repository.update_agent_run(self.run_id, values)
        except Exception:
            logger.exception("Run tracker persistence failed (run continues unaffected)")
            # 首次写入就失败说明表/权限有问题，后续不再重试打日志刷屏。
            if insert:
                self.enabled = False


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

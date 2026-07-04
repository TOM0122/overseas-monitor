from __future__ import annotations

from utils.run_tracker import RunTracker


class FakeRepo:
    def __init__(self, fail: bool = False):
        self.inserted: list[dict] = []
        self.updated: list[tuple[str, dict]] = []
        self.fail = fail

    def insert_agent_run(self, row):
        if self.fail:
            raise RuntimeError("db down")
        self.inserted.append(row)
        return [row]

    def update_agent_run(self, run_id, values):
        if self.fail:
            raise RuntimeError("db down")
        self.updated.append((run_id, values))
        return [values]


def test_tracker_success_flow_persists():
    repo = FakeRepo()
    t = RunTracker(repository=repo, report_date="2026-06-08")
    t.start()
    t.record_step("slickdeals_scraper", status="ok", count=12, duration_seconds=1.2)
    t.record_step("hip2save_scraper", status="ok", count=3, duration_seconds=0.5)
    t.record_step("daily_analyzer", status="ok")
    status = t.finish()
    assert status == "success"
    assert len(repo.inserted) == 1 and repo.inserted[0]["id"] == t.run_id
    last = repo.updated[-1][1]
    assert last["status"] == "success"
    assert last["source_counts"] == {"slickdeals_scraper": 12, "hip2save_scraper": 3}
    assert len(last["step_results"]) == 3


def test_tracker_partial_success_when_one_step_failed():
    t = RunTracker(repository=FakeRepo(), report_date="2026-06-08")
    t.start()
    t.record_step("slickdeals_scraper", status="failed", error="403")
    t.record_step("daily_analyzer", status="ok")
    assert t.finish() == "partial_success"


def test_tracker_all_failed_status():
    t = RunTracker(repository=FakeRepo(), report_date="2026-06-08")
    t.start()
    t.record_step("slickdeals_scraper", status="failed", error="boom")
    assert t.finish() == "failed"


def test_tracker_db_failure_does_not_raise():
    # DB 挂掉时追踪必须静默降级，绝不能拖垮主流程
    t = RunTracker(repository=FakeRepo(fail=True), report_date="2026-06-08")
    t.start()
    t.record_step("daily_analyzer", status="ok")
    assert t.finish() == "success"  # 状态仍在内存里算出，只是没写库


def test_tracker_disabled_when_no_repo():
    t = RunTracker(repository=None, enabled=True)
    assert t.enabled is False
    t.start()
    t.record_step("x", status="ok")
    assert t.finish() == "success"

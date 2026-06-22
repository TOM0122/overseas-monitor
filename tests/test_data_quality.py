from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from utils.data_quality import build_data_quality_alerts, should_alert, QualityMetric


TZ = ZoneInfo("Asia/Shanghai")


def row(day: date, **values):
    local_time = datetime.combine(day, datetime.min.time(), tzinfo=TZ)
    return {"scraped_at": local_time.astimezone(timezone.utc).isoformat(), **values}


def test_should_alert_requires_absolute_and_relative_drop():
    assert should_alert(
        QualityMetric("x", current=0, baseline_avg=10.0, baseline_days=14, minimum_expected=1),
        drop_ratio=0.4,
    )
    assert not should_alert(
        QualityMetric("x", current=3, baseline_avg=10.0, baseline_days=14, minimum_expected=1),
        drop_ratio=0.4,
    )
    assert not should_alert(
        QualityMetric("x", current=0, baseline_avg=0.0, baseline_days=14, minimum_expected=1),
        drop_ratio=0.4,
    )


def test_build_data_quality_alerts_detects_offsite_source_drops():
    report_date = date(2026, 6, 5)
    history_days = [report_date - timedelta(days=i) for i in range(1, 15)]
    history_offsite = []
    for day in history_days:
        history_offsite.extend(
            [
                row(day, source="slickdeals", brand="Gaiatop", price=9.99),
                row(day, source="slickdeals", brand="Diveblues", price=12.99),
                row(day, source="hip2save", brand="Shark", price=11.99),
            ]
        )

    alerts = build_data_quality_alerts(
        report_date=report_date,
        tz=TZ,
        today_offsite=[],
        history_offsite=history_offsite,
    )

    assert any("slickdeals Deal 数" in alert for alert in alerts)
    assert any("hip2save Deal 数" in alert for alert in alerts)
    assert any("slickdeals 品牌数" in alert for alert in alerts)
    assert any("hip2save 有效价格数" in alert for alert in alerts)
    assert all("行数" not in alert for alert in alerts)

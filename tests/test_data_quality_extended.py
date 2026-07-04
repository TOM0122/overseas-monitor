from __future__ import annotations

from utils.data_quality import build_ratio_alerts


def _deals(n, *, brand="Gaiatop", price=9.99, title=None, source="slickdeals", url_prefix="u"):
    return [
        {
            "source": source,
            "brand": brand,
            "price": price,
            "title": title or f"Portable Fan {i}",
            "deal_id": f"{source}:{url_prefix}{i}",
            "url": f"https://x/{url_prefix}{i}",
        }
        for i in range(n)
    ]


def _has(alerts, needle):
    return any(needle in a for a in alerts)


def test_unknown_brand_ratio_triggers():
    rows = _deals(12, brand="unknown")
    assert _has(build_ratio_alerts(rows, []), "unknown 品牌比例")


def test_unknown_brand_ratio_ok():
    rows = _deals(12, brand="Gaiatop")
    assert not _has(build_ratio_alerts(rows, []), "unknown 品牌比例")


def test_null_price_ratio_triggers():
    rows = _deals(12, price=None)
    assert _has(build_ratio_alerts(rows, []), "价格缺失比例")


def test_null_price_ratio_ok():
    assert not _has(build_ratio_alerts(_deals(12, price=9.99), []), "价格缺失比例")


def test_duplicate_ratio_triggers():
    rows = _deals(12)
    for r in rows:  # 全部同一个 deal_id -> 高重复
        r["deal_id"] = "slickdeals:dup"
        r["url"] = "https://x/dup"
    assert _has(build_ratio_alerts(rows, []), "重复 Deal 比例")


def test_duplicate_ratio_ok():
    assert not _has(build_ratio_alerts(_deals(12), []), "重复 Deal 比例")


def test_title_similarity_triggers():
    rows = _deals(12, title="Same Portable Fan")  # 所有标题相同
    assert _has(build_ratio_alerts(rows, []), "标题唯一率")


def test_title_similarity_ok():
    assert not _has(build_ratio_alerts(_deals(12), []), "标题唯一率")


def test_source_freshness_triggers():
    history = _deals(5, source="hip2save")
    today = _deals(12, source="slickdeals")  # hip2save 今天 0 条
    assert _has(build_ratio_alerts(today, history), "hip2save 今日 0 条")


def test_low_sample_does_not_trigger():
    # 样本 < min_sample 时比例检查跳过，避免误报
    rows = _deals(3, brand="unknown", price=None)
    assert build_ratio_alerts(rows, []) == []

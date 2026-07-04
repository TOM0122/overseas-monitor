from __future__ import annotations

from analysis.insights import build_insights


def _payload(**over):
    base = {
        "focus_brand": "Diveblues",
        "trends": {
            "focus_weekly": {"brand": "Diveblues", "deal_count": 2, "min_price": 8.5, "max_discount": 50.0},
            "competitor_weekly": [
                {"brand": "Gaiatop", "deal_count": 5, "min_price": 6.79, "max_discount": 51.0},
                {"brand": "Shark", "deal_count": 1, "min_price": 55.0, "max_discount": 23.0},
            ],
        },
        "competitor_candidates": [{"brand": "Vornado", "heat_score": 300}],
        "offsite": {
            "price_range": {"lowest_price_deal": {"brand": "Gaiatop", "price": 6.79}},
            "slickdeals_competitor_deals": [
                {"brand": "Gaiatop", "price": 6.79, "is_frontpage": True, "thumbs_up": 40, "comments_count": 10},
                {"brand": "Shark", "price": 55.0, "is_frontpage": False, "thumbs_up": 5, "comments_count": 1},
            ],
            "hip2save_competitor_deals": [],
        },
    }
    base.update(over)
    return base


def test_top_heat_and_lowest_and_frontpage():
    ins = build_insights(_payload())
    assert ins["top_heat_deal"]["brand"] == "Gaiatop"  # frontpage + high thumbs
    assert ins["lowest_price_deal"]["price"] == 6.79
    assert len(ins["frontpage_deals"]) == 1


def test_suggestion_competitor_more_active():
    ins = build_insights(_payload())
    joined = " ".join(ins["suggestion_candidates"])
    assert "铺 Deal 频率高于自有品牌" in joined
    assert "Gaiatop" in joined  # 5 > focus 2


def test_suggestion_frontpage_underpricing():
    ins = build_insights(_payload())
    joined = " ".join(ins["suggestion_candidates"])
    # Gaiatop frontpage $6.79 < focus min $8.5
    assert "跟价或站外 Deal 补位" in joined


def test_suggestion_new_candidate():
    ins = build_insights(_payload())
    joined = " ".join(ins["suggestion_candidates"])
    assert "加入 brand_list" in joined and "Vornado" in joined


def test_no_suggestions_when_focus_dominates_and_no_candidates():
    p = _payload(
        trends={
            "focus_weekly": {"brand": "Diveblues", "deal_count": 9, "min_price": 5.0, "max_discount": 60.0},
            "competitor_weekly": [{"brand": "Shark", "deal_count": 1, "min_price": 55.0, "max_discount": 23.0}],
        },
        competitor_candidates=[],
        offsite={"price_range": {}, "slickdeals_competitor_deals": [], "hip2save_competitor_deals": []},
    )
    assert build_insights(p)["suggestion_candidates"] == []

"""pipeline.versions:三种版本管线的算法行为(分级公式/边界/健壮性)。"""

import pytest
from pipeline.versions import analyze_v0, analyze_v1, analyze_v2


def _seg(**kw):
    base = {"segment_id": "S-01", "name": "测试路", "length_km": 1.0, "lane_count": 2,
            "capacity_per_lane": 1800, "volume": 1800, "speed": 40, "free_flow_speed": 60}
    base.update(kw)
    return base


class TestV0KnownDefects:
    def test_saturation_ignores_lane_count_and_rounds(self):
        out = analyze_v0([_seg(volume=3000)])  # 正确 V/C = 3000/3600 = 0.83
        assert out["segments"][0]["saturation"] == round(3000 / 1800)  # = 2,错的

    def test_delay_index_direction_reversed(self):
        out = analyze_v0([_seg(speed=30, free_flow_speed=60)])
        assert out["segments"][0]["delay_index"] < 0  # 方向写反,产生负值

    def test_missing_volume_crashes(self):
        with pytest.raises(TypeError):
            analyze_v0([_seg(volume=None)])

    def test_empty_dataset_zero_division(self):
        with pytest.raises(ZeroDivisionError):
            analyze_v0([])


class TestV1:
    def test_saturation_formula(self):
        out = analyze_v1([_seg(volume=2880)])  # 2880 / (1800*2) = 0.8 → 拥堵
        row = out["segments"][0]
        assert row["saturation"] == 0.8
        assert row["classification"] == "拥堵"

    def test_delay_index_nonnegative(self):
        out = analyze_v1([_seg(speed=30, free_flow_speed=60)])
        assert out["segments"][0]["delay_index"] == 0.5

    def test_missing_volume_degrades(self):
        out = analyze_v1([_seg(volume=None)])
        row = out["segments"][0]
        assert row["classification"] == "数据缺失"
        assert out["global_congestion_index"] is None
        assert "数据缺失 1 个" in out["summary"]

    def test_recommendations_cover_congested(self):
        out = analyze_v1([_seg(volume=3600)])  # V/C = 1.0 → 严重拥堵
        rec_ids = {r["segment_id"] for r in out["recommendations"]}
        assert rec_ids == set(out["congested_segments"]) == {"S-01"}


class TestV2:
    def test_escalation_band(self):
        # V/C=0.78 落在 [0.75,0.8) 且速度比 15/60=0.25 < 0.35 → 升级为拥堵
        out = analyze_v2([_seg(volume=2808, speed=15)])
        assert out["segments"][0]["classification"] == "拥堵"

    def test_no_escalation_when_speed_normal(self):
        # 同样 V/C=0.78,但速度比 0.5 → 维持「缓行」
        out = analyze_v2([_seg(volume=2808, speed=30)])
        assert out["segments"][0]["classification"] == "缓行"

    def test_global_index_volume_weighted_with_cap(self):
        # 两路段等流量 1800:V/C 分别为 0.5 与 2.0(过饱和封顶 1.2)
        # 全局指数 = (0.5 + 1.2) / 2 = 0.85;若不封顶则为 1.25
        out = analyze_v2([_seg(segment_id="A", volume=900),
                          _seg(segment_id="B", volume=3600)])
        assert abs(out["global_congestion_index"] - 0.85) <= 0.001

    def test_congested_sorted_by_saturation_desc(self):
        out = analyze_v2([_seg(segment_id="A", volume=2880),   # 0.8
                          _seg(segment_id="B", volume=3240)])  # 0.9
        assert out["congested_segments"] == ["B", "A"]

    def test_empty_dataset_degrades_gracefully(self):
        out = analyze_v2([])
        assert out["segments"] == []
        assert out["congested_segments"] == []
        assert out["global_congestion_index"] is None
        assert "0 个路段" in out["summary"]

    def test_all_missing_volume_index_is_none(self):
        out = analyze_v2([_seg(volume=None)])
        assert out["global_congestion_index"] is None

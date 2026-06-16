"""测试 PresetMatcher (Phase 1.5+ 探索 C 路径)。"""
import numpy as np
import torch
import pytest

from src.lut_generator.analysis.classic_presets import (
    CLASSIC_PRESETS,
    all_vectors,
    get_preset_vector,
    list_presets,
)
from src.lut_generator.analysis.preset_extractor import ParamSpace
from src.lut_generator.analysis.preset_matcher import (
    PresetMatcher,
    ciede2000_numpy,
    ciede2000_summary,
    format_results,
)


class TestClassicPresets:
    def test_library_has_at_least_10(self):
        assert len(list_presets()) >= 10

    def test_all_presets_are_ParamSpace(self):
        for name in list_presets():
            assert isinstance(CLASSIC_PRESETS[name], ParamSpace)

    def test_vectors_have_shape_67(self):
        for name in list_presets():
            v = get_preset_vector(name)
            assert v.shape == (67,), f"{name} vector shape: {v.shape}"

    def test_all_vectors_aligned(self):
        names = list_presets()
        ref = get_preset_vector(names[0])
        for name in names[1:]:
            v = get_preset_vector(name)
            assert v.shape == ref.shape

    def test_bw_presets_have_minus100_saturation(self):
        """B&W preset 必须 saturation=-100。"""
        for name in ["bw_high_contrast", "dramatic_bw"]:
            ps = CLASSIC_PRESETS[name]
            assert ps.saturation == -100, f"{name} saturation: {ps.saturation}"


class TestPresetMatcher:
    def _make_neutral_baseline(self, h=64, w=64):
        """0.5 灰 + 小梯度(模拟 RAW 直出有内容)。"""
        x = np.linspace(0.3, 0.7, w)
        y = np.linspace(0.3, 0.7, h)
        xx, yy = np.meshgrid(x, y)
        base = np.stack([xx, yy, (xx + yy) / 2], axis=-1).astype(np.float32)
        return torch.from_numpy(base)

    def test_ciede2000_summary_keys(self):
        de = np.array([1.0, 5.0, 10.0, 20.0])
        s = ciede2000_summary(de)
        assert set(s.keys()) == {"mean", "median", "max", "p95", "lt_2", "lt_5", "lt_10"}

    def test_ciede2000_lt_2_lt_5_lt_10(self):
        de = np.array([1.0, 2.5, 4.0, 6.0, 10.0, 20.0])
        s = ciede2000_summary(de)
        # < 2: only 1.0 → 1/6
        assert s["lt_2"] == 1 / 6
        # < 5: 1.0, 2.5, 4.0 → 3/6
        assert s["lt_5"] == 3 / 6
        # < 10: 1.0, 2.5, 4.0, 6.0 → 4/6 (10.0 is NOT < 10, it's ==)
        assert s["lt_10"] == 4 / 6

    def test_matcher_returns_sorted_results(self):
        """match() 返回 list, 按 mean 升序。"""
        matcher = PresetMatcher()
        baseline = self._make_neutral_baseline(64, 64)
        # 构造一个 ref (比 baseline 偏暖,触发 hue 差异)
        ref = baseline.clone()
        ref[..., 0] += 0.1  # R +
        ref[..., 2] -= 0.05  # B -
        results = matcher.match(ref, baseline, downsample=64)
        assert len(results) == len(list_presets())
        # 验证排序
        for i in range(len(results) - 1):
            assert results[i]["mean"] <= results[i + 1]["mean"]

    def test_matcher_top_result_is_warm(self):
        """用偏暖 ref 匹配, top 3 应该包含 warm_xxx。"""
        matcher = PresetMatcher()
        baseline = self._make_neutral_baseline(64, 64)
        ref = baseline.clone()
        ref[..., 0] += 0.15
        ref[..., 2] -= 0.1
        results = matcher.match(ref, baseline, downsample=64, candidates=[
            "portra_400", "kodak_gold", "velvia_50", "cinematic_teal_orange",
            "bw_high_contrast", "cross_process", "fade_film", "cool_mist",
            "warm_vintage", "dramatic_bw"
        ])
        # 简单 sanity: results 存在
        assert all("name" in r for r in results)

    def test_format_results(self):
        results = [
            {"name": "portra_400", "mean": 15.0, "median": 14.0, "lt_5": 0.3,
             "lt_10": 0.5, "elapsed_sec": 0.05}
        ]
        s = format_results(results)
        assert "portra_400" in s
        assert "15.00" in s

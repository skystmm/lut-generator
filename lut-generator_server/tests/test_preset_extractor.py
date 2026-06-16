"""
Lightroom 预设反推模块单元测试
"""

import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 这些测试需要 torch
torch = pytest.importorskip("torch")

from lut_generator.analysis.preset_extractor import (
    LRRenderer,
    ParamSpace,
    PresetExtractor,
    ExtractionResult,
)


# ----------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------


def _make_gradient_image(h: int = 96, w: int = 128, seed: int = 0) -> torch.Tensor:
    """构造一张简单的渐变 + 噪声测试图(模拟"中性基线")。"""
    rng = np.random.RandomState(seed)
    img = np.zeros((h, w, 3), dtype=np.float32)
    # R 通道:水平渐变
    img[:, :, 0] = np.tile(np.linspace(0.0, 1.0, w), (h, 1))
    # G 通道:垂直渐变
    img[:, :, 1] = np.tile(np.linspace(0.0, 1.0, h).reshape(-1, 1), (1, w))
    # B 通道:固定 0.4
    img[:, :, 2] = 0.4
    # 加少量噪声,避免纯色
    img += rng.normal(0, 0.01, img.shape).astype(np.float32)
    return torch.from_numpy(np.clip(img, 0, 1))


# ----------------------------------------------------------------------
# ParamSpace 测试
# ----------------------------------------------------------------------


class TestParamSpace:
    def test_default_dim(self):
        ps = ParamSpace()
        # 67 维 = 7 Basic + 2 Temp/Tint + 4 Presence + 24 HSL + 6 CG + 24 Curve
        assert int(ps.dim) == 67

    def test_to_from_vector_roundtrip(self):
        ps = ParamSpace()
        ps.exposure = 0.5
        ps.contrast = 20.0
        ps.temperature = 30.0
        ps.vibrance = 15.0
        ps.hsl_orange_sat = 25.0
        ps.cg_shadows_hue = 220.0
        vec = ps.to_vector()
        assert vec.shape == (67,)
        ps2 = ParamSpace.from_vector(vec)
        assert math.isclose(ps2.exposure, 0.5, abs_tol=1e-6)
        assert math.isclose(ps2.contrast, 20.0, abs_tol=1e-6)
        assert math.isclose(ps2.temperature, 30.0, abs_tol=1e-6)
        assert math.isclose(ps2.vibrance, 15.0, abs_tol=1e-6)
        assert math.isclose(ps2.hsl_orange_sat, 25.0, abs_tol=1e-6)
        assert math.isclose(ps2.cg_shadows_hue, 220.0, abs_tol=1e-6)
        assert ps2.curve_r == ps.curve_r

    def test_from_vector_wrong_shape(self):
        with pytest.raises(ValueError, match="expected vector of shape"):
            ParamSpace.from_vector(np.zeros(30, dtype=np.float64))

    def test_bounds_have_67_entries(self):
        bounds = ParamSpace.bounds()
        assert len(bounds) == 67
        # Basic 范围
        assert bounds[0] == (-5.0, 5.0)  # exposure
        assert bounds[1] == (-100.0, 100.0)  # contrast
        # Temp/Tint
        assert bounds[7] == (-100.0, 100.0)  # temperature
        assert bounds[8] == (-100.0, 100.0)  # tint
        # HSL Hue 范围
        assert bounds[13] == (-100.0, 100.0)  # hsl_red_hue
        # CG Hue 范围(0..360)
        assert bounds[37] == (0.0, 360.0)  # cg_shadows_hue
        # Curve 范围
        for b in bounds[43:]:
            assert b == (0.0, 1.0)


# ----------------------------------------------------------------------
# LRRenderer 测试
# ----------------------------------------------------------------------


class TestLRRenderer:
    def test_zero_params_is_identity(self):
        """零参数渲染应等于输入(允许有微小浮点误差)。"""
        renderer = LRRenderer("cpu")
        img = _make_gradient_image()
        default = ParamSpace().to_vector().astype(np.float32)
        out = renderer.render(img, default)
        diff = (out - img).abs().mean().item()
        assert diff < 1e-4, f"identity render diff too large: {diff}"

    def test_output_shape_preserved(self):
        renderer = LRRenderer("cpu")
        img = _make_gradient_image(64, 80)
        out = renderer.render(img, ParamSpace().to_vector().astype(np.float32))
        assert out.shape == img.shape

    def test_output_in_zero_one_range(self):
        """输出应 clamp 在 [0, 1]。"""
        renderer = LRRenderer("cpu")
        img = _make_gradient_image()
        # 极端参数
        ps = ParamSpace()
        ps.exposure = 4.0  # +4 EV
        ps.contrast = 100.0
        out = renderer.render(img, ps.to_vector().astype(np.float32))
        assert out.min().item() >= 0.0
        assert out.max().item() <= 1.0

    def test_accepts_numpy_or_tensor(self):
        """render 接受 numpy 和 tensor 两种 params。"""
        renderer = LRRenderer("cpu")
        img = _make_gradient_image()
        np_params = ParamSpace().to_vector().astype(np.float32)
        ts_params = torch.from_numpy(np_params)
        out_np = renderer.render(img, np_params)
        out_ts = renderer.render(img, ts_params)
        assert torch.allclose(out_np, out_ts, atol=1e-5)


# ----------------------------------------------------------------------
# PresetExtractor 反推测试
# ----------------------------------------------------------------------


class TestPresetExtractor:
    def test_load_image_shape(self, tmp_path):
        """load_image_as_neutral 应返回 HxWx3 float tensor ∈ [0, 1]。"""
        import cv2
        img = np.random.RandomState(0).randint(0, 256, (100, 200, 3), dtype=np.uint8)
        path = tmp_path / "test.png"
        cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        loaded = PresetExtractor.load_image_as_neutral(path, max_size=100)
        assert loaded.ndim == 3
        assert loaded.shape[-1] == 3
        assert loaded.min().item() >= 0.0
        assert loaded.max().item() <= 1.0

    def test_extract_recovers_curve(self):
        """给定调色图,反推的 Tone Curve 应接近 ground truth。"""
        renderer = LRRenderer("cpu")
        img = _make_gradient_image(seed=1)
        # Ground truth: 弯曲 R 通道
        gt = ParamSpace()
        gt.exposure = 0.5
        gt.contrast = 15.0
        gt.saturation = 10.0
        gt.curve_r = tuple(np.linspace(0.0, 0.85, 8).tolist())
        target = renderer.render(img, gt.to_vector().astype(np.float32)).detach()

        extractor = PresetExtractor(device="cpu", verbose=False)
        result = extractor.extract(target, max_iter=60, n_restarts=1)

        # Tone Curve 应高度还原
        recovered_curve = np.array(result.params.curve_r)
        expected_curve = np.array(gt.curve_r)
        curve_diff = np.abs(recovered_curve - expected_curve).mean()
        # 允许较大误差(多解性:renderer 把变化摊到 Basic + Curve)
        assert curve_diff < 0.15, f"curve diff too large: {curve_diff:.4f}"

    def test_extract_loss_decreases(self):
        """损失应在多次重启中保持较小(粗略 sanity check)。"""
        renderer = LRRenderer("cpu")
        img = _make_gradient_image(seed=2)
        gt = ParamSpace()
        gt.exposure = 0.3
        gt.contrast = 10.0
        target = renderer.render(img, gt.to_vector().astype(np.float32)).detach()

        extractor = PresetExtractor(device="cpu", verbose=False)
        result = extractor.extract(target, max_iter=60, n_restarts=1, staged=True)
        # 反推后渲染应与 target 接近(loss 较小)
        recovered_render = renderer.render(img, result.params.to_vector().astype(np.float32))
        direct_loss = torch.nn.functional.mse_loss(recovered_render, target).item()
        # Phase 1.2 阈值 0.03(67 维 + Gram 损失 + 3 阶段,容忍度更高)
        assert direct_loss < 0.03, f"recovery loss too high: {direct_loss}"

    def test_extraction_result_has_required_fields(self):
        renderer = LRRenderer("cpu")
        img = _make_gradient_image(seed=3)
        gt = ParamSpace(); gt.exposure = 0.2
        target = renderer.render(img, gt.to_vector().astype(np.float32)).detach()

        extractor = PresetExtractor(device="cpu", verbose=False)
        result = extractor.extract(target, max_iter=20, n_restarts=1)

        assert isinstance(result, ExtractionResult)
        assert isinstance(result.params, ParamSpace)
        assert result.loss >= 0
        assert result.iterations > 0
        assert result.elapsed_sec >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

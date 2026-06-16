"""
Lightroom 风格预设反推模块 - PresetExtractor

从单张调色后图片反推 Lightroom Develop 预设参数(Basic + Tone Curve 子集)。
输出为 .xmp 格式(Lightroom 7.3+ 规范)。

核心原理:
    假设一张"中性"输入图 I_neutral(灰度线性,无色调偏移),求参数 θ
    使得 render(I_neutral, θ) ≈ I_graded。

算法: Differentiable Renderer + L-BFGS 优化
    - render:  PyTorch 实现的 LR Basic + Tone Curve 子集
    - loss:    像素 MSE + 参数正则
    - optim:   torch.optim.LBFGS,多起点

参考: 2026-06-16 路径 B 调研报告。
    - Neural Preset (CVPR 2023, arXiv 2303.13511) — 网络快速候选
    - VSCO v. PicsArt — 业界精度标杆 CIEDE2000 < 2
    - LR 7.3+ .xmp 格式(Thomas Fitzgerald 博客)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np

# PyTorch 是可选依赖(用于 differentiable rendering + L-BFGS)。
# 缺失时给出明确错误信息,而不是 ImportError stack trace。
try:
    import torch
    import torch.nn.functional as F
    _HAS_TORCH = True
except ImportError:  # pragma: no cover - exercised only without torch
    _HAS_TORCH = False
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]


# ----------------------------------------------------------------------
# 参数空间定义
# ----------------------------------------------------------------------


@dataclass
class ParamSpace:
    """66 维参数向量的边界 / 名称 / 默认值。

    顺序: 7 Basic + 2 Temp/Tint + 4 Presence + 24 HSL + 6 Color Grading + 24 Tone Curve

    设计原则(2026-06-16 Phase 1.2):
        - 目标: 通用图类型反推,不是单一暖色风格
        - HSL: 8 色 × {Hue, Sat, Lum} = 24 维,做色相迁移
        - Color Grading (Split Toning): 3 区(Shadows/Midtones/Highlights) × {Hue, Sat} = 6 维
        - Temp/Tint: 2 维,白平衡偏移
        - Presence: 4 维,Vibrance/Texture/Clarity/Dehaze,做"质感"
        - 排除维度(暂): Sharpening/Grain/Vignette/Calibration(空间/相机校色,见审计表)
    """

    # Basic 7 维
    exposure: float = 0.0          # -5..+5  EV
    contrast: float = 0.0          # -100..+100
    highlights: float = 0.0        # -100..+100
    shadows: float = 0.0           # -100..+100
    whites: float = 0.0            # -100..+100
    blacks: float = 0.0            # -100..+100
    saturation: float = 0.0        # -100..+100

    # Temp/Tint 2 维
    temperature: float = 0.0       # -100..+100  (负=冷,正=暖)
    tint: float = 0.0              # -100..+100  (负=绿,正=品)

    # Presence 4 维
    vibrance: float = 0.0          # -100..+100
    texture: float = 0.0           # -100..+100
    clarity: float = 0.0           # -100..+100
    dehaze: float = 0.0            # -100..+100

    # HSL 24 维: 8 色 × {Hue, Sat, Lum}
    # 颜色顺序 (Adobe LR): Red, Orange, Yellow, Green, Aqua, Blue, Purple, Magenta
    hsl_red_hue: float = 0.0
    hsl_red_sat: float = 0.0
    hsl_red_lum: float = 0.0
    hsl_orange_hue: float = 0.0
    hsl_orange_sat: float = 0.0
    hsl_orange_lum: float = 0.0
    hsl_yellow_hue: float = 0.0
    hsl_yellow_sat: float = 0.0
    hsl_yellow_lum: float = 0.0
    hsl_green_hue: float = 0.0
    hsl_green_sat: float = 0.0
    hsl_green_lum: float = 0.0
    hsl_aqua_hue: float = 0.0
    hsl_aqua_sat: float = 0.0
    hsl_aqua_lum: float = 0.0
    hsl_blue_hue: float = 0.0
    hsl_blue_sat: float = 0.0
    hsl_blue_lum: float = 0.0
    hsl_purple_hue: float = 0.0
    hsl_purple_sat: float = 0.0
    hsl_purple_lum: float = 0.0
    hsl_magenta_hue: float = 0.0
    hsl_magenta_sat: float = 0.0
    hsl_magenta_lum: float = 0.0

    # Color Grading (Split Toning) 6 维: 3 区 × {Hue, Sat}
    # Hue: 0..360 (色环),Sat: -100..+100
    cg_shadows_hue: float = 0.0
    cg_shadows_sat: float = 0.0
    cg_midtones_hue: float = 0.0
    cg_midtones_sat: float = 0.0
    cg_highlights_hue: float = 0.0
    cg_highlights_sat: float = 0.0

    # Tone Curve 24 维:RGB 三通道 × 8 个控制点,值 ∈ [0, 1]
    curve_r: Tuple[float, ...] = field(default_factory=lambda: tuple(np.linspace(0, 1, 8).tolist()))
    curve_g: Tuple[float, ...] = field(default_factory=lambda: tuple(np.linspace(0, 1, 8).tolist()))
    curve_b: Tuple[float, ...] = field(default_factory=lambda: tuple(np.linspace(0, 1, 8).tolist()))

    @property
    def dim(self) -> int:
        return 7 + 2 + 4 + 24 + 6 + 24  # 65? 实际 7+2+4+24+6+24=67
        # 实际 7+2+4+24+6+24 = 67, 修正

    def to_vector(self) -> np.ndarray:
        """展开为 67 维 numpy 数组。"""
        # Basic 7
        vec = np.array([
            self.exposure, self.contrast, self.highlights, self.shadows,
            self.whites, self.blacks, self.saturation,
        ], dtype=np.float64)
        # Temp/Tint 2
        vec = np.concatenate([vec, [self.temperature, self.tint]])
        # Presence 4
        vec = np.concatenate([vec, [self.vibrance, self.texture, self.clarity, self.dehaze]])
        # HSL 24
        hsl_vals = [
            self.hsl_red_hue, self.hsl_red_sat, self.hsl_red_lum,
            self.hsl_orange_hue, self.hsl_orange_sat, self.hsl_orange_lum,
            self.hsl_yellow_hue, self.hsl_yellow_sat, self.hsl_yellow_lum,
            self.hsl_green_hue, self.hsl_green_sat, self.hsl_green_lum,
            self.hsl_aqua_hue, self.hsl_aqua_sat, self.hsl_aqua_lum,
            self.hsl_blue_hue, self.hsl_blue_sat, self.hsl_blue_lum,
            self.hsl_purple_hue, self.hsl_purple_sat, self.hsl_purple_lum,
            self.hsl_magenta_hue, self.hsl_magenta_sat, self.hsl_magenta_lum,
        ]
        vec = np.concatenate([vec, hsl_vals])
        # Color Grading 6
        cg_vals = [
            self.cg_shadows_hue, self.cg_shadows_sat,
            self.cg_midtones_hue, self.cg_midtones_sat,
            self.cg_highlights_hue, self.cg_highlights_sat,
        ]
        vec = np.concatenate([vec, cg_vals])
        # Tone Curve 24
        for curve in (self.curve_r, self.curve_g, self.curve_b):
            vec = np.concatenate([vec, np.asarray(curve, dtype=np.float64)])
        return vec

    @classmethod
    def from_vector(cls, vec: np.ndarray) -> "ParamSpace":
        """从 67 维向量构造。"""
        # 实例化一次以拿到 dim 数值(避免 @property 在类上访问返回 descriptor)
        expected_dim = int(cls().dim)
        if vec.shape != (expected_dim,):
            raise ValueError(f"expected vector of shape ({expected_dim},), got {vec.shape}")
        idx = 0
        # Basic 7
        exposure, contrast, highlights, shadows, whites, blacks, saturation = vec[idx:idx+7]; idx += 7
        # Temp/Tint 2
        temperature, tint = vec[idx:idx+2]; idx += 2
        # Presence 4
        vibrance, texture, clarity, dehaze = vec[idx:idx+4]; idx += 4
        # HSL 24
        hsl_vals = vec[idx:idx+24]; idx += 24
        hsl = {
            'red':    hsl_vals[0:3],
            'orange': hsl_vals[3:6],
            'yellow': hsl_vals[6:9],
            'green':  hsl_vals[9:12],
            'aqua':   hsl_vals[12:15],
            'blue':   hsl_vals[15:18],
            'purple': hsl_vals[18:21],
            'magenta':hsl_vals[21:24],
        }
        # Color Grading 6
        cg_shadows_hue, cg_shadows_sat, cg_midtones_hue, cg_midtones_sat, cg_highlights_hue, cg_highlights_sat = vec[idx:idx+6]; idx += 6
        # Tone Curve 24
        curve_r = tuple(vec[idx:idx+8].tolist()); idx += 8
        curve_g = tuple(vec[idx:idx+8].tolist()); idx += 8
        curve_b = tuple(vec[idx:idx+8].tolist()); idx += 8

        return cls(
            exposure=float(exposure), contrast=float(contrast),
            highlights=float(highlights), shadows=float(shadows),
            whites=float(whites), blacks=float(blacks),
            saturation=float(saturation),
            temperature=float(temperature), tint=float(tint),
            vibrance=float(vibrance), texture=float(texture),
            clarity=float(clarity), dehaze=float(dehaze),
            # HSL
            hsl_red_hue=float(hsl['red'][0]), hsl_red_sat=float(hsl['red'][1]), hsl_red_lum=float(hsl['red'][2]),
            hsl_orange_hue=float(hsl['orange'][0]), hsl_orange_sat=float(hsl['orange'][1]), hsl_orange_lum=float(hsl['orange'][2]),
            hsl_yellow_hue=float(hsl['yellow'][0]), hsl_yellow_sat=float(hsl['yellow'][1]), hsl_yellow_lum=float(hsl['yellow'][2]),
            hsl_green_hue=float(hsl['green'][0]), hsl_green_sat=float(hsl['green'][1]), hsl_green_lum=float(hsl['green'][2]),
            hsl_aqua_hue=float(hsl['aqua'][0]), hsl_aqua_sat=float(hsl['aqua'][1]), hsl_aqua_lum=float(hsl['aqua'][2]),
            hsl_blue_hue=float(hsl['blue'][0]), hsl_blue_sat=float(hsl['blue'][1]), hsl_blue_lum=float(hsl['blue'][2]),
            hsl_purple_hue=float(hsl['purple'][0]), hsl_purple_sat=float(hsl['purple'][1]), hsl_purple_lum=float(hsl['purple'][2]),
            hsl_magenta_hue=float(hsl['magenta'][0]), hsl_magenta_sat=float(hsl['magenta'][1]), hsl_magenta_lum=float(hsl['magenta'][2]),
            # CG
            cg_shadows_hue=float(cg_shadows_hue), cg_shadows_sat=float(cg_shadows_sat),
            cg_midtones_hue=float(cg_midtones_hue), cg_midtones_sat=float(cg_midtones_sat),
            cg_highlights_hue=float(cg_highlights_hue), cg_highlights_sat=float(cg_highlights_sat),
            # Curve
            curve_r=curve_r, curve_g=curve_g, curve_b=curve_b,
        )

    @staticmethod
    def bounds() -> List[Tuple[float, float]]:
        """每个维度的 (lo, hi) 边界,用于 box 约束优化。

        Hue 维度是 0..360 色环(CG 专用),其他 [-100, 100] 滑块类。
        """
        return (
            # Basic
            [(-5.0, 5.0), (-100.0, 100.0), (-100.0, 100.0), (-100.0, 100.0),
             (-100.0, 100.0), (-100.0, 100.0), (-100.0, 100.0)]
            # Temp/Tint
            + [(-100.0, 100.0), (-100.0, 100.0)]
            # Presence
            + [(-100.0, 100.0)] * 4
            # HSL: 8 色 × 3 维(Hue 仍是 ±100 内部尺度,与 Adobe 一致)
            + [(-100.0, 100.0)] * 24
            # Color Grading: 3 区 × (Hue 0..360, Sat ±100)
            + [(0.0, 360.0), (-100.0, 100.0),
               (0.0, 360.0), (-100.0, 100.0),
               (0.0, 360.0), (-100.0, 100.0)]
            # Tone Curve
            + [(0.0, 1.0)] * 24
        )


# ----------------------------------------------------------------------
# Differentiable Renderer (PyTorch)
# ----------------------------------------------------------------------


class LRRenderer:
    """Lightroom 全 67 维参数的 PyTorch 可微近似。

    算子顺序(模拟 LR 实际处理流水线):
        Temp/Tint → Exposure → Contrast → Highlights/Shadows → Whites/Blacks
        → Presence (Vibrance/Texture/Clarity/Dehaze 简化版)
        → HSL 8 色 × (Hue/Sat/Lum)
        → Color Grading (Shadows/Midtones/Highlights × H/S)
        → Tone Curve (RGB 8 控制点)

    输入: HxWx3 float tensor ∈ [0, 1] (sRGB 域)
    输出: HxWx3 float tensor ∈ [0, 1] (sRGB 域)
    参数: 67 维 float tensor (见 :class:`ParamSpace`)

    精度上限: PoC 1.2,无 VGG 感知损失,色相迁移精度有限
        (HSL 渲染用简化 mask,不是真正的 Adobe 闭源算法)。
    """

    def __init__(self, device: str = "cpu"):
        if not _HAS_TORCH:
            raise RuntimeError(
                "PyTorch is required for LRRenderer. "
                "Install with: pip install torch --index-url https://download.pytorch.org/whl/cpu"
            )
        self.device = torch.device(device)

    # ---- 色彩空间转换 (sRGB ↔ HSL) ----

    @staticmethod
    def _rgb_to_hsl(img: "torch.Tensor") -> "torch.Tensor":
        """sRGB (0..1) → HSL (H∈[0,360], S/L∈[0,1])

        向量化实现。输入 shape (H, W, 3)。
        """
        r, g, b = img[..., 0], img[..., 1], img[..., 2]
        max_c = img.max(dim=-1).values
        min_c = img.min(dim=-1).values
        v = max_c
        delta = max_c - min_c
        # Lightness: (max+min)/2
        l = (max_c + min_c) / 2.0
        # Saturation: 0 if delta==0 else delta/(1 - |2L-1|)
        s = torch.where(
            delta < 1e-8,
            torch.zeros_like(delta),
            delta / (1.0 - torch.abs(2.0 * l - 1.0) + 1e-8)
        )
        # Hue
        h = torch.zeros_like(delta)
        # r==max
        mask_r = (max_c == r) & (delta > 1e-8)
        h = torch.where(mask_r, ((g - b) / (delta + 1e-8)) % 6.0, h)
        # g==max
        mask_g = (max_c == g) & (delta > 1e-8)
        h = torch.where(mask_g, (b - r) / (delta + 1e-8) + 2.0, h)
        # b==max
        mask_b = (max_c == b) & (delta > 1e-8)
        h = torch.where(mask_b, (r - g) / (delta + 1e-8) + 4.0, h)
        h = h * 60.0  # 转为度数
        h = h % 360.0
        return torch.stack([h, s, l], dim=-1)

    @staticmethod
    def _hsl_to_rgb(hsl: "torch.Tensor") -> "torch.Tensor":
        """HSL (H∈[0,360], S/L∈[0,1]) → sRGB (0..1)"""
        h, s, l = hsl[..., 0], hsl[..., 1], hsl[..., 2]
        # 标准 HSL→RGB 公式
        c = (1.0 - torch.abs(2.0 * l - 1.0)) * s
        hp = h / 60.0
        x = c * (1.0 - torch.abs(hp % 2.0 - 1.0))
        zeros = torch.zeros_like(c)
        # 6 个区间
        r1 = torch.stack([c, x, zeros], dim=-1)  # 0..1
        r2 = torch.stack([x, c, zeros], dim=-1)  # 1..2
        r3 = torch.stack([zeros, c, x], dim=-1)  # 2..3
        r4 = torch.stack([zeros, x, c], dim=-1)  # 3..4
        r5 = torch.stack([x, zeros, c], dim=-1)  # 4..5
        r6 = torch.stack([c, zeros, x], dim=-1)  # 5..6

        # 用区间选择
        seg = (hp.floor() % 6).long()
        # 把 6 个候选 stack 成 (H, W, 6, 3)
        candidates = torch.stack([r1, r2, r3, r4, r5, r6], dim=-2)
        # gather
        idx = seg.unsqueeze(-1).unsqueeze(-1).expand(*seg.shape, 1, 3)
        rgb_chromaticity = torch.gather(candidates, -2, idx).squeeze(-2)
        m = l - c / 2.0
        return rgb_chromaticity + m.unsqueeze(-1)

    # ---- Temp / Tint (白平衡,简化版) ----

    @staticmethod
    def _temp_tint(img: "torch.Tensor", temp: "torch.Tensor", tint: "torch.Tensor") -> "torch.Tensor":
        """白平衡调整: temp>0 偏暖(R+, B-), tint>0 偏品(G-, R+)"""
        # 简化线性: temp±100 → ±20% 偏移;tint±100 → ±10%
        temp_scale = temp / 500.0  # -0.2..+0.2
        tint_scale = tint / 1000.0  # -0.1..+0.1
        r_scale = 1.0 + temp_scale + tint_scale * 0.3
        g_scale = 1.0 - tint_scale
        b_scale = 1.0 - temp_scale
        # 用 stack 创建新 tensor(非 in-place)
        out = torch.stack([
            img[..., 0] * r_scale,
            img[..., 1] * g_scale,
            img[..., 2] * b_scale,
        ], dim=-1)
        return out

    # ---- 基础算子(Basic 7 维,继承自 PoC 1.1) ----

    @staticmethod
    def _exposure(img: "torch.Tensor", ev: "torch.Tensor") -> "torch.Tensor":
        """EV 调整: out = in * 2^ev"""
        scale = torch.pow(torch.tensor(2.0, device=img.device, dtype=img.dtype), ev)
        return img * scale

    @staticmethod
    def _contrast(img: "torch.Tensor", c: "torch.Tensor") -> "torch.Tensor":
        """Contrast: 围绕 0.5 灰阶线性放缩,LR c ∈ [-100, 100] → [0.5, 1.5]"""
        amount = 1.0 + c / 200.0
        return 0.5 + (img - 0.5) * amount

    @staticmethod
    def _highlights_shadows(img: "torch.Tensor", hi: "torch.Tensor", sh: "torch.Tensor") -> "torch.Tensor":
        """简化版 Highlights/Shadows:基于亮度 mask 的两端加/减权。"""
        luma = 0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]
        shadow_mask = torch.sigmoid((0.4 - luma) * 10.0)
        highlight_mask = torch.sigmoid((luma - 0.6) * 10.0)
        hi_amount = hi / 333.0
        sh_amount = sh / 333.0
        adjustment = (highlight_mask * hi_amount - shadow_mask * sh_amount).unsqueeze(-1)
        return img + adjustment

    @staticmethod
    def _whites_blacks(img: "torch.Tensor", wh: "torch.Tensor", bk: "torch.Tensor") -> "torch.Tensor":
        """Whites/Blacks:基于端点 mask 的两端亮度调整,简化版。"""
        luma = 0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]
        white_mask = torch.sigmoid((luma - 0.7) * 15.0)
        black_mask = torch.sigmoid((0.3 - luma) * 15.0)
        wh_amount = wh / 500.0
        bk_amount = bk / 500.0
        adjustment = (white_mask * wh_amount - black_mask * bk_amount).unsqueeze(-1)
        return img + adjustment

    # ---- Presence 4 维 ----

    @staticmethod
    def _saturation(img: "torch.Tensor", s: "torch.Tensor") -> "torch.Tensor":
        """Saturation:在 luma 中心做色度放缩。LR ±100 → [0, 2]"""
        amount = 1.0 + s / 100.0
        luma = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]).unsqueeze(-1)
        return luma + (img - luma) * amount

    @staticmethod
    def _vibrance(img: "torch.Tensor", v: "torch.Tensor") -> "torch.Tensor":
        """Vibrance: 对低饱和度区域放大,高饱和度区域不变(比 Saturation 温和)。"""
        # 估算"饱和度"(用 max-min)
        sat_estimate = (img.max(dim=-1).values - img.min(dim=-1).values)
        # 低饱和区(接近 0)放大,高饱和区(接近 1)保持
        # weight = 1 - sat_estimate
        weight = 1.0 - sat_estimate
        amount = 1.0 + (v / 100.0) * weight.unsqueeze(-1)
        luma = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]).unsqueeze(-1)
        return luma + (img - luma) * amount

    @staticmethod
    def _texture(img: "torch.Tensor", t: "torch.Tensor") -> "torch.Tensor":
        """Texture: 高频细节增强(简化:基于局部均值差的 mask)。"""
        # 3×3 平均卷积,每个通道独立
        # kernel shape for conv2d: (out_channels=3, in_channels=3, H, W)
        # 用 group=3 让每通道独立
        kernel = torch.ones((3, 1, 3, 3), device=img.device, dtype=img.dtype) / 9.0
        img_4d = img.permute(2, 0, 1).unsqueeze(0)  # (1, 3, H, W)
        smoothed = F.conv2d(img_4d, kernel, padding=1, groups=3)
        smoothed = smoothed.squeeze(0).permute(1, 2, 0)  # (H, W, 3)
        high_freq = img - smoothed
        amount = t / 333.0
        return img + high_freq * amount

    @staticmethod
    def _clarity(img: "torch.Tensor", c: "torch.Tensor") -> "torch.Tensor":
        """Clarity: 中频对比度增强(类似 Texture 但尺度更大)。"""
        kernel5 = torch.ones((3, 1, 5, 5), device=img.device, dtype=img.dtype) / 25.0
        img_4d = img.permute(2, 0, 1).unsqueeze(0)
        smoothed = F.conv2d(img_4d, kernel5, padding=2, groups=3)
        smoothed = smoothed.squeeze(0).permute(1, 2, 0)
        mid_freq = img - smoothed
        amount = c / 333.0
        return img + mid_freq * amount

    @staticmethod
    def _dehaze(img: "torch.Tensor", d: "torch.Tensor") -> "torch.Tensor":
        """Dehaze: 暗部抬升 + 对比度增强(简化版)。
        真实算法是 dark channel prior,我们用 sigmoid 蒙版近似。
        """
        luma = 0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]
        # 暗部权重
        dark_mask = torch.sigmoid((0.5 - luma) * 6.0)
        amount = d / 200.0  # ±0.5
        # 抬升暗部 + 增加局部对比度
        boost = dark_mask.unsqueeze(-1) * amount * 0.3
        return img + boost

    # ---- HSL 24 维(关键: 色相迁移) ----

    @staticmethod
    def _hsl_color_mask(hsl: "torch.Tensor",
                        color_center: float,
                        color_width: float = 30.0) -> "torch.Tensor":
        """计算每个像素在 HSL 空间离目标颜色中心的"距离权重"。

        color_center: 目标色在色环上的角度(0..360)
        color_width: 影响半径(度),默认 ±30°
        返回 shape (H, W), 值 ∈ [0, 1](1 = 正好是目标色, 0 = 远离)
        """
        h = hsl[..., 0]
        # 色环距离: |h - center| mod 360 取 min(|a-b|, 360-|a-b|)
        diff = torch.abs(h - color_center)
        diff = torch.minimum(diff, 360.0 - diff)
        # 高斯衰减
        weight = torch.exp(-(diff ** 2) / (2 * color_width ** 2))
        return weight

    def _apply_hsl(self, img: "torch.Tensor", params: "torch.Tensor") -> "torch.Tensor":
        """params[13:37] = 8 色 × 3 维(Hue/Sat/Lum)

        8 色顺序 (Adobe LR): red=0°, orange=30°, yellow=60°, green=120°,
                              aqua=180°, blue=240°, purple=280°, magenta=320°

        真实 Adobe 语义:
            - HueAdjustmentX = ±100: 把"非 X 色"的色相**向 X 色方向** 拉
              (±100 → ±30° 实际偏移,中心在 X 的像素不动)
            - SaturationAdjustmentX = ±100: X 色区的饱和度放缩
            - LuminanceAdjustmentX = ±100: X 色区的亮度调整

        实现: 算每个像素到该色的色环距离,只对"非中心"像素做 hue 拉近。
        """
        hsl = self._rgb_to_hsl(img)
        h = hsl[..., 0]
        s = hsl[..., 1]
        l = hsl[..., 2]
        # 8 色中心(度,Adobe 实际位置: blue=240 不是 220)
        color_centers = [0, 30, 60, 120, 180, 240, 280, 320]
        for i, center in enumerate(color_centers):
            base_idx = 13 + i * 3
            hue_shift = params[base_idx]       # ±100 → ±30° 拉近距离
            sat_amount = params[base_idx + 1]  # ±100 → ±0.8 倍放缩
            lum_amount = params[base_idx + 2]  # ±100 → ±0.4 调整
            # 该色区权重(高斯衰减,中心=1,远离→0)
            color_mask = self._hsl_color_mask(hsl, center, color_width=40.0)
            # 色环有符号距离
            diff = (h - center + 180.0) % 360.0 - 180.0
            # hue_shift > 0: 把所有色拉向 center
            # 强度 = |diff| 越大,拉得越多;但 mask 中心区已经被 center 覆盖
            # 简化: 拉近距离 = hue_shift * 0.3,直接叠加到 h
            # 中心像素(diff≈0)自然不动
            h = (h + diff.sign() * torch.minimum(diff.abs(), torch.tensor(30.0)) * (hue_shift / 100.0) * 0.3) % 360.0
            # 饱和度: 该色区放缩
            sat_scale = 1.0 + sat_amount / 100.0 * 0.8 * color_mask
            s = (s * sat_scale).clamp(0, 1)
            # 亮度: 该色区加亮/减暗
            l = (l + lum_amount / 250.0 * color_mask).clamp(0, 1)
        return self._hsl_to_rgb(torch.stack([h, s, l], dim=-1))

    # ---- Color Grading 6 维 (Split Toning) ----

    def _apply_color_grading(self, img: "torch.Tensor", params: "torch.Tensor") -> "torch.Tensor":
        """params[37:43] = 3 区 × (Hue 0..360, Sat ±100)

        Shadows 暗部 / Midtones 中间 / Highlights 高光
        色相混合算法: 把当前像素的色相 h 拉向目标色相 hue_deg(色环距离),
        拉近距离由 sat_strength 决定。
        """
        luma = 0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]
        # 三个区域 mask(归一化,和为 1)
        shadow_mask = torch.sigmoid((0.35 - luma) * 12.0)
        highlight_mask = torch.sigmoid((luma - 0.65) * 12.0)
        midtone_mask = (1.0 - shadow_mask) * (1.0 - highlight_mask)
        # 归一化使和为 1
        total = shadow_mask + midtone_mask + highlight_mask + 1e-8
        shadow_mask = shadow_mask / total
        midtone_mask = midtone_mask / total
        highlight_mask = highlight_mask / total

        # 转 HSL
        hsl = self._rgb_to_hsl(img)
        h = hsl[..., 0]
        s = hsl[..., 1]
        l = hsl[..., 2]

        regions = [
            (params[37], params[38], shadow_mask),     # Shadows
            (params[39], params[40], midtone_mask),    # Midtones
            (params[41], params[42], highlight_mask),  # Highlights
        ]
        for hue_deg, sat_strength, mask in regions:
            # hue_deg 是 0..360 的目标色相,sat_strength ±100 是强度
            strength = sat_strength / 100.0  # 归一化到 [-1, 1]
            # 色环距离: |h - hue_deg| 取短边
            diff = (h - hue_deg + 180.0) % 360.0 - 180.0  # 有符号距离,∈ [-180, 180]
            # strength > 0: 把 h 拉向 hue_deg(正向旋转)
            # strength < 0: 把 h 拉离 hue_deg(反向旋转 / 去该色)
            h = (h + diff * strength * mask) % 360.0
            # 饱和度调整: 强度影响总体饱和度
            # strength > 0 增饱和,strength < 0 减饱和
            sat_shift = strength * 0.4 * mask
            s = (s + sat_shift).clamp(0, 1)
        return self._hsl_to_rgb(torch.stack([h, s, l], dim=-1))

    # ---- Tone Curve 24 维(继承自 PoC 1.1) ----

    @staticmethod
    def _apply_curve_channel(channel: "torch.Tensor",
                             control_points: "torch.Tensor") -> "torch.Tensor":
        """对单通道应用 Tone Curve(8 个控制点,默认线性)。"""
        xs = torch.linspace(0.0, 1.0, control_points.shape[0],
                           device=channel.device, dtype=channel.dtype)
        sorted_cp, _ = torch.sort(control_points)
        flat = channel.reshape(-1)
        n_seg = xs.shape[0] - 1
        scaled = flat * n_seg
        idx_floor = scaled.floor().clamp(0, n_seg - 1)
        t = (scaled - idx_floor).clamp(0, 1)
        y0 = sorted_cp[idx_floor.long()]
        y1 = sorted_cp[(idx_floor + 1).long()]
        out = y0 + t * (y1 - y0)
        return out.reshape(channel.shape)

    def _apply_curve(self, img: "torch.Tensor", params: "torch.Tensor") -> "torch.Tensor":
        """params[43:67] = [R8 G8 B8]"""
        cp_r = params[43:51]
        cp_g = params[51:59]
        cp_b = params[59:67]
        r = self._apply_curve_channel(img[..., 0], cp_r)
        g = self._apply_curve_channel(img[..., 1], cp_g)
        b = self._apply_curve_channel(img[..., 2], cp_b)
        return torch.stack([r, g, b], dim=-1)

    def render(self, img: "torch.Tensor", params: "torch.Tensor") -> "torch.Tensor":
        """主入口: 应用全 67 维参数到图像。

        流水线(模拟 LR 实际顺序):
            1. Temp/Tint       (白平衡)
            2. Exposure        (基础曝光)
            3. Contrast        (对比度)
            4. Highlights/Shadows
            5. Whites/Blacks
            6. Presence        (Vibrance/Texture/Clarity/Dehaze)
            7. HSL            (8 色调整)
            8. Color Grading   (Split Toning)
            9. Tone Curve      (RGB 三通道)
        """
        if not isinstance(params, torch.Tensor):
            params = torch.as_tensor(params, dtype=torch.float32, device=img.device)
        params = params.to(img.device).float()

        # 1. Temp/Tint
        out = self._temp_tint(img, params[7], params[8])
        # 2-5. Basic
        out = self._exposure(out, params[0])
        out = self._contrast(out, params[1])
        out = self._highlights_shadows(out, params[2], params[3])
        out = self._whites_blacks(out, params[4], params[5])
        # 6. Presence
        out = self._saturation(out, params[6])      # params[6] = saturation
        out = self._vibrance(out, params[9])        # params[9] = vibrance
        out = self._texture(out, params[10])        # params[10] = texture
        out = self._clarity(out, params[11])        # params[11] = clarity
        out = self._dehaze(out, params[12])         # params[12] = dehaze
        # 7. HSL
        out = self._apply_hsl(out, params)
        # 8. Color Grading
        out = self._apply_color_grading(out, params)
        # 9. Tone Curve
        out = self._apply_curve(out, params)
        return out.clamp(0, 1)


# ----------------------------------------------------------------------
# PresetExtractor
# ----------------------------------------------------------------------


@dataclass
class ExtractionResult:
    """反推结果。"""
    params: ParamSpace
    loss: float
    iterations: int
    elapsed_sec: float
    device: str


class PresetExtractor:
    """主入口: 给定一张调色图,反推 LR Basic + Tone Curve 参数。"""

    def __init__(self, device: str = "cpu", verbose: bool = False):
        if not _HAS_TORCH:
            raise RuntimeError(
                "PyTorch is required for PresetExtractor. "
                "Install with: pip install torch --index-url https://download.pytorch.org/whl/cpu"
            )
        self.device = device
        self.verbose = verbose
        self.renderer = LRRenderer(device=device)

    @staticmethod
    def load_image_as_neutral(image_path: Union[str, Path],
                              max_size: int = 512) -> "torch.Tensor":
        """加载图像并转成 HxWx3 float tensor ∈ [0, 1]。

        PoC 阶段假设输入图本身就是"中性"调色基线;真实场景需要
        先用 :class:`StyleExtractor` 反推 baseline。
        """
        import cv2
        img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"cannot load image: {image_path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        # 下采样到 max_size 加快优化
        h, w = img.shape[:2]
        scale = max_size / max(h, w)
        if scale < 1.0:
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        return torch.from_numpy(img).to("cpu")  # 放到 CPU 让 renderer 决定 device

    def _loss(self, rendered: "torch.Tensor",
              reference: "torch.Tensor",
              params: "torch.Tensor",
              reg_weight: float = 0.001) -> "torch.Tensor":
        """损失 = 像素 MSE + Gram 矩阵感知损失 + 参数 L2 正则。

        Gram 矩阵(简化版 VGG 风格):
            - 提取 RGB 通道的"色彩风格"统计(均值 + 协方差矩阵)
            - 不依赖预训练 VGG 模型,完全本地计算
            - 对色相迁移、对比度、饱和度敏感

        权重 (Phase 1.2 默认):
            pixel:  1.0
            gram:   0.5  (Phase 1.2 关键)
            reg:    0.001
        """
        # 像素 MSE
        pix_loss = F.mse_loss(rendered, reference)
        # Gram 风格损失: 用 8x8 patch 协方差
        gram_loss = self._gram_style_loss(rendered, reference)
        # 参数 L2 正则(避免极值)
        reg_loss = (params ** 2).mean() * reg_weight
        return pix_loss + 0.5 * gram_loss + reg_loss

    @staticmethod
    def _gram_style_loss(rendered: "torch.Tensor",
                         reference: "torch.Tensor") -> "torch.Tensor":
        """Gram 矩阵风格损失(简化版感知损失)。

        实现: 提取 RGB 通道的均值 + 协方差矩阵,对它们做 MSE。
        优点: 零依赖、对色相/对比度/饱和度敏感、不需预训练模型。
        """
        # 压平 (H*W, 3)
        r_flat = rendered.reshape(-1, 3)
        ref_flat = reference.reshape(-1, 3)
        # 均值差
        mean_diff = ((r_flat.mean(dim=0) - ref_flat.mean(dim=0)) ** 2).mean()
        # 协方差差(RGB 3x3)
        r_centered = r_flat - r_flat.mean(dim=0, keepdim=True)
        ref_centered = ref_flat - ref_flat.mean(dim=0, keepdim=True)
        r_cov = r_centered.t() @ r_centered / r_flat.shape[0]
        ref_cov = ref_centered.t() @ ref_centered / ref_flat.shape[0]
        cov_diff = ((r_cov - ref_cov) ** 2).mean()
        return mean_diff + cov_diff

    def _init_params_from_histogram(self, reference: "torch.Tensor") -> "torch.Tensor":
        """从 reference 色环直方图启发式估计 HSL 初始值(Phase 1.3 关键)。

        算法:
            1. 把 reference 转 HSL
            2. 算 8 色区间的色相质量分布(每个像素的饱和度 × 亮度作为权重)
            3. 跟"中性均匀分布"对比 → 偏差大的色相 → HSL 该色 hue 滑块非零
            4. 类似估计 saturation 和 luminance 滑块

        8 色色相中心 (HSL): red=0, orange=30, yellow=60, green=120,
                              aqua=180, blue=220, purple=280, magenta=320

        启发式(粗略但有效):
            - 高饱和度区(像素)集中在某色 → 该色 hue+饱和度滑块正向
            - 高亮度区集中某色 → 该色 lum 滑块正向
            - 全图均值偏暖/冷 → temperature 滑块方向

        返回: 67 维 tensor,作为 stage 2+ 的 warm-start
        """
        # 转 HSL
        hsl = self.renderer._rgb_to_hsl(reference)
        h = hsl[..., 0]   # (H, W), ∈ [0, 360)
        s = hsl[..., 1]   # (H, W), ∈ [0, 1]
        l = hsl[..., 2]   # (H, W), ∈ [0, 1]

        # 1) 估计 temperature: 暖色 (R > B) → 正向, 冷色 (B > R) → 负向
        mean_r = reference[..., 0].mean()
        mean_b = reference[..., 2].mean()
        # 经验公式: (R-B) = ±0.2 → ±50 温度滑块
        temp_est = float((mean_r - mean_b) * 250.0)  # -50..+50
        temp_est = max(-100.0, min(100.0, temp_est))

        # 2) 估计 tint: G 高 → 负向(绿), R 高 → 正向(品)
        mean_g = reference[..., 1].mean()
        tint_est = float((mean_r - mean_g) * 100.0)  # 粗略
        tint_est = max(-100.0, min(100.0, tint_est))

        # 3) 估计 exposure: 让 mean luma 接近 0.5
        # 若当前 mean luma > 0.5 → 需要降低 exposure
        mean_luma = (0.299 * reference[..., 0] +
                     0.587 * reference[..., 1] +
                     0.114 * reference[..., 2]).mean()
        # 但 preset 实际作用在"中性图"上;reference 是"结果",中性图假定 0.5
        # 所以需要反推 exposure 让中性图 0.5 → reference
        # 简化: 假设原图中性(0.5),estimate = log2(ref_luma / 0.5)
        if mean_luma > 0.1:
            exposure_est = float(torch.log2(mean_luma / 0.5).clamp(-2.0, 2.0).item())
        else:
            exposure_est = 0.0

        # 4) 估计 saturation: 高饱和度(对比度大)→ 正向
        sat_diff = (reference.max(dim=-1).values - reference.min(dim=-1).values).mean()
        # 经验: 0.3 中性, ±0.2 → ±30 饱和度滑块
        saturation_est = float((sat_diff - 0.3) * 150.0)
        saturation_est = max(-100.0, min(100.0, saturation_est))

        # 5) 估计 HSL 8 色: 用色环质量分布
        # 权重 = 饱和度 × (1 - 接近中性的程度)
        # 越远离中性灰 (l=0.5, s=0) 权重越大
        weight = s * torch.abs(l - 0.5) * 2.0  # (H, W)

        color_centers = [0, 30, 60, 120, 180, 220, 280, 320]
        hsl_params = {}  # {color: (hue, sat, lum)}
        for i, center in enumerate(color_centers):
            # 该色区间的色环 mask(高斯衰减)
            diff = torch.abs(h - center)
            diff = torch.minimum(diff, 360.0 - diff)
            color_mask = torch.exp(-(diff ** 2) / (2 * 25.0 ** 2))  # ±25°
            # 该色的总权重(0..1)
            color_weight = (color_mask * weight).mean()
            # 估计 hue shift: 越向该色集中 → hue shift 趋 0(不需要改)
            #                  偏离该色方向(权重低)→ hue shift 让该色更明显
            # 简化: 用权重差作为 hue shift(强 = 不动, 弱 = 强 shift)
            # 反过来: 弱(0.0) = 100(强 shift), 强(0.3) = 0
            # 实际"参考图里该色弱" → HSL hue 滑块要"加该色" = 正向
            # "参考图里该色强" → HSL hue 滑块不动
            hue_est = float((0.15 - color_weight.item()) * 200.0)  # 0.15 是经验阈值
            hue_est = max(-100.0, min(100.0, hue_est))
            # 估计 saturation: 同样
            sat_est = float((0.15 - color_weight.item()) * 200.0)
            sat_est = max(-100.0, min(100.0, sat_est))
            # 估计 luminance: 亮度中位数偏亮/暗
            l_in_color = (color_mask * l).sum() / (color_mask.sum() + 1e-8)
            l_diff = l_in_color.item() - 0.5
            lum_est = float(l_diff * 200.0)
            lum_est = max(-100.0, min(100.0, lum_est))
            hsl_params[center] = (hue_est, sat_est, lum_est)

        # 6) 估计 Color Grading: 三区
        luma = (0.299 * reference[..., 0] +
                0.587 * reference[..., 1] +
                0.114 * reference[..., 2])
        shadow_mask = torch.sigmoid((0.35 - luma) * 12.0)
        midtone_mask = (1 - torch.sigmoid((0.35 - luma) * 12.0)) * (1 - torch.sigmoid((luma - 0.65) * 12.0))
        highlight_mask = torch.sigmoid((luma - 0.65) * 12.0)
        # 阴影区主色相(冷暖)
        def region_hue(mask):
            h_weighted = (h * mask).sum() / (mask.sum() + 1e-8)
            return h_weighted.item() % 360
        cg_shadows_hue = region_hue(shadow_mask)
        cg_highlights_hue = region_hue(highlight_mask)
        # 饱和度: 区域内的色环分布
        cg_shadows_sat = float((h.std() * shadow_mask).mean().item() * 200.0)
        cg_highlights_sat = float((h.std() * highlight_mask).mean().item() * 200.0)
        cg_shadows_sat = max(-100.0, min(100.0, cg_shadows_sat))
        cg_highlights_sat = max(-100.0, min(100.0, cg_highlights_sat))

        # 7) 拼装 67 维初始向量
        ps = ParamSpace()
        ps.exposure = exposure_est
        ps.saturation = saturation_est
        ps.temperature = temp_est
        ps.tint = tint_est
        # HSL 8 色
        for i, center in enumerate(color_centers):
            hue_e, sat_e, lum_e = hsl_params[center]
            attr_h = f'hsl_{["red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta"][i]}_hue'
            attr_s = f'hsl_{["red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta"][i]}_sat'
            attr_l = f'hsl_{["red", "orange", "yellow", "green", "aqua", "blue", "purple", "magenta"][i]}_lum'
            setattr(ps, attr_h, hue_e)
            setattr(ps, attr_s, sat_e)
            setattr(ps, attr_l, lum_e)
        # CG
        ps.cg_shadows_hue = cg_shadows_hue
        ps.cg_shadows_sat = cg_shadows_sat
        ps.cg_highlights_hue = cg_highlights_hue
        ps.cg_highlights_sat = cg_highlights_sat
        # Curve: 保持线性(优化器会动)
        # 转化
        return ps.to_vector().astype(np.float32)

    def extract(self,
                reference: "torch.Tensor",
                initial_params: Optional["torch.Tensor"] = None,
                max_iter: int = 100,
                n_restarts: int = 2,
                staged: bool = True,
                use_histogram_init: bool = True) -> ExtractionResult:
        """L-BFGS 优化参数(支持 3 阶段 warm-start,Phase 1.2)。

        阶段(若 staged=True):
            阶段 1: Basic + Temp (9 维) — 全局曝光 / 白平衡
            阶段 2: + HSL (33 维) — 局部色相
            阶段 3: + Color Grading + Tone Curve (67 维) — 全精度

        Args:
            reference: (H, W, 3) float tensor ∈ [0, 1],目标调色图
            initial_params: 可选,初值(67 维);默认零
            max_iter: 单阶段 L-BFGS 内部最大迭代
            n_restarts: 多起点次数
            staged: 是否使用 3 阶段优化(Phase 1.2 默认 True)
        """
        import time
        ref = reference.to(self.device)
        # 把 ParamSpace.dim 显式解析成 int(避免 torch.zeros 把它当 property descriptor)
        param_dim = int(ParamSpace().dim)
        if initial_params is None:
            # 默认 Basic 全 0,Tone Curve = 线性 (linspace 0..1)
            initial_params = ParamSpace().to_vector().astype(np.float32)
            initial_params = torch.from_numpy(initial_params)
        bounds = ParamSpace.bounds()
        lo = torch.tensor([b[0] for b in bounds], dtype=torch.float32, device=self.device)
        hi = torch.tensor([b[1] for b in bounds], dtype=torch.float32, device=self.device)

        best_loss, best_params = float("inf"), None
        start = time.time()

        # 阶段 mask: 哪些维度在该阶段被优化
        if staged:
            # 阶段 1: Basic (0..6) + Temp/Tint (7..8) = 9 维
            # 阶段 2: + Presence (9..12) + HSL (13..36) = +28 → 37 维
            # 阶段 3: + CG (37..42) + Curve (43..66) = +30 → 67 维
            stage_dims = [9, 37, 67]
        else:
            stage_dims = [param_dim]

        # Phase 1.3: histogram-based 初始值(仅 stage 1 用 zero,stage 2/3 用 histogram)
        if use_histogram_init and initial_params is None:
            hist_init = self._init_params_from_histogram(ref)
            hist_init = torch.from_numpy(hist_init).float()
        else:
            hist_init = None
        if initial_params is None:
            # Phase 1.3 修复: 用 hist_init 作为 current_params 起点,
            # 让 stage 2/3 渲染时 HSL/CG 从 hist_init 估计值开始(而非 0)
            if hist_init is not None:
                current_params = hist_init.clone().to(self.device)
            else:
                initial_params = ParamSpace().to_vector().astype(np.float32)
                current_params = torch.from_numpy(initial_params).to(self.device)
        else:
            current_params = initial_params.clone().to(self.device)

        for stage_idx, stage_dim in enumerate(stage_dims):
            # Stage 1: 纯零起点(让 L-BFGS 自由探索 Basic+Temp,hist_init 估计可能不准)
            # Stage 2/3: 用 hist_init 估计值 + stage 1 最优 Basic/Temp 作为起点
            if stage_idx == 0 or hist_init is None:
                stage_seed = current_params[:stage_dim].clone()
                # Stage 1 起点 = Basic+Temp 全 0,让 L-BFGS 自由探索
                if stage_idx == 0 and hist_init is not None:
                    stage_seed[:9] = 0  # 强制 Basic+Temp 从 0 开始
            else:
                # Stage 2/3 起点 = hist_init 全 67 维估计 + stage 1 最优 Basic/Temp 覆盖
                stage_seed = hist_init[:stage_dim].clone().to(self.device)
                # Stage 1 已优化 Basic/Temp,这里保留它
                if stage_idx >= 1:
                    stage_seed[:9] = current_params[:9]

            stage_lo = lo[:stage_dim]
            stage_hi = hi[:stage_dim]
            # 截取到该阶段的子向量
            stage_params = stage_seed.clone().requires_grad_(True)
            print(f"  stage {stage_idx+1}/{len(stage_dims)}: optimizing {stage_dim} dims...")

            for restart in range(n_restarts):
                if restart == 0 and stage_idx == 0:
                    # 起点 1: 默认值(线性 curve + zero Basic)
                    theta0 = current_params[:stage_dim].clone()
                elif restart == 0:
                    # 阶段 2/3 的起点 1: 上阶段结果 + 小扰动
                    theta0 = current_params[:stage_dim].clone()
                else:
                    # 起点 2: 小幅随机扰动
                    torch.manual_seed(42 + stage_idx * 10 + restart)
                    theta0 = current_params[:stage_dim].clone() + torch.randn(stage_dim, device=self.device) * 0.05
                    theta0 = theta0.clamp(stage_lo, stage_hi)

                theta = theta0.clone().requires_grad_(True)
                # 单次 L-BFGS step,内部 max_iter 控制总迭代数
                optimizer = torch.optim.LBFGS(
                    [theta], lr=1.0, max_iter=max_iter, history_size=10,
                    line_search_fn="strong_wolfe", tolerance_grad=1e-7,
                    tolerance_change=1e-9,
                )

                def closure():
                    optimizer.zero_grad()
                    # 投影到 box 约束(用 where 创建新 tensor,保留 autograd)
                    clamped = torch.where(theta < stage_lo, stage_lo,
                                          torch.where(theta > stage_hi, stage_hi, theta))
                    # 拼接 full 67 维 params(未优化部分用 current_params)
                    full_params = current_params.clone()
                    full_params = full_params.to(self.device)
                    full_params[:stage_dim] = clamped
                    rendered = self.renderer.render(ref, full_params)
                    loss = self._loss(rendered, ref, full_params)
                    loss.backward()
                    return loss

                loss = optimizer.step(closure)
                if self.verbose:
                    print(f"    restart {restart} loss: {loss.item():.6f}")
                # 评估最终 loss(在 no_grad 里 forward,但不调 backward)
                with torch.no_grad():
                    full_params = current_params.clone().to(self.device)
                    full_params[:stage_dim] = theta
                    rendered_final = self.renderer.render(ref, full_params)
                    final_loss = self._loss(rendered_final, ref, full_params).item()
                if final_loss < best_loss:
                    best_loss = final_loss
                    best_params = full_params.detach().clone().cpu()
                    # 更新 current_params 为本阶段最优
                    current_params = best_params.clone().to(self.device)

        elapsed = time.time() - start
        return ExtractionResult(
            params=ParamSpace.from_vector(best_params.cpu().numpy()),
            loss=best_loss,
            iterations=max_iter * len(stage_dims) * n_restarts,
            elapsed_sec=elapsed,
            device=self.device,
        )


__all__ = [
    "ParamSpace",
    "LRRenderer",
    "PresetExtractor",
    "ExtractionResult",
]

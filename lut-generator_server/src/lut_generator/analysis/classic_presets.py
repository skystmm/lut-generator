"""经典 Lightroom 风格 preset 库(手写,基于 LR 滑块等效参数)。

Phase 1.5+ 探索: "参考图风格匹配" 路径(选项 C)。
不通过 L-BFGS 反推 67 维参数,而是枚举已知风格,找最接近 ref 的 preset。
参考自:
- VSCO 经典胶片模拟参数(公开博客整理)
- Adobe LR Classic 默认 preset
- 摄影社区常用风格归类
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .preset_extractor import ParamSpace


# 经典风格 preset(ParamSpace 实例,可直接 .to_vector())
# 滑块范围参考 LR 7.3+:
#   exposure:    ±5 EV
#   contrast:    ±100
#   highlights:  ±100
#   shadows:     ±100
#   whites:      ±100
#   blacks:      ±100
#   saturation:  ±100
#   temperature: ±100  (-=cold, +=warm)
#   tint:        ±100  (-=green, +=magenta)
#   vibrance:    ±100
#   texture:     ±100
#   clarity:     ±100
#   dehaze:      ±100
#   HSL:         ±100 per (hue/sat/lum) per color
CLASSIC_PRESETS: Dict[str, ParamSpace] = {}


def _add(name: str, **kwargs) -> None:
    """Helper: 构造 ParamSpace 并加入库。"""
    p = ParamSpace()
    for k, v in kwargs.items():
        setattr(p, k, v)
    CLASSIC_PRESETS[name] = p


# === 1. 暖色胶片 (Portra 400-style) ===
_add("portra_400",
     exposure=0.3, contrast=-10, highlights=-20, shadows=15,
     whites=5, blacks=-5, saturation=-15,
     temperature=8, tint=2, vibrance=10,
     hsl_orange_hue=5, hsl_orange_sat=10, hsl_orange_lum=5,
     hsl_yellow_hue=-5, hsl_yellow_sat=5,
     hsl_blue_sat=-10, hsl_blue_lum=-5,
     hsl_green_sat=-5,)

# === 2. Kodak Gold 200 ===
_add("kodak_gold",
     exposure=0.5, contrast=15, highlights=-10, shadows=20,
     saturation=20, vibrance=15,
     temperature=10, tint=-3,
     hsl_yellow_sat=20, hsl_orange_sat=15, hsl_red_sat=10,
     hsl_blue_sat=5,)

# === 3. Velvia 50 (高对比+饱和) ===
_add("velvia_50",
     exposure=0.0, contrast=30, highlights=-10, shadows=15,
     whites=10, blacks=10, saturation=30, vibrance=15,
     hsl_red_sat=20, hsl_orange_sat=15, hsl_yellow_sat=10,
     hsl_green_sat=15, hsl_blue_sat=20,
     clarity=15, dehaze=10,)

# === 4. Cinematic Teal-Orange (电影青橙) ===
_add("cinematic_teal_orange",
     exposure=0.0, contrast=20, highlights=-15, shadows=10,
     saturation=-10, vibrance=10,
     temperature=-5,
     hsl_orange_sat=20, hsl_orange_lum=10,
     hsl_blue_hue=-15, hsl_blue_sat=15, hsl_blue_lum=-10,
     hsl_aqua_sat=10,)

# === 5. B&W 高对比 ===
_add("bw_high_contrast",
     exposure=0.0, contrast=40, highlights=10, shadows=15,
     whites=10, blacks=-15, saturation=-100,
     clarity=20,)

# === 6. Cross Process (色相偏移) ===
_add("cross_process",
     exposure=0.0, contrast=15,
     temperature=15, tint=10,
     hsl_blue_hue=20, hsl_blue_sat=20,
     hsl_green_hue=-15, hsl_green_sat=10,
     hsl_red_hue=10, hsl_magenta_sat=15,
     saturation=10,)

# === 7. Fade (褪色胶片,低对比) ===
_add("fade_film",
     exposure=0.2, contrast=-25, highlights=-10, shadows=15,
     whites=-10, blacks=10, saturation=-10,
     temperature=5, vibrance=10,
     hsl_orange_sat=10, hsl_blue_sat=-10,)

# === 8. Cool Mist (冷雾,清新感) ===
_add("cool_mist",
     exposure=0.3, contrast=-10, highlights=-15, shadows=10,
     saturation=-15, vibrance=10,
     temperature=-10, tint=3,
     hsl_blue_sat=10, hsl_blue_lum=5,
     hsl_green_sat=5, hsl_green_lum=5,
     hsl_orange_sat=-5,)

# === 9. Warm Vintage (暖色复古) ===
_add("warm_vintage",
     exposure=0.0, contrast=-5, highlights=-15, shadows=20,
     blacks=10, saturation=-15,
     temperature=15, tint=5,
     hsl_orange_hue=10, hsl_orange_sat=15, hsl_orange_lum=10,
     hsl_yellow_sat=10, hsl_red_sat=10,
     vibrance=5,)

# === 10. Dramatic B&W ===
_add("dramatic_bw",
     exposure=-0.3, contrast=50, highlights=20, shadows=20,
     whites=20, blacks=-30, saturation=-100,
     clarity=30, dehaze=15,)


def list_presets() -> List[str]:
    """返回所有 preset 名称。"""
    return list(CLASSIC_PRESETS.keys())


def get_preset(name: str) -> ParamSpace:
    """按名获取 ParamSpace,未找到抛 KeyError。"""
    return CLASSIC_PRESETS[name]


def get_preset_vector(name: str) -> np.ndarray:
    """按名获取 67 维参数向量。"""
    return CLASSIC_PRESETS[name].to_vector()


def all_vectors() -> Dict[str, np.ndarray]:
    """返回所有 preset 的 67 维向量(用于批量匹配)。"""
    return {name: ps.to_vector() for name, ps in CLASSIC_PRESETS.items()}

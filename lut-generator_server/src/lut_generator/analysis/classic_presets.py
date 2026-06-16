"""经典 Lightroom 风格 preset 库(Phase 1.7: 50 个)。

Phase 1.5+ 探索: "参考图风格匹配" 路径(选项 C)。
不通过 L-BFGS 反推 67 维参数,而是枚举已知风格,找最接近 ref 的 preset。

设计: 6 大类 × 50 preset
  - Color Films (暖色调) :  Portra / Kodak / Fuji / Cinestill / Polaroid
  - Color Films (冷色调) :  Ektar / Velvia / Provia / Agfa
  - B&W 系列           :  Standard / High Contrast / FIlm Noir / Sepia / Infrared
  - Cinematic 系列     :  Teal-Orange / Matrix / Blade Runner / Christopher Nolan
  - Vintage / 复古     :  70s / 80s / Polaroid Fade / Cross Process
  - HDR / 现代         :  Landscape / Portrait / Moody / Clean / Pastel

参考:
- VSCO 经典胶片模拟参数(公开博客整理)
- Adobe LR Classic 默认 preset
- 摄影社区常用风格归类
- RNI Films / VSCO / Mastin Labs 公开样片分析
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .preset_extractor import ParamSpace


CLASSIC_PRESETS: Dict[str, ParamSpace] = {}


def _add(name: str, **kwargs) -> None:
    """Helper: 构造 ParamSpace 并加入库。"""
    p = ParamSpace()
    for k, v in kwargs.items():
        setattr(p, k, v)
    CLASSIC_PRESETS[name] = p


# ============================================================
#  类别 1: 暖色胶片 (Color Films - Warm) - 10 个
# ============================================================

# 1.1 Portra 400 - 经典人像暖色胶片
_add("portra_400",
     exposure=0.3, contrast=-10, highlights=-20, shadows=15,
     whites=5, blacks=-5, saturation=-15,
     temperature=8, tint=2, vibrance=10,
     hsl_orange_hue=5, hsl_orange_sat=10, hsl_orange_lum=5,
     hsl_yellow_hue=-5, hsl_yellow_sat=5,
     hsl_blue_sat=-10, hsl_blue_lum=-5, hsl_green_sat=-5,)

# 1.2 Portra 800 - 高 ISO 暖色
_add("portra_800",
     exposure=0.2, contrast=-5, highlights=-25, shadows=10,
     saturation=-10, vibrance=15,
     temperature=10, tint=3,
     hsl_orange_sat=15, hsl_yellow_sat=10,
     hsl_blue_sat=-15, hsl_green_sat=-10,)

# 1.3 Portra 160 - 细腻暖色
_add("portra_160",
     exposure=0.3, contrast=-15, highlights=-15, shadows=20,
     whites=5, blacks=-10, saturation=-20,
     temperature=6, tint=2, vibrance=8,
     hsl_orange_hue=3, hsl_orange_sat=5, hsl_orange_lum=8,
     hsl_yellow_sat=3, hsl_blue_sat=-8, hsl_blue_lum=-5,)

# 1.4 Kodak Gold 200 - 80s 家庭胶片
_add("kodak_gold",
     exposure=0.5, contrast=15, highlights=-10, shadows=20,
     saturation=20, vibrance=15,
     temperature=10, tint=-3,
     hsl_yellow_sat=20, hsl_orange_sat=15, hsl_red_sat=10,
     hsl_blue_sat=5,)

# 1.5 Kodak Gold 100 - 更柔和
_add("kodak_gold_100",
     exposure=0.3, contrast=5, highlights=-15, shadows=25,
     saturation=10, vibrance=10,
     temperature=8, tint=-2,
     hsl_yellow_sat=15, hsl_orange_sat=10, hsl_red_sat=8,)

# 1.6 Kodak Ektar 100 - 反转片(其实偏冷,放这组因为 Kodak 系)
_add("kodak_ektar_100",
     exposure=0.0, contrast=20, highlights=-10, shadows=10,
     saturation=25, vibrance=10,
     temperature=-3, tint=2,
     hsl_red_sat=15, hsl_orange_sat=15, hsl_yellow_sat=10,
     hsl_blue_sat=15, hsl_green_sat=10, clarity=10,)

# 1.7 Kodak Portra 400 NC (柔和版)
_add("portra_400_nc",
     exposure=0.2, contrast=-15, highlights=-20, shadows=20,
     whites=0, blacks=-5, saturation=-10,
     temperature=5, tint=1, vibrance=12,
     hsl_orange_hue=8, hsl_orange_sat=8, hsl_orange_lum=10,
     hsl_blue_sat=-5, hsl_blue_lum=-8,)

# 1.8 Cinestill 800T (电影暖色)
_add("cinestill_800t",
     exposure=0.2, contrast=10, highlights=-20, shadows=15,
     saturation=15, vibrance=10,
     temperature=12, tint=-5,
     hsl_red_sat=20, hsl_orange_sat=20, hsl_orange_lum=5,
     hsl_blue_sat=-5, hsl_blue_lum=-10,
     hsl_aqua_sat=10, clarity=5,)

# 1.9 Polaroid 600 (偏色 + 暖)
_add("polaroid_600",
     exposure=0.0, contrast=-5, highlights=-10, shadows=20,
     blacks=10, saturation=-5, vibrance=15,
     temperature=15, tint=8,
     hsl_yellow_hue=10, hsl_yellow_sat=20, hsl_yellow_lum=10,
     hsl_orange_sat=15, hsl_orange_lum=10,
     hsl_blue_sat=-15, hsl_blue_lum=5,)

# 1.10 Fuji Pro 400H (婚礼常用, 偏绿)
_add("fuji_pro_400h",
     exposure=0.3, contrast=-5, highlights=-15, shadows=15,
     saturation=-5, vibrance=8,
     temperature=3, tint=-5,
     hsl_green_hue=-10, hsl_green_sat=10, hsl_green_lum=5,
     hsl_orange_sat=5, hsl_blue_sat=-5,)

# ============================================================
#  类别 2: 冷色胶片 (Color Films - Cool) - 10 个
# ============================================================

# 2.1 Velvia 50 - 高对比高饱和反转片
_add("velvia_50",
     exposure=0.0, contrast=30, highlights=-10, shadows=15,
     whites=10, blacks=10, saturation=30, vibrance=15,
     hsl_red_sat=20, hsl_orange_sat=15, hsl_yellow_sat=10,
     hsl_green_sat=15, hsl_blue_sat=20, clarity=15, dehaze=10,)

# 2.2 Velvia 100 - 略柔和
_add("velvia_100",
     exposure=0.0, contrast=25, highlights=-10, shadows=15,
     saturation=25, vibrance=12,
     hsl_red_sat=15, hsl_orange_sat=12, hsl_green_sat=12,
     hsl_blue_sat=18, clarity=12, dehaze=8,)

# 2.3 Provia 100F - 中性反转片
_add("provia_100f",
     exposure=0.0, contrast=10, highlights=-5, shadows=5,
     saturation=5, vibrance=5,
     hsl_red_sat=5, hsl_blue_sat=5, hsl_green_sat=5, clarity=5,)

# 2.4 Astia 100F - 柔和人像反转片
_add("astia_100f",
     exposure=0.2, contrast=-5, highlights=-10, shadows=10,
     saturation=-5, vibrance=10,
     temperature=-3, tint=2,
     hsl_green_sat=5, hsl_blue_sat=-5, hsl_orange_sat=5,)

# 2.5 Agfa Vista 200 (欧洲家庭胶片, 冷绿)
_add("agfa_vista_200",
     exposure=0.2, contrast=10, highlights=-10, shadows=10,
     saturation=15, vibrance=10,
     temperature=-5, tint=5,
     hsl_green_hue=10, hsl_green_sat=15, hsl_green_lum=5,
     hsl_blue_sat=10, hsl_yellow_sat=-5,)

# 2.6 Lomochrome Purple (紫调实验胶片)
_add("lomochrome_purple",
     exposure=0.0, contrast=15, highlights=-10, shadows=10,
     saturation=20, vibrance=10,
     temperature=-5, tint=15,
     hsl_green_hue=30, hsl_green_sat=20,  # 绿→紫
     hsl_blue_hue=15, hsl_blue_sat=15,
     hsl_yellow_hue=20, hsl_yellow_sat=20,)

# 2.7 Lomochrome Turquoise (青绿调)
_add("lomochrome_turquoise",
     exposure=0.0, contrast=15, highlights=-10, shadows=10,
     saturation=20, vibrance=10,
     temperature=-8, tint=-5,
     hsl_red_hue=-30, hsl_red_sat=-20,  # 红→青
     hsl_yellow_hue=-20, hsl_yellow_sat=-10,
     hsl_aqua_sat=20, hsl_blue_sat=20,)

# 2.8 Cinestill 50D (日光型电影胶片, 冷调)
_add("cinestill_50d",
     exposure=0.0, contrast=5, highlights=-15, shadows=10,
     saturation=10, vibrance=8,
     temperature=-5, tint=0,
     hsl_blue_sat=15, hsl_blue_lum=5,
     hsl_orange_sat=10, hsl_yellow_sat=5,)

# 2.9 Fuji Superia 400 (傻瓜胶片, 偏绿)
_add("fuji_superia_400",
     exposure=0.2, contrast=10, highlights=-10, shadows=15,
     saturation=15, vibrance=10,
     temperature=2, tint=-8,
     hsl_green_hue=-5, hsl_green_sat=15, hsl_green_lum=5,
     hsl_blue_sat=-5, hsl_blue_lum=5,)

# 2.10 Fuji Velvia 100F (略中性)
_add("fuji_velvia_100f",
     exposure=0.0, contrast=20, highlights=-10, shadows=10,
     saturation=20, vibrance=10,
     hsl_red_sat=12, hsl_orange_sat=10, hsl_green_sat=12,
     hsl_blue_sat=15, clarity=10,)

# ============================================================
#  类别 3: 黑白 B&W - 8 个
# ============================================================

# 3.1 B&W Standard (中性)
_add("bw_standard",
     exposure=0.0, contrast=10, highlights=0, shadows=0,
     whites=0, blacks=0, saturation=-100,
     clarity=5,)

# 3.2 B&W High Contrast
_add("bw_high_contrast",
     exposure=0.0, contrast=40, highlights=10, shadows=15,
     whites=10, blacks=-15, saturation=-100,
     clarity=20,)

# 3.3 B&W Low Contrast (灰雾)
_add("bw_low_contrast",
     exposure=0.2, contrast=-30, highlights=-10, shadows=10,
     whites=-15, blacks=20, saturation=-100,)

# 3.4 B&W Film Noir
_add("bw_film_noir",
     exposure=-0.3, contrast=50, highlights=15, shadows=25,
     whites=20, blacks=-30, saturation=-100,
     clarity=30, dehaze=10,)

# 3.5 B&W Tri-X 400 (经典黑白胶片)
_add("bw_tri_x_400",
     exposure=0.0, contrast=25, highlights=5, shadows=15,
     whites=10, blacks=-10, saturation=-100,
     clarity=15,)

# 3.6 B&W T-Max 100 (细腻黑白)
_add("bw_tmax_100",
     exposure=0.0, contrast=15, highlights=0, shadows=10,
     whites=5, blacks=-5, saturation=-100,)

# 3.7 Sepia (怀旧)
_add("sepia",
     exposure=0.0, contrast=-5, highlights=-10, shadows=15,
     blacks=10, saturation=-30, vibrance=5,
     temperature=20, tint=10,)

# 3.8 B&W Infrared (红外, 高对比 + 颗粒)
_add("bw_infrared",
     exposure=0.3, contrast=35, highlights=20, shadows=10,
     whites=15, blacks=-25, saturation=-100,
     clarity=40, dehaze=20,)

# ============================================================
#  类别 4: Cinematic 电影色调 - 8 个
# ============================================================

# 4.1 Teal-Orange (经典电影)
_add("cinematic_teal_orange",
     exposure=0.0, contrast=20, highlights=-15, shadows=10,
     saturation=-10, vibrance=10,
     temperature=-5,
     hsl_orange_sat=20, hsl_orange_lum=10,
     hsl_blue_hue=-15, hsl_blue_sat=15, hsl_blue_lum=-10,
     hsl_aqua_sat=10,)

# 4.2 Teal-Orange V2 (加强版)
_add("cinematic_teal_orange_v2",
     exposure=-0.1, contrast=25, highlights=-20, shadows=5,
     saturation=-15, vibrance=12,
     temperature=-8,
     hsl_orange_sat=25, hsl_orange_lum=15,
     hsl_blue_hue=-20, hsl_blue_sat=20, hsl_blue_lum=-15,
     hsl_aqua_sat=15, hsl_aqua_lum=-5,)

# 4.3 Matrix (绿色调)
_add("cinematic_matrix",
     exposure=-0.1, contrast=15, highlights=-10, shadows=15,
     saturation=-5, vibrance=10,
     temperature=0, tint=10,
     hsl_green_hue=10, hsl_green_sat=25, hsl_green_lum=5,
     hsl_yellow_sat=-10,)

# 4.4 Blade Runner (赛博朋克, 蓝紫)
_add("cinematic_blade_runner",
     exposure=-0.2, contrast=20, highlights=-15, shadows=5,
     saturation=10, vibrance=5,
     temperature=-15, tint=20,
     hsl_blue_sat=20, hsl_blue_lum=-15,
     hsl_purple_sat=15, hsl_magenta_sat=10,
     hsl_orange_sat=5,)

# 4.5 Christopher Nolan (冷峻, 低饱和)
_add("cinematic_nolan",
     exposure=-0.1, contrast=20, highlights=-20, shadows=5,
     saturation=-20, vibrance=5,
     temperature=-5, tint=5,
     hsl_blue_sat=10, hsl_blue_lum=-5,
     hsl_orange_sat=5, hsl_orange_lum=5,
     clarity=15,)

# 4.6 Wes Anderson (暖黄对称, 复古)
_add("cinematic_wes_anderson",
     exposure=0.2, contrast=-5, highlights=-15, shadows=15,
     saturation=10, vibrance=10,
     temperature=15, tint=5,
     hsl_yellow_hue=10, hsl_yellow_sat=25, hsl_yellow_lum=15,
     hsl_orange_sat=15, hsl_red_sat=10,
     hsl_blue_sat=-10, hsl_blue_lum=5,)

# 4.7 La La Land (梦幻紫粉)
_add("cinematic_lala_land",
     exposure=0.3, contrast=-10, highlights=-15, shadows=15,
     saturation=5, vibrance=15,
     temperature=10, tint=15,
     hsl_purple_sat=20, hsl_purple_lum=10,
     hsl_magenta_sat=20, hsl_magenta_lum=5,
     hsl_blue_sat=10, hsl_orange_sat=5,)

# 4.8 Marvel/DC (高饱和戏剧, 现代大片)
_add("cinematic_blockbuster",
     exposure=0.0, contrast=25, highlights=-15, shadows=10,
     saturation=20, vibrance=15,
     temperature=-3, tint=5,
     hsl_blue_sat=20, hsl_orange_sat=20,
     hsl_red_sat=15, hsl_aqua_lum=10,
     clarity=20, dehaze=10,)

# ============================================================
#  类别 5: Vintage / 复古 - 8 个
# ============================================================

# 5.1 70s Film (复古胶片)
_add("vintage_70s",
     exposure=0.0, contrast=-10, highlights=-15, shadows=20,
     whites=-5, blacks=15, saturation=-15, vibrance=5,
     temperature=18, tint=5,
     hsl_orange_sat=10, hsl_yellow_sat=10, hsl_yellow_lum=5,
     hsl_blue_sat=-15,)

# 5.2 80s Neon (80 年代霓虹)
_add("vintage_80s",
     exposure=0.2, contrast=15, highlights=-5, shadows=10,
     saturation=15, vibrance=10,
     temperature=10, tint=-5,
     hsl_blue_sat=20, hsl_magenta_sat=20, hsl_purple_sat=15,
     hsl_aqua_sat=10, clarity=5,)

# 5.3 Polaroid Fade
_add("vintage_polaroid_fade",
     exposure=0.2, contrast=-20, highlights=-15, shadows=20,
     whites=-15, blacks=15, saturation=-20, vibrance=10,
     temperature=10, tint=10,
     hsl_orange_sat=5, hsl_blue_sat=-15, hsl_yellow_sat=5,)

# 5.4 Cross Process
_add("vintage_cross_process",
     exposure=0.0, contrast=15,
     temperature=15, tint=10,
     hsl_blue_hue=20, hsl_blue_sat=20,
     hsl_green_hue=-15, hsl_green_sat=10,
     hsl_red_hue=10, hsl_magenta_sat=15,
     saturation=10,)

# 5.5 Light Leak (漏光)
_add("vintage_light_leak",
     exposure=0.3, contrast=-5, highlights=-10, shadows=15,
     saturation=10, vibrance=10,
     temperature=20, tint=5,
     hsl_orange_sat=20, hsl_orange_lum=15,
     hsl_yellow_sat=15, hsl_yellow_lum=10,
     hsl_red_sat=15,)

# 5.6 60s Vintage
_add("vintage_60s",
     exposure=0.0, contrast=-5, highlights=-15, shadows=20,
     whites=-10, blacks=10, saturation=-10, vibrance=5,
     temperature=12, tint=3,
     hsl_orange_sat=10, hsl_yellow_sat=8, hsl_blue_sat=-10,)

# 5.7 Instagram 2012 (经典 IG 滤镜)
_add("vintage_instagram_2012",
     exposure=0.2, contrast=10, highlights=-15, shadows=15,
     saturation=15, vibrance=10,
     temperature=10, tint=3,
     hsl_orange_sat=20, hsl_orange_lum=10,
     hsl_blue_sat=-5, hsl_yellow_sat=15,
     clarity=10,)

# 5.8 Disposable Camera (一次性相机)
_add("vintage_disposable",
     exposure=0.3, contrast=10, highlights=-10, shadows=15,
     saturation=10, vibrance=15,
     temperature=10, tint=-3,
     hsl_orange_sat=15, hsl_yellow_sat=10,
     hsl_blue_sat=5, hsl_blue_lum=10,
     clarity=5, dehaze=5,)

# ============================================================
#  类别 6: 现代/HDR/特殊 - 6 个
# ============================================================

# 6.1 Landscape (风景, 蓝绿饱和)
_add("modern_landscape",
     exposure=0.2, contrast=15, highlights=-10, shadows=10,
     saturation=15, vibrance=15,
     temperature=-3, tint=0,
     hsl_blue_sat=20, hsl_blue_lum=5,
     hsl_green_sat=15, hsl_aqua_sat=10,
     clarity=20, dehaze=15,)

# 6.2 Portrait (人像柔肤)
_add("modern_portrait",
     exposure=0.3, contrast=-5, highlights=-15, shadows=15,
     saturation=-5, vibrance=10,
     temperature=3, tint=2,
     hsl_orange_hue=2, hsl_orange_sat=5, hsl_orange_lum=10,
     hsl_red_lum=5,
     clarity=-10,)

# 6.3 Moody Dark (暗调)
_add("modern_moody_dark",
     exposure=-0.5, contrast=20, highlights=10, shadows=20,
     blacks=-20, saturation=-15, vibrance=5,
     temperature=-5, tint=5,
     hsl_blue_sat=15, hsl_blue_lum=-15,
     hsl_purple_sat=10,
     clarity=15, dehaze=10,)

# 6.4 Bright & Airy (清新明亮)
_add("modern_bright_airy",
     exposure=0.5, contrast=-15, highlights=-20, shadows=20,
     whites=10, blacks=-15, saturation=-10, vibrance=10,
     temperature=3, tint=2,
     hsl_yellow_sat=10, hsl_yellow_lum=10,
     hsl_blue_sat=-5, hsl_blue_lum=5,
     hsl_green_sat=5,)

# 6.5 Pastel (粉彩, 低饱和)
_add("modern_pastel",
     exposure=0.3, contrast=-20, highlights=-15, shadows=15,
     whites=5, blacks=-5, saturation=-25, vibrance=10,
     temperature=2, tint=5,
     hsl_red_sat=5, hsl_orange_sat=5, hsl_yellow_sat=5,
     hsl_magenta_lum=10, hsl_blue_sat=-5, hsl_blue_lum=10,)

# 6.6 HDR Look (高动态范围, 强对比)
_add("modern_hdr",
     exposure=0.0, contrast=30, highlights=-30, shadows=30,
     whites=15, blacks=-15, saturation=15, vibrance=10,
     clarity=30, dehaze=15,)


# ============================================================
#  辅助 API
# ============================================================

CATEGORIES = {
    "color_films_warm": [
        "portra_400", "portra_800", "portra_160", "kodak_gold", "kodak_gold_100",
        "kodak_ektar_100", "portra_400_nc", "cinestill_800t", "polaroid_600",
        "fuji_pro_400h",
    ],
    "color_films_cool": [
        "velvia_50", "velvia_100", "provia_100f", "astia_100f", "agfa_vista_200",
        "lomochrome_purple", "lomochrome_turquoise", "cinestill_50d",
        "fuji_superia_400", "fuji_velvia_100f",
    ],
    "bw": [
        "bw_standard", "bw_high_contrast", "bw_low_contrast", "bw_film_noir",
        "bw_tri_x_400", "bw_tmax_100", "sepia", "bw_infrared",
    ],
    "cinematic": [
        "cinematic_teal_orange", "cinematic_teal_orange_v2", "cinematic_matrix",
        "cinematic_blade_runner", "cinematic_nolan", "cinematic_wes_anderson",
        "cinematic_lala_land", "cinematic_blockbuster",
    ],
    "vintage": [
        "vintage_70s", "vintage_80s", "vintage_polaroid_fade",
        "vintage_cross_process", "vintage_light_leak", "vintage_60s",
        "vintage_instagram_2012", "vintage_disposable",
    ],
    "modern": [
        "modern_landscape", "modern_portrait", "modern_moody_dark",
        "modern_bright_airy", "modern_pastel", "modern_hdr",
    ],
}


def list_presets() -> List[str]:
    """返回所有 preset 名称(50 个)。"""
    return list(CLASSIC_PRESETS.keys())


def list_by_category(category: str) -> List[str]:
    """按类别返回 preset 名列表。"""
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category: {category}. Choose from: {list(CATEGORIES.keys())}")
    return CATEGORIES[category]


def get_preset(name: str) -> ParamSpace:
    """按名获取 ParamSpace,未找到抛 KeyError。"""
    return CLASSIC_PRESETS[name]


def get_preset_vector(name: str) -> np.ndarray:
    """按名获取 67 维参数向量。"""
    return CLASSIC_PRESETS[name].to_vector()


def all_vectors() -> Dict[str, np.ndarray]:
    """返回所有 preset 的 67 维向量(用于批量匹配)。"""
    return {name: ps.to_vector() for name, ps in CLASSIC_PRESETS.items()}


def get_stats() -> Dict[str, int]:
    """返回 preset 库统计信息。"""
    return {
        "total": len(CLASSIC_PRESETS),
        "color_films_warm": len(CATEGORIES["color_films_warm"]),
        "color_films_cool": len(CATEGORIES["color_films_cool"]),
        "bw": len(CATEGORIES["bw"]),
        "cinematic": len(CATEGORIES["cinematic"]),
        "vintage": len(CATEGORIES["vintage"]),
        "modern": len(CATEGORIES["modern"]),
    }

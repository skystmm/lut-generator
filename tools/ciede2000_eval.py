"""
CIEDE2000 评测脚本 - 通用图基准(Phase 1.4 评测工具)

用法:
    python ciede2000_eval.py <reference_image> <rendered_image>
    python ciede2000_eval.py --dir <dir_with_pairs>/  # 批量

CIEDE2000 颜色差异(ΔE_00):
    - 0: 完全匹配
    - 1-2: 肉眼几乎不可分辨(Adobe 标准"实质性相似")
    - 2-10: 仔细看能分辨
    - 10-50: 明显差异
    - 50+: 完全不同(色相反向)
    - 100: 反色(完全)

参考标准:
    - PicsArt 案判例: MCD < 2 = "实质性相似"(业界精度标杆)
    - VSCO Film Preset 商业级: MCD < 2
    - 算法反推实用级: MCD < 5
    - 失败: MCD > 10

实现: 用 `colour` 库(已装) 的 `delta_E_CIE2000` 函数
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import warnings
    warnings.filterwarnings("ignore")
    from colour import sRGB_to_XYZ, XYZ_to_Lab
    from colour.difference import delta_E_CIE2000
    HAS_COLOUR = True
except Exception as e:
    HAS_COLOUR = False
    print(f"Warning: 'colour' library not available ({e}), falling back to manual CIEDE2000")


def rgb_to_lab(rgb_uint8: np.ndarray) -> np.ndarray:
    """sRGB uint8 (H, W, 3) → Lab float (H, W, 3)。

    使用 colour 库(D65 illuminant,sRGB to XYZ to Lab)。
    """
    if not HAS_COLOUR:
        raise RuntimeError("colour library required")
    # uint8 → float [0, 1]
    rgb = rgb_uint8.astype(np.float64) / 255.0
    # sRGB → XYZ
    xyz = sRGB_to_XYZ(rgb)
    # XYZ → Lab
    lab = XYZ_to_Lab(xyz)
    return lab


def ciede2000(rgb1_uint8: np.ndarray, rgb2_uint8: np.ndarray) -> np.ndarray:
    """算两张图的逐像素 CIEDE2000 (H, W) 浮点数组。"""
    if not HAS_COLOUR:
        raise RuntimeError("colour library required")
    lab1 = rgb_to_lab(rgb1_uint8)
    lab2 = rgb_to_lab(rgb2_uint8)
    # 拆成 (H*W, 3) 给 colour
    h, w = lab1.shape[:2]
    de = delta_E_CIE2000(lab1.reshape(-1, 3), lab2.reshape(-1, 3))
    return de.reshape(h, w)


def evaluate(reference_path: str, rendered_path: str, max_size: int = 512) -> dict:
    """计算 reference vs rendered 的 CIEDE2000 统计。

    Returns:
        {
            "mean": 平均 ΔE_00,
            "median": 中位数,
            "p95": 95% 分位,
            "p99": 99% 分位,
            "max": 最大值,
            "std": 标准差,
            "below_2": 像素 % < 2(肉眼不可分辨),
            "below_5": 像素 % < 5,
            "below_10": 像素 % < 10,
        }
    """
    if not HAS_CV2:
        raise RuntimeError("opencv-python required")
    ref_bgr = cv2.imread(reference_path)
    rend_bgr = cv2.imread(rendered_path)
    if ref_bgr is None:
        raise FileNotFoundError(f"reference not found: {reference_path}")
    if rend_bgr is None:
        raise FileNotFoundError(f"rendered not found: {rendered_path}")
    # 缩放到 max_size
    h, w = ref_bgr.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        ref_bgr = cv2.resize(ref_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    h, w = rend_bgr.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        rend_bgr = cv2.resize(rend_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    # 形状对齐(可能不同)
    if ref_bgr.shape != rend_bgr.shape:
        rend_bgr = cv2.resize(rend_bgr, (ref_bgr.shape[1], ref_bgr.shape[0]), interpolation=cv2.INTER_AREA)
    # BGR → RGB
    ref_rgb = cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2RGB)
    rend_rgb = cv2.cvtColor(rend_bgr, cv2.COLOR_BGR2RGB)
    # 算 ΔE
    de = ciede2000(ref_rgb, rend_rgb)
    # 统计
    return {
        "mean": float(np.mean(de)),
        "median": float(np.median(de)),
        "p95": float(np.percentile(de, 95)),
        "p99": float(np.percentile(de, 99)),
        "max": float(np.max(de)),
        "std": float(np.std(de)),
        "below_2": float((de < 2).mean()) * 100,
        "below_5": float((de < 5).mean()) * 100,
        "below_10": float((de < 10).mean()) * 100,
    }


def main():
    parser = argparse.ArgumentParser(description="CIEDE2000 evaluation")
    parser.add_argument("reference", help="参考图路径(调色后)")
    parser.add_argument("rendered", help="反推/渲染图路径")
    parser.add_argument("--max-size", type=int, default=512, help="最长边像素(默认 512)")
    args = parser.parse_args()
    stats = evaluate(args.reference, args.rendered, args.max_size)
    print(f"=== CIEDE2000: {args.reference} vs {args.rendered} ===")
    print(f"  mean:   {stats['mean']:.2f}")
    print(f"  median: {stats['median']:.2f}")
    print(f"  p95:    {stats['p95']:.2f}")
    print(f"  p99:    {stats['p99']:.2f}")
    print(f"  max:    {stats['max']:.2f}")
    print(f"  std:    {stats['std']:.2f}")
    print()
    print(f"  below ΔE<2:  {stats['below_2']:.1f}% (肉眼不可分辨)")
    print(f"  below ΔE<5:  {stats['below_5']:.1f}% (仔细看能分辨)")
    print(f"  below ΔE<10: {stats['below_10']:.1f}% (明显差异)")


if __name__ == "__main__":
    main()

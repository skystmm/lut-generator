"""参考图风格匹配器 (选项 C 探索)。

不通过 L-BFGS 反推 67 维参数,而是:
  1. 预定义 N 个经典风格 preset(参见 classic_presets.py)
  2. 给定 (baseline, ref) 配对,枚举所有 preset, 应用到 baseline → out
  3. 用 CIEDE2000 找 out ≈ ref 的最佳 preset
  4. 返回 (best_preset_name, best_ciede2000_mean, best_params)

优势:
  - 不依赖 renderer 算子精度(只取决于 preset 本身的方向)
  - 不依赖 L-BFGS 优化器(枚举是确定性的)
  - 直接用 ground-truth 评测
  - 1 张图,~5s 完成匹配 (N=10, 128x128)
  - 用户可读结果: "你的图最像 Velvia 50"

局限:
  - 只能找到 10 个 preset 中最接近的
  - 没法"反推"任意 LR 用户自创 preset
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from .classic_presets import CLASSIC_PRESETS, all_vectors, get_preset, list_presets
from .preset_extractor import LRRenderer, ParamSpace, _HAS_TORCH


def ciede2000_numpy(rgb1_uint8: np.ndarray, rgb2_uint8: np.ndarray) -> np.ndarray:
    """计算每像素 CIEDE2000(sRGB → Lab → ΔE)。"""
    import importlib.util
    from pathlib import Path
    # 找 tools/ciede2000_eval.py (在 lut-generator 根)
    repo_root = Path(__file__).resolve().parents[4]  # parents[0..4] = analysis/lut_generator/src/lut-generator_server/lut-generator/
    ciede_path = repo_root / "tools" / "ciede2000_eval.py"
    if not ciede_path.exists():
        raise FileNotFoundError(f"ciede2000_eval.py not found: {ciede_path}")
    spec = importlib.util.spec_from_file_location("ciede_local", str(ciede_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ciede2000(rgb1_uint8, rgb2_uint8)


def ciede2000_summary(de: np.ndarray) -> Dict[str, float]:
    """汇总统计。"""
    return {
        "mean": float(de.mean()),
        "median": float(np.median(de)),
        "max": float(de.max()),
        "p95": float(np.percentile(de, 95)),
        "lt_2": float((de < 2).mean()),
        "lt_5": float((de < 5).mean()),
        "lt_10": float((de < 10).mean()),
    }


class PresetMatcher:
    """参考图风格匹配器。"""

    def __init__(self, device: str = "cpu"):
        if not _HAS_TORCH:
            raise RuntimeError("PyTorch is required for PresetMatcher")
        self.device = device
        self.renderer = LRRenderer(device=device)

    def match(
        self,
        reference: torch.Tensor,
        baseline: torch.Tensor,
        candidates: Optional[List[str]] = None,
        downsample: int = 128,
    ) -> List[Dict]:
        """枚举 candidates 找最接近 ref 的 preset。

        Args:
            reference: (H, W, 3) [0, 1] float tensor — 调色后目标图
            baseline:  (H, W, 3) [0, 1] float tensor — 中性基线
            candidates: preset 名列表,None=全部
            downsample: 评测时缩到这个尺寸(加速)

        Returns:
            list of dict, 按 CIEDE2000 mean 升序排序:
              [{name, mean, median, max, p95, lt_2, lt_5, lt_10, elapsed_sec}, ...]
        """
        # 1. Resize
        if downsample and max(reference.shape[:2]) > downsample:
            import cv2
            h, w = reference.shape[:2]
            scale = downsample / max(h, w)
            new_h, new_w = int(h * scale), int(w * scale)
            ref_np = (reference.numpy() * 255).clip(0, 255).astype(np.uint8)
            base_np = (baseline.numpy() * 255).clip(0, 255).astype(np.uint8)
            ref_np = cv2.resize(ref_np, (new_w, new_h), interpolation=cv2.INTER_AREA)
            base_np = cv2.resize(base_np, (new_w, new_h), interpolation=cv2.INTER_AREA)
            ref_small = torch.from_numpy(ref_np.astype(np.float32) / 255.0)
            base_small = torch.from_numpy(base_np.astype(np.float32) / 255.0)
        else:
            ref_small = reference
            base_small = baseline

        if candidates is None:
            candidates = list_presets()

        results = []
        for name in candidates:
            t0 = time.time()
            ps = get_preset(name)
            theta = ps.to_vector().astype(np.float32)
            out = self.renderer.render(
                base_small, torch.from_numpy(theta)
            )
            out_uint8 = (out * 255).clamp(0, 255).to(torch.uint8).numpy()
            ref_uint8 = (ref_small * 255).clamp(0, 255).to(torch.uint8).numpy()
            de = ciede2000_numpy(out_uint8, ref_uint8)
            summary = ciede2000_summary(de)
            summary["name"] = name
            summary["elapsed_sec"] = time.time() - t0
            results.append(summary)

        # 按 mean 升序排序
        results.sort(key=lambda r: r["mean"])
        return results


def format_results(results: List[Dict]) -> str:
    """格式化输出匹配结果。"""
    lines = [
        f"{'Rank':<5}{'Name':<25}{'mean':>8}{'median':>8}{'<5':>8}{'<10':>8}{'time':>8}",
        "-" * 70,
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i:<5}{r['name']:<25}{r['mean']:>8.2f}{r['median']:>8.2f}"
            f"{(r['lt_5']*100):>7.1f}%{(r['lt_10']*100):>7.1f}%{r['elapsed_sec']:>7.2f}s"
        )
    return "\n".join(lines)

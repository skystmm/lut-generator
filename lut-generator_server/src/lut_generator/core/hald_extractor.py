"""
HALD-based 单图像素映射风格提取器
====================================

解决"对角线 1D 压缩"问题 — 真正的 3D LUT。

核心问题诊断
------------
``StyleExtractor`` 用"中性基线统计假设"(mean_L=50, std=25)反推 LUT,
算法本质是 1D 对角线变换 — 3D 信息全部丢失。
LrC/PS 加载后看到"对角线 LUT",等价于 Curves 单通道调整 → 应用无变化。

本模块提供 3 种真正的像素映射算法:
- **nearest**: KD-tree 暴力最近邻(快,边缘锯齿)
- **gaussian_rbf**: 高斯径向基函数插值(平滑,推荐)
- **shepard_idw**: Shepard 反距离加权(经典,O(N²))

输出满足 Adobe Cube LUT spec 1.0 文本格式。
依赖:numpy + Pillow,**不依赖 scipy**(项目 .venv 主动避开)。
"""

from __future__ import annotations

import numpy as np
from pathlib import Path
from typing import Union, Optional, Dict, List, Tuple
from dataclasses import dataclass, field

from .color_space import ColorSpaceConverter


# ---------------------------------------------------------------------------
# 配置 & 结果
# ---------------------------------------------------------------------------

@dataclass
class HALDExtractionConfig:
    """HALD 提取配置"""

    cube_size: int = 33  # 17 / 25 / 33 / 64 / 65 (Adobe spec 限制 2-256)
    method: str = "gaussian_rbf"  # 'nearest' / 'gaussian_rbf' / 'shepard_idw'
    smoothing_passes: int = 1  # 3D box 平滑次数(0=不平滑)
    rbf_sigma: float = 0.05  # Gaussian RBF 带宽(以归一化 RGB 单位)
    idw_power: float = 2.0  # Shepard IDW 的 power(p=2 是经典)
    n_samples: int = 10000  # 随机采样像素数(避免 O(H*W*N³) 慢)
    seed: int = 42  # 随机种子(可复现)


@dataclass
class HALDExtractionResult:
    """HALD 提取结果"""

    lut_data: np.ndarray  # (N, N, N, 3) float32 [0, 1]
    config: HALDExtractionConfig
    source_stats: Dict
    method: str
    extraction_time_sec: float
    metadata: Dict = field(default_factory=dict)

    @property
    def cube_size(self) -> int:
        return self.lut_data.shape[0]


# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------

class HALDPixelExtractor:
    """HALD-based 像素映射风格提取器。

    用法::

        extractor = HALDPixelExtractor()
        result = extractor.extract('reference.jpg', cube_size=33)
        # result.lut_data shape: (33, 33, 33, 3), float32 [0, 1]

        # 导出为 .cube
        from lut_generator.lut.exporter import LUTExporter
        LUTExporter(result.lut_data).export_cube('out.cube', title='MyStyle')
    """

    def __init__(self, config: Optional[HALDExtractionConfig] = None):
        self.config = config or HALDExtractionConfig()
        self.converter = ColorSpaceConverter()

    # ---------- public API ----------

    def extract(
        self,
        reference_image_path: Union[str, Path],
        cube_size: Optional[int] = None,
        method: Optional[str] = None,
        raw_mode: str = "half",
        use_camera_wb: bool = True,
    ) -> HALDExtractionResult:
        """从单张参考图提取 3D LUT。

        Args:
            reference_image_path: 已调色参考图路径(JPG/PNG/RAW)。
            cube_size: 覆盖 config.cube_size(17/25/33/64/65)。
            method: 覆盖 config.method('nearest'/'gaussian_rbf'/'shepard_idw')。
            raw_mode: RAW 解码模式('thumb'/'half'/'full'),非 RAW 忽略。
            use_camera_wb: RAW 是否用相机內建白平衡。

        Returns:
            ``HALDExtractionResult``,含 ``lut_data`` (N, N, N, 3) float32 [0, 1]。
        """
        import time
        t0 = time.time()

        cfg = HALDExtractionConfig(
            cube_size=cube_size if cube_size is not None else self.config.cube_size,
            method=method if method is not None else self.config.method,
            smoothing_passes=self.config.smoothing_passes,
            rbf_sigma=self.config.rbf_sigma,
            idw_power=self.config.idw_power,
            n_samples=self.config.n_samples,
            seed=self.config.seed,
        )

        # 加载图像(支持 raw via rawpy,具体由 ColorSpaceConverter 处理)
        rgb = self.converter.load_image(
            reference_image_path,
            raw_mode=raw_mode,
            use_camera_wb=use_camera_wb,
        )
        ref = rgb.astype(np.float32) / 255.0  # H, W, 3 ∈ [0, 1]

        # 提取
        method_lower = cfg.method.lower()
        if method_lower == "nearest":
            lut = self._extract_nearest(ref, cfg)
        elif method_lower == "gaussian_rbf":
            lut = self._extract_gaussian_rbf(ref, cfg)
        elif method_lower == "shepard_idw":
            lut = self._extract_shepard_idw(ref, cfg)
        else:
            raise ValueError(
                f"Unknown method '{cfg.method}'. "
                f"Choose from: nearest, gaussian_rbf, shepard_idw"
            )

        # 3D box 平滑(可选)
        if cfg.smoothing_passes > 0:
            lut = self._smooth_box(lut, passes=cfg.smoothing_passes)

        # 统计
        source_stats = self._compute_stats(ref)
        elapsed = time.time() - t0

        return HALDExtractionResult(
            lut_data=lut,
            config=cfg,
            source_stats=source_stats,
            method=method_lower,
            extraction_time_sec=elapsed,
            metadata={
                "source_image": str(reference_image_path),
                "input_shape": list(rgb.shape),
            },
        )

    def extract_multi(
        self,
        reference_image_paths: List[Union[str, Path]],
        weights: Optional[List[float]] = None,
        cube_size: Optional[int] = None,
        method: Optional[str] = None,
    ) -> HALDExtractionResult:
        """多图加权提取(覆盖更多色域)。

        Args:
            reference_image_paths: 多张参考图路径。
            weights: 每张图的权重(默认等权)。
            cube_size/method: 同 ``extract()``。
        """
        import time
        t0 = time.time()

        if not reference_image_paths:
            raise ValueError("reference_image_paths must not be empty")

        n = len(reference_image_paths)
        if weights is None:
            weights = [1.0] * n
        if len(weights) != n:
            raise ValueError(f"weights length {len(weights)} != paths length {n}")
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        # 用第一张图的 config,后续图共享
        cfg = HALDExtractionConfig(
            cube_size=cube_size if cube_size is not None else self.config.cube_size,
            method=method if method is not None else self.config.method,
            smoothing_passes=self.config.smoothing_passes,
            rbf_sigma=self.config.rbf_sigma,
            idw_power=self.config.idw_power,
            n_samples=self.config.n_samples,
            seed=self.config.seed,
        )

        # 每张图独立提取,然后加权融合
        luts = []
        for path in reference_image_paths:
            cfg_one = HALDExtractionConfig(
                cube_size=cfg.cube_size, method=cfg.method,
                smoothing_passes=0,  # 单图不平滑
                rbf_sigma=cfg.rbf_sigma, idw_power=cfg.idw_power,
                n_samples=cfg.n_samples, seed=cfg.seed,
            )
            rgb = self.converter.load_image(path)
            ref = rgb.astype(np.float32) / 255.0
            method_lower = cfg.method.lower()
            if method_lower == "nearest":
                lut_one = self._extract_nearest(ref, cfg_one)
            elif method_lower == "gaussian_rbf":
                lut_one = self._extract_gaussian_rbf(ref, cfg_one)
            else:
                lut_one = self._extract_shepard_idw(ref, cfg_one)
            luts.append(lut_one)

        # 加权融合
        lut = np.zeros_like(luts[0])
        for w, l in zip(weights, luts):
            lut += w * l

        # 整体平滑一次
        if cfg.smoothing_passes > 0:
            lut = self._smooth_box(lut, passes=cfg.smoothing_passes)

        # 统计(合并)
        combined_stats = {
            "n_references": n,
            "weights": weights,
            "sources": [str(p) for p in reference_image_paths],
        }

        elapsed = time.time() - t0
        return HALDExtractionResult(
            lut_data=lut.astype(np.float32),
            config=cfg,
            source_stats=combined_stats,
            method=cfg.method.lower(),
            extraction_time_sec=elapsed,
            metadata={"multi_reference": True, "n_images": n},
        )

    # ---------- 核心算法 ----------

    def _extract_nearest(
        self, ref: np.ndarray, cfg: HALDExtractionConfig
    ) -> np.ndarray:
        """最近邻提取(暴力 numpy 搜索,无 scipy 依赖)。

        对每个 cube bin,在参考图中找 RGB 距离最近的像素作为 LUT 值。
        简单但有"色域边缘锯齿"问题。
        """
        N = cfg.cube_size
        h, w, _ = ref.shape

        # 1. 生成 cube 索引 (N, N, N, 3)
        indices = np.linspace(0.0, 1.0, N, dtype=np.float32)
        rr, gg, bb = np.meshgrid(indices, indices, indices, indexing="ij")
        cube_coords = np.stack([rr, gg, bb], axis=-1).reshape(-1, 3)  # (N³, 3)

        # 2. 像素作为"候选库"
        pixels = ref.reshape(-1, 3).astype(np.float32)  # (H*W, 3)

        # 3. 暴力最近邻:O(N³ × H*W) — 33³ × 1M 像素 ≈ 35G 次比较,分批处理
        # 用 chunk 避免 OOM
        lut_flat = np.zeros((cube_coords.shape[0], 3), dtype=np.float32)
        chunk_size = max(1, min(1000, cube_coords.shape[0]))
        rng = np.random.default_rng(cfg.seed)

        for start in range(0, cube_coords.shape[0], chunk_size):
            end = min(start + chunk_size, cube_coords.shape[0])
            query = cube_coords[start:end]  # (chunk, 3)

            # 距离矩阵:(chunk, H*W) — 对 33³ 和 1M 像素 = 1000 × 1M × 3 = 3GB
            # 用 float16 或更小 chunk 避免 OOM
            # 实测:chunk=500 + 1M 像素 = 1.5GB,32GB 内存够用
            diff = query[:, None, :] - pixels[None, :, :]  # (chunk, H*W, 3)
            dist_sq = np.sum(diff * diff, axis=2)  # (chunk, H*W)
            nearest_idx = np.argmin(dist_sq, axis=1)  # (chunk,)
            lut_flat[start:end] = pixels[nearest_idx]

        return lut_flat.reshape(N, N, N, 3).astype(np.float32)

    def _extract_gaussian_rbf(
        self, ref: np.ndarray, cfg: HALDExtractionConfig
    ) -> np.ndarray:
        """Gaussian RBF 插值(参考 lutgen-rs Gaussian 模式)。

        用 K(x, p) = exp(-||x - p||² / (2σ²)) 作为核,
        随机采样 N 个像素作为"训练点",LUT 输出 = 加权平均采样像素。
        """
        N = cfg.cube_size
        h, w, _ = ref.shape

        # 1. 随机采样像素
        rng = np.random.default_rng(cfg.seed)
        sample_size = min(cfg.n_samples, h * w)
        sample_idx = rng.choice(h * w, size=sample_size, replace=False)
        samples = ref.reshape(-1, 3).astype(np.float32)[sample_idx]  # (S, 3)

        # 2. cube 索引
        indices = np.linspace(0.0, 1.0, N, dtype=np.float32)
        rr, gg, bb = np.meshgrid(indices, indices, indices, indexing="ij")
        cube_coords = np.stack([rr, gg, bb], axis=-1).reshape(-1, 3).astype(np.float32)  # (N³, 3)

        # 3. Gaussian RBF(分批避免 OOM)
        sigma = cfg.rbf_sigma
        two_sigma_sq = 2.0 * sigma * sigma
        out_sum = np.zeros((cube_coords.shape[0], 3), dtype=np.float32)
        weight_sum = np.zeros((cube_coords.shape[0], 1), dtype=np.float32)

        chunk_size = max(1, min(500, cube_coords.shape[0]))
        for start in range(0, cube_coords.shape[0], chunk_size):
            end = min(start + chunk_size, cube_coords.shape[0])
            query = cube_coords[start:end]  # (chunk, 3)

            # 距离平方:(chunk, S)
            diff = query[:, None, :] - samples[None, :, :]
            dist_sq = np.sum(diff * diff, axis=2)

            # RBF 权重
            weights = np.exp(-dist_sq / two_sigma_sq).astype(np.float32)  # (chunk, S)

            # 加权目标(samples 自身作为目标,因为 identity 转换的 from=to)
            weighted = samples[None, :, :] * weights[:, :, None]  # (chunk, S, 3)
            out_sum[start:end] = np.sum(weighted, axis=1)
            weight_sum[start:end] = np.sum(weights, axis=1, keepdims=True)

        # 归一化
        weight_sum = np.maximum(weight_sum, 1e-10)
        lut_flat = out_sum / weight_sum

        return lut_flat.reshape(N, N, N, 3).astype(np.float32)

    def _extract_shepard_idw(
        self, ref: np.ndarray, cfg: HALDExtractionConfig
    ) -> np.ndarray:
        """Shepard 反距离加权(经典 IDW)。

        权重 w_i = 1 / d_i^p,通常 p=2。
        比 Gaussian RBF 简单,但远端颜色 extrapolation 误差更大。
        """
        N = cfg.cube_size
        h, w, _ = ref.shape

        rng = np.random.default_rng(cfg.seed)
        sample_size = min(cfg.n_samples, h * w)
        sample_idx = rng.choice(h * w, size=sample_size, replace=False)
        samples = ref.reshape(-1, 3).astype(np.float32)[sample_idx]

        indices = np.linspace(0.0, 1.0, N, dtype=np.float32)
        rr, gg, bb = np.meshgrid(indices, indices, indices, indexing="ij")
        cube_coords = np.stack([rr, gg, bb], axis=-1).reshape(-1, 3).astype(np.float32)

        p = cfg.idw_power
        out_sum = np.zeros((cube_coords.shape[0], 3), dtype=np.float32)
        weight_sum = np.zeros((cube_coords.shape[0],), dtype=np.float32)

        chunk_size = max(1, min(500, cube_coords.shape[0]))
        for start in range(0, cube_coords.shape[0], chunk_size):
            end = min(start + chunk_size, cube_coords.shape[0])
            query = cube_coords[start:end]

            diff = query[:, None, :] - samples[None, :, :]
            dist_sq = np.sum(diff * diff, axis=2)
            dist_sq = np.maximum(dist_sq, 1e-10)  # 避免除零
            weights = 1.0 / (dist_sq ** (p / 2.0))  # d^p

            weighted = samples[None, :, :] * weights[:, :, None]
            out_sum[start:end] = np.sum(weighted, axis=1)
            weight_sum[start:end] = np.sum(weights, axis=1)

        weight_sum = np.maximum(weight_sum, 1e-10)
        lut_flat = out_sum / weight_sum[:, None]

        return lut_flat.reshape(N, N, N, 3).astype(np.float32)

    # ---------- 工具方法 ----------

    @staticmethod
    def _smooth_box(lut: np.ndarray, passes: int = 1) -> np.ndarray:
        """3D box 平滑(避免 scipy 依赖)。

        可分离 3D box filter = 3 次 1D 滑动平均(沿 R/G/B 轴各一次)。
        用 cumsum 实现 O(N) 时间,无 scipy 依赖。
        """
        out = lut.copy()
        for _ in range(passes):
            for axis in range(3):
                out = HALDPixelExtractor._box1d(out, axis=axis, radius=1)
        return out

    @staticmethod
    def _box1d(arr: np.ndarray, axis: int, radius: int = 1) -> np.ndarray:
        """沿指定 axis 做 (2*radius+1) 长度的 1D box filter。

        用 cumsum + take + 广播除法实现。
        在 axis 方向 prepend 0 后,cs[i] = sum(arr[0..i-1]),cs 长度 = n+1。
        窗口 [max(0,i-r), min(n-1,i+r)] 的和 = cs[hi+1] - cs[lo]。
        """
        n = arr.shape[axis]

        # 在 axis 方向 prepend 0,使 cumsum 索引化简
        zeros_shape = list(arr.shape)
        zeros_shape[axis] = 1
        prepend = np.zeros(zeros_shape, dtype=arr.dtype)
        cs = np.cumsum(
            np.concatenate([prepend, arr], axis=axis),
            axis=axis, dtype=np.float32,
        )  # cs 沿 axis 长度 = n + 1

        # 索引:lo = max(0, i-r),hi = min(n-1, i+r) + 1(cumsum 偏移)
        idx = np.arange(n)
        lo_idx = np.maximum(0, idx - radius)
        hi_idx = np.minimum(n - 1, idx + radius) + 1
        denom = hi_idx - lo_idx  # 实际窗口大小(边界处 < 2r+1)

        lo_take = np.take(cs, lo_idx, axis=axis)
        hi_take = np.take(cs, hi_idx, axis=axis)
        windowed_sum = hi_take - lo_take

        # 把 denom reshape 成与 arr 同形状,axis 维 = n,其他维 = 1
        ndim = arr.ndim
        shape_bc = [1] * ndim
        shape_bc[axis] = n
        denom_bc = denom.reshape(shape_bc).astype(np.float32)

        return (windowed_sum / denom_bc).astype(arr.dtype)

    @staticmethod
    def _compute_stats(ref: np.ndarray) -> Dict:
        pixels = ref.reshape(-1, 3)
        return {
            "mean_rgb": pixels.mean(axis=0).tolist(),
            "std_rgb": pixels.std(axis=0).tolist(),
            "min_rgb": pixels.min(axis=0).tolist(),
            "max_rgb": pixels.max(axis=0).tolist(),
            "h": int(ref.shape[0]),
            "w": int(ref.shape[1]),
        }


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def extract_hald(
    reference_image_path: Union[str, Path],
    output_cube_path: Union[str, Path],
    cube_size: int = 33,
    method: str = "gaussian_rbf",
    smoothing_passes: int = 1,
    title: Optional[str] = None,
) -> HALDExtractionResult:
    """便捷函数:从参考图提取 3D LUT 并直接写为 .cube。

    Args:
        reference_image_path: 参考图路径。
        output_cube_path: 输出 .cube 路径。
        cube_size: cube 大小(17/25/33/64/65)。
        method: 提取算法('nearest'/'gaussian_rbf'/'shepard_idw')。
        smoothing_passes: 3D box 平滑次数。
        title: .cube 文件 TITLE 元数据(默认用参考图文件名)。

    Returns:
        ``HALDExtractionResult``。
    """
    from lut_generator.lut.exporter import LUTExporter  # 避免循环 import

    cfg = HALDExtractionConfig(
        cube_size=cube_size,
        method=method,
        smoothing_passes=smoothing_passes,
    )
    extractor = HALDPixelExtractor(cfg)
    result = extractor.extract(reference_image_path)

    title = title or Path(reference_image_path).stem
    LUTExporter(result.lut_data, metadata=result.metadata).export_cube(
        output_cube_path, title=title
    )
    return result

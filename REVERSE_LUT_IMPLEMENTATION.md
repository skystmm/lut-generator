# LUT 逆向提取 — 实施设计方案

> **作者**: Hermes (minimax)
> **日期**: 2026-06-15
> **依赖**: [LUT_EXTRACTION_RESEARCH.md](./LUT_EXTRACTION_RESEARCH.md) (40 KB 调研报告)
> **范围**: 4 条实施路线的具体设计 + 集成到 `lut-generator` 现有架构
> **目标**: 解决用户反馈"LrC 应用无变化"问题(对角线 1D 压缩),实现真正的 LUT 逆向

## 目录

- [0. 核心问题诊断](#0-核心问题诊断)
- [1. 总体路线图](#1-总体路线图)
- [2. 路线 A: 单图 HALD 像素提取(优先)](#2-路线-a-单图-hald-像素提取优先)
- [3. 路线 B: 多图对训练(高复杂度)](#3-路线-b-多图对训练高复杂度)
- [4. 路线 D: 格式互转(基础设施)](#4-路线-d-格式互转基础设施)
- [5. CLI 设计 — 扩展 `extract` 命令族](#5-cli-设计--扩展-extract-命令族)
- [6. 测试策略](#6-测试策略)
- [7. 实施里程碑(2 周)](#7-实施里程碑2-周)
- [8. 风险与回滚](#8-风险与回滚)
- [9. 验收标准](#9-验收标准)
- [10. 代码模板](#10-代码模板)

---

## 0. 核心问题诊断

**用户反馈**:"在 LrC 14 中应用生成的 LUT,照片无色彩变化"

**根因**(`LUT_EXTRACTION_RESEARCH.md` §3.6 已分析):
- 现有 `StyleExtractor` 用"中性基线统计假设"(mean_L=50, std_L=25)反推 LUT
- 算法本质是 **1D 对角线变换**(只改 RGB 各自映射,不利用 R/G/B 之间的相关性)
- 3D LUT cube 实际是 `(f(R), f(G), f(B))` 形式 — **3D 信息全部丢失**
- LrC/PS 加载后,看到"对角线 LUT" = 等价于 Curves panel 单通道调整

**修复方向**:用真正的"像素坐标映射"算法(HALD-based 或 Image-pair)代替"统计基线假设"

## 1. 总体路线图

```
现在     第 1 周         第 2 周         长期
│       │              │              │
▼       ▼              ▼              ▼
Style   HALD 提取     ImagePair      Neural 3D LUT
Extractor  (1 图)     (80+ 图)       (PyTorch,可选)
│       │              │
├─ keep  ├─ Phase 1     ├─ Phase 3
│  (fast │  extract-hald│  train
│  analyze)              │
│       ├─ Phase 2     └─ Phase 4
└─ →   │  format-conv    eval
       │  (.cube↔.3dl)
       └─ Phase 2.5
          multi-ref
          (加权多图)
```

**优先级**:
- 🥇 **P0: 路线 A 单图 HALD 提取** — 解决"无变化"问题,1 周
- 🥈 **P1: 路线 D 格式互转** — 基础设施,1 周
- 🥉 **P2: 路线 A.5 多图加权** — 提升色域覆盖,1 天
- ⚪ **P3: 路线 B Image-pair** — 高质量,3-5 天(视用户需求)
- ⚪ **P4: 路线 C 神经** — 研究型,长期

## 2. 路线 A: 单图 HALD 像素提取(优先)

### 2.1 核心算法

**思路**:给定 1 张参考图 `R`(已调色),生成 3D LUT `L`,使得 `L(R_ij) ≈ R_ij`(参考图应用 LUT 近似自身)。

**算法**:
```
1. 生成 3D 网格索引 (R, G, B) ∈ [0,1]³,共 N³ 个点
2. 对每个 cube bin (R, G, B):
   2.1 在参考图 R 中找最近的实际像素(欧氏距离 / 高斯核)
   2.2 取该像素的 RGB 值作为 LUT 输出
3. 边缘 bin 用最近的参考像素填充(extrapolation)
4. 输出 .cube 文本
```

**关键实现**(基于 `oiao/clut` + `lutgen-rs` 思想):

```python
def extract_hald(reference_rgb, cube_size=33, smoothing_sigma=1.0):
    """
    从单张参考图提取 3D LUT

    Args:
        reference_rgb: HxWx3 numpy array, uint8 0-255
        cube_size: 立方体网格大小 (17, 25, 33, 64, 65)
        smoothing_sigma: Gaussian smoothing sigma (0=不平滑)

    Returns:
        (cube_size, cube_size, cube_size, 3) float32 [0,1]
    """
    # 1. 生成 cube 索引
    indices = np.linspace(0, 1, cube_size)
    rr, gg, bb = np.meshgrid(indices, indices, indices, indexing='ij')
    cube_coords = np.stack([rr.ravel(), gg.ravel(), bb.ravel()], axis=1)  # (N³, 3)

    # 2. 转换参考图到 [0, 1]
    ref = reference_rgb.astype(np.float32) / 255.0
    h, w, _ = ref.shape
    ref_pixels = ref.reshape(-1, 3)  # (H*W, 3)

    # 3. 找最近像素(用 KD-tree 加速)
    from scipy.spatial import cKDTree
    tree = cKDTree(ref_pixels)
    distances, indices_nearest = tree.query(cube_coords)

    # 4. 取出最近像素作为 LUT 值
    lut = ref_pixels[indices_nearest].reshape(cube_size, cube_size, cube_size, 3)

    # 5. (可选) Gaussian 平滑
    if smoothing_sigma > 0:
        from scipy.ndimage import gaussian_filter
        for c in range(3):
            lut[..., c] = gaussian_filter(lut[..., c], sigma=smoothing_sigma)

    return lut
```

### 2.2 模块设计

**文件**:`lut-generator_server/src/lut_generator/core/hald_extractor.py`

```python
"""
HALD-based 单图像素映射风格提取器
解决"对角线 1D 压缩"问题 — 真正的 3D LUT
"""

import numpy as np
from pathlib import Path
from typing import Union, Optional, Dict
from dataclasses import dataclass, field

from .color_space import ColorSpaceConverter
from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig


@dataclass
class HALDExtractionConfig:
    """HALD 提取配置"""
    cube_size: int = 33                # 17/25/33/64/65
    smoothing_sigma: float = 1.0       # 0=不平滑,1=中等,2=高
    use_gaussian_rbf: bool = True      # 替代 nearest neighbor
    rbf_sigma: float = 0.05            # RBF 带宽
    n_iterations: int = 100            # Gaussian sampling 迭代次数
    multi_ref_weights: Optional[list] = None  # 多图加权


@dataclass
class HALDExtractionResult:
    """HALD 提取结果"""
    lut_data: np.ndarray               # (N, N, N, 3) float32 [0, 1]
    config: HALDExtractionConfig
    source_stats: Dict
    method: str                        # 'nearest' / 'gaussian_rbf' / 'shepard_idw'
    metadata: Dict = field(default_factory=dict)


class HALDPixelExtractor:
    """HALD-based 像素映射风格提取器"""

    def __init__(self, config: HALDExtractionConfig = None):
        self.config = config or HALDExtractionConfig()
        self.converter = ColorSpaceConverter()

    def extract(
        self,
        reference_image_path: Union[str, Path],
        cube_size: Optional[int] = None,
        method: Optional[str] = None,
    ) -> HALDExtractionResult:
        """从单张参考图提取 3D LUT

        Args:
            reference_image_path: 调色后参考图路径
            cube_size: 覆盖配置 (17/25/33/64/65)
            method: 'nearest' / 'gaussian_rbf' / 'shepard_idw'
        """
        cfg = self.config
        if cube_size is not None:
            cfg.cube_size = cube_size
        if method is not None:
            cfg.use_gaussian_rbf = (method == 'gaussian_rbf')

        # 加载图像
        rgb = self.converter.load_image(reference_image_path)
        ref = rgb.astype(np.float32) / 255.0

        # 提取
        if cfg.use_gaussian_rbf:
            lut = self._extract_gaussian_rbf(ref)
            method_name = 'gaussian_rbf'
        elif method == 'shepard_idw':
            lut = self._extract_shepard_idw(ref)
            method_name = 'shepard_idw'
        else:
            lut = self._extract_nearest(ref)
            method_name = 'nearest'

        # 统计
        source_stats = self._compute_stats(ref)

        return HALDExtractionResult(
            lut_data=lut,
            config=cfg,
            source_stats=source_stats,
            method=method_name,
            metadata={'source_image': str(reference_image_path)}
        )

    def _extract_nearest(self, ref: np.ndarray) -> np.ndarray:
        """最近邻(KD-tree)"""
        from scipy.spatial import cKDTree
        N = self.config.cube_size
        indices = np.linspace(0, 1, N)
        rr, gg, bb = np.meshgrid(indices, indices, indices, indexing='ij')
        coords = np.stack([rr.ravel(), gg.ravel(), bb.ravel()], axis=1)

        pixels = ref.reshape(-1, 3)
        tree = cKDTree(pixels)
        _, idx = tree.query(coords)
        lut = pixels[idx].reshape(N, N, N, 3)

        if self.config.smoothing_sigma > 0:
            lut = self._smooth(lut)
        return lut.astype(np.float32)

    def _extract_gaussian_rbf(self, ref: np.ndarray) -> np.ndarray:
        """Gaussian RBF 插值(参考 lutgen-rs Gaussian 模式)"""
        from scipy.ndimage import gaussian_filter
        N = self.config.cube_size
        indices = np.linspace(0, 1, N)
        rr, gg, bb = np.meshgrid(indices, indices, indices, indexing='ij')
        coords = np.stack([rr.ravel(), gg.ravel(), bb.ravel()], axis=1).astype(np.float32)

        # 像素作为"训练点",目标 = 像素自身
        pixels = ref.reshape(-1, 3).astype(np.float32)
        h, w, _ = ref.shape

        # Gaussian RBF kernel: K(x, p) = exp(-||x-p||² / (2σ²))
        sigma = self.config.rbf_sigma

        # 累加器
        out_sum = np.zeros_like(coords)
        weight_sum = np.zeros((coords.shape[0], 1), dtype=np.float32)

        # 随机采样 N 个像素(避免 O(H*W*N³) 太慢)
        np.random.seed(42)
        sample_size = min(10000, h * w)
        sample_idx = np.random.choice(h * w, sample_size, replace=False)
        samples = pixels[sample_idx]  # (sample_size, 3)

        # 向量化距离计算
        # (N³, 1, 3) - (1, sample_size, 3) -> (N³, sample_size, 3)
        diff = coords[:, None, :] - samples[None, :, :]
        dist_sq = np.sum(diff ** 2, axis=2)  # (N³, sample_size)
        weights = np.exp(-dist_sq / (2 * sigma ** 2))  # (N³, sample_size)

        # 加权平均目标(目标 = 像素自身,因为 identity 的 from=to)
        weighted_samples = samples[None, :, :] * weights[:, :, None]  # (N³, sample_size, 3)
        out_sum = np.sum(weighted_samples, axis=1)  # (N³, 3)
        weight_sum = np.sum(weights, axis=1, keepdims=True)  # (N³, 1)

        # 避免除零
        weight_sum = np.maximum(weight_sum, 1e-10)
        lut = out_sum / weight_sum
        lut = lut.reshape(N, N, N, 3).astype(np.float32)

        if self.config.smoothing_sigma > 0:
            for c in range(3):
                lut[..., c] = gaussian_filter(lut[..., c], sigma=self.config.smoothing_sigma)

        return lut

    def _extract_shepard_idw(self, ref: np.ndarray) -> np.ndarray:
        """Shepard's Method / IDW(参考 snibgo sparse_hald_clut)"""
        from scipy.ndimage import gaussian_filter
        N = self.config.cube_size
        indices = np.linspace(0, 1, N)
        rr, gg, bb = np.meshgrid(indices, indices, indices, indexing='ij')
        coords = np.stack([rr.ravel(), gg.ravel(), bb.ravel()], axis=1).astype(np.float32)

        pixels = ref.reshape(-1, 3).astype(np.float32)
        h, w, _ = ref.shape

        # 采样
        sample_size = min(5000, h * w)
        sample_idx = np.random.choice(h * w, sample_size, replace=False)
        samples = pixels[sample_idx]

        # IDW: w_i = 1 / d_i^p,通常 p=2
        diff = coords[:, None, :] - samples[None, :, :]
        dist_sq = np.sum(diff ** 2, axis=2)
        dist_sq = np.maximum(dist_sq, 1e-10)  # 避免除零
        weights = 1.0 / dist_sq  # (N³, sample_size)

        weighted_samples = samples[None, :, :] * weights[:, :, None]
        out_sum = np.sum(weighted_samples, axis=1)
        weight_sum = np.sum(weights, axis=1, keepdims=True)
        lut = (out_sum / weight_sum).reshape(N, N, N, 3).astype(np.float32)

        if self.config.smoothing_sigma > 0:
            for c in range(3):
                lut[..., c] = gaussian_filter(lut[..., c], sigma=self.config.smoothing_sigma)

        return lut

    def _smooth(self, lut: np.ndarray) -> np.ndarray:
        from scipy.ndimage import gaussian_filter
        out = lut.copy()
        for c in range(3):
            out[..., c] = gaussian_filter(lut[..., c], sigma=self.config.smoothing_sigma)
        return out

    def _compute_stats(self, ref: np.ndarray) -> Dict:
        return {
            'mean_rgb': ref.reshape(-1, 3).mean(axis=0).tolist(),
            'std_rgb': ref.reshape(-1, 3).std(axis=0).tolist(),
            'min_rgb': ref.reshape(-1, 3).min(axis=0).tolist(),
            'max_rgb': ref.reshape(-1, 3).max(axis=0).tolist(),
        }
```

### 2.3 性能预算

| cube_size | N³ | 内存(LUT) | KD-tree 提取 | Gaussian RBF 提取 |
|---|---|---|---|---|
| 17 | 4913 | 1 MB | <1s | ~5s |
| 25 | 15625 | 3 MB | <1s | ~15s |
| 33 | 35937 | 7 MB | 1-2s | ~30s |
| 64 | 262144 | 50 MB | 5-10s | 慢(分钟级) |

**推荐默认**:`cube_size=33` + `method=gaussian_rbf`,符合 LrC/Resolve 主流 LUT size。

### 2.4 与现有 `StyleExtractor` 的关系

| 维度 | StyleExtractor(保留) | HALDPixelExtractor(新增) |
|---|---|---|
| 用途 | 快速风格分析(返回文本描述) | 真正生成可应用的 3D LUT |
| 速度 | < 1s | 5-30s |
| 精度 | 1D(对角线) | 3D(像素映射) |
| 输出 | 风格特征 dict | .cube 文件 |
| 适用 | 风格描述、统计 | LrC/PS 实际应用 |

**集成方式**:`StyleExtractor` 保留为 fast path;`HALDPixelExtractor` 作为 `extract-hald` CLI 命令的实现。

## 3. 路线 B: 多图对训练(高复杂度)

### 3.1 模块设计

**文件**:`lut-generator_server/src/lut_generator/core/image_pair_trainer.py`

```python
"""
Image-pair 训练:从 N 对 (source, target) 图像提取高精度 3D LUT
参考 bastibe/LUT-Maker + savuori/haldclut_dt
"""

import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .color_space import ColorSpaceConverter


@dataclass
class ImagePairTrainerConfig:
    cube_size: int = 16                 # bastibe 默认
    subsampling: int = 5                # 抗锐化
    weight_factor: float = 2.0          # 已采样 vs 中性
    boundary_weight_factor: float = 5.0
    smoothing_sigma: float = 1.0
    min_color_samples: int = 5          # < 此值 bin 拒收
    use_orientation: bool = True        # EXIF 修正
    require_alignment: bool = True      # 是否强制像素对齐


class ImagePairTrainer:
    """80+ (source, target) 图对 → 16³ HaldCLUT PNG"""

    def __init__(self, config: ImagePairTrainerConfig = None):
        self.config = config or ImagePairTrainerConfig()
        self.converter = ColorSpaceConverter()

    def train(
        self,
        source_dir: Path,
        target_dir: Path,
        output_hald_path: Path,
    ) -> np.ndarray:
        """
        从 source/target 图像对训练 LUT

        Args:
            source_dir: 中性/原始图像目录
            target_dir: 应用目标滤镜后的图像目录
            output_hald_path: 输出 HaldCLUT PNG (64x64x3 for 16³ cube)
        """
        cfg = self.config
        N = cfg.cube_size
        RGB2IDX = int(256 / N)

        # 累加器
        color_sum = np.zeros([N, N, N, 3], dtype=np.uint64)
        color_count = np.zeros([N, N, N], dtype=np.uint64)

        # 遍历匹配的图像对
        source_files = sorted(source_dir.glob('*.jpg')) + sorted(source_dir.glob('*.png'))
        for source_file in source_files:
            target_file = target_dir / source_file.name
            if not target_file.exists():
                continue

            self._process_pair(
                source_file, target_file,
                color_sum, color_count, N, RGB2IDX
            )

        # 生成 LUT 矩阵
        lut_matrix = self._generate_lut_matrix(color_sum, color_count, N)

        # 平滑 + 外推
        lut_matrix = self._smooth_and_extrapolate(lut_matrix, color_count, N)

        # Hald 格式:swapaxes(0, 2) 然后 reshape
        hald = lut_matrix.swapaxes(0, 2).reshape([N * N, N * N, 3])
        return hald.astype(np.uint8)  # PNG 8-bit

    def _process_pair(self, source_file, target_file, color_sum, color_count, N, RGB2IDX):
        """处理一对图像,累加到 color_sum/color_count"""
        from PIL import Image

        source_img = Image.open(source_file)
        target_img = Image.open(target_file)

        # 1. EXIF orientation 修正
        if self.config.use_orientation:
            try:
                orientation = target_img.getexif()[274]
                if orientation == 8:
                    target_img = target_img.transpose(2)
                elif orientation == 3:
                    target_img = target_img.transpose(3)
                elif orientation == 6:
                    target_img = target_img.transpose(4)
            except (KeyError, AttributeError):
                pass

        # 2. 中央裁剪对齐
        source_crop = [0, 0, source_img.width, source_img.height]
        target_crop = [0, 0, target_img.width, target_img.height]
        if source_img.width > target_img.width:
            diff = (source_img.width - target_img.width) // 2
            source_crop[0], source_crop[2] = diff, diff + target_img.width
        elif source_img.width < target_img.width:
            diff = (target_img.width - source_img.width) // 2
            target_crop[0], target_crop[2] = diff, diff + source_img.width
        # (height 同理)
        # ...

        # 3. Subsample 5x 抗锐化
        subsample = self.config.subsampling
        source_img = source_img.resize(
            [source_crop[2] // subsample, source_crop[3] // subsample],
            resample=Image.Resampling.LANCZOS, box=source_crop
        )
        target_img = target_img.resize(
            [target_crop[2] // subsample, target_crop[3] // subsample],
            resample=Image.Resampling.LANCZOS, box=target_crop
        )

        # 4. 累加
        source = np.asarray(source_img)
        target = np.asarray(target_img)
        if source.shape != target.shape:
            return  # skip

        self._count_pixels(source, target, color_sum, color_count, N, RGB2IDX)

    def _count_pixels(self, source, target, color_sum, color_count, N, RGB2IDX):
        """对每像素累加"""
        for x in range(source.shape[0]):
            for y in range(source.shape[1]):
                # 0-7 -> 0, 8-23 -> 1, ..., 248-255 -> 15
                ridx, gidx, bidx = (source[x, y] - RGB2IDX // 2) // (RGB2IDX + 1) + 1
                color_sum[ridx, gidx, bidx] += target[x, y]
                color_count[ridx, gidx, bidx] += 1

    def _generate_lut_matrix(self, color_sum, color_count, N):
        """生成 LUT 矩阵(平均 + 权重)"""
        from scipy.ndimage import gaussian_filter
        cfg = self.config
        lut = np.zeros([N, N, N, 3], dtype=np.float32)

        for r in range(N):
            for g in range(N):
                for b in range(N):
                    if color_count[r, g, b] >= cfg.min_color_samples:
                        lut[r, g, b] = color_sum[r, g, b] / color_count[r, g, b]
                    # else: leave as 0 (black) for boundary detection

        return lut

    def _smooth_and_extrapolate(self, lut, color_count, N):
        """高斯平滑 + 边界外推"""
        from scipy.ndimage import gaussian_filter
        sigma = self.config.smoothing_sigma

        out = lut.copy()
        for c in range(3):
            out[..., c] = gaussian_filter(lut[..., c], sigma=sigma)

        # 边界 bin(0 和 N-1)用最近的有效值填充
        # (简化:bastibe 用更复杂外推,这里先用 nearest)
        for r in range(N):
            for g in range(N):
                for b in range(N):
                    if color_count[r, g, b] < self.config.min_color_samples:
                        # 找最近的有效 bin
                        # (简化为 fallback 到 identity)
                        out[r, g, b] = [r / (N - 1), g / (N - 1), b / (N - 1)]

        return out
```

### 3.2 性能预算

- 80 对图对,500×300 像素(下采样后 ~120×80 = 9600 像素/对)
- 总像素:80 × 9600 = 768000
- 处理速度:Python 循环 ~10000 像素/秒 → **~77 秒**(可优化用 numba JIT → 5-10 秒)
- 推荐:加 numba 装饰,提速 10-50x

### 3.3 注意事项

- **需要用户输入对齐的图对**,普通创作者做不到
- 适合:胶片模拟开发、专业 LUT 工作室
- **不作为 MVP**,路线 A 完成后视用户反馈决定

## 4. 路线 D: 格式互转(基础设施)

### 4.1 模块设计

**文件**:`lut-generator_server/src/lut_generator/lut/format_converter.py`

```python
"""
LUT 格式互转:.cube ↔ .3dl ↔ Hald CLUT ↔ .xmp LookTable
"""

import numpy as np
from pathlib import Path
from typing import Union, Dict
from .exporter import LUTExporter  # 复用现有 .cube 导出
from .lut3d import LUT3DGenerator, LUT3DConfig


class LUTFormatConverter:
    """LUT 格式互转器"""

    def cube_to_hald(self, cube_path: Path, output_png_path: Path):
        """.cube → Hald CLUT PNG"""
        # 1. 解析 .cube
        lut_data, metadata = self._parse_cube(cube_path)
        N = lut_data.shape[0]

        # 2. .cube BGR 顺序 → RGB
        # (Adobe .cube 顺序:r + N*g + N²*b,RGB 索引)
        # Hald 格式需要 swapaxes(0, 2) 因为 R 和 B 通道互换
        hald = lut_data.swapaxes(0, 2).reshape([N * N, N * N, 3])

        # 3. 8-bit PNG
        from PIL import Image
        img = Image.fromarray((hald * 255).astype(np.uint8))
        img.save(output_png_path, 'PNG')

    def hald_to_cube(self, hald_png_path: Path, output_cube_path: Path, cube_size: int = None):
        """Hald CLUT PNG → .cube"""
        from PIL import Image
        hald = np.asarray(Image.open(hald_png_path)) / 255.0
        side = hald.shape[0]  # N²
        N = int(round(side ** 0.5))  # = 8, 16, 32, ...
        if cube_size and cube_size != N:
            # 重采样(用 scipy RegularGridInterpolator)
            from scipy.interpolate import RegularGridInterpolator
            ...

        # Hald swapaxes 反向
        lut_data = hald.reshape(N, N, N, 3).swapaxes(0, 2)  # R↔B

        # 写 .cube
        self._write_cube(lut_data, output_cube_path, cube_size=N)

    def cube_to_3dl(self, cube_path: Path, output_3dl_path: Path):
        """.cube → .3dl (Autodesk Flame/Lustre)"""
        lut_data, metadata = self._parse_cube(cube_path)
        N = lut_data.shape[0]
        # .3dl 是整数 0-4095 (12-bit)
        # 顺序与 .cube 相同 (r + N*g + N²*b)
        with open(output_3dl_path, 'w') as f:
            f.write(f"# Generated from {cube_path}\n")
            f.write(f"# Cube size: {N}\n")
            for r in range(N):
                for g in range(N):
                    for b in range(N):
                        ri, gi, bi = lut_data[r, g, b]
                        # 12-bit integer
                        ri_int = int(round(ri * 4095))
                        gi_int = int(round(gi * 4095))
                        bi_int = int(round(bi * 4095))
                        f.write(f"{ri_int} {gi_int} {bi_int}\n")

    def _parse_cube(self, cube_path: Path) -> tuple:
        """解析 .cube 文件 → (lut_data, metadata)"""
        with open(cube_path) as f:
            lines = f.readlines()

        metadata = {'title': None, 'domain_min': [0, 0, 0], 'domain_max': [1, 1, 1]}
        size_1d = None
        size_3d = None
        data_lines = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.upper().startswith('TITLE'):
                metadata['title'] = line[5:].strip().strip('"')
            elif line.upper().startswith('LUT_1D_SIZE'):
                size_1d = int(line.split()[1])
            elif line.upper().startswith('LUT_3D_SIZE'):
                size_3d = int(line.split()[1])
            elif line.upper().startswith('DOMAIN_MIN'):
                metadata['domain_min'] = [float(x) for x in line.split()[1:4]]
            elif line.upper().startswith('DOMAIN_MAX'):
                metadata['domain_max'] = [float(x) for x in line.split()[1:4]]
            else:
                # 数据行
                parts = line.split()
                if len(parts) >= 3:
                    data_lines.append([float(parts[0]), float(parts[1]), float(parts[2])])

        if size_3d:
            N = size_3d
            lut_data = np.array(data_lines).reshape(N, N, N, 3)
        elif size_1d:
            # 1D LUT:每 3 行组成 1 个 sample
            N = size_1d
            lut_data = np.array(data_lines).reshape(N, 3)
        else:
            raise ValueError("No LUT_1D_SIZE or LUT_3D_SIZE found")

        return lut_data, metadata

    def _write_cube(self, lut_data: np.ndarray, output_path: Path, cube_size: int = None, title: str = None):
        """写 .cube 文件"""
        with open(output_path, 'w') as f:
            if title:
                f.write(f'TITLE "{title}"\n')
            if lut_data.ndim == 4:
                N = lut_data.shape[0]
                f.write(f'LUT_3D_SIZE {N}\n')
                for r in range(N):
                    for g in range(N):
                        for b in range(N):
                            ri, gi, bi = lut_data[r, g, b]
                            f.write(f'{ri:.6f} {gi:.6f} {bi:.6f}\n')
            elif lut_data.ndim == 2:
                N = lut_data.shape[0]
                f.write(f'LUT_1D_SIZE {N}\n')
                for row in lut_data:
                    f.write(f'{row[0]:.6f} {row[1]:.6f} {row[2]:.6f}\n')
```

### 4.2 Hald CLUT 通道 swapaxes 问题

**关键陷阱**(已在调研报告 §1.6 标注):
- Hald CLUT 2D 格式中,**R 和 B 通道位置互换**(与 .cube 顺序不同)
- .cube 顺序:`r + N*g + N²*b`(Red changes fastest, Blue changes slowest)
- Hald 2D 存储顺序:需要 `swapaxes(0, 2).reshape(...)` 把 R 和 B 互换
- 这是 bastibe/LUT-Maker / oiao/clut 的"已实现且测试过"的标准做法

**测试用例**(必须验证):
- identity Hald CLUT:`hald:8` → `cube_to_hald(cube_identity, hald.png)` → 应该输出 identity
- round-trip:`hald_to_cube(hald.png, cube.cube)` → `cube_to_hald(cube.cube, hald2.png)` → 应该 ≈ 原 hald

## 5. CLI 设计 — 扩展 `extract` 命令族

**当前**:`lut-generator extract --input <img> --output <cube> --size 33`(用 StyleExtractor,对角线)

**新增命令**:

```bash
# 路线 A:单图 HALD 像素提取
lut-generator extract-hald \
  --input <reference.jpg> \
  --output <style.cube> \
  --size 33 \
  --method gaussian_rbf \
  --rbf-sigma 0.05 \
  --smoothing 1.0

# 路线 A.5:多图加权(覆盖更多色域)
lut-generator extract-multi \
  --inputs ref1.jpg,ref2.jpg,ref3.jpg \
  --weights 1.0,1.5,1.0 \
  --output style.cube \
  --size 33

# 路线 B:多图对训练
lut-generator train \
  --source-dir neutral/ \
  --target-dir graded/ \
  --output lut.hald.png \
  --size 16

# 路线 D:格式互转
lut-generator convert \
  --input style.cube \
  --output style.3dl
lut-generator convert \
  --input style.cube \
  --output style.hald.png
lut-generator convert \
  --input style.hald.png \
  --output style.cube
```

**保留向后兼容**:
- 现有 `extract` 命令(用 StyleExtractor)保留 — 用于快速风格分析
- 用户用 `--method hald` 显式选新算法:`lut-generator extract --method hald --input ...`(推荐默认改为 hald)

## 6. 测试策略

### 6.1 单元测试

**文件**:`tests/test_hald_extractor.py`(~15-20 个测试)

```python
def test_nearest_returns_3d_lut():
    """最近邻方法返回 (N, N, N, 3) 数组"""
    ...

def test_gaussian_rbf_preserves_input_pixels():
    """RBF 插值后,采样点附近的 LUT 值应接近参考图"""
    ref = create_test_image_red_dominant()
    lut = extractor._extract_gaussian_rbf(ref)
    # 红色像素 (255, 0, 0) 附近 cube bin 应输出接近红色
    red_bin = lut[-1, 0, 0]  # (1, 0, 0)
    assert red_bin[0] > 0.8  # R 高
    assert red_bin[1] < 0.2  # G 低
    assert red_bin[2] < 0.2  # B 低

def test_identity_input_returns_identity_lut():
    """输入 identity Hald CLUT 应得到 identity LUT"""
    # hald:8 identity 是 8×8×8 cube
    # 每个 bin 的 LUT 输出应 ≈ bin 自身
    ...

def test_smoothing_reduces_noise():
    """Gaussian 平滑应降低 LUT 方差"""
    ...

def test_cube_format_compliance():
    """输出 .cube 满足 Adobe spec 1.0"""
    lut = np.random.rand(33, 33, 33, 3)
    write_cube(lut, 'test.cube')
    # 验证:第一行非注释非空
    with open('test.cube') as f:
        first = f.readline().strip()
    assert first.startswith('LUT_3D_SIZE')
    # 验证:总行数 = 33³ + 1
    with open('test.cube') as f:
        lines = f.readlines()
    assert len(lines) == 33**3 + 1
```

### 6.2 集成测试

```python
def test_extract_hald_cli(tmp_path):
    """CLI 端到端测试"""
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, [
        'extract-hald',
        '--input', 'tests/fixtures/teal_orange_ref.jpg',
        '--output', str(tmp_path / 'out.cube'),
        '--size', '17',
        '--method', 'gaussian_rbf',
    ])
    assert result.exit_code == 0
    assert (tmp_path / 'out.cube').exists()
    # 验证 .cube 可被 lut_applier 应用
    applier = LUTApplier()
    result_img = applier.apply(lut_path=str(tmp_path / 'out.cube'), image=...)
    assert result_img.shape == ref_img.shape

def test_cube_to_hald_roundtrip(tmp_path):
    """互转 round-trip"""
    converter = LUTFormatConverter()
    converter.cube_to_hald('in.cube', str(tmp_path / 'mid.hald.png'))
    converter.hald_to_cube(str(tmp_path / 'mid.hald.png'), str(tmp_path / 'out.cube'))
    # 验证 out.cube ≈ in.cube
    in_lut, _ = converter._parse_cube('in.cube')
    out_lut, _ = converter._parse_cube(str(tmp_path / 'out.cube'))
    assert np.allclose(in_lut, out_lut, atol=1e-3)
```

### 6.3 视觉验证(关键!)

**用户**:
1. 用 IWLTBAP/3D LUT Creator 创建一个已知 LUT
2. 应用到中性测试图,保存为 `reference.jpg`
3. 用新工具提取:`lut-generator extract-hald --input reference.jpg --output test.cube --size 33`
4. 加载回 IWLTBAP/3D LUT Creator,应用 `test.cube` 到**另一张中性图**
5. 视觉对比:结果应与 `reference.jpg` **接近**(允许轻微色域边缘差异)

## 7. 实施里程碑(2 周)

| Day | 任务 | 验收 |
|---|---|---|
| **Day 1-2** | 实现 `HALDPixelExtractor`(路线 A 核心) | 3 个方法(nearest / gaussian_rbf / shepard_idw) 跑通 |
| **Day 3** | 写测试 `test_hald_extractor.py` | 15+ 单测全过 |
| **Day 4** | 集成到 CLI,加 `extract-hald` / `extract-multi` 命令 | CLI 帮助文档 + 端到端跑通 |
| **Day 5** | 视觉验证(与 IWLTBAP / 3D LUT Creator 对比) | 用户可看到"参考图 → LUT → 应用" 工作流 |
| **Day 6-7** | 实现 `LUTFormatConverter`(路线 D) | .cube ↔ .3dl ↔ Hald 三向互转 + round-trip 测试 |
| **Day 8** | 集成到 CLI,加 `convert` 命令 | CLI 端到端通 |
| **Day 9-10** | 文档:更新 README + CHANGELOG + 加 `docs/REVERSE_LUT.md` | 用户可上手 |
| **Day 11-14** | (视用户反馈) 路线 B 训练 / 路线 C 神经 | 视实际需求 |

**关键检查点**:
- Day 5:**必须用 LrC 14 实际测试**(用户手动验证"应用后有色彩变化")
- Day 7:**用户**拍板是否继续路线 B(多图对)或路线 C(神经)

## 8. 风险与回滚

### 8.1 风险清单

| 风险 | 影响 | 缓解 |
|---|---|---|
| 路线 A 提取的 LUT 仍不准确 | 用户仍看不到色彩变化 | 切换到路线 B(Image-pair) — 需要用户提供对齐图对 |
| `swapaxes(0, 2)` 在某个格式下有误 | 颜色翻转(R↔B) | 单元测试覆盖,`identity round-trip` 验证 |
| 33³ cube 内存占用大 | 性能问题 | 默认 17 或 25,33 用 `--size 33` 显式选 |
| 路线 B 需 numba | 额外依赖 | 包装成 optional,无 numba 走纯 Python 慢路径 |
| 与现有 StyleExtractor 命名冲突 | 用户混淆 | 新命令 `extract-hald` 明确区分,`extract` 保留旧行为 |

### 8.2 回滚计划

- 路线 A / D 是**纯增量** — 不修改 `StyleExtractor`,只是新增模块 + CLI 子命令
- 如果新功能出问题,只需移除 `hald_extractor.py` / `format_converter.py` 文件 + `cli/main.py` 的新子命令
- **不需要回滚 git commit**

## 9. 验收标准

### 9.1 路线 A(必须达成)

- [ ] `lut-generator extract-hald --input <ref> --output <cube> --size 33` 跑通
- [ ] 输出 .cube 文件满足 Adobe Cube LUT spec 1.0
- [ ] 在 LrC 14 中应用后,照片**有**色彩变化(用户视觉确认)
- [ ] 测试覆盖率 > 80%
- [ ] README 用法示例更新

### 9.2 路线 D(必须达成)

- [ ] `.cube → .3dl` 转换保留色彩
- [ ] `.cube → Hald CLUT` 转换保留色彩
- [ ] `Hald CLUT → .cube` round-trip 误差 < 1e-3
- [ ] `lut-generator convert --input in.cube --output out.3dl` 跑通

### 9.3 路线 A.5(可选)

- [ ] 多图加权(用户给 3 张图)提取的 LUT 色域覆盖更广
- [ ] 单图 / 多图结果可视化对比

### 9.4 路线 B(可选,P2)

- [ ] 80+ 图对训练生成 16³ HaldCLUT
- [ ] 与 bastibe/LUT-Maker 对比:同一图对,结果误差 < 5%

## 10. 代码模板

### 10.1 CLI 注册(修改 `cli/main.py`)

```python
# 在 main.py 加新子命令
from lut_generator.core.hald_extractor import HALDPixelExtractor, HALDExtractionConfig
from lut_generator.lut.format_converter import LUTFormatConverter


@cli.command()
@click.option('--input', '-i', required=True, help='参考图路径')
@click.option('--output', '-o', required=True, help='输出 .cube 路径')
@click.option('--size', '-s', default=33, type=int, help='cube 大小 (17/25/33/64/65)')
@click.option('--method', '-m', default='gaussian_rbf',
              type=click.Choice(['nearest', 'gaussian_rbf', 'shepard_idw']),
              help='提取算法')
@click.option('--rbf-sigma', default=0.05, type=float, help='Gaussian RBF 带宽')
@click.option('--smoothing', default=1.0, type=float, help='Gaussian 平滑 sigma')
def extract_hald(input, output, size, method, rbf_sigma, smoothing):
    """从单张参考图提取 3D LUT (HALD-based 像素映射)"""
    cfg = HALDExtractionConfig(
        cube_size=size,
        use_gaussian_rbf=(method == 'gaussian_rbf'),
        rbf_sigma=rbf_sigma,
        smoothing_sigma=smoothing,
    )
    extractor = HALDPixelExtractor(cfg)
    result = extractor.extract(input, method=method)

    # 导出 .cube
    from lut_generator.lut.exporter import LUTExporter
    exporter = LUTExporter()
    exporter.export_cube(result.lut_data, output, title=Path(input).stem)

    click.echo(f"✓ Extracted {size}³ LUT ({method}) to {output}")
    click.echo(f"  Source stats: {result.source_stats}")


@cli.command()
@click.option('--input', '-i', required=True, help='输入 LUT 文件')
@click.option('--output', '-o', required=True, help='输出文件')
@click.option('--format', '-f', default=None, type=click.Choice(['cube', '3dl', 'hald']),
              help='目标格式(默认从输出后缀推断)')
def convert(input, output, format):
    """LUT 格式互转:.cube ↔ .3dl ↔ Hald CLUT"""
    converter = LUTFormatConverter()
    src_path = Path(input)
    dst_path = Path(output)

    src_fmt = src_path.suffix.lstrip('.')
    dst_fmt = format or dst_path.suffix.lstrip('.')

    if src_fmt == 'cube' and dst_fmt == '3dl':
        converter.cube_to_3dl(src_path, dst_path)
    elif src_fmt == 'cube' and dst_fmt in ('hald', 'png'):
        converter.cube_to_hald(src_path, dst_path)
    elif src_fmt in ('hald', 'png') and dst_fmt == 'cube':
        converter.hald_to_cube(src_path, dst_path)
    else:
        raise click.BadParameter(f"Conversion {src_fmt} → {dst_fmt} not yet supported")

    click.echo(f"✓ Converted {src_path} → {dst_path}")
```

### 10.2 文件清单(总)

| 文件 | 大小(估) | 用途 |
|---|---|---|
| `core/hald_extractor.py` | ~250 行 | 路线 A 核心 |
| `core/image_pair_trainer.py` | ~300 行 | 路线 B 核心(可选) |
| `lut/format_converter.py` | ~200 行 | 路线 D 核心 |
| `cli/main.py` 修改 | +50 行 | 新增 3 个子命令 |
| `tests/test_hald_extractor.py` | ~200 行 | 路线 A 测试 |
| `tests/test_image_pair_trainer.py` | ~150 行 | 路线 B 测试 |
| `tests/test_format_converter.py` | ~120 行 | 路线 D 测试 |
| `docs/REVERSE_LUT.md` | ~150 行 | 用户文档 |
| **总计** | **~1400 行** | 不含 .venv 依赖 |

---

**实施作者**:Hermes (minimax, MiniMax-M3)
**方案版本**:v1.0
**生成日期**:2026-06-15
**字数**:~14 KB
**关联报告**:[LUT_EXTRACTION_RESEARCH.md](./LUT_EXTRACTION_RESEARCH.md) (40 KB)

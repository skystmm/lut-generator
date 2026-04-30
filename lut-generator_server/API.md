# LUT Generator API 参考文档

**版本**: v1.0.0  
**最后更新**: 2026-04-13

本文档提供 LUT Generator 所有公共 API 的详细参考。

---

## 目录

1. [核心模块](#核心模块)
   - [LUT3DGenerator](#lut3dgenerator)
   - [LUTApplier](#lutapplier)
2. [分析模块](#分析模块)
   - [ColorAnalyzer](#coloranalyzer)
   - [ColorTransferMatcher](#colortransfermatcher)
   - [FeatureFusionEngine](#featurefusionengine)
3. [预览模块](#预览模块)
   - [PreviewGenerator](#previewgenerator)
   - [ColorVisualizer](#colorvisualizer)
   - [HTMLReportGenerator](#htmlreportgenerator)
4. [优化模块](#优化模块)
   - [PerformanceOptimizer](#performanceoptimizer)
   - [LUTCache](#lutcache)
   - [ParallelProcessor](#parallelprocessor)
   - [ChunkedImageProcessor](#chunkedimageprocessor)
5. [批量处理](#批量处理)
   - [BatchAnalyzer](#batchanalyzer)
6. [命令行接口](#命令行接口)
7. [数据类型](#数据类型)

---

## 核心模块

### LUT3DGenerator

3D LUT 生成器核心类。

#### 初始化

```python
from lut3d_generator import LUT3DGenerator, LUT3DConfig

config = LUT3DConfig(
    grid_size: int = 33,           # LUT 网格大小 (17/33/65)
    smoothness: float = 0.5,       # 平滑度 (0.0-1.0)
    use_advanced_interpolation: bool = True,
    color_space: str = 'lab',      # 'lab' 或 'rgb'
    white_balance: bool = True
)

generator = LUT3DGenerator(config)
```

#### 方法

##### `generate_from_images(reference_path, target_path)`

从参考图像和目标图像生成 LUT。

**参数**:
- `reference_path` (str): 参考图像路径
- `target_path` (str): 目标图像路径

**返回**: `LUTResult` 对象或 `np.ndarray`

**示例**:
```python
result = generator.generate_from_images('ref.jpg', 'target.jpg')
```

##### `generate_from_stats(reference_stats, target_stats)`

从色彩统计生成 LUT。

**参数**:
- `reference_stats` (dict): 参考图像色彩统计
- `target_stats` (dict): 目标图像色彩统计

**返回**: `LUTResult` 对象

**示例**:
```python
result = generator.generate_from_stats(ref_stats, target_stats)
```

##### `export_to_cube(output_path)`

导出 LUT 为 .cube 文件格式。

**参数**:
- `output_path` (str): 输出文件路径

**返回**: `None`

**示例**:
```python
generator.export_to_cube('output.cube')
```

##### `load_from_cube(cube_path)`

从 .cube 文件加载 LUT。

**参数**:
- `cube_path` (str): .cube 文件路径

**返回**: `np.ndarray` LUT 数据

**示例**:
```python
lut_data = generator.load_from_cube('input.cube')
```

##### `apply_to_image(image, lut_data)`

将 LUT 应用到图像。

**参数**:
- `image` (np.ndarray): 输入图像 (RGB, float32, 0-1)
- `lut_data` (np.ndarray): LUT 数据

**返回**: `np.ndarray` 处理后的图像

**示例**:
```python
processed = generator.apply_to_image(image, lut_data)
```

---

### LUTApplier

LUT 应用器，提供高级 LUT 应用功能。

#### 初始化

```python
from lut_applier import LUTApplier, ApplyConfig

config = ApplyConfig(
    interpolation_method: str = 'trilinear',  # 'trilinear' 或 'nearest'
    clamp_output: bool = True,
    gamma_correction: float = 1.0,
    preserve_highlights: bool = False,
    preserve_shadows: bool = False
)

applier = LUTApplier(generator, config)
```

#### 方法

##### `apply_to_file(input_path, output_path, progress_callback=None)`

应用 LUT 到图像文件。

**参数**:
- `input_path` (str): 输入图像路径
- `output_path` (str): 输出图像路径
- `progress_callback` (callable, optional): 进度回调函数 `(progress: float)`

**返回**: `ApplyResult` 对象

**示例**:
```python
result = applier.apply_to_file(
    'input.jpg',
    'output.jpg',
    progress_callback=lambda p: print(f'{p*100:.1f}%')
)
```

##### `apply_to_image(image, lut_data)`

应用 LUT 到 numpy 图像数组。

**参数**:
- `image` (np.ndarray): 输入图像
- `lut_data` (np.ndarray): LUT 数据

**返回**: `np.ndarray` 处理后的图像

**示例**:
```python
processed = applier.apply_to_image(image, lut_data)
```

##### `apply_batch(input_paths, output_dir, extensions=None)`

批量应用 LUT 到多个图像。

**参数**:
- `input_paths` (List[str]): 输入图像路径列表
- `output_dir` (str): 输出目录
- `extensions` (List[str], optional): 处理的文件扩展名

**返回**: `List[ApplyResult]`

**示例**:
```python
results = applier.apply_batch(
    ['img1.jpg', 'img2.jpg', 'img3.jpg'],
    './output/'
)
```

---

## 分析模块

### ColorAnalyzer

色彩分析器，提取图像色彩统计信息。

#### 初始化

```python
from color_analyzer import ColorAnalyzer, AnalysisConfig

config = AnalysisConfig(
    color_space: str = 'lab',
    compute_histogram: bool = True,
    histogram_bins: int = 256,
    compute_gamut: bool = True
)

analyzer = ColorAnalyzer(config)
```

#### 方法

##### `analyze_image(image_path)`

分析单张图像的色彩特征。

**参数**:
- `image_path` (str): 图像路径

**返回**: `dict` 色彩统计信息

**返回数据结构**:
```python
{
    'mean_color': [L, a, b],           # 平均色彩 (Lab)
    'std_color': [L, a, b],            # 色彩标准差
    'min_color': [L, a, b],            # 最小色彩值
    'max_color': [L, a, b],            # 最大色彩值
    'histogram': {                     # 直方图
        'L': np.ndarray,
        'a': np.ndarray,
        'b': np.ndarray
    },
    'gamut': {                         # 色域信息
        'area': float,
        'volume': float,
        'points': np.ndarray
    },
    'brightness': float,               # 平均亮度
    'contrast': float,                 # 对比度
    'saturation': float                # 平均饱和度
}
```

**示例**:
```python
stats = analyzer.analyze_image('image.jpg')
print(f"平均色彩：{stats['mean_color']}")
```

##### `analyze_batch(image_paths)`

批量分析多张图像。

**参数**:
- `image_paths` (List[str]): 图像路径列表

**返回**: `List[dict]` 统计信息列表

**示例**:
```python
stats_list = analyzer.analyze_batch(['img1.jpg', 'img2.jpg'])
```

---

### ColorTransferMatcher

色彩迁移匹配器，实现 Reinhard 算法。

#### 初始化

```python
from color_transfer import ColorTransferMatcher

matcher = ColorTransferMatcher()
```

#### 方法

##### `match_colors(source_stats, target_stats)`

计算从源色彩到目标色彩的映射。

**参数**:
- `source_stats` (dict): 源图像色彩统计
- `target_stats` (dict): 目标图像色彩统计

**返回**: `dict` 映射参数

**示例**:
```python
mapping = matcher.match_colors(source_stats, target_stats)
```

##### `apply_transfer(image, mapping)`

应用色彩迁移到图像。

**参数**:
- `image` (np.ndarray): 输入图像
- `mapping` (dict): 映射参数

**返回**: `np.ndarray` 处理后的图像

**示例**:
```python
transferred = matcher.apply_transfer(image, mapping)
```

---

### FeatureFusionEngine

特征融合引擎，多特征加权融合。

#### 初始化

```python
from feature_fusion import FeatureFusionEngine, FusionConfig

config = FusionConfig(
    color_weight: float = 0.6,      # 色彩权重
    brightness_weight: float = 0.3,  # 亮度权重
    saturation_weight: float = 0.1   # 饱和度权重
)

engine = FeatureFusionEngine(config)
```

#### 方法

##### `fuse_features(feature_list, weights=None)`

融合多个特征。

**参数**:
- `feature_list` (List[dict]): 特征列表
- `weights` (List[float], optional): 权重列表

**返回**: `dict` 融合后的特征

**示例**:
```python
fused = engine.fuse_features([stats1, stats2, stats3])
```

##### `compute_similarity(features1, features2)`

计算两个特征集的相似度。

**参数**:
- `features1` (dict): 特征集 1
- `features2` (dict): 特征集 2

**返回**: `float` 相似度 (0.0-1.0)

**示例**:
```python
similarity = engine.compute_similarity(stats1, stats2)
```

---

## 预览模块

### PreviewGenerator

预览图生成器，生成对比图。

#### 初始化

```python
from preview_generator import PreviewGenerator, ComparisonConfig

config = ComparisonConfig(
    mode: str = 'side_by_side',     # 'side_by_side', 'slider', 'difference', 'blend'
    border_width: int = 2,
    show_labels: bool = True,
    show_statistics: bool = True,
    label_font_size: int = 16,
    label_color: str = 'white'
)

generator = PreviewGenerator(applier, config)
```

#### 方法

##### `generate_comparison(original_path, processed_path, output_path, mode=None)`

生成对比图。

**参数**:
- `original_path` (str): 原图路径
- `processed_path` (str): 处理后图像路径
- `output_path` (str): 输出路径
- `mode` (str, optional): 对比模式

**返回**: `PreviewResult` 对象

**示例**:
```python
result = generator.generate_comparison(
    'original.jpg',
    'processed.jpg',
    'comparison.png',
    mode='slider'
)
```

##### `generate_side_by_side(original, processed, output)`

生成并排对比图。

**参数**:
- `original` (np.ndarray 或 str): 原图
- `processed` (np.ndarray 或 str): 处理后图像
- `output` (str): 输出路径

**返回**: `PreviewResult`

---

##### `generate_slider_preview(original, processed, output)`

生成滑块对比预览图。

**参数**: 同上

**返回**: `PreviewResult`

---

##### `generate_difference_map(original, processed, output)`

生成差异可视化图。

**参数**: 同上

**返回**: `PreviewResult`

---

### ColorVisualizer

色彩可视化工具，生成直方图和色域图。

#### 初始化

```python
from visualizer import ColorVisualizer, VisualizationConfig

config = VisualizationConfig(
    theme: str = 'dark',            # 'dark' 或 'light'
    show_grid: bool = True,
    show_statistics: bool = True,
    figure_size: tuple = (10, 6),
    dpi: int = 150
)

visualizer = ColorVisualizer(config)
```

#### 方法

##### `plot_histogram(image_path, output_path)`

绘制 RGB 直方图。

**参数**:
- `image_path` (str): 图像路径
- `output_path` (str): 输出路径

**返回**: `VisualizationResult`

**示例**:
```python
result = visualizer.plot_histogram('image.jpg', 'hist.png')
```

##### `plot_histogram_comparison(image1_path, image2_path, output_path)`

绘制对比直方图。

**参数**:
- `image1_path` (str): 图像 1 路径
- `image2_path` (str): 图像 2 路径
- `output_path` (str): 输出路径

**返回**: `VisualizationResult`

---

##### `plot_gamut(image_path, output_path)`

绘制 Lab 色域图 (a*b 平面)。

**参数**:
- `image_path` (str): 图像路径
- `output_path` (str): 输出路径

**返回**: `VisualizationResult`

---

##### `plot_gamut_comparison(image1_path, image2_path, output_path)`

绘制对比色域图。

**参数**:
- `image1_path` (str): 图像 1 路径
- `image2_path` (str): 图像 2 路径
- `output_path` (str): 输出路径

**返回**: `VisualizationResult`

---

### HTMLReportGenerator

HTML 报告生成器。

#### 初始化

```python
from html_report import HTMLReportGenerator, ReportConfig

config = ReportConfig(
    theme: str = 'dark',
    include_slider: bool = True,
    include_histograms: bool = True,
    include_gamut: bool = True,
    title: str = 'LUT Analysis Report'
)

generator = HTMLReportGenerator(config)
```

#### 方法

##### `generate_from_paths(original_path, processed_path, output_path)`

从图像路径生成 HTML 报告。

**参数**:
- `original_path` (str): 原图路径
- `processed_path` (str): 处理后图像路径
- `output_path` (str): 输出 HTML 路径

**返回**: `ReportResult`

**示例**:
```python
result = generator.generate_from_paths(
    'original.jpg',
    'processed.jpg',
    'report.html'
)
```

##### `generate_from_data(report_data, output_path)`

从数据生成 HTML 报告。

**参数**:
- `report_data` (ReportData): 报告数据对象
- `output_path` (str): 输出路径

**返回**: `ReportResult`

---

## 优化模块

### PerformanceOptimizer

性能优化器，统一接口。

#### 初始化

```python
from optimizer import (
    PerformanceOptimizer,
    CacheConfig,
    ParallelConfig,
    MemoryConfig
)

optimizer = PerformanceOptimizer(
    cache_config=CacheConfig(
        max_size: int = 100,
        ttl_seconds: int = 3600,
        enabled: bool = True
    ),
    parallel_config=ParallelConfig(
        num_workers: int = None,     # None=自动检测
        chunk_size: int = 4,
        use_processes: bool = True,
        max_memory_per_worker: int = 2048
    ),
    memory_config=MemoryConfig(
        chunk_size_mb: int = 256,
        max_image_size: int = 10000,
        enable_chunking: bool = True,
        garbage_collection_interval: int = 10
    )
)
```

#### 方法

##### `apply_lut_optimized(image, lut, lut_applier_func, use_cache=True, use_chunking=True)`

优化的 LUT 应用。

**参数**:
- `image` (np.ndarray): 输入图像
- `lut` (np.ndarray): LUT 数据
- `lut_applier_func` (callable): LUT 应用函数
- `use_cache` (bool): 使用缓存
- `use_chunking` (bool): 使用分块处理

**返回**: `np.ndarray` 处理后的图像

**示例**:
```python
result = optimizer.apply_lut_optimized(
    image,
    lut,
    lambda img, l: img * 0.9,
    use_cache=True,
    use_chunking=True
)
```

##### `process_batch_optimized(images, process_func, progress_callback=None)`

优化的批量处理。

**参数**:
- `images` (List[np.ndarray]): 图像列表
- `process_func` (callable): 处理函数
- `progress_callback` (callable): 进度回调

**返回**: `List[np.ndarray]`

**示例**:
```python
results = optimizer.process_batch_optimized(
    images,
    lambda img: img * 0.9,
    progress_callback=lambda p, c, t: print(f'{c}/{t}')
)
```

##### `get_stats()`

获取优化器统计。

**返回**: `OptimizerStats`

**示例**:
```python
stats = optimizer.get_stats()
print(f"缓存命中：{stats.cache_hits}")
print(f"总处理时间：{stats.total_processing_time}")
```

##### `clear_cache()`

清空缓存。

**返回**: `None`

---

### LUTCache

LUT 缓存类。

#### 初始化

```python
from optimizer import LUTCache, CacheConfig

cache = LUTCache(CacheConfig(max_size=100, ttl_seconds=3600))
```

#### 方法

##### `get(key)`

从缓存获取数据。

**参数**:
- `key` (Any): 缓存键

**返回**: `Optional[Any]`

---

##### `put(key, value)`

将数据放入缓存。

**参数**:
- `key` (Any): 缓存键
- `value` (Any): 值

---

##### `clear()`

清空缓存。

---

##### `stats()`

获取缓存统计。

**返回**: `dict`

---

### ParallelProcessor

并行处理器。

#### 初始化

```python
from optimizer import ParallelProcessor, ParallelConfig

processor = ParallelProcessor(
    ParallelConfig(num_workers=4, use_processes=True)
)
```

#### 方法

##### `process_batch(items, process_func, progress_callback=None, *args, **kwargs)`

批量并行处理。

**参数**:
- `items` (List[Any]): 项目列表
- `process_func` (callable): 处理函数
- `progress_callback` (callable): 进度回调
- `*args`: 传递给处理函数的位置参数
- `**kwargs`: 传递给处理函数的关键字参数

**返回**: `List[Any]`

---

##### `calculate_speedup(items, process_func, *args, **kwargs)`

计算并行加速比。

**参数**: 同上

**返回**: `float` 加速比

---

### ChunkedImageProcessor

分块图像处理器。

#### 初始化

```python
from optimizer import ChunkedImageProcessor, MemoryConfig

processor = ChunkedImageProcessor(
    MemoryConfig(chunk_size_mb=256, enable_chunking=True)
)
```

#### 方法

##### `process_in_chunks(image, process_func, progress_callback=None)`

分块处理图像。

**参数**:
- `image` (np.ndarray): 输入图像
- `process_func` (callable): 处理函数
- `progress_callback` (callable): 进度回调

**返回**: `np.ndarray`

---

##### `estimate_memory_usage(image_shape)`

估算内存使用量。

**参数**:
- `image_shape` (tuple): 图像形状

**返回**: `float` 内存使用量 (MB)

---

## 批量处理

### BatchAnalyzer

批量分析器。

#### 初始化

```python
from batch_analyzer import BatchAnalyzer

analyzer = BatchAnalyzer()
```

#### 方法

##### `analyze_batch(image_paths, output_dir=None)`

批量分析图像。

**参数**:
- `image_paths` (List[str]): 图像路径列表
- `output_dir` (str, optional): 输出目录

**返回**: `BatchAnalysisResult`

**示例**:
```python
result = analyzer.analyze_batch(
    ['img1.jpg', 'img2.jpg', 'img3.jpg'],
    output_dir='./analysis/'
)
```

---

## 命令行接口

### 全局选项

```bash
lut-generator [command] [options]
```

**通用选项**:
- `--help`: 显示帮助信息
- `--version`: 显示版本号
- `--verbose`: 详细输出
- `--quiet`: 静默模式

### 命令

#### `analyze` - 分析图像并生成 LUT

```bash
lut-generator analyze \
  --input <path> \
  --output <path> \
  [options]
```

**选项**:
- `--input, -i` (required): 输入图像或目录
- `--output, -o` (required): 输出 .cube 文件路径
- `--size, -s` (default: 33): LUT 网格大小
- `--smoothness` (default: 0.5): 平滑度
- `--batch`: 批量模式
- `--preview`: 生成预览
- `--preview-input`: 预览输入图像
- `--preview-output`: 预览输出目录

#### `apply` - 应用 LUT 到图像

```bash
lut-generator apply \
  --input <path> \
  --lut <path> \
  --output <path> \
  [options]
```

**选项**:
- `--input, -i` (required): 输入图像或目录
- `--lut, -l` (required): LUT 文件路径
- `--output, -o` (required): 输出路径
- `--batch`: 批量模式
- `--interpolation` (default: trilinear): 插值方法
- `--gamma` (default: 1.0): Gamma 校正

#### `report` - 生成完整报告

```bash
lut-generator report \
  --reference <path> \
  --target <path> \
  --input <path> \
  --output <path> \
  [options]
```

**选项**:
- `--reference, -r` (required): 参考图像
- `--target, -t` (required): 目标图像
- `--input, -i` (required): 输入图像
- `--output, -o` (required): 输出目录
- `--theme` (default: dark): 主题
- `--no-slider`: 不包含滑块
- `--no-histogram`: 不包含直方图
- `--no-gamut`: 不包含色域图

#### `visualize` - 生成可视化

```bash
lut-generator visualize \
  --input <path> \
  --output <path> \
  [options]
```

**选项**:
- `--input, -i` (required): 输入图像
- `--output, -o` (required): 输出目录
- `--histogram`: 生成直方图
- `--gamut`: 生成色域图
- `--all`: 生成所有可视化

---

## 数据类型

### LUT3DConfig

```python
@dataclass
class LUT3DConfig:
    grid_size: int = 33
    smoothness: float = 0.5
    use_advanced_interpolation: bool = True
    color_space: str = 'lab'
    white_balance: bool = True
```

### ApplyConfig

```python
@dataclass
class ApplyConfig:
    interpolation_method: str = 'trilinear'
    clamp_output: bool = True
    gamma_correction: float = 1.0
    preserve_highlights: bool = False
    preserve_shadows: bool = False
```

### ComparisonConfig

```python
@dataclass
class ComparisonConfig:
    mode: str = 'side_by_side'
    border_width: int = 2
    show_labels: bool = True
    show_statistics: bool = True
    label_font_size: int = 16
    label_color: str = 'white'
```

### CacheConfig

```python
@dataclass
class CacheConfig:
    max_size: int = 100
    ttl_seconds: int = 3600
    enabled: bool = True
```

### ParallelConfig

```python
@dataclass
class ParallelConfig:
    num_workers: int = None
    chunk_size: int = 4
    use_processes: bool = True
    max_memory_per_worker: int = 2048
```

### MemoryConfig

```python
@dataclass
class MemoryConfig:
    chunk_size_mb: int = 256
    max_image_size: int = 10000
    enable_chunking: bool = True
    garbage_collection_interval: int = 10
```

### OptimizerStats

```python
@dataclass
class OptimizerStats:
    cache_hits: int = 0
    cache_misses: int = 0
    total_processing_time: float = 0.0
    total_images_processed: int = 0
    peak_memory_mb: float = 0.0
    parallel_speedup: float = 1.0
```

---

## 错误处理

所有模块都使用标准 Python 异常处理。

### 常见异常

- `FileNotFoundError`: 文件不存在
- `ValueError`: 无效的参数值
- `MemoryError`: 内存不足
- `IOError`: I/O 错误

### 错误处理示例

```python
try:
    result = generator.generate_from_images('ref.jpg', 'target.jpg')
except FileNotFoundError as e:
    print(f"文件未找到：{e}")
except ValueError as e:
    print(f"参数错误：{e}")
except MemoryError as e:
    print(f"内存不足，请启用分块处理")
```

---

## 最佳实践

### 1. 性能优化

```python
# 使用缓存和分块处理
optimizer = PerformanceOptimizer(
    cache_config=CacheConfig(max_size=100),
    memory_config=MemoryConfig(enable_chunking=True)
)

# 批量处理使用并行
processor = ParallelProcessor(
    ParallelConfig(num_workers=4, use_processes=True)
)
```

### 2. 内存管理

```python
# 处理大图像时启用分块
config = MemoryConfig(
    chunk_size_mb=128,  # 减小分块
    enable_chunking=True
)

# 定期清空缓存
optimizer.clear_cache()
```

### 3. 错误处理

```python
# 始终检查文件存在
if not os.path.exists(input_path):
    raise FileNotFoundError(input_path)

# 验证参数范围
if not 0.0 <= smoothness <= 1.0:
    raise ValueError("smoothness 必须在 0.0-1.0 之间")
```

---

## 版本历史

- **v1.0.0** (2026-04-13): 初始 API 文档
  - 完整 API 参考
  - 所有公共类和函数
  - 使用示例和最佳实践

---

**文档维护**: RD Agent  
**联系方式**: 项目 ID: 【图片分析风格生成 LUT 工具_标准版_20260413153500】

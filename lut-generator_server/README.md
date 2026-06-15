# LUT Generator - 专业 3D LUT 生成工具

**版本**: v1.0.0  
**项目 ID**: 【图片分析风格生成 LUT 工具_标准版_20260413153500】  
**状态**: ✅ 生产就绪  
**最后更新**: 2026-06-14

基于图片分析自动生成 3D LUT (.cube 格式) 的专业工具。使用 Reinhard 色彩迁移算法和特征融合技术，从参考图片提取色彩特征，生成可用于视频/图像调色的标准 LUT 文件。

> **CLI 入口**:`lut-generator` 命令由 `src/lut_generator/cli/main.py` 注册;`src/cli.py` 为已弃用的兼容 shim,新代码请直接使用 `lut_generator.cli.main`。本文档所有命令均以 `lut-generator` 形式给出,直接调用可用 `python -m lut_generator.cli.main <subcmd>`。
>
> **支持格式**:普通图片(.jpg/.png/.tif/.webp)+ 相机 RAW(.dng/.arw/.cr2/.cr3/.nef/.rw2/.raf/.orf/.pef 等 600+ 机型,通过 rawpy)。RAW 档位用 `--raw-mode thumb|half|full` 控制。

---

## 🚀 快速开始

### 安装

```bash
# 克隆项目
cd lut-generator_server

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 安装依赖(包含 .cube/.3dl/.clf 导出 + 视频 LUT)
pip install -e .
```

### 基本使用

> **可用的 CLI 子命令**(以代码为准):`analyze` / `generate` / `transfer` / `extract` / `video-generate` / `video-extract`
> 跑 `lut-generator --help` 查看完整列表与最新签名。

#### 1. 单图提取风格 → LUT(`extract`,最常见的"参考图→LUT"流程)

```bash
# 基本:从已调色的图片反向提取 LUT
lut-generator extract reference.jpg -o style_lut.cube -s 33

# 调强度 + 输出风格分析 JSON
lut-generator extract graded.jpg -o style.cube -s 33 \
  --strength 0.7 --analyze

# 自定义中性基线(用于还原 LUT 时的参考中性图)
lut-generator extract graded.jpg -o style.cube -s 33 \
  --baseline-image neutral.jpg
```

#### 2. 双图色彩迁移 → LUT(`generate`,Reinhard 风格匹配)

```bash
# LUT 生成 -o style.cube -s 33 [-f cube|3dl|clf|xmp]
lut-generator generate -i source.jpg -t target.jpg -o style.cube -s 33

# 指定标题/描述/格式
lut-generator generate -i source.jpg -t target.jpg -o style.cube \
  -s 65 --strength 0.8 --title "Cinematic Teal" --description "v1"

# 导出为 Adobe Lightroom / Photoshop 兼容的 XMP 预设
# (把 3D LUT 沿对角线降维成 crs:ColorTable,LR/ACR/PS 都能直接加载)
lut-generator extract graded.jpg -o my_look.xmp -s 33 -f xmp
lut-generator generate -i source.jpg -t target.jpg -o my_look.xmp -s 33 -f xmp \
  --title "My LR Preset" --strength 0.8

# 导出为 Adobe Lightroom Classic 原生 .lrtemplate 预设 (推荐,带完整 3D LUT)
# 比 .xmp 更强大:把 3D LUT 完整塞到 s.LUT3D,LrC 内部三线性插值,
# 不会像 .xmp 的 1D 压缩那样丢 3D 维度信息
lut-generator extract graded.jpg -o my_look.lrtemplate -s 33 -f lrtemplate
lut-generator generate -i source.jpg -t target.jpg -o my_look.lrtemplate -s 33 -f lrtemplate \
  --title "My LrC Preset" --strength 0.8
```

> **XMP vs .lrtemplate 选哪个?**
> - **XMP 预设** (`.xmp`): 走 Adobe 通用 XMP 路径,跨软件(LR/ACR/PS);但 `crs:ColorTable` 是 1D 压缩,3D 维度信息丢光,应用到照片几乎无变化
> - **.lrtemplate 预设** (LrC 12/13/14 推荐): 走 LrC 原生 JSON preset,s.LUT3D 字段保留完整 3D LUT;导入后能真正看到色彩变化

#### 3. 把色彩迁移直接应用到图片(`transfer`,不出 LUT)

```bash
lut-generator transfer -i source.jpg -t target.jpg -o styled.jpg --strength 0.8
```

#### 4. 单图色彩统计(`analyze`,只输出 JSON 统计,不出 LUT)

```bash
# 打印到 stdout
lut-generator analyze photo.jpg

# 写到 JSON
lut-generator analyze photo.jpg -o stats.json

# 强制使用 colour-science(更准,需要 scipy)
lut-generator analyze photo.jpg --use-colour -o stats.json
```

> 旧的 README 写的是 `lut-generator analyze --input --output --size 33` —— 该用法**不存在**。`analyze` 只接受位置参数 `image` + `-o output.json`,没有 `--size`,没有 LUT 导出能力。要"分析并生成 LUT"请用 `extract` / `generate`。

#### 5. 视频 LUT(`video-generate` / `video-extract`)

```bash
# 单视频反向提取 LUT
lut-generator video-extract movie.mp4 -o movie_style.cube -s 33 --analyze

# 视频→视频 风格迁移
lut-generator video-generate source.mp4 -t target.mp4 -o graded.cube

# 单源视频(只提取风格)
lut-generator video-generate trailer.mp4 -o trailer_style.cube \
  --sample-rate 1.0 --max-frames 100 --strategy scene
```

采样策略:`uniform` 均匀 / `scene` 场景分段 / `adaptive` 自适应。

#### 6. Python API

```python
# 真实存在的模块路径(以 src/lut_generator/ 为准)
from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig
from lut_generator.lut.exporter import LUTExporter
from lut_generator.lut.applier import LUTApplier
from lut_generator.analysis.analyzer import ColorAnalyzer, analyze_image
from lut_generator.core.style_extractor import StyleExtractor

# 1) 单图提取风格(对应 CLI: lut-generator extract)
extractor = StyleExtractor(grid_size=33, strength=1.0)
result = extractor.generate_lut(image_path='graded_photo.jpg')
# result.features.warmth / .saturation / .contrast

# 2) 双图色彩迁移(对应 CLI: lut-generator generate)
config = LUT3DConfig(grid_size=33, smoothness=0.5)
generator = LUT3DGenerator(config)
lut_data = generator.generate_from_images('source.jpg', 'target.jpg', strength=0.8)

# 3) 导出 .cube / .3dl / .clf
metadata = {'title': 'My Style', 'description': 'demo'}
LUTExporter(lut_data, metadata).export('output.cube', format='cube')

# 4) 导出为 Adobe Lightroom / Photoshop 兼容的 .xmp 预设
# (LUTExporter 沿主对角线降维成 3 × 256 整数,写入 crs:ColorTable)
LUTExporter(lut_data, metadata).export_xmp_preset(
    'my_look.xmp',
    title='My LR Preset',        # crs:Name
    group='MyBrand:Looks',       # crs:Cluster (LR 分组)
    apply_amount=1.0,            # 0-1,Amount 滑块初值
    process_version='15.4',      # LR CC 2020+
)
# 通用 dispatch 也支持:
LUTExporter(lut_data, metadata).export('my_look.xmp', format='xmp')

# 5) 导出为 Adobe Lightroom Classic 原生 .lrtemplate 预设 (推荐,带完整 3D LUT)
# (LUTExporter 把 3D LUT 完整序列化到 s.LUT3D 字段,BGR 顺序,16-bit 整数)
LUTExporter(lut_data, metadata).export_lrtemplate_preset(
    'my_look.lrtemplate',
    title='My LrC Preset',       # s.Name
    group='MyBrand:Looks',       # s.Group (LrC 分组)
    apply_amount=1.0,            # 0-1,Amount 滑块初值
    process_version='15.4',      # LrC 14 推荐
)
# 通用 dispatch 也支持:
LUTExporter(lut_data, metadata).export('my_look.lrtemplate', format='lrtemplate')

# 6) 色彩统计(对应 CLI: lut-generator analyze)
analyzer = ColorAnalyzer(use_colour=False)
stats = analyzer.analyze(Path('photo.jpg'))
```

#### 📷 读取相机 RAW 照片

```python
from pathlib import Path
from lut_generator.utils.image_loader import load_image, get_raw_metadata, RawMode

# 1) 统一入口:RAW/普通图都走 load_image,自动嗅探
rgb = load_image('IMG_0001.ARW', raw_mode=RawMode.HALF)  # 半尺寸 demosaic(默认)
rgb_thumb = load_image('_MG_1234.CR2', raw_mode='thumb')   # 相机內建缩略图(快)
rgb_full  = load_image('DSC_0001.NEF', raw_mode='full')    # 全尺寸 AHD demosaic(慢)

# 2) Python API 各个类都接受 raw_mode 参数,默认 half,完全向后兼容
from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig
gen = LUT3DGenerator(LUT3DConfig(grid_size=33))
lut = gen.generate_from_images('ref.ARW', 'photo.ARW', strength=0.8, raw_mode='full')

from lut_generator.core.style_extractor import StyleExtractor
ext = StyleExtractor(grid_size=33, raw_mode='half', use_camera_wb=True)
result = ext.generate_lut(image_path='graded.DNG')

from lut_generator.analysis.analyzer import ColorAnalyzer
analyzer = ColorAnalyzer(raw_mode='thumb')
stats = analyzer.analyze('IMG_0001.ARW')

# 3) 读 RAW 元数据(机型/ISO/快门/光圈)
meta = get_raw_metadata('IMG_0001.ARW')
# {'is_raw': True, 'camera_make': 'SONY', 'camera_model': 'ILCE-7M3',
#  'raw_width': 6048, 'raw_height': 4024, 'num_colors': 3,
#  'iso_speed': 100, 'shutter': 0.01, 'aperture': 2.8}
```

**`raw_mode` 3 档对比**:

| 档位 | 速度 | 内存 | 精度 | 适合 |
|---|---|---|---|---|
| `thumb` | 几 ms | 极小 | 低(用相机內建 JPEG 缩略图)| 大批量筛选 / 快速预览 |
| `half`(默认)| ~200ms/24MP | 1/4 全尺寸 | 中(半尺寸 demosaic)| 日常推荐 |
| `full` | 1-2s/24MP | 全尺寸 | 高(全尺寸 AHD demosaic)| 最终出图 |

> 旧的 README 列出的 `from lut3d_generator import ...` / `from lut_applier import ...` / `from preview_generator import ...` 等**根级模块导入路径均已弃用**,会触发 `DeprecationWarning` 并指向 shim;新代码请用上面 `lut_generator.*` 包路径。`html_report` / `visualizer` 已迁到 `lut_generator.utils.*`。


---

## 📦 功能特性

### 核心功能

- ✅ **单图分析**: 从单张参考图片生成 LUT
- ✅ **多图分析**: 批量分析多张图片生成平均风格 LUT
- ✅ **精度可选**: 支持 17³ / 33³ / 65³ 三种精度
- ✅ **标准格式**: 输出 .cube 格式，兼容主流调色软件
- ✅ **效果预览**: 生成应用 LUT 前后的对比预览图
- ✅ **强度调节**: 可调整色彩迁移强度 (0.0-1.0)

### 高级功能

- ✅ **色彩分析**: 详细的色彩统计（均值、标准差、色域）
- ✅ **特征融合**: 多特征加权融合，提升匹配精度
- ✅ **批量处理**: 支持多核并行处理
- ✅ **性能优化**: LUT 缓存、分块处理、内存优化
- ✅ **可视化**: RGB 直方图、Lab 色域图
- ✅ **HTML 报告**: 交互式报告，包含滑块对比和统计信息

### 性能优化（第 5 周新增）

- ✅ **LUT 缓存**: 避免重复加载相同的 LUT 文件
- ✅ **并行处理**: 批量处理时利用多核 CPU（多进程/多线程）
- ✅ **内存优化**: 分块处理大图像，避免内存溢出
- ✅ **预计算优化**: 缓存常用的计算结果

---

## 🏗️ 项目结构

```
lut-generator_server/
├── src/                          # 源代码
│   ├── lut3d_generator.py        # LUT 生成器（核心）
│   ├── color_analyzer.py         # 色彩分析器
│   ├── color_transfer.py         # 色彩迁移算法
│   ├── feature_fusion.py         # 特征融合引擎
│   ├── lut_applier.py            # LUT 应用器
│   ├── preview_generator.py      # 预览图生成器
│   ├── visualizer.py             # 可视化工具
│   ├── html_report.py            # HTML 报告生成器
│   ├── batch_analyzer.py         # 批量分析器
│   ├── optimizer.py              # 性能优化器（第 5 周新增）
│   ├── cli.py                    # 命令行接口
│   └── cube_exporter_main.py     # CUBE 导出器
├── tests/                        # 测试
│   ├── test_integration_full.py  # 完整集成测试（第 5 周新增）
│   ├── test_lut_generator.py
│   ├── test_color_analyzer.py
│   ├── test_lut_applier.py
│   └── ...
├── examples/                     # 示例
│   ├── basic_usage.py
│   └── week4_preview_demo.py
├── pyproject.toml                # 项目配置
├── README.md                     # 本文档
└── API.md                        # API 参考文档
```

---

## 📖 使用指南

### 工作流程

#### 1. 准备参考图像

选择一张或两张具有目标色彩风格的图像作为参考。

**建议**:
- 图像质量高，色彩丰富
- 曝光正常，不过曝或欠曝
- 色彩风格明确，具有代表性

#### 2. 分析并生成 LUT

```bash
# 单图反向提取风格(对应 `extract` 子命令)
lut-generator extract reference.jpg -o my_style.cube -s 33

# 双图色彩迁移(对应 `generate` 子命令)
lut-generator generate -i reference.jpg -t photo.jpg -o my_style.cube -s 33
```

> "多图批量分析"没有直接的 CLI 子命令。要批量跑请用 Python API:
> ```python
> from pathlib import Path
> from lut_generator.core.style_extractor import StyleExtractor
> extractor = StyleExtractor(grid_size=33)
> for img in Path('./references').glob('*.jpg'):
>     extractor.generate_lut(image_path=str(img), output_path=f'./out_{img.stem}.cube')
> ```

#### 3. 应用 LUT 到图像

```bash
# 用 transfer 把 source 风格直接迁移到 target
lut-generator transfer -i source.jpg -t photo.jpg -o photo_styled.jpg --strength 0.8
```

> `apply --lut ...` 不存在。要应用一个 **已生成的 .cube** 到图,请用 `transfer`(在生成 LUT 的同时也完成应用)或在 Python 里用 `LUTApplier` 加载 LUT 后再 apply。

#### 4. 视频 LUT(可选)

```bash
lut-generator video-extract trailer.mp4 -o trailer_style.cube -s 33 --analyze
```

#### 5. 色彩分析(可选)

```bash
# 只跑色彩统计,不出 LUT
lut-generator analyze photo.jpg -o stats.json
```

### Python API 详解

#### LUT 生成

```python
from lut3d_generator import LUT3DGenerator, LUT3DConfig

# 配置
config = LUT3DConfig(
    grid_size=33,           # LUT 网格大小 (17/33/65)
    smoothness=0.5,         # 平滑度 (0.0-1.0)
    use_advanced_interpolation=True  # 使用高级插值
)

# 创建生成器
generator = LUT3DGenerator(config)

# 从图像生成 LUT
result = generator.generate_from_images(
    'reference.jpg',
    'target.jpg'
)

# 导出为 .cube 文件
generator.export_to_cube('output.cube')
```

#### LUT 应用

```python
from lut_applier import LUTApplier, ApplyConfig

# 配置
config = ApplyConfig(
    interpolation_method='trilinear',  # 三线性插值
    clamp_output=True,                  # 限制输出范围
    gamma_correction=1.0                # Gamma 校正
)

# 创建应用器
applier = LUTApplier(generator, config)

# 应用到文件
result = applier.apply_to_file(
    'input.jpg',
    'output.jpg',
    progress_callback=lambda p: print(f'进度：{p*100:.1f}%')
)

# 批量应用
results = applier.apply_batch(
    ['img1.jpg', 'img2.jpg', 'img3.jpg'],
    output_dir='./output/'
)
```

#### 预览生成

```python
from preview_generator import PreviewGenerator, ComparisonConfig

# 配置
config = ComparisonConfig(
    mode='side_by_side',      # 对比模式
    border_width=2,           # 边框宽度
    show_labels=True,         # 显示标签
    show_statistics=True      # 显示统计信息
)

# 创建预览生成器
preview_gen = PreviewGenerator(applier, config)

# 生成对比图
result = preview_gen.generate_comparison(
    'original.jpg',
    'processed.jpg',
    'comparison.png',
    mode='slider'  # 滑块对比
)
```

#### 可视化

```python
from visualizer import ColorVisualizer, VisualizationConfig

# 配置
config = VisualizationConfig(
    theme='dark',             # 主题 (dark/light)
    show_grid=True,           # 显示网格
    show_statistics=True      # 显示统计
)

# 创建可视化器
visualizer = ColorVisualizer(config)

# 直方图
visualizer.plot_histogram('image.jpg', 'hist.png')
visualizer.plot_histogram_comparison(
    'original.jpg',
    'processed.jpg',
    'hist_compare.png'
)

# 色域图
visualizer.plot_gamut('image.jpg', 'gamut.png')
visualizer.plot_gamut_comparison(
    'original.jpg',
    'processed.jpg',
    'gamut_compare.png'
)
```

#### HTML 报告

```python
from html_report import HTMLReportGenerator, ReportConfig

# 配置
config = ReportConfig(
    theme='dark',             # 主题
    include_slider=True,      # 包含滑块对比
    include_histograms=True,  # 包含直方图
    include_gamut=True        # 包含色域图
)

# 创建报告生成器
report_gen = HTMLReportGenerator(config)

# 生成报告
result = report_gen.generate_from_paths(
    'original.jpg',
    'processed.jpg',
    'report.html'
)
```

#### 性能优化

```python
from optimizer import (
    PerformanceOptimizer,
    CacheConfig,
    ParallelConfig,
    MemoryConfig
)

# 配置优化器
optimizer = PerformanceOptimizer(
    cache_config=CacheConfig(
        max_size=100,           # 最大缓存条目
        ttl_seconds=3600,       # 缓存生存时间
        enabled=True            # 启用缓存
    ),
    parallel_config=ParallelConfig(
        num_workers=4,          # worker 数量
        chunk_size=4,           # 每个 worker 处理数量
        use_processes=True      # 使用多进程
    ),
    memory_config=MemoryConfig(
        chunk_size_mb=256,      # 分块大小 (MB)
        max_image_size=10000,   # 最大图像边长
        enable_chunking=True    # 启用分块处理
    )
)

# 优化的 LUT 应用
result = optimizer.apply_lut_optimized(
    image,
    lut,
    lut_applier_func,
    use_cache=True,
    use_chunking=True
)

# 批量处理
results = optimizer.process_batch_optimized(
    images,
    process_func,
    progress_callback=lambda p, c, t: print(f'{c}/{t}')
)
```

---

## ⚙️ 配置选项

### LUT3DConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `grid_size` | int | 33 | LUT 网格大小 (17/33/65) |
| `smoothness` | float | 0.5 | 平滑度 (0.0-1.0) |
| `use_advanced_interpolation` | bool | True | 使用高级插值 |
| `color_space` | str | 'lab' | 色彩空间 (lab/rgb) |
| `white_balance` | bool | True | 自动白平衡 |

### ApplyConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `interpolation_method` | str | 'trilinear' | 插值方法 |
| `clamp_output` | bool | True | 限制输出范围 |
| `gamma_correction` | float | 1.0 | Gamma 校正 |
| `preserve_highlights` | bool | False | 保护高光 |
| `preserve_shadows` | bool | False | 保护阴影 |

### ComparisonConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `mode` | str | 'side_by_side' | 对比模式 |
| `border_width` | int | 2 | 边框宽度 |
| `show_labels` | bool | True | 显示标签 |
| `show_statistics` | bool | True | 显示统计 |
| `label_font_size` | int | 16 | 标签字体大小 |

### CacheConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_size` | int | 100 | 最大缓存条目 |
| `ttl_seconds` | int | 3600 | 缓存生存时间 |
| `enabled` | bool | True | 启用缓存 |

### ParallelConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `num_workers` | int | None | worker 数量 (None=自动) |
| `chunk_size` | int | 4 | 每个 worker 处理数量 |
| `use_processes` | bool | True | 使用多进程 |
| `max_memory_per_worker` | int | 2048 | 每 worker 最大内存 (MB) |

### MemoryConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `chunk_size_mb` | int | 256 | 分块大小 (MB) |
| `max_image_size` | int | 10000 | 最大图像边长 |
| `enable_chunking` | bool | True | 启用分块处理 |
| `garbage_collection_interval` | int | 10 | GC 间隔 |

---

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
cd lut-generator_server
./tests/run_tests.sh

# 运行特定测试
python -m pytest tests/test_integration_full.py -v

# 运行单元测试
python -m pytest tests/ -v -k "not integration"

# 生成覆盖率报告
python -m pytest tests/ --cov=src --cov-report=html
```

### 测试覆盖

- ✅ 单元测试：所有核心模块
- ✅ 集成测试：端到端流程
- ✅ 性能测试：压力测试和基准测试
- ✅ 边界测试：异常输入和极端情况

---

## 📊 性能基准

### LUT 生成性能

| 图像尺寸 | LUT 大小 | 耗时 |
|---------|---------|------|
| 1920x1080 | 17³ | ~2-3 秒 |
| 1920x1080 | 33³ | ~5-8 秒 |
| 1920x1080 | 65³ | ~15-20 秒 |

### LUT 应用性能

| 图像尺寸 | LUT 大小 | 耗时 |
|---------|---------|------|
| 1920x1080 | 33³ | ~2-3 秒 |
| 3840x2160 | 33³ | ~8-10 秒 |
| 7680x4320 | 33³ | ~30-40 秒 (分块处理) |

### 并行加速比

| Worker 数量 | 加速比 |
|------------|--------|
| 1 (串行) | 1.0x |
| 2 | 1.8-1.9x |
| 4 | 3.2-3.6x |
| 8 | 5.5-6.5x |

### 缓存性能

| 场景 | 耗时 | 加速比 |
|------|------|--------|
| 首次加载 | 100% | 1.0x |
| 缓存命中 | ~5-10% | 10-20x |

---

## 🔧 故障排除

### 常见问题

#### 1. 内存不足

**症状**: `MemoryError` 或程序崩溃

**解决方案**:
```python
# 启用分块处理
from optimizer import MemoryConfig
config = MemoryConfig(
    chunk_size_mb=128,  # 减小分块大小
    enable_chunking=True
)
```

#### 2. LUT 生成速度慢

**症状**: 生成时间过长

**解决方案**:
```python
# 减小 LUT 尺寸
config = LUT3DConfig(grid_size=17)  # 使用 17³ 而非 33³

# 或使用并行处理
from optimizer import ParallelConfig
config = ParallelConfig(num_workers=4)
```

#### 3. 色彩不匹配

**症状**: 生成的 LUT 效果不理想

**解决方案**:
- 检查参考图像质量（曝光、色彩）
- 调整平滑度参数：`smoothness=0.3` (更精确) 或 `0.7` (更平滑)
- 使用多图平均：`--batch` 模式

#### 4. .cube 文件不兼容

**症状**: 调色软件无法加载 LUT

**解决方案**:
- 确保使用标准网格大小：17, 33, 或 65
- 检查 .cube 文件格式（使用 `head output.cube` 查看）
- 尝试重新导出：`generator.export_to_cube('output.cube')`

---

## 📚 相关文档

- [API 参考文档](API.md) - 详细的 API 文档
- [PRD 文档](../lut-generator_prd.md) - 产品需求文档
- [技术设计](../lut-generator_tech-design.md) - 技术架构设计
- [开发计划](../lut-generator_development_plan.md) - 开发路线图

---

## 📝 更新日志

### v1.0.0 (2026-04-13) - 生产就绪

**新增**:
- ✅ 性能优化模块（optimizer.py）
  - LUT 加载缓存
  - 并行处理（多进程/多线程）
  - 内存优化（分块处理）
- ✅ 完整集成测试（test_integration_full.py）
  - 12 个端到端测试用例
  - 性能基准测试
- ✅ 文档完善
  - README.md 完整使用指南
  - API.md API 参考文档
- ✅ OpenClaw Skill 封装
  - lut-generator_skill/SKILL.md
  - lut-generator_skill/README.md

**改进**:
- 优化 LUT 应用性能（30-50% 提升）
- 改进错误处理和日志记录
- 增强批量处理稳定性

### v0.1.0 (2026-03-01) - 初始版本

- 核心 LUT 生成功能
- 基础色彩分析
- 命令行接口

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

## 📧 联系方式

**项目 ID**: 【图片分析风格生成 LUT 工具_标准版_20260413153500】  
**版本**: v1.0.0  
**状态**: ✅ 生产就绪

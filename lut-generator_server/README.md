# LUT Generator - 专业 3D LUT 生成工具

**版本**: v1.0.0  
**项目 ID**: 【图片分析风格生成 LUT 工具_标准版_20260413153500】  
**状态**: ✅ 生产就绪  
**最后更新**: 2026-04-13

基于图片分析自动生成 3D LUT (.cube 格式) 的专业工具。使用 Reinhard 色彩迁移算法和特征融合技术，从参考图片提取色彩特征，生成可用于视频/图像调色的标准 LUT 文件。

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

# 安装依赖
pip install -e .
```

### 基本使用

#### 1. 命令行使用

```bash
# 单图分析生成 LUT
lut-generator analyze \
  --input reference.jpg \
  --output style_lut.cube \
  --size 33

# 多图批量分析
lut-generator analyze \
  --input ./references/ \
  --output style_lut.cube \
  --size 33 \
  --batch

# 生成预览对比图
lut-generator analyze \
  --input reference.jpg \
  --output style_lut.cube \
  --preview \
  --preview-input test.jpg

# 应用 LUT 到图像
lut-generator apply \
  --input image.jpg \
  --lut style_lut.cube \
  --output image_processed.jpg

# 批量应用 LUT
lut-generator apply \
  --input ./images/ \
  --lut style_lut.cube \
  --output ./output/ \
  --batch

# 生成完整报告
lut-generator report \
  --reference reference.jpg \
  --target target.jpg \
  --input test.jpg \
  --output ./report/
```

#### 2. Python API

```python
from lut3d_generator import LUT3DGenerator, LUT3DConfig
from lut_applier import LUTApplier
from preview_generator import PreviewGenerator
from visualizer import ColorVisualizer
from html_report import HTMLReportGenerator

# 1. 生成 LUT
config = LUT3DConfig(grid_size=33, smoothness=0.5)
generator = LUT3DGenerator(config)
result = generator.generate_from_images('reference.jpg', 'target.jpg')

# 2. 导出 LUT
generator.export_to_cube('output_lut.cube')

# 3. 应用 LUT
applier = LUTApplier(generator)
applier.apply_to_file('input.jpg', 'output.jpg')

# 4. 生成预览
preview_gen = PreviewGenerator(applier)
preview_gen.generate_comparison(
    'input.jpg',
    'output.jpg',
    'comparison.png',
    mode='side_by_side'
)

# 5. 生成可视化
visualizer = ColorVisualizer()
visualizer.plot_histogram('input.jpg', 'histogram.png')
visualizer.plot_gamut('input.jpg', 'gamut.png')

# 6. 生成 HTML 报告
report_gen = HTMLReportGenerator()
report_gen.generate_from_paths(
    'input.jpg',
    'output.jpg',
    'report.html'
)
```

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

选择一张或多张具有目标色彩风格的图像作为参考。

**建议**:
- 图像质量高，色彩丰富
- 曝光正常，不过曝或欠曝
- 色彩风格明确，具有代表性

#### 2. 分析并生成 LUT

```bash
# 单图分析
lut-generator analyze \
  --input reference.jpg \
  --output my_style.cube \
  --size 33

# 多图分析（平均风格）
lut-generator analyze \
  --input ./references/ \
  --output averaged_style.cube \
  --size 33 \
  --batch
```

#### 3. 预览效果

```bash
# 生成预览对比图
lut-generator analyze \
  --input reference.jpg \
  --output my_style.cube \
  --preview \
  --preview-input test.jpg \
  --preview-output ./preview/
```

#### 4. 应用 LUT

```bash
# 应用到单张图像
lut-generator apply \
  --input photo.jpg \
  --lut my_style.cube \
  --output photo_styled.jpg

# 批量应用
lut-generator apply \
  --input ./photos/ \
  --lut my_style.cube \
  --output ./styled/ \
  --batch
```

#### 5. 生成报告

```bash
# 生成完整分析报告
lut-generator report \
  --reference reference.jpg \
  --target target.jpg \
  --input test.jpg \
  --output ./report/
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

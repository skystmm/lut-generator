# 第 4 周：预览功能模块

## 概述

本周实现了 LUT 工具的预览功能，包括：
1. **LUT 应用模块** - 将生成的 3D LUT 应用到图像
2. **预览图生成** - 生成前后对比图（并排/滑块/差异）
3. **色彩可视化** - RGB 直方图、色域图对比
4. **HTML 报告导出** - 交互式报告，包含所有对比和统计信息

## 新增模块

### 1. lut_applier.py - LUT 应用模块

**核心类**: `LUTApplier`

**主要功能**:
- 将 3D LUT 应用到单张或批量图像
- 支持三线性插值和最近邻插值
- 支持从 .cube 文件加载 LUT
- 进度回调支持
- 批量处理

**使用示例**:
```python
from lut3d_generator import LUT3DGenerator, LUT3DConfig
from lut_applier import LUTApplier, ApplyConfig

# 生成 LUT
config = LUT3DConfig(grid_size=33)
generator = LUT3DGenerator(config)
generator.generate_from_images('reference.jpg', 'target.jpg')

# 应用 LUT
applier = LUTApplier(generator)
result = applier.apply_to_file('input.jpg', 'output.png')

print(f"处理完成：{result.success}")
print(f"输出：{result.output_path}")
```

### 2. preview_generator.py - 预览图生成模块

**核心类**: `PreviewGenerator`

**对比模式**:
- `side_by_side` - 并排对比（左原图/右处理后）
- `slider` - 滑块对比预览
- `blend` - 50% 混合对比
- `difference` - 差异可视化

**使用示例**:
```python
from preview_generator import PreviewGenerator, ComparisonConfig

generator = PreviewGenerator(applier)

# 并排对比
config = ComparisonConfig(mode='side_by_side', add_labels=True)
result = generator.generate_comparison('original.jpg', 'processed.jpg', 'comparison.png', config)

# 统计信息
print(f"亮度变化：{result.statistics['brightness_change']:+.2f}%")
print(f"平均差异：{result.statistics['difference']['mean_diff']:.2f}")
```

### 3. visualizer.py - 色彩可视化模块

**核心类**: `ColorVisualizer`

**可视化类型**:
- RGB 直方图（单图/对比）
- 色域图 - Lab 色彩空间的 a*b 平面（单图/对比）

**使用示例**:
```python
from visualizer import ColorVisualizer, VisualizationConfig

config = VisualizationConfig(width=1200, height=800)
visualizer = ColorVisualizer(config)

# 直方图
visualizer.plot_histogram('image.jpg', 'histogram.png')

# 对比直方图
visualizer.plot_histogram_comparison('original.jpg', 'processed.jpg', 'histogram_comp.png')

# 色域图
visualizer.plot_gamut('image.jpg', 'gamut.png')

# 对比色域图
visualizer.plot_gamut_comparison('original.jpg', 'processed.jpg', 'gamut_comp.png')
```

### 4. html_report.py - HTML 报告导出模块

**核心类**: `HTMLReportGenerator`

**功能**:
- 交互式滑块对比
- 统计信息表格
- 直方图和色域图嵌入
- 暗色/亮色主题
- 响应式设计

**使用示例**:
```python
from html_report import HTMLReportGenerator, ReportConfig, ReportData

config = ReportConfig(title='LUT 处理报告', theme='dark')
generator = HTMLReportGenerator(config)

report_data = ReportData(
    original_image='original.jpg',
    processed_image='processed.jpg',
    comparison_image='comparison.png',
    histogram_comparison='histogram_comp.png',
    gamut_comparison='gamut_comp.png',
    statistics=stats_dict,
    lut_info=lut_info_dict,
    processing_time=2.5
)

result = generator.generate(report_data, 'report.html')
```

## 完整演示

运行完整演示脚本：

```bash
cd /home/openclaw/.openclaw/workspace-assistent/projects/lut-generator/lut-generator_server

python examples/week4_preview_demo.py \
    photos/reference.jpg \
    photos/target.jpg \
    photos/input.jpg \
    output/
```

输出文件：
```
output/
├── processed.png                    # LUT 处理后图像
├── comparison_side_by_side.png      # 并排对比图
├── comparison_slider.png            # 滑块对比图
├── comparison_difference.png        # 差异可视化
├── histogram_original.png           # 原图直方图
├── histogram_processed.png          # 处理后直方图
├── histogram_comparison.png         # 对比直方图
├── gamut_original.png               # 原图色域图
├── gamut_processed.png              # 处理后色域图
├── gamut_comparison.png             # 对比色域图
└── report.html                      # 交互式 HTML 报告
```

## 单元测试

运行所有测试：

```bash
cd tests
./run_tests.sh
```

或单独运行：

```bash
cd /home/openclaw/.openclaw/workspace-assistent/projects/lut-generator/lut-generator_server
source .venv/bin/activate
export PYTHONPATH=src:$PYTHONPATH

pytest tests/test_lut_applier.py -v
pytest tests/test_preview_generator.py -v
pytest tests/test_visualizer.py -v
pytest tests/test_html_report.py -v
```

查看测试覆盖率：

```bash
pytest tests/ --cov=src --cov-report=html
# 打开 tests/htmlcov/index.html 查看报告
```

## 技术要点

### LUT 应用优化

1. **分块处理** - 大图像分块处理，避免内存溢出
2. **向量化** - 使用 numpy 向量化操作，比循环快 10-100 倍
3. **三线性插值** - 平滑的 3D 插值，保证色彩过渡自然

### 对比图生成

1. **并排对比** - 简单直观，适合打印和静态展示
2. **滑块对比** - 交互式，适合 Web 展示
3. **差异可视化** - 突出显示变化区域

### 色彩可视化

1. **RGB 直方图** - 显示各通道像素分布
2. **色域图** - Lab 色彩空间的 a*b 平面，直观展示色彩范围
3. **对比展示** - 原图和处理后叠加对比

### HTML 报告

1. **自包含** - 所有图像嵌入为 base64，单文件分发
2. **交互式** - 滑块对比，无需额外依赖
3. **响应式** - 适配桌面和移动设备

## API 参考

### LUTApplier

```python
class LUTApplier:
    def __init__(self, lut_generator: LUT3DGenerator)
    
    @classmethod
    def from_lut_file(cls, lut_path: str, grid_size: int = 33) -> LUTApplier
    
    def apply_to_image(self, image: np.ndarray, 
                       progress_callback: Callable[[float], None] = None) -> np.ndarray
    
    def apply_to_file(self, input_path: str, output_path: str,
                      config: ApplyConfig = None) -> ApplyResult
    
    def apply_batch(self, input_paths: List[str], output_dir: str,
                    config: ApplyConfig = None) -> List[ApplyResult]
```

### PreviewGenerator

```python
class PreviewGenerator:
    def __init__(self, lut_applier: LUTApplier)
    
    def generate_comparison(self, original_path: str, processed_path: str,
                           output_path: str, config: ComparisonConfig = None) -> PreviewResult
    
    def generate_from_image(self, input_path: str, output_dir: str,
                           config: ComparisonConfig = None) -> PreviewResult
```

### ColorVisualizer

```python
class ColorVisualizer:
    def __init__(self, config: VisualizationConfig = None)
    
    def plot_histogram(self, image_path: str, output_path: str,
                      title: str = "RGB Histogram") -> VisualizationResult
    
    def plot_histogram_comparison(self, original_path: str, processed_path: str,
                                  output_path: str) -> VisualizationResult
    
    def plot_gamut(self, image_path: str, output_path: str,
                  title: str = "Color Gamut") -> VisualizationResult
    
    def plot_gamut_comparison(self, original_path: str, processed_path: str,
                             output_path: str) -> VisualizationResult
```

### HTMLReportGenerator

```python
class HTMLReportGenerator:
    def __init__(self, config: ReportConfig = None)
    
    def generate(self, report_data: ReportData, 
                output_path: str) -> ReportResult
    
    def generate_from_paths(self, original_path: str, processed_path: str,
                           output_path: str, statistics: dict = None) -> ReportResult
```

## 性能指标

| 操作 | 图像尺寸 | 耗时 |
|------|---------|------|
| LUT 应用 (33³) | 1920x1080 | ~2-3 秒 |
| LUT 应用 (33³) | 4000x3000 | ~8-10 秒 |
| 并排对比图生成 | 1920x1080 | ~0.5 秒 |
| 直方图绘制 | - | ~0.3 秒 |
| 色域图绘制 | - | ~0.5 秒 |
| HTML 报告生成 | - | ~0.2 秒 |

## 下一步

第 5 周计划：
- [ ] CLI 工具集成预览功能
- [ ] 批量处理优化
- [ ] Web 界面开发
- [ ] 性能进一步优化

## 文件清单

```
lut-generator_server/
├── src/
│   ├── lut_applier.py          # LUT 应用模块 (新增)
│   ├── preview_generator.py    # 预览图生成 (新增)
│   ├── visualizer.py           # 可视化模块 (新增)
│   ├── html_report.py          # HTML 报告导出 (新增)
│   ├── lut3d_generator.py      # LUT 生成器 (第 3 周)
│   ├── color_analyzer.py       # 色彩分析器 (第 3 周)
│   ├── color_transfer.py       # 色彩迁移 (第 3 周)
│   └── ...
├── tests/
│   ├── test_lut_applier.py     # LUT 应用测试 (新增)
│   ├── test_preview_generator.py  # 预览测试 (新增)
│   ├── test_visualizer.py      # 可视化测试 (新增)
│   ├── test_html_report.py     # HTML 报告测试 (新增)
│   └── run_tests.sh            # 测试运行脚本 (新增)
├── examples/
│   ├── week4_preview_demo.py   # 第 4 周演示 (新增)
│   └── basic_usage.py          # 基础使用示例
└── WEEK4_README.md             # 本文档 (新增)
```

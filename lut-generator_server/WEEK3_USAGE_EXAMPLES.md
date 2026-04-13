# 第 3 周交付：批量处理 + 多图融合 - 使用示例

## 概述

本周实现了 LUT 工具的批量处理和多图融合功能，包括：

1. **批量分析模块** (`batch_analyzer.py`) - 支持目录扫描、并行分析、异常处理
2. **特征融合模块** (`feature_fusion.py`) - 支持加权平均、中值融合等多种策略
3. **CLI 命令行工具** (`cli.py`) - 统一的命令行接口

## 安装依赖

```bash
cd lut-generator_server
source .venv/bin/activate
pip install -e .
```

## 使用示例

### 1. 单图分析模式

分析单张图片的色彩特征：

```bash
# 基本用法
python src/cli.py analyze path/to/image.jpg

# 保存结果为 JSON
python src/cli.py analyze path/to/image.jpg -o analysis_result.json

# 快速模式（使用 OpenCV 而非 colour-science）
python src/cli.py analyze path/to/image.jpg --fast
```

**输出示例：**
```
Analyzing: path/to/image.jpg

=== Analysis Result ===
Image shape: (1920, 1080, 3)

Statistics:
  Mean (L,a,b): [52.34, 8.76, 15.23]
  Std  (L,a,b): [18.45, 12.34, 16.78]

Distribution:
  L range: [5.23, 95.67]
  a range: [-35.45, 42.31]
  b range: [-28.90, 48.56]
  Gamut coverage: 28.45%
  Color entropy: 6.78
  Dominant color (L,a,b): [52.34, 8.76, 15.23]

Results saved to: analysis_result.json
```

### 2. 批量分析模式

分析整个目录的图片：

```bash
# 基本用法
python src/cli.py batch ./images

# 递归扫描子目录
python src/cli.py batch ./images -r

# 保存结果为 JSON
python src/cli.py batch ./images -r -o batch_results.json

# 保存结果为文本
python src/cli.py batch ./images -o results.txt -f txt

# 指定工作线程数
python src/cli.py batch ./images -w 8

# 串行处理（调试用）
python src/cli.py batch ./images -s
```

**输出示例：**
```
Scanning directory: ./images
Recursive: True
Parallel: True

=== Batch Analysis Report ===
Total images: 15
Valid: 14
Failed: 1

Valid images:
  ✓ photo_001.jpg
  ✓ photo_002.jpg
  ✓ photo_003.jpg
  ...

Failed images:
  ✗ corrupted.jpg: Failed to load image

=== Aggregated Statistics ===
Mean (L,a,b): [51.23, 9.45, 16.78]
Std  (L,a,b): [17.89, 11.23, 15.67]
Avg gamut coverage: 26.34%
Avg color entropy: 6.45

Results saved to: batch_results.json
```

### 3. 多图融合模式

融合多张图片的色彩特征：

```bash
# 等权融合（默认）
python src/cli.py fuse ./reference_images

# 加权融合（指定每张图片的权重）
python src/cli.py fuse ./reference_images -w "3,2,1,1"

# 使用中值融合策略
python src/cli.py fuse ./reference_images -s median

# 保存融合结果
python src/cli.py fuse ./reference_images -w "2,1,1" -o fused_result.json

# 保存融合配置（便于重用）
python src/cli.py fuse ./reference_images -w "2,1,1" --save-config fusion_config.json

# 递归扫描
python src/cli.py fuse ./reference_images -r -w "1,1,1,1"
```

**输出示例：**
```
Loading images from: ./reference_images
Loaded 4 valid images

=== Fusion Result ===
Strategy: weighted_average
Weights: [0.4, 0.267, 0.2, 0.133]

Fused Statistics:
  Mean (L,a,b): [53.45, 10.23, 17.89]
  Std  (L,a,b): [16.78, 10.45, 14.23]

Fused Distribution:
  Gamut coverage: 29.67%
  Color entropy: 6.89
  Dominant color (L,a,b): [53.45, 10.23, 17.89]

Fusion result saved to: fused_result.json
```

### 4. LUT 生成模式

基于源风格和目标风格生成 LUT：

```bash
# 基本用法
python src/cli.py generate ./source_images ./target_images

# 指定 LUT 大小
python src/cli.py generate ./source ./target -s 64

# 指定输出文件
python src/cli.py generate ./source ./target -o my_style.cube -s 32

# 递归扫描子目录
python src/cli.py generate ./source ./target -r -o style.cube
```

**输出示例：**
```
Source directory: ./source_images
Target directory: ./target_images
LUT size: 32

Analyzing source images...
Source: 10 images analyzed

Analyzing target images...
Target: 8 images analyzed

Generating 32x32x32 LUT...

LUT generated successfully!
Output: style.cube
Size: 32x32x32
```

## 权重配置说明

### 权重格式

权重使用逗号分隔的数字字符串：

```bash
# 3 张图片，权重分别为 3:2:1
-w "3,2,1"

# 5 张图片，第一张权重加倍
-w "2,1,1,1,1"

# 不指定权重（等权）
# 默认行为，无需 -w 参数
```

### 权重策略

- **weighted_average** (默认): 加权平均融合
- **equal_average**: 等权平均融合
- **median**: 中值融合（抗异常值）

## 融合配置保存与加载

### 保存配置

```python
from feature_fusion import FusionConfig

config = FusionConfig(
    weights=[3.0, 2.0, 1.0],
    strategy='weighted_average'
)

config.save('my_fusion_config.json')
```

### 加载配置

```python
from feature_fusion import FusionConfig

config = FusionConfig.load('my_fusion_config.json')
print(config.weights)  # [3.0, 2.0, 1.0]
print(config.strategy)  # 'weighted_average'
```

## 编程接口示例

### 批量分析

```python
from batch_analyzer import BatchAnalyzer

# 创建分析器
analyzer = BatchAnalyzer(use_colour=True, max_workers=4)

# 分析目录
result = analyzer.analyze_directory('./images', recursive=True)

# 获取有效结果
valid_results = result.get_valid_results()
valid_paths = result.get_valid_paths()

# 聚合统计
aggregated = analyzer.aggregate_statistics(valid_results)
print(f"Mean Lab: {aggregated['mean']}")

# 保存结果
analyzer.save_results(result, 'results.json', format='json')
```

### 特征融合

```python
from feature_fusion import FeatureFusion, FusionConfig, fuse_features
from batch_analyzer import BatchAnalyzer

# 批量分析获取结果
analyzer = BatchAnalyzer()
batch_result = analyzer.analyze_directory('./reference_images')
results = batch_result.get_valid_results()

# 方法 1: 使用便捷函数
fused = fuse_features(results, weights=[2, 1, 1], strategy='weighted_average')

# 方法 2: 使用配置对象
config = FusionConfig(
    weights=[2, 1, 1],
    strategy='weighted_average',
    histogram_method='average',
    distribution_method='average'
)
fusion = FeatureFusion(config)
fused = fusion.fuse(results)

# 转换为 AnalysisResult 用于 LUT 生成
analysis_result = fused.to_analysis_result()

# 访问融合后的特征
print(f"Fused mean: {fused.statistics.mean_array()}")
print(f"Fused std: {fused.statistics.std_array()}")
```

### 自定义权重配置

```python
from feature_fusion import create_weight_config

# 创建等权配置
image_paths = ['img1.jpg', 'img2.jpg', 'img3.jpg']
config = create_weight_config(image_paths)

# 创建自定义权重配置
weights = [3.0, 2.0, 1.0]
config = create_weight_config(image_paths, weight_values=weights)
```

## 异常处理

模块会自动处理以下异常情况：

1. **文件不存在**: 跳过并记录警告
2. **不支持的格式**: 跳过并记录警告
3. **损坏的图片**: 跳过并记录错误
4. **内存不足**: 降低并行度或串行处理

所有异常都会记录到日志，不会中断整个批处理流程。

## 性能优化建议

1. **并行处理**: 默认启用，可通过 `-w` 参数调整线程数
2. **快速模式**: 使用 `--fast` 参数使用 OpenCV 而非 colour-science（更快但精度略低）
3. **串行调试**: 使用 `-s` 参数禁用并行，便于调试
4. **批量大小**: 对于大量图片（>100），建议分批处理

## 日志配置

默认日志级别为 INFO，可通过 verbose 模式获取更详细信息：

```bash
python src/cli.py batch ./images -v
```

或在代码中配置：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 支持的文件格式

- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)
- TIFF (.tiff, .tif)
- WebP (.webp)

## 输出文件格式

### JSON 格式

```json
{
  "total_images": 10,
  "valid_images": 9,
  "failed_images": 1,
  "image_results": [
    {
      "path": "image1.jpg",
      "valid": true,
      "analysis_result": {
        "statistics": {
          "mean": [52.34, 8.76, 15.23],
          "std": [18.45, 12.34, 16.78],
          "var": [340.23, 152.34, 281.45]
        },
        ...
      }
    }
  ],
  "aggregated_statistics": {
    "mean": [51.23, 9.45, 16.78],
    "std": [17.89, 11.23, 15.67],
    ...
  }
}
```

### TXT 格式

```
Total images: 10
Valid images: 9
Failed images: 1

Valid images:
  ✓ image1.jpg
  ✓ image2.jpg
  ...

Failed images:
  ✗ corrupted.jpg: Failed to load image
```

## 最佳实践

1. **参考图片选择**: 选择 3-10 张具有代表性的图片进行融合
2. **权重分配**: 给最重要/最具代表性的图片更高权重
3. **质量检查**: 批量分析后检查 failed images，排除损坏文件
4. **配置保存**: 对于常用的融合配置，保存为 JSON 便于重用
5. **版本控制**: 将融合配置纳入版本控制，确保可复现性

## 故障排除

### 问题：某些图片分析失败

**解决方案**: 
- 检查文件格式是否支持
- 检查文件是否损坏
- 查看错误日志获取详细信息

### 问题：处理速度慢

**解决方案**:
- 增加工作线程数：`-w 8`
- 使用快速模式：`--fast`
- 减少递归深度或分批处理

### 问题：内存占用高

**解决方案**:
- 减少工作线程数：`-w 2`
- 使用串行模式：`-s`
- 分批处理大量图片

## 下一步

使用生成的融合特征创建 LUT：

```bash
# 基于融合特征生成 LUT
python src/cli.py generate ./fused_source ./fused_target -o final_style.cube
```

或编程方式：

```python
from lut3d_generator import LUT3DGenerator

generator = LUT3DGenerator(size=32)
lut = generator.generate_style_transfer_lut(
    source_mean=fused_source.statistics.mean_array(),
    target_mean=fused_target.statistics.mean_array()
)
```

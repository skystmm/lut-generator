# LUT Generator Skill - 使用文档

**版本**: v1.0.0  
**最后更新**: 2026-04-13

本文档介绍如何在 OpenClaw 中使用 LUT Generator Skill。

---

## 快速开始

### 1. 安装 Skill

```bash
# 在 OpenClaw 工作区中
cd ~/.openclaw/workspace-assistent/projects/lut-generator

# 安装服务器端依赖
cd lut-generator_server
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. 在 OpenClaw 中调用

```python
# 在 OpenClaw 对话中
从 lut_generator_skill 导入技能

# 分析图像生成 LUT
分析图像生成 LUT(
    图像路径="reference.jpg",
    输出路径="output.cube",
    LUT 尺寸=33
)
```

---

## 技能功能

### 核心功能

1. **图像分析生成 LUT**
   - 从单张参考图像提取色彩风格
   - 批量分析多张图像生成平均风格
   - 支持 17³/33³/65³ 三种精度

2. **LUT 应用**
   - 将生成的 LUT 应用到图像
   - 批量处理多张图像
   - 支持多种插值方法

3. **预览和报告**
   - 生成对比预览图
   - 色彩可视化（直方图、色域图）
   - 交互式 HTML 报告

4. **性能优化**
   - LUT 缓存（10-20x 加速）
   - 并行处理（3-6x 加速）
   - 内存优化（分块处理）

---

## 使用示例

### 示例 1: 单图分析

```python
from lut_generator_skill import analyze_image_for_lut

# 分析单张图像生成 LUT
lut_path = analyze_image_for_lut(
    image_path="photos/reference.jpg",
    output_path="luts/my_style.cube",
    lut_size=33,
    smoothness=0.5
)

print(f"LUT 已生成：{lut_path}")
```

### 示例 2: 批量分析

```python
from lut_generator_skill import analyze_images_batch

# 批量分析多张图像
image_paths = [
    "references/style1.jpg",
    "references/style2.jpg",
    "references/style3.jpg"
]

lut_path = analyze_images_batch(
    image_paths=image_paths,
    output_path="luts/averaged_style.cube",
    lut_size=33
)

print(f"平均风格 LUT 已生成：{lut_path}")
```

### 示例 3: 应用 LUT

```python
from lut_generator_skill import apply_lut_to_image

# 应用 LUT 到单张图像
result = apply_lut_to_image(
    input_path="photos/original.jpg",
    lut_path="luts/my_style.cube",
    output_path="photos/styled.jpg",
    interpolation="trilinear",
    gamma=1.0
)

print(f"处理完成：{result['output_path']}")
print(f"耗时：{result['processing_time']:.2f}秒")
```

### 示例 4: 批量应用 LUT

```python
from lut_generator_skill import apply_lut_batch

# 批量应用 LUT
input_images = [
    "photos/img1.jpg",
    "photos/img2.jpg",
    "photos/img3.jpg"
]

results = apply_lut_batch(
    input_paths=input_images,
    lut_path="luts/my_style.cube",
    output_dir="output/styled/",
    num_workers=4  # 并行处理
)

print(f"处理完成：{len(results)} 张图像")
```

### 示例 5: 生成预览报告

```python
from lut_generator_skill import generate_preview_report

# 生成完整预览报告
report_path = generate_preview_report(
    reference_path="photos/reference.jpg",
    target_path="photos/target.jpg",
    input_path="photos/test.jpg",
    output_dir="reports/",
    include_slider=True,
    include_histograms=True,
    include_gamut=True
)

print(f"报告已生成：{report_path}")
```

### 示例 6: 使用优化器

```python
from lut_generator_skill import optimize_processing

# 配置优化器
optimizer_config = {
    'cache_enabled': True,
    'cache_size': 100,
    'parallel_workers': 4,
    'chunk_size_mb': 256,
    'use_processes': True
}

# 处理图像
results = optimize_processing(
    input_images=["img1.jpg", "img2.jpg", "img3.jpg"],
    lut_path="style.cube",
    config=optimizer_config
)

# 查看性能统计
stats = results['performance_stats']
print(f"缓存命中：{stats['cache_hits']}")
print(f"加速比：{stats['parallel_speedup']:.2f}x")
```

---

## API 参考

### analyze_image_for_lut

分析单张图像生成 LUT。

**参数**:
- `image_path` (str): 参考图像路径
- `output_path` (str): 输出 LUT 路径
- `lut_size` (int, optional): LUT 尺寸 (17/33/65), 默认 33
- `smoothness` (float, optional): 平滑度 (0.0-1.0), 默认 0.5
- `color_space` (str, optional): 色彩空间 ('lab'/'rgb'), 默认 'lab'

**返回**: `str` LUT 文件路径

**示例**:
```python
lut_path = analyze_image_for_lut("ref.jpg", "output.cube")
```

---

### analyze_images_batch

批量分析多张图像生成平均 LUT。

**参数**:
- `image_paths` (List[str]): 图像路径列表
- `output_path` (str): 输出 LUT 路径
- `lut_size` (int, optional): LUT 尺寸，默认 33
- `weights` (List[float], optional): 权重列表

**返回**: `str` LUT 文件路径

**示例**:
```python
lut_path = analyze_images_batch(
    ["ref1.jpg", "ref2.jpg", "ref3.jpg"],
    "averaged.cube"
)
```

---

### apply_lut_to_image

应用 LUT 到图像。

**参数**:
- `input_path` (str): 输入图像路径
- `lut_path` (str): LUT 文件路径
- `output_path` (str): 输出图像路径
- `interpolation` (str, optional): 插值方法，默认 'trilinear'
- `gamma` (float, optional): Gamma 校正，默认 1.0
- `clamp` (bool, optional): 限制输出范围，默认 True

**返回**: `dict` 处理结果

**返回数据**:
```python
{
    'success': bool,
    'output_path': str,
    'processing_time': float,
    'input_size': tuple,
    'output_size': tuple
}
```

---

### apply_lut_batch

批量应用 LUT 到多张图像。

**参数**:
- `input_paths` (List[str]): 输入图像路径列表
- `lut_path` (str): LUT 文件路径
- `output_dir` (str): 输出目录
- `num_workers` (int, optional): 并行 worker 数量
- `extensions` (List[str], optional): 处理的文件扩展名

**返回**: `List[dict]` 处理结果列表

---

### generate_preview_report

生成完整预览报告。

**参数**:
- `reference_path` (str): 参考图像路径
- `target_path` (str): 目标图像路径
- `input_path` (str): 输入图像路径
- `output_dir` (str): 输出目录
- `include_slider` (bool, optional): 包含滑块对比，默认 True
- `include_histograms` (bool, optional): 包含直方图，默认 True
- `include_gamut` (bool, optional): 包含色域图，默认 True
- `theme` (str, optional): 主题 ('dark'/'light'), 默认 'dark'

**返回**: `str` HTML 报告路径

---

### optimize_processing

使用优化器处理图像。

**参数**:
- `input_images` (List[str]): 输入图像列表
- `lut_path` (str): LUT 文件路径
- `config` (dict, optional): 优化器配置
- `output_dir` (str, optional): 输出目录

**返回**: `dict` 处理结果和性能统计

**配置选项**:
```python
config = {
    'cache_enabled': True,       # 启用缓存
    'cache_size': 100,           # 缓存大小
    'parallel_workers': 4,       # worker 数量
    'chunk_size_mb': 256,        # 分块大小 (MB)
    'use_processes': True,       # 使用多进程
    'max_memory_mb': 2048        # 最大内存 (MB)
}
```

---

## 配置选项

### 全局配置

可以在 `~/.openclaw/workspace-assistent/projects/lut-generator/config.json` 中配置全局参数：

```json
{
  "default_lut_size": 33,
  "default_smoothness": 0.5,
  "default_color_space": "lab",
  "cache": {
    "enabled": true,
    "max_size": 100,
    "ttl_seconds": 3600
  },
  "parallel": {
    "num_workers": null,
    "use_processes": true,
    "max_memory_per_worker_mb": 2048
  },
  "memory": {
    "chunk_size_mb": 256,
    "enable_chunking": true,
    "max_image_size": 10000
  }
}
```

---

## 最佳实践

### 1. 选择合适的 LUT 尺寸

- **17³**: 快速测试，文件小 (~15KB)
- **33³**: 推荐默认，平衡质量和性能 (~180KB)
- **65³**: 最高质量，文件大 (~1.5MB)，生成慢

### 2. 批量处理优化

```python
# 推荐配置
config = {
    'cache_enabled': True,      # 启用缓存
    'parallel_workers': 4,      # 4 个 worker
    'chunk_size_mb': 256,       # 256MB 分块
    'use_processes': True       # 多进程
}

results = optimize_processing(images, lut, config)
```

### 3. 内存管理

处理大图像时：

```python
# 减小分块大小
config = {
    'chunk_size_mb': 128,  # 减小到 128MB
    'enable_chunking': True,
    'max_memory_mb': 1024   # 限制最大内存
}
```

### 4. 缓存使用

```python
# 首次处理（缓存未命中）
result1 = apply_lut_to_image("img1.jpg", "lut.cube", "out1.jpg")

# 相同 LUT 再次处理（缓存命中，10-20x 加速）
result2 = apply_lut_to_image("img2.jpg", "lut.cube", "out2.jpg")
```

---

## 错误处理

### 常见错误

#### 1. 文件未找到

```python
try:
    result = analyze_image_for_lut("missing.jpg", "output.cube")
except FileNotFoundError as e:
    print(f"文件未找到：{e}")
```

#### 2. 内存不足

```python
try:
    result = apply_lut_to_image("large.jpg", "lut.cube", "out.jpg")
except MemoryError as e:
    print("内存不足，请启用分块处理")
    # 使用优化器
    result = optimize_processing(
        ["large.jpg"],
        "lut.cube",
        {'chunk_size_mb': 128}
    )
```

#### 3. 无效的 LUT 文件

```python
try:
    result = apply_lut_to_image("img.jpg", "invalid.cube", "out.jpg")
except ValueError as e:
    print(f"LUT 文件无效：{e}")
```

---

## 性能调优

### 基准测试

```python
from lut_generator_skill import benchmark

# 运行基准测试
results = benchmark(
    image_sizes=[(1920, 1080), (3840, 2160)],
    lut_sizes=[17, 33, 65],
    num_iterations=3
)

# 查看结果
for result in results:
    print(f"{result['image_size']} - {result['lut_size']}³: {result['time']:.2f}s")
```

### 性能建议

| 场景 | 推荐配置 |
|------|---------|
| 快速测试 | LUT 17³, 缓存启用，单线程 |
| 日常使用 | LUT 33³, 缓存启用，4 workers |
| 高质量输出 | LUT 65³, 缓存启用，8 workers |
| 大图像 (>4K) | LUT 33³, 分块 128MB, 缓存启用 |
| 批量处理 (>100 张) | LUT 33³, 最大 workers, 分块 256MB |

---

## 集成示例

### 与 OpenClaw 工作流集成

```python
# 在 OpenClaw 技能中使用
from lut_generator_skill import analyze_image_for_lut, apply_lut_to_image

# 1. 分析参考图像
lut_path = analyze_image_for_lut(
    image_path="reference.jpg",
    output_path="style.cube"
)

# 2. 应用到工作区图像
input_images = list_workspace_images("photos/")
for img_path in input_images:
    output_path = img_path.replace("photos/", "styled/")
    apply_lut_to_image(img_path, lut_path, output_path)

# 3. 生成报告
generate_preview_report(
    reference_path="reference.jpg",
    input_path=input_images[0],
    output_dir="reports/"
)
```

### 与 Feishu 集成

```python
# 在 Feishu Bot 中使用
from lut_generator_skill import analyze_image_for_lut

# 用户发送参考图像
image_path = download_feishu_image(message)

# 生成 LUT
lut_path = analyze_image_for_lut(
    image_path=image_path,
    output_path=f"luts/{message_id}.cube"
)

# 返回结果
send_message(f"LUT 已生成：{lut_path}")
```

---

## 故障排除

### 问题 1: 处理速度慢

**解决方案**:
1. 检查是否启用缓存
2. 增加 worker 数量
3. 减小 LUT 尺寸 (33³ → 17³)
4. 启用分块处理

### 问题 2: 色彩不匹配

**解决方案**:
1. 检查参考图像质量
2. 调整平滑度参数 (0.3-0.7)
3. 使用多图平均
4. 确保 sRGB 色彩空间

### 问题 3: 内存溢出

**解决方案**:
1. 启用分块处理
2. 减小分块大小
3. 限制最大内存
4. 分批处理大图像

---

## 更新日志

### v1.0.0 (2026-04-13)

- ✅ 性能优化模块
- ✅ 完整集成测试
- ✅ 文档完善
- ✅ OpenClaw Skill 封装

### v0.1.0 (2026-03-01)

- 初始版本
- 核心 LUT 生成功能

---

## 联系方式

**项目 ID**: 【图片分析风格生成 LUT 工具_标准版_20260413153500】  
**技能版本**: v1.0.0  
**状态**: ✅ 生产就绪

---

## 相关文档

- [主 README](../lut-generator_server/README.md)
- [API 文档](../lut-generator_server/API.md)
- [技术设计](../lut-generator_tech-design.md)
- [PRD 文档](../lut-generator_prd.md)

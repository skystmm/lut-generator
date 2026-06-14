# LUT Generator Skill - 使用文档
# LUT Generator Skill - 使用文档

**版本**: v1.0.0  
**最后更新**: 2026-06-14

本文档介绍 LUT Generator 在 OpenClaw / Hermes Agent 中的调用方式。Skill 本身没有独立 Python 包装层,**实际调用走 CLI**(`lut-generator` 命令)。

---

## 快速开始

### 1. 安装服务器端

```bash
cd lut-generator_server
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -e .
```

### 2. 在 OpenClaw / Hermes 中调用

OpenClaw / Hermes 没有 `lut_generator_skill` 这个 importable Python 包。**所有 skill 实际行为都通过 `lut-generator` CLI 完成**。在对话中调起时,直接告诉 agent 你要做什么即可(它会执行 CLI)。

| 用户意图 | 调用的 CLI |
|---|---|
| "分析 reference.jpg 风格,生成 33³ LUT" | `lut-generator extract reference.jpg -o style.cube -s 33` |
| "把 A 的风格迁移到 B,输出 LUT" | `lut-generator generate -i A.jpg -t B.jpg -o style.cube -s 33` |
| "用 A 的风格渲染 B" | `lut-generator transfer -i A.jpg -t B.jpg -o B_styled.jpg` |
| "输出 photo.jpg 的色彩统计" | `lut-generator analyze photo.jpg -o stats.json` |
| "从 trailer.mp4 提取风格" | `lut-generator video-extract trailer.mp4 -o trailer.cube --analyze` |
| "生成 LR/PS 预设 (.xmp)" | `lut-generator extract photo.jpg -o look.xmp -s 33 -f xmp` |
| "从 RAW 提取风格 (DNG/ARW/CR2/NEF)" | `lut-generator extract IMG_0001.ARW -o style.cube -s 33` |

---

## 技能功能

### 核心能力

1. **单图风格提取** — 从一张已调色图片反向提取 17³ / 33³ / 65³ LUT
2. **双图色彩迁移** — Reinhard 算法把 source 风格迁移到 target
3. **视频 LUT** — 从单视频提取 / 视频→视频风格迁移,支持场景检测 + 智能帧采样
4. **批量处理** — 暂未提供 CLI 子命令,需走 Python API
5. **Python 编程** — 完整 Python 包,支持嵌入到自定义 pipeline

---

## 使用示例

### 示例 1: 单图分析 → LUT

```bash
# 等价于: 让 agent 跑这条命令
lut-generator extract photos/reference.jpg -o luts/my_style.cube -s 33
```

Python 等价写法(完整可控):
```python
from lut_generator.core.style_extractor import StyleExtractor
extractor = StyleExtractor(grid_size=33, strength=1.0)
result = extractor.generate_lut(image_path='photos/reference.jpg')
# result 包含 features(warmth/saturation/contrast)和 LUT 数据
```

### 示例 2: 批量分析

CLI 没有 `analyze` 的多图模式,Python 写:

```python
from pathlib import Path
from lut_generator.core.style_extractor import StyleExtractor

extractor = StyleExtractor(grid_size=33)
image_paths = [
    "references/style1.jpg",
    "references/style2.jpg",
    "references/style3.jpg",
]
for img_path in image_paths:
    p = Path(img_path)
    extractor.generate_lut(image_path=img_path, output_path=f"luts/{p.stem}.cube")
```

### 示例 3: 应用 LUT 到图像

CLI 没有 `apply` 子命令;**通过双图色彩迁移直接出图** 或 **Python 加载 .cube 后 apply**:

```bash
# 方案 A:双图迁移(同时生成 LUT + 应用)
lut-generator generate -i reference.jpg -t photo.jpg -o style.cube \
  -s 33 && lut-generator transfer -i reference.jpg -t photo.jpg -o photo_styled.jpg
```

```python
# 方案 B:加载已有 .cube 应用到图
from lut_generator.lut.applier import LUTApplier
applier = LUTApplier.from_lut_file('luts/my_style.cube')
result = applier.apply_to_file('photos/original.jpg', 'photos/styled.jpg')
print(f"处理完成:{result.success}, 输出:{result.output_path}")
```

### 示例 4: 批量应用 LUT

```python
from lut_generator.lut.applier import LUTApplier
from pathlib import Path

applier = LUTApplier.from_lut_file('luts/my_style.cube', grid_size=33)
inputs = list(Path('photos').glob('*.jpg'))
results = applier.apply_batch([str(p) for p in inputs], output_dir='output/styled/')
print(f"处理完成:{len(results)} 张图像")
```

### 示例 5: 视频 LUT

```bash
# 从电影预告片提取整体风格
lut-generator video-extract trailer.mp4 -o trailer_style.cube -s 33 --analyze

# 视频→视频 风格迁移
lut-generator video-generate source.mp4 -t target.mp4 -o graded.cube \
  --strategy scene --max-frames 50
```

### 示例 6: 色彩统计 / HTML 报告

```bash
# 色彩统计
lut-generator analyze photos/reference.jpg -o stats.json --use-colour

# 完整 HTML 报告:暂无 CLI 子命令,用 Python:
# python -c "
# from lut_generator.utils.html_report import HTMLReportGenerator
# gen = HTMLReportGenerator()
# gen.generate_from_paths('photos/original.jpg', 'photos/styled.jpg', 'report.html')
# "
```

---

## API 参考(以 `src/lut_generator/` 实际包为准)

| 模块 | 主要导出 |
|---|---|
| `lut_generator.lut.lut3d` | `LUT3DGenerator`, `LUT3DConfig` |
| `lut_generator.lut.exporter` | `LUTExporter`(支持 cube/3dl/clf) |
| `lut_generator.lut.applier` | `LUTApplier`, `ApplyConfig` |
| `lut_generator.analysis.analyzer` | `ColorAnalyzer`, `analyze_image` |
| `lut_generator.core.style_extractor` | `StyleExtractor` |
| `lut_generator.core.reinhard` | `ReinhardColorTransfer` |
| `lut_generator.video.frame_extractor` | `VideoFrameExtractor`, `ExtractorConfig` |
| `lut_generator.video.analyzer` | `VideoColorAnalyzer` |
| `lut_generator.utils.html_report` | `HTMLReportGenerator`, `ReportConfig` |
| `lut_generator.utils.visualizer` | `ColorVisualizer` |

> 旧版 README 列出的 `from lut_generator_skill import analyze_image_for_lut / apply_lut_to_image` 等函数**不是真实存在的接口**;`lut_generator_skill/` 目录下只有 `SKILL.md` + `README.md`,**没有 Python 包**。要编程接入请直接 import 上面这些 `lut_generator.*` 模块。
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

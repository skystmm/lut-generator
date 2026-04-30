# 🎨 LUT Generator

**从图片分析自动生成 3D LUT (.cube) 的专业工具**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-205%20passed-green.svg)]()
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 📖 简介

LUT Generator 是一款专业的色彩工具，能够从参考图片自动分析色彩风格，并生成标准的 3D LUT (.cube 格式)。使用 Reinhard 色彩迁移算法，实现精确的色彩风格匹配。

**核心能力**：
- 📸 **图片分析** - 从单张或多张参考图片提取色彩特征
- 🎯 **色彩迁移** - 基于 Reinhard 算法实现专业级色彩匹配
- 📦 **LUT 生成** - 输出 17³/33³/65³ 精度的标准 .cube 文件
- 👁️ **效果预览** - 生成前后对比图、直方图、色域图和 HTML 报告
- ⚡ **高性能** - 缓存加速 2-20x，并行处理 3-6x

**兼容软件**：DaVinci Resolve、Premiere Pro、Final Cut Pro、Photoshop、OBS 等所有支持 .cube 格式的专业软件。

---

## ✨ 功能特性

### 核心功能

| 功能 | 说明 |
|------|------|
| 🖼️ 单图风格提取 | 从单张调色后图片提取风格特征，生成模拟该风格的 LUT |
| 🎨 暖冷色调检测 | 自动识别图像的暖/冷色调倾向 |
| 🌓 亮度/对比度分析 | 检测图像的高调/低调特征和对比度 |
| 📚 批量分析 | 扫描整个目录，分析多张图片 |
| 🎨 多图融合 | 加权平均/中值融合多张图片的风格 |
| 🎯 精度可选 | 17³ / 33³ / 65³ 三种精度 |
| 📦 标准格式 | 输出 .cube 格式，兼容所有主流软件 |
| 🎚️ 强度调节 | 0.0-1.0 可调的迁移强度 |
| 👁️ 效果预览 | 并排/滑块/混合/差异 4 种对比模式 |
| 📊 可视化 | RGB 直方图、Lab 色域图 |
| 📄 HTML 报告 | 交互式报告，含滑块对比和统计信息 |

### 性能优化

- ✅ **LUT 缓存** - 避免重复加载，加速 2-20x
- ✅ **并行处理** - 多核 CPU 利用，加速 3-6x
- ✅ **内存优化** - 分块处理，支持 8K+ 图像
- ✅ **向量化计算** - numpy 优化，比循环快 10-100x

---

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/skystmm/lut-generator.git
cd lut-generator/lut-generator_server

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -e .
```

### 基础使用

#### 1️⃣ 从图片生成 LUT

```bash
# 单张图片
lut-generator analyze \
  --input reference.jpg \
  --output style.cube \
  --size 33

# 多张图片（批量）
lut-generator analyze \
  --input ./references/ \
  --output style.cube \
  --size 33 \
  --batch

# 带权重融合
lut-generator analyze \
  --input ./references/ \
  --output style.cube \
  --weights "3,2,1" \
  --preview
```

#### 2️⃣ 单图风格提取（新功能 🎉）

从一张调色后的图片提取风格特征，生成可复用的 LUT：

```bash
# 基础用法
lut-generator extract \
  --input graded_photo.jpg \
  --output extracted_style.cube

# 带强度调节
lut-generator extract \
  --input graded_photo.jpg \
  --output extracted_style.cube \
  --strength 0.7 \
  --size 33

# 生成分析报告
lut-generator extract \
  --input graded_photo.jpg \
  --output extracted_style.cube \
  --report analysis.json
```

**提取的风格特征**：
- 🎨 色调偏移（暖色/冷色倾向）
- 🌓 亮度特征（高调/低调）
- 📊 对比度比例
- 💫 饱和度变化

#### 3️⃣ 应用 LUT 到图片

```bash
# 单张
lut-generator apply \
  --input photo.jpg \
  --lut style.cube \
  --output photo_styled.jpg

# 批量
lut-generator apply \
  --input ./photos/ \
  --lut style.cube \
  --output ./styled/ \
  --batch \
  --parallel
```

#### 3️⃣ 生成完整报告

```bash
lut-generator report \
  --reference style_reference.jpg \
  --input original.jpg \
  --output ./report/
```

**输出**：
- `report.html` - 交互式 HTML 报告（滑块对比）
- `histogram.png` - RGB 直方图对比
- `gamut.png` - Lab 色域图对比
- `statistics.json` - 色彩统计数据

---

## 📖 Python API

### 基础用法

```python
from lut3d_generator import LUT3DGenerator, LUT3DConfig
from lut_applier import LUTApplier
from preview_generator import PreviewGenerator
from html_report import HTMLReportGenerator

# 1. 配置 LUT 生成器
config = LUT3DConfig(
    grid_size=33,        # 33³ 精度
    smoothness=0.5,      # 平滑度
    strength=0.8         # 迁移强度
)

# 2. 从参考图片生成 LUT
generator = LUT3DGenerator(config)
result = generator.generate_from_images(
    reference_path='./references/cyberpunk.jpg',
    target_colorspace='sRGB'
)

# 3. 导出 LUT
generator.export_to_cube('cyberpunk_lut.cube')

# 4. 应用 LUT
applier = LUTApplier(generator)
applier.apply_to_file('photo.jpg', 'photo_styled.jpg')

# 5. 生成预览对比
preview = PreviewGenerator()
preview.generate_comparison(
    original='photo.jpg',
    styled='photo_styled.jpg',
    output='comparison.png',
    mode='slider'  # 滑块对比
)

# 6. 生成 HTML 报告
report = HTMLReportGenerator()
report.generate_from_paths(
    reference='cyberpunk.jpg',
    input='photo.jpg',
    output='photo_styled.jpg',
    output_html='report.html'
)
```

### 单图风格提取 API

```python
from lut_generator.core.style_extractor import StyleExtractor
import numpy as np

# 1. 创建风格提取器
extractor = StyleExtractor(
    grid_size=33,     # LUT 精度：17, 33, 或 65
    strength=0.8      # 风格强度：0.0-1.0
)

# 2. 从文件提取风格
result = extractor.generate_lut(
    image_path='./graded_photo.jpg',
    strength=0.7       # 可选：覆盖默认强度
)

# 3. 访问提取的风格特征
features = result.features
print(f"色调偏移 L: {features.tone_shift_L:.2f}")  # 亮度
print(f"色调偏移 b: {features.tone_shift_b:.2f}")  # 暖冷
print(f"Warmth: {features.warmth:.3f}")            # -1(冷) 到 1(暖)
print(f"Saturation: {features.saturation:.3f}")
print(f"Contrast: {features.contrast:.3f}")

# 4. 从 numpy 数组提取（适用于批处理）
import cv2
rgb = cv2.imread('photo.jpg')[:, :, ::-1]  # BGR -> RGB
features = extractor.extract_features_from_array(rgb)
lut = extractor.generate_lut_from_features(features, strength=0.8)

# 5. 导出 LUT
from lut_generator.io.cube_writer import CubeWriter
writer = CubeWriter()
writer.write(result.style_lut_data, 'extracted_style.cube', title='My Style')

# 6. 导出分析报告
import json
with open('analysis.json', 'w') as f:
    json.dump({
        'tone_shift': {
            'L': features.tone_shift_L,
            'a': features.tone_shift_a,
            'b': features.tone_shift_b
        },
        'style_metrics': {
            'warmth': features.warmth,
            'saturation': features.saturation,
            'contrast': features.contrast
        }
    }, f, indent=2)
```

---

## 🎯 使用场景

### 场景 1：电影风格调色

```bash
# 从电影截图生成 LUT
lut-generator analyze \
  --input movie_frame.jpg \
  --output cinematic_lut.cube \
  --size 65 \
  --preview

# 应用到你的视频素材
lut-generator apply \
  --input ./footage/ \
  --lut cinematic_lut.cube \
  --output ./graded/ \
  --batch
```

### 场景 2：品牌色彩统一

```bash
# 从品牌视觉素材生成统一风格
lut-generator analyze \
  --input ./brand_assets/ \
  --output brand_lut.cube \
  --weights "5,3,2" \
  --preview

# 批量应用到所有内容
lut-generator apply \
  --input ./content/ \
  --lut brand_lut.cube \
  --output ./branded/ \
  --parallel
```

### 场景 3：摄影师个人风格

```bash
# 从代表作品生成个人风格 LUT
lut-generator analyze \
  --input ./portfolio/best_works/ \
  --output my_style_lut.cube \
  --size 33 \
  --strength 0.7

# 快速应用到新作品
lut-generator apply \
  --input new_photo.jpg \
  --lut my_style_lut.cube \
  --output new_photo_styled.jpg
```

---

## 📊 性能基准

| 操作 | 图像尺寸 | 耗时 |
|------|---------|------|
| LUT 生成 | 1920×1080 | 5-8 秒 |
| LUT 应用 | 1920×1080 | 2-3 秒 |
| LUT 应用（缓存） | 1920×1080 | 0.3-0.5 秒 |
| 批量处理（4 核） | 100 张 | 45-60 秒 |
| HTML 报告生成 | - | 1-2 秒 |

**测试环境**: Linux x64, Python 3.11, 16GB RAM

---

## 🏗️ 项目结构

```
lut-generator/
├── lut-generator_server/      # Python 后端
│   ├── src/
│   │   ├── color_analyzer.py      # 色彩分析
│   │   ├── color_transfer.py      # Reinhard 色彩迁移
│   │   ├── lut3d_generator.py     # 3D LUT 生成
│   │   ├── cube_exporter_main.py  # .cube 导出
│   │   ├── batch_analyzer.py      # 批量分析
│   │   ├── feature_fusion.py      # 特征融合
│   │   ├── lut_applier.py         # LUT 应用
│   │   ├── preview_generator.py   # 预览图生成
│   │   ├── visualizer.py          # 可视化
│   │   ├── html_report.py         # HTML 报告
│   │   ├── optimizer.py           # 性能优化
│   │   └── cli.py                 # 命令行工具
│   ├── tests/                     # 单元测试 (205+ 用例)
│   ├── README.md                  # 详细文档
│   ├── API.md                     # API 参考
│   └── pyproject.toml             # 项目配置
├── lut-generator_skill/           # OpenClaw Skill
│   ├── SKILL.md
│   └── README.md
├── README.md                      # 本文件
├── lut-generator_prd.md           # PRD 文档
└── lut-generator_tech-design.md   # 技术设计
```

---

## 🧪 测试

```bash
cd lut-generator_server

# 运行所有测试
./tests/run_tests.sh

# 或使用 pytest
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=src --cov-report=html
```

**测试覆盖**: 205+ 测试用例，94.8% 通过率

---

## 🛠️ 技术栈

- **Python 3.11+**
- **colour-science** - 专业色彩科学计算
- **opencv-python** - 图像处理
- **numpy** - 数值计算
- **scipy** - 插值算法
- **matplotlib** - 可视化
- **Pillow** - 图像 I/O

---

## 📚 文档

- [完整使用文档](lut-generator_server/README.md)
- [API 参考](lut-generator_server/API.md)
- [PRD 文档](lut-generator_prd.md)
- [技术设计](lut-generator_tech-design.md)
- [最终交付报告](FINAL_DELIVERY_REPORT.md)

---

## 🎓 学习资源

### LUT 基础
- [什么是 LUT？](https://en.wikipedia.org/wiki/Look-up_table)
- [3D LUT 技术原理](https://www.blackmagicdesign.com/products/davinciresolve/learning)
- [.cube 格式规范](https://www.adobe.com/devnippets/pdfs/CS6Extensions/1.0/3DLUTFileSpecification.pdf)

### 色彩科学
- [colour-science 文档](https://www.colour-science.org/)
- [Reinhard 色彩迁移论文](https://www.cs.colostate.edu/~cs510/yr2016/papers/paper015.pdf)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## 👨‍💻 作者

**Sky** - [@skystmm](https://github.com/skystmm)

---

## 🙏 致谢

- [colour-science](https://github.com/colour-science/colour) - 色彩科学库
- [OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO) - 色彩管理框架
- Reinhard et al. - 色彩迁移算法论文

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！**

[报告问题](https://github.com/skystmm/lut-generator/issues) · [请求功能](https://github.com/skystmm/lut-generator/issues)

</div>

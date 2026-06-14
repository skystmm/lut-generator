# 🎨 LUT Generator

**从图片和视频自动生成 3D LUT (.cube) 的专业调色工具**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![CI](https://github.com/skystmm/lut-generator/actions/workflows/ci.yml/badge.svg)
[![Code Style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## 📖 简介

LUT Generator 是一款专业的色彩工具，能够从参考图片或视频自动分析色彩风格，生成标准 3D LUT (.cube 格式)。基于 Reinhard 色彩迁移算法，实现精确的色彩风格匹配与反向提取。

**核心能力**：
- 📸 **图片风格提取** — 从单张或多张参考图片提取色彩特征
- 🎬 **视频 LUT 生成** — 支持从视频中提取风格，含场景检测与智能帧采样
- 🎯 **色彩迁移** — 基于 Reinhard 算法实现专业级色彩匹配
- 🔄 **风格反向解析** — 从已调色的图片/视频中还原 LUT
- 📦 **标准格式** — 输出 17³/33³/65³ 精度的 .cube 文件
- 👁️ **效果预览** — 前后对比图、直方图、色域图和交互式 HTML 报告
- ⚡ **高性能** — LUT 缓存加速 2-20x，并行处理 3-6x

**兼容软件**：DaVinci Resolve、Premiere Pro、Final Cut Pro、Photoshop、OBS 等所有支持 .cube 格式的专业软件。

---

## ✨ 功能特性

### 图片 LUT

| 功能 | 说明 |
|------|------|
| 🖼️ 单图风格提取 | 从单张调色后图片提取风格特征，生成模拟该风格的 LUT |
| 🎨 暖冷色调检测 | 自动识别图像的暖/冷色调倾向 |
| 🌓 亮度/对比度分析 | 检测图像的高调/低调特征和对比度 |
| 📚 批量分析 | 扫描整个目录，分析多张图片 |
| 🎨 多图融合 | 加权平均/中值融合多张图片的风格 |
| 🎚️ 强度调节 | 0.0-1.0 可调的迁移强度 |

### 视频 LUT 🎬

| 功能 | 说明 |
|------|------|
| 🎬 视频风格生成 | 从视频提取色彩风格，生成 3D LUT |
| 🎞️ 视频到视频风格迁移 | 将 A 视频的风格应用到 B 视频 |
| 📸 视频到图片风格迁移 | 从视频提取风格，应用到图片 |
| 🔍 场景检测 | 基于直方图的自动场景分割 |
| 📊 智能帧采样 | 均匀/场景/自适应三种采样策略 |

### 性能优化

- ✅ **LUT 缓存** — 避免重复加载，加速 2-20x
- ✅ **并行处理** — 多核 CPU 利用，加速 3-6x
- ✅ **内存优化** — 分块处理，支持 8K+ 图像
- ✅ **向量化计算** — numpy 优化，比循环快 10-100x

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

> **所有命令以 `lut-generator` 子命令形式调用。**可用子命令:`analyze` / `generate` / `transfer` / `extract` / `video-generate` / `video-extract`。
> 跑 `lut-generator --help` 看完整签名。

#### 1️⃣ 从图片生成 LUT(单图反向提取)

```bash
# 真实命令:extract 接位置参数 <image> + 必填 -o
lut-generator extract graded_photo.jpg -o style.cube -s 33

# 调强度 + 输出风格分析
lut-generator extract graded_photo.jpg -o style.cube -s 33 --strength 0.7 --analyze
```

> 旧版 README 写的 `lut-generator extract --input ...` **不存在**;`extract` 的图是位置参数,不是 `--input`。

#### 📌 导出为 Adobe Lightroom / Photoshop 预设(XMP)

```bash
# 加 -f xmp 即可输出 Adobe .xmp 预设,LR / LR Classic / ACR / PS 都能直接加载
lut-generator extract graded_photo.jpg -o my_look.xmp -s 33 -f xmp
lut-generator generate -i ref.jpg -t photo.jpg -o my_look.xmp -s 33 -f xmp --title "My Look"
```

#### 2️⃣ 色彩迁移生成 LUT(双图)

```bash
# 真实命令:generate 必填 -i -t -o
lut-generator generate -i reference.jpg -t photo.jpg -o style.cube -s 33

# 自带强度调节
lut-generator generate -i reference.jpg -t photo.jpg -o style.cube -s 33 --strength 0.8
```

> `--batch` 标志已移除,多图批量请用 Python API(见下)。

#### 3️⃣ 应用 LUT 到图片(色彩迁移直接出图,不出 LUT)

```bash
# transfer 子命令:把 source 的色彩风格直接迁移到 target
lut-generator transfer -i reference.jpg -t photo.jpg -o photo_styled.jpg --strength 0.8
```

> 旧版 README 写的 `lut-generator apply --input ... --lut ...` **不存在**。要应用"已生成的 .cube"到新图,用 Python 调 `LUTApplier` 加载 .cube 后 apply。

#### 4️⃣ 从视频生成 LUT 🎬

```bash
# 单视频反向提取风格
lut-generator video-extract source_video.mp4 -o video_style.cube -s 33 --analyze

# 视频→视频 风格迁移
lut-generator video-generate style_source.mp4 -t target_video.mp4 -o graded_video.cube

# 场景模式(自动检测场景分段)
lut-generator video-generate movie.mp4 -o cinematic.cube --strategy scene

# 自适应采样
lut-generator video-generate vlog.mp4 -o vlog_style.cube --strategy adaptive --max-frames 50
```

> 视频采样参数:
> - `--strategy` 取值 `uniform` / `scene` / `adaptive`(旧版 README 写成 `--sampling`,已改名为 `--strategy`)
> - `--sample-rate` 每秒采样帧数(默认 1.0)
> - `--max-frames` 最大采样帧数(默认 100)
> - `--scene-threshold` 场景检测阈值(默认 0.3)

#### 5️⃣ 色彩分析

```bash
# 单图统计(只输出 JSON 统计,不出 LUT)
lut-generator analyze photo.jpg -o stats.json

# 强制走 colour-science(更准,需要 scipy)
lut-generator analyze photo.jpg --use-colour -o stats.json
```

---

## 📖 Python API

### 基础用法

```python
# 真实存在的模块路径(以 src/lut_generator/ 为准)
from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig
from lut_generator.lut.exporter import LUTExporter

# 配置 LUT 生成器
config = LUT3DConfig(
    grid_size=33,        # 33³ 精度
    smoothness=0.5,      # 平滑度
)

# 双图色彩迁移
generator = LUT3DGenerator(config)
lut_data = generator.generate_from_images(
    'reference.jpg', 'target.jpg', strength=0.8
)
# 注意:方法名是 generate_from_images(...),不是 generate(...)

# 导出 .cube / .3dl / .clf
LUTExporter(lut_data, {'title': 'My Style', 'description': 'demo'}) \
    .export('output.cube', format='cube')
```

### 视频 LUT API 🎬

```python
from lut_generator.video.frame_extractor import VideoFrameExtractor, ExtractorConfig
from lut_generator.video.analyzer import VideoColorAnalyzer

# 1. 提取视频帧
extractor = VideoFrameExtractor(
    config=ExtractorConfig(
        sampling='scene',     # 场景分割采样
        max_frames=30
    )
)
frames = extractor.extract('source_video.mp4')

# 2. 分析视频色彩
analyzer = VideoColorAnalyzer()
video_stats = analyzer.analyze_frames(frames)

# 3. 生成视频 LUT
lut = analyzer.generate_lut(video_stats, grid_size=33)
```

### 风格提取 API

```python
from lut_generator.core.style_extractor import StyleExtractor

extractor = StyleExtractor(grid_size=33, strength=0.8)
result = extractor.generate_lut(image_path='./graded_photo.jpg')

# 访问提取的风格特征
features = result.features
print(f"Warmth: {features.warmth:.3f}")        # -1(冷) 到 1(暖)
print(f"Saturation: {features.saturation:.3f}")
print(f"Contrast: {features.contrast:.3f}")
```

---

## 🎯 使用场景

### 场景 1：电影风格调色

```bash
# 从电影截图反向提取 LUT
lut-generator extract movie_frame.jpg -o cinematic_lut.cube -s 65

# 强度衰减
lut-generator extract movie_frame.jpg -o cinematic_lut.cube -s 65 --strength 0.7

# 直接生成调色后的图
lut-generator transfer -i movie_frame.jpg -t footage/ -o graded/ 2>/dev/null \
  || true   # transfer 不支持目录,用 Python 循环
```

### 场景 2：从视频提取调色风格 🎬

```bash
# 从电影预告片提取整体风格
lut-generator video-extract trailer.mp4 -o trailer_style.cube --strategy scene

# 把电影风格应用到你的 Vlog
lut-generator video-generate movie_trailer.mp4 -t my_vlog.mp4 -o my_vlog_graded.cube
```

### 场景 3：品牌色彩统一

```bash
# 单图风格提取
lut-generator extract brand_photo.jpg -o brand_lut.cube -s 33 --analyze

# 批量用 Python 跑
# python -c "
# from pathlib import Path
# from lut_generator.core.style_extractor import StyleExtractor
# extractor = StyleExtractor(grid_size=33)
# for img in Path('brand_assets').glob('*.jpg'):
#     extractor.generate_lut(image_path=str(img), output_path=f'luts/{img.stem}.cube')
# "
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

## 🖥️ 视频处理配置要求

> 视频 LUT 逆向功能已针对内存进行优化，**普通笔记本（8GB RAM / 4 核 CPU）即可流畅运行**。

### 推荐配置

| 项目 | 最低配置 | 推荐配置 |
|------|---------|----------|
| CPU | 4 核 | 8 核+ |
| 内存 | 4GB | 8GB+ |
| 存储 | 100MB 可用空间 | 500MB+ |
| 处理能力 | 1080p 短视频 (<3 min) | 4K 长视频、场景检测模式 |

### 内存消耗与优化

主要瓶颈在于视频帧加载到内存。单帧 RGB 内存消耗如下：

| 分辨率 | 单帧内存 | max_frames=100 总消耗 |
|--------|---------|----------------------|
| 1080p | ~6MB | ~600MB |
| 4K | ~25MB | ~2.5GB |

**内置优化机制**：
- 📉 **帧数限制** — `max_frames=100` 默认上限，防止 OOM
- 🔍 **降维场景检测** — 场景识别使用 1/4 分辨率直方图计算
- ⚡ **自适应策略** — 超过 30 秒自动启用场景检测，避免逐帧处理

### 长视频/低配机器调优

如果机器配置较低或视频较长，可通过参数优化：

```bash
# 限制采样帧数（降低内存）
lut-generator video-generate long_video.mp4 --max-frames 30

# 使用均匀采样（跳过场景检测，更快更省内存）
lut-generator video-generate long_video.mp4 \
  --sampling uniform \
  --max-frames 30

# 降低场景检测阈值（更灵敏，适合剪辑频繁的视频）
lut-generator video-generate video.mp4 \
  --sampling scene \
  --scene-threshold 0.2
```

---

## 🏗️ 项目结构

```
lut-generator/
├── lut-generator_server/          # Python 后端
│   ├── src/
│   │   ├── lut_generator/         # 核心包（统一架构）
│   │   │   ├── core/              # 核心算法
│   │   │   │   ├── reinhard.py    # Reinhard 色彩迁移
│   │   │   │   ├── style_extractor.py  # 风格提取
│   │   │   │   ├── color_space.py # 色彩空间转换
│   │   │   │   └── interpolation.py   # 插值算法
│   │   │   ├── analysis/          # 色彩分析
│   │   │   │   ├── analyzer.py    # 图像分析
│   │   │   │   ├── batch_analyzer.py  # 批量分析
│   │   │   │   └── feature_fusion.py  # 特征融合
│   │   │   ├── lut/               # LUT 操作
│   │   │   │   ├── lut3d.py       # 3D LUT 生成
│   │   │   │   ├── applier.py     # LUT 应用
│   │   │   │   └── exporter.py    # .cube 导出
│   │   │   ├── video/             # 视频处理 🎬
│   │   │   │   ├── frame_extractor.py # 帧提取
│   │   │   │   └── analyzer.py    # 视频色彩分析
│   │   │   ├── preview/           # 预览生成
│   │   │   │   └── generator.py   # 对比图生成
│   │   │   ├── utils/             # 工具模块
│   │   │   │   ├── html_report.py # HTML 报告
│   │   │   │   ├── optimizer.py   # 性能优化
│   │   │   │   └── visualizer.py  # 可视化
│   │   │   └── cli/               # 命令行入口
│   │   │       └── main.py        # CLI 实现
│   │   └── *.py                   # 向后兼容 shim（已弃用）
│   ├── tests/                     # 单元测试
│   ├── .github/workflows/ci.yml   # CI/CD 流水线
│   └── pyproject.toml             # 项目配置
├── README.md                      # 本文件
├── lut-generator_prd.md           # PRD 文档
└── lut-generator_tech-design.md   # 技术设计
```

> **注意**：`src/` 根目录下的 `color_analyzer.py`、`cli.py` 等文件为向后兼容的 shim 包装器，已标记为 `DeprecationWarning`。新代码请直接引用 `lut_generator/` 包。

---

## 🧪 测试

```bash
cd lut-generator_server

# 运行所有测试
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=lut_generator --cov-report=html
```

---

## 🛠️ 技术栈

- **Python 3.10+**
- **colour-science** — 专业色彩科学计算
- **opencv-python** — 图像处理与视频帧提取
- **numpy** — 数值计算
- **scipy** — 插值算法
- **matplotlib** — 可视化
- **Pillow** — 图像 I/O

---

## 🔧 CI/CD

项目使用 GitHub Actions 进行持续集成：

- 自动运行测试（Python 3.10 / 3.11 / 3.12）
- 代码风格检查（ruff）
- 详见 [.github/workflows/ci.yml](lut-generator_server/.github/workflows/ci.yml)

---

## 📚 文档

- [完整使用文档](lut-generator_server/README.md)
- [API 参考](lut-generator_server/API.md)
- [PRD 文档](lut-generator_prd.md)
- [技术设计](lut-generator_tech-design.md)

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

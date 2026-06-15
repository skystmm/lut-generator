# LUT Generator - 专业 3D LUT 生成工具

**版本**: v0.3.0  
**项目 ID**: 【图片分析风格生成 LUT 工具_标准版_20260413153500】  
**状态**: ✅ 生产就绪  
**最后更新**: 2026-06-16

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

> **可用的 CLI 子命令**(以代码为准):`analyze` / `generate` / `transfer` / `extract` / **`extract-hald`** / `video-generate` / `video-extract`
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

> ⚠️ `extract` 内部用 `StyleExtractor`(中性基线统计假设),算法本质是 **1D 对角线变换** — 3D 信息被压缩,加载到 LrC/PS/Resolve 时**应用后照片无色彩变化**。要保留 3D 维度请用下面的 `extract-hald`。

#### 1.5 HALD-based 单图像素映射 → 真实 3D LUT(`extract-hald`,推荐)

`extract-hald` 用真正的像素映射算法生成 3D LUT,直接解决 "LrC 应用 LUT 后无色彩变化" 的根因。3 种算法可选,默认 `gaussian_rbf`(推荐,质量+速度平衡):

```bash
# 推荐:从已调色参考图生成 33³ 3D LUT(gaussian_rbf 算法)
lut-generator extract-hald reference.jpg -o style_lut.cube -s 33

# 17³(快,LrC 14 官方推荐尺寸,4913 entries ≈ 60 KB)
lut-generator extract-hald graded.jpg -o style.cube -s 17 --n-samples 5000

# 33³ 完整精度(~250 KB,LrC 14 也接受;Resolve/Premiere 推荐)
lut-generator extract-hald graded.jpg -o style.cube -s 33 --n-samples 10000

# 高精度 65³(8 MB,LrC 14 / DaVinci Resolve 兼容)
lut-generator extract-hald graded.jpg -o style.cube -s 65 --n-samples 20000

# 算法切换:3 种
lut-generator extract-hald graded.jpg -o style.cube -s 17 -m nearest
lut-generator extract-hald graded.jpg -o style.cube -s 17 -m gaussian_rbf   # 默认
lut-generator extract-hald graded.jpg -o style.cube -s 17 -m shepard_idw

# 关闭 3D box 平滑(更锐利但可能有噪点)
lut-generator extract-hald graded.jpg -o style.cube -s 33 --smoothing 0

# 多参考图加权(覆盖更多色域,适合复杂场景)
lut-generator extract-hald ref1.jpg,ref2.jpg,ref3.jpg \
  -o style.cube -s 33 --weights 1.0,1.5,1.0

# RAW 输入(走 rawpy demosaic,跟 extract 一致的 --raw-mode 档位)
lut-generator extract-hald photo.cr3 -o style.cube -s 33 --raw-mode half --raw-wb
```

| 算法 | 速度(17³,5k 采样) | 质量 | 适用场景 |
|---|---|---|---|
| `gaussian_rbf` ⭐ | ~1s | 平滑、跨 bin 一致 | **默认推荐**;通用 |
| `nearest` | ~0.5s | 边缘锐利、有锯齿 | 调试、需保留原图每个像素 |
| `shepard_idw` | ~1s | 经典,远端色 extrapolation 略差 | 兼容性 / 老派算法 |

**与 `extract` 的核心差异**:

| 维度 | `extract` (StyleExtractor) | `extract-hald` (HALDPixelExtractor) |
|---|---|---|
| 维度 | 1D 对角线压缩 | **3D 真实映射** |
| 算法 | 统计基线假设(mean_L=50, std=25) | 高斯 RBF / 最近邻 / IDW |
| 输出 | 1D 沿对角线的 LUT | 真正的 `(R,G,B) → (R',G',B')` LUT |
| LrC 应用 | 几乎无色彩变化 | **完整 3D 色彩偏移** |
| 适用 | 快速风格描述、统计 | **LrC / Resolve / Premiere 实际应用** |

> 💡 **怎么选?** 先试 `extract-hald reference.jpg -o style.cube -s 33` —— 这是 LrC 14/Resolve/Premiere 实际能用的"标准 3D LUT"工作流。需要保留 `extract` 的语义(快速风格描述)就用 `extract`。

#### 2. 双图色彩迁移 → LUT(`generate`,Reinhard 风格匹配)

```bash
# LUT 生成 -o style.cube -s 33 [-f cube|3dl|clf|xmp]
lut-generator generate -i source.jpg -t target.jpg -o style.cube -s 33

# 指定标题/描述/格式
lut-generator generate -i source.jpg -t target.jpg -o style.cube \
  -s 65 --strength 0.8 --title "Cinematic Teal" --description "v1"

# 导出为 Adobe Lightroom / Photoshop 兼容的 XMP 预设
# (把 3D LUT 沿对角线降维成 crs:ColorTable,LR/ACR/PS 都能直接加载;
#  但 1D 压缩会丢 3D 维度信息,应用到照片几乎无色彩变化 — 实验性)
lut-generator extract graded.jpg -o my_look.xmp -s 33 -f xmp
lut-generator generate -i source.jpg -t target.jpg -o my_look.xmp -s 33 -f xmp \
  --title "My LR Preset" --strength 0.8

# 导出为 Adobe Lightroom Classic **Creative Profile** .xmp (LrC 14 官方 3D LUT 路线,推荐)
# 完整 3D LUT 通过 crs:RGBTable 字段内嵌 (zlib + Ascii85 编码),不丢维度
lut-generator extract graded.jpg -o my_look.xmp -s 33 -f xmpcreative \
  --title "My Creative Look"
lut-generator generate -i source.jpg -t target.jpg -o my_look.xmp -s 33 -f xmpcreative \
  --title "Cinematic Teal" --strength 0.8

# 导出为 .lrtemplate 旧 preset 格式 (LrC 7.3 之前路线,LrC 14 已弃用)
# 仅兼容老 LrC 用户。LrC 14 加载 .lrtemplate 会自动转 .xmp 并可能忽略 LUT 字段
lut-generator extract graded.jpg -o my_look.lrtemplate -s 33 -f lrtemplate
```

> **xmpcreative vs xmp vs lrtemplate 选哪个?**
> - **`xmpcreative`** (LrC 14 推荐): 走 Creative Profile 路径,完整 3D LUT 通过 `crs:RGBTable` 内嵌;需要安装到 `CameraRaw/Settings/` 目录,LrC Profile Browser 加载。**唯一保留 3D 维度信息的 LrC 路线**。
> - **`xmp`** (通用, 1D 压缩): 走通用 XMP preset 路径,`crs:ColorTable` 沿对角线 1D 压缩;**3D 维度信息丢光,实验性**。
> - **`.lrtemplate`** (LrC 7.3 前,已弃用): 走 LrC 旧 JSON preset,无 LUT3D 字段;LrC 14 自动隐藏并转换。

#### 2.1 LrC Creative Profile (xmpcreative) 安装

`xmpcreative` 生成的 .xmp 不是普通的 LrC Preset,而是 **Adobe Camera Raw Creative Profile**,需要放到特定目录 LrC/ACR 才能发现:

| 平台 | 安装路径 |
|---|---|
| **Windows** | `C:\ProgramData\Adobe\CameraRaw\Settings\`(需管理员) |
| **Mac** | `/Library/Application Support/Adobe/CameraRaw/Settings/` |

或 LrC → `Edit` → `Preferences` → `Presets` → `Show All Other Lightroom Presets` 打开此目录。

装好后**重启 LrC 14**,Develop 模块 → Profile Browser → 找到"lut-generator"分组 → 选择 Profile 应用,照片上能看见完整 3D 色彩变化。

> ⚠️ `[EXPERIMENTAL]` Adobe 的 RGBTable 私有编码细节(asymmetric85 + 压缩算法)未公开;本实现走标准 Ascii85 + zlib 路线。LrC 14 的 XMP parser 通常宽容接受,但若加载不成功可能是编码细节差异,反馈后可调。

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

# 6) 导出为 Adobe Lightroom Classic Creative Profile .xmp (LrC 14 官方 3D LUT 路线,推荐)
# (LUTExporter 把 3D LUT 通过 zlib 压缩 + Ascii85 编码内嵌到 crs:Table_<md5> 字段)
LUTExporter(lut_data, metadata).export_xmp_creative_profile(
    'my_look.xmp',
    title='My Creative Look',    # 在 LrC Profile Browser 中显示
    group='MyBrand:Looks',       # 分组
    apply_amount=1.0,            # 0-1,默认强度
    process_version='15.4',      # LrC 14
)
# 通用 dispatch 也支持:
LUTExporter(lut_data, metadata).export('my_look.xmp', format='xmpcreative')

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

#### HALD-based 3D LUT 提取(Python API)

`extract-hald` CLI 对应的 Python API,直接用于代码集成:

```python
from lut_generator.core.hald_extractor import (
    HALDPixelExtractor,
    HALDExtractionConfig,
    HALDExtractionResult,
    extract_hald,
)

# 1. 简洁方式:从参考图提取并直接写 .cube
result: HALDExtractionResult = extract_hald(
    "reference.jpg",
    "style_lut.cube",
    cube_size=33,
    method="gaussian_rbf",   # 或 "nearest" / "shepard_idw"
    smoothing_passes=1,
    title="Cinematic Teal",
)
print(f"LUT shape: {result.lut_data.shape}")  # (33, 33, 33, 3)
print(f"Time: {result.extraction_time_sec:.2f}s")

# 2. 精细控制:用 HALDPixelExtractor 直接拿 lut_data (numpy 数组,不写文件)
extractor = HALDPixelExtractor(
    HALDExtractionConfig(
        cube_size=33,
        method="gaussian_rbf",
        rbf_sigma=0.05,
        smoothing_passes=1,
        n_samples=10000,
        seed=42,
    )
)
result = extractor.extract("graded.jpg")
lut_data = result.lut_data  # (33, 33, 33, 3) float32 [0, 1]
source_stats = result.source_stats  # dict(mean_rgb, std_rgb, h, w, ...)

# 3. 多图加权(覆盖更多色域)
result_multi = extractor.extract_multi(
    ["ref1.jpg", "ref2.jpg", "ref3.jpg"],
    weights=[1.0, 1.5, 1.0],   # 可选,默认等权
    cube_size=33,
)

# 4. RAW 输入(走 rawpy demosaic)
result_raw = extractor.extract(
    "photo.cr3",
    raw_mode="half",          # "thumb" / "half" / "full"
    use_camera_wb=True,
)
```

**返回的 `HALDExtractionResult` 字段**:
- `lut_data`: `(N, N, N, 3)` float32,RGB ∈ [0, 1]
- `config`: 实际使用的 `HALDExtractionConfig`
- `source_stats`: `{mean_rgb, std_rgb, min_rgb, max_rgb, h, w}`
- `method`: `nearest` / `gaussian_rbf` / `shepard_idw`
- `extraction_time_sec`: float
- `metadata`: 源路径、shape 等

**`HALDExtractionConfig` 字段**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cube_size` | int | 33 | LUT 网格大小(8/17/25/33/64/65) |
| `method` | str | `"gaussian_rbf"` | 提取算法(`nearest` / `gaussian_rbf` / `shepard_idw`) |
| `smoothing_passes` | int | 1 | 3D box 平滑次数(0=不平滑) |
| `rbf_sigma` | float | 0.05 | Gaussian RBF 带宽(归一化 RGB 单位) |
| `idw_power` | float | 2.0 | Shepard IDW 的 p(1/距离^p) |
| `n_samples` | int | 10000 | RBF/IDW 随机采样像素数(加速 O(N³ × H*W)) |
| `seed` | int | 42 | 随机种子(可复现) |

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

**HALD 提取器测试**(`tests/test_hald_extractor.py`,24 个测试):
- 基础 API / shape / dtype / 值范围 (5)
- 3 种算法 × 参数化验证色彩保留 (4)
- identity 输入 → 近似 identity LUT (1)
- 3D box 平滑降噪 (4)
- multi-reference 多图加权 (3)
- 便捷函数 + .cube 写出符合 Adobe Cube LUT spec 1.0 (2)
- 性能冒烟(17³ < 30s,33³ < 60s)(2)
- source_stats 字段 (3)

代码覆盖率:`core/hald_extractor.py` **98%** 行覆盖。

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

### v0.3.0 (2026-06-16) - HALD-based 3D LUT 提取(路线 A)

**新增**:
- ✅ **`extract-hald` CLI 子命令** + `HALDPixelExtractor` Python API
  - 从单张参考图生成**真正的 3D LUT**(解决"LrC/PS 应用 LUT 后无色彩变化"问题)
  - 3 种算法:`nearest` / `gaussian_rbf` ⭐ (默认) / `shepard_idw`
  - 支持 17³/33³/65³ 多种网格尺寸(LrC 14 / Resolve / Premiere 兼容)
  - 多图加权提取(覆盖更多色域)
  - RAW 输入(走 rawpy demosaic,与 `extract` 共享 `--raw-mode`/`--raw-wb`)
- ✅ `tests/test_hald_extractor.py` — **24 个单元测试**(98% 行覆盖)
  - 基础 API / 3 算法 / identity / smoothing / multi-reference / .cube 规范 / 性能冒烟
- ✅ **不依赖 scipy** — 纯 numpy + Pillow 实现
  - KD-tree 最近邻:暴力 numpy `argmin`
  - Gaussian RBF / Shepard IDW:随机采样 + 向量化距离矩阵
  - 3D box 平滑:可分离 cumsum `box1d`(沿 3 个轴各一次)
- ✅ 文档:`README.md` 加 `#### 1.5 extract-hald` + Python API 段 + `HALDExtractionConfig` 表

**为什么需要 `extract-hald`**:
旧的 `extract` 用 `StyleExtractor`(中性基线统计假设 `mean_L=50, std=25`),算法本质是 **1D 对角线变换** — 3D 维度信息全部丢失。LrC/PS/Resolve 加载后"对角线 LUT"等价于 Curves 单通道调整,应用后照片几乎无色彩变化。

`extract-hald` 用真实像素映射生成 3D LUT,验证:teal_orange 256×256 测试图 → LUT 应用后 Orange bin 输出变 Teal,反之亦然(完整 3D 翻转)。

**端到端验证**:
```bash
lut-generator extract-hald reference.jpg -o style_lut.cube -s 33 -m gaussian_rbf
# 17³ 耗时 ~1s,33³ ~5-15s,65³ ~30-60s(取决于图片尺寸)
```

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

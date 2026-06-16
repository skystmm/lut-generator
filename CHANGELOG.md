# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> 项目当前在 `main` 分支,版本号 `0.2.1`(2026-06-17,见下方)。
> 下面 `[Unreleased]` 段记录 Phase 1.6+/1.7 的 PresetMatcher 风格匹配(已 commit 在 main)。

---

## [Unreleased]

### Added
- **`.xmp` Creative Profile 导出**(LrC 14 **官方 3D LUT 路线**,推荐): `LUTExporter.export_xmp_creative_profile()` + CLI `-f xmpcreative`
  - 通过 `crs:RGBTable` 字段内嵌完整 3D LUT(BGR 顺序,16-bit big-endian,zlib 压缩,Ascii85 编码)
  - 安装路径:
    - **Windows**: `C:\ProgramData\Adobe\CameraRaw\Settings\`
    - **Mac**: `/Library/Application Support/Adobe/CameraRaw/Settings/`
  - 重启 LrC 14 → Develop → Profile Browser → 找"lut-generator"分组应用
  - 33 个新测试 (`test_xmpcreative_exporter.py`): 覆盖 5³/17³/33³/65³、必备字段、XML 解析、round-trip 解码验证、压缩比、Ascii85 字符集、MD5 一致性、auto-suffix、回归(5 个旧格式)
  - ⚠️ `[EXPERIMENTAL]` Adobe 私有 `asymmetric85` 编码细节未公开,本实现走标准 Ascii85 + zlib;LrC 14 通常宽容接受,若加载不成功可调

- **`.lrtemplate` 预设导出**(LrC 7.3 之前路线,**已弃用 fallback**): `LUTExporter.export_lrtemplate_preset()` + CLI `-f lrtemplate`
  - 走 LrC 旧 JSON preset;**实测不带 `LUT3D` 字段**,仅 100+ 个 per-channel 调色参数
  - LrC 14 自动隐藏并转 .xmp,仅兼容老 LrC 用户
  - 13 个新测试 (`test_lrtemplate_exporter.py`): 覆盖 17³/33³/65³、字段齐备性、JSON 合法、auto-suffix、dispatch、回归

### Fixed
- **静默 `colour-science` 启动时的 `ColourUsageWarning`**: 之前 CLI 启动会污染性输出 2 行 `"Matplotlib" / "SciPy" related API features are not available`(实际上 `colour-science 0.4.7` 已不硬依赖这两个,警告属软提示,不影响功能)。`src/lut_generator/__init__.py` 顶部加 `warnings.filterwarnings('ignore', category=Warning, module=r'colour\.utilities\.verbose')`,2 行内静默。**踩坑**:`ColourUsageWarning` 直接继承 `Warning`(**不**是 `UserWarning`),所以 `category=UserWarning` 匹配不到,必须用 `category=Warning`。

### Documentation
- **`XMP_LRTEMPLATE_RESEARCH.md`** — 完整的 LrC 14 preset 格式调研报告(17.7 KB),含:
  - `.lrtemplate` 真实字段集(从 GitHub `NightFactory.lrtemplate` 反推)
  - `.xmp` Creative Profile 真实结构(从 exiftool 论坛 Boyd 2020 帖反推)
  - DNG spec 1.4 PDF 中 `ProfileLookTableDims` / `ProfileLookTableData` / `ProfileLookTableEncoding` / `ProfileToneCurve` 字段定义
  - LrC 7.3 (2018-04) 弃用 .lrtemplate 时间线
  - 27 个分类链接(Adobe 官方文档、exiftool 论坛、Adobe 社区、mattk.com、jasonodell、lrjson、dcptool 等)
  - 推荐路线:`xmpcreative`(.xmp Creative Profile, LrC 14 官方 3D LUT 路径)

### Misdiagnosis Withdrawn
- **`crs:ColorTable` 8-bit 误诊撤回**(从历史 `220f558` force-replaced): 实际 `crs:ColorTable` 是 16-bit(0-65535),LrC 14 不消费作为 3D LUT,仅作 1D tone curve。**`.xmp` preset 路线本质是 1D 表达,无法保留 3D LUT**。真正 3D 路线是 `.xmp` Creative Profile(`crs:RGBTable`)。
- **`.lrtemplate` 推荐宣传撤回**(从 `d27b599` 注释撤回): 真实 LrC 导出的 `.lrtemplate` **没有** `LUT3D` 字段;LrC 7.3 起弃用,LrC 14 自动隐藏。**`.lrtemplate` 不能装 3D LUT**。

### Phase 1: 单图反推 preset (preset_extractor + PresetMatcher)
- **Phase 1.4 — VGG-11 感知损失替代 Gram 矩阵** (`703f0c6`): 修 `core/vgg_perceptual.py` 2 个 bug (移除 `@torch.no_grad()` 阻断梯度 + 修 state_dict key strip `features.X.weight` → `X.weight`)。VGG-11 权重下载自 PyTorch 官方源 (`models/vgg11-bbd30ac9.pth`, 507MB)
- **Phase 1.5 — baseline 参数打破 trivial 解** (`eeadc1a`): `extract()` 新增 `baseline` 参数,无 baseline 时用 0.5 灰 fallback。L-BFGS 不能再选 theta=0 渲染 = identity 的 trivial 解,exposure -0.86 非零
- **Phase 1.6+ — PresetMatcher 风格匹配 (C 路径)** (`00b27fa`): 不通过 L-BFGS 反推 67 维参数,而是枚举 10 个经典风格 + CIEDE2000 找最接近 ref 的 preset。**覆盖率 4× 提升** (1% → 20% < 5 像素),**速度 25× 提升** (13s → 0.5s)
- **Phase 1.7 — 扩展 preset 库到 50** (`3b1955b`): 6 大类 (Color Films 暖/冷、B&W、Cinematic、Vintage、HDR/现代) × 50 preset。丽江图测试: best mean ΔE 18.95 (modern_pastel), < 10 像素 35.3%, 2.6s/张。**饱和效应**: 50 vs 10 只改善 5%
- **Phase 1.9 — NN-based baseline 估计器 归档 (不执行)**: 4 候选方案全需 GPU (主机 CPU only, `torch.cuda.is_available() = False`, 训练 30-60 天不实际)。详见 `WEEK6_PRESET_MATCHER_DELIVERY.md` 第九节

### Tests
- **PresetMatcher 测试**: 10 测试 (`test_preset_matcher.py`), 全过
- **pytest 全量**: 25 passed, 0.85s

---

## [0.2.1] - 2026-06-17

### Added
- **PresetMatcher 风格匹配 (Phase 1.6+ / 1.7)**: 从调色后图片反推"最接近的 Lightroom preset"
  - `lut_generator.analysis.preset_matcher.PresetMatcher` 类
  - 输入: `(baseline, ref)` 配对 (RAW + JPG, 或 0.5 灰 fallback + JPG)
  - 输出: `{best_preset, mean_ΔE, coverage_lt5/lt10, all_results}`
  - 50 个经典 preset 库 (`classic_presets.py`): Color Films 暖/冷 (20) + B&W (10) + Cinematic (6) + Vintage (7) + HDR/现代 (7)
  - **量化 (丽江图测试)**: best mean ΔE 18.95 (modern_pastel), < 5 像素 19.7%, < 10 像素 35.3%, 2.6s/张
  - **vs Phase 1.5 L-BFGS 反推**: 覆盖率 4× 提升, 速度 25× 提升, 可解释 (用户拿到风格名)
- **CIEDE2000 评测脚本** `tools/ciede2000_eval.py`: 7 项统计 (mean/median/max/p95/< 2/< 5/< 10)
- **VGG-11 感知损失** `core/vgg_perceptual.py`: Phase 1.4 修 2 bug 后, 替代 Gram 矩阵

### Documentation
- **`WEEK6_PRESET_MATCHER_DELIVERY.md`** (8.6 KB): 完整产品定位 + 算法 + 50 preset 分类 + 量化评测 + Phase 1.9 归档
- **`PROGRESS.md`**: 重写为 Phase 1.7 状态 (替代 4 月 15 日老版本)

### Commits
- `703f0c6` Phase 1.4 - VGG-11 perceptual loss replaces Gram matrix
- `eeadc1a` Phase 1.5 - baseline param to break trivial solution
- `00b27fa` Phase 1.6+ - PresetMatcher (C path: reference-based style matching)
- `3b1955b` Phase 1.7 - expand preset library to 50 (6 categories)

---

## [0.2.0] - 2026-06-14

### Added
- **相机 RAW 读取支持**: 新增 `lut_generator.utils.image_loader` 模块,通过 `rawpy` + LibRaw 支持 16+ RAW 后缀(DNG/ARW/CR2/CR3/NEF/NRW/RW2/RAF/ORF/PEF/DCR/KDC/MRW/SRW/X3F/3FR 等 600+ 机型)
  - 3 档可调: `thumb`(相机內建缩略图,几 ms) / `half`(半尺寸 demosaic,默认,~200ms/24MP) / `full`(全尺寸 AHD demosaic,~1-2s/24MP)
  - 失败优雅降级到 OpenCV,rawpy 未装时给 warning 而不是 crash
  - `get_raw_metadata(path)` 工具读机型 / ISO / 快门 / 光圈
- **Adobe Lightroom / Photoshop 预设导出**: `LUTExporter.export_xmp_preset()` + CLI `-f xmp`
  - 把 3D LUT 沿主对角线降维成 `crs:ColorTable`(3 × 256 个 16-bit 整数)
  - LR / LR Classic / ACR / PS 都能直接加载应用
  - 13 个 XMP 专项测试,纯 numpy 三线性插值(无 scipy 依赖)
- **未来规划 / Roadmap 章节**: 根 README 记录 DNG Camera Profile (.dcp) 和 Adobe .look 两种长期方向的评估(目前未实现)

### Changed
- **CLI 命令与 Python API 文档大修正**: 旧 README 写的 `lut-generator analyze --input --size` / `apply` / `report` / `from lut_generator_skill import ...` 等接口根本不存在或已弃用,全部按 `src/lut_generator/cli/main.py` 实际签名改正
  - 根 `README.md` + `lut-generator_server/README.md` + `lut-generator_skill/README.md` 同步
  - `lut-generator_skill` 目录**没有 Python 包**,旧文档是规划残留,改写为"agent 调 CLI"使用文档
- **核心类 `__init__` 加 RAW 透传参数**(`raw_mode='half'`, `use_camera_wb=True`),完全向后兼容:
  - `ColorSpaceConverter.load_image()`
  - `ColorAnalyzer(raw_mode, use_camera_wb)`
  - `StyleExtractor(raw_mode, use_camera_wb)`
  - `LUT3DGenerator.generate_from_images(..., raw_mode, use_camera_wb)`
  - `ReinhardColorTransfer.transfer_images(..., raw_mode, use_camera_wb)`

### Fixed
- README 文档与代码漂移(参见 `git log 7e8a648`)
- numpy 2.x 测试 fixture 兼容性(`np.random.RandomState.integers` → `default_rng().integers`)
- Python 3.12+ Enum 字符串格式化(`f"{Enum}"` → `Enum.value`)

### Dependencies
- 新增 `rawpy>=0.17.0`(全平台 wheel,无需外部 LibRaw;已加进 `pyproject.toml`)

### Tests
- `tests/test_xmp_exporter.py`: 13 个 XMP 导出用例
- `tests/test_image_loader.py`: 41 个 RAW 读取用例 + 2 skip(无 rawpy 环境)
- 合跑 **54 passed + 2 skipped**, 0.85s

---

## [0.1.0] - 2026-04-30

### Added (初版提交)
- 核心 LUT 生成:LUT3DGenerator(Lab 空间,Reinhard 色彩迁移)
- 多格式导出: .cube (Adobe) / .3dl (Autodesk) / .clf (ACES)
- 批量分析: BatchAnalyzer + 特征融合(FeatureFusion)
- 视频 LUT 提取: `video-generate` / `video-extract` + 场景检测
- CLI 子命令: `generate` / `analyze` / `transfer` / `extract` / `video-generate` / `video-extract`
- 性能优化模块: 缓存 + 并行 + 内存分块
- HTML 报告生成器 / 预览对比图 / RGB 直方图 / Lab 色域图
- OpenClaw Skill 包装(实际仅 SKILL.md + README.md,无 Python 包 — 已在 unreleased 修正文档)

### Known Issues (from initial commit)
- README 文档与代码漂移严重(参见 unreleased "Fixed" 部分)
- `WEEK4_README.md` 的 Python API demo 仍引用已弃用根级 shim 路径(`from lut3d_generator import ...`),本 release 暂不修
- `lut-generator_skill/` 目录没有 Python 包但 README 描述成"完整 Python 库",误导性已被本 release 修正

---

## 版本约定

本项目使用 [Semantic Versioning](https://semver.org/):

- **MAJOR**: 不兼容 API 变更(目前 `0.x`,API 仍在演化)
- **MINOR**: 向后兼容的功能新增(本次 unreleased: 0.1.0 → 0.2.0)
- **PATCH**: 向后兼容的 bug 修复

每个 release 标注日期 + 链接到对应的 commit range。

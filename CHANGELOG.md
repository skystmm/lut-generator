# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> 项目当前在 `main` 分支,版本号 `0.2.0`(unreleased,见末尾)。
> 历史 commit 是 2026-04 起由原 [skystmm/lut-generator](https://github.com/skystmm/lut-generator) 仓库累积。

---

## [Unreleased]

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

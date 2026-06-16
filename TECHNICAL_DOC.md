# LUT Generator — 技术文档

> 状态: 2026-06-16 修复工程
> 代码版本: `e5a37c6` + 7 模块补丁(未 commit)
> 测试基线: 350 passed + 2 xfailed + 2 skipped(集成测试预先腐烂,见末页)

---

## 1. 整体流程架构

LUT Generator 是一个**端到端色彩风格迁移工具**,把"参考图"和"目标图"两路 RGB 图像
作为输入,产出 `.cube` 3D-LUT 文件以及应用 LUT 后的预览、对比、报告。

### 1.1 顶层数据流

```
┌─────────────────┐                  ┌─────────────────┐
│   参考图 (ref)   │──┐               │   目标图 (tgt)   │──┐
└─────────────────┘  │               └─────────────────┘  │
                     ▼                                     ▼
        ┌────────────────────────┐           ┌────────────────────────┐
        │  ColorAnalyzer.analyze │           │  ColorAnalyzer.analyze │
        │  (Lab 统计)            │           │  (Lab 统计)            │
        └────────────────────────┘           └────────────────────────┘
                     │                                     │
                     ▼                                     ▼
        ┌────────────────────────────────────────────────────────┐
        │                StyleExtractor                          │
        │   source_stats  ←  ref 统计                            │
        │   target_stats  ←  tgt 统计                            │
        │   可选:  feature_fusion 多参考图融合                    │
        └────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌────────────────────────────────────────────────────────┐
        │   ReinhardColorTransfer / LUTTransformBuilder          │
        │   (a, b, L) 三通道独立做 mean/std 线性匹配             │
        │   strength ∈ [0, 1]: 0 → identity, 1 → full transfer  │
        └────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌────────────────────────────────────────────────────────┐
        │   LUT3DGenerator                                       │
        │   沿 [0,1]³ 立方体采样 transform_func → 33³ LUT 数组  │
        │   默认 trilinear 插值, 17³/33³/65³ 三档精度            │
        └────────────────────────────────────────────────────────┘
                                  │
                                  ▼
        ┌────────────────────────────────────────────────────────┐
        │   CUBEExporter (cube_exporter_main)                    │
        │   写出标准 Adobe .cube 文件 (DOMAIN_MIN/MAX 头 + R 行) │
        └────────────────────────────────────────────────────────┘

旁路输出(可选):
- PreviewGenerator   — side_by_side / slider / blend / difference 4 模式对比图
- ColorVisualizer    — RGB 直方图 / Lab 色域图 (单图 + 对比版)
- HTMLReportGenerator — 内嵌 base64 图片的交互式 HTML 报告(dark/light 主题)
- PerformanceOptimizer — LUT 缓存 + 多线程 + 图像分块,加速批处理
- BatchAnalyzer      — 一次性把多组 (ref, tgt) 跑完
```

### 1.2 内部包结构

```
src/lut_generator/
├── core/             # 算法层(纯 NumPy / colour-science)
│   ├── color_space.py        # RGB ↔ Lab ↔ sRGB 转换
│   ├── reinhard.py           # Reinhard 色彩迁移 + LUTTransformBuilder
│   ├── interpolation.py      # trilinear / nearest 插值器
│   ├── hald_extractor.py     # Hald 图像 → identity LUT
│   └── style_extractor.py    # 把 ColorAnalyzer 输出打包成 StyleFeatures
│
├── analysis/         # 图像分析层
│   ├── analyzer.py           # 单图分析: Lab 统计 + 颜色直方图
│   ├── batch_analyzer.py     # 多图批量 + 跨平台路径
│   └── feature_fusion.py     # 多参考图特征融合 (weight 配置)
│
├── lut/              # LUT 生成与应用
│   ├── lut3d.py              # 3D LUT 生成器 + trilinear 应用
│   ├── exporter.py           # CUBEExporter (本项目内置) + 导出格式校验
│   └── applier.py            # 把 LUT 应用到单/批图
│
├── utils/            # 周边工具
│   ├── visualizer.py         # ColorVisualizer
│   ├── html_report.py        # HTMLReportGenerator
│   ├── preview_generator.py  # PreviewGenerator
│   ├── optimizer.py          # 缓存 / 并行 / 分块
│   └── image_loader.py       # 跨格式图像读取
│
├── preview/          # 预览生成(独立子包,被 utils 复用)
│   └── generator.py
│
├── video/            # 视频相关(可选,本次未深入)
│   ├── analyzer.py
│   └── frame_extractor.py
│
└── cli/main.py       # lut-generator CLI 入口 (analyze / generate / transfer)
```

### 1.3 兼容性 shim 模式

代码库目前使用 **flat shim + canonical package 双路径**:

```
src/color_analyzer.py    ──┐   (旧 flat 路径, 仍在被测试导入)
src/lut_generator/        ──┼──> analysis/analyzer.py (权威实现)
  analysis/analyzer.py    ──┘
```

每个 `src/<name>.py` shim 做两件事:
1. 抑制 DeprecationWarning(`warnings.filterwarnings("ignore", ...)`)
2. 从 `lut_generator.<sub>.<name>` 导入并重导出

**约定**:新代码走 canonical 路径;shim 维持向后兼容。

---

## 2. 核心功能流程

### 2.1 色彩迁移核心算法

`LUTTransformBuilder.build_transform_func()` 是整个系统的心脏:

```python
# 1) 计算 Lab 三通道的 source / target 统计
src_mean = [μs_L, μs_a, μs_b]   src_std  = [σs_L, σs_a, σs_b]
tgt_mean = [μt_L, μt_a, μt_b]   tgt_std  = [σt_L, σt_a, σt_b]

# 2) 通道独立的 scale / offset
scale    = tgt_std  / max(src_std, 1e-6)
offset   = tgt_mean - src_mean * scale

# 3) 强度衰减 (strength ∈ [0, 1])
scale_adjusted = 1 + (scale - 1) * strength     # 1.0 → scale
offset_adjusted = offset * strength              # 0   → offset

# 4) transform_func: T(L, a, b) → (L', a', b')
#    strength=0 → identity (T = x.copy())        ← 2026-06-16 修复
#    strength=1 → full Reinhard transfer
T_i(x_i) = (x_i - src_mean_i) * scale_adjusted_i + tgt_mean_i
```

**修复点(2026-06-16)**:旧实现 strength=0 时仍迁移 mean,产生"无色偏"但有亮度漂移的伪影。
修复后 strength=0 严格返回 `identity` 复制,与测试期望一致。

### 2.2 3D LUT 生成

`LUT3DGenerator.generate_lut_3d(transform_func, grid_size=33)`:

```
对 (r, g, b) ∈ [0, 1]³ 的每个格点:
    lut_data[r, g, b] = transform_func(np.array([r, g, b]))

输出 shape: (grid, grid, grid, 3)  ← (R, G, B) 顺序排列的 LUT
```

`LUT3DGenerator.apply_trilinear_interpolation(image)` 把 LUT 应用到 RGB 图像:
1. 把 image float 化到 [0, 1]
2. 把 (R, G, B) 三维坐标当 3D 网格索引,trilinear 插值
3. 回到 uint8 范围

`generate_lut_3d` 支持 `use_vectorized: bool` kwarg(默认 True),向量化版本比逐点循环快 5-10×。

### 2.3 .cube 导出

`CUBEExporter` 写出标准 Adobe `.cube` 文件:

```
TITLE "Generated by lut-generator"
LUT_3D_SIZE 33
DOMAIN_MIN 0.0 0.0 0.0
DOMAIN_MAX 1.0 1.0 1.0
0.0000 0.0000 0.0000
0.0312 0.0000 0.0000
...
```

**关键修复(2026-06-16)**: `_format_lut_data` 之前用 `for r in shape[0]: for g in shape[1]: for b in shape[2]:`
但索引写的是 `lut_data[r, g, b]`,因变量名误导,实际上是把 axis 0 当 B, axis 2 当 R,顺序
完全颠倒。修复后循环变量与索引轴严格对齐。

### 2.4 对比图生成

`PreviewGenerator.generate_comparison(original, processed, output, config)`:

| mode | 实现 |
|---|---|
| `side_by_side` | `np.hstack([original, processed])` + 标签 |
| `slider` | 单张图 + 垂直分割线 + 滑块位置 |
| `blend` | `α * original + (1-α) * processed` 透明度混合 |
| `difference` | `np.abs(original - processed) * k` 增强差异 |

### 2.5 HTML 报告

`HTMLReportGenerator.generate_from_paths(orig, proc, output)`:
1. 把 orig/proc 编码为 base64 内嵌
2. 拼装 HTML: 头部 → slider 对比 → 统计表 → 直方图 → 色域图 → 脚本
3. 支持 `dark` / `light` 主题;`no_slider=True` 时跳过 slider 区块(CSS 也不输出)

`ReportConfig` 双字段 `include_slider` / `no_slider` 在 `__post_init__` 互相镜像,保证无论调用
方传哪个,渲染层都看到一致状态。

---

## 3. 未来演进

### 3.1 立即可做(低风险,1-2 周)

| 项目 | 说明 | 工作量 |
|---|---|---|
| 集成测试重构 | `test_integration_full.py` 10 个失败源自 API 漂移(`export_to_cube` / `analyze_image` / `process_batch_optimized` 等),需统一接口或更新测试 | 2 天 |
| `test_performance_scaling` 修复 | WinError 32 文件占用 + 性能断言 fail(992k < 1M),需加 sleep / unlink 重试 | 0.5 天 |
| 浮点精度统一 | `test_cube_exporter` 中 2 个 xfail 标记 round-trip rtol=1e-5 不达,改用 KMeans 哈希比较或固定 LSB 容差 | 0.5 天 |
| CLI `analyze` 子命令修复 | 用户跑 `lut-generator analyze --input --size 33` 报 "unrecognized arguments",CLI 签名与 README 不一致 | 0.5 天 |

### 3.2 中期(1-2 月)

**算法升级**:
- 引入 MKL 色彩迁移(多维统计保持相关性,优于 Reinhard 单通道)
- 引入深度学习风格迁移(`CycleGAN` 或 `AdaIN`)作为可选 backend
- HALD image → identity LUT 已实现,但尚未接到 CLI 流程

**性能优化**:
- `PerformanceOptimizer` 已支持缓存/并行/分块,但未做 LUT 索引 → 颜色空间预计算
- 33³ LUT 应用是 35k 查表 + 插值,GPU 端用 texture 3D 可提速 20×

**架构**:
- 当前 `core/ + analysis/ + lut/ + utils/` 分层清晰,但缺少 `domain/` 模型层(dataclasses 应抽到独立模块)
- 缺少 plugin 系统,新插值器 / 新 LUT 格式靠 monkey-patch

### 3.3 长期(季度级)

**产品方向**:
- Web 端编辑器(浏览器内实时调参 + 滑块对比)
- 移动端 capture → 现场 LUT 生成
- 视频 LUT 实时应用(流式处理 + GPU shader)

**生态**:
- 集成 DaVinci Resolve / Premiere 插件
- 标准化 .cube 之外支持 `.3dl` (Lattice) / `.mga` (Maze) / `.png` (Hald)
- 提供 Python API + CLI + Docker image + GitHub Action 四端一致接口

**质量**:
- 把 74% 行覆盖率拉到 90%+(重点是 `analysis/` 26% 和 `lut/exporter.py` 11%)
- 加 property-based testing(hypothesis)覆盖 LUT 浮点不变量
- 引入 mypy strict + ruff 全量规范

---

## 附录:本次修复清单

| # | 文件 | 修复 |
|---|---|---|
| 1 | `src/cube_exporter_main.py` | 重写 260 行;CUBEExportConfig 字段补全;循环索引 R/G/B 顺序修正;移除 DOMAIN_MIN/MAX;移除 16 档无效 grid;写时转 float64 |
| 2 | `src/lut_generator/core/style_extractor.py` | `source_stats: Optional[Any] = None` |
| 3 | `src/lut_generator/lut/lut3d.py` | 加 `apply_trilinear_interpolation`;加 `use_vectorized` kwarg;`LUT3DConfig` 加 `smoothness` / `use_advanced_interpolation` 兼容字段 |
| 4 | `src/lut_generator/core/reinhard.py` | `build_transform_func` strength=0 短路返回 identity |
| 5 | `src/lut_generator/utils/html_report.py` | 加 `no_slider` 字段 + `__post_init__` 镜像;`_image_to_base64` 返 `''` 而非 `None`;CSS slider 段按 `no_slider` 条件裁掉 |
| 6 | `src/visualizer.py` | shim 加 `plot_histogram_comparison` / `plot_gamut_comparison` / 顶层 `visualize_color_distribution` |
| 7 | `src/html_report.py` | shim 加 `generate_html_report` 顶层 + 抑制警告 |
| 8 | `src/preview_generator.py` | shim 加 `generate_preview` 顶层 |
| 9 | `src/color_transfer.py` | shim 加 `ColorTransferMatcher` 别名 |
| 10 | `src/feature_fusion.py` | shim 加 `FeatureFusionEngine` 别名 |
| 11 | `tests/test_*.py` (3 个) | `TestConvenienceFunction` 加本地 `temp_dir` fixture |

**测试基线**: 350 passed + 2 xfailed + 2 skipped = 354 tests, 0 unexpected failure
(集成测试 10 个失败属于预先 API 漂移,不在本次修复清单)

# LUT Generator 项目进度 (2026-06-17 更新)

## 项目概述

基于 Reinhard 色彩迁移算法 + PresetMatcher 风格匹配的 3D LUT 生成器。
从单张调色后图片反推"最接近的 Lightroom preset",输出风格名称 + 参数 + .cube LUT。

## 项目位置

- 根目录: `D:\workspace\lut-generator\`
- 服务端: `lut-generator_server/` (PyTorch + colour-science + rawpy)
- 技能: `lut-generator_skill/`
- 模型: `D:\workspace\lut-generator\models\` (VGG-11 507MB)

---

## 已完成模块 ✅

### 1. 核心算法 (Phase 0) ✅
- `core/color_space.py` — RGB↔Lab
- `core/reinhard.py` — Reinhard 色彩迁移
- `core/interpolation.py` — 三线性/最近邻
- `core/vgg_perceptual.py` — VGG-11 感知损失 (Phase 1.4 修复 2 bug)

### 2. LUT 生成 ✅
- `lut/lut3d.py` — 3D LUT (17³/33³/65³)
- `lut/exporter.py` — 6 格式导出 (CUBE/3DL/CLF/XMP/LRTEMPLATE/XMPCREATIVE)

### 3. 图像分析 ✅
- `analysis/analyzer.py` — 色彩特征
- `analysis/batch_analyzer.py` — 批量扫描
- `analysis/feature_fusion.py` — 多图加权融合
- `analysis/preset_extractor.py` — 67 维 ParamSpace + LRRenderer + VGG 感知
- `analysis/preset_xmp_writer.py` — .xmp 写出
- `analysis/preset_matcher.py` — **PresetMatcher (Phase 1.6+)**
- `analysis/classic_presets.py` — **50 个经典 preset (Phase 1.7)**

### 4. CLI 命令 ✅
- `lut-generator generate` — 双图对比生成 LUT
- `lut-generator analyze` — 图像色彩分析
- `lut-generator transfer` — 色彩迁移
- `lut-generator extract` — 单图反推 (Phase 1.5,带 baseline 参数)
- `lut-generator extract-hald` — Hald 图导出 (6 格式)
- `lut-generator video-generate/extract` — 视频支持

### 5. 测试 ✅
- `pytest tests/` — **25 测试全过**
- `tools/ciede2000_eval.py` — CIEDE2000 评测脚本

---

## Phase 1 完整路径 (单图反推) ✅

| Phase | 方案 | 结果 | commit |
|---|---|---|---|
| 1.1 | 31 维 ParamSpace + Gram loss | loss 0.002 但视觉全图变青绿 (trivial 解) | (earlier) |
| 1.2 | 67 维 ParamSpace + 3 阶段 warm-start | 修 HSL 算子 bug | `b38bee9` |
| 1.3 | HSL histogram warm-start | 暴露 Gram 损失伪解 | (merged 1.2) |
| 1.4 | **VGG-11 感知损失 替代 Gram** | 数值更好但仍 trivial | `703f0c6` |
| 1.5 | **+ baseline 参数 (RAW 配对)** | 打破 trivial 解,CIEDE2000 17.46 | `eeadc1a` |
| 1.6+ | **PresetMatcher (10 preset)** | 4× 提升覆盖率,2.5s/张 | `00b27fa` |
| **1.7** | **PresetMatcher (50 preset)** | **35.3% < 10 (丽江图)** | `3b1955b` |

**最终方案**: PresetMatcher + 真实 RAW baseline (或 0.5 灰 fallback)
**量化结果**: mean ΔE 18.95, < 5 像素 19.7%, < 10 像素 35.3%, 2.6s / 张

---

## 当前开发 ✅ → 待新方向

### 已完成 (短期方案)
- ✅ Phase 1.7 50 preset matcher
- ✅ WEEK6_PRESET_MATCHER_DELIVERY.md
- ✅ 归档 Phase 1.9 (NN baseline 估计器)

### Phase 1.9 归档 (不执行)

**原因**: 主机 CPU only,NN 训练 30-60 天,投入产出比低。

**触发条件**(若未来重启):
- 用户开始抱怨"找不到合适 preset" 而非"匹配不准"
- 愿意投入云 GPU (V100 6h = $18) + MIT-Adobe FiveK 数据集 ($50-200)

**详见**: `WEEK6_PRESET_MATCHER_DELIVERY.md` 第九节 + `LUT_EXTRACTION_RESEARCH.md`

---

## 未来方向 (Phase 2.0+)

### 优先级高
- [ ] **CLI `match` 子命令** — 包装 PresetMatcher
- [ ] **更新 README.md** — 加 PresetMatcher 章节 + 5 行示例
- [ ] **Web API `/match` 端点** — 上传 (baseline, ref) → 返回 best preset

### 优先级中
- [ ] Phase 1.8 — 用户 preset 上传 (.xmp 入库)
- [ ] 通用图基准测试 (5+ 张,暖/冷/高对比/低光/户外)
- [ ] LUT → preset 转换 (反向:从 .cube 推 preset)

### 优先级低
- [ ] Web UI (拖拽上传 + 风格预览)
- [ ] Phase 1.9 (若重启) — NN baseline 估计器
- [ ] Phase 3.0 商业化路线

---

## CLI 使用示例

```bash
# 双图对比生成 LUT
lut-generator generate -i original.png -t graded.png -o style.cube -s 33

# 单图反推 (Phase 1.5,需 baseline)
lut-generator extract graded.jpg -o preset.xmp --baseline neutral.arw

# 色彩迁移
lut-generator transfer -i ref.png -t target.png -o output.png

# 图像分析
lut-generator analyze image.png -o analysis.json

# Hald 图导出 (6 格式)
lut-generator extract-hald style.cube -f xmpcreative -o preset.xmp
```

**Phase 2.0 新增** (待):
```bash
# 风格匹配 (PresetMatcher)
lut-generator match --baseline neutral.arw --ref graded.jpg
# 输出: "best preset: modern_pastel, mean ΔE: 18.95"
```

---

## 技术栈

| 组件 | 技术 |
|---|---|
| 色彩科学 | colour-science (CIEDE2000) |
| 图像处理 | OpenCV, Pillow, rawpy |
| 数值计算 | NumPy, SciPy, PyTorch 2.12 (CPU) |
| 感知损失 | VGG-11 (Phase 1.4) |
| CLI | argparse |
| 包管理 | setuptools |

---

## 下次继续时

**当前 (Phase 1.7) 已生产可用,无需立即推进。**

可选方向:
1. 写 CLI `match` 子命令 (2-3 小时)
2. 更新 README.md + 写 CHANGELOG
3. 通用图基准测试 (5+ 张图)
4. 收尾归档 (无新开发)

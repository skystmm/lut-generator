# LUT 提取与逆向工程 — 完整调研报告

> **作者**: Hermes (minimax)
> **日期**: 2026-06-15
> **项目**: `lut-generator` (D:\workspace\lut-generator)
> **范围**: LUT 容器格式 / 商业 + 开源工具 / 逆向算法 / 实施建议
> **总字数**: ~22 KB

## 目录

- [0. TL;DR(执行摘要)](#0-tldr-执行摘要)
- [1. LUT 容器格式 — 包含什么](#1-lut-容器格式--包含什么)
  - [1.1 .cube (Adobe/Iridas) — 1D + 3D LUT 文本格式](#11-cube-adobeiridas--1d--3d-lut-文本格式)
  - [1.2 .3dl / .flame / .lustre (Discreet/Kodak/Autodesk)](#12-3dl--flame--lustre-discreetkodakautodesk)
  - [1.3 .xmp Creative Profile (Lightroom/ACR)](#13-xmp-creative-profile-lightroomacr)
  - [1.4 .lrtemplate (Lightroom 7.3 旧版预设)](#14-lrtemplate-lightroom-73-旧版预设)
  - [1.5 DNG Profile / DCP — Camera Calibration](#15-dng-profile--dcp--camera-calibration)
  - [1.6 Hald CLUT — 2D 图像格式](#16-hald-clut--2d-图像格式)
  - [1.7 CLF — Common LUT Format (ACES/Academy)](#17-clf--common-lut-format-acesacademy)
  - [1.8 行业级格式对照](#18-行业级格式对照)
- [2. 商业 / 开源 LUT 提取工具](#2-商业--开源-lut-提取工具)
  - [2.1 商业工具](#21-商业工具)
  - [2.2 开源工具](#22-开源工具)
- [3. 逆向 LUT 的算法](#3-逆向-lut-的算法)
  - [3.1 单图风格提取 (HALD-based)](#31-单图风格提取-hald-based)
  - [3.2 双图对训练 (Source/Target pairs)](#32-双图对训练-sourcetarget-pairs)
  - [3.3 网格弯曲 (Grid Bending, 手工)](#33-网格弯曲-grid-bending-手工)
  - [3.4 神经网络 LUT](#34-神经网络-lut)
  - [3.5 颜色对插值 (Snibgo sparse HALD)](#35-颜色对插值-snibgo-sparse-hald)
  - [3.6 实用对比](#36-实用对比)
- [4. 逆向 LUT 所需的信息](#4-逆向-lut-所需的信息)
  - [4.1 必要信息](#41-必要信息)
  - [4.2 可选增强](#42-可选增强)
  - [4.3 数据规模建议](#43-数据规模建议)
- [5. 实施建议 — 适合 `lut-generator` 的方案](#5-实施建议--适合-lut-generator-的方案)
  - [5.1 路线 A: HALD-based(快速,推荐)](#51-路线-a-hald-based快速推荐)
  - [5.2 路线 B: Image-pair 训练(高精度,慢)](#52-路线-b-image-pair-训练高精度慢)
  - [5.3 路线 C: Neural 3D LUT(研究型)](#53-路线-c-neural-3d-lut研究型)
  - [5.4 路线 D: 格式互转 + HALD 库](#54-路线-d-格式互转--hald-库)
- [6. 参考文献 & 链接](#6-参考文献--链接)

---

## 0. TL;DR(执行摘要)

**LUT 提取(逆向)有 4 类核心算法**,所需输入差异巨大:

| 路线 | 输入 | 输出精度 | 速度 | 适合场景 |
|---|---|---|---|---|
| **A. HALD-based** | 1 张参考图 + HALD identity | 中(可调) | 极快 | 个人创作者,带 HALD 库 |
| **B. Image-pair 训练** | 80+ source/target 图对 | 高 | 慢(分钟级) | 胶片模拟、风格迁移 |
| **C. Neural 3D LUT** | 训练集 + 神经架构 | 高 | 训练慢,推理快 | 商业级胶片 LUT |
| **D. 颜色对 IDW** | N×2 颜色列表 | 中(取决于点密度) | 中 | 局部精确控制(暗调/中间调) |

**对 `lut-generator` 的建议**:先做 **路线 A**(HALD-based),参考 `bastibe/LUT-Maker` + `oiao/clut` 实现,把现有 `extract` 能力扩展为"双向":既支持 reference image → LUT,也支持 existing LUT → analyze 信息可视化。HALD PNG 8-bit 限制 256³,实用 16³ 或 25³。

**关键陷阱**:
- **DNG `ProfileLookTable` 不是 RGB 3D LUT**,是 **HSV 调整表**(每条 3 个 float: hue shift °, sat scale, val scale),Adobe 内部用 LrC `.xmp` 实际可能与此格式一致
- **Hald CLUT "Hald"** 是 Eskil Steenberg 奶奶的 maiden name,Im(2D 像素)= N³(边长)= cube size N
- **OCIO cube 3D 顺序**:Red changes most rapidly, Blue changes least rapidly(`r + N*g + N²*b` 索引)
- **DNG 1D LUT 范围 2-65536,3D LUT 2-256**(规范硬限制)
- **1D LUT 用 linear 插值,3D LUT 用 tetrahedral 插值**(Adobe spec 要求)

---

## 1. LUT 容器格式 — 包含什么

### 1.1 .cube (Adobe/Iridas) — 1D + 3D LUT 文本格式

**官方规范**:`Cube LUT Specification Version 1.0`, Adobe Systems, September 2013(原 IRIDAS 2003)。
**文件**:PDF 25 KB,[kono.phpage.fr mirror](https://kono.phpage.fr/images/a/a1/Adobe-cube-lut-specification-1.0.pdf) / [Wikidata Q105850066](https://www.wikidata.org/wiki/Q105850066)

**完整关键字**:

```text
# 5.6 Common Keywords
TITLE "My LUT Name"
DOMAIN_MIN 0.0 0.0 0.0      # 三个通道独立设置输入域
DOMAIN_MAX 1.0 1.0 1.0      # 默认 [0,1],HDR 可超过 1.0

# 1D LUT(可选)
LUT_1D_SIZE 32                # N in [2, 65536]
# 后面 N 行,每行 3 个 float (R G B 三个并行表)

# 3D LUT(可选,1D/3D 不可同时存在)
LUT_3D_SIZE 33                # N in [2, 256]
# 后面 N×N×N 行,每行 3 个 float
# 顺序:Red 变化最快,Blue 变化最慢
# C 索引: r + N*g + N*N*b
```

**关键规则**(从 spec 摘录):
- **3D 行顺序**:"ascending index order, with the first component index (Red) changing most rapidly, and the last component index (Blue) changing least rapidly" — **与典型内存顺序相反**
- **3D 范围**:N ∈ [2, 256],且 N=256 需要 ~200MB 内存
- **1D 范围**:N ∈ [2, 65536],每通道独立 domain
- **插值**:"1D 用 linear,3D 用 tetrahedral"
- **注释**:`#` 开头(无前导空格)
- **数值编码**:1D/3D 数据是 float 0.0-1.0,无 alpha,无 HDR 标志位
- **整数编码**:"EXAMPLE: Scale 10-bit RGB from [0, 1023] to [0.0, 1.0], and then back to [0, 1023]"

**官方示例(3D)**:
```text
# Created Tue 19 Mar 2013
LUT_3D_SIZE 2
0 0 0      # r=0 g=0 b=0
1 0 0      # r=1 g=0 b=0
0 .75 0    # r=0 g=1 b=0
1 .75 0    # r=1 g=1 b=0
0 0 .25    # r=0 g=0 b=1
1 0 .25    # r=1 g=0 b=1
0 1 .25    # r=0 g=1 b=1
1 1 .25    # r=1 g=1 b=1
```

**官方示例(1D Mixed Domain)**:
```text
TITLE "Demo"
LUT_1D_SIZE 3
DOMAIN_MIN 0 0 0
DOMAIN_MAX 1 2 3
0 0 0
0.5 1 1.5
1 1 1
```

**C++ 头文件示例**(spec Annex B 提供完整 C++ 解析/写入代码,400 行,使用 `vector<float>` 嵌套):

```cpp
class CubeLUT {
    typedef vector<float> tableRow;
    typedef vector<tableRow> table1D;
    typedef vector<table1D> table3D;  // 三维嵌套
    
    string title;
    tableRow domainMin;  // [3]
    tableRow domainMax;  // [3]
    table1D LUT1D;
    table3D LUT3D;
    
    LUTState LoadCubeFile(ifstream& infile);
    LUTState SaveCubeFile(ofstream& outfile);
};
```

**OCIO 严格实现**:`AcademySoftwareFoundation/OpenColorIO/src/OpenColorIO/fileformats/FileFormatIridasCube.cpp`
- 1D 和 3D **不能共存**
- 解析时 trim/lower 每个 keyword
- `sscanf(line.c_str(), "lut_1d_size %d %c", &size1d, &endTok)` 严格格式

### 1.2 .3dl / .flame / .lustre (Discreet/Kodak/Autodesk)

**来源**:`OCIO/src/OpenColorIO/fileformats/FileFormat3DL.cpp`(Discreet's Flame LUT Format,loose interpretation)

**特点**:
- 1D shaper + 3D 组合(IRIDAS .cube 不允许)
- **3D 整数编码**(12-bit / 14-bit / 16-bit 整数,通过最大值推 bit depth)
- **网格大小限制**:`Lustre` 仅支持 17³ / 33³ / 65³,17/65 内部转 33
- Bit depth 推算规则:

| Bit depth | Expected max | 接受范围 |
|---|---|---|
| 8-bit | 255 | [0, 511] |
| 10-bit | 1023 | [512, 2047] |
| 12-bit | 4095 | [2048, 8191] |
| 14-bit | 16383 | [8192, 32767] (OCIO 直接当 16-bit) |
| 16-bit | 65535 | [32768, 131071+] |

**3DL 文件结构**(Flame 风格):
```text
# Comment here
0 64 128 192 256 320 384 448 512 576 640 704 768 832 896 960 1023    # 1D shaper
0 0 0
0 0 100
0 0 200
```

**Lustre 风格**(带 header):
```text
#Tokens required by applications - do not edit
3DMESH
Mesh 4 12
0 64 128 192 256 320 384 448 512 576 640 704 768 832 896 960 1023
0 17 17
0 0 88
...
#Tokens required by applications - do not edit
LUT8
gamma 1.0
```

### 1.3 .xmp Creative Profile (Lightroom/ACR)

**权威来源**:
- `exiftool.org/TagNames/XMP.html#crs` — 完整 426 KB 字段表
- `exiftool.org/forum/index.php?topic=11258.0` — Boyd 2020 真实 XMP Creative Profile 样本
- `developer.adobe.com/xmp/docs/xmp-namespaces/crs` — Adobe 官方 namespace(本次调研未抓到完整字段)
- 上一轮调研:`D:\workspace\lut-generator\XMP_LRTEMPLATE_RESEARCH.md`(exiftool 字段映射笔记)

**Look struct 关键字段**(exiftool 字段表摘录):

| XMP 字段 | 类型 | 含义 |
|---|---|---|
| `crs:LookAmount` | string | 强度(0-100) |
| `crs:LookCluster` | string | 分类组(例 "My Looks") |
| `crs:LookCopyright` | string | 版权 |
| `crs:LookGroup` | lang-alt | 组名(i18n) |
| `crs:LookName` | string | **预设名**(NOT a flattened tag) |
| `crs:LookParameters` | struct | 包含 LookTable |
| `crs:LookParametersCameraProfile` | string | 关联相机 profile |
| `crs:LookParametersClarity2012` | string | 清晰度值 |
| `crs:LookParametersConvertToGrayscale` | string | 转灰度 |
| **`crs:LookParametersLookTable`** | string | **3D LUT 字段**(Ascii85 + zlib 编码二进制) |
| `crs:LookParametersProcessVersion` | string | 例 "6.7" |
| `crs:LookParametersShadows2012` | string | 阴影 |
| `crs:LookParametersToneCurvePV2012` | string | 主 tone curve |
| `crs:LookParametersToneCurvePV2012Blue/Green/Red` | string | 分通道 tone curve |
| `crs:LookParametersVersion` | string | |
| `crs:LookSupportsAmount` | string | |
| `crs:LookSupportsMonochrome` | string | |
| `crs:LookSupportsOutputReferred` | string | |
| `crs:LookUUID` | string | 唯一 ID |

**编码细节**(基于 exiftool Boyd 帖 + 上一轮 `XMP_LRTEMPLATE_RESEARCH.md`):
- LookTable 字符串:Ascii85 编码 + zlib 压缩 + MD5 表名引用
- 16-bit RGB(BGR 顺序,B 最外层,见 `.lrtemplate` 段)
- Adobe 私有 asymmetric85 编码(非标准 Ascii85,字符 `v` 不在标准集)
- LrC 14 中"无变化"的根因可能是 Adobe 编码解析错误或 LrC 实际只读部分字段

**完整支持字段集合**(exiftool crs 字段表):
- **基础**:Version、ProcessVersion、PresetType、Cluster、SupportsAmount、SupportsColor、SupportsMonochrome、SupportsHighDynamicRange、SupportsNormalDynamicRange、SupportsSceneReferred、SupportsOutputReferred
- **基础调整**:Exposure、Contrast、Highlights、Shadows、Whites、Blacks、Texture、Clarity、Dehaze、Vibrance、Saturation
- **HSL 8 色**:HueAdjustment{Red/Orange/Yellow/Green/Aqua/Blue/Purple/Magenta}、SaturationAdjustment{...}、LuminanceAdjustment{...}
- **Tone Curve**:ToneCurveName2012、ToneCurvePV2012[Red/Green/Blue]、ToneCurvePV2012
- **Split Toning**:SplitToningShadowHue/Saturation、SplitToningHighlightHue/Saturation、SplitToningBalance
- **Parametric**:ParametricShadows/Darks/Lights/Highlights、ParametricShadowSplit/ParametricMidtoneSplit/ParametricHighlightSplit
- **Detail**:Sharpness、SharpenRadius、SharpenDetail、SharpenEdgeMasking、LuminanceNoiseReductionContrast/Detail、LuminanceSmoothing、ColorNoiseReduction/Detail/Smoothness
- **Effects**:GrainAmount、GrainSize、GrainFrequency、GrainSeed、PostCropVignetteAmount/Feather/Roundness/Midpoint/HighlightContrast/HighlightSaturation/ShadowContrast/ShadowSaturation
- **Color Grading**:ColorGradeBlending/ColorGradeGlobalHue/Saturation/Luminance,ShadowHue/Sat/Lum, MidtoneHue/Sat/Lum, HighlightHue/Sat/Lum, ColorGradeMidtonesHue/Saturation, etc
- **Optics**:LensProfileEnable/ChromaticAberrationScale/DistortionScale/VignettingScale, LensManualDistortionAmount, DefringePurpleAmount/DefringeGreenAmount
- **Calibration**:CameraProfile(关联)、CameraProfileDigest、HasSettings、Version
- **混合**:`MaskGroupBasedCorrections`(局部蒙版,struct+)

### 1.4 .lrtemplate (Lightroom 7.3 旧版预设)

**实际格式**:JSON-like(不是真正 JSON,有单引号/双引号混用,尾部逗号)

**真实样本**(shadawck/lrjson README 给出完整 JSON 转换后的样本):
```json
{
  "id": "A76FFDE6-31E0-4FF6-AD4E-FF6F9EE930E9",
  "internalName": "mytemplate",
  "title": "myTemplate",
  "type": "Develop",
  "value": {
    "settings": {
      "Blacks2012": 40,
      "Clarity2012": 18,
      "ColorNoiseReduction": 5,
      "ColorNoiseReductionDetail": 50,
      "ColorNoiseReductionSmoothness": 50,
      "Contrast2012": 49,
      "HueAdjustmentRed": 9,
      "HueAdjustmentYellow": -89,
      "LuminanceAdjustmentAqua": -50,
      "LuminanceAdjustmentBlue": 34,
      "LuminanceAdjustmentGreen": 5,
      "LuminanceAdjustmentMagenta": 1,
      "LuminanceAdjustmentOrange": -1,
      "LuminanceAdjustmentPurple": 40,
      "LuminanceAdjustmentRed": 0,
      "LuminanceAdjustmentYellow": 37,
      "LuminanceNoiseReductionContrast": 0,
      "LuminanceNoiseReductionDetail": 50,
      "LuminanceSmoothing": 0,
      "ParametricDarks": 0,
      "ParametricHighlightSplit": 48,
      "ParametricHighlights": 0,
      "ParametricLights": 0,
      "Tint": 33,
      "ToneCurveName2012": "Custom",
      "ToneCurvePV2012": [14, 25, 94, 112, 198, 170, 255],
      "ToneCurvePV2012Blue": [0, 0, 255],
      "ToneCurvePV2012Green": [0, 0, 255],
      "ToneCurvePV2012Red": [0, 0, 255],
      "Vibrance": 1,
      "WhiteBalance": "Custom",
      "Whites2012": 55,
      "orientation": "AB"
    },
    "uuid": "28ACD78F-6C28-4A38-B09E-A62718A4C073"
  },
  "version": 0
}
```

**LrC 14 状态**:
- LrC 7.3 (2018-04) 起 Adobe 弃用 .lrtemplate,改用 `.xmp`
- 字段集与 `.xmp` Creative Profile **完全相同**,只是序列化格式不同
- **不支持 3D LUT 字段**(Look struct 在 .lrtemplate 中未出现)

**解析工具**:`shadawck/lrjson` — 唯一开源 .lrtemplate ↔ JSON 转换器
- `lrjson myfilter.lrtemplate` → 文件输出
- `lrjson myfilter.lrtemplate -p` → stdout
- Python API:`from lrjson import convert_lr_to_json as cvj; cvj.convert("myFilter.lrtemplate", "output.json")`

### 1.5 DNG Profile / DCP — Camera Calibration

**DNG spec 1.4.0.0** [kronometric.org PDF](https://www.kronometric.org/phot/processing/DNG/dng_spec_1.4.0.0.pdf), 133 KB

**ProfileLookTable 是 HSV 调整表,不是 RGB 3D LUT**(关键发现!):

| Tag | Type | 内容 |
|---|---|---|
| **ProfileLookTableDims (50981)** | LONG × 3 | HueDivisions / SaturationDivisions / ValueDivisions(默认 ≥1, sat ≥2) |
| **ProfileLookTableData (50982)** | FLOAT × (H × S × V × 3) | 每条 3 个 32-bit float:① hue shift in degrees ② saturation scale factor ③ value scale factor |
| **ProfileLookTableEncoding (51108)** | LONG | 0=Linear, 1=sRGB (V 通道 sRGB 编码以提升暗部精度) |
| **ProfileToneCurve (50940)** | FLOAT × (Samples × 2) | (input, output) 对,0.0-1.0 线性伽马,**cubic spline 插值** |
| **ProfileHueSatMapDims (50937)** | LONG × 3 | 同 ProfileLookTableDims |
| **ProfileHueSatMapData1/2 (50938/50939)** | FLOAT × ... | 同 ProfileLookTableData(两套用于色温补偿插值) |
| **ProfileHueSatMapEncoding (51107)** | LONG | 同 ProfileLookTableEncoding |
| **ColorMatrix1/2 (50721/50722)** | SRATIONAL × (3 × ColorPlanes) | Color Matrix(3×3) |
| **ForwardMatrix1/2 (50964/50965)** | SRATIONAL × (3 × ColorPlanes) | Forward Matrix |
| **CameraCalibration1/2 (50723/50724)** | SRATIONAL × (3 × ColorPlanes) | 校准矩阵 |
| **ReductionMatrix1/2 (50725/50726)** | SRATIONAL × (3 × ColorPlanes) | 缩放矩阵 |

**嵌套循环顺序**:"value divisions in the outer loop, hue divisions in the middle loop, saturation divisions in the inner loop" — **与 DNG/PROPhoto RGB 索引顺序不同**

**应用管线**(ProfileLookTableEncoding 字段描述):
1. Convert linear ProPhoto RGB → HSV
2. (可选) V 通道 sRGB 编码
3. 用 HSV 坐标索引到 color table(得到 hue shift, sat scale, val scale)
4. 应用到原始/编码的 HSV 值
5. (可选) V 通道 sRGB 解码
6. Convert HSV → linear ProPhoto RGB

**对 LUT 提取的意义**:
- DCP 文件**不直接包含 RGB 3D LUT**,LUT 必须通过"应用 ProfileLookTable + 实际 raw → ProPhoto RGB 转换"得来
- LrC `.xmp` Creative Profile `crs:LookParametersLookTable` 字段**可能**采用相同 HSV 表格式(待验证)

**DCP 8 步处理管线**(dcptool.sourceforge.net):
1. Linearize, rescale, do black level compensation, clip
2. Derive interpolated ColorMatrix and HueSatDelta matrixes(based on color temperature)
3. Get to an XYZ (absolute color space) via the interpolated ColorMatrix
4. Convert to HSV
5. Apply the interpolated HueSatDelta mapping table
6. Convert back to XYZ
7. Do exposure compensation, fill light, etc.
8. Convert to HSV, apply the LookTable and ToneCurve, convert back

### 1.6 Hald CLUT — 2D 图像格式

**命名来源**:"Hald" = Eskil Steenberg **奶奶的 maiden name**(专有名词,非缩写)
**标准化**:`ImageMagick` 核心操作,任意支持 Hald CLUT 的软件都使用相同 2D↔3D 映射

**结构**:
- 2D 正方形图像,边长 = N³(N = cube size)
- `hald:N` 伪格式生成 identity,例 `magick hald:8 eh_h8.png` = 512×512 PNG(8³ = 512)
- N=16 = 16³ = 4096 像素(每通道 256 采样需 N=16, 16³ = 4096 entries)
- 2D 像素坐标 (x, y) ↔ 3D cube 坐标 (r, g, b):有明确 mapping 公式
- **与 .cube 不同**:`hald` 8-bit,值范围 0-255,统一灰度或彩色
- **bastibe/LUT-Maker**:`swapaxes(0, 2).reshape([64, 64, 3])` — 关键 bug 来源,因为 HaldCLUT 格式 **R 和 B 通道互换**

**identity Hald CLUT**:`magick hald:4 eh_h4.png` — 每像素 = cube 索引的 RGB,应用于图像时无变化

**核心特性**:
- 与色彩空间无关:任何 3 通道色彩空间都可用(RGB、HSV、HCL、JzAzBz)
- 颜色空间必须**图像与 Hald 一致**
- many-to-one:多输入可映射同一输出
- 处理路径:`-hald-clut` 输入图像 RGB = 坐标 → HaldClut 像素 = 输出
- interpolation:`-interpolate` 设置(linear、nearest、spline、...)
- out-of-range 输入 → 立方体外 → extrapolation(仍工作)

**通用提取流程**:
1. 生成 identity Hald CLUT(`magick hald:N identity.png`)
2. 把 identity 追加到参考帧(并排或叠加)
3. 在任意软件(PS/LR/GIMP/darktable/rawtherapee)中编辑
4. 提取 modified Hald CLUT
5. 应用到上千帧

### 1.7 CLF — Common LUT Format (ACES/Academy)

**官方规范**:`Academy Software Foundation Common LUT Format`,XML-based,ACES 项目产物
**实现**:`hpd/CLF`(Python + C++ 双实现)
**文档**:`docs.acescentral.com/clf/introduction` + `duikerresearch.com/2015/08/academy-common-lut-format`

**特点**:
- XML,可表达**链式处理节点**(matrix + 1D LUT + 3D LUT + Range + Log)
- ACES 工业标准,好莱坞 / 调色 / 母版制作广泛采用
- 适合复杂色彩管线,不是简单 LUT 容器
- 实施成本高(完整 spec 数百页)

### 1.8 行业级格式对照

| 格式 | 维度 | 编码 | 编辑性 | LrC 支持 | ACES 支持 | 适合 |
|---|---|---|---|---|---|---|
| **.cube** | 1D / 3D | text float | 易编辑 | 是(LUT 路径) | 大量 | 通用,标准 |
| **.3dl/.flame/.lustre** | 1D+3D | text int | 可读但冗长 | 否 | 是(OCIO) | 调色 / 母版 |
| **.xmp Creative Profile** | struct | XML+Ascii85 | 二进制 LUT + 编辑 | **是(原版)** | 否 | Lightroom 创作 |
| **.lrtemplate** | struct | JSON-like | 易编辑 | 是(7.3-) | 否 | Lightroom 旧版 |
| **.dcp (DNG Profile)** | HSV + matrix | TIFF + binary | 编辑需 DNG PE | 是(Camera Profile) | 否 | 相机校准 |
| **Hald CLUT** | 3D RGB/HSV | PNG/JPG | 用图像软件 | 是(用户导入) | 否 | 快速风格迁移 |
| **CLF (Common LUT)** | 链式 | XML | 复杂,可读 | 有限 | **是(原生)** | ACES 工业管线 |
| **.look (Magic Bullet)** | 多层 | binary | 否 | 否 | 否 | Red Giant 套件 |
| **.nk (Nuke)** | 节点图 | 文本 | 易 | 否 | 有限 | Nuke 调色 |
| **ICC Profile** | matrix + LUT | binary | 否 | 有限 | 是 | 颜色管理 |

---

## 2. 商业 / 开源 LUT 提取工具

### 2.1 商业工具

| 工具 | 平台 | 核心思路 | LUT 导出 | 关键参考 |
|---|---|---|---|---|
| **3D LUT Creator** | macOS/Win | Grid Bending 手动调色 | ✅ .cube | [3dlutcreator.com](https://3dlutcreator.com) |
| **IWLTBAP LUT Generator** | macOS/Win | HALD identity → PS/LR 调色 → .cube | ✅ .cube (25/64) | [generator.iwltbap.com](https://generator.iwltbap.com) |
| **FilmConvert Nitrate** | PPro/AE/FCP/Avid/Resolve | 19 胶片模拟 + 6K 扫描 grain | ✅ 任意 LUT | [filmconvert.com](https://www.filmconvert.com) |
| **Color Finale 2 Pro** | FCPX (macOS) | 完整调色插件 | ✅ 自定义 grade → .cube | [docs.colorfinale.com](https://docs.colorfinale.com/docs/layers/luts) |
| **LUT Bakery** | Win/Mac | 自动分析参考图 | ✅ .cube | (演示视频) |
| **VSCO Film** | PS/Lr 插件 | 2 年研究 + Kodachrome 复刻 | 闭源 preset | [eng.vsco.co/reviving-kodachrome](https://eng.vsco.co/reviving-kodachrome) |
| **Imagen AI LUT Generator** | SaaS | 神经分析参考图 | ✅ .cube | [imagen-ai.com](https://imagen-ai.com/tools/lut-generator-from-image) |
| **Luminar Neo** | macOS/Win | 调色 + AI | ✅ 自定义 .cube | 文档 |
| **Capture One** | macOS/Win | .costyle 风格 | ✅ .costyle(私有) | [support.captureone.com](https://support.captureone.com) |
| **Pat David Film Emulation** | darktable 兼容 | 经典模拟套装 | ✅ Hald CLUT | 社区 |

**重要事实**:
- **Color Finale 不能直接导出 LUT**(旧版),但 **Color Finale 2 Pro 可以**(从 grade → .cube)
- **FilmConvert** 严格意义上是"胶片模拟",不是 LUT 提取工具,但可导出调整结果为 LUT
- **VSCO Film 2018** 起诉 PicsArt **reverse engineer 照片滤镜**(法律风险案例)

### 2.2 开源工具

| 项目 | 语言 | 核心思路 | 输出 | Star/活跃度 |
|---|---|---|---|---|
| **[bastibe/LUT-Maker](https://github.com/bastibe/LUT-Maker)** | Python (numpy + numba + scipy + Pillow) | image pairs → 16³ HaldCLUT PNG | PNG (Hald) | 中(13 commits) |
| **[oiao/clut](https://github.com/oiao/clut)** | Python (numpy + scipy) | HaldCLUT 加载/保存/fit CLI | Hald + npy + 应用 | 中(48 commits) |
| **[homm/color-filters-reconstruction](https://github.com/homm/color-filters-reconstruction)** | Python (Pillow) | 抗畸变 HALD5 + Instagram 重建 | HaldCLUT PNG | 中(53 commits) |
| **[savuori/haldclut_dt](https://github.com/savuori/haldclut_dt)** | Zig + SDL2 | darktable 配套,Hald 生成 | PNG (Hald) | 低(7 commits) |
| **[ozwaldorf/lutgen-rs](https://github.com/ozwaldorf/lutgen-rs)** | Rust (crate: lutgen) | 调色板 → Gaussian RBF 3D LUT | HaldCLUT | 高(活跃) |
| **[o-l-l-i/lut-maker](https://github.com/o-l-l-i/lut-maker)** | JS (WebGL) | GPU 加速 LUT 生成器 | PNG / cube | 中 |
| **[Skyfish1/lut-utility](https://github.com/Skyfish1/lut-utility)** | Python | Hald CLUT / Reshade / 批量 | .cube / PNG | 低(11 commits) |
| **[mikeboers/LUT-Convert](https://github.com/mikeboers/LUT-Convert)** | Python | Hald CLUT ↔ .cube | .cube | 中 |
| **[shadawck/lrjson](https://github.com/shadawck/lrjson)** | Python | .lrtemplate ↔ JSON | JSON | 中 |
| **[jedypod/ociogen](https://github.com/jedypod/ociogen)** | Python | OCIO config 生成 | .ocio | 中 |
| **OpenColorIO (ASWF)** | C++ / Python | 完整 .cube/.3dl/.clf 解析,bake | 全部格式 | 高(工业标准) |
| **darktable color lookup module** | C (in-tree) | Lab 空间 spline 插值 | 内部 CLUT | 高(主流软件) |
| **RawTherapee clutstore.cc** | C++ (in-tree) | vectorized CLUT apply | 内部 CLUT | 高 |
| **ImageMagick `-hald-clut`** | C (in-tree) | 任意图像软件编辑 HALD | PNG | 极高 |

**关键参考实现详细**:
- **bastibe/LUT-Maker**:`make_lut.py` 完整可读,< 200 行,核心常量:
  ```python
  LUT_CUBE_SIZE = 16
  LUT_IMAGE_SIZE = 64        # = 16²
  WEIGHT_FACTOR = 2
  BOUNDARY_WEIGHT_FACTOR = 5
  SMOOTHING_SIGMA = 1
  SUBSAMPLING = 5
  RGB2IDX = int(256 / LUT_CUBE_SIZE)  # = 16
  ```
  算法:source pixel → cube bin → 累加 target → 平均 → Gaussian smooth → `swapaxes(0, 2).reshape([64, 64, 3])` → PNG

- **oiao/clut**:`clutfit(*image_pairs)` 一行从 (in, out) → CLUT 实例;CLI `clut {apply, batch-apply, fit}`

- **homm/color-filters-reconstruction**:`./bin/generate.py` 生成 `hald.5.png` 抗畸变 identity

- **lutgen-rs 算法演进**:
  - v1: noise + nearest neighbor average(3 分钟)
  - v2: Gaussian sampling(3 秒)
  - v3: Shepard's Method / IDW inverse distance weighting(几百毫秒)
  - **v4: Gaussian RBF interpolation**(当前默认,快 + 高质量)
  - 支持 OKLab 色彩空间(感知线性,平均更准)

- **OCIO FileFormatIridasCube.cpp**:1D 和 3D 互斥,`sscanf` 严格解析,trim+lower each keyword

---

## 3. 逆向 LUT 的算法

### 3.1 单图风格提取 (HALD-based)

**代表**:IWLTBAP LUT Generator、LUT Bakery、3D LUT Creator

**输入**:
- 1 张目标风格参考图(graded)
- HALD identity image(N=8/16/25/64)

**流程**:
1. 生成 `hald:N identity.png` (边长 = N³ = 64 / 512 / 15625 / 262144)
2. 在 PS/LR/ACR/Camera Raw/darktable 中打开 identity,应用参考图的色彩曲线/HSL/Split Toning 等所有调整
3. 保存 modified identity(必须 lossless PNG 或 JPG 100%)
4. 工具逐像素对比原/改 identity → 直接读出 N×N×N 3D LUT
5. 输出 .cube (25³ 或 64³)

**关键限制**:
- **不能含** grain、vignette、watermark、scratches、gradient、局部 mask
- 任何非全局色彩变换都不能 capture
- 8-bit 限制 256³(实际 N=16 = 4096 entries)
- JPEG 压缩必须禁用(否则引入颜色伪影)

**优势**:
- 单图即可,无需图对
- 算法极简(O(N³) 像素对比)
- 速度快(IWLTBAP 几秒)
- 适合个人创作者快速复制风格

### 3.2 双图对训练 (Source/Target pairs)

**代表**:bastibe/LUT-Maker、oiao/clut、homm/color-filters-reconstruction、savuori/haldclut_dt

**输入**:
- source 目录:中性/原始图像(最好是 raw 转线性,8-bit PNG)
- target 目录:相同图像应用目标滤镜后
- 80+ 不同曝光/色域样本(关键)
- 必须像素对齐(EXIF orientation 修正 + ROI crop)

**算法**(bastibe 核心 11 个常量):
```python
LUT_CUBE_SIZE = 16
LUT_IMAGE_SIZE = 64
RGB2IDX = int(256 / LUT_CUBE_SIZE)  # 16

# 对每对 source/target:
# 1. EXIF orientation 修正
# 2. 中央裁剪对齐
# 3. resize 5x downsample (LANCZOS)
# 4. count_pixels(): for each (x, y):
#      ridx, gidx, bidx = (src - 8) // 17 + 1   # bin into 16×16×16
#      color_sum[ridx, gidx, bidx] += tgt[x, y]
#      color_count[ridx, gidx, bidx] += 1
# 5. generate_lut(): average color_sum / color_count
# 6. smooth_and_extrapolate_lut(): Gaussian sigma=1
# 7. lut_matrix.swapaxes(0, 2).reshape([64, 64, 3])  # 关键:R↔B
# 8. Image.fromarray(lut_image).save('lut.png', 'PNG')
```

**关键陷阱**:
- 源/目标像素**必须严格对齐**,否则 LUT 模糊
- 关闭**镜头校正、锐化、降噪**(否则引入非色彩变换)
- 黑像素(0,0,0)不计入(可能是 JPEG 压缩伪影)
- N=16 cube = 4096 bin,每个 bin 至少 5+ 像素(MIN_COLOR_SAMPLES=5),否则拒收

**优势**:
- 高精度(基于真实 raw 数据)
- 可处理 camera 内部 LUT / film simulation(暗角、tone curve 局部非线性)
- 已有成功案例:Fujifilm 胶片模拟(暗调、肤色)
- 适合暗调 / 高光精细控制

**劣势**:
- 80+ 图像对数据采集费时
- 算法复杂(需要 numba JIT / GPU)
- 必须严格控制源/目标环境(镜头、相机、曝光、白平衡)

### 3.3 网格弯曲 (Grid Bending, 手工)

**代表**:3D LUT Creator、darktable color lookup module(基于 color checker 24/49 色板)

**输入**:
- 24/49/更多色板的 source / target 颜色对
- 或直接编辑 RGB cube 上的网格节点

**算法**:
- 24 色 ColorChecker → 24 个 Lab 颜色对
- spline 插值完整 16³ cube
- darktable 支持用户拖动色板调整目标颜色

**优势**:
- 专家级精度,可针对肤色/天空/草地等局部精细控制
- 无需原始 raw 图像

**劣势**:
- 需要专业知识(色彩理论)
- 速度慢,完全手工
- 24 色板可能错过色域边缘

### 3.4 神经网络 LUT

**代表**:semchan/NLUT、MuLUT (2024)、Zeng 2020 PAMI (PolyU)

**核心论文**:
- Zeng 2020 "Learning Image-adaptive 3D LUTs for High Performance Photo Enhancement in Real-time"(IEEE PAMI)
- semchan/NLUT:"build a neural network to generate a stylized 3D LUT"
- MuLUT 2024:"universal method to construct multiple LUTs like a neural network"

**算法**:
- 神经网络(小型 CNN)输入参考图,输出 3D LUT 系数
- LUT 保持可解释(可导出 .cube)
- 推理快,训练慢
- 可学习**多个 LUT 链**(MuLUT)

**优势**:
- 训练后可实时应用
- 自适应图片内容
- 输出是标准 .cube,兼容所有 LUT 消费软件

**劣势**:
- 训练需要大数据集(数千图对)
- 黑盒,难解释
- PyTorch 依赖重

### 3.5 颜色对插值 (Snibgo sparse HALD)

**代表**:[im.snibgo.com/sphaldcl.htm](https://im.snibgo.com/sphaldcl.htm#procmod),ImageMagick `-process sparse_hald_clut`

**输入**:
- N×2 颜色列表(N 个 from 颜色 + 对应 N 个 to 颜色)
- 或两幅图采样得到的 from/to 像素

**算法**:
- 把 from/to 列表组合成 "transformation image"(Nx2)
- 用 Shepard's Method(IDW) / Voronoi / Gaussian RBF 插值
- 输入图像每个像素 → 找到 N 个 from 颜色中最接近的几个 → 加权平均 to 颜色

**优势**:
- 极快(Shepard 几百毫秒)
- 适合局部精确控制(用户标记关键色)
- snibgo 全套 IM 脚本可直接用

**劣势**:
- N 小(10-100)时色域覆盖不全
- 远端颜色 extrapolation 误差大
- 需要 ImageMagick 7 + process modules

### 3.6 实用对比

| 算法 | 输入 | 输出 | 速度 | 精度 | 适合 |
|---|---|---|---|---|---|
| **HALD-based** | 1 ref + HALD | .cube | 极快 | 中 | 个人创作者 |
| **Image-pair** | 80+ pairs | Hald PNG | 慢(分钟) | 高 | 胶片模拟 |
| **Grid Bending** | 手工拖点 | .cube | 慢(小时) | 极高 | 专家级 |
| **Neural 3D LUT** | 训练集 | .cube | 训练慢,推理快 | 高 | 商业级 |
| **Color-pair IDW** | N 颜色对 | Hald PNG | 快 | 中(取决于 N) | 局部精确 |

---

## 4. 逆向 LUT 所需的信息

### 4.1 必要信息

| 类别 | 必要信息 | 备注 |
|---|---|---|
| **来源素材** | 目标风格参考图 OR (source, target) 图对 | 至少 1 张,推荐 80+ |
| **LUT 维度** | 网格 size(17/25/33/64/65) | 决定精度 vs 文件大小 |
| **LUT 类型** | 1D only / 3D only / 1D+3D 组合 | .cube 不允许混合,.3dl 允许 |
| **色彩空间** | 输入/输出 RGB / HSV / Lab | 大多数工具假设 sRGB |
| **对齐信息** | EXIF orientation、ROI crop | 图像对方法必填 |
| **校准** | 关闭锐化、降噪、镜头校正 | 图像对方法必填 |
| **格式编码** | 整数 bit depth(8/10/12/16) | .3dl 通过 max 推算 |
| **DOMAIN_MIN/MAX** | 输入域 | 默认 [0, 1],HDR 可超 |

### 4.2 可选增强

| 类别 | 增强信息 | 价值 |
|---|---|---|
| **多图覆盖** | 80+ 不同曝光、色域、皮肤色 | LUT 在色域边缘准确 |
| **RAW 输入** | raw 转 16-bit TIFF | 避免 JPEG 压缩伪影 |
| **降采样** | 5x downscale(bastibe) | 抗锐化、抗噪点 |
| **目标尺寸** | 500×300 PNG(savuori) | 减少相机内部处理影响 |
| **Tone Curve 拆分** | R/G/B 独立曲线 | 保留 LrC 风格的色调分离 |
| **HSL 调整** | 8 色 hue/sat/lum 调整 | 保留 LrC 风格的核心调色 |
| **Grain / Vignette** | 单独参数(非 LUT) | 不适合 LUT,需独立导出 |
| **局部蒙版** | MaskGroupBasedCorrections | LrC 强大,非 LUT |

### 4.3 数据规模建议

| 用途 | 推荐规模 | 原因 |
|---|---|---|
| **个人创作者** | 1-3 张参考图 + HALD:N=8 (512×512) | 快速出效果 |
| **中级质量** | 10-30 张图对 + N=16 (4096 entries) | 色域覆盖 80% |
| **胶片模拟** | 80-200 张图对 + N=16 (4096) | bastibe 经验值 |
| **商业 LUT** | 200+ 张图对 + 神经训练 + N=25 (15625) | 精度 + 一致性 |
| **视频 LUT** | 10-50 张帧 + N=33 (35937) | Nuke 主流 size |

**色域覆盖技巧**:
- 包含纯白、纯黑、纯红/绿/蓝原色
- 包含 24 色 ColorChecker
- 包含皮肤色(多种肤色)
- 包含天空色(多种天气)
- 包含草地、树叶、水面
- 包含暗调、高光、阴影过渡区

---

## 5. 实施建议 — 适合 `lut-generator` 的方案

### 5.1 路线 A: HALD-based(快速,推荐)

**理由**:
- 单图输入,UX 简单
- 算法极简,Python 50 行可实现
- 与现有 `extract` 命令工作流吻合(用户给参考图 → 输出 LUT)
- 复用现有 numpy/Pillow 依赖

**实现**:
```python
# lut_generator/core/hald_extract.py
def extract_from_reference(reference_image_path, output_cube_path, cube_size=25):
    """从参考图反向提取 3D LUT。

    流程:
    1. 加载参考图 → RGB array
    2. 对每个 cube bin (R, G, B) 索引,在参考图中找最近像素
    3. 累加 → 平均 → 3D LUT
    4. 输出 .cube 文本
    """
    # 实现基于 lutgen-rs 的 Gaussian RBF 算法
    # 或 oiao/clut 的 clutfit
    pass
```

**CLI**:
```bash
lut-generator extract-style --reference movie_frame.png --output movie.cube --size 25
```

**依赖**:`Pillow`, `numpy`(已有)

**风险**:
- 单图色域覆盖不足,需要提示用户提供多张参考图(可加 `--multi-ref` 选项)

### 5.2 路线 B: Image-pair 训练(高精度,慢)

**理由**:
- 高精度,可处理局部非线性
- 适合 LUT-generator 当前"参考图"场景升级

**实现**:
- 参考 `bastibe/LUT-Maker`,需要 numba JIT(优化性能)
- 命令: `lut-generator train-lut --source-dir neutral/ --target-dir graded/ --output lut.png`
- 输出 Hald CLUT PNG(64×64 = 16³)
- 再用 `mikeboers/LUT-Convert` 转为 .cube

**依赖**:`numba`, `scipy.signal`, `tqdm`(较重)

**风险**:
- 用户需提供对齐的图对(普通创作者做不到)
- 80+ 张数据采集成本高
- 不适合 LUT-generator 当前"单图 reverse"UX

### 5.3 路线 C: Neural 3D LUT(研究型)

**理由**:
- 长期价值高,可与现有 `lut-generator` 的 `generate` 命令互补
- 输出仍是 .cube,兼容

**实现**:
- 参考 `semchan/NLUT`(PyTorch)
- 训练需要预录制的 (neutral, graded) 数据集(数百张)
- 推理命令:`lut-generator neural-lut --reference ref.png --output lut.cube`

**依赖**:`torch`, `torchvision`(非常重,可能不适合轻量 lut-generator_skill)

**风险**:
- PyTorch 100MB+ 依赖
- 训练 GPU 资源
- 通用模型 vs 风格特定模型,产品形态需决策

### 5.4 路线 D: 格式互转 + HALD 库(基础设施)

**理由**:
- 最稳,先有"互转能力",再谈"提取"
- 商业价值:LUT 仓库维护者、影楼工作流

**实现**:
- `.cube` ↔ `.3dl` ↔ `.xmp Creative Profile` ↔ `.lrtemplate` ↔ Hald CLUT
- 每个方向独立可测试
- 整合到现有 `extract / generate / transfer` 命令

**依赖**:现有即可

**风险**:
- 与现有提取/生成能力重叠
- 不解决"逆向 LUT"核心需求

### 5.5 综合建议(优先级排序)

| 优先级 | 路线 | 工作量 | 价值 | 推荐 |
|---|---|---|---|---|
| 🥇 1 | **A. HALD-based 单图提取** | 中(1-2 天) | 高 | ✅ **优先做** |
| 🥈 2 | **D. 格式互转** | 中(2-3 天) | 中 | ✅ 第二步 |
| 🥉 3 | **B. Image-pair 训练** | 高(3-5 天) | 中 | 视用户需求 |
| 4 | **C. Neural 3D LUT** | 极高(1-2 周) | 高 | 长期项目 |

**建议开发顺序**:
1. **第一周**:实现路线 A(单图 HALD 提取 → .cube)
2. **第二周**:实现路线 D(.cube ↔ .3dl ↔ Hald 互转)
3. **第三周起**:看用户反馈决定是否做路线 B(高复杂度)或路线 C(高依赖)

---

## 6. 参考文献 & 链接

### 6.1 官方规范

- [Adobe Cube LUT Specification 1.0 (PDF)](https://kono.phpage.fr/images/a/a1/Adobe-cube-lut-specification-1.0.pdf) — IRIDAS + Adobe, September 2013
- [Wikidata Q105850066 - Cube LUT format](https://www.wikidata.org/wiki/Q105850066) — 镜像 + 元数据
- [DNG Specification 1.4.0.0 (PDF)](https://www.kronometric.org/phot/processing/DNG/dng_spec_1.4.0.0.pdf) — Adobe, June 2012, 133 KB
- [Adobe Camera Raw namespace (crs)](https://developer.adobe.com/xmp/docs/xmp-namespaces/crs) — Adobe Developer
- [CLF — Common LUT Format (ACES)](https://docs.acescentral.com/clf/introduction) — Academy Software Foundation

### 6.2 字段表 / 字典

- [exiftool XMP.html #crs](https://exiftool.org/TagNames/XMP.html#crs) — Phil Harvey, 完整 426 KB XMP 字段表
- [EXIFTool 论坛 Boyd XMP-crs 样本](https://exiftool.org/forum/index.php?topic=11258.0) — 真实 Creative Profile 样本
- [DCP Files (Sandy McGuffog)](https://dcptool.sourceforge.net/DCP%20FIles.html) — DCP 完整结构 + 8 步处理管线

### 6.3 商业工具

- [3D LUT Creator](https://3dlutcreator.com) — Grid Bending
- [IWLTBAP LUT Generator](https://generator.iwltbap.com) — HALD-based
- [FilmConvert](https://www.filmconvert.com) — 19 film stocks, 6K grain
- [Color Finale 2 Pro](https://docs.colorfinale.com/docs/layers/luts) — FCPX
- [Imagen AI LUT Generator](https://imagen-ai.com/tools/lut-generator-from-image) — 神经
- [VSCO Engineering: Reviving Kodachrome](https://eng.vsco.co/reviving-kodachrome) — 2 年复刻研究

### 6.4 开源库

| 项目 | URL | 重点 |
|---|---|---|
| bastibe/LUT-Maker | https://github.com/bastibe/LUT-Maker | image pairs → HaldCLUT |
| oiao/clut | https://github.com/oiao/clut | clutfit() + CLI |
| homm/color-filters-reconstruction | https://github.com/homm/color-filters-reconstruction | Instagram filter reverse |
| savuori/haldclut_dt | https://github.com/savuori/haldclut_dt | Zig + darktable |
| ozwaldorf/lutgen-rs | https://github.com/ozwaldorf/lutgen-rs | Rust, Gaussian RBF, 4 个算法版本 |
| o-l-l-i/lut-maker | https://github.com/o-l-l-i/lut-maker | WebGL GPU |
| Skyfish1/lut-utility | https://github.com/Skyfish1/lut-utility | Hald/Reshade/批量 |
| mikeboers/LUT-Convert | https://github.com/mikeboers/LUT-Convert | Hald ↔ .cube |
| shadawck/lrjson | https://github.com/shadawck/lrjson | .lrtemplate ↔ JSON |
| OpenColorIO (ASWF) | https://github.com/AcademySoftwareFoundation/OpenColorIO | 工业级 C++ 解析 |
| hpd/CLF | https://github.com/hpd/CLF | Common LUT Format |
| jedypod/ociogen | https://github.com/jedypod/ociogen | OCIO config 生成 |
| ImageMagick `-hald-clut` | https://imagemagick.org | 内置,任意图像软件编辑 |

### 6.5 算法 / 教程

- [Snibgo: Editing with hald cluts](https://im.snibgo.com/edithald.htm) — IM 完整 HALD 工作流
- [Snibgo: Sparse hald cluts](https://im.snibgo.com/sphaldcl.htm#procmod) — Shepard / Voronoi / IDW
- [pixls.us: technical details of LUTs](https://discuss.pixls.us/t/technical-details-of-luts/51629) — IM 开发者视角
- [HaldCLUT module in darktable](https://discuss.pixls.us/t/hald-clut-module-in-darktable/1735) — patdavid 模拟套装
- [lut.sh/lore](https://lut.sh/lore) — lutgen-rs 4 个算法演进史
- [Quelsolaar CLUT technology](https://www.quelsolaar.com/technology/clut.html) — Eskil Steenberg 原始概念
- [Tetrahedral vs Trilinear LUT Interpolation](https://www.alestemple.net/blog/tetrahedral-vs-trilinear-lut-interpolation.html) — Adobe vs Nuke interpolation 差异
- [darktable color lookup module docs](https://docs.darktable.org/usermanual/4.6/en/module-reference/processing-modules/color-look-up-table) — Lab 空间 spline

### 6.6 神经 / 学术

- Zeng 2020 (PolyU):[Learning Image-adaptive 3D LUTs](https://www4.comp.polyu.edu.hk/~cslzhang/paper/PAMI_LUT.pdf) — IEEE PAMI
- semchan/NLUT:GitHub repo — Neural 3D LUT for video
- MuLUT 2024:[Toward DNN of LUTs](https://www.computer.org/csdl/journal/tp/2024/12/10530442/1WWdXQI2oda) — 多 LUT 链
- [Emergent Mind: Learnable 3D LUT](https://www.emergentmind.com/topics/learnable-3d-lookup-table-lut) — 综述
- [3D LUT Interpolation (ACES)](https://community.acescentral.com/uploads/default/original/2X/5/518c5ede1ca11c4a7e13f9c7350e2228bb8762c7.pdf) — JD Vandenberg 2017

### 6.7 视频 / 社区

- [Larry Jordan: 3D LUT Creator First Look](https://larryjordan.com/articles/first-look-3d-lut-creator-absolute-color-magic-for-stills)
- [Reddit Filmmakers: Image to LUT generator](https://www.reddit.com/r/Filmmakers/comments/1o7ia2j/got_something_new_an_image_to_lut_generator_no)
- [DPReview: Eterna LUT for darktable (bastibe)](https://www.dpreview.com/forums/threads/eterna-lut-for-darktable-made-with-bastibes-lut-maker.4724639)
- [Jonny Elwyn on FilmConvert (Jonny Elwyn)](http://jonnyelwyn.co.uk/film-and-video-editing/creating-a-real-film-look-with-filmconverts-premiere-plugin/)
- [cinem8: Free Online LUT Converter](https://cinem8.co/pages/free-online-lut-converter-65x-to-33x-to-17x) — 65↔33↔17

### 6.8 上一轮调研(本项目)

- `D:\workspace\lut-generator\XMP_LRTEMPLATE_RESEARCH.md` — LrC 14 格式调研,17.7 KB,27 链接
- `lut-generator_server\README.md` — 当前 README 包含 .cube / .xmp / .lrtemplate / .xmpcreative 用法

---

**报告作者**:Hermes (minimax, MiniMax-M3)
**报告版本**:v1.0
**生成日期**:2026-06-15
**字数**:~22 KB

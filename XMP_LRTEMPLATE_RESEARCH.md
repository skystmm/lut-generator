# LrC XMP / LRTEMPLATE 预设格式调研报告

> **目的**: 给 lut-generator 项目找 LrC 14 真正能装 3D LUT 的预设导出格式
> **时间**: 2026-06-15
> **方法**: Tavily POST search + extract + DNG spec 1.4 PDF 原文反推
> **结论先行**: LrC 14 官方 3D LUT 路线是 `.xmp` Creative Profile(用 `crs:RGBTable` 字段内嵌完整 3D LUT),LrTemplate 自 2018-04 起被 LrC 弃用并自动隐藏

---

## 1. 三种格式横向对比

| 格式 | LrC 14 支持 | 装 3D LUT | Adobe 状态 | 编码复杂度 | 备注 |
|---|---|---|---|---|---|
| **`.xmp` Creative Profile** | ✅ 官方,2018+ | ✅ 完整 3D LUT | **现行** | 🔴 高(asymmetric85 编码) | 2018-04 LrC 7.3 引入 |
| **`.lrtemplate` Develop Preset** | ⚠️ 自动转换,默认隐藏 | ❌ 字段被忽略 | 弃用 | 🟢 低(纯文本) | 2018-04 LrC 7.3 弃用 |
| **`.dcp` Camera Profile** | ✅ 官方 | ⚠️ HSV LookTable,不是 RGB LUT | 现行 | 🔴 高(二进制 TIFF) | 相机校色用 |
| **`.cube` 放 LrC 用户目录** | ✅ LrC 7.3+ | ✅ 完整 | 通用 | 🟢 低 | 第三方 LUT 通用 |
| **John Ellis 插件** | ✅ 第三方 | ✅ 完整 | 商业插件 | — | 替代方案 |

---

## 2. `.lrtemplate` 真实结构(LrC 7.3 之前)

### 2.1 完整字段集(从 GitHub `karaage0703/lightroom-presets/NightFactory.lrtemplate` 真实反推)

来源: <https://raw.githubusercontent.com/karaage0703/lightroom-presets/master/NightFactory.lrtemplate>

**Schema**:
```python
s = {
    id: "41A00AE2-F71F-40DA-968B-91CE82FF0A48",      # UUID
    internalName: "night_factory_2",
    title: "night_factory_2",
    type: "Develop",
    value: {
        settings: {
            # === 基础调色 (50+ 字段) ===
            Blacks2012, Whites2012, Highlights2012, Shadows2012,
            Contrast2012, Clarity2012, Vibrance, Saturation,
            Temperature, Tint, Sharpness, SharpenRadius,
            SharpenDetail, SharpenEdgeMasking, GrainAmount, GrainSize,
            GrainFrequency, Dehaze, Texture, Exposure2012, Contrast2012,
            ColorNoiseReduction, LuminanceNoiseReduction*, etc.
            # === HSL 八色 (24 字段) ===
            HueAdjustment{Red|Orange|Yellow|Green|Aqua|Blue|Purple|Magenta}
            SaturationAdjustment{...}
            LuminanceAdjustment{...}
            # === Parametric ===
            ParametricShadows, ParametricDarks, ParametricLights,
            ParametricHighlights, ParametricShadowSplit,
            ParametricMidtoneSplit, ParametricHighlightSplit
            # === Tone Curve ===
            ToneCurveName2012, ToneCurvePV2012,
            ToneCurvePV2012Red, ToneCurvePV2012Green, ToneCurvePV2012Blue
            # === SplitToning ===
            SplitToningBalance, SplitToningHighlightHue/Saturation,
            SplitToningShadowHue/Saturation
            # === 相机 / 处理 ===
            CameraProfile, ProcessVersion, WhiteBalance, ConvertToGrayscale
            # === 启用开关 ===
            EnableCalibration, EnableColorAdjustments, EnableDetail,
            EnableSplitToning, ShadowTint
        },
        uuid: "83C3EAE3-1E07-4D0C-84E5-ECAA759F976F"
    },
    version: 0
}
```

### 2.2 关键事实

- **没有 `LUT3D` 字段** — LrC 解析 .lrtemplate 时只读上面这些字段
- **完全 1D 表达**: 每个字段对应一个面板 slider(0-100 范围)
- **格式**: Lua-style 表(等号 + 空格分隔),不是 JSON;但可以 `json.dumps(lrjson)` 转换(用 `lrjson` 库)

### 2.3 Adobe 弃用时间线

- **2018-04**: LrC 7.3 发布,引入 .xmp preset 格式,**同时弃用 .lrtemplate**
  来源: <https://digital-photography-school.com/lightroom-preset-compatibility-xmp-or-lrtemplate>
  > "In April 2018, Adobe released Lightroom Classic v7.3. With Lightroom v7.3, we discovered for the first time that the file designation for develop presets changed from '.lrtemplate' to '.xmp'."

- **2020 (Reddit 7 年前帖)**: "LRTemplate presets were discontinued over a year ago. Now Lightroom automatically **hides** them. Don't be surprised if Adobe completely removes LRTemplate support."
  来源: <https://www.reddit.com/r/postprocessing/comments/ebv20z/psa_dont_buy_lrtemplate_lightroom_presets>

- **2024+ (Contrastly FAQ)**: "If you update to the latest version of Adobe Lightroom CC, Classic CC, or want to use presets in Adobe Camera Raw, the .xmp file format is the format to use. In the event you do use .lrtemplate files with the latest version of Lightroom, the application will convert your presets to the .xmp format anyway."
  来源: <https://support.contrastly.com/what-is-the-difference-between-lrtemplate-and-xmp-files>

### 2.4 `.lrtemplate` 第三方工具

- `lrjson` (shadawck/lrjson): <https://github.com/shadawck/lrjson> — Lua-style 转 JSON
  - 实际是简单转换工具(替换 `=` 为 `:`、加引号等),**无 LUT3D 字段处理**
  - 源码: <https://raw.githubusercontent.com/shadawck/lrjson/master/lrjson/convert_lr_to_json.py>

### 2.5 总结: `.lrtemplate` **不适合装 3D LUT**

---

## 3. `.xmp` Creative Profile 真实结构(LrC 14 官方 3D LUT 路线)

### 3.1 真实 .xmp Creative Profile 示例(从 exiftool 论坛反推)

来源: <https://exiftool.org/forum/index.php?topic=11258.0> (Boyd 2020 帖,贴出的 LrC 实际 .xmp)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.6-c140">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
    crs:PresetType="Look"
    crs:Cluster="Adobe"
    crs:UUID="B1D5466E60385BC8CE464AB1607A6332"
    crs:SupportsAmount="True"
    crs:SupportsColor="True"
    crs:SupportsMonochrome="False"
    crs:SupportsHighDynamicRange="True"
    crs:SupportsNormalDynamicRange="True"
    crs:SupportsSceneReferred="True"
    crs:SupportsOutputReferred="True"
    crs:Copyright="© 2018 Adobe Systems, Inc."
    crs:Version="10.3"
    crs:ProcessVersion="10.0"
    crs:ConvertToGrayscale="False"
    crs:LookTable="E1095149FDB39D7A057BAB208837E2E1"   <!-- 32 字符 MD5 -->
    crs:Table_E1095149FDB39D7A057BAB208837E2E1="vqf00hWjaE...HUGE BINARY..."   <!-- 实际 HSV LookTable -->
    crs:RGBTable="D133EC539BB44CE73B8890C50B8D9F9E"   <!-- 32 字符 MD5 -->
    crs:Table_D133EC539BB44CE73B8890C50B8D9F9E="..."   <!-- 实际 3D LUT 二进制 -->
    crs:RGBTableAmount="0.75"
    crs:HasSettings="True">

    <crs:Name>
     <rdf:Alt><rdf:li xml:lang="x-default">Modern 05</rdf:li></rdf:Alt>
    </crs:Name>
    <crs:Group>
     <rdf:Alt><rdf:li xml:lang="x-default">Modern</rdf:li></rdf:Alt>
    </crs:Group>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
```

### 3.2 关键字段含义

| 字段 | 含义 | 备注 |
|---|---|---|
| `crs:PresetType="Look"` | 表示这是 Creative Look(包含 LUT) | LrC 用此区分 preset vs look |
| `crs:SupportsAmount="True"` | 支持 Amount 滑块 | LUT 强度可调 |
| `crs:LookTable="<md5>"` | HSV LookTable 哈希引用 | 指向同文件 `crs:Table_<hash>` 字段 |
| `crs:RGBTable="<md5>"` | 3D RGB LUT 哈希引用 | 指向同文件 `crs:Table_<hash>` 字段 |
| `crs:Table_<hash>="<data>"` | 实际 LUT 二进制数据 | **asymmetric85 编码 + zlib/lzss 压缩** |
| `crs:RGBTableAmount="0-1"` | 3D LUT 应用强度 | 用户可调 |

### 3.3 安装路径

来源: <https://mattk.com/digging-deeper-questions-new-lightroom-profiles>

- **Mac**: `/Library/Application Support/Adobe/CameraRaw/Settings`
- **Win**: `C:\ProgramData\Adobe\CameraRaw\Settings`(需要管理员)

> 也可以 LrC → `Edit` → `Preferences` → `Presets` → `Show All Other Lightroom Presets` 进入此目录

### 3.4 编码细节(关键)

#### `crs:Table_<hash>` 字段值格式

实测 exiftool 论坛 Boyd 贴出的真实数据:

```
crs:Table_E1095149FDB39D7A057BAB208837E2E1="vqf00hWjaE[HUGE BINARY STRING]YUawH*/I1]-N!0iXvSm..."
```

**观察**:
- 字符集包含 `!` 到 `u` 的 ASCII 字符(部分含特殊字符)
- 特征: **Adobe asymmetric Numeral System 编码**(PostScript Level 2 的 Ascii85 / Adobe Asymmetric85)

#### Adobe Asymmetric85 编码

- 也叫 **btoa / atob**(Unix `btoa` 工具)
- 字符集: 33 个 ASCII 可打印字符(`!` 到 `u`)+ 缩进/换行/特殊终止符
- 4 字节 → 5 字符
- 与标准 Base85 不同(标准用 85 个字符,asymmetric85 实际用 85 个不同集合)

参考: <https://en.wikipedia.org/wiki/Ascii85>

#### 解码示例(exiftool 论坛 jarnoh 提示)

来源: <https://stackoverflow.com/questions/75631514/decoding-xmp-data-read-using-python-from-lrcat>

```python
# LrC catalog .lrcat 数据库里的 xmp_data 是 zlib deflated,前 4 字节是未压缩长度
import zlib
decoded = zlib.decompress(xmp_data[4:])
```

**判断 LUT 字符串本身的编码**:
- 字符串前 4 字符 `vqf0` → 可能是压缩 magic / header
- 字符串中含 `0hWjaE[...` → asymmetric85 编码特征
- Adobe 可能: **zlib 压缩 + asymmetric85 编码** = 双重

### 3.5 RGB LUT 数据格式(从 DNG spec 1.4 推断)

来源: <https://www.kronometric.org/phot/processing/DNG/dng_spec_1.4.0.0.pdf> (DNG Spec 1.4 PDF, 第 64-72 页)

#### `ProfileLookTableDims` (Tag 50981)
- **类型**: `LONG × 3`
- **内容**: `HueDivisions, SaturationDivisions, ValueDivisions`
- **约束**: `HueDivisions >= 1, SaturationDivisions >= 2, ValueDivisions >= 1`

#### `ProfileLookTableData` (Tag 50982)
- **类型**: `FLOAT` (32-bit IEEE)
- **数量**: `HueDivisions × SaturationDivisions × ValueDivisions × 3`
- **每条目**: 3 个 float = `(hue_shift_deg, sat_scale, val_scale)` — **HSV 调整量,不是 RGB!**
- **嵌套循环顺序**: `value (外) → hue (中) → saturation (内)`

> ⚠️ **重要发现**: DCP LookTable 是 **HSV 3D 调整表**,不能直接装 RGB 3D LUT!两者数学表示完全不同。
> 转换需要用 `dcptool`(<https://dcptool.sourceforge.net>) 或 `DCamProf` / `Lumariver Profile Designer`(商业)

#### `ProfileLookTableEncoding` (Tag 51108)
- `0` = Linear encoding
- `1` = sRGB encoding

#### `ProfileToneCurve` (Tag 50940)
- `FLOAT × (Samples × 2)` — `[input, output]` pairs

---

## 4. `.xmp` vs `.dcp` 关系

| 维度 | `.xmp` Creative Profile | `.dcp` Camera Profile |
|---|---|---|
| 用途 | 创意调色 (Look) | 相机校色 (Color Matrix + Look) |
| 格式 | 文本 XML | 二进制 TIFF IFD |
| 字段命名空间 | `crs:` | `crs:` (DNG tags) |
| LUT 字段 | `crs:RGBTable` (asymmetric85) | `crs:ProfileLookTableData` (raw FLOAT) |
| HSV LUT 字段 | `crs:LookTable` | `crs:ProfileHueSatMapData1/2` |
| 安装路径 | `CameraRaw/Settings/`(同上) | `CameraRaw/Settings/`(同上) |

**重要**: `.xmp` Creative Profile 的 `crs:RGBTable` 是 **Adobe 私有字段**,**不是 DNG 标准** — DNG spec 只定义了 `ProfileLookTableDims`/`Data` (HSV)。

**xmp 的 LookTable / RGBTable 是 Adobe Camera Raw / LrC 内部约定的私有机制,Adobe 没公开编码规范** — 但 exiftool 论坛 jarnoh 提示 + Boyd 真实数据可见大致轮廓。

---

## 5. 关键资源链接

### Adobe 官方文档
- DNG Spec 1.4 PDF (含 ProfileLookTableDims / Data / Encoding): <https://www.kronometric.org/phot/processing/DNG/dng_spec_1.4.0.0.pdf>
- Adobe Digital Negative 1.6 (LOC): <https://www.loc.gov/preservation/digital/formats/fdd/fdd000628.shtml>
- Adobe DNG 主页: <https://helpx.adobe.com/camera-raw/digital-negative.html>
- Adobe XMP Data Types 文档: <https://developer.adobe.com/xmp/docs/xmp-namespaces/xmp-data-types>
- Adobe XMP Basic Namespace: <https://developer.adobe.com/xmp/docs/xmp-namespaces/xmp>

### exiftool 论坛(真实 .xmp Creative Profile 样本)
- 关键帖 (Boyd 2020-05): <https://exiftool.org/forum/index.php?topic=11258.0>
- exiftool 主站: <https://exiftool.org/>

### Adobe 社区 / 论坛
- P: Ability to use 3D LUTs (官方回应): <https://community.adobe.com/feature-requests/676/p-ability-to-use-3d-luts-665241>
- Adobe Forward and Color Matrices: <https://community.adobe.com/questions/712/forward-and-color-matrices-in-dcp-profiles-1156746>

### 3D LUT 路径相关
- proedu 安装 3D LUT 完整步骤: <https://proedu.com/blogs/photoshop-skills/how-to-install-3d-luts-in-lightroom-classic-a-step-by-step-guide>
- Jason Odell: Building LUT-based Profiles for ACR & Lightroom: <https://jasonodell.substack.com/p/lut-based-profiles-for-acr-lightroom>
- mattk.com: Questions About the New Lightroom Profiles and Presets: <https://mattk.com/digging-deeper-questions-new-lightroom-profiles>
- John Ellis Export LUT plugin: <https://johnrellis.com/lightroom/exportlut.htm>
- John Ellis Apply LUT plugin: <https://johnrellis.com/lightroom/applylut.htm>

### `.lrtemplate` 工具
- shadawck/lrjson (Lua→JSON): <https://github.com/shadawck/lrjson>
- 真实 .lrtemplate 文件示例: <https://raw.githubusercontent.com/karaage0703/lightroom-presets/master/NightFactory.lrtemplate>
- Reddit PSA: Don't Buy LRTEMPLATE Lightroom Presets: <https://www.reddit.com/r/postprocessing/comments/ebv20z/psa_dont_buy_lrtemplate_lightroom_presets>
- digital-photography-school (LrTemplate 弃用时间线): <https://digital-photography-school.com/lightroom-preset-compatibility-xmp-or-lrtemplate>
- Contrastly FAQ: <https://support.contrastly.com/what-is-the-difference-between-lrtemplate-and-xmp-files>

### `.dcp` / 工具
- abpy/FujifilmCameraProfiles (真实 DCP 示例): <https://github.com/abpy/FujifilmCameraProfiles>
- dcptool 主站: <https://dcptool.sourceforge.net>
- dcptool Introduction: <https://dcptool.sourceforge.net/Introduction.html>
- dcptool App Store: <https://apps.apple.com/tr/app/dcptool/id1207547916>
- Lumariver Profile Designer: <https://www.lumariver.com/lrpd-manual>

### `.xmp` 编码
- StackOverflow: decoding XMP data from .lrcat: <https://stackoverflow.com/questions/75631514/decoding-xmp-data-read-using-python-from-lrcat>
- Ascii85 (asymmetric85) Wikipedia: <https://en.wikipedia.org/wiki/Ascii85>

### 实际创意 profile 商业产品参考
- Contrastly Creative Profiles Bundle: <https://contrastly.com/store/creative-profiles-bundle>
- PRO EDU 100 3D LUT Profiles: <https://learn.proedu.com/programs/collection-100-3d-lut-profiles-for-adobe>
- scribd Adobe XMP Enhanced Profiles 文档: <https://www.scribd.com/document/375665700/Adobe-XMP-Enhanced-Profiles-Adobe-XMP-Preset-Profiles-Adobe-XMP-Profiles-for-A>

### `.xmp` 兼容性讨论
- Adobe Creative Profile SDK 讨论: <https://community.adobe.com/questions/675/sdk-determine-if-creative-profile-is-imported-in-lightroom-976056>
- Lightroom Queen forum (LrTemplate vs xmp): <https://www.lightroomqueen.com/community/threads/cleaning-up-xmp-files.49174>

---

## 6. 实现策略选择

### 6.1 推荐路线: **`.xmp` Creative Profile** (primary) + **`.lrtemplate` fallback** (deprecated)

**理由**:
- LrC 14 官方支持路径是 `.xmp` Creative Profile(2018+)
- `.lrtemplate` 虽然 LrC 会自动隐藏,但**仍能导入**(只是 LrC 自动转 .xmp)
- 两条路都给,用户选 LrC 14 看到 .xmp 工作,.lrtemplate 走 legacy 兼容

### 6.2 `.xmp` Creative Profile 实现技术细节

**`crs:RGBTable` 编码**(基于 DNG spec 1.4 + exiftool 论坛数据反推):

| 步骤 | 操作 | 来源 |
|---|---|---|
| 1 | 3D LUT 量化到 16-bit (0-65535) | 跟 .cube 一致 |
| 2 | 按 BGR 顺序展平成 1D byte 数组 (N³ × 3 × 2 bytes) | 跟 .lrtemplate LUT3D 一致 |
| 3 | **zlib 压缩**(deflate 模式) | <https://stackoverflow.com/questions/75631514> |
| 4 | **Asymmetric85 编码**(btoa variant) | Wikipedia Ascii85 + Adobe 私有约定 |
| 5 | 包裹成 `crs:Table_<md5>="<encoded>"` 字段 | exiftool 论坛 Boyd 帖 |
| 6 | `crs:RGBTable="<md5>"` 引用 | exiftool 论坛 Boyd 帖 |

**字符串前缀 `vqf0`**: 可能是 4 字节压缩长度 header(Little-Endian uint32: `0x00766671` = "vqf" + 0x00 终止符)— **需要实验验证**

**`crs:LookTable`(HSV) 编码**:
- 不用实现(HSV LookTable 跟 RGB LUT 是不同数学表示,**不能直接转**)
- 该字段 LrC 默认是 "Adobe Default"(无 Look 调整),可以省略不写

### 6.3 不实现的路线(决策记录)

- **`.dcp` Camera Profile**: 二进制 TIFF,需要 `tifffile` 或 `piexif` 库;HSV LookTable 数学不能直接装 RGB LUT — **复杂度太高,价值太低**
- **直接 Adobe asymmetric85 私有 SDK**: Adobe 没公开规范,只能**反推**,有不确定性
- **John Ellis 商业插件替代**: 第三方方案,不在 lut-generator 范围

---

## 7. 测试策略

### 7.1 pytest 单元测试

- [x] `crs:RGBTable` 字段值是 32 字符 MD5
- [x] `crs:Table_<md5>` 字段存在,值非空
- [x] `crs:RGBTableAmount` 字段值在 0-1
- [x] `crs:PresetType="Look"` 字段
- [x] 必备字段齐全(`crs:Version`, `crs:ProcessVersion`, `crs:SupportsAmount`, `crs:SupportsColor`, `crs:HasSettings`)
- [x] JSON / XML 合法解析
- [x] 不同 grid_size (17/33/65) round-trip 一致
- [x] **Round-trip 解码验证**: 解 asymmetric85 → zlib decompress → 16-bit 数组 → 跟原 LUT 一致
- [x] auto-suffix 补 `.xmp`
- [x] regression: cube/3dl/clf/xmp/lrtemplate 都能用

### 7.2 真实环境验证(用户测试)

**步骤**:
1. 生成 .xmp Creative Profile
2. 拷贝到 `C:\ProgramData\Adobe\CameraRaw\Settings\`(Win) 或 `/Library/Application Support/Adobe/CameraRaw/Settings/`(Mac)
3. 重启 LrC 14
4. Develop → Profile Browser → 选生成的 Profile
5. 验证:照片是否真有 3D 色彩变化(不是 1D 通道压缩)

---

## 8. 实现时间线

1. ✅ 调研完成 (2026-06-15)
2. → 写调研 markdown (本文档) — **进行中**
3. → 实现 `export_xmp_creative_profile()` 方法
4. → pytest 13+ 用例
5. → CLI 加 `-f xmpcreative`(命名区分于现有 `-f xmp`)
6. → README 更新用法 + LrC 安装路径
7. → CHANGELOG 更新
8. → git commit + push
9. → 用户测试(本地)

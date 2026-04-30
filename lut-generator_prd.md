# LUT Generator - 产品需求文档 (PRD)

**文档版本**: v1.0  
**创建日期**: 2026-04-13  
**项目 ID**: 【图片分析风格生成 LUT 工具_标准版_20260413153500】

---

## 1. 产品概述

### 1.1 产品定位
LUT Generator 是一款专业的色彩分析工具，通过分析参考图片的色彩特征，生成标准的 3D LUT (.cube 格式)，用于视频/图像后期调色的色彩风格迁移。

### 1.2 目标用户
- 影视后期调色师
- 摄影师
- 视频创作者
- 色彩研究人员

### 1.3 核心价值
- **自动化**: 无需手动调色，自动分析图片色彩特征
- **标准化**: 输出行业标准的 .cube 格式 LUT 文件
- **灵活性**: 支持多精度输出，适配不同应用场景
- **可复用**: 一次分析，多次应用，保持色彩风格一致

---

## 2. 功能定义

### 2.1 核心功能

#### F1: 单图分析
- 上传单张参考图片
- 自动提取色彩统计特征
- 生成对应的 3D LUT 文件

#### F2: 多图分析
- 上传多张参考图片（批量）
- 计算平均色彩特征
- 生成综合风格的 3D LUT 文件

#### F3: 色彩特征提取
- 分析图片的色彩分布
- 提取亮度、饱和度、色相统计信息
- 计算色彩均值和标准差（Lab 空间）

#### F4: LUT 生成
- 基于 Reinhard 色彩迁移算法
- 支持 3 种精度等级：17³ / 33³ / 65³
- 输出标准 .cube 格式文件

#### F5: 预览对比
- 提供应用 LUT 前后的效果预览
- 支持并排对比查看

### 2.2 辅助功能

#### F6: 文件管理
- 保存历史分析记录
- 支持 LUT 文件导出/导入

#### F7: 参数配置
- 可调整色彩迁移强度
- 可设置输出精度
- 可配置输出路径

---

## 3. 输入输出规范

### 3.1 输入

| 类型 | 格式 | 要求 | 说明 |
|------|------|------|------|
| 参考图片 | JPG, PNG, TIFF, WEBP | sRGB 色彩空间 | 单张或多张 |
| 精度选择 | 17 / 33 / 65 | 默认 33 | LUT 维度 |
| 迁移强度 | 0.0 - 1.0 | 默认 1.0 | 色彩迁移程度 |

### 3.2 输出

| 类型 | 格式 | 说明 |
|------|------|------|
| LUT 文件 | .cube | 标准 3D LUT 文件 |
| 分析报告 | .json | 色彩特征统计数据 |
| 预览图 | PNG | 应用 LUT 前后对比 |

### 3.3 .cube 文件格式示例
```
TITLE "LUT_Generator_20260413"
LUT_3D_SIZE 33

0.000000 0.000000 0.000000
0.031250 0.000000 0.000000
...
1.000000 1.000000 1.000000
```

---

## 4. 使用流程

### 4.1 基础流程

```
1. 启动工具
   ↓
2. 选择参考图片（单张/多张）
   ↓
3. 配置参数（精度、强度）
   ↓
4. 执行分析
   ↓
5. 预览效果
   ↓
6. 导出 LUT 文件
```

### 4.2 命令行使用示例

```bash
# 单图分析
python -m lut_generator analyze \
  --input reference.jpg \
  --output style_lut.cube \
  --size 33

# 多图分析
python -m lut_generator analyze \
  --input ./references/ \
  --output style_lut.cube \
  --size 33 \
  --batch

# 带预览
python -m lut_generator analyze \
  --input reference.jpg \
  --output style_lut.cube \
  --preview \
  --preview-input test.jpg
```

### 4.3 API 使用示例

```python
from lut_generator import LUTGenerator

# 初始化
generator = LUTGenerator(lut_size=33)

# 单图分析
lut = generator.analyze_image("reference.jpg")

# 多图分析
lut = generator.analyze_images(["ref1.jpg", "ref2.jpg", "ref3.jpg"])

# 导出 LUT
lut.export("output.cube")

# 应用 LUT 到图片
generator.apply_lut("input.jpg", lut, "output.jpg")
```

---

## 5. 非功能需求

### 5.1 性能要求
- 单图分析时间 < 5 秒（1080p 图片）
- 多图分析（10 张）< 30 秒
- LUT 导出时间 < 1 秒

### 5.2 精度要求
- 色彩计算精度：浮点 32 位
- Lab 空间转换误差 < 0.01
- LUT 插值精度：三线性插值

### 5.3 兼容性
- Python 3.11+
- 支持 Windows / macOS / Linux
- 兼容主流调色软件（DaVinci Resolve, Premiere Pro, Final Cut Pro）

### 5.4 可扩展性
- 支持未来添加其他色彩迁移算法
- 支持自定义 LUT 格式输出

---

## 6. 验收标准

### 6.1 功能验收
- [ ] 单图分析功能正常
- [ ] 多图分析功能正常
- [ ] 三种精度 LUT 均可生成
- [ ] .cube 文件格式符合标准
- [ ] 预览功能正常

### 6.2 质量验收
- [ ] 单元测试覆盖率 > 80%
- [ ] 无严重 Bug
- [ ] 代码符合 PEP8 规范
- [ ] 文档完整

---

## 7. 开发计划

| 阶段 | 周期 | 交付物 |
|------|------|--------|
| 阶段 1: 核心算法 | 第 1 周 | Reinhard 算法实现 + 单元测试 |
| 阶段 2: LUT 生成 | 第 2 周 | 3D LUT 生成模块 + 精度配置 |
| 阶段 3: 批量处理 | 第 3 周 | 多图分析 + 平均算法 |
| 阶段 4: 预览功能 | 第 4 周 | 效果预览 + 对比查看 |
| 阶段 5: 优化测试 | 第 5 周 | 性能优化 + 完整测试 + 文档 |

---

## 8. 风险与依赖

### 8.1 技术风险
- Reinhard 算法在极端色彩分布下可能效果不佳
- 大尺寸 LUT（65³）生成耗时较长

### 8.2 依赖项
- colour-science: 色彩空间转换
- opencv-python: 图像处理
- numpy: 数值计算
- scipy: 科学计算

---

## 9. 附录

### 9.1 参考资料
- Reinhard, E. et al. "Color Transfer between Images" (2001)
- .cube 格式规范：https://www.adobe.com/devnet/adobemediaserver.html
- colour-science 文档：https://www.colour-science.org/

### 9.2 术语表
- **LUT**: Look-Up Table，查找表，用于色彩变换
- **Lab 空间**: CIELAB 色彩空间，感知均匀的色彩模型
- **Reinhard 算法**: 基于统计的色彩迁移算法

---

**文档结束**

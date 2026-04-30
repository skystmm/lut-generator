# 视频 LUT 逆向解析 — 设计文档

## 概述

扩展 LUT Generator 支持从视频文件逆向提取色彩风格，生成 3D LUT。

## 需求

| 场景 | 输入 | 输出 |
|------|------|------|
| 单视频提取 | 1 个调色后的视频 | LUT（风格从 sRGB neutral 提取） |
| 双视频对比 | 原始视频 + 调色视频 | LUT（色彩迁移映射） |
| 视频→图片 | 视频 + 参考图片 | LUT（视频色彩映射到图片风格） |
| 图片→视频 | 图片 + 参考视频 | LUT（图片色彩映射到视频风格） |

## 架构设计

```
lut_generator/video/
├── __init__.py
├── frame_extractor.py    # 视频帧提取 + 智能采样
├── scene_detector.py     # 场景切换检测（直方图差异）
├── video_analyzer.py     # 视频色彩分析 + 统计聚合
└── cli.py                # CLI 命令
```

### 模块职责

**VideoFrameExtractor**
- 使用 OpenCV cv2.VideoCapture 读取视频
- 支持均匀采样（每隔 N 帧）和关键帧采样（场景切换点）
- 内存控制：流式处理，不加载全部帧
- 输出：帧列表 (np.ndarray) 或生成器

**SceneDetector**
- 基于 RGB 直方图差异检测场景切换
- 可配置阈值（默认 0.3）
- 输出：场景边界帧号列表

**VideoColorAnalyzer**
- 对采样帧进行色彩分析（复用 ColorAnalyzer）
- 聚合多帧统计信息（加权平均）
- 支持场景权重（长场景权重更高）
- 输出：聚合后的 ColorStatistics

### 算法流程

```
video-generate src.mp4 target.mp4 -o output.cube
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  VideoFrameExtractor    VideoFrameExtractor
        │                       │
        ▼                       ▼
   SceneDetector          SceneDetector
        │                       │
        ▼                       ▼
  采样帧: [f1, f5, f12, ...]  采样帧: [f1, f5, f12, ...]
        │                       │
        ▼                       ▼
  VideoColorAnalyzer     VideoColorAnalyzer
        │                       │
        ▼                       ▼
   聚合统计 S_src         聚合统计 S_tgt
        │                       │
        └───────────┬───────────┘
                    ▼
           LUT3DGenerator.generate_from_stats()
                    │
                    ▼
               output.cube
```

### 智能采样策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| uniform | 每隔 N 帧采样一帧 | 短片、单场景 |
| scene | 每个场景采样 3-5 帧 | 长片、多场景 |
| adaptive | 根据视频长度自动选择 | 通用 |

### 性能优化

- 帧采样率默认 1fps（可通过 -r 调整）
- 场景检测使用 1/4 分辨率直方图
- 统计聚合使用增量式均值/方差计算（无需存储所有帧）

## CLI 设计

```bash
# 从两个视频生成 LUT
lut-generator video-generate src.mp4 graded.mp4 -o output.cube

# 从单个调色视频提取风格
lut-generator video-extract graded.mp4 -o output.cube

# 视频→图片
lut-generator video-generate src.mp4 -t ref.jpg -o output.cube

# 图片→视频
lut-generator video-generate src.jpg -t graded.mp4 -o output.cube

# 高级选项
lut-generator video-generate src.mp4 graded.mp4 \
    -o output.cube \
    -s 33 \
    --sample-rate 0.5 \        # 每秒采样 0.5 帧
    --scene-threshold 0.3 \    # 场景检测阈值
    --max-frames 50 \          # 最大采样帧数
    --strength 0.8
```

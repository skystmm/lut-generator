"""
视频帧提取模块 - VideoFrameExtractor

负责从视频文件中智能提取代表性帧，用于后续色彩分析。
支持三种采样策略：
- uniform: 均匀间隔采样
- scene: 基于场景切换的智能采样
- adaptive: 根据视频长度自动选择策略
"""

import logging
from pathlib import Path
from typing import List, Union, Optional, Iterator, Tuple
from dataclasses import dataclass, field
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger(__name__)


@dataclass
class FrameInfo:
    """帧信息"""
    frame_number: int
    timestamp: float  # seconds
    image: np.ndarray  # RGB format
    is_keyframe: bool = False


@dataclass
class VideoInfo:
    """视频基本信息"""
    path: Path
    total_frames: int
    fps: float
    duration: float  # seconds
    width: int
    height: int
    codec: str = ''


@dataclass
class ExtractorConfig:
    """帧提取配置"""
    # 采样策略: 'uniform', 'scene', 'adaptive'
    strategy: str = 'adaptive'
    
    # 采样率 (帧/秒)，0 = 全部帧
    sample_rate: float = 1.0
    
    # 最大采样帧数（防止内存溢出）
    max_frames: int = 100
    
    # 场景检测阈值（仅 scene/adaptive 策略）
    scene_threshold: float = 0.3
    
    # 每个场景采样的帧数
    frames_per_scene: int = 3
    
    # 用于场景检测的分辨率缩放比例
    scene_detect_scale: float = 0.25


class VideoFrameExtractor:
    """
    视频帧提取器
    
    从视频中提取代表性帧，支持均匀采样和场景智能采样。
    """
    
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
    
    def __init__(self, config: Optional[ExtractorConfig] = None):
        self.config = config or ExtractorConfig()
        
        if cv2 is None:
            raise ImportError(
                "opencv-python is required for video processing. "
                "Install with: pip install opencv-python"
            )
    
    @staticmethod
    def get_video_info(path: Union[str, Path]) -> VideoInfo:
        """获取视频基本信息"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Video not found: {path}")
        if path.suffix.lower() not in VideoFrameExtractor.SUPPORTED_FORMATS:
            logger.warning(f"Unsupported video format: {path.suffix}")
        
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        codec_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = ''.join([chr((codec_int >> 8 * i) & 0xFF) for i in range(4)])
        
        cap.release()
        
        duration = total_frames / fps if fps > 0 else 0
        
        return VideoInfo(
            path=path,
            total_frames=total_frames,
            fps=fps,
            duration=duration,
            width=width,
            height=height,
            codec=codec
        )
    
    def extract(self, path: Union[str, Path]) -> List[FrameInfo]:
        """
        从视频中提取代表性帧
        
        Args:
            path: 视频文件路径
            
        Returns:
            FrameInfo 列表
        """
        path = Path(path)
        info = self.get_video_info(path)
        
        logger.info(
            f"Video: {path.name} | {info.total_frames} frames | "
            f"{info.fps:.1f}fps | {info.duration:.1f}s"
        )
        
        # 选择采样策略
        strategy = self.config.strategy
        if strategy == 'adaptive':
            # 超过 30 秒使用场景检测，否则均匀采样
            strategy = 'scene' if info.duration > 30 else 'uniform'
            logger.info(f"Adaptive strategy selected: {strategy}")
        
        if strategy == 'scene':
            return self._extract_by_scenes(path, info)
        else:
            return self._extract_uniform(path, info)
    
    def extract_frames_generator(
        self, path: Union[str, Path]
    ) -> Iterator[FrameInfo]:
        """生成器模式提取帧（内存友好）"""
        for frame_info in self.extract(path):
            yield frame_info
    
    def _extract_uniform(
        self, path: Path, info: VideoInfo
    ) -> List[FrameInfo]:
        """均匀间隔采样"""
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {path}")
        
        # 计算采样间隔
        if self.config.sample_rate > 0:
            interval = max(1, int(info.fps / self.config.sample_rate))
        else:
            interval = 1
        
        # 限制最大帧数
        total_needed = info.total_frames // interval + 1
        if total_needed > self.config.max_frames:
            # 动态调整间隔
            interval = max(1, info.total_frames // self.config.max_frames)
            logger.info(
                f"Adjusting interval to {interval} "
                f"(max_frames={self.config.max_frames})"
            )
        
        frames = []
        frame_idx = 0
        sample_count = 0
        
        while True:
            ret, frame_bgr = cap.read()
            if not ret:
                break
            
            if frame_idx % interval == 0:
                # BGR → RGB
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                timestamp = frame_idx / info.fps if info.fps > 0 else 0
                
                frames.append(FrameInfo(
                    frame_number=frame_idx,
                    timestamp=timestamp,
                    image=frame_rgb,
                    is_keyframe=(sample_count == 0)
                ))
                sample_count += 1
            
            frame_idx += 1
        
        cap.release()
        logger.info(f"Uniform sampling: {len(frames)} frames extracted")
        return frames
    
    def _extract_by_scenes(
        self, path: Path, info: VideoInfo
    ) -> List[FrameInfo]:
        """基于场景切换的智能采样"""
        # 第一步：检测场景边界
        scene_boundaries = self._detect_scene_boundaries(path, info)
        
        logger.info(
            f"Scene detection: {len(scene_boundaries)} scenes found "
            f"(threshold={self.config.scene_threshold})"
        )
        
        # 第二步：从每个场景采样
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {path}")
        
        frames = []
        fps_per_scene = self.config.frames_per_scene
        
        for i, (start, end) in enumerate(scene_boundaries):
            scene_length = end - start
            if scene_length <= 0:
                continue
            
            # 计算该场景的采样帧号
            if scene_length <= fps_per_scene:
                sample_positions = [start]
            else:
                # 均匀分布在场景中
                step = scene_length / (fps_per_scene + 1)
                sample_positions = [
                    start + int(step * (j + 1))
                    for j in range(fps_per_scene)
                ]
            
            # 限制总帧数
            if len(frames) + len(sample_positions) > self.config.max_frames:
                remaining = self.config.max_frames - len(frames)
                if remaining <= 0:
                    break
                sample_positions = sample_positions[:remaining]
            
            for pos in sample_positions:
                cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
                ret, frame_bgr = cap.read()
                if not ret:
                    continue
                
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                timestamp = pos / info.fps if info.fps > 0 else 0
                
                frames.append(FrameInfo(
                    frame_number=pos,
                    timestamp=timestamp,
                    image=frame_rgb,
                    is_keyframe=(pos == start)  # 场景第一帧标记为关键帧
                ))
        
        cap.release()
        logger.info(f"Scene-based sampling: {len(frames)} frames from {len(scene_boundaries)} scenes")
        return frames
    
    def _detect_scene_boundaries(
        self, path: Path, info: VideoInfo
    ) -> List[Tuple[int, int]]:
        """
        检测场景切换点
        
        基于 RGB 直方图差异检测场景变化。
        使用降低分辨率的帧进行快速比较。
        
        Returns:
            场景边界列表 [(start_frame, end_frame), ...]
        """
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {path}")
        
        scale = self.config.scene_detect_scale
        threshold = self.config.scene_threshold
        step = max(1, int(info.fps * 0.5))  # 每 0.5 秒检测一次
        
        scenes = []
        current_start = 0
        prev_hist = None
        frame_idx = 0
        
        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break
            
            # 缩放加速
            h, w = frame.shape[:2]
            small = cv2.resize(
                frame,
                (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_AREA
            )
            
            # 计算 RGB 直方图
            hist = self._compute_histogram(small)
            
            if prev_hist is not None:
                # 直方图相似度 (Bhattacharyya distance)
                similarity = cv2.compareHist(
                    hist, prev_hist, cv2.HISTCMP_BHATTACHARYYA
                )
                
                if similarity > threshold:
                    # 场景切换
                    scenes.append((current_start, frame_idx - step))
                    current_start = frame_idx
            
            prev_hist = hist
            frame_idx += step
        
        # 添加最后一个场景
        if current_start < frame_idx:
            scenes.append((current_start, frame_idx))
        
        cap.release()
        
        if not scenes:
            # 单场景
            scenes = [(0, info.total_frames)]
        
        return scenes
    
    @staticmethod
    def _compute_histogram(image: np.ndarray) -> np.ndarray:
        """计算 RGB 联合直方图（用于场景检测）"""
        # 使用 8x8x8 bin 的 RGB 直方图
        hist = cv2.calcHist(
            [image], [0, 1, 2], None,
            [8, 8, 8], [0, 256, 0, 256, 0, 256]
        )
        cv2.normalize(hist, hist)
        return hist.flatten()

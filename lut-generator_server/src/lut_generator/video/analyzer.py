"""
视频色彩分析模块 - VideoColorAnalyzer

对视频帧进行色彩分析并聚合统计信息，
支持生成视频级 LUT。
"""

import logging
from pathlib import Path
from typing import List, Optional, Union
from dataclasses import dataclass
import numpy as np

from lut_generator.analysis.analyzer import ColorAnalyzer, AnalysisResult, ColorStatistics
from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig
from lut_generator.video.frame_extractor import (
    VideoFrameExtractor, FrameInfo, ExtractorConfig, VideoInfo
)

logger = logging.getLogger(__name__)


@dataclass
class VideoColorStats:
    """视频聚合色彩统计"""
    # 聚合后的 mean/std/var (Lab 空间)
    mean_L: float
    mean_a: float
    mean_b: float
    std_L: float
    std_a: float
    std_b: float
    var_L: float
    var_a: float
    var_b: float
    
    # 元信息
    total_frames_analyzed: int
    video_info: Optional[VideoInfo] = None
    
    # 每个场景的统计（可选）
    scene_stats: Optional[List['SceneStats']] = None
    
    def to_color_statistics(self) -> ColorStatistics:
        """转换为 ColorStatistics（兼容现有 LUT 生成接口）"""
        return ColorStatistics(
            mean_L=self.mean_L,
            mean_a=self.mean_a,
            mean_b=self.mean_b,
            std_L=self.std_L,
            std_a=self.std_a,
            std_b=self.std_b,
            var_L=self.var_L,
            var_a=self.var_a,
            var_b=self.var_b
        )


@dataclass
class SceneStats:
    """单个场景的统计"""
    scene_index: int
    start_frame: int
    end_frame: int
    frame_count: int
    mean_L: float
    mean_a: float
    mean_b: float
    std_L: float
    std_a: float
    std_b: float


class VideoColorAnalyzer:
    """
    视频色彩分析器
    
    从视频帧中提取色彩统计信息，聚合为视频级特征。
    """
    
    def __init__(
        self,
        use_colour: bool = True,
        extractor_config: Optional[ExtractorConfig] = None
    ):
        self.use_colour = use_colour
        self.extractor_config = extractor_config or ExtractorConfig()
        self.frame_extractor = VideoFrameExtractor(self.extractor_config)
        self.color_analyzer = ColorAnalyzer(use_colour=use_colour)
    
    def analyze_video(
        self, path: Union[str, Path]
    ) -> VideoColorStats:
        """
        分析视频的聚合色彩统计
        
        Args:
            path: 视频文件路径
            
        Returns:
            VideoColorStats 对象
        """
        path = Path(path)
        video_info = self.frame_extractor.get_video_info(path)
        logger.info(f"Analyzing video: {path.name}")
        
        # 提取代表性帧
        frames = self.frame_extractor.extract(path)
        
        if not frames:
            raise ValueError(f"No frames extracted from {path}")
        
        # 分析每帧
        results = []
        for frame_info in frames:
            try:
                # 将 numpy 数组临时保存为临时文件进行分析
                # 或者直接使用内存分析
                result = self._analyze_frame(frame_info.image)
                results.append(result)
            except Exception as e:
                logger.warning(
                    f"Failed to analyze frame {frame_info.frame_number}: {e}"
                )
        
        if not results:
            raise ValueError(
                f"No frames could be analyzed from {path}"
            )
        
        # 聚合统计
        agg_stats = self._aggregate_stats(results, frames)
        
        return VideoColorStats(
            mean_L=agg_stats['mean'][0],
            mean_a=agg_stats['mean'][1],
            mean_b=agg_stats['mean'][2],
            std_L=agg_stats['std'][0],
            std_a=agg_stats['std'][1],
            std_b=agg_stats['std'][2],
            var_L=agg_stats['var'][0],
            var_a=agg_stats['var'][1],
            var_b=agg_stats['var'][2],
            total_frames_analyzed=len(results),
            video_info=video_info
        )
    
    def generate_lut_from_videos(
        self,
        source_path: Union[str, Path],
        target_path: Union[str, Path],
        lut_size: int = 33,
        strength: float = 1.0
    ) -> np.ndarray:
        """
        从两个视频生成 LUT
        
        Args:
            source_path: 源视频（原始）
            target_path: 目标视频（调色后）
            lut_size: LUT 精度 (17/33/65)
            strength: 迁移强度 (0-1)
            
        Returns:
            LUT 数组 shape=(N, N, N, 3)
        """
        logger.info(f"Generating LUT: {Path(source_path).name} → {Path(target_path).name}")
        
        # 并行分析两个视频
        source_stats = self.analyze_video(source_path)
        target_stats = self.analyze_video(target_path)
        
        # 生成 LUT
        config = LUT3DConfig(grid_size=lut_size)
        generator = LUT3DGenerator(config)
        
        lut = generator.generate_from_stats(
            source_stats.to_color_statistics(),
            target_stats.to_color_statistics(),
            strength=strength
        )
        
        logger.info(f"LUT generated: {lut.shape}")
        return lut
    
    def generate_lut_from_video_and_image(
        self,
        video_path: Union[str, Path],
        image_path: Union[str, Path],
        lut_size: int = 33,
        strength: float = 1.0,
        video_is_source: bool = True
    ) -> np.ndarray:
        """
        从视频+图片生成 LUT
        
        Args:
            video_path: 视频路径
            image_path: 图片路径
            lut_size: LUT 精度
            strength: 迁移强度
            video_is_source: True=视频为源，False=视频为目标
        """
        video_stats = self.analyze_video(video_path)
        
        # 分析图片
        img_result = self.color_analyzer.analyze(Path(image_path))
        
        if video_is_source:
            source = video_stats.to_color_statistics()
            target = img_result.statistics
        else:
            source = img_result.statistics
            target = video_stats.to_color_statistics()
        
        config = LUT3DConfig(grid_size=lut_size)
        generator = LUT3DGenerator(config)
        
        return generator.generate_from_stats(source, target, strength)
    
    def _analyze_frame(self, frame_rgb: np.ndarray) -> AnalysisResult:
        """
        分析单帧（从 numpy 数组）
        
        使用临时文件方式兼容现有的 ColorAnalyzer。
        """
        import tempfile
        from PIL import Image
        
        # 保存为临时 PNG
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            img = Image.fromarray(frame_rgb)
            img.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            return self.color_analyzer.analyze(Path(tmp_path))
        finally:
            import os
            os.unlink(tmp_path)
    
    def _aggregate_stats(
        self,
        results: List[AnalysisResult],
        frames: List[FrameInfo]
    ) -> dict:
        """
        聚合多帧的统计信息
        
        使用增量式均值和方差计算。
        """
        n = len(results)
        if n == 0:
            raise ValueError("No results to aggregate")
        
        # 初始化
        sum_mean_L = sum_mean_a = sum_mean_b = 0.0
        sum_var_L = sum_var_a = sum_var_b = 0.0
        sum_std_L = sum_std_a = sum_std_b = 0.0
        
        for r in results:
            s = r.statistics
            sum_mean_L += s.mean_L
            sum_mean_a += s.mean_a
            sum_mean_b += s.mean_b
            sum_var_L += s.var_L
            sum_var_a += s.var_a
            sum_var_b += s.var_b
            sum_std_L += s.std_L
            sum_std_a += s.std_a
            sum_std_b += s.std_b
        
        return {
            'mean': [
                sum_mean_L / n,
                sum_mean_a / n,
                sum_mean_b / n
            ],
            'std': [
                sum_std_L / n,
                sum_std_a / n,
                sum_std_b / n
            ],
            'var': [
                sum_var_L / n,
                sum_var_a / n,
                sum_var_b / n
            ],
            'num_frames': n
        }

"""
视频 LUT 逆向解析模块单元测试

测试视频帧提取、场景检测、色彩分析和 LUT 生成功能。
"""

import pytest
import numpy as np
import cv2
import tempfile
from pathlib import Path
import sys

# 添加 src 目录到路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from lut_generator.video.frame_extractor import (
    VideoFrameExtractor, FrameInfo, VideoInfo, ExtractorConfig
)
from lut_generator.video.analyzer import (
    VideoColorAnalyzer, VideoColorStats
)


def create_test_video(path: Path, frames: int = 60, fps: int = 30,
                      width: int = 320, height: int = 240) -> Path:
    """创建测试视频"""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    
    for i in range(frames):
        # 创建渐变帧
        t = i / frames
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :, 2] = int(100 + 155 * t)  # R
        frame[:, :, 1] = int(50 + 100 * t)   # G
        frame[:, :, 0] = int(30 + 70 * t)    # B
        writer.write(frame)
    
    writer.release()
    return path


class TestExtractorConfig:
    """测试 ExtractorConfig 数据类"""
    
    def test_defaults(self):
        config = ExtractorConfig()
        assert config.strategy == 'adaptive'
        assert config.sample_rate == 1.0
        assert config.max_frames == 100
        assert config.scene_threshold == 0.3
        assert config.frames_per_scene == 3
    
    def test_custom(self):
        config = ExtractorConfig(
            strategy='uniform',
            sample_rate=2.0,
            max_frames=50
        )
        assert config.strategy == 'uniform'
        assert config.sample_rate == 2.0
        assert config.max_frames == 50


class TestVideoInfo:
    """测试 VideoInfo"""
    
    def test_get_video_info(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        create_test_video(video_path, frames=30, fps=30)
        
        info = VideoFrameExtractor.get_video_info(video_path)
        assert info.total_frames == 30
        assert info.fps == 30.0
        assert info.duration == 1.0
        assert info.width == 320
        assert info.height == 240


class TestVideoFrameExtractor:
    """测试 VideoFrameExtractor"""
    
    def test_uniform_sampling(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        create_test_video(video_path, frames=60, fps=30)
        
        config = ExtractorConfig(
            strategy='uniform',
            sample_rate=2.0,  # 2fps
            max_frames=100
        )
        extractor = VideoFrameExtractor(config)
        frames = extractor.extract(video_path)
        
        assert len(frames) > 0
        assert len(frames) <= 100  # max_frames
        assert isinstance(frames[0], FrameInfo)
        assert frames[0].image.shape[2] == 3  # RGB
    
    def test_max_frames_limit(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        create_test_video(video_path, frames=300, fps=30)
        
        config = ExtractorConfig(
            strategy='uniform',
            sample_rate=10.0,  # 高采样率
            max_frames=5
        )
        extractor = VideoFrameExtractor(config)
        frames = extractor.extract(video_path)
        
        assert len(frames) <= 5
    
    def test_adaptive_strategy(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        create_test_video(video_path, frames=30, fps=30)  # 1s video
        
        config = ExtractorConfig(strategy='adaptive')
        extractor = VideoFrameExtractor(config)
        frames = extractor.extract(video_path)
        
        assert len(frames) > 0
    
    def test_file_not_found(self):
        config = ExtractorConfig()
        extractor = VideoFrameExtractor(config)
        
        with pytest.raises(FileNotFoundError):
            extractor.extract("/nonexistent/video.mp4")


class TestVideoColorAnalyzer:
    """测试 VideoColorAnalyzer"""
    
    def test_analyze_video(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        create_test_video(video_path, frames=30, fps=30)
        
        config = ExtractorConfig(
            strategy='uniform',
            sample_rate=5.0,
            max_frames=10
        )
        analyzer = VideoColorAnalyzer(
            use_colour=False,  # 更快
            extractor_config=config
        )
        
        stats = analyzer.analyze_video(video_path)
        
        assert isinstance(stats, VideoColorStats)
        assert stats.total_frames_analyzed > 0
        assert 0 <= stats.mean_L <= 100  # Lab L range
        assert stats.video_info is not None
    
    def test_generate_lut_from_videos(self, tmp_path):
        src_path = tmp_path / "source.mp4"
        tgt_path = tmp_path / "target.mp4"
        create_test_video(src_path, frames=30, fps=30)
        create_test_video(tgt_path, frames=30, fps=30)
        
        config = ExtractorConfig(
            strategy='uniform',
            sample_rate=5.0,
            max_frames=10
        )
        analyzer = VideoColorAnalyzer(
            use_colour=False,
            extractor_config=config
        )
        
        lut = analyzer.generate_lut_from_videos(src_path, tgt_path, lut_size=17)
        
        assert lut.shape == (17, 17, 17, 3)
    
    def test_generate_lut_video_to_image(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        create_test_video(video_path, frames=30, fps=30)
        
        # 创建测试图片
        img_path = tmp_path / "ref.png"
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        img[:, :, 2] = 150  # R
        img[:, :, 1] = 100  # G
        img[:, :, 0] = 50   # B
        from PIL import Image
        Image.fromarray(img).save(img_path)
        
        config = ExtractorConfig(
            strategy='uniform',
            sample_rate=5.0,
            max_frames=10
        )
        analyzer = VideoColorAnalyzer(
            use_colour=False,
            extractor_config=config
        )
        
        lut = analyzer.generate_lut_from_video_and_image(
            video_path, img_path,
            lut_size=17,
            video_is_source=True
        )
        
        assert lut.shape == (17, 17, 17, 3)
    
    def test_to_color_statistics(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        create_test_video(video_path, frames=30, fps=30)
        
        config = ExtractorConfig(
            strategy='uniform',
            sample_rate=5.0,
            max_frames=10
        )
        analyzer = VideoColorAnalyzer(
            use_colour=False,
            extractor_config=config
        )
        
        stats = analyzer.analyze_video(video_path)
        color_stats = stats.to_color_statistics()
        
        # 验证可以转换为 ColorStatistics
        assert hasattr(color_stats, 'mean_L')
        assert hasattr(color_stats, 'mean_a')
        assert hasattr(color_stats, 'mean_b')

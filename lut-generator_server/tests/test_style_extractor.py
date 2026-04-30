"""
单图风格提取模块单元测试

测试 style_extractor.py 中的功能：
- StyleExtractor 类初始化
- 风格特征提取
- LUT 生成
- 强度调节
- 分析报告生成
"""

import pytest
import numpy as np
import sys
from pathlib import Path
import tempfile
import json

# 添加 src 目录到路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from lut_generator.core.style_extractor import (
    StyleExtractor,
    StyleFeatures,
    NeutralBaseline,
    ExtractionResult
)


class TestStyleExtractor:
    """测试 StyleExtractor 类"""

    @pytest.fixture
    def extractor(self):
        """创建提取器实例"""
        return StyleExtractor(grid_size=17, strength=0.8)  # 使用较小的网格加速测试

    @pytest.fixture
    def warm_rgb(self):
        """创建暖色调测试图像"""
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb[:, :] = [255, 128, 64]  # 橙色
        return rgb

    @pytest.fixture
    def cool_rgb(self):
        """创建冷色调测试图像"""
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb[:, :] = [64, 128, 255]  # 蓝色
        return rgb

    @pytest.fixture
    def neutral_rgb(self):
        """创建中性灰测试图像"""
        return np.ones((100, 100, 3), dtype=np.uint8) * 128

    def test_extractor_creation(self, extractor):
        """测试提取器创建"""
        assert extractor.grid_size == 17
        assert extractor.strength == 0.8
        assert extractor.baseline.mean_L == 50.0
        assert extractor.baseline.mean_a == 0.0
        assert extractor.baseline.mean_b == 0.0

    def test_extractor_different_sizes(self):
        """测试不同网格尺寸"""
        for size in [17, 33, 65]:
            ext = StyleExtractor(grid_size=size)
            assert ext.grid_size == size

    def test_extract_features_from_array(self, extractor, warm_rgb):
        """测试从数组提取风格特征"""
        features = extractor.extract_features_from_array(warm_rgb)

        # 检查返回类型
        assert isinstance(features, StyleFeatures)

        # 检查特征值合理性
        assert isinstance(features.warmth, float)
        assert isinstance(features.saturation, float)
        assert isinstance(features.contrast, float)
        assert isinstance(features.tone_shift_L, float)

    def test_extract_features_warm_vs_cool(self, extractor, warm_rgb, cool_rgb):
        """测试暖色调和冷色调图像的特征差异"""
        warm_features = extractor.extract_features_from_array(warm_rgb)
        cool_features = extractor.extract_features_from_array(cool_rgb)

        # 暖色调图像应该有更高的 b 值（黄色通道）
        assert warm_features.tone_shift_b > cool_features.tone_shift_b

        # warmth 指标也应该体现差异
        assert warm_features.warmth > cool_features.warmth

    def test_extract_features_neutral(self, extractor, neutral_rgb):
        """测试中性灰图像特征"""
        features = extractor.extract_features_from_array(neutral_rgb)

        # 中性灰应该接近中性
        assert abs(features.tone_shift_L) < 10  # 允许一定误差
        assert abs(features.warmth) < 0.3
        assert features.saturation < 0.5

    def test_generate_lut_from_features(self, extractor, warm_rgb):
        """测试从特征生成 LUT"""
        features = extractor.extract_features_from_array(warm_rgb)
        lut = extractor.generate_lut_from_features(features)

        # 检查 LUT 形状
        assert lut.shape == (17, 17, 17, 3)

        # 检查值范围
        assert lut.min() >= 0
        assert lut.max() <= 1

    def test_generate_lut_with_different_strengths(self, extractor, warm_rgb):
        """测试不同强度下的 LUT 生成"""
        features = extractor.extract_features_from_array(warm_rgb)

        # 生成不同强度的 LUT
        lut_weak = extractor.generate_lut_from_features(features, strength=0.3)
        lut_strong = extractor.generate_lut_from_features(features, strength=0.9)

        # 都应该有正确的形状
        assert lut_weak.shape == (17, 17, 17, 3)
        assert lut_strong.shape == (17, 17, 17, 3)

    def test_generate_lut_full_workflow(self, extractor, tmp_path):
        """测试完整的 LUT 生成流程"""
        import cv2

        # 创建测试图像
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb[:, :] = [200, 150, 100]  # 暖灰调

        img_path = tmp_path / "test_source.png"
        cv2.imwrite(str(img_path), rgb[:, :, ::-1])  # BGR

        # 生成 LUT
        result = extractor.generate_lut(str(img_path))

        # 检查返回类型
        assert isinstance(result, ExtractionResult)
        assert isinstance(result.features, StyleFeatures)
        assert result.style_lut_data.shape == (17, 17, 17, 3)

        # 检查元数据
        assert 'source_image' in result.metadata
        assert 'strength' in result.metadata
        assert 'description' in result.metadata

    def test_file_not_found(self, extractor):
        """测试文件不存在的情况"""
        with pytest.raises(FileNotFoundError):
            extractor.extract_features("/nonexistent/path/image.png")


class TestNeutralBaseline:
    """测试 NeutralBaseline 类"""

    def test_default_baseline(self):
        """测试默认基准"""
        baseline = NeutralBaseline()

        assert baseline.mean_L == 50.0
        assert baseline.mean_a == 0.0
        assert baseline.mean_b == 0.0
        assert baseline.std_L == 25.0

    def test_to_color_statistics(self):
        """测试转换为 ColorStatistics"""
        baseline = NeutralBaseline()
        stats = baseline.to_color_statistics()

        assert stats.mean_L == 50.0
        assert stats.std_L == 25.0


class TestStyleFeatures:
    """测试 StyleFeatures 数据类"""

    def test_features_creation(self):
        """测试创建特征对象"""
        features = StyleFeatures(
            tone_shift_L=-5.0,
            tone_shift_a=2.0,
            tone_shift_b=3.0,
            contrast_L=1.2,
            saturation_a=0.8,
            saturation_b=0.9,
            warmth=0.15,
            saturation=0.85,
            contrast=1.2
        )

        assert features.tone_shift_L == -5.0
        assert features.warmth == 0.15
        assert features.saturation == 0.85


class TestBrightnessDetection:
    """测试亮度检测"""

    @pytest.fixture
    def extractor(self):
        return StyleExtractor(grid_size=17)

    def test_high_key_detection(self, extractor):
        """测试高调图像检测"""
        high_key = np.ones((100, 100, 3), dtype=np.uint8) * 220
        features = extractor.extract_features_from_array(high_key)

        # 高调图像应该有正的 tone_shift_L
        assert features.tone_shift_L > 0

    def test_low_key_detection(self, extractor):
        """测试低调图像检测"""
        low_key = np.ones((100, 100, 3), dtype=np.uint8) * 30
        features = extractor.extract_features_from_array(low_key)

        # 低调图像应该有负的 tone_shift_L
        assert features.tone_shift_L < 0


class TestSaturationDetection:
    """测试饱和度检测"""

    @pytest.fixture
    def extractor(self):
        return StyleExtractor(grid_size=17)

    def test_high_saturation(self, extractor):
        """测试高饱和度图像"""
        saturated = np.zeros((100, 100, 3), dtype=np.uint8)
        saturated[:, :] = [255, 0, 0]  # 纯红

        features = extractor.extract_features_from_array(saturated)
        neutral = np.ones((100, 100, 3), dtype=np.uint8) * 128
        neutral_features = extractor.extract_features_from_array(neutral)

        # 高饱和度图像应该有更高的饱和度值
        assert features.saturation > neutral_features.saturation

    def test_low_saturation(self, extractor):
        """测试低饱和度图像"""
        desaturated = np.ones((100, 100, 3), dtype=np.uint8) * 128
        features = extractor.extract_features_from_array(desaturated)

        # 低饱和度图像应该有较低的饱和度值
        assert features.saturation < 0.5


class TestContrastDetection:
    """测试对比度检测"""

    @pytest.fixture
    def extractor(self):
        return StyleExtractor(grid_size=17)

    def test_high_contrast(self, extractor):
        """测试高对比度图像"""
        high_contrast = np.zeros((100, 100, 3), dtype=np.uint8)
        high_contrast[:, :50] = 255
        high_contrast[:, 50:] = 0

        features = extractor.extract_features_from_array(high_contrast)

        # 高对比度图像应该有较高的对比度值
        assert features.contrast > 1.0

    def test_low_contrast(self, extractor):
        """测试低对比度图像"""
        low_contrast = np.ones((100, 100, 3), dtype=np.uint8) * 128
        features = extractor.extract_features_from_array(low_contrast)

        # 低对比度（均匀图像）应该有较低的对比度值
        assert features.contrast < 1.0


class TestEdgeCases:
    """测试边界情况"""

    @pytest.fixture
    def extractor(self):
        return StyleExtractor(grid_size=17)

    def test_single_pixel_image(self, extractor):
        """测试单像素图像"""
        single = np.array([[[255, 128, 0]]], dtype=np.uint8)
        features = extractor.extract_features_from_array(single)

        assert isinstance(features, StyleFeatures)

    def test_large_image(self, extractor):
        """测试大尺寸图像"""
        large = np.random.randint(0, 256, (500, 500, 3), dtype=np.uint8)
        features = extractor.extract_features_from_array(large)

        assert isinstance(features, StyleFeatures)

    def test_extreme_colors(self, extractor):
        """测试极端颜色"""
        # 纯白
        white = np.ones((100, 100, 3), dtype=np.uint8) * 255
        white_features = extractor.extract_features_from_array(white)

        # 纯黑
        black = np.zeros((100, 100, 3), dtype=np.uint8)
        black_features = extractor.extract_features_from_array(black)

        assert isinstance(white_features, StyleFeatures)
        assert isinstance(black_features, StyleFeatures)

        # 白色应该有更高的 tone_shift_L
        assert white_features.tone_shift_L > black_features.tone_shift_L


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
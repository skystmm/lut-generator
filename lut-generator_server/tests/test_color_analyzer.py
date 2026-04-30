"""
色彩分析模块单元测试

测试 color_analyzer.py 中的功能：
- 色彩空间转换（RGB ↔ Lab）
- 统计特征提取
- 直方图提取
- 分布分析
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# 添加 src 目录到路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from color_analyzer import (
    ColorAnalyzer,
    ColorStatistics,
    ColorHistogram,
    ColorDistribution,
    AnalysisResult,
    analyze_image
)


class TestColorStatistics:
    """测试 ColorStatistics 数据类"""
    
    def test_creation(self):
        """测试创建统计对象"""
        stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=15.0, std_a=5.0, std_b=8.0,
            var_L=225.0, var_a=25.0, var_b=64.0
        )
        assert stats.mean_L == 50.0
        assert stats.mean_a == 10.0
        assert stats.mean_b == 20.0
    
    def test_to_dict(self):
        """测试转换为字典"""
        stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=15.0, std_a=5.0, std_b=8.0,
            var_L=225.0, var_a=25.0, var_b=64.0
        )
        d = stats.to_dict()
        assert 'mean' in d
        assert 'std' in d
        assert 'var' in d
        assert d['mean'] == [50.0, 10.0, 20.0]
        assert d['std'] == [15.0, 5.0, 8.0]
    
    def test_mean_array(self):
        """测试均值数组"""
        stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=15.0, std_a=5.0, std_b=8.0,
            var_L=225.0, var_a=25.0, var_b=64.0
        )
        arr = stats.mean_array()
        assert arr.shape == (3,)
        assert np.allclose(arr, [50.0, 10.0, 20.0])
    
    def test_std_array(self):
        """测试标准差数组"""
        stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=15.0, std_a=5.0, std_b=8.0,
            var_L=225.0, var_a=25.0, var_b=64.0
        )
        arr = stats.std_array()
        assert arr.shape == (3,)
        assert np.allclose(arr, [15.0, 5.0, 8.0])


class TestColorAnalyzer:
    """测试 ColorAnalyzer 类"""
    
    @pytest.fixture
    def analyzer(self):
        """创建分析器实例"""
        return ColorAnalyzer(use_colour=False)  # 使用 OpenCV 避免依赖问题
    
    @pytest.fixture
    def test_rgb_image(self):
        """创建测试 RGB 图像"""
        # 创建 100x100 的测试图像
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        
        # 左上角：红色
        rgb[:50, :50] = [255, 0, 0]
        
        # 右上角：绿色
        rgb[:50, 50:] = [0, 255, 0]
        
        # 左下角：蓝色
        rgb[50:, :50] = [0, 0, 255]
        
        # 右下角：白色
        rgb[50:, 50:] = [255, 255, 255]
        
        return rgb
    
    def test_rgb_to_lab_conversion(self, analyzer, test_rgb_image):
        """测试 RGB 到 Lab 转换"""
        lab = analyzer.rgb_to_lab(test_rgb_image)
        
        # 检查形状
        assert lab.shape == test_rgb_image.shape
        
        # 检查值范围
        assert lab[:, :, 0].min() >= 0
        assert lab[:, :, 0].max() <= 100
        assert lab[:, :, 1].min() >= -128
        assert lab[:, :, 1].max() <= 127
        assert lab[:, :, 2].min() >= -128
        assert lab[:, :, 2].max() <= 127
    
    def test_lab_to_rgb_conversion(self, analyzer, test_rgb_image):
        """测试 Lab 到 RGB 转换（往返测试）"""
        # RGB → Lab → RGB
        lab = analyzer.rgb_to_lab(test_rgb_image)
        rgb_back = analyzer.lab_to_rgb(lab)
        
        # 检查形状
        assert rgb_back.shape == test_rgb_image.shape
        
        # 检查值范围（允许一定误差）
        assert rgb_back.min() >= 0
        assert rgb_back.max() <= 1.0
        
        # 转换回 uint8 比较
        rgb_back_uint8 = (rgb_back * 255).astype(np.uint8)
        # 允许一定误差（色彩空间转换不是完全可逆的）
        diff = np.mean(np.abs(rgb_back_uint8.astype(float) - test_rgb_image.astype(float)))
        assert diff < 15  # 平均误差小于 15
    
    def test_extract_statistics(self, analyzer, test_rgb_image):
        """测试统计特征提取"""
        lab = analyzer.rgb_to_lab(test_rgb_image)
        stats = analyzer.extract_statistics(lab)
        
        # 检查返回类型
        assert isinstance(stats, ColorStatistics)
        
        # 检查值合理性
        assert stats.mean_L > 0
        assert stats.mean_L < 100
        assert stats.std_L >= 0
        assert stats.std_a >= 0
        assert stats.std_b >= 0
    
    def test_extract_histogram(self, analyzer, test_rgb_image):
        """测试直方图提取"""
        lab = analyzer.rgb_to_lab(test_rgb_image)
        hist = analyzer.extract_histogram(lab, bins=256)
        
        # 检查返回类型
        assert isinstance(hist, ColorHistogram)
        
        # 检查直方图形状
        assert hist.L_hist.shape == (256,)
        assert hist.a_hist.shape == (256,)
        assert hist.b_hist.shape == (256,)
        
        # 检查归一化
        assert np.isclose(hist.L_hist.sum(), 1.0)
        assert np.isclose(hist.a_hist.sum(), 1.0)
        assert np.isclose(hist.b_hist.sum(), 1.0)
    
    def test_extract_distribution(self, analyzer, test_rgb_image):
        """测试分布特征提取"""
        lab = analyzer.rgb_to_lab(test_rgb_image)
        dist = analyzer.extract_distribution(lab)
        
        # 检查返回类型
        assert isinstance(dist, ColorDistribution)
        
        # 检查范围
        assert dist.L_range[0] >= 0
        assert dist.L_range[1] <= 100
        assert dist.a_range[0] >= -128
        assert dist.a_range[1] <= 127
        assert dist.b_range[0] >= -128
        assert dist.b_range[1] <= 127
        
        # 检查色域覆盖
        assert 0 <= dist.gamut_coverage <= 100
        
        # 检查熵
        assert dist.color_entropy >= 0
    
    def test_analyze_array(self, analyzer, test_rgb_image):
        """测试完整的数组分析"""
        result = analyzer.analyze_array(test_rgb_image)
        
        # 检查返回类型
        assert isinstance(result, AnalysisResult)
        
        # 检查包含所有组件
        assert isinstance(result.statistics, ColorStatistics)
        assert isinstance(result.histogram, ColorHistogram)
        assert isinstance(result.distribution, ColorDistribution)
        
        # 检查图像形状
        assert result.image_shape == test_rgb_image.shape
    
    def test_analyze_with_different_sizes(self, analyzer):
        """测试不同尺寸的图像"""
        sizes = [(50, 50), (100, 200), (256, 256), (1920, 1080)]
        
        for h, w in sizes:
            rgb = np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)
            result = analyzer.analyze_array(rgb)
            assert result.image_shape == (h, w, 3)
    
    def test_uniform_color(self, analyzer):
        """测试纯色图像"""
        # 创建纯灰色图像
        gray = np.ones((100, 100, 3), dtype=np.uint8) * 128
        
        lab = analyzer.rgb_to_lab(gray)
        stats = analyzer.extract_statistics(lab)
        
        # 纯色图像的标准差应该接近 0
        assert stats.std_L < 1.0
        assert stats.std_a < 1.0
        assert stats.std_b < 1.0
        
        # 熵应该很低
        dist = analyzer.extract_distribution(lab)
        assert dist.color_entropy < 1.0
    
    def test_gradient_image(self, analyzer):
        """测试渐变图像"""
        # 创建灰度渐变（从黑到白）
        gradient = np.zeros((100, 100, 3), dtype=np.uint8)
        for i in range(100):
            gradient[i, :] = [i * 2, i * 2, i * 2]  # 灰度渐变
        
        lab = analyzer.rgb_to_lab(gradient)
        stats = analyzer.extract_statistics(lab)
        
        # 渐变图像应该有较大的标准差（L 通道）
        # 由于 RGB 到 Lab 不是完全线性，使用更宽松的阈值
        assert stats.std_L > 3
        assert stats.std_L < 50  # 但不应过大


class TestAnalyzeImageFunction:
    """测试便捷函数 analyze_image"""
    
    @pytest.fixture
    def test_image_path(self, tmp_path):
        """创建临时测试图像"""
        import cv2
        
        # 创建测试图像
        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        rgb[:50, :50] = [255, 0, 0]
        rgb[:50, 50:] = [0, 255, 0]
        rgb[50:, :50] = [0, 0, 255]
        rgb[50:, 50:] = [255, 255, 255]
        
        # 保存为 BGR（OpenCV 格式）
        bgr = rgb[:, :, ::-1]
        
        img_path = tmp_path / "test_image.png"
        cv2.imwrite(str(img_path), bgr)
        
        return img_path
    
    def test_analyze_image(self, test_image_path):
        """测试分析图像文件"""
        result = analyze_image(test_image_path, use_colour=False)
        
        assert isinstance(result, AnalysisResult)
        assert result.image_shape[0] == 100
        assert result.image_shape[1] == 100
    
    def test_analyze_image_not_found(self):
        """测试文件不存在的情况"""
        with pytest.raises(FileNotFoundError):
            analyze_image("/nonexistent/path/image.png")


class TestColorSpaceAccuracy:
    """测试色彩空间转换的准确性"""
    
    def test_known_colors(self):
        """测试已知颜色的转换"""
        analyzer = ColorAnalyzer(use_colour=False)
        
        # 测试纯红色
        red_rgb = np.array([[[255, 0, 0]]], dtype=np.uint8)
        red_lab = analyzer.rgb_to_lab(red_rgb)
        
        # 红色的 L 应该在 50-60 左右
        assert 40 < red_lab[0, 0, 0] < 70
        # a 应该是正值（红-绿轴的正向）
        assert red_lab[0, 0, 1] > 50
        # b 应该是较小的正值
        assert red_lab[0, 0, 2] > 0
        
        # 测试纯绿色
        green_rgb = np.array([[[0, 255, 0]]], dtype=np.uint8)
        green_lab = analyzer.rgb_to_lab(green_rgb)
        
        # 绿色的 L 应该在 80-95 左右
        assert 70 < green_lab[0, 0, 0] < 100
        # a 应该是负值
        assert green_lab[0, 0, 1] < -50
        
        # 测试纯蓝色
        blue_rgb = np.array([[[0, 0, 255]]], dtype=np.uint8)
        blue_lab = analyzer.rgb_to_lab(blue_rgb)
        
        # 蓝色的 L 应该较低
        assert blue_lab[0, 0, 0] < 40
        # b 应该是负值
        assert blue_lab[0, 0, 2] < -50
        
        # 测试纯白色
        white_rgb = np.array([[[255, 255, 255]]], dtype=np.uint8)
        white_lab = analyzer.rgb_to_lab(white_rgb)
        
        # 白色的 L 应该接近 100
        assert white_lab[0, 0, 0] > 90
        # a, b 应该接近 0
        assert abs(white_lab[0, 0, 1]) < 10
        assert abs(white_lab[0, 0, 2]) < 10
        
        # 测试纯黑色
        black_rgb = np.array([[[0, 0, 0]]], dtype=np.uint8)
        black_lab = analyzer.rgb_to_lab(black_rgb)
        
        # 黑色的 L 应该接近 0
        assert black_lab[0, 0, 0] < 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

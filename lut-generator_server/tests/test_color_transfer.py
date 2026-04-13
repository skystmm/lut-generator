"""
色彩迁移模块单元测试

测试 color_transfer.py 中的功能：
- Reinhard 色彩迁移算法
- 变换矩阵构建
- LUT 变换构建
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# 添加 src 目录到路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from color_analyzer import ColorAnalyzer, ColorStatistics, AnalysisResult
from color_transfer import (
    TransferConfig,
    TransferResult,
    ReinhardColorTransfer,
    LUTTransformBuilder,
    transfer_colors
)


class TestTransferConfig:
    """测试 TransferConfig 数据类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = TransferConfig()
        assert config.strength == 1.0
        assert config.clip_out_of_gamut is True
        assert config.L_strength is None
        assert config.a_strength is None
        assert config.b_strength is None
    
    def test_custom_strength(self):
        """测试自定义强度"""
        config = TransferConfig(strength=0.5)
        assert config.strength == 0.5
    
    def test_channel_strengths_default(self):
        """测试通道强度（默认）"""
        config = TransferConfig(strength=0.7)
        L_s, a_s, b_s = config.get_channel_strengths()
        assert L_s == 0.7
        assert a_s == 0.7
        assert b_s == 0.7
    
    def test_channel_strengths_custom(self):
        """测试通道强度（自定义）"""
        config = TransferConfig(
            strength=0.5,
            L_strength=0.8,
            a_strength=0.6,
            b_strength=0.4
        )
        L_s, a_s, b_s = config.get_channel_strengths()
        assert L_s == 0.8
        assert a_s == 0.6
        assert b_s == 0.4


class TestReinhardColorTransfer:
    """测试 ReinhardColorTransfer 类"""
    
    @pytest.fixture
    def transfer(self):
        """创建迁移器实例"""
        return ReinhardColorTransfer()
    
    @pytest.fixture
    def test_images(self):
        """创建测试图像"""
        # 源图像（暖色调）
        source = np.zeros((100, 100, 3), dtype=np.uint8)
        source[:, :] = [200, 150, 100]  # 橙色调
        
        # 目标图像（冷色调）
        target = np.zeros((100, 100, 3), dtype=np.uint8)
        target[:, :] = [100, 150, 200]  # 蓝色调
        
        return source, target
    
    def test_compute_statistics(self, transfer, test_images):
        """测试统计特征计算"""
        source, target = test_images
        analyzer = ColorAnalyzer()
        
        source_lab = analyzer.rgb_to_lab(source)
        target_lab = analyzer.rgb_to_lab(target)
        
        source_stats = transfer.compute_statistics(source_lab)
        target_stats = transfer.compute_statistics(target_lab)
        
        # 检查返回类型
        assert isinstance(source_stats, ColorStatistics)
        assert isinstance(target_stats, ColorStatistics)
        
        # 暖色调的 a, b 应该较高
        assert source_stats.mean_a > target_stats.mean_a
        assert source_stats.mean_b > target_stats.mean_b
    
    def test_build_transformation_matrix(self, transfer, test_images):
        """测试变换矩阵构建"""
        source, target = test_images
        analyzer = ColorAnalyzer()
        
        source_lab = analyzer.rgb_to_lab(source)
        target_lab = analyzer.rgb_to_lab(target)
        
        source_stats = transfer.compute_statistics(source_lab)
        target_stats = transfer.compute_statistics(target_lab)
        
        matrix = transfer.build_transformation_matrix(source_stats, target_stats)
        
        # 检查矩阵形状
        assert matrix.shape == (3, 2)
        
        # 每行应该是 [scale, offset]
        for i in range(3):
            assert np.isfinite(matrix[i, 0])
            assert np.isfinite(matrix[i, 1])
    
    def test_transfer(self, transfer, test_images):
        """测试色彩迁移"""
        source, target = test_images
        analyzer = ColorAnalyzer()
        
        source_lab = analyzer.rgb_to_lab(source)
        target_lab = analyzer.rgb_to_lab(target)
        
        result = transfer.transfer(source_lab, target_lab)
        
        # 检查返回类型
        assert isinstance(result, TransferResult)
        
        # 检查结果形状
        assert result.lab_result.shape == target_lab.shape
        assert result.rgb_result.shape == target_lab.shape
        
        # 检查 RGB 值范围
        assert result.rgb_result.min() >= 0
        assert result.rgb_result.max() <= 1.0
        
        # 检查统计信息
        assert isinstance(result.source_stats, ColorStatistics)
        assert isinstance(result.target_stats, ColorStatistics)
        
        # 检查变换参数
        assert 'scale_L' in result.transform_params
        assert 'scale_a' in result.transform_params
        assert 'scale_b' in result.transform_params
    
    def test_transfer_with_strength(self, transfer, test_images):
        """测试不同强度的迁移"""
        source, target = test_images
        analyzer = ColorAnalyzer()
        
        source_lab = analyzer.rgb_to_lab(source)
        target_lab = analyzer.rgb_to_lab(target)
        
        # 强度 0.0（无迁移）
        config_0 = TransferConfig(strength=0.0)
        result_0 = transfer.transfer(source_lab, target_lab, config_0)
        
        # 强度 1.0（完全迁移）
        config_1 = TransferConfig(strength=1.0)
        result_1 = transfer.transfer(source_lab, target_lab, config_1)
        
        # 强度 0.5（部分迁移）
        config_05 = TransferConfig(strength=0.5)
        result_05 = transfer.transfer(source_lab, target_lab, config_05)
        
        # 结果应该不同
        diff_0_1 = np.mean(np.abs(result_0.rgb_result - result_1.rgb_result))
        diff_0_05 = np.mean(np.abs(result_0.rgb_result - result_05.rgb_result))
        diff_05_1 = np.mean(np.abs(result_05.rgb_result - result_1.rgb_result))
        
        # 强度 0 和 1 的差异应该最大
        assert diff_0_1 > diff_0_05
        assert diff_0_1 > diff_05_1
    
    def test_transfer_images(self, transfer, tmp_path):
        """测试从文件迁移"""
        import cv2
        
        # 创建测试图像
        source = np.zeros((100, 100, 3), dtype=np.uint8)
        source[:, :] = [200, 150, 100]
        
        target = np.zeros((100, 100, 3), dtype=np.uint8)
        target[:, :] = [100, 150, 200]
        
        # 保存为 BGR
        source_path = tmp_path / "source.png"
        target_path = tmp_path / "target.png"
        cv2.imwrite(str(source_path), source[:, :, ::-1])
        cv2.imwrite(str(target_path), target[:, :, ::-1])
        
        # 执行迁移
        result = transfer.transfer_images(str(source_path), str(target_path))
        
        assert isinstance(result, TransferResult)
        assert result.rgb_result.shape == (100, 100, 3)
    
    def test_clip_out_of_gamut(self, transfer, test_images):
        """测试色域裁剪"""
        source, target = test_images
        analyzer = ColorAnalyzer()
        
        source_lab = analyzer.rgb_to_lab(source)
        target_lab = analyzer.rgb_to_lab(target)
        
        # 启用裁剪
        config_clip = TransferConfig(clip_out_of_gamut=True)
        result_clip = transfer.transfer(source_lab, target_lab, config_clip)
        
        # 禁用裁剪
        config_no_clip = TransferConfig(clip_out_of_gamut=False)
        result_no_clip = transfer.transfer(source_lab, target_lab, config_no_clip)
        
        # 裁剪后的 Lab 值应该在有效范围内
        assert result_clip.lab_result[:, :, 0].min() >= 0
        assert result_clip.lab_result[:, :, 0].max() <= 100
        assert result_clip.lab_result[:, :, 1].min() >= -128
        assert result_clip.lab_result[:, :, 1].max() <= 127
        assert result_clip.lab_result[:, :, 2].min() >= -128
        assert result_clip.lab_result[:, :, 2].max() <= 127
    
    def test_to_rgb_uint8(self, transfer, test_images):
        """测试 RGB uint8 转换"""
        source, target = test_images
        analyzer = ColorAnalyzer()
        
        source_lab = analyzer.rgb_to_lab(source)
        target_lab = analyzer.rgb_to_lab(target)
        
        result = transfer.transfer(source_lab, target_lab)
        rgb_uint8 = result.to_rgb_uint8()
        
        # 检查类型和范围
        assert rgb_uint8.dtype == np.uint8
        assert rgb_uint8.min() >= 0
        assert rgb_uint8.max() <= 255


class TestLUTTransformBuilder:
    """测试 LUTTransformBuilder 类"""
    
    def test_build_transform_func(self):
        """测试构建变换函数"""
        # 创建统计信息
        source_stats = ColorStatistics(
            mean_L=50.0, mean_a=30.0, mean_b=20.0,
            std_L=15.0, std_a=10.0, std_b=8.0,
            var_L=225.0, var_a=100.0, var_b=64.0
        )
        
        target_stats = ColorStatistics(
            mean_L=60.0, mean_a=10.0, mean_b=-10.0,
            std_L=20.0, std_a=15.0, std_b=12.0,
            var_L=400.0, var_a=225.0, var_b=144.0
        )
        
        builder = LUTTransformBuilder(source_stats, target_stats, strength=1.0)
        transform_func = builder.build_transform_func()
        
        # 测试变换函数
        test_rgb = np.array([0.5, 0.5, 0.5])
        result_rgb = transform_func(test_rgb)
        
        # 检查结果
        assert result_rgb.shape == (3,)
        assert result_rgb.min() >= 0
        assert result_rgb.max() <= 1.0
    
    def test_transform_batch(self):
        """测试批量变换"""
        source_stats = ColorStatistics(
            mean_L=50.0, mean_a=30.0, mean_b=20.0,
            std_L=15.0, std_a=10.0, std_b=8.0,
            var_L=225.0, var_a=100.0, var_b=64.0
        )
        
        target_stats = ColorStatistics(
            mean_L=60.0, mean_a=10.0, mean_b=-10.0,
            std_L=20.0, std_a=15.0, std_b=12.0,
            var_L=400.0, var_a=225.0, var_b=144.0
        )
        
        builder = LUTTransformBuilder(source_stats, target_stats, strength=1.0)
        transform_func = builder.build_transform_func()
        
        # 测试多个颜色
        test_rgbs = np.array([
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [1.0, 1.0, 1.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]
        ])
        
        results = []
        for rgb in test_rgbs:
            result = transform_func(rgb)
            results.append(result)
        
        # 检查所有结果
        for result in results:
            assert result.shape == (3,)
            assert result.min() >= 0
            assert result.max() <= 1.0


class TestTransferColorsFunction:
    """测试便捷函数 transfer_colors"""
    
    def test_transfer_colors(self, tmp_path):
        """测试色彩迁移函数"""
        import cv2
        
        # 创建测试图像
        source = np.zeros((100, 100, 3), dtype=np.uint8)
        source[:, :] = [200, 150, 100]
        
        target = np.zeros((100, 100, 3), dtype=np.uint8)
        target[:, :] = [100, 150, 200]
        
        # 保存
        source_path = tmp_path / "source.png"
        target_path = tmp_path / "target.png"
        cv2.imwrite(str(source_path), source[:, :, ::-1])
        cv2.imwrite(str(target_path), target[:, :, ::-1])
        
        # 执行迁移
        rgb_result, params = transfer_colors(
            str(source_path),
            str(target_path),
            strength=0.8
        )
        
        # 检查结果
        assert rgb_result.shape == (100, 100, 3)
        assert rgb_result.min() >= 0
        assert rgb_result.max() <= 1.0
        
        # 检查参数
        assert 'strength' in params
        assert params['strength'] == 0.8


class TestReinhardAlgorithm:
    """测试 Reinhard 算法的正确性"""
    
    def test_identity_transfer(self):
        """测试相同图像的迁移（应该是恒等变换）"""
        transfer = ReinhardColorTransfer()
        analyzer = ColorAnalyzer()
        
        # 创建测试图像
        test_img = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
        test_lab = analyzer.rgb_to_lab(test_img)
        
        # 源和目标相同
        result = transfer.transfer(test_lab, test_lab)
        
        # 结果应该非常接近原图
        diff = np.mean(np.abs(result.rgb_result - analyzer.lab_to_rgb(test_lab)))
        assert diff < 5  # 允许小的数值误差
    
    def test_gray_preservation(self):
        """测试灰色保持"""
        transfer = ReinhardColorTransfer()
        analyzer = ColorAnalyzer()
        
        # 源图像：暖色调
        source = np.zeros((100, 100, 3), dtype=np.uint8)
        source[:, :] = [200, 150, 100]
        
        # 目标图像：灰色
        target = np.zeros((100, 100, 3), dtype=np.uint8)
        target[:, :] = [128, 128, 128]
        
        source_lab = analyzer.rgb_to_lab(source)
        target_lab = analyzer.rgb_to_lab(target)
        
        result = transfer.transfer(source_lab, target_lab)
        
        # 灰色目标迁移后应该仍然接近灰色（a, b 接近 0）
        result_lab = analyzer.rgb_to_lab((result.rgb_result * 255).astype(np.uint8))
        
        # a, b 的标准差应该很小
        assert np.std(result_lab[:, :, 1]) < 5
        assert np.std(result_lab[:, :, 2]) < 5
    
    def test_mean_matching(self):
        """测试均值匹配"""
        transfer = ReinhardColorTransfer()
        analyzer = ColorAnalyzer()
        
        # 源图像：红色调
        source = np.zeros((100, 100, 3), dtype=np.uint8)
        source[:, :] = [200, 50, 50]
        
        # 目标图像：蓝色调
        target = np.zeros((100, 100, 3), dtype=np.uint8)
        target[:, :] = [50, 50, 200]
        
        source_lab = analyzer.rgb_to_lab(source)
        target_lab = analyzer.rgb_to_lab(target)
        
        result = transfer.transfer(source_lab, target_lab)
        
        # 迁移后的均值应该接近目标
        result_stats = transfer.compute_statistics(result.lab_result)
        target_stats = transfer.compute_statistics(target_lab)
        
        # 允许一定误差
        assert abs(result_stats.mean_L - target_stats.mean_L) < 10
        assert abs(result_stats.mean_a - target_stats.mean_a) < 15
        assert abs(result_stats.mean_b - target_stats.mean_b) < 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

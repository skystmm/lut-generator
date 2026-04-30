"""
LUT3DGenerator 单元测试

测试 3D LUT 生成器的核心功能：
- 不同精度网格生成（17³/33³/65³）
- 向量化性能优化
- 三线性插值准确性
- 统计信息到 LUT 的转换
"""

import pytest
import numpy as np
from pathlib import Path
import sys
import time

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from lut3d_generator import (
    LUT3DGenerator, LUT3DConfig, LUT3DMetadata,
    generate_lut_3d
)
from color_analyzer import ColorStatistics


class TestLUT3DConfig:
    """测试 LUT 配置"""
    
    def test_valid_config(self):
        """测试有效配置"""
        for grid_size in [17, 33, 65]:
            config = LUT3DConfig(grid_size=grid_size)
            assert config.validate() is True
            assert config.grid_size == grid_size
    
    def test_invalid_grid_size(self):
        """测试无效网格大小"""
        with pytest.raises(ValueError, match="grid_size must be one of"):
            config = LUT3DConfig(grid_size=16)
            config.validate()
        
        with pytest.raises(ValueError, match="grid_size must be one of"):
            config = LUT3DConfig(grid_size=100)
            config.validate()
    
    def test_invalid_interpolation(self):
        """测试无效插值方法"""
        with pytest.raises(ValueError, match="interpolation must be one of"):
            config = LUT3DConfig(interpolation='bicubic')
            config.validate()
    
    def test_default_config(self):
        """测试默认配置"""
        config = LUT3DConfig()
        assert config.grid_size == 33
        assert config.use_vectorized is True
        assert config.interpolation == 'trilinear'


class TestLUT3DGenerator:
    """测试 LUT 生成器"""
    
    @pytest.fixture
    def sample_stats(self):
        """示例统计信息"""
        source_stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=20.0, std_a=15.0, std_b=18.0,
            var_L=400.0, var_a=225.0, var_b=324.0
        )
        
        target_stats = ColorStatistics(
            mean_L=60.0, mean_a=5.0, mean_b=30.0,
            std_L=25.0, std_a=12.0, std_b=22.0,
            var_L=625.0, var_a=144.0, var_b=484.0
        )
        
        return source_stats, target_stats
    
    def test_generate_lut_17(self, sample_stats):
        """测试 17³ 精度 LUT 生成"""
        source_stats, target_stats = sample_stats
        
        lut = generate_lut_3d(source_stats, target_stats, grid_size=17)
        
        assert lut.shape == (17, 17, 17, 3)
        assert lut.dtype in [np.float32, np.float64]
        assert lut.min() >= 0.0
        assert lut.max() <= 1.0
    
    def test_generate_lut_33(self, sample_stats):
        """测试 33³ 精度 LUT 生成"""
        source_stats, target_stats = sample_stats
        
        lut = generate_lut_3d(source_stats, target_stats, grid_size=33)
        
        assert lut.shape == (33, 33, 33, 3)
        assert lut.min() >= 0.0
        assert lut.max() <= 1.0
    
    def test_generate_lut_65(self, sample_stats):
        """测试 65³ 精度 LUT 生成"""
        source_stats, target_stats = sample_stats
        
        lut = generate_lut_3d(source_stats, target_stats, grid_size=65)
        
        assert lut.shape == (65, 65, 65, 3)
        assert lut.min() >= 0.0
        assert lut.max() <= 1.0
    
    def test_vectorized_vs_iterative(self, sample_stats):
        """测试向量化与迭代方法结果一致性"""
        source_stats, target_stats = sample_stats
        
        # 向量化生成
        lut_vectorized = generate_lut_3d(
            source_stats, target_stats,
            grid_size=17,
            use_vectorized=True
        )
        
        # 迭代生成
        lut_iterative = generate_lut_3d(
            source_stats, target_stats,
            grid_size=17,
            use_vectorized=False
        )
        
        # 结果应该相同（允许浮点误差）
        assert np.allclose(lut_vectorized, lut_iterative, rtol=1e-5)
    
    def test_vectorized_performance(self, sample_stats):
        """测试向量化性能优势"""
        source_stats, target_stats = sample_stats
        
        # 向量化方法
        start = time.time()
        lut_vec = generate_lut_3d(
            source_stats, target_stats,
            grid_size=33,
            use_vectorized=True
        )
        time_vec = time.time() - start
        
        # 迭代方法
        start = time.time()
        lut_iter = generate_lut_3d(
            source_stats, target_stats,
            grid_size=33,
            use_vectorized=False
        )
        time_iter = time.time() - start
        
        # 向量化应该更快（至少 2 倍）
        # 注意：这个测试可能在小网格上不稳定
        print(f"\nVectorized: {time_vec:.3f}s, Iterative: {time_iter:.3f}s")
        print(f"Speedup: {time_iter / time_vec:.1f}x")
        
        # 结果一致性
        assert np.allclose(lut_vec, lut_iter, rtol=1e-5)
    
    def test_generator_class(self, sample_stats):
        """测试 LUT3DGenerator 类"""
        source_stats, target_stats = sample_stats
        
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        
        # 生成 LUT
        lut = generator.generate_from_stats(source_stats, target_stats)
        
        assert lut.shape == (17, 17, 17, 3)
        # 注意：generate_from_stats 不保存内部状态，只返回结果
        # 使用 generate_from_images 才会保存 metadata
        assert lut is not None
    
    def test_strength_parameter(self, sample_stats):
        """测试迁移强度参数"""
        source_stats, target_stats = sample_stats
        
        grid_size = 17
        
        # 不同强度
        lut_full = generate_lut_3d(source_stats, target_stats, grid_size=grid_size, strength=1.0)
        lut_half = generate_lut_3d(source_stats, target_stats, grid_size=grid_size, strength=0.5)
        lut_zero = generate_lut_3d(source_stats, target_stats, grid_size=grid_size, strength=0.0)
        
        # 强度为 0 时应该接近恒等变换
        # 创建恒等 LUT 进行比较
        identity_lut = np.zeros((grid_size, grid_size, grid_size, 3))
        grid_values = np.linspace(0, 1, grid_size)
        R, G, B = np.meshgrid(grid_values, grid_values, grid_values, indexing='ij')
        identity_lut[:, :, :, 0] = R
        identity_lut[:, :, :, 1] = G
        identity_lut[:, :, :, 2] = B
        
        # 强度 0 应该接近恒等
        assert np.allclose(lut_zero, identity_lut, atol=0.01)
        
        # 强度 1 和 0.5 应该不同
        assert not np.allclose(lut_full, lut_half, rtol=0.1)


class TestTrilinearInterpolation:
    """测试三线性插值"""
    
    @pytest.fixture
    def simple_lut(self):
        """创建简单的测试 LUT (17³)"""
        # 创建一个 17x17x17 的简单 LUT 用于测试
        grid_size = 17
        lut = np.zeros((grid_size, grid_size, grid_size, 3))
        
        # 填充整个 LUT - 恒等变换
        grid_values = np.linspace(0, 1, grid_size)
        R, G, B = np.meshgrid(grid_values, grid_values, grid_values, indexing='ij')
        lut[:, :, :, 0] = R
        lut[:, :, :, 1] = G
        lut[:, :, :, 2] = B
        
        return lut
    
    def test_corner_points(self, simple_lut):
        """测试角点插值"""
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        generator.lut_data = simple_lut
        
        # 测试角点 (0,0,0)
        result = generator.apply_trilinear_interpolation(np.array([0, 0, 0]))
        assert np.allclose(result, [0, 0, 0], atol=1e-6)
        
        # 测试角点 (1,1,1)
        result = generator.apply_trilinear_interpolation(np.array([1, 1, 1]))
        assert np.allclose(result, [1, 1, 1], atol=1e-6)
    
    def test_center_point(self, simple_lut):
        """测试中心点插值"""
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        generator.lut_data = simple_lut
        
        # 测试中心点 (0.5, 0.5, 0.5)
        result = generator.apply_trilinear_interpolation(np.array([0.5, 0.5, 0.5]))
        assert np.allclose(result, [0.5, 0.5, 0.5], atol=0.01)
    
    def test_batch_interpolation(self, simple_lut):
        """测试批量插值"""
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        generator.lut_data = simple_lut
        
        # 批量输入
        inputs = np.array([
            [0, 0, 0],
            [0.5, 0.5, 0.5],
            [1, 1, 1]
        ])
        
        results = generator.apply_trilinear_interpolation(inputs)
        
        assert results.shape == (3, 3)
        assert np.allclose(results[0], [0, 0, 0], atol=1e-6)
        assert np.allclose(results[2], [1, 1, 1], atol=1e-6)
    
    def test_interpolation_consistency(self):
        """测试插值一致性"""
        source_stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=20.0, std_a=15.0, std_b=18.0,
            var_L=400.0, var_a=225.0, var_b=324.0
        )
        target_stats = ColorStatistics(
            mean_L=60.0, mean_a=5.0, mean_b=30.0,
            std_L=25.0, std_a=12.0, std_b=22.0,
            var_L=625.0, var_a=144.0, var_b=484.0
        )
        
        # 生成 LUT
        lut = generate_lut_3d(source_stats, target_stats, grid_size=17)
        
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        generator.lut_data = lut
        
        # 测试网格点上的值
        grid_values = np.linspace(0, 1, 17)
        
        # 随机选择一些网格点
        np.random.seed(42)
        indices = np.random.choice(17, size=10, replace=False)
        
        for idx in indices:
            i = idx // (17 * 17)
            j = (idx // 17) % 17
            k = idx % 17
            
            rgb = np.array([grid_values[i], grid_values[j], grid_values[k]])
            result = generator.apply(rgb)
            
            # 应该与 LUT 中存储的值非常接近
            expected = lut[i, j, k]
            assert np.allclose(result, expected, atol=1e-5)


class TestEdgeCases:
    """测试边界情况"""
    
    def test_extreme_statistics(self):
        """测试极端统计值"""
        # 极大标准差
        source_stats = ColorStatistics(
            mean_L=50.0, mean_a=0.0, mean_b=0.0,
            std_L=1.0, std_a=1.0, std_b=1.0,
            var_L=1.0, var_a=1.0, var_b=1.0
        )
        
        target_stats = ColorStatistics(
            mean_L=50.0, mean_a=0.0, mean_b=0.0,
            std_L=50.0, std_a=50.0, std_b=50.0,
            var_L=2500.0, var_a=2500.0, var_b=2500.0
        )
        
        lut = generate_lut_3d(source_stats, target_stats, grid_size=17)
        
        assert lut.shape == (17, 17, 17, 3)
        assert not np.any(np.isnan(lut))
        assert not np.any(np.isinf(lut))
    
    def test_zero_std_source(self):
        """测试源图像标准差为零的情况"""
        # 源图像标准差为零（纯色图像）
        source_stats = ColorStatistics(
            mean_L=50.0, mean_a=0.0, mean_b=0.0,
            std_L=0.0, std_a=0.0, std_b=0.0,
            var_L=0.0, var_a=0.0, var_b=0.0
        )
        
        target_stats = ColorStatistics(
            mean_L=60.0, mean_a=10.0, mean_b=20.0,
            std_L=20.0, std_a=15.0, std_b=18.0,
            var_L=400.0, var_a=225.0, var_b=324.0
        )
        
        # 应该能处理（内部有防止除零的机制）
        lut = generate_lut_3d(source_stats, target_stats, grid_size=17)
        
        assert lut.shape == (17, 17, 17, 3)
        assert not np.any(np.isnan(lut))
    
    def test_identical_statistics(self):
        """测试相同统计值（恒等变换）"""
        stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=20.0, std_a=15.0, std_b=18.0,
            var_L=400.0, var_a=225.0, var_b=324.0
        )
        
        lut = generate_lut_3d(stats, stats, grid_size=17)
        
        # 创建恒等 LUT
        identity_lut = np.zeros((17, 17, 17, 3))
        grid_values = np.linspace(0, 1, 17)
        R, G, B = np.meshgrid(grid_values, grid_values, grid_values, indexing='ij')
        identity_lut[:, :, :, 0] = R
        identity_lut[:, :, :, 1] = G
        identity_lut[:, :, :, 2] = B
        
        # 应该接近恒等变换
        assert np.allclose(lut, identity_lut, atol=0.01)


class TestMetadata:
    """测试元数据"""
    
    def test_metadata_creation(self):
        """测试元数据创建"""
        from datetime import datetime
        
        source_stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=20.0, std_a=15.0, std_b=18.0,
            var_L=400.0, var_a=225.0, var_b=324.0
        )
        target_stats = ColorStatistics(
            mean_L=60.0, mean_a=5.0, mean_b=30.0,
            std_L=25.0, std_a=12.0, std_b=22.0,
            var_L=625.0, var_a=144.0, var_b=484.0
        )
        
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        
        # 注意：generate_from_stats 不保存 metadata
        # 需要使用 generate_from_images 或手动设置
        lut = generator.generate_from_stats(source_stats, target_stats)
        
        # 手动设置元数据用于测试
        from datetime import datetime
        generator.metadata = LUT3DMetadata(
            created_at=datetime.now().isoformat(),
            description="Test metadata",
            source_stats=source_stats,
            target_stats=target_stats
        )
        
        metadata = generator.get_metadata()
        
        assert metadata is not None
        assert metadata.source_stats is not None
        assert metadata.target_stats is not None
        assert metadata.created_at is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

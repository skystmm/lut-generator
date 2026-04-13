"""
特征融合模块单元测试 - Test Feature Fusion

测试覆盖：
- FusionConfig 配置类
- 特征融合算法
- 权重处理
- 融合策略（平均/加权/中值）
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import os
import json

# 导入被测试模块
from feature_fusion import (
    FusionConfig,
    FusedFeatures,
    FeatureFusion,
    fuse_features,
    create_weight_config
)
from color_analyzer import (
    AnalysisResult,
    ColorStatistics,
    ColorHistogram,
    ColorDistribution
)


class TestFusionConfig:
    """测试 FusionConfig 类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = FusionConfig()
        
        assert config.weights == []
        assert config.strategy == 'weighted_average'
        assert config.normalize_weights is True
        assert config.histogram_method == 'average'
        assert config.distribution_method == 'average'
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = FusionConfig(
            weights=[2.0, 1.0, 1.0],
            strategy='equal_average',
            normalize_weights=False,
            histogram_method='weighted_average',
            distribution_method='union'
        )
        
        assert config.weights == [2.0, 1.0, 1.0]
        assert config.strategy == 'equal_average'
        assert config.normalize_weights is False
        assert config.histogram_method == 'weighted_average'
        assert config.distribution_method == 'union'
    
    def test_validate_success(self):
        """测试验证成功"""
        config = FusionConfig(
            weights=[1.0, 1.0],
            strategy='weighted_average'
        )
        
        assert config.validate(num_images=2) is True
    
    def test_validate_wrong_weights_length(self):
        """测试验证失败 - 权重数量不匹配"""
        config = FusionConfig(
            weights=[1.0, 1.0, 1.0],
            strategy='weighted_average'
        )
        
        assert config.validate(num_images=2) is False
    
    def test_validate_invalid_strategy(self):
        """测试验证失败 - 无效策略"""
        config = FusionConfig(strategy='invalid_strategy')
        
        assert config.validate(num_images=2) is False
    
    def test_get_normalized_weights_equal(self):
        """测试获取归一化权重 - 等权"""
        config = FusionConfig()
        
        weights = config.get_normalized_weights(num_images=3)
        
        assert len(weights) == 3
        assert all(abs(w - 1/3) < 0.001 for w in weights)
    
    def test_get_normalized_weights_custom(self):
        """测试获取归一化权重 - 自定义"""
        config = FusionConfig(weights=[2.0, 1.0, 1.0])
        
        weights = config.get_normalized_weights(num_images=3)
        
        assert len(weights) == 3
        assert abs(weights[0] - 0.5) < 0.001  # 2/4
        assert abs(weights[1] - 0.25) < 0.001  # 1/4
        assert abs(weights[2] - 0.25) < 0.001  # 1/4
    
    def test_get_normalized_weights_mismatch(self):
        """测试获取归一化权重 - 数量不匹配"""
        config = FusionConfig(weights=[1.0, 1.0])
        
        with pytest.raises(ValueError):
            config.get_normalized_weights(num_images=3)
    
    def test_to_dict(self):
        """测试转换为字典"""
        config = FusionConfig(
            weights=[2.0, 1.0],
            strategy='weighted_average'
        )
        
        result = config.to_dict()
        
        assert result['weights'] == [2.0, 1.0]
        assert result['strategy'] == 'weighted_average'
        assert result['normalize_weights'] is True
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            'weights': [2.0, 1.0, 1.0],
            'strategy': 'median',
            'normalize_weights': False,
            'histogram_method': 'weighted_average',
            'distribution_method': 'intersection'
        }
        
        config = FusionConfig.from_dict(data)
        
        assert config.weights == [2.0, 1.0, 1.0]
        assert config.strategy == 'median'
        assert config.normalize_weights is False
    
    def test_save_and_load(self, tmp_path):
        """测试保存和加载配置"""
        config = FusionConfig(
            weights=[3.0, 2.0, 1.0],
            strategy='weighted_average'
        )
        
        config_path = tmp_path / 'config.json'
        
        # 保存
        config.save(config_path)
        
        # 加载
        loaded_config = FusionConfig.load(config_path)
        
        assert loaded_config.weights == config.weights
        assert loaded_config.strategy == config.strategy


class TestFusedFeatures:
    """测试 FusedFeatures 类"""
    
    @pytest.fixture
    def sample_statistics(self):
        """创建示例统计特征"""
        return ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=15.0, std_a=5.0, std_b=8.0,
            var_L=225.0, var_a=25.0, var_b=64.0
        )
    
    @pytest.fixture
    def sample_histogram(self):
        """创建示例直方图"""
        bins = 256
        return ColorHistogram(
            L_hist=np.ones(bins) / bins,
            a_hist=np.ones(bins) / bins,
            b_hist=np.ones(bins) / bins,
            bins=bins
        )
    
    @pytest.fixture
    def sample_distribution(self):
        """创建示例分布特征"""
        return ColorDistribution(
            L_range=(0.0, 100.0),
            a_range=(-50.0, 50.0),
            b_range=(-50.0, 50.0),
            gamut_coverage=25.0,
            color_entropy=5.0,
            dominant_color=(50.0, 10.0, 20.0)
        )
    
    @pytest.fixture
    def sample_config(self):
        """创建示例配置"""
        return FusionConfig(strategy='weighted_average')
    
    def test_fused_features_creation(
        self, 
        sample_statistics, 
        sample_histogram, 
        sample_distribution,
        sample_config
    ):
        """测试 FusedFeatures 创建"""
        fused = FusedFeatures(
            statistics=sample_statistics,
            histogram=sample_histogram,
            distribution=sample_distribution,
            config=sample_config,
            num_images=3,
            weights=[0.5, 0.3, 0.2]
        )
        
        assert fused.num_images == 3
        assert len(fused.weights) == 3
        assert fused.statistics == sample_statistics
    
    def test_to_dict(
        self, 
        sample_statistics, 
        sample_histogram, 
        sample_distribution,
        sample_config
    ):
        """测试转换为字典"""
        fused = FusedFeatures(
            statistics=sample_statistics,
            histogram=sample_histogram,
            distribution=sample_distribution,
            config=sample_config,
            num_images=3,
            weights=[0.5, 0.3, 0.2]
        )
        
        result = fused.to_dict()
        
        assert 'statistics' in result
        assert 'histogram' in result
        assert 'distribution' in result
        assert 'config' in result
        assert result['num_images'] == 3
    
    def test_to_analysis_result(
        self, 
        sample_statistics, 
        sample_histogram, 
        sample_distribution,
        sample_config
    ):
        """测试转换为 AnalysisResult"""
        fused = FusedFeatures(
            statistics=sample_statistics,
            histogram=sample_histogram,
            distribution=sample_distribution,
            config=sample_config,
            num_images=3,
            weights=[0.5, 0.3, 0.2]
        )
        
        result = fused.to_analysis_result()
        
        assert isinstance(result, AnalysisResult)
        assert result.statistics == sample_statistics
        assert result.histogram == sample_histogram
        assert result.distribution == sample_distribution


class TestFeatureFusion:
    """测试 FeatureFusion 类"""
    
    @pytest.fixture
    def sample_results(self):
        """创建示例分析结果列表"""
        results = []
        
        for i in range(3):
            stats = ColorStatistics(
                mean_L=50.0 + i * 5,
                mean_a=10.0 + i * 2,
                mean_b=20.0 + i * 3,
                std_L=15.0,
                std_a=5.0,
                std_b=8.0,
                var_L=225.0,
                var_a=25.0,
                var_b=64.0
            )
            
            bins = 256
            hist = ColorHistogram(
                L_hist=np.ones(bins) / bins,
                a_hist=np.ones(bins) / bins,
                b_hist=np.ones(bins) / bins,
                bins=bins
            )
            
            dist = ColorDistribution(
                L_range=(0.0 + i * 5, 100.0 - i * 5),
                a_range=(-50.0 + i * 5, 50.0 - i * 5),
                b_range=(-50.0 + i * 5, 50.0 - i * 5),
                gamut_coverage=25.0 + i * 2,
                color_entropy=5.0 + i * 0.5,
                dominant_color=(50.0 + i * 5, 10.0 + i * 2, 20.0 + i * 3)
            )
            
            result = AnalysisResult(
                statistics=stats,
                histogram=hist,
                distribution=dist,
                image_shape=(100, 100, 3)
            )
            
            results.append(result)
        
        return results
    
    def test_fuse_empty_results(self):
        """测试融合空结果"""
        fusion = FeatureFusion()
        
        with pytest.raises(ValueError, match="No results to fuse"):
            fusion.fuse([])
    
    def test_fuse_equal_weights(self, sample_results):
        """测试等权融合"""
        config = FusionConfig(strategy='equal_average')
        fusion = FeatureFusion(config)
        
        fused = fusion.fuse(sample_results)
        
        # 检查权重是否归一化
        assert len(fused.weights) == 3
        assert abs(sum(fused.weights) - 1.0) < 0.001
        
        # 检查均值是否为平均值
        expected_mean_L = np.mean([r.statistics.mean_L for r in sample_results])
        assert abs(fused.statistics.mean_L - expected_mean_L) < 0.01
    
    def test_fuse_custom_weights(self, sample_results):
        """测试自定义权重融合"""
        weights = [0.5, 0.3, 0.2]
        config = FusionConfig(weights=weights, strategy='weighted_average')
        fusion = FeatureFusion(config)
        
        fused = fusion.fuse(sample_results)
        
        # 检查权重
        assert fused.weights == weights
        
        # 检查加权均值
        expected_mean_L = sum(
            r.statistics.mean_L * w 
            for r, w in zip(sample_results, weights)
        )
        assert abs(fused.statistics.mean_L - expected_mean_L) < 0.01
    
    def test_fuse_median_strategy(self, sample_results):
        """测试中值融合策略"""
        config = FusionConfig(strategy='median')
        fusion = FeatureFusion(config)
        
        fused = fusion.fuse(sample_results)
        
        # 检查中值
        expected_mean_L = np.median([r.statistics.mean_L for r in sample_results])
        assert abs(fused.statistics.mean_L - expected_mean_L) < 0.01
    
    def test_fuse_wrong_weights_length(self, sample_results):
        """测试权重数量不匹配"""
        fusion = FeatureFusion()
        
        with pytest.raises(ValueError):
            fusion.fuse(sample_results, weights=[0.5, 0.5])
    
    def test_fuse_histograms(self, sample_results):
        """测试直方图融合"""
        fusion = FeatureFusion()
        
        fused = fusion.fuse(sample_results)
        
        # 检查直方图是否归一化
        assert abs(fused.histogram.L_hist.sum() - 1.0) < 0.001
        assert abs(fused.histogram.a_hist.sum() - 1.0) < 0.001
        assert abs(fused.histogram.b_hist.sum() - 1.0) < 0.001
    
    def test_fuse_distributions_union(self, sample_results):
        """测试分布融合 - 并集"""
        config = FusionConfig(distribution_method='union')
        fusion = FeatureFusion(config)
        
        fused = fusion.fuse(sample_results)
        
        # 并集应该取最大范围
        expected_L_min = min(r.distribution.L_range[0] for r in sample_results)
        expected_L_max = max(r.distribution.L_range[1] for r in sample_results)
        
        assert fused.distribution.L_range[0] == expected_L_min
        assert fused.distribution.L_range[1] == expected_L_max
    
    def test_fuse_distributions_intersection(self, sample_results):
        """测试分布融合 - 交集"""
        config = FusionConfig(distribution_method='intersection')
        fusion = FeatureFusion(config)
        
        fused = fusion.fuse(sample_results)
        
        # 交集应该取最小范围
        expected_L_min = max(r.distribution.L_range[0] for r in sample_results)
        expected_L_max = min(r.distribution.L_range[1] for r in sample_results)
        
        assert fused.distribution.L_range[0] == expected_L_min
        assert fused.distribution.L_range[1] == expected_L_max


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    @pytest.fixture
    def sample_results(self):
        """创建示例分析结果"""
        results = []
        
        for i in range(2):
            stats = ColorStatistics(
                mean_L=50.0 + i * 10,
                mean_a=10.0,
                mean_b=20.0,
                std_L=15.0,
                std_a=5.0,
                std_b=8.0,
                var_L=225.0,
                var_a=25.0,
                var_b=64.0
            )
            
            bins = 256
            hist = ColorHistogram(
                L_hist=np.ones(bins) / bins,
                a_hist=np.ones(bins) / bins,
                b_hist=np.ones(bins) / bins,
                bins=bins
            )
            
            dist = ColorDistribution(
                L_range=(0.0, 100.0),
                a_range=(-50.0, 50.0),
                b_range=(-50.0, 50.0),
                gamut_coverage=25.0,
                color_entropy=5.0,
                dominant_color=(50.0, 10.0, 20.0)
            )
            
            result = AnalysisResult(
                statistics=stats,
                histogram=hist,
                distribution=dist,
                image_shape=(100, 100, 3)
            )
            
            results.append(result)
        
        return results
    
    def test_fuse_features_default(self, sample_results):
        """测试便捷函数 - 默认参数"""
        fused = fuse_features(sample_results)
        
        assert isinstance(fused, FusedFeatures)
        assert fused.num_images == 2
    
    def test_fuse_features_with_weights(self, sample_results):
        """测试便捷函数 - 带权重"""
        weights = [0.7, 0.3]
        fused = fuse_features(sample_results, weights=weights)
        
        assert fused.weights == weights
    
    def test_fuse_features_with_strategy(self, sample_results):
        """测试便捷函数 - 带策略"""
        fused = fuse_features(sample_results, strategy='median')
        
        assert fused.config.strategy == 'median'
    
    def test_create_weight_config_equal(self):
        """测试创建权重配置 - 等权"""
        paths = ['img1.jpg', 'img2.jpg', 'img3.jpg']
        config = create_weight_config(paths)
        
        assert config.weights == []
        assert config.strategy == 'equal_average'
    
    def test_create_weight_config_custom(self):
        """测试创建权重配置 - 自定义"""
        paths = ['img1.jpg', 'img2.jpg', 'img3.jpg']
        weights = [3.0, 2.0, 1.0]
        
        config = create_weight_config(paths, weight_values=weights)
        
        assert config.weights == weights
        assert config.strategy == 'weighted_average'
    
    def test_create_weight_config_mismatch(self):
        """测试创建权重配置 - 数量不匹配"""
        paths = ['img1.jpg', 'img2.jpg']
        weights = [1.0, 2.0, 3.0]
        
        with pytest.raises(ValueError):
            create_weight_config(paths, weight_values=weights)


class TestEdgeCases:
    """测试边界情况"""
    
    def test_single_image_fusion(self):
        """测试单图融合"""
        stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=15.0, std_a=5.0, std_b=8.0,
            var_L=225.0, var_a=25.0, var_b=64.0
        )
        
        bins = 256
        hist = ColorHistogram(
            L_hist=np.ones(bins) / bins,
            a_hist=np.ones(bins) / bins,
            b_hist=np.ones(bins) / bins,
            bins=bins
        )
        
        dist = ColorDistribution(
            L_range=(0.0, 100.0),
            a_range=(-50.0, 50.0),
            b_range=(-50.0, 50.0),
            gamut_coverage=25.0,
            color_entropy=5.0,
            dominant_color=(50.0, 10.0, 20.0)
        )
        
        result = AnalysisResult(
            statistics=stats,
            histogram=hist,
            distribution=dist,
            image_shape=(100, 100, 3)
        )
        
        fusion = FeatureFusion()
        fused = fusion.fuse([result])
        
        # 单图融合应该保持原值
        assert fused.statistics.mean_L == 50.0
        assert fused.num_images == 1
    
    def test_zero_weights(self):
        """测试零权重处理"""
        stats = ColorStatistics(
            mean_L=50.0, mean_a=10.0, mean_b=20.0,
            std_L=15.0, std_a=5.0, std_b=8.0,
            var_L=225.0, var_a=25.0, var_b=64.0
        )
        
        bins = 256
        hist = ColorHistogram(
            L_hist=np.ones(bins) / bins,
            a_hist=np.ones(bins) / bins,
            b_hist=np.ones(bins) / bins,
            bins=bins
        )
        
        dist = ColorDistribution(
            L_range=(0.0, 100.0),
            a_range=(-50.0, 50.0),
            b_range=(-50.0, 50.0),
            gamut_coverage=25.0,
            color_entropy=5.0,
            dominant_color=(50.0, 10.0, 20.0)
        )
        
        result1 = AnalysisResult(statistics=stats, histogram=hist, distribution=dist, image_shape=(100, 100, 3))
        result2 = AnalysisResult(statistics=stats, histogram=hist, distribution=dist, image_shape=(100, 100, 3))
        
        # 零权重应该回退到等权
        config = FusionConfig(weights=[0.0, 0.0])
        fusion = FeatureFusion(config)
        
        fused = fusion.fuse([result1, result2])
        
        # 应该使用等权
        assert abs(fused.weights[0] - 0.5) < 0.01
        assert abs(fused.weights[1] - 0.5) < 0.01


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

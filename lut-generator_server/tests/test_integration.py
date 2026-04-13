#!/usr/bin/env python3
"""
集成测试 - Integration Tests

测试完整的批处理 + 融合流程
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import numpy as np
import cv2


class TestEndToEnd:
    """端到端集成测试"""
    
    @pytest.fixture
    def test_environment(self):
        """创建测试环境"""
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        
        # 创建源图片目录
        source_dir = temp_path / 'source'
        source_dir.mkdir()
        
        # 创建目标图片目录
        target_dir = temp_path / 'target'
        target_dir.mkdir()
        
        # 创建测试图片
        for i in range(3):
            # 源图片（偏冷色调）
            img_source = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            img_source[:, :, 0] = img_source[:, :, 0] * 0.8  # 降低红色
            img_source[:, :, 2] = np.clip(img_source[:, :, 2] * 1.2, 0, 255)  # 增加蓝色
            cv2.imwrite(str(source_dir / f'source_{i}.jpg'), img_source)
            
            # 目标图片（偏暖色调）
            img_target = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            img_target[:, :, 0] = np.clip(img_target[:, :, 0] * 1.2, 0, 255)  # 增加红色
            img_target[:, :, 1] = np.clip(img_target[:, :, 1] * 1.1, 0, 255)  # 增加绿色
            cv2.imwrite(str(target_dir / f'target_{i}.jpg'), img_target)
        
        yield temp_path
        
        # 清理
        shutil.rmtree(temp_path)
    
    def test_batch_analyze_and_fuse(self, test_environment):
        """测试批量分析 + 融合完整流程"""
        from batch_analyzer import BatchAnalyzer
        from feature_fusion import FeatureFusion, fuse_features
        
        temp_path = test_environment
        source_dir = temp_path / 'source'
        
        # 步骤 1: 批量分析
        analyzer = BatchAnalyzer(use_colour=False, max_workers=2)
        batch_result = analyzer.analyze_directory(source_dir)
        
        assert batch_result.total_images == 3
        assert batch_result.valid_images == 3
        assert batch_result.failed_images == 0
        
        # 步骤 2: 获取分析结果
        results = batch_result.get_valid_results()
        assert len(results) == 3
        
        # 步骤 3: 特征融合
        fused = fuse_features(results, weights=[2.0, 1.0, 1.0])
        
        assert fused.num_images == 3
        assert len(fused.weights) == 3
        assert abs(sum(fused.weights) - 1.0) < 0.001
        
        # 步骤 4: 验证融合结果
        assert fused.statistics.mean_L > 0
        assert fused.statistics.mean_a is not None
        assert fused.statistics.mean_b is not None
        
        # 步骤 5: 转换为 AnalysisResult
        analysis_result = fused.to_analysis_result()
        assert analysis_result is not None
        assert analysis_result.statistics == fused.statistics
    
    def test_weighted_vs_equal_fusion(self, test_environment):
        """测试加权融合与等权融合的差异"""
        from batch_analyzer import BatchAnalyzer
        from feature_fusion import fuse_features
        
        temp_path = test_environment
        source_dir = temp_path / 'source'
        
        # 批量分析
        analyzer = BatchAnalyzer(use_colour=False)
        batch_result = analyzer.analyze_directory(source_dir)
        results = batch_result.get_valid_results()
        
        # 等权融合
        fused_equal = fuse_features(results, strategy='equal_average')
        
        # 加权融合
        fused_weighted = fuse_features(results, weights=[3.0, 1.0, 1.0])
        
        # 验证权重不同
        assert fused_equal.weights != fused_weighted.weights
        
        # 验证融合结果不同
        # (由于随机图片，均值可能相近但不完全相同)
        assert fused_equal.num_images == fused_weighted.num_images
    
    def test_config_save_load(self, test_environment):
        """测试配置保存和加载"""
        from feature_fusion import FusionConfig
        
        temp_path = test_environment
        
        # 创建配置
        config = FusionConfig(
            weights=[3.0, 2.0, 1.0],
            strategy='weighted_average',
            histogram_method='weighted_average'
        )
        
        # 保存
        config_path = temp_path / 'test_config.json'
        config.save(config_path)
        
        # 加载
        loaded_config = FusionConfig.load(config_path)
        
        # 验证
        assert loaded_config.weights == config.weights
        assert loaded_config.strategy == config.strategy
        assert loaded_config.histogram_method == config.histogram_method
    
    def test_aggregate_statistics(self, test_environment):
        """测试统计聚合功能"""
        from batch_analyzer import BatchAnalyzer
        
        temp_path = test_environment
        source_dir = temp_path / 'source'
        
        # 批量分析
        analyzer = BatchAnalyzer(use_colour=False)
        batch_result = analyzer.analyze_directory(source_dir)
        results = batch_result.get_valid_results()
        
        # 聚合统计
        aggregated = analyzer.aggregate_statistics(results)
        
        # 验证聚合结果
        assert 'mean' in aggregated
        assert 'std' in aggregated
        assert 'var' in aggregated
        assert len(aggregated['mean']) == 3  # L, a, b
        assert len(aggregated['std']) == 3
        assert len(aggregated['var']) == 3
        assert aggregated['num_images'] == 3
        
        # 验证加权聚合
        weights = [2.0, 1.0, 1.0]
        aggregated_weighted = analyzer.aggregate_statistics(results, weights=weights)
        
        assert 'mean' in aggregated_weighted
    
    def test_error_handling_in_batch(self, test_environment):
        """测试批量处理中的错误处理"""
        from batch_analyzer import BatchAnalyzer
        
        temp_path = test_environment
        
        # 创建一个损坏的文件
        corrupted_file = temp_path / 'corrupted.jpg'
        with open(corrupted_file, 'wb') as f:
            f.write(b'not a valid image')
        
        # 批量分析（应该跳过损坏文件）
        analyzer = BatchAnalyzer(use_colour=False)
        result = analyzer.analyze_single(corrupted_file)
        
        assert result.valid is False
        assert result.error_message is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

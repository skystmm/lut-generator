"""
多图色彩特征融合模块 - Feature Fusion

负责：
- 多图色彩特征融合（平均/加权）
- 权重配置和管理
- 融合策略实现
- 融合结果验证

依赖：
- color_analyzer: 色彩分析结果类型
- numpy: 数值计算
"""

import numpy as np
from typing import List, Dict, Optional, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json

from color_analyzer import (
    AnalysisResult, 
    ColorStatistics, 
    ColorHistogram, 
    ColorDistribution
)


@dataclass
class FusionConfig:
    """融合配置"""
    # 权重列表（对应每张图片）
    weights: List[float] = field(default_factory=list)
    
    # 融合策略
    strategy: str = 'weighted_average'  # 'weighted_average', 'equal_average', 'median'
    
    # 是否归一化权重
    normalize_weights: bool = True
    
    # 直方图融合方法
    histogram_method: str = 'average'  # 'average', 'weighted_average'
    
    # 分布融合方法
    distribution_method: str = 'average'  # 'average', 'union', 'intersection'
    
    def validate(self, num_images: int) -> bool:
        """
        验证配置是否有效
        
        Args:
            num_images: 图片数量
            
        Returns:
            是否有效
        """
        if self.weights and len(self.weights) != num_images:
            return False
        if self.strategy not in ['weighted_average', 'equal_average', 'median']:
            return False
        if self.histogram_method not in ['average', 'weighted_average']:
            return False
        if self.distribution_method not in ['average', 'union', 'intersection']:
            return False
        return True
    
    def get_normalized_weights(self, num_images: int) -> List[float]:
        """
        获取归一化后的权重
        
        Args:
            num_images: 图片数量
            
        Returns:
            归一化权重列表
        """
        if not self.weights:
            # 等权重
            return [1.0 / num_images] * num_images
        
        if len(self.weights) != num_images:
            raise ValueError(
                f"weights length ({len(self.weights)}) must match num_images ({num_images})"
            )
        
        if self.normalize_weights:
            total = sum(self.weights)
            if total == 0:
                return [1.0 / num_images] * num_images
            return [w / total for w in self.weights]
        
        return self.weights
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'weights': self.weights,
            'strategy': self.strategy,
            'normalize_weights': self.normalize_weights,
            'histogram_method': self.histogram_method,
            'distribution_method': self.distribution_method
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FusionConfig':
        """从字典创建"""
        return cls(**data)
    
    def save(self, path: Union[str, Path]) -> None:
        """保存配置到文件"""
        path = Path(path)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> 'FusionConfig':
        """从文件加载配置"""
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class FusedFeatures:
    """融合后的特征"""
    # 融合后的统计特征
    statistics: ColorStatistics
    
    # 融合后的直方图
    histogram: ColorHistogram
    
    # 融合后的分布特征
    distribution: ColorDistribution
    
    # 使用的配置
    config: FusionConfig
    
    # 参与融合的图片数量
    num_images: int
    
    # 权重信息
    weights: List[float]
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'statistics': self.statistics.to_dict(),
            'histogram': self.histogram.to_dict(),
            'distribution': self.distribution.to_dict(),
            'config': self.config.to_dict(),
            'num_images': self.num_images,
            'weights': self.weights
        }
    
    def to_analysis_result(self) -> AnalysisResult:
        """转换为 AnalysisResult 格式（便于后续 LUT 生成）"""
        return AnalysisResult(
            statistics=self.statistics,
            histogram=self.histogram,
            distribution=self.distribution,
            image_shape=(0, 0, 3)  # 虚拟 shape
        )


class FeatureFusion:
    """
    特征融合器
    
    支持多种融合策略：
    - 等权平均
    - 加权平均
    - 中值融合
    """
    
    def __init__(self, config: Optional[FusionConfig] = None):
        """
        初始化融合器
        
        Args:
            config: 融合配置，如果为 None 则使用默认配置
        """
        self.config = config or FusionConfig()
    
    def _fuse_statistics(
        self, 
        statistics_list: List[ColorStatistics],
        weights: List[float]
    ) -> ColorStatistics:
        """
        融合统计特征
        
        Args:
            statistics_list: 统计特征列表
            weights: 权重列表
            
        Returns:
            融合后的统计特征
        """
        if self.config.strategy == 'median':
            # 中值融合
            mean_L = np.median([s.mean_L for s in statistics_list])
            mean_a = np.median([s.mean_a for s in statistics_list])
            mean_b = np.median([s.mean_b for s in statistics_list])
            std_L = np.median([s.std_L for s in statistics_list])
            std_a = np.median([s.std_a for s in statistics_list])
            std_b = np.median([s.std_b for s in statistics_list])
            var_L = np.median([s.var_L for s in statistics_list])
            var_a = np.median([s.var_a for s in statistics_list])
            var_b = np.median([s.var_b for s in statistics_list])
        else:
            # 加权平均（包括等权平均）
            mean_L = sum(s.mean_L * w for s, w in zip(statistics_list, weights))
            mean_a = sum(s.mean_a * w for s, w in zip(statistics_list, weights))
            mean_b = sum(s.mean_b * w for s, w in zip(statistics_list, weights))
            std_L = sum(s.std_L * w for s, w in zip(statistics_list, weights))
            std_a = sum(s.std_a * w for s, w in zip(statistics_list, weights))
            std_b = sum(s.std_b * w for s, w in zip(statistics_list, weights))
            var_L = sum(s.var_L * w for s, w in zip(statistics_list, weights))
            var_a = sum(s.var_a * w for s, w in zip(statistics_list, weights))
            var_b = sum(s.var_b * w for s, w in zip(statistics_list, weights))
        
        return ColorStatistics(
            mean_L=float(mean_L), mean_a=float(mean_a), mean_b=float(mean_b),
            std_L=float(std_L), std_a=float(std_a), std_b=float(std_b),
            var_L=float(var_L), var_a=float(var_a), var_b=float(var_b)
        )
    
    def _fuse_histograms(
        self, 
        histograms: List[ColorHistogram],
        weights: List[float]
    ) -> ColorHistogram:
        """
        融合直方图
        
        Args:
            histograms: 直方图列表
            weights: 权重列表
            
        Returns:
            融合后的直方图
        """
        if not histograms:
            raise ValueError("No histograms to fuse")
        
        # 检查所有直方图的 bin 数是否一致
        bins = histograms[0].bins
        if not all(h.bins == bins for h in histograms):
            raise ValueError("All histograms must have the same number of bins")
        
        if self.config.histogram_method == 'weighted_average' or \
           (self.config.histogram_method == 'average' and self.config.strategy == 'weighted_average'):
            # 加权平均
            L_hist = sum(h.L_hist * w for h, w in zip(histograms, weights))
            a_hist = sum(h.a_hist * w for h, w in zip(histograms, weights))
            b_hist = sum(h.b_hist * w for h, w in zip(histograms, weights))
        else:
            # 等权平均
            L_hist = np.mean([h.L_hist for h in histograms], axis=0)
            a_hist = np.mean([h.a_hist for h in histograms], axis=0)
            b_hist = np.mean([h.b_hist for h in histograms], axis=0)
        
        # 归一化
        L_hist = L_hist / L_hist.sum()
        a_hist = a_hist / a_hist.sum()
        b_hist = b_hist / b_hist.sum()
        
        return ColorHistogram(L_hist=L_hist, a_hist=a_hist, b_hist=b_hist, bins=bins)
    
    def _fuse_distributions(
        self, 
        distributions: List[ColorDistribution],
        weights: List[float]
    ) -> ColorDistribution:
        """
        融合分布特征
        
        Args:
            distributions: 分布特征列表
            weights: 权重列表
            
        Returns:
            融合后的分布特征
        """
        if self.config.distribution_method == 'union':
            # 并集：取最大范围
            L_range = (
                min(d.L_range[0] for d in distributions),
                max(d.L_range[1] for d in distributions)
            )
            a_range = (
                min(d.a_range[0] for d in distributions),
                max(d.a_range[1] for d in distributions)
            )
            b_range = (
                min(d.b_range[0] for d in distributions),
                max(d.b_range[1] for d in distributions)
            )
        elif self.config.distribution_method == 'intersection':
            # 交集：取最小范围
            L_range = (
                max(d.L_range[0] for d in distributions),
                min(d.L_range[1] for d in distributions)
            )
            a_range = (
                max(d.a_range[0] for d in distributions),
                min(d.a_range[1] for d in distributions)
            )
            b_range = (
                max(d.b_range[0] for d in distributions),
                min(d.b_range[1] for d in distributions)
            )
        else:
            # 平均
            L_range = (
                sum(d.L_range[0] * w for d, w in zip(distributions, weights)),
                sum(d.L_range[1] * w for d, w in zip(distributions, weights))
            )
            a_range = (
                sum(d.a_range[0] * w for d, w in zip(distributions, weights)),
                sum(d.a_range[1] * w for d, w in zip(distributions, weights))
            )
            b_range = (
                sum(d.b_range[0] * w for d, w in zip(distributions, weights)),
                sum(d.b_range[1] * w for d, w in zip(distributions, weights))
            )
        
        # 加权平均其他特征
        gamut_coverage = sum(d.gamut_coverage * w for d, w in zip(distributions, weights))
        color_entropy = sum(d.color_entropy * w for d, w in zip(distributions, weights))
        
        # 主色调：加权平均
        dominant_L = sum(d.dominant_color[0] * w for d, w in zip(distributions, weights))
        dominant_a = sum(d.dominant_color[1] * w for d, w in zip(distributions, weights))
        dominant_b = sum(d.dominant_color[2] * w for d, w in zip(distributions, weights))
        
        return ColorDistribution(
            L_range=L_range,
            a_range=a_range,
            b_range=b_range,
            gamut_coverage=float(gamut_coverage),
            color_entropy=float(color_entropy),
            dominant_color=(dominant_L, dominant_a, dominant_b)
        )
    
    def fuse(
        self, 
        results: List[AnalysisResult],
        weights: Optional[List[float]] = None
    ) -> FusedFeatures:
        """
        融合多个分析结果
        
        Args:
            results: 分析结果列表
            weights: 权重列表（可选，如果为 None 则使用配置中的权重）
            
        Returns:
            FusedFeatures 对象
        """
        if not results:
            raise ValueError("No results to fuse")
        
        num_images = len(results)
        
        # 确定权重
        if weights is None:
            weights = self.config.get_normalized_weights(num_images)
        else:
            if len(weights) != num_images:
                raise ValueError(
                    f"weights length ({len(weights)}) must match num_images ({num_images})"
                )
            # 归一化
            total = sum(weights)
            if total > 0:
                weights = [w / total for w in weights]
            else:
                weights = [1.0 / num_images] * num_images
        
        # 提取特征列表
        statistics_list = [r.statistics for r in results]
        histograms = [r.histogram for r in results]
        distributions = [r.distribution for r in results]
        
        # 融合
        fused_stats = self._fuse_statistics(statistics_list, weights)
        fused_hist = self._fuse_histograms(histograms, weights)
        fused_dist = self._fuse_distributions(distributions, weights)
        
        return FusedFeatures(
            statistics=fused_stats,
            histogram=fused_hist,
            distribution=fused_dist,
            config=self.config,
            num_images=num_images,
            weights=weights
        )
    
    def fuse_from_paths(
        self,
        image_paths: List[Union[str, Path]],
        weights: Optional[List[float]] = None,
        use_colour: bool = True
    ) -> FusedFeatures:
        """
        从图片路径直接融合（内部调用批量分析）
        
        Args:
            image_paths: 图片路径列表
            weights: 权重列表
            use_colour: 是否使用 colour-science
            
        Returns:
            FusedFeatures 对象
        """
        from color_analyzer import ColorAnalyzer
        
        analyzer = ColorAnalyzer(use_colour=use_colour)
        results = []
        
        for path in image_paths:
            try:
                result = analyzer.analyze(path)
                results.append(result)
            except Exception as e:
                print(f"Warning: Failed to analyze {path}: {e}")
        
        if not results:
            raise ValueError("No valid images to fuse")
        
        return self.fuse(results, weights)


def fuse_features(
    results: List[AnalysisResult],
    weights: Optional[List[float]] = None,
    strategy: str = 'weighted_average'
) -> FusedFeatures:
    """
    便捷函数：融合特征
    
    Args:
        results: 分析结果列表
        weights: 权重列表
        strategy: 融合策略
        
    Returns:
        FusedFeatures 对象
    """
    config = FusionConfig(strategy=strategy, weights=weights or [])
    fusion = FeatureFusion(config)
    return fusion.fuse(results, weights)


def create_weight_config(
    image_paths: List[Union[str, Path]],
    weight_values: Optional[List[float]] = None
) -> FusionConfig:
    """
    创建权重配置
    
    Args:
        image_paths: 图片路径列表
        weight_values: 权重值列表（可选）
        
    Returns:
        FusionConfig 对象
    """
    if weight_values is None:
        # 等权重
        return FusionConfig(weights=[], strategy='equal_average')
    
    if len(weight_values) != len(image_paths):
        raise ValueError(
            f"weight_values length ({len(weight_values)}) must match "
            f"image_paths length ({len(image_paths)})"
        )
    
    return FusionConfig(weights=weight_values, strategy='weighted_average')


if __name__ == "__main__":
    # 简单测试
    import sys
    from batch_analyzer import BatchAnalyzer
    
    if len(sys.argv) > 1:
        # 从目录加载多张图片
        directory = sys.argv[1]
        
        print(f"Loading images from: {directory}")
        
        batch_analyzer = BatchAnalyzer()
        batch_result = batch_analyzer.analyze_directory(directory)
        
        if batch_result.valid_images < 2:
            print("Need at least 2 valid images for fusion")
            sys.exit(1)
        
        results = batch_result.get_valid_results()
        print(f"Loaded {len(results)} valid images")
        
        # 等权融合
        print("\n=== Equal Weight Fusion ===")
        fused_equal = fuse_features(results, strategy='equal_average')
        print(f"Fused mean (L,a,b): {fused_equal.statistics.mean_array()}")
        
        # 加权融合（示例：第一张图权重 2，其他权重 1）
        if len(results) >= 2:
            print("\n=== Weighted Fusion (2:1:1:...) ===")
            weights = [2.0] + [1.0] * (len(results) - 1)
            fused_weighted = fuse_features(results, weights=weights)
            print(f"Fused mean (L,a,b): {fused_weighted.statistics.mean_array()}")
        
        # 保存配置
        config_path = Path(directory) / 'fusion_config.json'
        fused_equal.config.save(config_path)
        print(f"\nConfig saved to: {config_path}")
    else:
        print("Usage: python feature_fusion.py <directory>")

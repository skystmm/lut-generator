"""
单图风格提取模块 - StyleExtractor

从单张调色后图片提取风格特征，生成模拟该风格的 LUT

核心原理：
1. 假设一个"中性基准图像"的统计特征（L=50, a=0, b=0 为中心）
2. 分析调色后图片的色彩偏移和对比度变化
3. 生成从基准到目标风格的变换
"""

import numpy as np
from typing import Dict, Tuple, Optional, Union, Callable
from dataclasses import dataclass
from pathlib import Path

from .color_space import ColorSpaceConverter
from .reinhard import ColorStatistics, LUTTransformBuilder
from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig


@dataclass
class NeutralBaseline:
    """
    中性基准图像的统计特征
    
    模拟一张"正常曝光、中性白平衡"的参考图像
    """
    # Lab 空间均值 - 中性灰
    mean_L: float = 50.0   # 中灰亮度
    mean_a: float = 0.0    # 无绿/红偏移
    mean_b: float = 0.0    # 无蓝/黄偏移
    
    # Lab 空间标准差 - 正常对比度范围
    std_L: float = 25.0    # 正常亮度对比度
    std_a: float = 15.0    # 正常饱和度范围
    std_b: float = 15.0    # 正常饱和度范围
    
    # 方差（派生）
    var_L: float = 625.0
    var_a: float = 225.0
    var_b: float = 225.0
    
    def to_color_statistics(self) -> ColorStatistics:
        """转换为 ColorStatistics 对象"""
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
    
    @classmethod
    def from_reference_image(cls, image_path: Union[str, Path],
                            converter: ColorSpaceConverter = None) -> 'NeutralBaseline':
        """
        从参考图像创建基准（用于自定义中性参考）
        
        Args:
            image_path: 参考图像路径
            converter: 色彩空间转换器
            
        Returns:
            NeutralBaseline 对象
        """
        if converter is None:
            converter = ColorSpaceConverter()
        
        rgb = converter.load_image(image_path)
        lab = converter.rgb_to_lab(rgb)
        
        L = lab[:, :, 0]
        a = lab[:, :, 1]
        b = lab[:, :, 2]
        
        return cls(
            mean_L=float(np.mean(L)),
            mean_a=float(np.mean(a)),
            mean_b=float(np.mean(b)),
            std_L=float(np.std(L)),
            std_a=float(np.std(a)),
            std_b=float(np.std(b)),
            var_L=float(np.var(L)),
            var_a=float(np.var(a)),
            var_b=float(np.var(b))
        )


@dataclass
class StyleFeatures:
    """
    风格特征描述
    
    从图像提取的风格参数
    """
    # 色调偏移 (Lab 均值偏移)
    tone_shift_L: float     # 亮度偏移 (-50 到 +50)
    tone_shift_a: float     # 绿-红偏移 (-128 到 +127)
    tone_shift_b: float    # 蓝-黄偏移 (-128 到 +127)
    
    # 对比度调整 (标准差比例)
    contrast_L: float       # 亮度对比度比例
    saturation_a: float    # a通道饱和度比例
    saturation_b: float    # b通道饱和度比例
    
    # 综合指标
    warmth: float          # 色温 (-1 冷色 到 +1 暖色)
    contrast: float        # 整体对比度 (0.5 低对比 到 2.0 高对比)
    saturation: float      # 整体饱和度 (0 灰度 到 2 过饱和)
    
    # 原始统计
    source_stats: ColorStatistics
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'tone_shift': {
                'L': self.tone_shift_L,
                'a': self.tone_shift_a,
                'b': self.tone_shift_b
            },
            'contrast_ratio': {
                'L': self.contrast_L,
                'a': self.saturation_a,
                'b': self.saturation_b
            },
            'style_metrics': {
                'warmth': self.warmth,
                'contrast': self.contrast,
                'saturation': self.saturation
            },
            'source_stats': self.source_stats.to_dict()
        }


@dataclass
class ExtractionResult:
    """风格提取结果"""
    features: StyleFeatures
    baseline: NeutralBaseline
    style_lut_data: np.ndarray  # 生成的风格 LUT 数据
    metadata: Dict
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'features': self.features.to_dict(),
            'baseline': {
                'mean_L': self.baseline.mean_L,
                'mean_a': self.baseline.mean_a,
                'mean_b': self.baseline.mean_b,
                'std_L': self.baseline.std_L,
                'std_a': self.baseline.std_a,
                'std_b': self.baseline.std_b
            },
            'metadata': self.metadata
        }


class StyleExtractor:
    """
    单图风格提取器
    
    从单张调色后图片提取风格特征并生成模拟 LUT
    """
    
    def __init__(self, 
                 baseline: NeutralBaseline = None,
                 grid_size: int = 33,
                 strength: float = 1.0):
        """
        初始化风格提取器
        
        Args:
            baseline: 中性基准，None 则使用默认
            grid_size: LUT 网格尺寸 (17, 33, 65)
            strength: 风格强度 (0-1)
        """
        self.baseline = baseline or NeutralBaseline()
        self.grid_size = grid_size
        self.strength = strength
        self.converter = ColorSpaceConverter()
    
    def extract_features(self, image_path: Union[str, Path]) -> StyleFeatures:
        """
        从图像提取风格特征
        
        Args:
            image_path: 图像路径
            
        Returns:
            StyleFeatures 对象
        """
        # 加载并转换到 Lab 空间
        rgb = self.converter.load_image(image_path)
        lab = self.converter.rgb_to_lab(rgb)
        
        # 计算统计信息
        L = lab[:, :, 0]
        a = lab[:, :, 1]
        b = lab[:, :, 2]
        
        mean_L = float(np.mean(L))
        mean_a = float(np.mean(a))
        mean_b = float(np.mean(b))
        std_L = float(np.std(L))
        std_a = float(np.std(a))
        std_b = float(np.std(b))
        
        source_stats = ColorStatistics(
            mean_L=mean_L,
            mean_a=mean_a,
            mean_b=mean_b,
            std_L=std_L,
            std_a=std_a,
            std_b=std_b,
            var_L=float(np.var(L)),
            var_a=float(np.var(a)),
            var_b=float(np.var(b))
        )
        
        # 计算风格特征
        return self._compute_features(source_stats)
    
    def extract_features_from_array(self, rgb_array: np.ndarray) -> StyleFeatures:
        """
        从 RGB 数组提取风格特征
        
        Args:
            rgb_array: RGB 图像数组 (H, W, 3), 值域 0-255
            
        Returns:
            StyleFeatures 对象
        """
        lab = self.converter.rgb_to_lab(rgb_array)
        
        L = lab[:, :, 0]
        a = lab[:, :, 1]
        b = lab[:, :, 2]
        
        source_stats = ColorStatistics(
            mean_L=float(np.mean(L)),
            mean_a=float(np.mean(a)),
            mean_b=float(np.mean(b)),
            std_L=float(np.std(L)),
            std_a=float(np.std(a)),
            std_b=float(np.std(b)),
            var_L=float(np.var(L)),
            var_a=float(np.var(a)),
            var_b=float(np.var(b))
        )
        
        return self._compute_features(source_stats)
    
    def _compute_features(self, source_stats: ColorStatistics) -> StyleFeatures:
        """
        计算风格特征
        
        Args:
            source_stats: 源图像统计信息
            
        Returns:
            StyleFeatures 对象
        """
        # 色调偏移（相对于中性基准）
        tone_shift_L = source_stats.mean_L - self.baseline.mean_L
        tone_shift_a = source_stats.mean_a - self.baseline.mean_a
        tone_shift_b = source_stats.mean_b - self.baseline.mean_b
        
        # 对比度/饱和度比例
        # 防止除零
        std_L_safe = max(self.baseline.std_L, 1e-6)
        std_a_safe = max(self.baseline.std_a, 1e-6)
        std_b_safe = max(self.baseline.std_b, 1e-6)
        
        contrast_L = source_stats.std_L / std_L_safe
        saturation_a = source_stats.std_a / std_a_safe
        saturation_b = source_stats.std_b / std_b_safe
        
        # 色温指标 (b > 0 为暖色, b < 0 为冷色)
        # 归一化到 -1 到 1
        warmth = np.clip(tone_shift_b / 30.0, -1.0, 1.0)
        
        # 整体对比度 (L 通道标准差比例)
        contrast = contrast_L
        
        # 整体饱和度 (a, b 通道标准差比例的平均)
        saturation = (saturation_a + saturation_b) / 2.0
        
        return StyleFeatures(
            tone_shift_L=tone_shift_L,
            tone_shift_a=tone_shift_a,
            tone_shift_b=tone_shift_b,
            contrast_L=contrast_L,
            saturation_a=saturation_a,
            saturation_b=saturation_b,
            warmth=warmth,
            contrast=contrast,
            saturation=saturation,
            source_stats=source_stats
        )
    
    def generate_lut(self, image_path: Union[str, Path],
                    strength: float = None) -> ExtractionResult:
        """
        从单张图像生成风格 LUT
        
        Args:
            image_path: 调色后图像路径
            strength: 风格强度 (0-1)，None 使用默认值
            
        Returns:
            ExtractionResult 对象
        """
        strength = strength if strength is not None else self.strength
        
        # 提取特征
        features = self.extract_features(image_path)
        
        # 生成 LUT
        lut_data = self._generate_lut_from_features(features, strength)
        
        metadata = {
            'source_image': str(image_path),
            'strength': strength,
            'grid_size': self.grid_size,
            'description': self._generate_description(features)
        }
        
        return ExtractionResult(
            features=features,
            baseline=self.baseline,
            style_lut_data=lut_data,
            metadata=metadata
        )
    
    def generate_lut_from_features(self, features: StyleFeatures,
                                   strength: float = None) -> np.ndarray:
        """
        从风格特征生成 LUT
        
        Args:
            features: 风格特征
            strength: 风格强度
            
        Returns:
            3D LUT 数组
        """
        strength = strength if strength is not None else self.strength
        return self._generate_lut_from_features(features, strength)
    
    def _generate_lut_from_features(self, features: StyleFeatures,
                                    strength: float) -> np.ndarray:
        """
        内部方法：从特征生成 LUT
        """
        # 使用 Reinhard 变换：从中性基准变换到目标风格
        baseline_stats = self.baseline.to_color_statistics()
        
        # 构建变换构建器
        builder = LUTTransformBuilder(
            source_stats=baseline_stats,
            target_stats=features.source_stats,
            strength=strength
        )
        
        # 生成 LUT
        config = LUT3DConfig(grid_size=self.grid_size)
        generator = LUT3DGenerator(config)
        
        transform_func = builder.build_transform_func()
        lut_data = generator.generate_from_transform(transform_func)
        
        return lut_data
    
    def _generate_description(self, features: StyleFeatures) -> str:
        """生成风格描述"""
        desc_parts = []
        
        # 色温
        if features.warmth > 0.2:
            desc_parts.append("warm tone")
        elif features.warmth < -0.2:
            desc_parts.append("cool tone")
        
        # 对比度
        if features.contrast > 1.3:
            desc_parts.append("high contrast")
        elif features.contrast < 0.7:
            desc_parts.append("low contrast")
        
        # 饱和度
        if features.saturation > 1.3:
            desc_parts.append("vivid")
        elif features.saturation < 0.7:
            desc_parts.append("desaturated")
        
        # 亮度
        if features.tone_shift_L > 10:
            desc_parts.append("bright")
        elif features.tone_shift_L < -10:
            desc_parts.append("dark")
        
        if not desc_parts:
            desc_parts.append("neutral")
        
        return ", ".join(desc_parts)
    
    def analyze_image(self, image_path: Union[str, Path]) -> Dict:
        """
        分析图像并返回详细的风格报告
        
        Args:
            image_path: 图像路径
            
        Returns:
            风格分析报告字典
        """
        features = self.extract_features(image_path)
        
        return {
            'image_path': str(image_path),
            'lab_statistics': {
                'mean': {
                    'L': features.source_stats.mean_L,
                    'a': features.source_stats.mean_a,
                    'b': features.source_stats.mean_b
                },
                'std': {
                    'L': features.source_stats.std_L,
                    'a': features.source_stats.std_a,
                    'b': features.source_stats.std_b
                }
            },
            'style_analysis': {
                'tone_shift': {
                    'L': features.tone_shift_L,
                    'a': features.tone_shift_a,
                    'b': features.tone_shift_b
                },
                'contrast_ratio': {
                    'L': features.contrast_L,
                    'a': features.saturation_a,
                    'b': features.saturation_b
                },
                'style_metrics': {
                    'warmth': features.warmth,
                    'contrast': features.contrast,
                    'saturation': features.saturation
                },
                'style_description': self._generate_description(features)
            },
            'baseline': {
                'mean_L': self.baseline.mean_L,
                'mean_a': self.baseline.mean_a,
                'mean_b': self.baseline.mean_b,
                'std_L': self.baseline.std_L,
                'std_a': self.baseline.std_a,
                'std_b': self.baseline.std_b
            }
        }


# 便捷函数
def extract_style(image_path: Union[str, Path],
                  output_lut_path: Union[str, Path],
                  grid_size: int = 33,
                  strength: float = 1.0,
                  baseline: NeutralBaseline = None) -> ExtractionResult:
    """
    便捷函数：从单张图像提取风格并生成 LUT
    
    Args:
        image_path: 调色后图像路径
        output_lut_path: 输出 LUT 文件路径
        grid_size: LUT 网格尺寸
        strength: 风格强度
        baseline: 自定义中性基准
        
    Returns:
        ExtractionResult 对象
    """
    from lut_generator.lut.exporter import LUTExporter
    
    extractor = StyleExtractor(
        baseline=baseline,
        grid_size=grid_size,
        strength=strength
    )
    
    result = extractor.generate_lut(image_path, strength)
    
    # 导出 LUT
    metadata = {
        'title': f"Style extracted from {Path(image_path).stem}",
        'description': result.metadata.get('description', '')
    }
    
    exporter = LUTExporter(result.style_lut_data, metadata)
    exporter.export(output_lut_path)
    
    return result


def analyze_style(image_path: Union[str, Path],
                  baseline: NeutralBaseline = None) -> Dict:
    """
    便捷函数：分析图像风格
    
    Args:
        image_path: 图像路径
        baseline: 自定义中性基准
        
    Returns:
        风格分析报告
    """
    extractor = StyleExtractor(baseline=baseline)
    return extractor.analyze_image(image_path)
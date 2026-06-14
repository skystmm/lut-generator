"""
色彩分析模块 - ColorAnalyzer

提供图像色彩特征提取功能
"""

import numpy as np
import cv2
from typing import Dict, Tuple, Optional, Union
from dataclasses import dataclass
from pathlib import Path

from lut_generator.core.color_space import ColorSpaceConverter
from lut_generator.core.reinhard import ColorStatistics


@dataclass
class ColorHistogram:
    """色彩直方图"""
    L_hist: np.ndarray
    a_hist: np.ndarray
    b_hist: np.ndarray
    bins: int = 256
    
    def to_dict(self) -> Dict[str, list]:
        return {
            'L_hist': self.L_hist.tolist(),
            'a_hist': self.a_hist.tolist(),
            'b_hist': self.b_hist.tolist(),
            'bins': self.bins
        }


@dataclass
class ColorDistribution:
    """色彩分布分析"""
    L_range: Tuple[float, float]
    a_range: Tuple[float, float]
    b_range: Tuple[float, float]
    gamut_coverage: float
    color_entropy: float
    dominant_color: Tuple[float, float, float]
    
    def to_dict(self) -> Dict:
        return {
            'L_range': list(self.L_range),
            'a_range': list(self.a_range),
            'b_range': list(self.b_range),
            'gamut_coverage': self.gamut_coverage,
            'color_entropy': self.color_entropy,
            'dominant_color': list(self.dominant_color)
        }


@dataclass
class AnalysisResult:
    """完整的色彩分析结果"""
    statistics: ColorStatistics
    histogram: ColorHistogram
    distribution: ColorDistribution
    image_shape: Tuple[int, int, int]
    
    def to_dict(self) -> Dict:
        return {
            'statistics': self.statistics.to_dict(),
            'histogram': self.histogram.to_dict(),
            'distribution': self.distribution.to_dict(),
            'image_shape': self.image_shape
        }


class ColorAnalyzer:
    """
    色彩分析器
    
    提供完整的图像色彩特征提取功能
    """
    
    def __init__(self, use_colour: bool = True, raw_mode: str = 'half',
                 use_camera_wb: bool = True):
        self.converter = ColorSpaceConverter(use_colour=use_colour)
        self.raw_mode = raw_mode
        self.use_camera_wb = use_camera_wb

    def load_image(self, image_path: Union[str, Path]) -> np.ndarray:
        """加载图像(支持相机 RAW,通过构造时的 raw_mode 决定档位)"""
        return self.converter.load_image(
            image_path, raw_mode=self.raw_mode, use_camera_wb=self.use_camera_wb
        )
    
    def rgb_to_lab(self, rgb: np.ndarray) -> np.ndarray:
        """RGB 转 Lab"""
        return self.converter.rgb_to_lab(rgb)
    
    def lab_to_rgb(self, lab: np.ndarray) -> np.ndarray:
        """Lab 转 RGB"""
        return self.converter.lab_to_rgb(lab)
    
    def extract_statistics(self, lab_image: np.ndarray) -> ColorStatistics:
        """
        提取 Lab 空间的统计特征
        
        Args:
            lab_image: Lab 图像数组
            
        Returns:
            ColorStatistics 对象
        """
        L = lab_image[:, :, 0]
        a = lab_image[:, :, 1]
        b = lab_image[:, :, 2]
        
        return ColorStatistics(
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
    
    def extract_histogram(self, lab_image: np.ndarray, bins: int = 256) -> ColorHistogram:
        """
        提取 Lab 空间的色彩直方图
        
        Args:
            lab_image: Lab 图像数组
            bins: 直方图 bin 数量
            
        Returns:
            ColorHistogram 对象
        """
        L = lab_image[:, :, 0]
        a = lab_image[:, :, 1]
        b = lab_image[:, :, 2]
        
        L_range = (0, 100)
        a_range = (-128, 127)
        b_range = (-128, 127)
        
        L_hist, _ = np.histogram(L, bins=bins, range=L_range)
        a_hist, _ = np.histogram(a, bins=bins, range=a_range)
        b_hist, _ = np.histogram(b, bins=bins, range=b_range)
        
        # 归一化
        L_hist = L_hist.astype(np.float64) / L_hist.sum()
        a_hist = a_hist.astype(np.float64) / a_hist.sum()
        b_hist = b_hist.astype(np.float64) / b_hist.sum()
        
        return ColorHistogram(L_hist=L_hist, a_hist=a_hist, b_hist=b_hist, bins=bins)
    
    def extract_distribution(self, lab_image: np.ndarray) -> ColorDistribution:
        """
        提取色彩分布特征
        
        Args:
            lab_image: Lab 图像数组
            
        Returns:
            ColorDistribution 对象
        """
        L = lab_image[:, :, 0].flatten()
        a = lab_image[:, :, 1].flatten()
        b = lab_image[:, :, 2].flatten()
        
        L_range = (float(L.min()), float(L.max()))
        a_range = (float(a.min()), float(a.max()))
        b_range = (float(b.min()), float(b.max()))
        
        # 色域覆盖
        actual_area = (a_range[1] - a_range[0]) * (b_range[1] - b_range[0])
        max_area = 255 * 255
        gamut_coverage = float(actual_area / max_area * 100)
        
        # 色彩熵
        bins_2d = 32
        hist_2d, _, _ = np.histogram2d(a, b, bins=bins_2d,
                                        range=[a_range, b_range])
        hist_2d = hist_2d.flatten()
        hist_2d = hist_2d[hist_2d > 0]
        hist_2d = hist_2d / hist_2d.sum()
        color_entropy = float(-np.sum(hist_2d * np.log2(hist_2d)))
        
        # 主色调
        max_idx = np.argmax(hist_2d)
        max_bin = np.unravel_index(max_idx, (bins_2d, bins_2d))
        dominant_a = a_range[0] + (max_bin[0] + 0.5) * (a_range[1] - a_range[0]) / bins_2d
        dominant_b = b_range[0] + (max_bin[1] + 0.5) * (b_range[1] - b_range[0]) / bins_2d
        dominant_L = float(np.mean(L))
        
        return ColorDistribution(
            L_range=L_range,
            a_range=a_range,
            b_range=b_range,
            gamut_coverage=gamut_coverage,
            color_entropy=color_entropy,
            dominant_color=(dominant_L, dominant_a, dominant_b)
        )
    
    def analyze(self, image_path: Union[str, Path]) -> AnalysisResult:
        """
        完整分析一张图像的色彩特征
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            AnalysisResult 对象
        """
        rgb = self.load_image(image_path)
        lab = self.rgb_to_lab(rgb)
        
        statistics = self.extract_statistics(lab)
        histogram = self.extract_histogram(lab)
        distribution = self.extract_distribution(lab)
        
        return AnalysisResult(
            statistics=statistics,
            histogram=histogram,
            distribution=distribution,
            image_shape=tuple(lab.shape)
        )
    
    def analyze_array(self, rgb_array: np.ndarray) -> AnalysisResult:
        """
        分析 RGB 数组的色彩特征
        
        Args:
            rgb_array: RGB 图像数组
            
        Returns:
            AnalysisResult 对象
        """
        lab = self.rgb_to_lab(rgb_array)
        
        statistics = self.extract_statistics(lab)
        histogram = self.extract_histogram(lab)
        distribution = self.extract_distribution(lab)
        
        return AnalysisResult(
            statistics=statistics,
            histogram=histogram,
            distribution=distribution,
            image_shape=tuple(lab.shape)
        )


def analyze_image(image_path: Union[str, Path], use_colour: bool = True) -> AnalysisResult:
    """
    便捷函数：分析单张图像
    
    Args:
        image_path: 图像文件路径
        use_colour: 是否使用 colour-science 库
        
    Returns:
        AnalysisResult 对象
    """
    analyzer = ColorAnalyzer(use_colour=use_colour)
    return analyzer.analyze(image_path)
"""
色彩分析模块 - Color Analyzer

负责图像色彩特征提取，包括：
- 色彩空间转换（RGB ↔ Lab）
- 色彩统计特征（均值、方差、标准差）
- 色彩直方图
- 色彩分布分析

依赖：
- colour-science: 精确的色彩空间转换
- opencv-python: 图像处理和直方图计算
- numpy: 数值计算
"""

import numpy as np
import cv2
from typing import Dict, Tuple, Optional, Union
from dataclasses import dataclass
from pathlib import Path

try:
    import colour
    COLOUR_AVAILABLE = True
except ImportError:
    COLOUR_AVAILABLE = False
    print("Warning: colour-science not installed. Using OpenCV for color conversion.")


@dataclass
class ColorStatistics:
    """色彩统计信息"""
    mean_L: float
    mean_a: float
    mean_b: float
    std_L: float
    std_a: float
    std_b: float
    var_L: float
    var_a: float
    var_b: float
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            'mean': [self.mean_L, self.mean_a, self.mean_b],
            'std': [self.std_L, self.std_a, self.std_b],
            'var': [self.var_L, self.var_a, self.var_b]
        }
    
    def mean_array(self) -> np.ndarray:
        """均值数组"""
        return np.array([self.mean_L, self.mean_a, self.mean_b])
    
    def std_array(self) -> np.ndarray:
        """标准差数组"""
        return np.array([self.std_L, self.std_a, self.std_b])


@dataclass
class ColorHistogram:
    """色彩直方图"""
    L_hist: np.ndarray
    a_hist: np.ndarray
    b_hist: np.ndarray
    bins: int = 256
    
    def to_dict(self) -> Dict[str, list]:
        """转换为字典（列表格式，便于 JSON 序列化）"""
        return {
            'L_hist': self.L_hist.tolist(),
            'a_hist': self.a_hist.tolist(),
            'b_hist': self.b_hist.tolist(),
            'bins': self.bins
        }


@dataclass
class ColorDistribution:
    """色彩分布分析"""
    # Lab 空间分布
    L_range: Tuple[float, float]
    a_range: Tuple[float, float]
    b_range: Tuple[float, float]
    
    # 色域覆盖（百分比）
    gamut_coverage: float
    
    # 色彩丰富度（熵）
    color_entropy: float
    
    # 主色调（占比最高的颜色区域）
    dominant_color: Tuple[float, float, float]
    
    def to_dict(self) -> Dict:
        """转换为字典"""
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
        """转换为字典"""
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
    
    def __init__(self, use_colour: bool = True):
        """
        初始化色彩分析器
        
        Args:
            use_colour: 是否使用 colour-science 库进行色彩空间转换
                       如果为 False，则使用 OpenCV 的近似转换
        """
        self.use_colour = use_colour and COLOUR_AVAILABLE
        if not self.use_colour:
            print("Using OpenCV for color space conversion (approximate)")
    
    def load_image(self, image_path: Union[str, Path]) -> np.ndarray:
        """
        加载图像并转换为 RGB 格式
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            RGB 格式的 numpy 数组，值范围 0-255
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # OpenCV 默认读取为 BGR
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        # BGR → RGB
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return img_rgb
    
    def rgb_to_lab(self, rgb: np.ndarray) -> np.ndarray:
        """
        RGB 转 Lab 色彩空间
        
        Args:
            rgb: RGB 图像数组，shape=(H, W, 3)，值范围 0-255 或 0-1
            
        Returns:
            Lab 图像数组，shape=(H, W, 3)
            L: 0-100, a: -128-127, b: -128-127
        """
        # 归一化到 0-1
        if rgb.max() > 1.0:
            rgb_normalized = rgb.astype(np.float64) / 255.0
        else:
            rgb_normalized = rgb.astype(np.float64)
        
        if self.use_colour:
            # 使用 colour-science 进行精确转换
            # sRGB → XYZ → Lab (D65 illuminant, 2° observer)
            try:
                # colour 库期望 shape=(H*W, 3)
                h, w = rgb_normalized.shape[:2]
                rgb_flat = rgb_normalized.reshape(-1, 3)
                
                # sRGB → XYZ
                xyz = colour.sRGB_to_XYZ(rgb_flat)
                
                # XYZ → Lab (D65, CIE 1931 2°)
                lab_flat = colour.XYZ_to_Lab(xyz)
                
                lab = lab_flat.reshape(h, w, 3)
                return lab
            except Exception as e:
                print(f"colour-science conversion failed: {e}, falling back to OpenCV")
                self.use_colour = False
        
        # 使用 OpenCV 近似转换（更快但精度略低）
        # OpenCV 的 RGB→Lab 实际上是 sRGB→CIELAB
        if rgb_normalized.max() <= 1.0:
            rgb_for_cv = (rgb_normalized * 255).astype(np.uint8)
        else:
            rgb_for_cv = rgb_normalized.astype(np.uint8)
        
        # OpenCV 的 cvtColor 期望 uint8 输入
        lab = cv2.cvtColor(rgb_for_cv, cv2.COLOR_RGB2LAB).astype(np.float64)
        
        # OpenCV 的 L 范围是 0-255，需要转换到 0-100
        # a,b 范围是 0-255，需要调整到 -128-127
        lab[:, :, 0] = lab[:, :, 0] * (100.0 / 255.0)  # L: 0-255 → 0-100
        lab[:, :, 1] = lab[:, :, 1] - 128  # a: 0-255 → -128-127
        lab[:, :, 2] = lab[:, :, 2] - 128  # b: 0-255 → -128-127
        
        return lab
    
    def lab_to_rgb(self, lab: np.ndarray) -> np.ndarray:
        """
        Lab 转 RGB 色彩空间
        
        Args:
            lab: Lab 图像数组，shape=(H, W, 3)
                 L: 0-100, a: -128-127, b: -128-127
                 
        Returns:
            RGB 图像数组，shape=(H, W, 3)，值范围 0-1
        """
        if self.use_colour:
            try:
                h, w = lab.shape[:2]
                lab_flat = lab.reshape(-1, 3)
                
                # Lab → XYZ
                xyz = colour.Lab_to_XYZ(lab_flat)
                
                # XYZ → sRGB
                rgb_flat = colour.XYZ_to_sRGB(xyz)
                
                # 裁剪到有效范围
                rgb_flat = np.clip(rgb_flat, 0, 1)
                
                return rgb_flat.reshape(h, w, 3)
            except Exception as e:
                print(f"colour-science conversion failed: {e}, falling back to OpenCV")
                self.use_colour = False
        
        # 使用 OpenCV
        lab_for_cv = lab.copy()
        lab_for_cv[:, :, 0] = lab_for_cv[:, :, 0] * (255.0 / 100.0)  # L: 0-100 → 0-255
        lab_for_cv[:, :, 1] = lab_for_cv[:, :, 1] + 128  # a: -128-127 → 0-255
        lab_for_cv[:, :, 2] = lab_for_cv[:, :, 2] + 128  # b: -128-127 → 0-255
        lab_for_cv = np.clip(lab_for_cv, 0, 255).astype(np.uint8)
        
        rgb_bgr = cv2.cvtColor(lab_for_cv, cv2.COLOR_LAB2RGB)
        return rgb_bgr.astype(np.float64) / 255.0
    
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
        
        # 计算均值
        mean_L = float(np.mean(L))
        mean_a = float(np.mean(a))
        mean_b = float(np.mean(b))
        
        # 计算方差
        var_L = float(np.var(L))
        var_a = float(np.var(a))
        var_b = float(np.var(b))
        
        # 计算标准差
        std_L = float(np.std(L))
        std_a = float(np.std(a))
        std_b = float(np.std(b))
        
        return ColorStatistics(
            mean_L=mean_L, mean_a=mean_a, mean_b=mean_b,
            std_L=std_L, std_a=std_a, std_b=std_b,
            var_L=var_L, var_a=var_a, var_b=var_b
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
        
        # 定义每个通道的范围
        L_range = (0, 100)
        a_range = (-128, 127)
        b_range = (-128, 127)
        
        # 计算直方图
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
        
        # 范围
        L_range = (float(L.min()), float(L.max()))
        a_range = (float(a.min()), float(a.max()))
        b_range = (float(b.min()), float(b.max()))
        
        # 色域覆盖（简化计算：基于 a,b 范围的面积比例）
        # 理论最大范围：a,b 各 255，总面积 255*255
        actual_area = (a_range[1] - a_range[0]) * (b_range[1] - b_range[0])
        max_area = 255 * 255
        gamut_coverage = float(actual_area / max_area * 100)
        
        # 色彩熵（基于 2D 直方图）
        # 将 a,b 空间离散化
        bins_2d = 32
        hist_2d, _, _ = np.histogram2d(a, b, bins=bins_2d, 
                                        range=[a_range, b_range])
        hist_2d = hist_2d.flatten()
        hist_2d = hist_2d[hist_2d > 0]  # 只保留非零值
        hist_2d = hist_2d / hist_2d.sum()  # 归一化
        color_entropy = float(-np.sum(hist_2d * np.log2(hist_2d)))
        
        # 主色调（找到最密集的 a,b 区域）
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
            AnalysisResult 对象，包含所有分析结果
        """
        # 加载图像
        rgb = self.load_image(image_path)
        
        # 转换到 Lab 空间
        lab = self.rgb_to_lab(rgb)
        
        # 提取统计特征
        statistics = self.extract_statistics(lab)
        
        # 提取直方图
        histogram = self.extract_histogram(lab)
        
        # 提取分布特征
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
            rgb_array: RGB 图像数组，shape=(H, W, 3)
            
        Returns:
            AnalysisResult 对象
        """
        # 转换到 Lab 空间
        lab = self.rgb_to_lab(rgb_array)
        
        # 提取统计特征
        statistics = self.extract_statistics(lab)
        
        # 提取直方图
        histogram = self.extract_histogram(lab)
        
        # 提取分布特征
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


if __name__ == "__main__":
    # 简单测试
    import sys
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        result = analyze_image(image_path)
        
        print(f"Image shape: {result.image_shape}")
        print(f"\nStatistics:")
        print(f"  Mean (L,a,b): {result.statistics.mean_array()}")
        print(f"  Std  (L,a,b): {result.statistics.std_array()}")
        print(f"\nDistribution:")
        print(f"  L range: {result.distribution.L_range}")
        print(f"  a range: {result.distribution.a_range}")
        print(f"  b range: {result.distribution.b_range}")
        print(f"  Gamut coverage: {result.distribution.gamut_coverage:.2f}%")
        print(f"  Color entropy: {result.distribution.color_entropy:.2f}")
        print(f"  Dominant color (L,a,b): {result.distribution.dominant_color}")
    else:
        print("Usage: python color_analyzer.py <image_path>")

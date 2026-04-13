"""
色彩迁移模块 - Color Transfer

实现 Reinhard 色彩迁移算法，用于将参考图像的色彩风格迁移到目标图像。

算法原理：
Reinhard 等人提出的基于 Lab 色彩空间的统计匹配方法：
1. 将源图像（参考图）和目标图像转换到 Lab 空间
2. 计算源图像的 L, a, b 均值和标准差
3. 计算目标图像的 L, a, b 均值和标准差
4. 对目标图像的每个像素应用变换：
   L_new = (L - mean_L_source) * (std_L_target / std_L_source) + mean_L_target
   a_new = (a - mean_a_source) * (std_a_target / std_a_source) + mean_a_target
   b_new = (b - mean_b_source) * (std_b_target / std_b_source) + mean_b_target

依赖：
- colour-science: 精确的色彩空间转换
- opencv-python: 图像处理
- numpy: 数值计算
"""

import numpy as np
import cv2
from typing import Dict, Tuple, Optional, Union, Callable
from dataclasses import dataclass
from pathlib import Path

from color_analyzer import ColorAnalyzer, ColorStatistics, AnalysisResult


@dataclass
class TransferConfig:
    """色彩迁移配置"""
    # 迁移强度 (0.0-1.0)
    strength: float = 1.0
    
    # 是否使用色彩校正（防止色域外颜色）
    clip_out_of_gamut: bool = True
    
    # 每个通道的独立强度
    L_strength: Optional[float] = None
    a_strength: Optional[float] = None
    b_strength: Optional[float] = None
    
    def get_channel_strengths(self) -> Tuple[float, float, float]:
        """获取各通道的迁移强度"""
        L_s = self.L_strength if self.L_strength is not None else self.strength
        a_s = self.a_strength if self.a_strength is not None else self.strength
        b_s = self.b_strength if self.b_strength is not None else self.strength
        return (L_s, a_s, b_s)


@dataclass
class TransferResult:
    """色彩迁移结果"""
    # 迁移后的 Lab 图像
    lab_result: np.ndarray
    
    # 迁移后的 RGB 图像（归一化到 0-1）
    rgb_result: np.ndarray
    
    # 使用的源图像统计信息
    source_stats: ColorStatistics
    
    # 使用的目标图像统计信息
    target_stats: ColorStatistics
    
    # 变换参数
    transform_params: Dict[str, float]
    
    def to_rgb_uint8(self) -> np.ndarray:
        """转换为 uint8 RGB 格式（0-255）"""
        return (self.rgb_result * 255).astype(np.uint8)


class ReinhardColorTransfer:
    """
    Reinhard 色彩迁移实现
    
    基于论文：
    "Color Transfer between Images" by Erik Reinhard et al. (2001)
    """
    
    def __init__(self, config: TransferConfig = None):
        """
        初始化色彩迁移器
        
        Args:
            config: 迁移配置
        """
        self.config = config or TransferConfig()
        self.analyzer = ColorAnalyzer()
    
    def compute_statistics(self, lab_image: np.ndarray) -> ColorStatistics:
        """
        计算 Lab 图像的统计特征
        
        Args:
            lab_image: Lab 图像数组
            
        Returns:
            ColorStatistics 对象
        """
        return self.analyzer.extract_statistics(lab_image)
    
    def build_transformation_matrix(self, source_stats: ColorStatistics,
                                     target_stats: ColorStatistics) -> np.ndarray:
        """
        构建色彩变换矩阵
        
        变换公式（每个通道独立）：
        new = (old - mean_source) * (std_target / std_source) + mean_target
        
        可以表示为仿射变换：new = scale * old + offset
        
        Args:
            source_stats: 源图像统计信息
            target_stats: 目标图像统计信息
            
        Returns:
            变换矩阵，shape=(3, 2)，每行 [scale, offset]
        """
        src_mean = source_stats.mean_array()
        src_std = source_stats.std_array()
        tgt_mean = target_stats.mean_array()
        tgt_std = target_stats.std_array()
        
        # 防止除零
        src_std = np.maximum(src_std, 1e-6)
        
        # 计算缩放因子
        scale = tgt_std / src_std
        
        # 计算偏移量
        offset = tgt_mean - src_mean * scale
        
        # 构建变换矩阵 [scale, offset]
        transform_matrix = np.column_stack([scale, offset])
        
        return transform_matrix
    
    def transfer(self, source_lab: np.ndarray, target_lab: np.ndarray,
                 config: TransferConfig = None) -> TransferResult:
        """
        执行色彩迁移
        
        Args:
            source_lab: 源图像（参考图）的 Lab 数组
            target_lab: 目标图像（待处理图）的 Lab 数组
            config: 迁移配置（可选，覆盖实例配置）
            
        Returns:
            TransferResult 对象
        """
        cfg = config or self.config
        L_s, a_s, b_s = cfg.get_channel_strengths()
        
        # 计算统计特征
        source_stats = self.compute_statistics(source_lab)
        target_stats = self.compute_statistics(target_lab)
        
        # 获取统计值
        src_mean = source_stats.mean_array()
        src_std = source_stats.std_array()
        tgt_mean = target_stats.mean_array()
        tgt_std = target_stats.std_array()
        
        # 防止除零
        src_std_safe = np.maximum(src_std, 1e-6)
        
        # 计算变换参数
        scale = tgt_std / src_std_safe
        offset = tgt_mean - src_mean * scale
        
        # 应用强度因子
        scale_adjusted = 1 + (scale - 1) * np.array([L_s, a_s, b_s])
        offset_adjusted = offset * np.array([L_s, a_s, b_s])
        
        # 执行变换
        lab_result = np.zeros_like(target_lab)
        for i in range(3):
            lab_result[:, :, i] = (target_lab[:, :, i] - src_mean[i]) * scale_adjusted[i] + tgt_mean[i]
        
        # 处理色域外颜色
        if cfg.clip_out_of_gamut:
            lab_result = self._clip_to_gamut(lab_result)
        
        # 转换回 RGB
        rgb_result = self.analyzer.lab_to_rgb(lab_result)
        
        # 构建变换参数字典
        transform_params = {
            'source_mean_L': float(src_mean[0]),
            'source_mean_a': float(src_mean[1]),
            'source_mean_b': float(src_mean[2]),
            'source_std_L': float(src_std[0]),
            'source_std_a': float(src_std[1]),
            'source_std_b': float(src_std[2]),
            'target_mean_L': float(tgt_mean[0]),
            'target_mean_a': float(tgt_mean[1]),
            'target_mean_b': float(tgt_mean[2]),
            'target_std_L': float(tgt_std[0]),
            'target_std_a': float(tgt_std[1]),
            'target_std_b': float(tgt_std[2]),
            'scale_L': float(scale[0]),
            'scale_a': float(scale[1]),
            'scale_b': float(scale[2]),
            'strength': cfg.strength
        }
        
        return TransferResult(
            lab_result=lab_result,
            rgb_result=rgb_result,
            source_stats=source_stats,
            target_stats=target_stats,
            transform_params=transform_params
        )
    
    def _clip_to_gamut(self, lab: np.ndarray) -> np.ndarray:
        """
        裁剪到有效 Lab 色域
        
        Args:
            lab: Lab 图像数组
            
        Returns:
            裁剪后的 Lab 数组
        """
        lab_clipped = lab.copy()
        
        # L: 0-100
        lab_clipped[:, :, 0] = np.clip(lab_clipped[:, :, 0], 0, 100)
        
        # a, b: -128-127 (理论范围，实际可能更小)
        lab_clipped[:, :, 1] = np.clip(lab_clipped[:, :, 1], -128, 127)
        lab_clipped[:, :, 2] = np.clip(lab_clipped[:, :, 2], -128, 127)
        
        return lab_clipped
    
    def transfer_images(self, source_path: Union[str, Path],
                        target_path: Union[str, Path],
                        config: TransferConfig = None) -> TransferResult:
        """
        从图像文件执行色彩迁移
        
        Args:
            source_path: 源图像（参考图）路径
            target_path: 目标图像（待处理图）路径
            config: 迁移配置
            
        Returns:
            TransferResult 对象
        """
        # 加载并转换图像
        source_rgb = self.analyzer.load_image(source_path)
        target_rgb = self.analyzer.load_image(target_path)
        
        source_lab = self.analyzer.rgb_to_lab(source_rgb)
        target_lab = self.analyzer.rgb_to_lab(target_rgb)
        
        # 执行迁移
        return self.transfer(source_lab, target_lab, config)
    
    def transfer_from_analysis(self, source_analysis: AnalysisResult,
                                target_rgb: np.ndarray,
                                config: TransferConfig = None) -> TransferResult:
        """
        从已有的分析结果执行色彩迁移
        
        Args:
            source_analysis: 源图像的分析结果
            target_rgb: 目标图像的 RGB 数组
            config: 迁移配置
            
        Returns:
            TransferResult 对象
        """
        # 转换目标图像到 Lab
        target_lab = self.analyzer.rgb_to_lab(target_rgb)
        target_stats = self.analyzer.extract_statistics(target_lab)
        
        # 使用源图像的统计信息
        source_stats = source_analysis.statistics
        
        # 构建变换参数
        src_mean = source_stats.mean_array()
        src_std = source_stats.std_array()
        tgt_mean = target_stats.mean_array()
        tgt_std = target_stats.std_array()
        
        cfg = config or self.config
        L_s, a_s, b_s = cfg.get_channel_strengths()
        
        # 防止除零
        src_std_safe = np.maximum(src_std, 1e-6)
        
        # 计算变换
        scale = tgt_std / src_std_safe
        offset = tgt_mean - src_mean * scale
        
        # 应用强度因子
        scale_adjusted = 1 + (scale - 1) * np.array([L_s, a_s, b_s])
        offset_adjusted = offset * np.array([L_s, a_s, b_s])
        
        # 执行变换
        lab_result = np.zeros_like(target_lab)
        for i in range(3):
            lab_result[:, :, i] = (target_lab[:, :, i] - src_mean[i]) * scale_adjusted[i] + tgt_mean[i]
        
        # 处理色域外颜色
        if cfg.clip_out_of_gamut:
            lab_result = self._clip_to_gamut(lab_result)
        
        # 转换回 RGB
        rgb_result = self.analyzer.lab_to_rgb(lab_result)
        
        transform_params = {
            'source_mean_L': float(src_mean[0]),
            'source_mean_a': float(src_mean[1]),
            'source_mean_b': float(src_mean[2]),
            'source_std_L': float(src_std[0]),
            'source_std_a': float(src_std[1]),
            'source_std_b': float(src_std[2]),
            'target_mean_L': float(tgt_mean[0]),
            'target_mean_a': float(tgt_mean[1]),
            'target_mean_b': float(tgt_mean[2]),
            'target_std_L': float(tgt_std[0]),
            'target_std_a': float(tgt_std[1]),
            'target_std_b': float(tgt_std[2]),
            'scale_L': float(scale[0]),
            'scale_a': float(scale[1]),
            'scale_b': float(scale[2]),
            'strength': cfg.strength
        }
        
        return TransferResult(
            lab_result=lab_result,
            rgb_result=rgb_result,
            source_stats=source_stats,
            target_stats=target_stats,
            transform_params=transform_params
        )


class LUTTransformBuilder:
    """
    LUT 变换构建器
    
    基于 Reinhard 算法构建可用于 LUT 生成的变换函数
    """
    
    def __init__(self, source_stats: ColorStatistics, 
                 target_stats: ColorStatistics,
                 strength: float = 1.0):
        """
        初始化 LUT 变换构建器
        
        Args:
            source_stats: 源图像统计信息
            target_stats: 目标图像统计信息
            strength: 迁移强度
        """
        self.source_stats = source_stats
        self.target_stats = target_stats
        self.strength = strength
        
        # 预计算变换参数
        src_mean = source_stats.mean_array()
        src_std = source_stats.std_array()
        tgt_mean = target_stats.mean_array()
        tgt_std = target_stats.std_array()
        
        # 防止除零
        src_std_safe = np.maximum(src_std, 1e-6)
        
        self.scale = tgt_std / src_std_safe
        self.offset = tgt_mean - src_mean * self.scale
        
        # 应用强度因子
        self.scale_adjusted = 1 + (self.scale - 1) * strength
        self.offset_adjusted = self.offset * strength
    
    def build_transform_func(self) -> Callable[[np.ndarray], np.ndarray]:
        """
        构建变换函数（用于 LUT 生成）
        
        Returns:
            变换函数，输入 RGB(0-1)，输出 RGB(0-1)
        """
        analyzer = ColorAnalyzer()
        
        def transform(rgb: np.ndarray) -> np.ndarray:
            """
            应用 Reinhard 变换
            
            Args:
                rgb: RGB 数组，shape=(3,) 或 (N, 3)，值范围 0-1
                
            Returns:
                变换后的 RGB 数组
            """
            # 确保是二维数组
            if rgb.ndim == 1:
                rgb = rgb.reshape(1, -1)
            
            # RGB → Lab
            # 注意：这里需要转换单个颜色点，而不是图像
            # 使用简化的转换方法
            lab = analyzer.rgb_to_lab((rgb * 255).astype(np.uint8).reshape(-1, 1, 3))
            lab = lab.reshape(-1, 3)
            
            # 应用变换
            lab_result = np.zeros_like(lab)
            for i in range(3):
                lab_result[:, i] = (lab[:, i] - self.source_stats.mean_array()[i]) * \
                                   self.scale_adjusted[i] + \
                                   self.target_stats.mean_array()[i]
            
            # 裁剪到有效范围
            lab_result[:, 0] = np.clip(lab_result[:, 0], 0, 100)
            lab_result[:, 1] = np.clip(lab_result[:, 1], -128, 127)
            lab_result[:, 2] = np.clip(lab_result[:, 2], -128, 127)
            
            # Lab → RGB
            lab_img = lab_result.reshape(1, -1, 3)
            rgb_result = analyzer.lab_to_rgb(lab_img)
            rgb_result = rgb_result.reshape(-1, 3)
            
            # 裁剪到 0-1
            rgb_result = np.clip(rgb_result, 0, 1)
            
            if rgb_result.shape[0] == 1:
                return rgb_result[0]
            return rgb_result
        
        return transform


def transfer_colors(source_path: Union[str, Path],
                    target_path: Union[str, Path],
                    strength: float = 1.0) -> Tuple[np.ndarray, Dict]:
    """
    便捷函数：执行色彩迁移
    
    Args:
        source_path: 源图像路径
        target_path: 目标图像路径
        strength: 迁移强度 (0.0-1.0)
        
    Returns:
        (rgb_result, transform_params) 元组
    """
    config = TransferConfig(strength=strength)
    transfer = ReinhardColorTransfer(config)
    result = transfer.transfer_images(source_path, target_path)
    return result.rgb_result, result.transform_params


if __name__ == "__main__":
    # 简单测试
    import sys
    
    if len(sys.argv) >= 3:
        source_path = sys.argv[1]
        target_path = sys.argv[2]
        strength = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
        
        print(f"Transferring colors from {source_path} to {target_path}")
        print(f"Strength: {strength}")
        
        rgb_result, params = transfer_colors(source_path, target_path, strength)
        
        print(f"\nTransform parameters:")
        for key, value in params.items():
            print(f"  {key}: {value:.4f}")
        
        print(f"\nResult shape: {rgb_result.shape}")
        print(f"Result range: [{rgb_result.min():.4f}, {rgb_result.max():.4f}]")
        
        # 保存结果（需要额外参数）
        if len(sys.argv) > 4:
            output_path = sys.argv[4]
            result_bgr = (rgb_result[:, :, ::-1] * 255).astype(np.uint8)
            cv2.imwrite(output_path, result_bgr)
            print(f"Saved result to {output_path}")
    else:
        print("Usage: python color_transfer.py <source_image> <target_image> [strength] [output_path]")

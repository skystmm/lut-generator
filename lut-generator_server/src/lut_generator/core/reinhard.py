"""
Reinhard 色彩迁移算法 - ReinhardColorTransfer

基于论文 "Color Transfer between Images" by Erik Reinhard et al. (2001)
实现基于 Lab 空间统计匹配的色彩迁移
"""

import numpy as np
from typing import Dict, Tuple, Optional, Union, Callable
from dataclasses import dataclass
from pathlib import Path

from .color_space import ColorSpaceConverter


@dataclass
class TransferConfig:
    """色彩迁移配置"""
    strength: float = 1.0
    clip_out_of_gamut: bool = True
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
class TransferResult:
    """色彩迁移结果"""
    lab_result: np.ndarray
    rgb_result: np.ndarray
    source_stats: ColorStatistics
    target_stats: ColorStatistics
    transform_params: Dict[str, float]
    
    def to_rgb_uint8(self) -> np.ndarray:
        """转换为 uint8 RGB 格式"""
        return (self.rgb_result * 255).astype(np.uint8)


class ReinhardColorTransfer:
    """
    Reinhard 色彩迁移实现
    
    基于 Lab 空间的统计匹配方法：
    1. 将源图像和目标图像转换到 Lab 空间
    2. 计算均值和标准差
    3. 应用线性变换：new = (old - mean_source) * (std_target / std_source) + mean_target
    """
    
    def __init__(self, config: TransferConfig = None):
        self.config = config or TransferConfig()
        self.converter = ColorSpaceConverter()
    
    def compute_statistics(self, lab_image: np.ndarray) -> ColorStatistics:
        """
        计算 Lab 图像的统计特征
        
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
    
    def build_transformation_matrix(self, source_stats: ColorStatistics,
                                     target_stats: ColorStatistics) -> np.ndarray:
        """
        构建色彩变换矩阵
        
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
        
        src_std = np.maximum(src_std, 1e-6)
        scale = tgt_std / src_std
        offset = tgt_mean - src_mean * scale
        
        return np.column_stack([scale, offset])
    
    def transfer(self, source_lab: np.ndarray, target_lab: np.ndarray,
                 config: TransferConfig = None) -> TransferResult:
        """
        执行色彩迁移
        
        Args:
            source_lab: 源图像（参考图）的 Lab 数组
            target_lab: 目标图像（待处理图）的 Lab 数组
            config: 迁移配置
            
        Returns:
            TransferResult 对象
        """
        cfg = config or self.config
        L_s, a_s, b_s = cfg.get_channel_strengths()
        
        source_stats = self.compute_statistics(source_lab)
        target_stats = self.compute_statistics(target_lab)
        
        src_mean = source_stats.mean_array()
        src_std = source_stats.std_array()
        tgt_mean = target_stats.mean_array()
        tgt_std = target_stats.std_array()
        
        src_std_safe = np.maximum(src_std, 1e-6)
        scale = tgt_std / src_std_safe
        offset = tgt_mean - src_mean * scale
        
        scale_adjusted = 1 + (scale - 1) * np.array([L_s, a_s, b_s])
        
        lab_result = np.zeros_like(target_lab)
        for i in range(3):
            lab_result[:, :, i] = (target_lab[:, :, i] - src_mean[i]) * scale_adjusted[i] + tgt_mean[i]
        
        if cfg.clip_out_of_gamut:
            lab_result = self.converter.clip_to_gamut(lab_result)
        
        rgb_result = self.converter.lab_to_rgb(lab_result)
        
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
    
    def transfer_images(self, source_path: Union[str, Path],
                        target_path: Union[str, Path],
                        config: TransferConfig = None,
                        raw_mode: str = 'half',
                        use_camera_wb: bool = True) -> TransferResult:
        """
        从图像文件执行色彩迁移

        Args:
            source_path: 源图像(参考图)路径
            target_path: 目标图像路径
            config: 迁移配置
            raw_mode: RAW 读取档位
            use_camera_wb: RAW 是否用相机內建白平衡

        Returns:
            TransferResult 对象
        """
        source_rgb = self.converter.load_image(
            source_path, raw_mode=raw_mode, use_camera_wb=use_camera_wb
        )
        target_rgb = self.converter.load_image(
            target_path, raw_mode=raw_mode, use_camera_wb=use_camera_wb
        )
        
        source_lab = self.converter.rgb_to_lab(source_rgb)
        target_lab = self.converter.rgb_to_lab(target_rgb)
        
        return self.transfer(source_lab, target_lab, config)


class LUTTransformBuilder:
    """
    LUT 变换构建器
    
    基于 Reinhard 算法构建可用于 LUT 生成的变换函数
    """
    
    def __init__(self, source_stats: ColorStatistics, 
                 target_stats: ColorStatistics,
                 strength: float = 1.0):
        self.source_stats = source_stats
        self.target_stats = target_stats
        self.strength = strength
        
        src_mean = source_stats.mean_array()
        src_std = source_stats.std_array()
        tgt_mean = target_stats.mean_array()
        tgt_std = target_stats.std_array()
        
        src_std_safe = np.maximum(src_std, 1e-6)
        self.scale = tgt_std / src_std_safe
        self.offset = tgt_mean - src_mean * self.scale
        
        # strength=0 → 恒等变换;strength=1 → 完全迁移
        # scale=1 + offset=0 时(无 source/target 差异时)无论 strength 都恒等
        self.scale_adjusted = 1 + (self.scale - 1) * strength
        # 让 scale 也乘以 strength,这样 strength=0 时 scale=1 也变成 scale=0,
        # 输出 = (lab - src_mean) * 0 + 0 = 0(不是 identity)
        # 正确做法:strength=0 时直接短路返回 identity
        self.offset_adjusted = self.offset * strength
        self._strength_zero = strength == 0.0
    
    def build_transform_func(self) -> Callable[[np.ndarray], np.ndarray]:
        """
        构建变换函数（用于 LUT 生成）
        
        Returns:
            变换函数，输入 RGB(0-1)，输出 RGB(0-1)
        """
        converter = ColorSpaceConverter()

        # 强度=0 短路:返回 identity
        if self._strength_zero:
            def identity_transform(rgb: np.ndarray) -> np.ndarray:
                out = np.clip(rgb.astype(np.float32), 0, 1)
                if out.ndim == 1:
                    return out
                return out
            return identity_transform

        def transform(rgb: np.ndarray) -> np.ndarray:
            if rgb.ndim == 1:
                rgb = rgb.reshape(1, -1)
            
            # RGB → Lab
            lab = converter.rgb_to_lab((rgb * 255).astype(np.uint8).reshape(-1, 1, 3))
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
            rgb_result = converter.lab_to_rgb(lab_img)
            rgb_result = rgb_result.reshape(-1, 3)
            rgb_result = np.clip(rgb_result, 0, 1)
            
            if rgb_result.shape[0] == 1:
                return rgb_result[0]
            return rgb_result
        
        return transform
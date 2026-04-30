"""
3D LUT 生成器 - LUT3DGenerator

基于色彩迁移结果生成 3D LUT
支持 17³/33³/65³ 三种精度
numpy 向量化优化性能
"""

import numpy as np
from typing import Optional, Callable, Union
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from lut_generator.core.reinhard import (
    ColorStatistics, LUTTransformBuilder
)
from lut_generator.core.interpolation import get_interpolator


@dataclass
class LUT3DConfig:
    """3D LUT 配置"""
    grid_size: int = 33
    input_colorspace: str = 'sRGB'
    output_colorspace: str = 'sRGB'
    use_vectorized: bool = True
    interpolation: str = 'trilinear'
    
    def validate(self) -> bool:
        """验证配置有效性"""
        valid_sizes = [17, 33, 65]
        if self.grid_size not in valid_sizes:
            raise ValueError(f"grid_size must be one of {valid_sizes}, got {self.grid_size}")
        
        valid_interpolations = ['trilinear', 'nearest']
        if self.interpolation not in valid_interpolations:
            raise ValueError(f"interpolation must be one of {valid_interpolations}")
        
        return True


@dataclass
class LUT3DMetadata:
    """3D LUT 元数据"""
    created_at: str
    description: str
    source_stats: Optional[ColorStatistics] = None
    target_stats: Optional[ColorStatistics] = None
    transform_params: Optional[dict] = None
    config: Optional[LUT3DConfig] = None


class LUT3DGenerator:
    """
    3D LUT 生成器
    
    基于 Reinhard 色彩迁移算法生成 3D LUT
    """
    
    def __init__(self, config: LUT3DConfig = None):
        self.config = config or LUT3DConfig()
        self.config.validate()
        
        self.lut_data: Optional[np.ndarray] = None
        self.metadata: Optional[LUT3DMetadata] = None
        self._interpolator = get_interpolator(self.config.interpolation)
    
    def generate_from_stats(self, source_stats: ColorStatistics,
                            target_stats: ColorStatistics,
                            strength: float = 1.0) -> np.ndarray:
        """
        从统计信息生成 3D LUT
        
        Args:
            source_stats: 源图像统计信息
            target_stats: 目标图像统计信息
            strength: 迁移强度
            
        Returns:
            3D LUT 数组
        """
        builder = LUTTransformBuilder(source_stats, target_stats, strength)
        transform_func = builder.build_transform_func()
        
        self.lut_data = self._generate_lut_grid(transform_func)
        
        self.metadata = LUT3DMetadata(
            created_at=datetime.now().isoformat(),
            description="LUT generated from stats",
            source_stats=source_stats,
            target_stats=target_stats,
            config=self.config
        )
        
        return self.lut_data
    
    def generate_from_images(self, source_path: Union[str, Path],
                             target_path: Union[str, Path],
                             strength: float = 1.0) -> np.ndarray:
        """
        从图像文件生成 3D LUT
        
        Args:
            source_path: 源图像路径
            target_path: 目标图像路径
            strength: 迁移强度
            
        Returns:
            3D LUT 数组
        """
        from lut_generator.core.color_space import ColorSpaceConverter
        from lut_generator.core.reinhard import ReinhardColorTransfer
        
        converter = ColorSpaceConverter()
        transfer = ReinhardColorTransfer()
        
        source_rgb = converter.load_image(source_path)
        target_rgb = converter.load_image(target_path)
        
        source_lab = converter.rgb_to_lab(source_rgb)
        target_lab = converter.rgb_to_lab(target_rgb)
        
        source_stats = transfer.compute_statistics(source_lab)
        target_stats = transfer.compute_statistics(target_lab)
        
        self.lut_data = self.generate_from_stats(source_stats, target_stats, strength)
        
        self.metadata = LUT3DMetadata(
            created_at=datetime.now().isoformat(),
            description=f"LUT generated from {Path(source_path).name} to {Path(target_path).name}",
            source_stats=source_stats,
            target_stats=target_stats,
            config=self.config
        )
        
        return self.lut_data
    
    def generate_from_transform(self, transform_func: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
        """
        从自定义变换函数生成 3D LUT
        
        Args:
            transform_func: 变换函数
            
        Returns:
            3D LUT 数组
        """
        return self._generate_lut_grid(transform_func)
    
    def _generate_lut_grid(self, transform_func: Callable) -> np.ndarray:
        """
        生成 LUT 网格
        
        Args:
            transform_func: 变换函数
            
        Returns:
            3D LUT 数组
        """
        grid_size = self.config.grid_size
        
        if self.config.use_vectorized:
            return self._generate_vectorized(transform_func, grid_size)
        else:
            return self._generate_iterative(transform_func, grid_size)
    
    def _generate_vectorized(self, transform_func: Callable, grid_size: int) -> np.ndarray:
        """
        向量化生成 LUT（高性能）
        """
        grid_values = np.linspace(0, 1, grid_size)
        R_grid, G_grid, B_grid = np.meshgrid(grid_values, grid_values, grid_values, indexing='ij')
        
        input_rgb = np.column_stack([
            R_grid.flatten(),
            G_grid.flatten(),
            B_grid.flatten()
        ])
        
        output_rgb = transform_func(input_rgb)
        output_rgb = np.clip(output_rgb, 0, 1)
        
        lut_data = output_rgb.reshape(grid_size, grid_size, grid_size, 3)
        return lut_data
    
    def _generate_iterative(self, transform_func: Callable, grid_size: int) -> np.ndarray:
        """
        迭代生成 LUT（低内存）
        """
        grid_values = np.linspace(0, 1, grid_size)
        lut_data = np.zeros((grid_size, grid_size, grid_size, 3), dtype=np.float32)
        
        for i in range(grid_size):
            for j in range(grid_size):
                for k in range(grid_size):
                    input_rgb = np.array([grid_values[i], grid_values[j], grid_values[k]])
                    output_rgb = transform_func(input_rgb)
                    lut_data[i, j, k] = np.clip(output_rgb, 0, 1)
        
        return lut_data
    
    def apply(self, rgb: np.ndarray) -> np.ndarray:
        """
        应用 LUT 变换
        
        Args:
            rgb: 输入 RGB 值
            
        Returns:
            变换后的 RGB 值
        """
        if self.lut_data is None:
            raise ValueError("LUT data not generated. Call generate_* first.")
        
        return self._interpolator.interpolate(self.lut_data, rgb, self.config.grid_size)
    
    def get_lut_data(self) -> Optional[np.ndarray]:
        """获取 LUT 数据"""
        return self.lut_data
    
    def get_metadata(self) -> Optional[LUT3DMetadata]:
        """获取 LUT 元数据"""
        return self.metadata


def generate_lut_3d(source_stats: ColorStatistics,
                    target_stats: ColorStatistics,
                    grid_size: int = 33,
                    strength: float = 1.0) -> np.ndarray:
    """
    便捷函数：生成 3D LUT
    
    Args:
        source_stats: 源图像统计信息
        target_stats: 目标图像统计信息
        grid_size: LUT 精度
        strength: 迁移强度
        
    Returns:
        3D LUT 数组
    """
    config = LUT3DConfig(grid_size=grid_size)
    generator = LUT3DGenerator(config)
    return generator.generate_from_stats(source_stats, target_stats, strength)
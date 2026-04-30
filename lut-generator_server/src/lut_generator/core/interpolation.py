"""
插值算法模块 - Interpolation

提供三线性插值和最近邻插值算法
用于 LUT 应用时的颜色查找
"""

import numpy as np
from typing import Tuple


class Interpolator:
    """
    插值器基类
    """
    
    def interpolate(self, lut_data: np.ndarray, rgb: np.ndarray, grid_size: int) -> np.ndarray:
        """
        执行插值
        
        Args:
            lut_data: LUT 数据，shape=(grid_size, grid_size, grid_size, 3)
            rgb: 输入 RGB 值，shape=(N, 3) 或 (3,)，范围 0-1
            grid_size: LUT 网格大小
            
        Returns:
            插值后的 RGB 值
        """
        raise NotImplementedError


class TrilinearInterpolator(Interpolator):
    """
    三线性插值器
    
    对于不在 LUT 网格点上的 RGB 值，使用三线性插值计算
    """
    
    def interpolate(self, lut_data: np.ndarray, rgb: np.ndarray, grid_size: int) -> np.ndarray:
        """
        应用三线性插值
        
        Args:
            lut_data: LUT 数据
            rgb: 输入 RGB 值，shape=(N, 3) 或 (3,)
            grid_size: LUT 网格大小
            
        Returns:
            变换后的 RGB 值
        """
        # 确保输入是二维数组
        if rgb.ndim == 1:
            rgb = rgb.reshape(1, -1)
            single_input = True
        else:
            single_input = False
        
        # 计算网格坐标
        coords = rgb * (grid_size - 1)
        
        # 获取整数和小数部分
        coords_floor = np.floor(coords).astype(np.int32)
        coords_ceil = np.ceil(coords).astype(np.int32)
        coords_frac = coords - coords_floor
        
        # 限制索引在有效范围内
        coords_floor = np.clip(coords_floor, 0, grid_size - 1)
        coords_ceil = np.clip(coords_ceil, 0, grid_size - 1)
        
        # 获取 8 个顶点的值
        v000 = lut_data[coords_floor[:, 0], coords_floor[:, 1], coords_floor[:, 2]]
        v100 = lut_data[coords_ceil[:, 0], coords_floor[:, 1], coords_floor[:, 2]]
        v010 = lut_data[coords_floor[:, 0], coords_ceil[:, 1], coords_floor[:, 2]]
        v110 = lut_data[coords_ceil[:, 0], coords_ceil[:, 1], coords_floor[:, 2]]
        v001 = lut_data[coords_floor[:, 0], coords_floor[:, 1], coords_ceil[:, 2]]
        v101 = lut_data[coords_ceil[:, 0], coords_floor[:, 1], coords_ceil[:, 2]]
        v011 = lut_data[coords_floor[:, 0], coords_ceil[:, 1], coords_ceil[:, 2]]
        v111 = lut_data[coords_ceil[:, 0], coords_ceil[:, 1], coords_ceil[:, 2]]
        
        # 三线性插值
        # R 方向
        v00 = v000 * (1 - coords_frac[:, 0:1]) + v100 * coords_frac[:, 0:1]
        v01 = v001 * (1 - coords_frac[:, 0:1]) + v101 * coords_frac[:, 0:1]
        v10 = v010 * (1 - coords_frac[:, 0:1]) + v110 * coords_frac[:, 0:1]
        v11 = v011 * (1 - coords_frac[:, 0:1]) + v111 * coords_frac[:, 0:1]
        
        # G 方向
        v0 = v00 * (1 - coords_frac[:, 1:2]) + v10 * coords_frac[:, 1:2]
        v1 = v01 * (1 - coords_frac[:, 1:2]) + v11 * coords_frac[:, 1:2]
        
        # B 方向
        result = v0 * (1 - coords_frac[:, 2:3]) + v1 * coords_frac[:, 2:3]
        
        if single_input:
            return result[0]
        return result


class NearestNeighborInterpolator(Interpolator):
    """
    最近邻插值器
    
    对于不在 LUT 网格点上的 RGB 值，使用最近的网格点值
    """
    
    def interpolate(self, lut_data: np.ndarray, rgb: np.ndarray, grid_size: int) -> np.ndarray:
        """
        应用最近邻插值
        
        Args:
            lut_data: LUT 数据
            rgb: 输入 RGB 值
            grid_size: LUT 网格大小
            
        Returns:
            变换后的 RGB 值
        """
        if rgb.ndim == 1:
            rgb = rgb.reshape(1, -1)
            single_input = True
        else:
            single_input = False
        
        # 计算最近的网格索引
        coords = np.round(rgb * (grid_size - 1)).astype(np.int32)
        coords = np.clip(coords, 0, grid_size - 1)
        
        # 获取 LUT 值
        result = lut_data[coords[:, 0], coords[:, 1], coords[:, 2]]
        
        if single_input:
            return result[0]
        return result


def get_interpolator(method: str = 'trilinear') -> Interpolator:
    """
    获取插值器
    
    Args:
        method: 插值方法 ('trilinear' 或 'nearest')
        
    Returns:
        Interpolator 实例
    """
    if method == 'trilinear':
        return TrilinearInterpolator()
    elif method == 'nearest':
        return NearestNeighborInterpolator()
    else:
        raise ValueError(f"Unknown interpolation method: {method}")
"""
3D LUT 生成器 - LUT3DGenerator

基于色彩迁移结果生成 3D LUT（Look-Up Table）
支持 17³/33³/65³ 三种精度
使用三线性插值填充 LUT 网格
numpy 向量化优化性能

输出格式兼容 DaVinci Resolve、Premiere Pro、Final Cut Pro 等专业软件
"""

import numpy as np
from typing import Tuple, Optional, Callable, Union
from dataclasses import dataclass
from pathlib import Path

from color_analyzer import ColorAnalyzer, ColorStatistics
from color_transfer import ReinhardColorTransfer, TransferConfig, LUTTransformBuilder


@dataclass
class LUT3DConfig:
    """3D LUT 配置"""
    # LUT 精度（每维网格点数）
    # 标准值：17, 33, 65
    grid_size: int = 33
    
    # 输入色彩空间
    input_colorspace: str = 'sRGB'
    
    # 输出色彩空间
    output_colorspace: str = 'sRGB'
    
    # 是否使用向量化优化
    use_vectorized: bool = True
    
    # 插值方法
    # 'trilinear': 三线性插值（推荐）
    # 'nearest': 最近邻插值（更快但质量略低）
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
    # 创建时间
    created_at: str
    
    # 描述
    description: str
    
    # 源图像统计信息
    source_stats: Optional[ColorStatistics] = None
    
    # 目标图像统计信息
    target_stats: Optional[ColorStatistics] = None
    
    # 变换参数
    transform_params: Optional[dict] = None
    
    # LUT 配置
    config: Optional[LUT3DConfig] = None


class LUT3DGenerator:
    """
    3D LUT 生成器
    
    基于 Reinhard 色彩迁移算法生成 3D LUT
    支持标准精度（17³/33³/65³）
    使用 numpy 向量化优化性能
    """
    
    def __init__(self, config: LUT3DConfig = None):
        """
        初始化 LUT 生成器
        
        Args:
            config: LUT 配置
        """
        self.config = config or LUT3DConfig()
        self.config.validate()
        
        self.analyzer = ColorAnalyzer()
        self.lut_data: Optional[np.ndarray] = None
        self.metadata: Optional[LUT3DMetadata] = None
    
    def generate_from_stats(self, source_stats: ColorStatistics,
                            target_stats: ColorStatistics,
                            strength: float = 1.0) -> np.ndarray:
        """
        从统计信息生成 3D LUT
        
        Args:
            source_stats: 源图像（参考图）统计信息
            target_stats: 目标图像统计信息
            strength: 迁移强度 (0.0-1.0)
            
        Returns:
            3D LUT 数组，shape=(grid_size, grid_size, grid_size, 3)
            值范围 0-1，表示变换后的 RGB 值
        """
        # 构建变换器
        builder = LUTTransformBuilder(source_stats, target_stats, strength)
        transform_func = builder.build_transform_func()
        
        # 生成 LUT
        self.lut_data = self._generate_lut_grid(transform_func)
        
        # 保存元数据
        from datetime import datetime
        self.metadata = LUT3DMetadata(
            created_at=datetime.now().isoformat(),
            description=f"LUT generated from stats",
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
            source_path: 源图像（参考图）路径
            target_path: 目标图像（待处理图）路径
            strength: 迁移强度 (0.0-1.0)
            
        Returns:
            3D LUT 数组，shape=(grid_size, grid_size, grid_size, 3)
        """
        # 分析源图像
        source_lab = self.analyzer.rgb_to_lab(
            self.analyzer.load_image(source_path)
        )
        source_stats = self.analyzer.extract_statistics(source_lab)
        
        # 分析目标图像
        target_lab = self.analyzer.rgb_to_lab(
            self.analyzer.load_image(target_path)
        )
        target_stats = self.analyzer.extract_statistics(target_lab)
        
        # 生成 LUT
        self.lut_data = self.generate_from_stats(source_stats, target_stats, strength)
        
        # 保存元数据
        from datetime import datetime
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
            transform_func: 变换函数，输入 RGB(0-1)，输出 RGB(0-1)
                           支持 shape=(3,) 或 (N, 3)
            
        Returns:
            3D LUT 数组，shape=(grid_size, grid_size, grid_size, 3)
        """
        return self._generate_lut_grid(transform_func)
    
    def _generate_lut_grid(self, transform_func: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
        """
        生成 LUT 网格
        
        Args:
            transform_func: 变换函数
            
        Returns:
            3D LUT 数组，shape=(grid_size, grid_size, grid_size, 3)
        """
        grid_size = self.config.grid_size
        
        if self.config.use_vectorized:
            return self._generate_vectorized(transform_func, grid_size)
        else:
            return self._generate_iterative(transform_func, grid_size)
    
    def _generate_vectorized(self, transform_func: Callable[[np.ndarray], np.ndarray],
                             grid_size: int) -> np.ndarray:
        """
        向量化生成 LUT（高性能）
        
        使用 numpy 向量化一次性处理所有网格点
        比迭代方法快 10-100 倍
        
        Args:
            transform_func: 变换函数
            grid_size: 网格大小
            
        Returns:
            3D LUT 数组
        """
        # 生成归一化网格坐标 (0-1)
        # shape=(grid_size,)
        grid_values = np.linspace(0, 1, grid_size)
        
        # 创建 3D 网格
        # shape=(grid_size, grid_size, grid_size)
        R_grid, G_grid, B_grid = np.meshgrid(grid_values, grid_values, grid_values, indexing='ij')
        
        # 合并为 (N, 3) 格式，N = grid_size³
        # shape=(grid_size³, 3)
        input_rgb = np.column_stack([
            R_grid.flatten(),
            G_grid.flatten(),
            B_grid.flatten()
        ])
        
        # 应用变换（向量化处理）
        output_rgb = transform_func(input_rgb)
        
        # 确保输出在 0-1 范围内
        output_rgb = np.clip(output_rgb, 0, 1)
        
        # 重塑为 3D 网格
        # shape=(grid_size, grid_size, grid_size, 3)
        lut_data = output_rgb.reshape(grid_size, grid_size, grid_size, 3)
        
        return lut_data
    
    def _generate_iterative(self, transform_func: Callable[[np.ndarray], np.ndarray],
                            grid_size: int) -> np.ndarray:
        """
        迭代生成 LUT（低内存，慢速）
        
        逐个网格点处理，内存占用低但速度慢
        仅用于调试或内存受限场景
        
        Args:
            transform_func: 变换函数
            grid_size: 网格大小
            
        Returns:
            3D LUT 数组
        """
        # 生成归一化网格坐标
        grid_values = np.linspace(0, 1, grid_size)
        
        # 初始化 LUT 数组
        lut_data = np.zeros((grid_size, grid_size, grid_size, 3), dtype=np.float32)
        
        # 逐个网格点处理
        for i in range(grid_size):
            for j in range(grid_size):
                for k in range(grid_size):
                    # 输入 RGB 值
                    input_rgb = np.array([grid_values[i], grid_values[j], grid_values[k]])
                    
                    # 应用变换
                    output_rgb = transform_func(input_rgb)
                    
                    # 存储结果
                    lut_data[i, j, k] = np.clip(output_rgb, 0, 1)
        
        return lut_data
    
    def apply_trilinear_interpolation(self, rgb: np.ndarray) -> np.ndarray:
        """
        应用三线性插值
        
        对于不在 LUT 网格点上的 RGB 值，使用三线性插值计算
        
        Args:
            rgb: 输入 RGB 值，shape=(3,) 或 (N, 3)，范围 0-1
            
        Returns:
            变换后的 RGB 值，shape 与输入相同
        """
        if self.lut_data is None:
            raise ValueError("LUT data not generated. Call generate_* first.")
        
        grid_size = self.config.grid_size
        
        # 确保输入是二维数组
        if rgb.ndim == 1:
            rgb = rgb.reshape(1, -1)
            single_input = True
        else:
            single_input = False
        
        # 计算网格坐标（0 到 grid_size-1）
        # 注意：LUT 索引是 (R, G, B) 对应 (i, j, k)
        coords = rgb * (grid_size - 1)
        
        # 获取每个点的整数和小数部分
        coords_floor = np.floor(coords).astype(np.int32)
        coords_ceil = np.ceil(coords).astype(np.int32)
        coords_frac = coords - coords_floor
        
        # 限制索引在有效范围内
        coords_floor = np.clip(coords_floor, 0, grid_size - 1)
        coords_ceil = np.clip(coords_ceil, 0, grid_size - 1)
        
        # 获取 8 个顶点的值
        # 顶点索引：(000, 100, 010, 110, 001, 101, 011, 111)
        v000 = self.lut_data[coords_floor[:, 0], coords_floor[:, 1], coords_floor[:, 2]]
        v100 = self.lut_data[coords_ceil[:, 0], coords_floor[:, 1], coords_floor[:, 2]]
        v010 = self.lut_data[coords_floor[:, 0], coords_ceil[:, 1], coords_floor[:, 2]]
        v110 = self.lut_data[coords_ceil[:, 0], coords_ceil[:, 1], coords_floor[:, 2]]
        v001 = self.lut_data[coords_floor[:, 0], coords_floor[:, 1], coords_ceil[:, 2]]
        v101 = self.lut_data[coords_ceil[:, 0], coords_floor[:, 1], coords_ceil[:, 2]]
        v011 = self.lut_data[coords_floor[:, 0], coords_ceil[:, 1], coords_ceil[:, 2]]
        v111 = self.lut_data[coords_ceil[:, 0], coords_ceil[:, 1], coords_ceil[:, 2]]
        
        # 三线性插值
        # 先在 R 方向插值
        v00 = v000 * (1 - coords_frac[:, 0:1]) + v100 * coords_frac[:, 0:1]
        v01 = v001 * (1 - coords_frac[:, 0:1]) + v101 * coords_frac[:, 0:1]
        v10 = v010 * (1 - coords_frac[:, 0:1]) + v110 * coords_frac[:, 0:1]
        v11 = v011 * (1 - coords_frac[:, 0:1]) + v111 * coords_frac[:, 0:1]
        
        # 再在 G 方向插值
        v0 = v00 * (1 - coords_frac[:, 1:2]) + v10 * coords_frac[:, 1:2]
        v1 = v01 * (1 - coords_frac[:, 1:2]) + v11 * coords_frac[:, 1:2]
        
        # 最后在 B 方向插值
        result = v0 * (1 - coords_frac[:, 2:3]) + v1 * coords_frac[:, 2:3]
        
        if single_input:
            return result[0]
        return result
    
    def apply_nearest_interpolation(self, rgb: np.ndarray) -> np.ndarray:
        """
        应用最近邻插值
        
        对于不在 LUT 网格点上的 RGB 值，使用最近的网格点值
        
        Args:
            rgb: 输入 RGB 值，shape=(3,) 或 (N, 3)，范围 0-1
            
        Returns:
            变换后的 RGB 值，shape 与输入相同
        """
        if self.lut_data is None:
            raise ValueError("LUT data not generated. Call generate_* first.")
        
        grid_size = self.config.grid_size
        
        # 确保输入是二维数组
        if rgb.ndim == 1:
            rgb = rgb.reshape(1, -1)
            single_input = True
        else:
            single_input = False
        
        # 计算最近的网格索引
        coords = np.round(rgb * (grid_size - 1)).astype(np.int32)
        coords = np.clip(coords, 0, grid_size - 1)
        
        # 获取 LUT 值
        result = self.lut_data[coords[:, 0], coords[:, 1], coords[:, 2]]
        
        if single_input:
            return result[0]
        return result
    
    def apply(self, rgb: np.ndarray) -> np.ndarray:
        """
        应用 LUT 变换
        
        根据配置的插值方法自动选择
        
        Args:
            rgb: 输入 RGB 值，shape=(3,) 或 (N, 3)，范围 0-1
            
        Returns:
            变换后的 RGB 值
        """
        if self.config.interpolation == 'trilinear':
            return self.apply_trilinear_interpolation(rgb)
        else:
            return self.apply_nearest_interpolation(rgb)
    
    def get_lut_data(self) -> Optional[np.ndarray]:
        """获取 LUT 数据"""
        return self.lut_data
    
    def get_metadata(self) -> Optional[LUT3DMetadata]:
        """获取 LUT 元数据"""
        return self.metadata


def generate_lut_3d(source_stats: ColorStatistics,
                    target_stats: ColorStatistics,
                    grid_size: int = 33,
                    strength: float = 1.0,
                    use_vectorized: bool = True) -> np.ndarray:
    """
    便捷函数：生成 3D LUT
    
    Args:
        source_stats: 源图像统计信息
        target_stats: 目标图像统计信息
        grid_size: LUT 精度（17/33/65）
        strength: 迁移强度
        use_vectorized: 是否使用向量化优化
        
    Returns:
        3D LUT 数组，shape=(grid_size, grid_size, grid_size, 3)
    """
    config = LUT3DConfig(grid_size=grid_size, use_vectorized=use_vectorized)
    generator = LUT3DGenerator(config)
    return generator.generate_from_stats(source_stats, target_stats, strength)


if __name__ == "__main__":
    # 简单测试
    import sys
    from datetime import datetime
    
    print("3D LUT Generator Test")
    print("=" * 50)
    
    # 创建模拟统计信息
    source_stats = ColorStatistics(
        mean_L=50.0, mean_a=10.0, mean_b=20.0,
        std_L=20.0, std_a=15.0, std_b=18.0,
        var_L=400.0, var_a=225.0, var_b=324.0
    )
    
    target_stats = ColorStatistics(
        mean_L=60.0, mean_a=5.0, mean_b=30.0,
        std_L=25.0, std_a=12.0, std_b=22.0,
        var_L=625.0, var_a=144.0, var_b=484.0
    )
    
    # 测试不同精度
    for grid_size in [17, 33, 65]:
        print(f"\nGenerating LUT with grid_size={grid_size}...")
        start_time = datetime.now()
        
        lut = generate_lut_3d(source_stats, target_stats, grid_size=grid_size)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"  Shape: {lut.shape}")
        print(f"  Data type: {lut.dtype}")
        print(f"  Value range: [{lut.min():.4f}, {lut.max():.4f}]")
        print(f"  Generation time: {duration:.3f}s")
        print(f"  Memory size: {lut.nbytes / 1024:.2f} KB")
    
    print("\nTest completed!")

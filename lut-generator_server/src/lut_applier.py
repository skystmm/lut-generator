"""
LUT 应用模块 - LUTApplier

将生成的 3D LUT 应用到图片
支持批量处理、进度回调
使用 OpenCV 和 colour-science 进行高效变换
"""

import numpy as np
import cv2
from pathlib import Path
from typing import Union, Optional, Callable, Tuple, List
from dataclasses import dataclass
from datetime import datetime
import json

from lut3d_generator import LUT3DGenerator, LUT3DConfig, LUT3DMetadata
from color_analyzer import ColorAnalyzer


@dataclass
class ApplyConfig:
    """LUT 应用配置"""
    # 输出质量 (0-100)
    quality: int = 95
    
    # 输出格式
    output_format: str = 'png'  # 'png', 'jpg', 'tiff'
    
    # 是否保持原图尺寸
    keep_original_size: bool = True
    
    # 输出宽度（如果调整大小）
    output_width: Optional[int] = None
    
    # 输出高度（如果调整大小）
    output_height: Optional[int] = None
    
    # 色彩空间转换
    # 'sRGB': 标准 sRGB
    # 'linear': 线性光
    input_colorspace: str = 'sRGB'
    
    def validate(self) -> bool:
        """验证配置"""
        if not 0 <= self.quality <= 100:
            raise ValueError("quality must be between 0 and 100")
        
        valid_formats = ['png', 'jpg', 'jpeg', 'tiff', 'tif']
        if self.output_format.lower() not in valid_formats:
            raise ValueError(f"output_format must be one of {valid_formats}")
        
        return True


@dataclass
class ApplyResult:
    """LUT 应用结果"""
    # 输入路径
    input_path: str
    
    # 输出路径
    output_path: str
    
    # 处理时间（秒）
    processing_time: float
    
    # 输入图像尺寸
    input_size: Tuple[int, int]
    
    # 输出图像尺寸
    output_size: Tuple[int, int]
    
    # 是否成功
    success: bool
    
    # 错误信息（如果失败）
    error_message: Optional[str] = None
    
    # 元数据
    metadata: Optional[dict] = None


class LUTApplier:
    """
    LUT 应用器
    
    将 3D LUT 应用到单张或批量图片
    支持三线性插值和最近邻插值
    """
    
    def __init__(self, lut_generator: LUT3DGenerator):
        """
        初始化 LUT 应用器
        
        Args:
            lut_generator: 已生成 LUT 的生成器实例
        """
        if lut_generator.lut_data is None:
            raise ValueError("LUT data not generated. Call generate_* on LUT3DGenerator first.")
        
        self.lut_generator = lut_generator
        self.config = lut_generator.config
        self.analyzer = ColorAnalyzer()
    
    @classmethod
    def from_lut_file(cls, lut_path: Union[str, Path], 
                      grid_size: int = 33,
                      interpolation: str = 'trilinear') -> 'LUTApplier':
        """
        从 .cube 文件加载 LUT 并创建应用器
        
        Args:
            lut_path: .cube 文件路径
            grid_size: LUT 网格大小
            interpolation: 插值方法
            
        Returns:
            LUTApplier 实例
        """
        lut_data = cls._load_cube_file(lut_path, grid_size)
        
        config = LUT3DConfig(grid_size=grid_size, interpolation=interpolation)
        generator = LUT3DGenerator(config)
        generator.lut_data = lut_data
        
        return cls(generator)
    
    @staticmethod
    def _load_cube_file(cube_path: Union[str, Path], 
                         grid_size: int = 33) -> np.ndarray:
        """
        加载 .cube 格式的 LUT 文件
        
        Args:
            cube_path: .cube 文件路径
            grid_size: LUT 网格大小
            
        Returns:
            LUT 数组，shape=(grid_size, grid_size, grid_size, 3)
        """
        cube_path = Path(cube_path)
        
        if not cube_path.exists():
            raise FileNotFoundError(f"CUBE file not found: {cube_path}")
        
        # 读取文件
        with open(cube_path, 'r') as f:
            lines = f.readlines()
        
        # 解析 LUT 数据
        lut_values = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('TITLE'):
                continue
            if line.startswith('LUT_3D_SIZE'):
                continue
            
            # 解析 RGB 值
            parts = line.split()
            if len(parts) >= 3:
                try:
                    r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
                    lut_values.append([r, g, b])
                except ValueError:
                    continue
        
        # 重塑为 3D 数组
        lut_array = np.array(lut_values, dtype=np.float32)
        expected_size = grid_size ** 3
        
        if len(lut_array) != expected_size:
            raise ValueError(
                f"CUBE file has {len(lut_array)} entries, expected {expected_size} for grid_size={grid_size}"
            )
        
        # 重塑为 (grid_size, grid_size, grid_size, 3)
        # 注意：CUBE 文件格式通常是 B 优先，需要调整轴顺序
        lut_data = lut_array.reshape(grid_size, grid_size, grid_size, 3)
        
        return lut_data
    
    def apply_to_image(self, image: np.ndarray, 
                       progress_callback: Optional[Callable[[float], None]] = None) -> np.ndarray:
        """
        将 LUT 应用到单张图像
        
        Args:
            image: 输入图像，RGB 格式，shape=(H, W, 3)，值范围 0-255 或 0-1
            progress_callback: 进度回调函数，接收 0.0-1.0 的进度值
            
        Returns:
            处理后的图像，RGB 格式，shape 与输入相同
        """
        if progress_callback:
            progress_callback(0.0)
        
        # 确保图像是 RGB 格式
        if len(image.shape) != 3 or image.shape[2] not in [3, 4]:
            raise ValueError(f"Image must have 3 or 4 channels, got {image.shape}")
        
        # 分离 Alpha 通道（如果有）
        has_alpha = image.shape[2] == 4
        if has_alpha:
            alpha_channel = image[:, :, 3:4]
            image = image[:, :, :3]
        
        # 归一化到 0-1
        if image.dtype != np.float32 and image.dtype != np.float64:
            image_normalized = image.astype(np.float32) / 255.0
        else:
            image_normalized = image
        
        # 重塑为 (N, 3) 格式
        h, w = image_normalized.shape[:2]
        pixels = image_normalized.reshape(-1, 3)
        
        if progress_callback:
            progress_callback(0.1)
        
        # 批量处理像素（分块处理以节省内存）
        batch_size = 100000
        output_pixels = np.zeros_like(pixels)
        
        num_batches = (len(pixels) + batch_size - 1) // batch_size
        
        for i in range(num_batches):
            start_idx = i * batch_size
            end_idx = min((i + 1) * batch_size, len(pixels))
            
            batch = pixels[start_idx:end_idx]
            transformed = self.lut_generator.apply(batch)
            output_pixels[start_idx:end_idx] = transformed
            
            if progress_callback:
                progress_callback(0.1 + 0.8 * (i + 1) / num_batches)
        
        # 重塑回图像格式
        output_image = output_pixels.reshape(h, w, 3)
        
        # 反归一化到 0-255
        output_image = np.clip(output_image * 255.0, 0, 255).astype(np.uint8)
        
        # 恢复 Alpha 通道（如果有）
        if has_alpha:
            output_image = np.concatenate([output_image, alpha_channel], axis=2)
        
        if progress_callback:
            progress_callback(1.0)
        
        return output_image
    
    def apply_to_file(self, input_path: Union[str, Path],
                      output_path: Union[str, Path],
                      config: ApplyConfig = None,
                      progress_callback: Optional[Callable[[float], None]] = None) -> ApplyResult:
        """
        将 LUT 应用到图像文件
        
        Args:
            input_path: 输入图像路径
            output_path: 输出图像路径
            config: 应用配置
            progress_callback: 进度回调
            
        Returns:
            ApplyResult 结果对象
        """
        if config is None:
            config = ApplyConfig()
        
        config.validate()
        
        start_time = datetime.now()
        
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)
            
            # 加载图像
            image = self.analyzer.load_image(input_path)
            input_size = (image.shape[1], image.shape[0])  # (width, height)
            
            if progress_callback:
                progress_callback(0.0)
            
            # 应用 LUT
            output_image = self.apply_to_image(image, progress_callback)
            
            if progress_callback:
                progress_callback(0.9)
            
            # 调整大小（如果需要）
            if not config.keep_original_size and config.output_width:
                h, w = output_image.shape[:2]
                aspect_ratio = h / w
                output_width = config.output_width
                output_height = int(output_width * aspect_ratio)
                
                if config.output_height:
                    output_height = config.output_height
                
                output_image = cv2.resize(output_image, (output_width, output_height), 
                                         interpolation=cv2.INTER_LANCZOS4)
            
            output_size = (output_image.shape[1], output_image.shape[0])
            
            # 保存图像
            self._save_image(output_image, output_path, config)
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            return ApplyResult(
                input_path=str(input_path),
                output_path=str(output_path),
                processing_time=processing_time,
                input_size=input_size,
                output_size=output_size,
                success=True,
                metadata=self._get_metadata()
            )
            
        except Exception as e:
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            return ApplyResult(
                input_path=str(input_path),
                output_path=str(output_path),
                processing_time=processing_time,
                input_size=(0, 0),
                output_size=(0, 0),
                success=False,
                error_message=str(e)
            )
    
    def apply_batch(self, input_paths: List[Union[str, Path]],
                    output_dir: Union[str, Path],
                    config: ApplyConfig = None,
                    progress_callback: Optional[Callable[[int, int, ApplyResult], None]] = None) -> List[ApplyResult]:
        """
        批量应用 LUT 到多个图像文件
        
        Args:
            input_paths: 输入图像路径列表
            output_dir: 输出目录
            config: 应用配置
            progress_callback: 进度回调，参数为 (current_index, total, result)
            
        Returns:
            ApplyResult 列表
        """
        if config is None:
            config = ApplyConfig()
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        total = len(input_paths)
        
        for i, input_path in enumerate(input_paths):
            input_path = Path(input_path)
            
            # 生成输出路径
            output_filename = f"{input_path.stem}_lut.{config.output_format}"
            output_path = output_dir / output_filename
            
            # 应用 LUT
            result = self.apply_to_file(input_path, output_path, config)
            results.append(result)
            
            if progress_callback:
                progress_callback(i, total, result)
        
        return results
    
    def _save_image(self, image: np.ndarray, 
                    output_path: Path, 
                    config: ApplyConfig) -> None:
        """
        保存图像到文件
        
        Args:
            image: 图像数组
            output_path: 输出路径
            config: 配置
        """
        output_format = config.output_format.lower()
        
        if output_format in ['jpg', 'jpeg']:
            # JPEG 需要 BGR 格式
            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(output_path), image_bgr, 
                       [cv2.IMWRITE_JPEG_QUALITY, config.quality])
        elif output_format == 'png':
            cv2.imwrite(str(output_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
                       [cv2.IMWRITE_PNG_COMPRESSION, 9 - int(config.quality / 11)])
        elif output_format in ['tiff', 'tif']:
            cv2.imwrite(str(output_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        else:
            cv2.imwrite(str(output_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    
    def _get_metadata(self) -> dict:
        """获取元数据"""
        metadata = {
            'lut_grid_size': self.config.grid_size,
            'interpolation': self.config.interpolation,
            'input_colorspace': self.config.input_colorspace,
            'output_colorspace': self.config.output_colorspace,
            'generated_at': datetime.now().isoformat()
        }
        
        if self.lut_generator.metadata:
            metadata['description'] = self.lut_generator.metadata.description
        
        return metadata


def apply_lut_to_image(lut_generator: LUT3DGenerator,
                       image_path: Union[str, Path],
                       output_path: Union[str, Path],
                       quality: int = 95,
                       output_format: str = 'png') -> ApplyResult:
    """
    便捷函数：将 LUT 应用到图像文件
    
    Args:
        lut_generator: 已生成 LUT 的生成器
        image_path: 输入图像路径
        output_path: 输出图像路径
        quality: 输出质量 (0-100)
        output_format: 输出格式
        
    Returns:
        ApplyResult 结果对象
    """
    config = ApplyConfig(quality=quality, output_format=output_format)
    applier = LUTApplier(lut_generator)
    return applier.apply_to_file(image_path, output_path, config)


if __name__ == "__main__":
    # 简单测试
    import sys
    
    print("LUT Applier Test")
    print("=" * 50)
    
    # 创建模拟 LUT
    from lut3d_generator import LUT3DConfig, LUT3DGenerator
    from color_analyzer import ColorStatistics
    
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
    
    config = LUT3DConfig(grid_size=17)  # 使用小网格加速测试
    generator = LUT3DGenerator(config)
    generator.generate_from_stats(source_stats, target_stats)
    
    print(f"LUT generated: shape={generator.lut_data.shape}")
    
    # 测试应用（需要实际图像文件）
    print("\nTo test with real images, run:")
    print("  python lut_applier.py <input_image> <output_image> <reference_image> <target_image>")
    
    if len(sys.argv) >= 5:
        input_image = sys.argv[1]
        output_image = sys.argv[2]
        ref_image = sys.argv[3]
        target_image = sys.argv[4]
        
        # 生成 LUT
        generator.generate_from_images(ref_image, target_image)
        
        # 应用 LUT
        applier = LUTApplier(generator)
        result = applier.apply_to_file(input_image, output_image)
        
        print(f"\nResult: {result.success}")
        print(f"Processing time: {result.processing_time:.2f}s")
        print(f"Output: {result.output_path}")

"""
LUT 应用模块 - LUTApplier

将生成的 3D LUT 应用到图片
支持批量处理、进度回调
"""

import numpy as np
import cv2
from pathlib import Path
from typing import Union, Optional, Callable, Tuple, List
from dataclasses import dataclass
from datetime import datetime
import json

from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig, LUT3DMetadata
from lut_generator.analysis.analyzer import ColorAnalyzer


@dataclass
class ApplyConfig:
    """LUT 应用配置"""
    quality: int = 95
    output_format: str = 'png'  # 'png', 'jpg', 'tiff'
    keep_original_size: bool = True
    output_width: Optional[int] = None
    output_height: Optional[int] = None
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
    input_path: str
    output_path: str
    processing_time: float
    input_size: Tuple[int, int]
    output_size: Tuple[int, int]
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[dict] = None


class LUTApplier:
    """
    LUT 应用器
    
    将 3D LUT 应用到单张或批量图片
    """
    
    def __init__(self, lut_generator: LUT3DGenerator):
        """
        初始化 LUT 应用器

        Args:
            lut_generator: 已生成 LUT 的生成器实例。
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
        """从 .cube 文件加载 LUT 并创建应用器"""
        lut_data = cls._load_cube_file(lut_path, grid_size)
        
        config = LUT3DConfig(grid_size=grid_size, interpolation=interpolation)
        generator = LUT3DGenerator(config)
        generator.lut_data = lut_data
        
        return cls(generator)
    
    @staticmethod
    def _load_cube_file(cube_path: Union[str, Path], 
                         grid_size: int = 33) -> np.ndarray:
        """加载 .cube 格式的 LUT 文件"""
        cube_path = Path(cube_path)
        
        if not cube_path.exists():
            raise FileNotFoundError(f"CUBE file not found: {cube_path}")
        
        with open(cube_path, 'r') as f:
            lines = f.readlines()
        
        lut_values = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('TITLE'):
                continue
            if line.startswith('LUT_3D_SIZE'):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                try:
                    r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
                    lut_values.append([r, g, b])
                except ValueError:
                    continue
        
        lut_array = np.array(lut_values, dtype=np.float32)
        expected_size = grid_size ** 3
        
        if len(lut_array) != expected_size:
            raise ValueError(
                f"CUBE file has {len(lut_array)} entries, expected {expected_size} for grid_size={grid_size}"
            )
        
        lut_data = lut_array.reshape(grid_size, grid_size, grid_size, 3)
        
        return lut_data
    
    def apply_to_image(self, image: np.ndarray, 
                       progress_callback: Optional[Callable[[float], None]] = None) -> np.ndarray:
        """
        将 LUT 应用到单张图像
        
        Args:
            image: 输入图像，RGB 格式
            progress_callback: 进度回调函数
            
        Returns:
            处理后的图像
        """
        if progress_callback:
            progress_callback(0.0)
        
        if len(image.shape) != 3 or image.shape[2] not in [3, 4]:
            raise ValueError(f"Image must have 3 or 4 channels, got {image.shape}")
        
        has_alpha = image.shape[2] == 4
        if has_alpha:
            alpha_channel = image[:, :, 3:4]
            image = image[:, :, :3]
        
        if image.dtype != np.float32 and image.dtype != np.float64:
            image_normalized = image.astype(np.float32) / 255.0
        else:
            image_normalized = image
        
        h, w = image_normalized.shape[:2]
        pixels = image_normalized.reshape(-1, 3)
        
        if progress_callback:
            progress_callback(0.1)
        
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
        
        output_image = output_pixels.reshape(h, w, 3)
        output_image = np.clip(output_image * 255.0, 0, 255).astype(np.uint8)
        
        if has_alpha:
            output_image = np.concatenate([output_image, alpha_channel], axis=2)
        
        if progress_callback:
            progress_callback(1.0)
        
        return output_image
    
    def apply_to_file(self, input_path: Union[str, Path],
                      output_path: Union[str, Path],
                      config: ApplyConfig = None,
                      progress_callback: Optional[Callable[[float], None]] = None) -> ApplyResult:
        """将 LUT 应用到图像文件"""
        if config is None:
            config = ApplyConfig()
        
        config.validate()
        
        start_time = datetime.now()
        
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)
            
            image = self.analyzer.load_image(input_path)
            input_size = (image.shape[1], image.shape[0])
            
            if progress_callback:
                progress_callback(0.0)
            
            output_image = self.apply_to_image(image, progress_callback)
            
            if progress_callback:
                progress_callback(0.9)
            
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
            
        except (OSError, IOError, ValueError, RuntimeError) as e:
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
        """批量应用 LUT 到多个图像文件"""
        if config is None:
            config = ApplyConfig()
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        total = len(input_paths)
        
        for i, input_path in enumerate(input_paths):
            input_path = Path(input_path)
            
            output_filename = f"{input_path.stem}_lut.{config.output_format}"
            output_path = output_dir / output_filename
            
            result = self.apply_to_file(input_path, output_path, config)
            results.append(result)
            
            if progress_callback:
                progress_callback(i, total, result)
        
        return results
    
    def _save_image(self, image: np.ndarray, 
                    output_path: Path, 
                    config: ApplyConfig) -> None:
        """保存图像到文件"""
        output_format = config.output_format.lower()
        
        if output_format in ['jpg', 'jpeg']:
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
    """便捷函数：将 LUT 应用到图像文件"""
    config = ApplyConfig(quality=quality, output_format=output_format)
    applier = LUTApplier(lut_generator)
    return applier.apply_to_file(image_path, output_path, config)

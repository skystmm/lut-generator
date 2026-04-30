"""
预览图生成模块 - PreviewGenerator

生成前后对比图
支持并排对比、滑块对比等多种展示方式
"""

import numpy as np
import cv2
from pathlib import Path
from typing import Union, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime
import json

from lut_generator.analysis.analyzer import ColorAnalyzer


@dataclass
class ComparisonConfig:
    """对比图配置"""
    mode: str = 'side_by_side'  # 'side_by_side', 'slider', 'blend', 'difference'
    output_width: int = 1920
    output_height: Optional[int] = None
    border_width: int = 2
    border_color: Tuple[int, int, int] = (255, 255, 255)
    add_labels: bool = True
    label_font: int = cv2.FONT_HERSHEY_SIMPLEX
    label_scale: float = 1.0
    label_color: Tuple[int, int, int] = (255, 255, 255)
    label_background: bool = True
    slider_position: float = 0.5
    slider_color: Tuple[int, int, int] = (255, 255, 255)
    slider_width: int = 3
    
    def validate(self) -> bool:
        """验证配置"""
        valid_modes = ['side_by_side', 'slider', 'blend', 'difference']
        if self.mode not in valid_modes:
            raise ValueError(f"mode must be one of {valid_modes}")
        
        if not 0.0 <= self.slider_position <= 1.0:
            raise ValueError("slider_position must be between 0.0 and 1.0")
        
        return True


@dataclass
class PreviewResult:
    """预览图生成结果"""
    output_path: str
    mode: str
    output_size: Tuple[int, int]
    generation_time: float
    success: bool
    error_message: Optional[str] = None
    statistics: Optional[dict] = None


class PreviewGenerator:
    """
    预览图生成器
    
    生成原图和处理后图像的对比图
    支持多种对比模式
    """
    
    def __init__(self, lut_applier):
        """
        初始化预览生成器
        
        Args:
            lut_applier: LUT 应用器实例
        """
        self.lut_applier = lut_applier
        self.analyzer = ColorAnalyzer()
    
    def generate_comparison(self, 
                           original_path: Union[str, Path],
                           processed_path: Union[str, Path],
                           output_path: Union[str, Path],
                           config: ComparisonConfig = None) -> PreviewResult:
        """生成对比图"""
        if config is None:
            config = ComparisonConfig()
        
        config.validate()
        
        start_time = datetime.now()
        
        try:
            original_path = Path(original_path)
            processed_path = Path(processed_path)
            output_path = Path(output_path)
            
            original = self.analyzer.load_image(original_path)
            processed = self.analyzer.load_image(processed_path)
            
            processed = cv2.resize(processed, (original.shape[1], original.shape[0]), 
                                  interpolation=cv2.INTER_LANCZOS4)
            
            if config.mode == 'side_by_side':
                comparison_image = self._generate_side_by_side(original, processed, config)
            elif config.mode == 'slider':
                comparison_image = self._generate_slider_preview(original, processed, config)
            elif config.mode == 'blend':
                comparison_image = self._generate_blend(original, processed, config)
            elif config.mode == 'difference':
                comparison_image = self._generate_difference(original, processed, config)
            else:
                raise ValueError(f"Unknown mode: {config.mode}")
            
            cv2.imwrite(str(output_path), cv2.cvtColor(comparison_image, cv2.COLOR_RGB2BGR))
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            statistics = self._calculate_statistics(original, processed)
            
            return PreviewResult(
                output_path=str(output_path),
                mode=config.mode,
                output_size=(comparison_image.shape[1], comparison_image.shape[0]),
                generation_time=generation_time,
                success=True,
                statistics=statistics
            )
            
        except Exception as e:
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            return PreviewResult(
                output_path=str(output_path),
                mode=config.mode if config else 'unknown',
                output_size=(0, 0),
                generation_time=generation_time,
                success=False,
                error_message=str(e)
            )
    
    def generate_from_image(self,
                           input_path: Union[str, Path],
                           output_dir: Union[str, Path],
                           config: ComparisonConfig = None) -> PreviewResult:
        """从单张图像生成对比图（自动应用 LUT）"""
        if config is None:
            config = ComparisonConfig()
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        input_path = Path(input_path)
        
        processed_path = output_dir / f"{input_path.stem}_processed.png"
        result = self.lut_applier.apply_to_file(input_path, processed_path)
        
        if not result.success:
            return PreviewResult(
                output_path='',
                mode=config.mode,
                output_size=(0, 0),
                generation_time=0,
                success=False,
                error_message=f"Failed to apply LUT: {result.error_message}"
            )
        
        comparison_path = output_dir / f"{input_path.stem}_comparison.png"
        return self.generate_comparison(input_path, processed_path, comparison_path, config)
    
    def _generate_side_by_side(self, 
                               original: np.ndarray, 
                               processed: np.ndarray,
                               config: ComparisonConfig) -> np.ndarray:
        """生成并排对比图"""
        h, w = original.shape[:2]
        
        total_width = w * 2 + config.border_width * 3
        
        if len(original.shape) == 3:
            canvas = np.ones((h, total_width, 3), dtype=np.uint8) * 255
        else:
            canvas = np.ones((h, total_width), dtype=np.uint8) * 255
        
        canvas[0:h, config.border_width:config.border_width+w] = original
        
        border_x = config.border_width * 2 + w
        canvas[:, border_x:border_x+config.border_width] = config.border_color
        
        canvas[0:h, border_x+config.border_width:border_x+config.border_width+w] = processed
        
        if config.add_labels:
            self._add_label(canvas, "Original", config.border_width, h - 10, config)
            self._add_label(canvas, "Processed", border_x + config.border_width + 10, h - 10, config)
        
        return canvas
    
    def _generate_slider_preview(self,
                                 original: np.ndarray,
                                 processed: np.ndarray,
                                 config: ComparisonConfig) -> np.ndarray:
        """生成滑块对比预览图"""
        h, w = original.shape[:2]
        
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        
        slider_x = int(w * config.slider_position)
        
        canvas[:, :slider_x] = original[:, :slider_x]
        canvas[:, slider_x:] = processed[:, slider_x:]
        
        cv2.line(canvas, (slider_x, 0), (slider_x, h), config.slider_color, config.slider_width)
        
        handle_y = h // 2
        handle_size = 20
        cv2.circle(canvas, (slider_x, handle_y), handle_size, config.slider_color, -1)
        cv2.circle(canvas, (slider_x, handle_y), handle_size - 3, (0, 0, 0), -1)
        
        arrow_points = np.array([
            [slider_x - 8, handle_y - 5],
            [slider_x + 8, handle_y - 5],
            [slider_x, handle_y + 5]
        ], dtype=np.int32)
        cv2.fillPoly(canvas, [arrow_points], (255, 255, 255))
        
        if config.add_labels:
            self._add_label(canvas, "Original", 10, 30, config)
            self._add_label(canvas, "Processed", w - 100, 30, config)
        
        return canvas
    
    def _generate_blend(self,
                       original: np.ndarray,
                       processed: np.ndarray,
                       config: ComparisonConfig) -> np.ndarray:
        """生成混合对比图"""
        alpha = 0.5
        blended = cv2.addWeighted(original, alpha, processed, 1 - alpha, 0)
        
        h, w = original.shape[:2]
        canvas = np.zeros((h, w * 2, 3), dtype=np.uint8)
        
        canvas[:, :w] = original
        canvas[:, w:] = blended
        
        if config.add_labels:
            self._add_label(canvas, "Original", 10, 30, config)
            self._add_label(canvas, f"50% Blend", w + 10, 30, config)
        
        return canvas
    
    def _generate_difference(self,
                            original: np.ndarray,
                            processed: np.ndarray,
                            config: ComparisonConfig) -> np.ndarray:
        """生成差异可视化图"""
        diff = cv2.absdiff(original, processed)
        diff_enhanced = cv2.convertScaleAbs(diff, alpha=2.0, beta=0)
        
        h, w = original.shape[:2]
        canvas = np.zeros((h, w * 3, 3), dtype=np.uint8)
        
        canvas[:, :w] = original
        canvas[:, w:w*2] = processed
        canvas[:, w*2:] = diff_enhanced
        
        if config.add_labels:
            self._add_label(canvas, "Original", 10, 30, config)
            self._add_label(canvas, "Processed", w + 10, 30, config)
            self._add_label(canvas, "Difference", w * 2 + 10, 30, config)
        
        return canvas
    
    def _add_label(self, 
                   image: np.ndarray, 
                   text: str, 
                   x: int, 
                   y: int, 
                   config: ComparisonConfig) -> None:
        """添加标签到图像"""
        if config.label_background:
            (text_width, text_height), baseline = cv2.getTextSize(
                text, config.label_font, config.label_scale, 2
            )
            
            cv2.rectangle(
                image,
                (x - 5, y - text_height - 5),
                (x + text_width + 5, y + baseline + 5),
                (0, 0, 0),
                -1
            )
        
        cv2.putText(
            image,
            text,
            (x, y),
            config.label_font,
            config.label_scale,
            config.label_color,
            2,
            cv2.LINE_AA
        )
    
    def _calculate_statistics(self,
                             original: np.ndarray,
                             processed: np.ndarray) -> dict:
        """计算图像统计信息"""
        orig_float = original.astype(np.float32)
        proc_float = processed.astype(np.float32)
        
        diff = np.abs(orig_float - proc_float)
        
        stats = {
            'original': {
                'mean_rgb': np.mean(orig_float, axis=(0, 1)).tolist(),
                'std_rgb': np.std(orig_float, axis=(0, 1)).tolist(),
                'brightness': np.mean(np.mean(orig_float, axis=2))
            },
            'processed': {
                'mean_rgb': np.mean(proc_float, axis=(0, 1)).tolist(),
                'std_rgb': np.std(proc_float, axis=(0, 1)).tolist(),
                'brightness': np.mean(np.mean(proc_float, axis=2))
            },
            'difference': {
                'mean_diff': np.mean(diff),
                'max_diff': np.max(diff),
                'std_diff': np.std(diff)
            }
        }
        
        orig_brightness = np.mean(np.mean(orig_float, axis=2))
        proc_brightness = np.mean(np.mean(proc_float, axis=2))
        stats['brightness_change'] = ((proc_brightness - orig_brightness) / orig_brightness * 100) if orig_brightness > 0 else 0
        
        return stats

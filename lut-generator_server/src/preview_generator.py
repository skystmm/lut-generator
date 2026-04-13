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

from lut_applier import LUTApplier, ApplyConfig
from color_analyzer import ColorAnalyzer


@dataclass
class ComparisonConfig:
    """对比图配置"""
    # 对比模式
    # 'side_by_side': 并排对比
    # 'slider': 滑块对比（生成可交互 HTML 所需的基础图）
    # 'blend': 混合对比
    # 'difference': 差异可视化
    mode: str = 'side_by_side'
    
    # 输出宽度（像素）
    output_width: int = 1920
    
    # 输出高度（像素，None 表示自动计算）
    output_height: Optional[int] = None
    
    # 边框宽度（像素）
    border_width: int = 2
    
    # 边框颜色（RGB）
    border_color: Tuple[int, int, int] = (255, 255, 255)
    
    # 是否添加标签
    add_labels: bool = True
    
    # 标签字体
    label_font: int = cv2.FONT_HERSHEY_SIMPLEX
    
    # 标签字体大小
    label_scale: float = 1.0
    
    # 标签颜色（RGB）
    label_color: Tuple[int, int, int] = (255, 255, 255)
    
    # 标签背景（半透明黑色）
    label_background: bool = True
    
    # 滑块位置（0.0-1.0，仅 slider 模式）
    slider_position: float = 0.5
    
    # 滑块颜色和宽度
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
    # 输出路径
    output_path: str
    
    # 对比模式
    mode: str
    
    # 输出尺寸
    output_size: Tuple[int, int]
    
    # 生成时间（秒）
    generation_time: float
    
    # 是否成功
    success: bool
    
    # 错误信息
    error_message: Optional[str] = None
    
    # 统计信息
    statistics: Optional[dict] = None


class PreviewGenerator:
    """
    预览图生成器
    
    生成原图和处理后图像的对比图
    支持多种对比模式
    """
    
    def __init__(self, lut_applier: LUTApplier):
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
        """
        生成对比图
        
        Args:
            original_path: 原图路径
            processed_path: 处理后图像路径
            output_path: 输出路径
            config: 对比配置
            
        Returns:
            PreviewResult 结果对象
        """
        if config is None:
            config = ComparisonConfig()
        
        config.validate()
        
        start_time = datetime.now()
        
        try:
            original_path = Path(original_path)
            processed_path = Path(processed_path)
            output_path = Path(output_path)
            
            # 加载图像
            original = self.analyzer.load_image(original_path)
            processed = self.analyzer.load_image(processed_path)
            
            # 统一尺寸
            processed = cv2.resize(processed, (original.shape[1], original.shape[0]), 
                                  interpolation=cv2.INTER_LANCZOS4)
            
            # 根据模式生成对比图
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
            
            # 保存图像
            cv2.imwrite(str(output_path), cv2.cvtColor(comparison_image, cv2.COLOR_RGB2BGR))
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            # 计算统计信息
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
        """
        从单张图像生成对比图（自动应用 LUT）
        
        Args:
            input_path: 输入图像路径
            output_dir: 输出目录
            config: 对比配置
            
        Returns:
            PreviewResult 结果对象
        """
        if config is None:
            config = ComparisonConfig()
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        input_path = Path(input_path)
        
        # 生成处理后图像
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
        
        # 生成对比图
        comparison_path = output_dir / f"{input_path.stem}_comparison.png"
        return self.generate_comparison(input_path, processed_path, comparison_path, config)
    
    def _generate_side_by_side(self, 
                               original: np.ndarray, 
                               processed: np.ndarray,
                               config: ComparisonConfig) -> np.ndarray:
        """
        生成并排对比图
        
        Args:
            original: 原图
            processed: 处理后图像
            config: 配置
            
        Returns:
            对比图
        """
        h, w = original.shape[:2]
        
        # 计算总宽度（两图 + 边框）
        total_width = w * 2 + config.border_width * 3
        
        # 创建画布
        if len(original.shape) == 3:
            canvas = np.ones((h, total_width, 3), dtype=np.uint8) * 255
        else:
            canvas = np.ones((h, total_width), dtype=np.uint8) * 255
        
        # 放置原图 (y: 0-h, x: border_width:border_width+w)
        canvas[0:h, config.border_width:config.border_width+w] = original
        
        # 放置边框
        border_x = config.border_width * 2 + w
        canvas[:, border_x:border_x+config.border_width] = config.border_color
        
        # 放置处理后图像
        canvas[0:h, border_x+config.border_width:border_x+config.border_width+w] = processed
        
        # 添加标签
        if config.add_labels:
            self._add_label(canvas, "Original", config.border_width, h - 10, config)
            self._add_label(canvas, "Processed", border_x + config.border_width + 10, h - 10, config)
        
        return canvas
    
    def _generate_slider_preview(self,
                                 original: np.ndarray,
                                 processed: np.ndarray,
                                 config: ComparisonConfig) -> np.ndarray:
        """
        生成滑块对比预览图
        
        生成一张静态预览图，滑块位置在中间
        实际交互需要 HTML 实现
        
        Args:
            original: 原图
            processed: 处理后图像
            config: 配置
            
        Returns:
            对比图
        """
        h, w = original.shape[:2]
        
        # 创建画布
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        
        # 计算滑块位置
        slider_x = int(w * config.slider_position)
        
        # 左侧显示原图
        canvas[:, :slider_x] = original[:, :slider_x]
        
        # 右侧显示处理后图像
        canvas[:, slider_x:] = processed[:, slider_x:]
        
        # 绘制滑块线
        cv2.line(canvas, (slider_x, 0), (slider_x, h), config.slider_color, config.slider_width)
        
        # 绘制滑块手柄
        handle_y = h // 2
        handle_size = 20
        cv2.circle(canvas, (slider_x, handle_y), handle_size, config.slider_color, -1)
        cv2.circle(canvas, (slider_x, handle_y), handle_size - 3, (0, 0, 0), -1)
        
        # 添加箭头指示
        arrow_points = np.array([
            [slider_x - 8, handle_y - 5],
            [slider_x + 8, handle_y - 5],
            [slider_x, handle_y + 5]
        ], dtype=np.int32)
        cv2.fillPoly(canvas, [arrow_points], (255, 255, 255))
        
        # 添加标签
        if config.add_labels:
            self._add_label(canvas, "Original", 10, 30, config)
            self._add_label(canvas, "Processed", w - 100, 30, config)
        
        return canvas
    
    def _generate_blend(self,
                       original: np.ndarray,
                       processed: np.ndarray,
                       config: ComparisonConfig) -> np.ndarray:
        """
        生成混合对比图
        
        使用 alpha 混合展示原图和处理后图像
        
        Args:
            original: 原图
            processed: 处理后图像
            config: 配置
            
        Returns:
            对比图
        """
        # 50% 混合
        alpha = 0.5
        blended = cv2.addWeighted(original, alpha, processed, 1 - alpha, 0)
        
        # 创建画布（原图 + 混合图）
        h, w = original.shape[:2]
        canvas = np.zeros((h, w * 2, 3), dtype=np.uint8)
        
        canvas[:, :w] = original
        canvas[:, w:] = blended
        
        # 添加标签
        if config.add_labels:
            self._add_label(canvas, "Original", 10, 30, config)
            self._add_label(canvas, f"50% Blend", w + 10, 30, config)
        
        return canvas
    
    def _generate_difference(self,
                            original: np.ndarray,
                            processed: np.ndarray,
                            config: ComparisonConfig) -> np.ndarray:
        """
        生成差异可视化图
        
        显示原图和处理后图像的差异
        
        Args:
            original: 原图
            processed: 处理后图像
            config: 配置
            
        Returns:
            对比图
        """
        # 计算绝对差异
        diff = cv2.absdiff(original, processed)
        
        # 增强差异可视化
        diff_enhanced = cv2.convertScaleAbs(diff, alpha=2.0, beta=0)
        
        # 创建画布（原图 + 处理后 + 差异）
        h, w = original.shape[:2]
        canvas = np.zeros((h, w * 3, 3), dtype=np.uint8)
        
        canvas[:, :w] = original
        canvas[:, w:w*2] = processed
        canvas[:, w*2:] = diff_enhanced
        
        # 添加标签
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
        """
        添加标签到图像
        
        Args:
            image: 目标图像
            text: 标签文本
            x: x 坐标
            y: y 坐标
            config: 配置
        """
        if config.label_background:
            # 计算文本大小
            (text_width, text_height), baseline = cv2.getTextSize(
                text, config.label_font, config.label_scale, 2
            )
            
            # 绘制背景矩形
            cv2.rectangle(
                image,
                (x - 5, y - text_height - 5),
                (x + text_width + 5, y + baseline + 5),
                (0, 0, 0),
                -1
            )
        
        # 绘制文本
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
        """
        计算图像统计信息
        
        Args:
            original: 原图
            processed: 处理后图像
            
        Returns:
            统计信息字典
        """
        # 转换为 float 计算
        orig_float = original.astype(np.float32)
        proc_float = processed.astype(np.float32)
        
        # 计算差异
        diff = np.abs(orig_float - proc_float)
        
        # 计算每个通道的统计
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
        
        # 计算亮度变化
        orig_brightness = np.mean(np.mean(orig_float, axis=2))
        proc_brightness = np.mean(np.mean(proc_float, axis=2))
        stats['brightness_change'] = ((proc_brightness - orig_brightness) / orig_brightness * 100) if orig_brightness > 0 else 0
        
        return stats


def generate_preview(lut_applier: LUTApplier,
                    input_path: Union[str, Path],
                    output_dir: Union[str, Path],
                    mode: str = 'side_by_side',
                    output_width: int = 1920) -> PreviewResult:
    """
    便捷函数：生成预览对比图
    
    Args:
        lut_applier: LUT 应用器
        input_path: 输入图像路径
        output_dir: 输出目录
        mode: 对比模式
        output_width: 输出宽度
        
    Returns:
        PreviewResult 结果对象
    """
    config = ComparisonConfig(mode=mode, output_width=output_width)
    generator = PreviewGenerator(lut_applier)
    return generator.generate_from_image(input_path, output_dir, config)


if __name__ == "__main__":
    # 简单测试
    import sys
    
    print("Preview Generator Test")
    print("=" * 50)
    
    print("\nUsage:")
    print("  python preview_generator.py <input_image> <reference_image> <target_image> <output_dir>")
    
    if len(sys.argv) >= 5:
        input_image = sys.argv[1]
        ref_image = sys.argv[2]
        target_image = sys.argv[3]
        output_dir = sys.argv[4]
        
        # 生成 LUT 并应用
        from lut3d_generator import LUT3DGenerator, LUT3DConfig
        
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        generator.generate_from_images(ref_image, target_image)
        
        applier = LUTApplier(generator)
        
        # 生成预览
        preview_gen = PreviewGenerator(applier)
        result = preview_gen.generate_from_image(input_image, output_dir)
        
        print(f"\nResult: {result.success}")
        if result.success:
            print(f"Output: {result.output_path}")
            print(f"Size: {result.output_size}")
            print(f"Generation time: {result.generation_time:.2f}s")
            
            if result.statistics:
                print(f"\nStatistics:")
                print(f"  Brightness change: {result.statistics['brightness_change']:.2f}%")
                print(f"  Mean difference: {result.statistics['difference']['mean_diff']:.2f}")
        else:
            print(f"Error: {result.error_message}")

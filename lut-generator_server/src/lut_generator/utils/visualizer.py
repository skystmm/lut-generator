"""
可视化模块 - Visualizer

色彩分布可视化
支持 RGB 直方图、色域图等可视化
"""

import numpy as np
import cv2
from pathlib import Path
from typing import Union, Optional, Tuple, List, Dict
from dataclasses import dataclass
from datetime import datetime
import json

from lut_generator.analysis.analyzer import ColorAnalyzer
from lut_generator.core.reinhard import ColorStatistics


@dataclass
class VisualizationConfig:
    """可视化配置"""
    width: int = 1200
    height: int = 800
    background_color: Tuple[int, int, int] = (30, 30, 30)
    colors: Dict[str, Tuple[int, int, int]] = None
    font: int = cv2.FONT_HERSHEY_SIMPLEX
    font_scale: float = 0.7
    line_thickness: int = 2
    show_grid: bool = True
    grid_color: Tuple[int, int, int] = (60, 60, 60)
    alpha: float = 0.7
    
    def __post_init__(self):
        if self.colors is None:
            self.colors = {
                'red': (255, 100, 100),
                'green': (100, 255, 100),
                'blue': (100, 100, 255),
                'white': (255, 255, 255),
                'gray': (128, 128, 128),
                'yellow': (255, 255, 100),
                'cyan': (100, 255, 255),
                'magenta': (255, 100, 255)
            }
    
    def validate(self) -> bool:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be between 0.0 and 1.0")
        return True


@dataclass
class VisualizationResult:
    """可视化结果"""
    output_path: str
    viz_type: str
    output_size: Tuple[int, int]
    generation_time: float
    success: bool
    error_message: Optional[str] = None
    data_path: Optional[str] = None


class ColorVisualizer:
    """色彩可视化工具"""
    
    def __init__(self, config: VisualizationConfig = None):
        self.config = config or VisualizationConfig()
        self.config.validate()
        self.analyzer = ColorAnalyzer()
    
    def plot_histogram(self,
                      image_path: Union[str, Path],
                      output_path: Union[str, Path],
                      title: str = "RGB Histogram",
                      show_combined: bool = True) -> VisualizationResult:
        """绘制 RGB 直方图"""
        start_time = datetime.now()
        
        try:
            image = self.analyzer.load_image(image_path)
            histograms = self._calculate_histogram(image)
            
            canvas = np.ones((self.config.height, self.config.width, 3), dtype=np.uint8)
            canvas[:] = self.config.background_color
            
            self._draw_title(canvas, title)
            
            chart_area = self._get_chart_area(canvas)
            self._draw_histogram_chart(canvas, histograms, chart_area, show_combined)
            
            self._draw_legend(canvas, show_combined)
            
            cv2.imwrite(str(output_path), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            return VisualizationResult(
                output_path=str(output_path),
                viz_type='histogram',
                output_size=(canvas.shape[1], canvas.shape[0]),
                generation_time=generation_time,
                success=True
            )
            
        except Exception as e:
            return VisualizationResult(
                output_path=str(output_path),
                viz_type='histogram',
                output_size=(0, 0),
                generation_time=0,
                success=False,
                error_message=str(e)
            )
    
    def plot_gamut(self,
                  image_path: Union[str, Path],
                  output_path: Union[str, Path],
                  title: str = "Color Gamut (a*b plane)",
                  max_points: int = 50000) -> VisualizationResult:
        """绘制色域图"""
        start_time = datetime.now()
        
        try:
            image = self.analyzer.load_image(image_path)
            lab = self.analyzer.rgb_to_lab(image)
            
            h, w = lab.shape[:2]
            total_pixels = h * w
            
            if total_pixels > max_points:
                indices = np.random.choice(total_pixels, max_points, replace=False)
                a_channel = lab[:, :, 1].flatten()[indices]
                b_channel = lab[:, :, 2].flatten()[indices]
            else:
                a_channel = lab[:, :, 1].flatten()
                b_channel = lab[:, :, 2].flatten()
            
            canvas = np.ones((self.config.height, self.config.width, 3), dtype=np.uint8)
            canvas[:] = self.config.background_color
            
            self._draw_title(canvas, title)
            
            chart_area = self._get_chart_area(canvas)
            self._draw_gamut_chart(canvas, a_channel, b_channel, chart_area)
            
            self._draw_gamut_stats(canvas, a_channel, b_channel)
            
            cv2.imwrite(str(output_path), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            return VisualizationResult(
                output_path=str(output_path),
                viz_type='gamut',
                output_size=(canvas.shape[1], canvas.shape[0]),
                generation_time=generation_time,
                success=True
            )
            
        except Exception as e:
            return VisualizationResult(
                output_path=str(output_path),
                viz_type='gamut',
                output_size=(0, 0),
                generation_time=0,
                success=False,
                error_message=str(e)
            )
    
    def _calculate_histogram(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """计算 RGB 直方图"""
        histograms = {}
        
        for i, channel in enumerate(['red', 'green', 'blue']):
            hist = cv2.calcHist([image], [i], None, [256], [0, 256])
            hist = hist.flatten()
            hist = hist / hist.max() if hist.max() > 0 else hist
            histograms[channel] = hist
        
        return histograms
    
    def _get_chart_area(self, canvas: np.ndarray, 
                        x_offset: int = 50, 
                        y_offset: int = 60,
                        x_margin: int = 50,
                        y_margin: int = 50) -> Tuple[int, int, int, int]:
        """获取图表绘制区域"""
        x = x_offset
        y = y_offset
        w = canvas.shape[1] - x_offset - x_margin
        h = canvas.shape[0] - y_offset - y_margin
        return (x, y, w, h)
    
    def _draw_title(self, canvas: np.ndarray, title: str) -> None:
        """绘制标题"""
        cv2.putText(
            canvas, title, (50, 40),
            self.config.font, self.config.font_scale * 1.2,
            self.config.colors['white'], 2, cv2.LINE_AA
        )
    
    def _draw_histogram_chart(self, canvas: np.ndarray,
                             histograms: Dict[str, np.ndarray],
                             chart_area: Tuple[int, int, int, int],
                             show_combined: bool) -> None:
        """绘制直方图"""
        x, y, w, h = chart_area
        
        if self.config.show_grid:
            self._draw_grid(canvas, x, y, w, h)
        
        cv2.line(canvas, (x, y), (x, y + h), self.config.colors['white'], 1)
        cv2.line(canvas, (x, y + h), (x + w, y + h), self.config.colors['white'], 1)
        
        bin_width = w / 256
        
        if show_combined:
            for channel, hist in histograms.items():
                color = self.config.colors[channel]
                
                points = []
                for i, value in enumerate(hist):
                    px = x + i * bin_width
                    py = y + h - value * h
                    points.append((int(px), int(py)))
                
                if len(points) > 1:
                    pts = np.array(points, dtype=np.int32)
                    pts = np.vstack([pts, np.array([[pts[-1, 0], y + h], [pts[0, 0], y + h]], dtype=np.int32)])
                    
                    overlay = canvas.copy()
                    cv2.fillPoly(overlay, [pts], color)
                    cv2.addWeighted(overlay, self.config.alpha, canvas, 1 - self.config.alpha, 0, canvas)
        else:
            channel_height = h // 3
            for i, (channel, hist) in enumerate(histograms.items()):
                color = self.config.colors[channel]
                channel_y = y + i * channel_height
                
                for j, value in enumerate(hist):
                    px = x + j * bin_width
                    py_start = channel_y + channel_height - value * channel_height
                    py_end = channel_y + channel_height
                    
                    cv2.line(canvas, (int(px), int(py_start)), (int(px), int(py_end)), color, 1)
    
    def _draw_gamut_chart(self, canvas: np.ndarray,
                         a_channel: np.ndarray, b_channel: np.ndarray,
                         chart_area: Tuple[int, int, int, int]) -> None:
        """绘制色域图"""
        x, y, w, h = chart_area
        
        if self.config.show_grid:
            self._draw_grid(canvas, x, y, w, h)
        
        # 坐标轴
        center_x = x + w // 2
        center_y = y + h // 2
        cv2.line(canvas, (center_x, y), (center_x, y + h), self.config.colors['gray'], 1)
        cv2.line(canvas, (x, center_y), (x + w, center_y), self.config.colors['gray'], 1)
        
        # 映射 a, b 到坐标
        a_min, a_max = a_channel.min(), a_channel.max()
        b_min, b_max = b_channel.min(), b_channel.max()
        
        a_range = max(abs(a_min), abs(a_max), 1)
        b_range = max(abs(b_min), abs(b_max), 1)
        
        # 采样绘制点
        max_pts = 10000
        if len(a_channel) > max_pts:
            indices = np.random.choice(len(a_channel), max_pts, replace=False)
            a_sample = a_channel[indices]
            b_sample = b_channel[indices]
        else:
            a_sample = a_channel
            b_sample = b_channel
        
        for a_val, b_val in zip(a_sample, b_sample):
            px = center_x + int((a_val / a_range) * (w // 2))
            py = center_y - int((b_val / b_range) * (h // 2))
            
            if x <= px <= x + w and y <= py <= y + h:
                cv2.circle(canvas, (px, py), 1, self.config.colors['cyan'], 1)
    
    def _draw_gamut_stats(self, canvas: np.ndarray,
                         a_channel: np.ndarray, b_channel: np.ndarray) -> None:
        """绘制色域统计信息"""
        stats_text = [
            f"a range: [{a_channel.min():.1f}, {a_channel.max():.1f}]",
            f"b range: [{b_channel.min():.1f}, {b_channel.max():.1f}]",
            f"a mean: {a_channel.mean():.1f}",
            f"b mean: {b_channel.mean():.1f}",
        ]
        
        y_pos = self.config.height - 30
        for text in reversed(stats_text):
            cv2.putText(canvas, text, (10, y_pos),
                       self.config.font, self.config.font_scale * 0.7,
                       self.config.colors['white'], 1, cv2.LINE_AA)
            y_pos -= 25
    
    def _draw_legend(self, canvas: np.ndarray, show_combined: bool) -> None:
        """绘制图例"""
        if show_combined:
            channels = ['red', 'green', 'blue']
        else:
            channels = ['red', 'green', 'blue']
        
        x = self.config.width - 150
        y = 70
        
        for channel in channels:
            color = self.config.colors[channel]
            cv2.rectangle(canvas, (x, y), (x + 15, y + 15), color, -1)
            cv2.putText(canvas, channel, (x + 20, y + 12),
                       self.config.font, self.config.font_scale * 0.7,
                       self.config.colors['white'], 1, cv2.LINE_AA)
            y += 25
    
    def _draw_grid(self, canvas: np.ndarray, x: int, y: int, w: int, h: int) -> None:
        """绘制网格"""
        for i in range(5):
            gx = x + int(w * i / 4)
            gy = y + int(h * i / 4)
            cv2.line(canvas, (gx, y), (gx, y + h), self.config.grid_color, 1)
            cv2.line(canvas, (x, gy), (x + w, gy), self.config.grid_color, 1)

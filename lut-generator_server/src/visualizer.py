"""
可视化模块 - Visualizer

色彩分布可视化
支持 RGB 直方图、色域图、3D 色彩空间等可视化
"""

import numpy as np
import cv2
from pathlib import Path
from typing import Union, Optional, Tuple, List, Dict
from dataclasses import dataclass
from datetime import datetime
import json

from color_analyzer import ColorAnalyzer, ColorStatistics


@dataclass
class VisualizationConfig:
    """可视化配置"""
    # 输出宽度
    width: int = 1200
    
    # 输出高度
    height: int = 800
    
    # 背景颜色（RGB）
    background_color: Tuple[int, int, int] = (30, 30, 30)
    
    # 图表颜色
    colors: Dict[str, Tuple[int, int, int]] = None
    
    # 字体
    font: int = cv2.FONT_HERSHEY_SIMPLEX
    
    # 字体大小
    font_scale: float = 0.7
    
    # 线条粗细
    line_thickness: int = 2
    
    # 网格显示
    show_grid: bool = True
    
    # 网格颜色
    grid_color: Tuple[int, int, int] = (60, 60, 60)
    
    # 透明度
    alpha: float = 0.7
    
    def __post_init__(self):
        """初始化默认颜色"""
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
        """验证配置"""
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("alpha must be between 0.0 and 1.0")
        
        return True


@dataclass
class VisualizationResult:
    """可视化结果"""
    # 输出路径
    output_path: str
    
    # 可视化类型
    viz_type: str
    
    # 输出尺寸
    output_size: Tuple[int, int]
    
    # 生成时间（秒）
    generation_time: float
    
    # 是否成功
    success: bool
    
    # 错误信息
    error_message: Optional[str] = None
    
    # 数据文件路径（如果有）
    data_path: Optional[str] = None


class ColorVisualizer:
    """
    色彩可视化工具
    
    生成各种色彩分析图表
    """
    
    def __init__(self, config: VisualizationConfig = None):
        """
        初始化可视化工具
        
        Args:
            config: 可视化配置
        """
        self.config = config or VisualizationConfig()
        self.config.validate()
        self.analyzer = ColorAnalyzer()
    
    def plot_histogram(self,
                      image_path: Union[str, Path],
                      output_path: Union[str, Path],
                      title: str = "RGB Histogram",
                      show_combined: bool = True) -> VisualizationResult:
        """
        绘制 RGB 直方图
        
        Args:
            image_path: 图像路径
            output_path: 输出路径
            title: 图表标题
            show_combined: 是否显示合并直方图
            
        Returns:
            VisualizationResult 结果对象
        """
        start_time = datetime.now()
        
        try:
            # 加载图像
            image = self.analyzer.load_image(image_path)
            
            # 计算直方图
            histograms = self._calculate_histogram(image)
            
            # 创建画布
            canvas = np.ones((self.config.height, self.config.width, 3), dtype=np.uint8)
            canvas[:] = self.config.background_color
            
            # 绘制标题
            self._draw_title(canvas, title)
            
            # 绘制直方图
            chart_area = self._get_chart_area(canvas)
            self._draw_histogram_chart(canvas, histograms, chart_area, show_combined)
            
            # 添加图例
            self._draw_legend(canvas, show_combined)
            
            # 保存
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
    
    def plot_histogram_comparison(self,
                                 original_path: Union[str, Path],
                                 processed_path: Union[str, Path],
                                 output_path: Union[str, Path],
                                 title: str = "RGB Histogram Comparison") -> VisualizationResult:
        """
        绘制对比直方图（原图 vs 处理后）
        
        Args:
            original_path: 原图路径
            processed_path: 处理后图像路径
            output_path: 输出路径
            title: 图表标题
            
        Returns:
            VisualizationResult 结果对象
        """
        start_time = datetime.now()
        
        try:
            # 加载图像
            original = self.analyzer.load_image(original_path)
            processed = self.analyzer.load_image(processed_path)
            
            # 计算直方图
            hist_original = self._calculate_histogram(original)
            hist_processed = self._calculate_histogram(processed)
            
            # 创建画布
            canvas = np.ones((self.config.height, self.config.width, 3), dtype=np.uint8)
            canvas[:] = self.config.background_color
            
            # 绘制标题
            self._draw_title(canvas, title)
            
            # 绘制对比直方图
            chart_area = self._get_chart_area(canvas, y_offset=80)
            self._draw_comparison_histogram(canvas, hist_original, hist_processed, chart_area)
            
            # 添加图例
            self._draw_comparison_legend(canvas)
            
            # 保存
            cv2.imwrite(str(output_path), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            return VisualizationResult(
                output_path=str(output_path),
                viz_type='histogram_comparison',
                output_size=(canvas.shape[1], canvas.shape[0]),
                generation_time=generation_time,
                success=True
            )
            
        except Exception as e:
            return VisualizationResult(
                output_path=str(output_path),
                viz_type='histogram_comparison',
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
        """
        绘制色域图（Lab 色彩空间的 a*b 平面）
        
        Args:
            image_path: 图像路径
            output_path: 输出路径
            title: 图表标题
            max_points: 最大采样点数
            
        Returns:
            VisualizationResult 结果对象
        """
        start_time = datetime.now()
        
        try:
            # 加载图像并转换为 Lab
            image = self.analyzer.load_image(image_path)
            lab = self.analyzer.rgb_to_lab(image)
            
            # 采样像素
            h, w = lab.shape[:2]
            total_pixels = h * w
            
            if total_pixels > max_points:
                # 随机采样
                indices = np.random.choice(total_pixels, max_points, replace=False)
                a_channel = lab[:, :, 1].flatten()[indices]
                b_channel = lab[:, :, 2].flatten()[indices]
            else:
                a_channel = lab[:, :, 1].flatten()
                b_channel = lab[:, :, 2].flatten()
            
            # 创建画布
            canvas = np.ones((self.config.height, self.config.width, 3), dtype=np.uint8)
            canvas[:] = self.config.background_color
            
            # 绘制标题
            self._draw_title(canvas, title)
            
            # 绘制色域图
            chart_area = self._get_chart_area(canvas)
            self._draw_gamut_chart(canvas, a_channel, b_channel, chart_area)
            
            # 添加统计信息
            self._draw_gamut_stats(canvas, a_channel, b_channel)
            
            # 保存
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
    
    def plot_gamut_comparison(self,
                             original_path: Union[str, Path],
                             processed_path: Union[str, Path],
                             output_path: Union[str, Path],
                             title: str = "Color Gamut Comparison") -> VisualizationResult:
        """
        绘制色域对比图
        
        Args:
            original_path: 原图路径
            processed_path: 处理后图像路径
            output_path: 输出路径
            title: 图表标题
            
        Returns:
            VisualizationResult 结果对象
        """
        start_time = datetime.now()
        
        try:
            # 加载并转换
            original = self.analyzer.load_image(original_path)
            processed = self.analyzer.load_image(processed_path)
            
            original_lab = self.analyzer.rgb_to_lab(original)
            processed_lab = self.analyzer.rgb_to_lab(processed)
            
            # 采样
            max_points = 30000
            
            orig_a = original_lab[:, :, 1].flatten()
            orig_b = original_lab[:, :, 2].flatten()
            proc_a = processed_lab[:, :, 1].flatten()
            proc_b = processed_lab[:, :, 2].flatten()
            
            if len(orig_a) > max_points:
                indices = np.random.choice(len(orig_a), max_points, replace=False)
                orig_a = orig_a[indices]
                orig_b = orig_b[indices]
                proc_a = proc_a[indices]
                proc_b = proc_b[indices]
            
            # 创建画布
            canvas = np.ones((self.config.height, self.config.width, 3), dtype=np.uint8)
            canvas[:] = self.config.background_color
            
            # 绘制标题
            self._draw_title(canvas, title)
            
            # 绘制对比色域图
            chart_area = self._get_chart_area(canvas)
            self._draw_gamut_comparison_chart(canvas, orig_a, orig_b, proc_a, proc_b, chart_area)
            
            # 添加图例
            self._draw_gamut_comparison_legend(canvas)
            
            # 保存
            cv2.imwrite(str(output_path), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            return VisualizationResult(
                output_path=str(output_path),
                viz_type='gamut_comparison',
                output_size=(canvas.shape[1], canvas.shape[0]),
                generation_time=generation_time,
                success=True
            )
            
        except Exception as e:
            return VisualizationResult(
                output_path=str(output_path),
                viz_type='gamut_comparison',
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
            # 归一化
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
            canvas,
            title,
            (50, 40),
            self.config.font,
            self.config.font_scale * 1.2,
            self.config.colors['white'],
            2,
            cv2.LINE_AA
        )
    
    def _draw_histogram_chart(self, canvas: np.ndarray,
                             histograms: Dict[str, np.ndarray],
                             chart_area: Tuple[int, int, int, int],
                             show_combined: bool) -> None:
        """绘制直方图"""
        x, y, w, h = chart_area
        
        # 绘制网格
        if self.config.show_grid:
            self._draw_grid(canvas, x, y, w, h)
        
        # 绘制坐标轴
        cv2.line(canvas, (x, y), (x, y + h), self.config.colors['white'], 1)
        cv2.line(canvas, (x, y + h), (x + w, y + h), self.config.colors['white'], 1)
        
        # 绘制直方图
        bin_width = w / 256
        
        if show_combined:
            # 合并显示（半透明叠加）
            for channel, hist in histograms.items():
                color = self.config.colors[channel]
                
                points = []
                for i, value in enumerate(hist):
                    px = x + i * bin_width
                    py = y + h - value * h
                    points.append((int(px), int(py)))
                
                # 填充区域
                if len(points) > 1:
                    pts = np.array(points, dtype=np.int32)
                    pts = np.vstack([pts, np.array([[pts[-1, 0], y + h], [pts[0, 0], y + h]], dtype=np.int32)])
                    
                    overlay = canvas.copy()
                    cv2.fillPoly(overlay, [pts], color)
                    cv2.addWeighted(overlay, self.config.alpha, canvas, 1 - self.config.alpha, 0, canvas)
        else:
            # 分开通道显示
            channel_height = h // 3
            for i, (channel, hist) in enumerate(histograms.items()):
                color = self.config.colors[channel]
                channel_y = y + i * channel_height
                
                for j, value in enumerate(hist):
                    px = x + j * bin_width
                    py_start = channel_y + channel_height - value * channel_height
                    py_end = channel_y + channel_height
                    
                    cv2.line(
                        canvas,
                        (int(px), int(py_start)),
                        (int(px), int(py_end)),
                        color,
                        1
                    )
    
    def _draw_comparison_histogram(self, canvas: np.ndarray,
                                   hist_original: Dict[str, np.ndarray],
                                   hist_processed: Dict[str, np.ndarray],
                                   chart_area: Tuple[int, int, int, int]) -> None:
        """绘制对比直方图"""
        x, y, w, h = chart_area
        
        # 绘制网格
        if self.config.show_grid:
            self._draw_grid(canvas, x, y, w, h)
        
        # 绘制坐标轴
        cv2.line(canvas, (x, y), (x, y + h), self.config.colors['white'], 1)
        cv2.line(canvas, (x, y + h), (x + w, y + h), self.config.colors['white'], 1)
        
        bin_width = w / 256
        
        # 绘制原图直方图（实线）
        for channel, hist in hist_original.items():
            color = self.config.colors[channel]
            
            points = []
            for i, value in enumerate(hist):
                px = x + i * bin_width
                py = y + h - value * h * 0.9  # 留出空间给处理后
                points.append((int(px), int(py)))
            
            if len(points) > 1:
                pts = np.array(points, dtype=np.int32)
                cv2.polylines(canvas, [pts], False, color, 2)
        
        # 绘制处理后直方图（虚线效果）
        for channel, hist in hist_processed.items():
            color = self.config.colors[channel]
            lighter_color = tuple(min(255, c + 50) for c in color)
            
            points = []
            for i, value in enumerate(hist):
                px = x + i * bin_width
                py = y + h - value * h * 0.9
                points.append((int(px), int(py)))
            
            if len(points) > 1:
                pts = np.array(points, dtype=np.int32)
                cv2.polylines(canvas, [pts], False, lighter_color, 2)
    
    def _draw_gamut_chart(self, canvas: np.ndarray,
                         a_channel: np.ndarray,
                         b_channel: np.ndarray,
                         chart_area: Tuple[int, int, int, int]) -> None:
        """绘制色域图"""
        x, y, w, h = chart_area
        
        # 计算中心点和半径
        center_x = x + w // 2
        center_y = y + h // 2
        radius = min(w, h) // 2 - 10
        
        # 绘制背景圆（理论色域）
        cv2.circle(canvas, (center_x, center_y), radius, self.config.colors['gray'], 1)
        
        # 绘制坐标轴
        cv2.line(canvas, (center_x - radius, center_y), 
                (center_x + radius, center_y), 
                self.config.colors['white'], 1)
        cv2.line(canvas, (center_x, center_y - radius), 
                (center_x, center_y + radius), 
                self.config.colors['white'], 1)
        
        # 绘制标签
        cv2.putText(canvas, "+a", (center_x + radius - 20, center_y - 5),
                   self.config.font, 0.5, self.config.colors['white'], 1)
        cv2.putText(canvas, "-a", (center_x - radius + 5, center_y - 5),
                   self.config.font, 0.5, self.config.colors['white'], 1)
        cv2.putText(canvas, "+b", (center_x + 5, center_y - radius + 15),
                   self.config.font, 0.5, self.config.colors['white'], 1)
        cv2.putText(canvas, "-b", (center_x + 5, center_y + radius - 5),
                   self.config.font, 0.5, self.config.colors['white'], 1)
        
        # 绘制数据点
        a_min, a_max = -128, 127
        b_min, b_max = -128, 127
        
        for a, b in zip(a_channel[::10], b_channel[::10]):  # 降采样
            # 映射到画布坐标
            px = center_x + int((a - a_min) / (a_max - a_min) * w) - w // 2
            py = center_y - int((b - b_min) / (b_max - b_min) * h) + h // 2
            
            if x <= px <= x + w and y <= py <= y + h:
                cv2.circle(canvas, (px, py), 1, self.config.colors['cyan'], -1)
    
    def _draw_gamut_comparison_chart(self, canvas: np.ndarray,
                                    orig_a: np.ndarray, orig_b: np.ndarray,
                                    proc_a: np.ndarray, proc_b: np.ndarray,
                                    chart_area: Tuple[int, int, int, int]) -> None:
        """绘制色域对比图"""
        x, y, w, h = chart_area
        
        # 计算中心点和半径
        center_x = x + w // 2
        center_y = y + h // 2
        radius = min(w, h) // 2 - 10
        
        # 绘制背景圆
        cv2.circle(canvas, (center_x, center_y), radius, self.config.colors['gray'], 1)
        
        # 绘制坐标轴
        cv2.line(canvas, (center_x - radius, center_y), 
                (center_x + radius, center_y), 
                self.config.colors['white'], 1)
        cv2.line(canvas, (center_x, center_y - radius), 
                (center_x, center_y + radius), 
                self.config.colors['white'], 1)
        
        # 映射函数
        a_min, a_max = -128, 127
        b_min, b_max = -128, 127
        
        def map_coords(a, b):
            px = center_x + int((a - a_min) / (a_max - a_min) * w) - w // 2
            py = center_y - int((b - b_min) / (b_max - b_min) * h) + h // 2
            return px, py
        
        # 绘制原图数据点（青色）
        for a, b in zip(orig_a[::10], orig_b[::10]):
            px, py = map_coords(a, b)
            if x <= px <= x + w and y <= py <= y + h:
                cv2.circle(canvas, (px, py), 1, self.config.colors['cyan'], -1)
        
        # 绘制处理后数据点（黄色）
        for a, b in zip(proc_a[::10], proc_b[::10]):
            px, py = map_coords(a, b)
            if x <= px <= x + w and y <= py <= y + h:
                cv2.circle(canvas, (px, py), 1, self.config.colors['yellow'], -1)
    
    def _draw_gamut_stats(self, canvas: np.ndarray,
                         a_channel: np.ndarray,
                         b_channel: np.ndarray) -> None:
        """绘制色域统计信息"""
        y_start = 50
        x_start = self.config.width - 250
        
        stats = [
            f"a mean: {np.mean(a_channel):.1f}",
            f"a std: {np.std(a_channel):.1f}",
            f"b mean: {np.mean(b_channel):.1f}",
            f"b std: {np.std(b_channel):.1f}",
            f"a range: [{np.min(a_channel):.1f}, {np.max(a_channel):.1f}]",
            f"b range: [{np.min(b_channel):.1f}, {np.max(b_channel):.1f}]"
        ]
        
        for i, stat in enumerate(stats):
            cv2.putText(
                canvas,
                stat,
                (x_start, y_start + i * 20),
                self.config.font,
                0.5,
                self.config.colors['white'],
                1,
                cv2.LINE_AA
            )
    
    def _draw_legend(self, canvas: np.ndarray, show_combined: bool) -> None:
        """绘制图例"""
        x = 50
        y = self.config.height - 40
        
        if show_combined:
            labels = [
                (self.config.colors['red'], "Red"),
                (self.config.colors['green'], "Green"),
                (self.config.colors['blue'], "Blue")
            ]
        else:
            labels = [
                (self.config.colors['red'], "Red Channel"),
                (self.config.colors['green'], "Green Channel"),
                (self.config.colors['blue'], "Blue Channel")
            ]
        
        for color, label in labels:
            cv2.rectangle(canvas, (x, y - 10), (x + 20, y + 5), color, -1)
            cv2.putText(
                canvas,
                label,
                (x + 25, y + 5),
                self.config.font,
                0.5,
                self.config.colors['white'],
                1,
                cv2.LINE_AA
            )
            x += 120
    
    def _draw_comparison_legend(self, canvas: np.ndarray) -> None:
        """绘制对比图例"""
        x = 50
        y = self.config.height - 40
        
        labels = [
            (self.config.colors['white'], "Original"),
            (self.config.colors['yellow'], "Processed")
        ]
        
        for color, label in labels:
            cv2.line(canvas, (x, y), (x + 20, y), color, 2)
            cv2.putText(
                canvas,
                label,
                (x + 25, y + 5),
                self.config.font,
                0.5,
                self.config.colors['white'],
                1,
                cv2.LINE_AA
            )
            x += 120
    
    def _draw_gamut_comparison_legend(self, canvas: np.ndarray) -> None:
        """绘制色域对比图例"""
        x = 50
        y = self.config.height - 40
        
        labels = [
            (self.config.colors['cyan'], "Original"),
            (self.config.colors['yellow'], "Processed")
        ]
        
        for color, label in labels:
            cv2.circle(canvas, (x + 10, y - 3), 5, color, -1)
            cv2.putText(
                canvas,
                label,
                (x + 25, y + 5),
                self.config.font,
                0.5,
                self.config.colors['white'],
                1,
                cv2.LINE_AA
            )
            x += 120
    
    def _draw_grid(self, canvas: np.ndarray,
                  x: int, y: int, w: int, h: int) -> None:
        """绘制网格"""
        # 垂直线
        for i in range(11):
            px = x + int(w * i / 10)
            cv2.line(canvas, (px, y), (px, y + h), self.config.grid_color, 1)
        
        # 水平线
        for i in range(6):
            py = y + int(h * i / 5)
            cv2.line(canvas, (x, py), (x + w, py), self.config.grid_color, 1)


def visualize_color_distribution(image_path: Union[str, Path],
                                output_dir: Union[str, Path],
                                width: int = 1200,
                                height: int = 800) -> List[VisualizationResult]:
    """
    便捷函数：生成完整的色彩分布可视化
    
    Args:
        image_path: 图像路径
        output_dir: 输出目录
        width: 输出宽度
        height: 输出高度
        
    Returns:
        VisualizationResult 列表
    """
    config = VisualizationConfig(width=width, height=height)
    visualizer = ColorVisualizer(config)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    # RGB 直方图
    hist_path = output_dir / "histogram.png"
    results.append(visualizer.plot_histogram(image_path, hist_path))
    
    # 色域图
    gamut_path = output_dir / "gamut.png"
    results.append(visualizer.plot_gamut(image_path, gamut_path))
    
    return results


if __name__ == "__main__":
    # 简单测试
    import sys
    
    print("Color Visualizer Test")
    print("=" * 50)
    
    print("\nUsage:")
    print("  python visualizer.py <image_path> <output_dir>")
    
    if len(sys.argv) >= 3:
        image_path = sys.argv[1]
        output_dir = sys.argv[2]
        
        results = visualize_color_distribution(image_path, output_dir)
        
        for result in results:
            print(f"\n{result.viz_type}:")
            print(f"  Success: {result.success}")
            if result.success:
                print(f"  Output: {result.output_path}")
                print(f"  Size: {result.output_size}")
            else:
                print(f"  Error: {result.error_message}")

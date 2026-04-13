"""
HTML 报告导出模块 - HTMLReportGenerator

生成包含对比图和统计信息的交互式 HTML 报告
支持滑块对比、直方图展示、色彩分布可视化
"""

import numpy as np
from pathlib import Path
from typing import Union, Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import base64
import cv2

from color_analyzer import ColorStatistics


@dataclass
class ReportConfig:
    """HTML 报告配置"""
    # 报告标题
    title: str = "LUT 处理报告"
    
    # 是否包含滑块对比
    include_slider: bool = True
    
    # 是否包含直方图
    include_histogram: bool = True
    
    # 是否包含色域图
    include_gamut: bool = True
    
    # 是否包含统计表格
    include_statistics: bool = True
    
    # 主题
    theme: str = 'dark'  # 'dark', 'light'
    
    # 输出宽度
    output_width: int = 1400
    
    def validate(self) -> bool:
        """验证配置"""
        valid_themes = ['dark', 'light']
        if self.theme not in valid_themes:
            raise ValueError(f"theme must be one of {valid_themes}")
        
        return True


@dataclass
class ReportData:
    """报告数据"""
    # 原图路径
    original_image: str
    
    # 处理后图像路径
    processed_image: str
    
    # 对比图路径
    comparison_image: Optional[str] = None
    
    # 直方图路径
    histogram_original: Optional[str] = None
    histogram_processed: Optional[str] = None
    histogram_comparison: Optional[str] = None
    
    # 色域图路径
    gamut_original: Optional[str] = None
    gamut_processed: Optional[str] = None
    gamut_comparison: Optional[str] = None
    
    # 统计信息
    statistics: Optional[Dict[str, Any]] = None
    
    # LUT 信息
    lut_info: Optional[Dict[str, Any]] = None
    
    # 处理时间
    processing_time: Optional[float] = None
    
    # 生成时间
    generated_at: str = None
    
    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now().isoformat()


@dataclass
class ReportResult:
    """报告生成结果"""
    # 输出路径
    output_path: str
    
    # 是否成功
    success: bool
    
    # 错误信息
    error_message: Optional[str] = None
    
    # 报告大小（字节）
    file_size: int = 0
    
    # 生成时间（秒）
    generation_time: float = 0.0


class HTMLReportGenerator:
    """
    HTML 报告生成器
    
    生成包含交互式对比和统计信息的 HTML 报告
    """
    
    def __init__(self, config: ReportConfig = None):
        """
        初始化报告生成器
        
        Args:
            config: 报告配置
        """
        self.config = config or ReportConfig()
        self.config.validate()
    
    def generate(self, 
                report_data: ReportData,
                output_path: Union[str, Path]) -> ReportResult:
        """
        生成 HTML 报告
        
        Args:
            report_data: 报告数据
            output_path: 输出路径
            
        Returns:
            ReportResult 结果对象
        """
        start_time = datetime.now()
        
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 生成 HTML 内容
            html_content = self._generate_html(report_data)
            
            # 保存文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            file_size = output_path.stat().st_size
            
            return ReportResult(
                output_path=str(output_path),
                success=True,
                file_size=file_size,
                generation_time=generation_time
            )
            
        except Exception as e:
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            return ReportResult(
                output_path=str(output_path),
                success=False,
                error_message=str(e),
                generation_time=generation_time
            )
    
    def generate_from_paths(self,
                           original_path: Union[str, Path],
                           processed_path: Union[str, Path],
                           output_path: Union[str, Path],
                           statistics: Dict[str, Any] = None,
                           lut_info: Dict[str, Any] = None,
                           processing_time: float = None) -> ReportResult:
        """
        从图像路径生成报告
        
        Args:
            original_path: 原图路径
            processed_path: 处理后图像路径
            output_path: 输出路径
            statistics: 统计信息
            lut_info: LUT 信息
            processing_time: 处理时间
            
        Returns:
            ReportResult 结果对象
        """
        report_data = ReportData(
            original_image=str(original_path),
            processed_image=str(processed_path),
            statistics=statistics,
            lut_info=lut_info,
            processing_time=processing_time
        )
        
        return self.generate(report_data, output_path)
    
    def _generate_html(self, report_data: ReportData) -> str:
        """生成 HTML 内容"""
        # 编码图像为 base64
        original_b64 = self._image_to_base64(report_data.original_image)
        processed_b64 = self._image_to_base64(report_data.processed_image)
        
        comparison_b64 = None
        if report_data.comparison_image and Path(report_data.comparison_image).exists():
            comparison_b64 = self._image_to_base64(report_data.comparison_image)
        
        histogram_b64 = None
        if report_data.histogram_comparison and Path(report_data.histogram_comparison).exists():
            histogram_b64 = self._image_to_base64(report_data.histogram_comparison)
        
        gamut_b64 = None
        if report_data.gamut_comparison and Path(report_data.gamut_comparison).exists():
            gamut_b64 = self._image_to_base64(report_data.gamut_comparison)
        
        # 生成 HTML
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config.title}</title>
    <style>
        {self._get_css()}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{self.config.title}</h1>
            <p class="timestamp">生成时间：{report_data.generated_at}</p>
        </header>
        
        {self._generate_slider_section(original_b64, processed_b64) if self.config.include_slider else ''}
        
        {self._generate_statistics_section(report_data.statistics, report_data.lut_info, report_data.processing_time) if self.config.include_statistics else ''}
        
        {self._generate_histogram_section(histogram_b64) if self.config.include_histogram and histogram_b64 else ''}
        
        {self._generate_gamut_section(gamut_b64) if self.config.include_gamut and gamut_b64 else ''}
        
        <footer>
            <p>LUT Generator - 色彩风格分析与迁移工具</p>
        </footer>
    </div>
    
    <script>
        {self._get_javascript()}
    </script>
</body>
</html>"""
        
        return html
    
    def _generate_slider_section(self, original_b64: str, processed_b64: str) -> str:
        """生成滑块对比部分"""
        return f"""
        <section class="comparison-section">
            <h2>前后对比</h2>
            <div class="slider-container">
                <div class="slider-wrapper">
                    <div class="image-container">
                        <img src="data:image/png;base64,{original_b64}" alt="Original" class="image original">
                    </div>
                    <div class="image-container overlay">
                        <img src="data:image/png;base64,{processed_b64}" alt="Processed" class="image processed">
                    </div>
                    <input type="range" min="0" max="100" value="50" class="slider" id="comparisonSlider">
                    <div class="slider-handle" id="sliderHandle"></div>
                </div>
                <div class="slider-labels">
                    <span>原图</span>
                    <span>处理后</span>
                </div>
            </div>
        </section>"""
    
    def _generate_statistics_section(self, statistics: Dict, lut_info: Dict, 
                                     processing_time: float) -> str:
        """生成统计信息部分"""
        stats_html = ""
        
        if statistics:
            stats_html += """
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>原图</h3>
                    <table class="stats-table">"""
            
            if 'original' in statistics:
                orig = statistics['original']
                stats_html += f"""
                        <tr><td>平均亮度</td><td>{orig.get('brightness', 0):.2f}</td></tr>
                        <tr><td>R 均值</td><td>{orig['mean_rgb'][0] if 'mean_rgb' in orig else 0:.2f}</td></tr>
                        <tr><td>G 均值</td><td>{orig['mean_rgb'][1] if 'mean_rgb' in orig else 0:.2f}</td></tr>
                        <tr><td>B 均值</td><td>{orig['mean_rgb'][2] if 'mean_rgb' in orig else 0:.2f}</td></tr>"""
            
            stats_html += """
                    </table>
                </div>
                
                <div class="stat-card">
                    <h3>处理后</h3>
                    <table class="stats-table">"""
            
            if 'processed' in statistics:
                proc = statistics['processed']
                stats_html += f"""
                        <tr><td>平均亮度</td><td>{proc.get('brightness', 0):.2f}</td></tr>
                        <tr><td>R 均值</td><td>{proc['mean_rgb'][0] if 'mean_rgb' in proc else 0:.2f}</td></tr>
                        <tr><td>G 均值</td><td>{proc['mean_rgb'][1] if 'mean_rgb' in proc else 0:.2f}</td></tr>
                        <tr><td>B 均值</td><td>{proc['mean_rgb'][2] if 'mean_rgb' in proc else 0:.2f}</td></tr>"""
            
            stats_html += """
                    </table>
                </div>
                
                <div class="stat-card">
                    <h3>变化</h3>
                    <table class="stats-table">"""
            
            if 'difference' in statistics:
                diff = statistics['difference']
                brightness_change = statistics.get('brightness_change', 0)
                stats_html += f"""
                        <tr><td>亮度变化</td><td>{brightness_change:+.2f}%</td></tr>
                        <tr><td>平均差异</td><td>{diff.get('mean_diff', 0):.2f}</td></tr>
                        <tr><td>最大差异</td><td>{diff.get('max_diff', 0):.2f}</td></tr>"""
            
            stats_html += """
                    </table>
                </div>
            </div>"""
        
        # LUT 信息
        lut_html = ""
        if lut_info:
            lut_html = f"""
            <div class="lut-info">
                <h3>LUT 信息</h3>
                <table class="stats-table">
                    <tr><td>网格大小</td><td>{lut_info.get('lut_grid_size', 33)}³</td></tr>
                    <tr><td>插值方法</td><td>{lut_info.get('interpolation', 'trilinear')}</td></tr>
                    <tr><td>输入色彩空间</td><td>{lut_info.get('input_colorspace', 'sRGB')}</td></tr>
                    <tr><td>输出色彩空间</td><td>{lut_info.get('output_colorspace', 'sRGB')}</td></tr>
                </table>
            </div>"""
        
        # 处理时间
        time_html = ""
        if processing_time is not None:
            time_html = f"""
            <div class="processing-time">
                <p>处理时间：<strong>{processing_time:.2f} 秒</strong></p>
            </div>"""
        
        return f"""
        <section class="statistics-section">
            <h2>统计信息</h2>
            {stats_html}
            {lut_html}
            {time_html}
        </section>"""
    
    def _generate_histogram_section(self, histogram_b64: str) -> str:
        """生成直方图部分"""
        return f"""
        <section class="histogram-section">
            <h2>RGB 直方图对比</h2>
            <div class="image-wrapper">
                <img src="data:image/png;base64,{histogram_b64}" alt="Histogram Comparison" class="chart-image">
            </div>
        </section>"""
    
    def _generate_gamut_section(self, gamut_b64: str) -> str:
        """生成色域图部分"""
        return f"""
        <section class="gamut-section">
            <h2>色彩分布对比 (a*b 平面)</h2>
            <div class="image-wrapper">
                <img src="data:image/png;base64,{gamut_b64}" alt="Gamut Comparison" class="chart-image">
            </div>
        </section>"""
    
    def _get_css(self) -> str:
        """获取 CSS 样式"""
        if self.config.theme == 'dark':
            return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            line-height: 1.6;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #0f3460;
        }
        
        header h1 {
            font-size: 2.5em;
            color: #e94560;
            margin-bottom: 10px;
        }
        
        .timestamp {
            color: #888;
            font-size: 0.9em;
        }
        
        section {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
        }
        
        section h2 {
            color: #e94560;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        
        .comparison-section {
            text-align: center;
        }
        
        .slider-container {
            position: relative;
            display: inline-block;
            margin: 20px 0;
        }
        
        .slider-wrapper {
            position: relative;
            overflow: hidden;
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }
        
        .image-container {
            position: relative;
        }
        
        .image {
            display: block;
            max-width: 100%;
            height: auto;
        }
        
        .overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 50%;
            overflow: hidden;
            border-right: 3px solid #e94560;
        }
        
        .slider {
            position: absolute;
            width: 100%;
            height: 100%;
            opacity: 0;
            cursor: ew-resize;
            z-index: 10;
        }
        
        .slider-handle {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 40px;
            height: 40px;
            background: #e94560;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            pointer-events: none;
            z-index: 5;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        }
        
        .slider-handle::before {
            content: '◀ ▶';
            color: white;
            font-size: 14px;
        }
        
        .slider-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
            font-weight: bold;
            color: #e94560;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 20px;
        }
        
        .stat-card h3 {
            color: #0f3460;
            color: #e94560;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        
        .stats-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .stats-table td {
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .stats-table td:first-child {
            color: #888;
        }
        
        .stats-table td:last-child {
            text-align: right;
            font-weight: bold;
            color: #e0e0e0;
        }
        
        .lut-info, .processing-time {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .lut-info h3, .processing-time h3 {
            color: #e94560;
            margin-bottom: 15px;
        }
        
        .image-wrapper {
            text-align: center;
        }
        
        .chart-image {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
        }
        
        footer {
            text-align: center;
            padding-top: 40px;
            border-top: 2px solid #0f3460;
            color: #888;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 20px 10px;
            }
            
            header h1 {
                font-size: 1.8em;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
        }"""
        else:
            # Light theme (简化版本)
            return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        section {
            background: white;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        /* ... 其他样式类似 ... */"""
    
    def _get_javascript(self) -> str:
        """获取 JavaScript 代码"""
        return """
        // 滑块对比功能
        const slider = document.getElementById('comparisonSlider');
        const overlay = document.querySelector('.overlay');
        const handle = document.getElementById('sliderHandle');
        
        if (slider && overlay && handle) {
            slider.addEventListener('input', function() {
                const value = this.value;
                overlay.style.width = value + '%';
                handle.style.left = value + '%';
            });
        }
        
        // 图片加载完成后初始化
        window.addEventListener('load', function() {
            if (slider) {
                // 初始化滑块位置
                const event = new Event('input');
                slider.dispatchEvent(event);
            }
        });
        
        // 响应式处理
        function updateSliderDimensions() {
            if (overlay) {
                const wrapper = overlay.parentElement;
                overlay.style.height = wrapper.offsetHeight + 'px';
            }
        }
        
        window.addEventListener('resize', updateSliderDimensions);
        window.addEventListener('load', updateSliderDimensions);"""
    
    def _image_to_base64(self, image_path: str) -> str:
        """将图像转换为 base64 编码"""
        if not image_path or not Path(image_path).exists():
            return ""
        
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            return base64.b64encode(image_data).decode('utf-8')
        except Exception:
            return ""


def generate_html_report(original_path: Union[str, Path],
                        processed_path: Union[str, Path],
                        output_path: Union[str, Path],
                        statistics: Dict = None,
                        lut_info: Dict = None,
                        processing_time: float = None,
                        theme: str = 'dark') -> ReportResult:
    """
    便捷函数：生成 HTML 报告
    
    Args:
        original_path: 原图路径
        processed_path: 处理后图像路径
        output_path: 输出路径
        statistics: 统计信息
        lut_info: LUT 信息
        processing_time: 处理时间
        theme: 主题
        
    Returns:
        ReportResult 结果对象
    """
    config = ReportConfig(theme=theme)
    generator = HTMLReportGenerator(config)
    
    return generator.generate_from_paths(
        original_path,
        processed_path,
        output_path,
        statistics,
        lut_info,
        processing_time
    )


if __name__ == "__main__":
    # 简单测试
    import sys
    
    print("HTML Report Generator Test")
    print("=" * 50)
    
    print("\nUsage:")
    print("  python html_report.py <original_image> <processed_image> <output_html>")
    
    if len(sys.argv) >= 4:
        original = sys.argv[1]
        processed = sys.argv[2]
        output = sys.argv[3]
        
        # 模拟统计信息
        statistics = {
            'original': {
                'brightness': 128.5,
                'mean_rgb': [120.3, 125.7, 130.2]
            },
            'processed': {
                'brightness': 135.2,
                'mean_rgb': [125.8, 130.4, 138.6]
            },
            'difference': {
                'mean_diff': 15.3,
                'max_diff': 85.2
            },
            'brightness_change': 5.2
        }
        
        lut_info = {
            'lut_grid_size': 33,
            'interpolation': 'trilinear',
            'input_colorspace': 'sRGB',
            'output_colorspace': 'sRGB'
        }
        
        result = generate_html_report(
            original,
            processed,
            output,
            statistics=statistics,
            lut_info=lut_info,
            processing_time=2.5
        )
        
        print(f"\nResult: {result.success}")
        if result.success:
            print(f"Output: {result.output_path}")
            print(f"File size: {result.file_size} bytes")
            print(f"Generation time: {result.generation_time:.2f}s")
        else:
            print(f"Error: {result.error_message}")

"""
HTML 报告导出模块 - HTMLReportGenerator

生成包含对比图和统计信息的交互式 HTML 报告
"""

import numpy as np
from pathlib import Path
from typing import Union, Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import base64
import cv2


@dataclass
class ReportConfig:
    """HTML 报告配置"""
    title: str = "LUT 处理报告"
    include_slider: bool = True
    include_histogram: bool = True
    include_gamut: bool = True
    include_statistics: bool = True
    theme: str = 'dark'
    output_width: int = 1400
    
    def validate(self) -> bool:
        valid_themes = ['dark', 'light']
        if self.theme not in valid_themes:
            raise ValueError(f"theme must be one of {valid_themes}")
        return True


@dataclass
class ReportData:
    """报告数据"""
    original_image: str
    processed_image: str
    comparison_image: Optional[str] = None
    histogram_original: Optional[str] = None
    histogram_processed: Optional[str] = None
    histogram_comparison: Optional[str] = None
    gamut_original: Optional[str] = None
    gamut_processed: Optional[str] = None
    gamut_comparison: Optional[str] = None
    statistics: Optional[Dict[str, Any]] = None
    lut_info: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None
    generated_at: str = None
    
    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now().isoformat()


@dataclass
class ReportResult:
    """报告生成结果"""
    output_path: str
    success: bool
    error_message: Optional[str] = None
    file_size: int = 0
    generation_time: float = 0.0


class HTMLReportGenerator:
    """HTML 报告生成器"""
    
    def __init__(self, config: ReportConfig = None):
        self.config = config or ReportConfig()
        self.config.validate()
    
    def generate(self, 
                report_data: ReportData,
                output_path: Union[str, Path]) -> ReportResult:
        """生成 HTML 报告"""
        start_time = datetime.now()
        
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            html_content = self._generate_html(report_data)
            
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
            
        except (OSError, IOError, ValueError, RuntimeError) as e:
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
        """从图像路径生成报告"""
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
    
    def _image_to_base64(self, image_path: str) -> Optional[str]:
        """将图像转换为 base64"""
        path = Path(image_path)
        if not path.exists():
            return None
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
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
            </div>"""
        
        lut_html = ""
        if lut_info:
            lut_html = f"""
            <div class="lut-info">
                <h3>LUT 信息</h3>
                <table class="stats-table">
                    <tr><td>网格大小</td><td>{lut_info.get('lut_grid_size', 33)}³</td></tr>
                    <tr><td>插值方法</td><td>{lut_info.get('interpolation', 'trilinear')}</td></tr>
                </table>
            </div>"""
        
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
        return f"""
        <section class="histogram-section">
            <h2>RGB 直方图对比</h2>
            <div class="image-wrapper">
                <img src="data:image/png;base64,{histogram_b64}" alt="Histogram" class="chart-image">
            </div>
        </section>"""
    
    def _generate_gamut_section(self, gamut_b64: str) -> str:
        return f"""
        <section class="gamut-section">
            <h2>色彩分布对比 (a*b 平面)</h2>
            <div class="image-wrapper">
                <img src="data:image/png;base64,{gamut_b64}" alt="Gamut" class="chart-image">
            </div>
        </section>"""
    
    def _get_css(self) -> str:
        if self.config.theme == 'dark':
            return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            line-height: 1.6;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 40px 20px; }
        header { text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 2px solid #0f3460; }
        header h1 { font-size: 2.5em; color: #e94560; margin-bottom: 10px; }
        .timestamp { color: #888; font-size: 0.9em; }
        section { background: rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 30px; margin-bottom: 30px; }
        section h2 { color: #e94560; margin-bottom: 20px; font-size: 1.8em; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .stat-card { background: rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 20px; }
        .stat-card h3 { color: #e94560; margin-bottom: 15px; }
        .stats-table { width: 100%; border-collapse: collapse; }
        .stats-table td { padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .stats-table td:first-child { color: #888; }
        .image-wrapper { text-align: center; }
        .chart-image { max-width: 100%; border-radius: 8px; }
        .slider-container { position: relative; display: inline-block; }
        .slider-wrapper { position: relative; overflow: hidden; border-radius: 8px; }
        .image-container { position: relative; }
        .image { display: block; max-width: 100%; height: auto; }
        .overlay { position: absolute; top: 0; left: 0; width: 50%; overflow: hidden; }
        .slider { position: absolute; width: 100%; height: 100%; opacity: 0; cursor: ew-resize; z-index: 10; }
        .slider-handle { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; background: #e94560; border-radius: 50%; z-index: 5; pointer-events: none; }
        .slider-labels { display: flex; justify-content: space-between; margin-top: 10px; color: #888; }
        footer { text-align: center; padding: 20px; color: #666; }
        .lut-info { margin-top: 20px; }
        .processing-time { margin-top: 20px; text-align: center; }"""
        else:
            return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; min-height: 100vh; }
        .container { max-width: 1400px; margin: 0 auto; padding: 40px 20px; }
        header { text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 2px solid #ddd; }
        header h1 { font-size: 2.5em; color: #2c3e50; margin-bottom: 10px; }
        .timestamp { color: #666; font-size: 0.9em; }
        section { background: #fff; border-radius: 12px; padding: 30px; margin-bottom: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        section h2 { color: #2c3e50; margin-bottom: 20px; font-size: 1.8em; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .stat-card { background: #f9f9f9; border-radius: 8px; padding: 20px; }
        .stat-card h3 { color: #2c3e50; margin-bottom: 15px; }
        .stats-table { width: 100%; border-collapse: collapse; }
        .stats-table td { padding: 8px; border-bottom: 1px solid #eee; }
        .stats-table td:first-child { color: #666; }
        .image-wrapper { text-align: center; }
        .chart-image { max-width: 100%; border-radius: 8px; }
        .slider-container { position: relative; display: inline-block; }
        .slider-wrapper { position: relative; overflow: hidden; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .image-container { position: relative; }
        .image { display: block; max-width: 100%; height: auto; }
        .overlay { position: absolute; top: 0; left: 0; width: 50%; overflow: hidden; }
        .slider { position: absolute; width: 100%; height: 100%; opacity: 0; cursor: ew-resize; z-index: 10; }
        .slider-handle { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 40px; height: 40px; background: #3498db; border-radius: 50%; z-index: 5; pointer-events: none; }
        .slider-labels { display: flex; justify-content: space-between; margin-top: 10px; color: #666; }
        footer { text-align: center; padding: 20px; color: #999; }
        .lut-info { margin-top: 20px; }
        .processing-time { margin-top: 20px; text-align: center; }"""
    
    def _get_javascript(self) -> str:
        return """
        document.addEventListener('DOMContentLoaded', function() {
            const slider = document.getElementById('comparisonSlider');
            const handle = document.getElementById('sliderHandle');
            const overlay = document.querySelector('.overlay');
            
            if (slider && overlay && handle) {
                slider.addEventListener('input', function() {
                    const value = this.value + '%';
                    overlay.style.width = value;
                    handle.style.left = value;
                });
            }
        });"""

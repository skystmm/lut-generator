"""
HTML 报告模块单元测试
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
import sys
import tempfile
import shutil
import json

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from html_report import HTMLReportGenerator, ReportConfig, ReportData, ReportResult


class TestReportConfig:
    """测试 ReportConfig"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = ReportConfig()
        assert config.title == "LUT 处理报告"
        assert config.include_slider is True
        assert config.include_histogram is True
        assert config.include_gamut is True
        assert config.include_statistics is True
        assert config.theme == 'dark'
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = ReportConfig(
            title="Custom Report",
            include_slider=False,
            theme='light'
        )
        assert config.title == "Custom Report"
        assert config.include_slider is False
        assert config.theme == 'light'
    
    def test_valid_themes(self):
        """测试有效主题"""
        for theme in ['dark', 'light']:
            config = ReportConfig(theme=theme)
            assert config.validate() is True
    
    def test_invalid_theme(self):
        """测试无效主题"""
        with pytest.raises(ValueError):
            config = ReportConfig(theme='invalid')
            config.validate()


class TestReportData:
    """测试 ReportData"""
    
    def test_minimal_data(self):
        """测试最小数据"""
        data = ReportData(
            original_image="/path/to/original.png",
            processed_image="/path/to/processed.png"
        )
        
        assert data.original_image == "/path/to/original.png"
        assert data.processed_image == "/path/to/processed.png"
        assert data.generated_at is not None
    
    def test_full_data(self):
        """测试完整数据"""
        data = ReportData(
            original_image="/path/to/original.png",
            processed_image="/path/to/processed.png",
            comparison_image="/path/to/comparison.png",
            statistics={'brightness': 128},
            lut_info={'grid_size': 33},
            processing_time=2.5
        )
        
        assert data.comparison_image == "/path/to/comparison.png"
        assert data.statistics == {'brightness': 128}
        assert data.lut_info == {'grid_size': 33}
        assert data.processing_time == 2.5


class TestHTMLReportGenerator:
    """测试 HTMLReportGenerator"""
    
    @pytest.fixture
    def generator(self):
        """创建报告生成器"""
        config = ReportConfig()
        return HTMLReportGenerator(config)
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    @pytest.fixture
    def sample_images(self, temp_dir):
        """创建样本图像"""
        # 创建原图
        original = np.random.randint(0, 256, (400, 600, 3), dtype=np.uint8)
        processed = np.random.randint(50, 200, (400, 600, 3), dtype=np.uint8)
        
        original_path = Path(temp_dir) / "original.png"
        processed_path = Path(temp_dir) / "processed.png"
        
        cv2.imwrite(str(original_path), cv2.cvtColor(original, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(processed_path), cv2.cvtColor(processed, cv2.COLOR_RGB2BGR))
        
        return original_path, processed_path
    
    def test_init(self, generator):
        """测试初始化"""
        assert generator is not None
        assert generator.config is not None
    
    def test_generate_minimal_report(self, generator, temp_dir):
        """测试生成最小报告"""
        report_data = ReportData(
            original_image=str(Path(temp_dir) / "original.png"),
            processed_image=str(Path(temp_dir) / "processed.png"
        ))
        
        # 创建空文件（用于测试）
        Path(temp_dir, "original.png").touch()
        Path(temp_dir, "processed.png").touch()
        
        output_path = Path(temp_dir) / "report.html"
        
        result = generator.generate(report_data, output_path)
        
        assert isinstance(result, ReportResult)
        assert result.success is True
        assert Path(output_path).exists()
        assert result.file_size > 0
        assert result.generation_time >= 0
    
    def test_generate_full_report(self, generator, sample_images, temp_dir):
        """测试生成完整报告"""
        original, processed = sample_images
        
        # 创建对比图
        comparison = np.hstack([
            cv2.imread(str(original)),
            cv2.imread(str(processed))
        ])
        comparison_path = Path(temp_dir) / "comparison.png"
        cv2.imwrite(str(comparison_path), comparison)
        
        report_data = ReportData(
            original_image=str(original),
            processed_image=str(processed),
            comparison_image=str(comparison_path),
            statistics={
                'original': {'brightness': 128.5, 'mean_rgb': [120, 130, 140]},
                'processed': {'brightness': 135.2, 'mean_rgb': [125, 135, 145]},
                'difference': {'mean_diff': 15.3, 'max_diff': 85.2},
                'brightness_change': 5.2
            },
            lut_info={
                'lut_grid_size': 33,
                'interpolation': 'trilinear',
                'input_colorspace': 'sRGB'
            },
            processing_time=2.5
        )
        
        output_path = Path(temp_dir) / "report_full.html"
        
        result = generator.generate(report_data, output_path)
        
        assert result.success is True
        assert Path(output_path).exists()
        assert result.file_size > 1000  # 完整报告应该较大
    
    def test_generate_from_paths(self, generator, sample_images, temp_dir):
        """测试从路径生成报告"""
        original, processed = sample_images
        
        output_path = Path(temp_dir) / "report_paths.html"
        
        result = generator.generate_from_paths(
            original,
            processed,
            output_path,
            statistics={'test': 'data'},
            lut_info={'grid': 33},
            processing_time=1.5
        )
        
        assert result.success is True
        assert Path(output_path).exists()
    
    def test_html_content_structure(self, generator, sample_images, temp_dir):
        """测试 HTML 内容结构"""
        original, processed = sample_images
        
        output_path = Path(temp_dir) / "report_structure.html"
        
        result = generator.generate_from_paths(original, processed, output_path)
        
        assert result.success is True
        
        # 读取并验证 HTML 内容
        with open(output_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 检查基本结构
        assert '<!DOCTYPE html>' in html_content
        assert '<html' in html_content
        assert '<head>' in html_content
        assert '<body>' in html_content
        assert '</html>' in html_content
        
        # 检查标题
        assert 'LUT 处理报告' in html_content
        
        # 检查 CSS
        assert '<style>' in html_content
        assert '</style>' in html_content
        
        # 检查 JavaScript
        assert '<script>' in html_content
        assert '</script>' in html_content
    
    def test_dark_theme(self, sample_images, temp_dir):
        """测试暗色主题"""
        original, processed = sample_images
        
        config = ReportConfig(theme='dark')
        generator = HTMLReportGenerator(config)
        
        output_path = Path(temp_dir) / "report_dark.html"
        
        result = generator.generate_from_paths(original, processed, output_path)
        
        assert result.success is True
        
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '#1a1a2e' in content or '#16213e' in content  # 暗色主题颜色
    
    def test_light_theme(self, sample_images, temp_dir):
        """测试亮色主题"""
        original, processed = sample_images
        
        config = ReportConfig(theme='light')
        generator = HTMLReportGenerator(config)
        
        output_path = Path(temp_dir) / "report_light.html"
        
        result = generator.generate_from_paths(original, processed, output_path)
        
        assert result.success is True
        
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '#f5f5f5' in content  # 亮色主题背景
    
    def test_no_slider(self, sample_images, temp_dir):
        """测试不包含滑块"""
        original, processed = sample_images
        
        config = ReportConfig(include_slider=False)
        generator = HTMLReportGenerator(config)
        
        output_path = Path(temp_dir) / "report_no_slider.html"
        
        result = generator.generate_from_paths(original, processed, output_path)
        
        assert result.success is True
        
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'slider-container' not in content
    
    def test_no_statistics(self, sample_images, temp_dir):
        """测试不包含统计"""
        original, processed = sample_images
        
        config = ReportConfig(include_statistics=False)
        generator = HTMLReportGenerator(config)
        
        output_path = Path(temp_dir) / "report_no_stats.html"
        
        result = generator.generate_from_paths(original, processed, output_path)
        
        assert result.success is True
        
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'statistics-section' not in content
    
    def test_image_to_base64(self, generator, sample_images):
        """测试图像转 base64"""
        original, _ = sample_images
        
        base64_str = generator._image_to_base64(str(original))
        
        assert base64_str is not None
        assert len(base64_str) > 0
        # 验证是有效的 base64
        import base64
        decoded = base64.b64decode(base64_str)
        assert len(decoded) > 0
    
    def test_image_to_base64_nonexistent(self, generator):
        """测试不存在的图像转 base64"""
        result = generator._image_to_base64("/nonexistent/path.png")
        assert result == ""
    
    def test_output_directory_creation(self, generator, sample_images, temp_dir):
        """测试输出目录自动创建"""
        original, processed = sample_images
        
        output_path = Path(temp_dir) / "subdir" / "nested" / "report.html"
        
        result = generator.generate_from_paths(original, processed, output_path)
        
        assert result.success is True
        assert Path(output_path).exists()


class TestConvenienceFunction:
    """测试便捷函数"""
    
    def test_generate_html_report(self, temp_dir):
        """测试便捷函数"""
        from html_report import generate_html_report
        
        # 创建测试图像
        original = np.random.randint(0, 256, (400, 600, 3), dtype=np.uint8)
        processed = np.random.randint(50, 200, (400, 600, 3), dtype=np.uint8)
        
        original_path = Path(temp_dir) / "original.png"
        processed_path = Path(temp_dir) / "processed.png"
        
        cv2.imwrite(str(original_path), cv2.cvtColor(original, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(processed_path), cv2.cvtColor(processed, cv2.COLOR_RGB2BGR))
        
        output_path = Path(temp_dir) / "report.html"
        
        result = generate_html_report(
            original_path,
            processed_path,
            output_path,
            statistics={'test': 'data'},
            theme='dark'
        )
        
        assert result.success is True
        assert Path(output_path).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

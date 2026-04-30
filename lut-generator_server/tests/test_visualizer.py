"""
可视化模块单元测试
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
import sys
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from visualizer import ColorVisualizer, VisualizationConfig, VisualizationResult


class TestVisualizationConfig:
    """测试 VisualizationConfig"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = VisualizationConfig()
        assert config.width == 1200
        assert config.height == 800
        assert config.show_grid is True
        assert config.alpha == 0.7
    
    def test_custom_colors(self):
        """测试自定义颜色"""
        custom_colors = {
            'red': (255, 0, 0),
            'custom': (100, 150, 200)
        }
        config = VisualizationConfig(colors=custom_colors)
        assert config.colors['red'] == (255, 0, 0)
        assert config.colors['custom'] == (100, 150, 200)
    
    def test_invalid_dimensions(self):
        """测试无效尺寸"""
        with pytest.raises(ValueError):
            config = VisualizationConfig(width=0)
            config.validate()
        
        with pytest.raises(ValueError):
            config = VisualizationConfig(height=-100)
            config.validate()
    
    def test_invalid_alpha(self):
        """测试无效透明度"""
        with pytest.raises(ValueError):
            config = VisualizationConfig(alpha=1.5)
            config.validate()


class TestColorVisualizer:
    """测试 ColorVisualizer"""
    
    @pytest.fixture
    def visualizer(self):
        """创建可视化工具"""
        config = VisualizationConfig(width=800, height=600)
        return ColorVisualizer(config)
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    @pytest.fixture
    def sample_image(self, temp_dir):
        """创建样本图像"""
        # 创建彩色渐变测试图
        image = np.zeros((400, 600, 3), dtype=np.uint8)
        
        # R 渐变
        image[:, :, 0] = np.tile(np.linspace(0, 255, 600), (400, 1)).astype(np.uint8)
        # G 渐变
        image[:, :, 1] = np.tile(np.linspace(0, 255, 400).reshape(-1, 1), (1, 600)).astype(np.uint8)
        # B 固定
        image[:, :, 2] = 128
        
        path = Path(temp_dir) / "test_image.png"
        cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        return path
    
    def test_init(self, visualizer):
        """测试初始化"""
        assert visualizer is not None
        assert visualizer.config is not None
    
    def test_plot_histogram(self, visualizer, sample_image, temp_dir):
        """测试绘制直方图"""
        output_path = Path(temp_dir) / "histogram.png"
        
        result = visualizer.plot_histogram(sample_image, output_path)
        
        assert isinstance(result, VisualizationResult)
        assert result.success is True
        assert Path(output_path).exists()
        assert result.viz_type == 'histogram'
        assert result.output_size[0] == 800
        assert result.output_size[1] == 600
    
    def test_plot_histogram_with_title(self, visualizer, sample_image, temp_dir):
        """测试带标题的直方图"""
        output_path = Path(temp_dir) / "histogram_title.png"
        
        result = visualizer.plot_histogram(
            sample_image,
            output_path,
            title="Custom Histogram Title"
        )
        
        assert result.success is True
        assert Path(output_path).exists()
    
    def test_plot_histogram_combined(self, visualizer, sample_image, temp_dir):
        """测试合并直方图"""
        output_path = Path(temp_dir) / "histogram_combined.png"
        
        result = visualizer.plot_histogram(
            sample_image,
            output_path,
            show_combined=True
        )
        
        assert result.success is True
    
    def test_plot_histogram_separate(self, visualizer, sample_image, temp_dir):
        """测试分开通道直方图"""
        output_path = Path(temp_dir) / "histogram_separate.png"
        
        result = visualizer.plot_histogram(
            sample_image,
            output_path,
            show_combined=False
        )
        
        assert result.success is True
    
    def test_plot_gamut(self, visualizer, sample_image, temp_dir):
        """测试绘制色域图"""
        output_path = Path(temp_dir) / "gamut.png"
        
        result = visualizer.plot_gamut(sample_image, output_path)
        
        assert result.success is True
        assert Path(output_path).exists()
        assert result.viz_type == 'gamut'
    
    def test_plot_gamut_with_title(self, visualizer, sample_image, temp_dir):
        """测试带标题的色域图"""
        output_path = Path(temp_dir) / "gamut_title.png"
        
        result = visualizer.plot_gamut(
            sample_image,
            output_path,
            title="Custom Gamut Title"
        )
        
        assert result.success is True
    
    def test_plot_gamut_max_points(self, visualizer, sample_image, temp_dir):
        """测试色域图最大采样点"""
        output_path = Path(temp_dir) / "gamut_sampled.png"
        
        result = visualizer.plot_gamut(
            sample_image,
            output_path,
            max_points=10000
        )
        
        assert result.success is True
    
    def test_invalid_image_path(self, visualizer, temp_dir):
        """测试无效图像路径"""
        output_path = Path(temp_dir) / "output.png"
        
        result = visualizer.plot_histogram(
            Path(temp_dir) / "nonexistent.png",
            output_path
        )
        
        assert result.success is False
        assert result.error_message is not None
    
    def test_histogram_comparison(self, visualizer, temp_dir):
        """测试直方图对比"""
        # 创建两张不同的图像
        image1 = np.random.randint(0, 256, (400, 600, 3), dtype=np.uint8)
        image2 = np.random.randint(50, 200, (400, 600, 3), dtype=np.uint8)
        
        path1 = Path(temp_dir) / "image1.png"
        path2 = Path(temp_dir) / "image2.png"
        
        cv2.imwrite(str(path1), cv2.cvtColor(image1, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(path2), cv2.cvtColor(image2, cv2.COLOR_RGB2BGR))
        
        output_path = Path(temp_dir) / "histogram_comparison.png"
        
        result = visualizer.plot_histogram_comparison(path1, path2, output_path)
        
        assert result.success is True
        assert Path(output_path).exists()
        assert result.viz_type == 'histogram_comparison'
    
    def test_gamut_comparison(self, visualizer, temp_dir):
        """测试色域图对比"""
        # 创建两张不同的图像
        image1 = np.random.randint(0, 256, (400, 600, 3), dtype=np.uint8)
        image2 = np.random.randint(50, 200, (400, 600, 3), dtype=np.uint8)
        
        path1 = Path(temp_dir) / "image1.png"
        path2 = Path(temp_dir) / "image2.png"
        
        cv2.imwrite(str(path1), cv2.cvtColor(image1, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(path2), cv2.cvtColor(image2, cv2.COLOR_RGB2BGR))
        
        output_path = Path(temp_dir) / "gamut_comparison.png"
        
        result = visualizer.plot_gamut_comparison(path1, path2, output_path)
        
        assert result.success is True
        assert Path(output_path).exists()
        assert result.viz_type == 'gamut_comparison'
    
    def test_chart_area_calculation(self, visualizer):
        """测试图表区域计算"""
        canvas = np.zeros((600, 800, 3), dtype=np.uint8)
        
        area = visualizer._get_chart_area(canvas)
        
        assert len(area) == 4
        assert area[0] == 50  # x_offset
        assert area[1] == 60  # y_offset
        assert area[2] > 0    # width
        assert area[3] > 0    # height
    
    def test_grid_drawing(self, visualizer):
        """测试网格绘制"""
        canvas = np.zeros((600, 800, 3), dtype=np.uint8)
        
        # 不应抛出异常
        visualizer._draw_grid(canvas, 50, 60, 700, 490)
        
        # 检查是否绘制了线条（至少有一些非零像素）
        assert np.any(canvas > 0)


class TestConvenienceFunction:
    """测试便捷函数"""
    
    def test_visualize_color_distribution(self, temp_dir):
        """测试便捷函数"""
        from visualizer import visualize_color_distribution
        
        # 创建测试图像
        image = np.random.randint(0, 256, (400, 600, 3), dtype=np.uint8)
        input_path = Path(temp_dir) / "input.png"
        cv2.imwrite(str(input_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        
        results = visualize_color_distribution(
            input_path,
            temp_dir,
            width=800,
            height=600
        )
        
        assert isinstance(results, list)
        assert len(results) == 2  # histogram + gamut
        
        for result in results:
            assert result.success is True
            assert Path(result.output_path).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

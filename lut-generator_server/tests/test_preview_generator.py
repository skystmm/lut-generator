"""
预览生成模块单元测试
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
import sys
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from preview_generator import PreviewGenerator, ComparisonConfig, PreviewResult
from lut_applier import LUTApplier
from lut3d_generator import LUT3DGenerator, LUT3DConfig
from color_analyzer import ColorStatistics


class TestComparisonConfig:
    """测试 ComparisonConfig"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = ComparisonConfig()
        assert config.mode == 'side_by_side'
        assert config.output_width == 1920
        assert config.add_labels is True
    
    def test_valid_modes(self):
        """测试有效模式"""
        for mode in ['side_by_side', 'slider', 'blend', 'difference']:
            config = ComparisonConfig(mode=mode)
            assert config.validate() is True
    
    def test_invalid_mode(self):
        """测试无效模式"""
        with pytest.raises(ValueError):
            config = ComparisonConfig(mode='invalid')
            config.validate()
    
    def test_invalid_slider_position(self):
        """测试无效滑块位置"""
        with pytest.raises(ValueError):
            config = ComparisonConfig(mode='slider', slider_position=1.5)
            config.validate()


class TestPreviewGenerator:
    """测试 PreviewGenerator"""
    
    @pytest.fixture
    def sample_lut_generator(self):
        """创建样本 LUT 生成器"""
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        
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
        
        generator.generate_from_stats(source_stats, target_stats)
        return generator
    
    @pytest.fixture
    def sample_applier(self, sample_lut_generator):
        """创建样本应用器"""
        return LUTApplier(sample_lut_generator)
    
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
        original = np.zeros((200, 300, 3), dtype=np.uint8)
        original[:, :] = [100, 150, 200]  # 蓝色调
        
        # 创建处理后图像（模拟）
        processed = np.zeros((200, 300, 3), dtype=np.uint8)
        processed[:, :] = [120, 140, 180]  # 略不同的蓝色调
        
        original_path = Path(temp_dir) / "original.png"
        processed_path = Path(temp_dir) / "processed.png"
        
        cv2.imwrite(str(original_path), cv2.cvtColor(original, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(processed_path), cv2.cvtColor(processed, cv2.COLOR_RGB2BGR))
        
        return original_path, processed_path
    
    def test_init(self, sample_applier):
        """测试初始化"""
        generator = PreviewGenerator(sample_applier)
        assert generator is not None
        assert generator.lut_applier is not None
    
    def test_generate_side_by_side(self, sample_applier, sample_images, temp_dir):
        """测试并排对比图生成"""
        original, processed = sample_images
        output_path = Path(temp_dir) / "comparison_sbs.png"
        
        config = ComparisonConfig(mode='side_by_side')
        generator = PreviewGenerator(sample_applier)
        
        result = generator.generate_comparison(original, processed, output_path, config)
        
        assert isinstance(result, PreviewResult)
        assert result.success is True
        assert Path(output_path).exists()
        assert result.mode == 'side_by_side'
        assert result.output_size[0] > 0
        assert result.output_size[1] > 0
        assert result.statistics is not None
    
    def test_generate_slider(self, sample_applier, sample_images, temp_dir):
        """测试滑块对比图生成"""
        original, processed = sample_images
        output_path = Path(temp_dir) / "comparison_slider.png"
        
        config = ComparisonConfig(mode='slider', slider_position=0.5)
        generator = PreviewGenerator(sample_applier)
        
        result = generator.generate_comparison(original, processed, output_path, config)
        
        assert result.success is True
        assert Path(output_path).exists()
        assert result.mode == 'slider'
    
    def test_generate_blend(self, sample_applier, sample_images, temp_dir):
        """测试混合对比图生成"""
        original, processed = sample_images
        output_path = Path(temp_dir) / "comparison_blend.png"
        
        config = ComparisonConfig(mode='blend')
        generator = PreviewGenerator(sample_applier)
        
        result = generator.generate_comparison(original, processed, output_path, config)
        
        assert result.success is True
        assert Path(output_path).exists()
        assert result.mode == 'blend'
    
    def test_generate_difference(self, sample_applier, sample_images, temp_dir):
        """测试差异对比图生成"""
        original, processed = sample_images
        output_path = Path(temp_dir) / "comparison_diff.png"
        
        config = ComparisonConfig(mode='difference')
        generator = PreviewGenerator(sample_applier)
        
        result = generator.generate_comparison(original, processed, output_path, config)
        
        assert result.success is True
        assert Path(output_path).exists()
        assert result.mode == 'difference'
    
    def test_generate_from_image(self, sample_applier, temp_dir):
        """测试从单张图像生成对比图"""
        # 创建测试图像
        image = np.random.randint(0, 256, (200, 300, 3), dtype=np.uint8)
        input_path = Path(temp_dir) / "input.png"
        cv2.imwrite(str(input_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        
        generator = PreviewGenerator(sample_applier)
        result = generator.generate_from_image(input_path, temp_dir)
        
        assert result.success is True
        assert Path(result.output_path).exists()
    
    def test_custom_border_config(self, sample_applier, sample_images, temp_dir):
        """测试自定义边框配置"""
        original, processed = sample_images
        output_path = Path(temp_dir) / "comparison_custom.png"
        
        config = ComparisonConfig(
            mode='side_by_side',
            border_width=5,
            border_color=(255, 0, 0),
            label_scale=1.5,
            label_color=(0, 255, 0)
        )
        generator = PreviewGenerator(sample_applier)
        
        result = generator.generate_comparison(original, processed, output_path, config)
        
        assert result.success is True
        assert Path(output_path).exists()
    
    def test_invalid_input_path(self, sample_applier, temp_dir):
        """测试无效输入路径"""
        generator = PreviewGenerator(sample_applier)
        
        result = generator.generate_comparison(
            Path(temp_dir) / "nonexistent.png",
            Path(temp_dir) / "nonexistent2.png",
            Path(temp_dir) / "output.png"
        )
        
        assert result.success is False
        assert result.error_message is not None
    
    def test_statistics_calculation(self, sample_applier, sample_images):
        """测试统计信息计算"""
        original, processed = sample_images
        original_img = cv2.imread(str(original))
        processed_img = cv2.imread(str(processed))
        original_rgb = cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB)
        processed_rgb = cv2.cvtColor(processed_img, cv2.COLOR_BGR2RGB)
        
        generator = PreviewGenerator(sample_applier)
        stats = generator._calculate_statistics(original_rgb, processed_rgb)
        
        assert 'original' in stats
        assert 'processed' in stats
        assert 'difference' in stats
        assert 'brightness_change' in stats
        assert 'mean_rgb' in stats['original']
        assert 'mean_diff' in stats['difference']


class TestConvenienceFunction:
    """测试便捷函数"""
    
    @pytest.fixture
    def sample_applier(self):
        """创建样本应用器"""
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        
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
        
        generator.generate_from_stats(source_stats, target_stats)
        return LUTApplier(generator)
    
    def test_generate_preview(self, sample_applier, temp_dir):
        """测试便捷函数"""
        # 创建测试图像
        image = np.random.randint(0, 256, (200, 300, 3), dtype=np.uint8)
        input_path = Path(temp_dir) / "input.png"
        cv2.imwrite(str(input_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        
        from preview_generator import generate_preview
        
        result = generate_preview(
            sample_applier,
            input_path,
            temp_dir,
            mode='side_by_side'
        )
        
        assert result.success is True
        assert Path(result.output_path).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

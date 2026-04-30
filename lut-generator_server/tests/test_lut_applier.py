"""
LUT 应用模块单元测试
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
import sys
import tempfile
import shutil

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from lut_applier import LUTApplier, ApplyConfig, ApplyResult
from lut3d_generator import LUT3DGenerator, LUT3DConfig
from color_analyzer import ColorStatistics


class TestApplyConfig:
    """测试 ApplyConfig"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = ApplyConfig()
        assert config.quality == 95
        assert config.output_format == 'png'
        assert config.keep_original_size is True
    
    def test_valid_config(self):
        """测试有效配置"""
        config = ApplyConfig(quality=80, output_format='jpg')
        assert config.validate() is True
    
    def test_invalid_quality(self):
        """测试无效质量值"""
        with pytest.raises(ValueError):
            config = ApplyConfig(quality=150)
            config.validate()
    
    def test_invalid_format(self):
        """测试无效格式"""
        with pytest.raises(ValueError):
            config = ApplyConfig(output_format='bmp')
            config.validate()


class TestLUTApplier:
    """测试 LUTApplier"""
    
    @pytest.fixture
    def sample_lut_generator(self):
        """创建样本 LUT 生成器"""
        config = LUT3DConfig(grid_size=17)  # 小网格加速测试
        generator = LUT3DGenerator(config)
        
        # 创建模拟统计信息
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
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    @pytest.fixture
    def sample_image(self, temp_dir):
        """创建样本图像"""
        # 创建渐变测试图
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        
        # R 渐变
        r_grad = np.linspace(0, 255, 100, dtype=np.uint8)
        image[:, :, 0] = np.tile(r_grad, (100, 1))
        # G 渐变
        g_grad = np.linspace(0, 255, 100, dtype=np.uint8)
        image[:, :, 1] = np.tile(g_grad.reshape(-1, 1), (1, 100))
        # B 固定
        image[:, :, 2] = 128
        
        path = Path(temp_dir) / "test_image.png"
        cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        return path
    
    def test_init_with_generated_lut(self, sample_lut_generator):
        """测试使用已生成 LUT 初始化"""
        applier = LUTApplier(sample_lut_generator)
        assert applier is not None
        assert applier.lut_generator.lut_data is not None
    
    def test_init_without_lut(self):
        """测试未生成 LUT 时初始化应失败"""
        config = LUT3DConfig(grid_size=17)
        generator = LUT3DGenerator(config)
        
        with pytest.raises(ValueError, match="LUT data not generated"):
            LUTApplier(generator)
    
    def test_apply_to_image(self, sample_lut_generator, sample_image):
        """测试应用 LUT 到图像"""
        applier = LUTApplier(sample_lut_generator)
        
        # 加载图像
        image = cv2.imread(str(sample_image))
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # 应用 LUT
        result = applier.apply_to_image(image_rgb)
        
        assert result is not None
        assert result.shape == image_rgb.shape
        assert result.dtype == np.uint8
        assert result.min() >= 0
        assert result.max() <= 255
    
    def test_apply_to_file(self, sample_lut_generator, sample_image, temp_dir):
        """测试应用 LUT 到文件"""
        applier = LUTApplier(sample_lut_generator)
        output_path = Path(temp_dir) / "output.png"
        
        result = applier.apply_to_file(sample_image, output_path)
        
        assert isinstance(result, ApplyResult)
        assert result.success is True
        assert Path(output_path).exists()
        assert result.output_size[0] > 0
        assert result.output_size[1] > 0
        assert result.processing_time >= 0
    
    def test_apply_to_file_with_config(self, sample_lut_generator, sample_image, temp_dir):
        """测试带配置应用 LUT"""
        applier = LUTApplier(sample_lut_generator)
        config = ApplyConfig(quality=80, output_format='jpg')
        output_path = Path(temp_dir) / "output.jpg"
        
        result = applier.apply_to_file(sample_image, output_path, config)
        
        assert result.success is True
        assert Path(output_path).exists()
        assert output_path.suffix == '.jpg'
    
    def test_apply_to_file_invalid_input(self, sample_lut_generator, temp_dir):
        """测试无效输入文件"""
        applier = LUTApplier(sample_lut_generator)
        output_path = Path(temp_dir) / "output.png"
        
        result = applier.apply_to_file(
            Path(temp_dir) / "nonexistent.png",
            output_path
        )
        
        assert result.success is False
        assert result.error_message is not None
    
    def test_progress_callback(self, sample_lut_generator, sample_image, temp_dir):
        """测试进度回调"""
        applier = LUTApplier(sample_lut_generator)
        output_path = Path(temp_dir) / "output.png"
        
        progress_values = []
        
        def callback(progress):
            progress_values.append(progress)
        
        result = applier.apply_to_file(
            sample_image,
            output_path,
            progress_callback=callback
        )
        
        assert result.success is True
        assert len(progress_values) > 0
        assert progress_values[0] == 0.0
        assert progress_values[-1] >= 0.9  # 最后进度至少 0.9
    
    def test_batch_apply(self, sample_lut_generator, temp_dir):
        """测试批量应用"""
        # 创建多个测试图像
        input_paths = []
        for i in range(3):
            image = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)
            path = Path(temp_dir) / f"input_{i}.png"
            cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            input_paths.append(path)
        
        output_dir = Path(temp_dir) / "output"
        applier = LUTApplier(sample_lut_generator)
        
        results = applier.apply_batch(input_paths, output_dir)
        
        assert len(results) == 3
        assert all(r.success for r in results)
        assert output_dir.exists()
        
        # 检查输出文件
        output_files = list(output_dir.glob("*.png"))
        assert len(output_files) == 3


class TestCubeFileLoading:
    """测试 CUBE 文件加载"""
    
    @pytest.fixture
    def temp_dir_local(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        try:
            yield temp
        finally:
            try:
                shutil.rmtree(temp)
            except FileNotFoundError:
                pass  # 目录可能已被删除
    
    @pytest.fixture
    def sample_cube_file(self, temp_dir_local):
        """创建样本 CUBE 文件"""
        temp = temp_dir_local
        
        # 创建简单的 3x3x3 LUT
        cube_path = Path(temp) / "test.cube"
        
        with open(cube_path, 'w') as f:
            f.write("# Test LUT\n")
            f.write("LUT_3D_SIZE 3\n")
            
            # 写入 27 个 RGB 值
            for b in range(3):
                for g in range(3):
                    for r in range(3):
                        f.write(f"{r/2:.6f} {g/2:.6f} {b/2:.6f}\n")
        
        yield cube_path
        shutil.rmtree(temp)
    
    def test_load_cube_file(self, sample_cube_file):
        """测试加载 CUBE 文件"""
        lut_data = LUTApplier._load_cube_file(sample_cube_file, grid_size=3)
        
        assert lut_data is not None
        assert lut_data.shape == (3, 3, 3, 3)
        assert lut_data.dtype == np.float32


class TestConvenienceFunction:
    """测试便捷函数"""
    
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
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    def test_apply_lut_to_image(self, sample_lut_generator, temp_dir):
        """测试便捷函数"""
        # 创建测试图像
        image = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)
        input_path = Path(temp_dir) / "input.png"
        output_path = Path(temp_dir) / "output.png"
        
        cv2.imwrite(str(input_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        
        from lut_applier import apply_lut_to_image
        
        result = apply_lut_to_image(
            sample_lut_generator,
            input_path,
            output_path
        )
        
        assert result.success is True
        assert Path(output_path).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

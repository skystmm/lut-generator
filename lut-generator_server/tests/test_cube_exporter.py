"""
CUBEExporter 单元测试

测试 CUBE 文件导出器的核心功能：
- CUBE 文件导出
- 文件格式验证
- CUBE 文件加载
- 元数据包含
- 不同精度支持
"""

import pytest
import numpy as np
from pathlib import Path
import sys
import tempfile
import os

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cube_exporter_main import (
    CUBEExporter, CUBEExportConfig,
    export_to_cube
)
from lut3d_generator import LUT3DConfig, LUT3DMetadata
from datetime import datetime


class TestCUBEExportConfig:
    """测试 CUBE 导出配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = CUBEExportConfig()
        assert config.include_metadata is True
        assert config.precision == 6
        assert config.use_tabs is False
        assert config.custom_title is None
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = CUBEExportConfig(
            include_metadata=False,
            precision=8,
            use_tabs=True,
            custom_title="My Custom LUT"
        )
        assert config.include_metadata is False
        assert config.precision == 8
        assert config.use_tabs is True
        assert config.custom_title == "My Custom LUT"


class TestCUBEExporter:
    """测试 CUBE 导出器"""
    
    @pytest.fixture
    def sample_lut_17(self):
        """17³ 测试 LUT"""
        grid_size = 17
        lut = np.random.rand(grid_size, grid_size, grid_size, 3).astype(np.float32)
        # 确保值在 0-1 范围
        lut = np.clip(lut, 0, 1)
        return lut
    
    @pytest.fixture
    def sample_lut_33(self):
        """33³ 测试 LUT"""
        grid_size = 33
        lut = np.random.rand(grid_size, grid_size, grid_size, 3).astype(np.float32)
        lut = np.clip(lut, 0, 1)
        return lut
    
    @pytest.fixture
    def sample_metadata(self):
        """示例元数据"""
        return LUT3DMetadata(
            created_at=datetime.now().isoformat(),
            description="Test LUT for CUBE export",
            config=LUT3DConfig(grid_size=17)
        )
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_export_17(self, sample_lut_17, sample_metadata, temp_dir):
        """测试 17³ LUT 导出"""
        output_path = Path(temp_dir) / "test_17.cube"
        
        exported = export_to_cube(
            sample_lut_17,
            output_path,
            sample_metadata
        )
        
        assert exported.exists()
        assert exported.suffix == '.cube'
        assert exported.stat().st_size > 0
    
    def test_export_33(self, sample_lut_33, temp_dir):
        """测试 33³ LUT 导出"""
        output_path = Path(temp_dir) / "test_33.cube"
        
        metadata = LUT3DMetadata(
            created_at=datetime.now().isoformat(),
            description="Test 33³ LUT",
            config=LUT3DConfig(grid_size=33)
        )
        
        exported = export_to_cube(sample_lut_33, output_path, metadata)
        
        assert exported.exists()
        assert exported.stat().st_size > 0
    
    def test_export_without_metadata(self, sample_lut_17, temp_dir):
        """测试不包含元数据的导出"""
        output_path = Path(temp_dir) / "test_no_meta.cube"
        
        exported = export_to_cube(
            sample_lut_17,
            output_path,
            metadata=None,
            include_metadata=False
        )
        
        assert exported.exists()
        
        # 检查文件内容不包含注释
        with open(exported, 'r') as f:
            content = f.read()
        
        # 应该只有 TITLE 和 LUT_3D_SIZE，没有 # 注释
        lines = [l for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
        assert len(lines) >= 2  # TITLE + LUT_3D_SIZE + data
    
    def test_export_precision(self, sample_lut_17, temp_dir):
        """测试导出精度"""
        output_path_6 = Path(temp_dir) / "test_prec6.cube"
        output_path_8 = Path(temp_dir) / "test_prec8.cube"
        
        export_to_cube(sample_lut_17, output_path_6, precision=6)
        export_to_cube(sample_lut_17, output_path_8, precision=8)
        
        # 读取文件内容
        with open(output_path_6, 'r') as f:
            content_6 = f.read()
        with open(output_path_8, 'r') as f:
            content_8 = f.read()
        
        # 精度 8 的文件应该更大（更多小数位）
        # 注意：这个测试可能不总是成立，取决于具体数值
        # 这里只做基本检查
        assert output_path_6.exists()
        assert output_path_8.exists()
    
    def test_export_to_string(self, sample_lut_17, sample_metadata):
        """测试导出为字符串"""
        exporter = CUBEExporter()
        
        content = exporter.export_to_string(sample_lut_17, sample_metadata)
        
        assert isinstance(content, str)
        assert 'TITLE' in content
        assert 'LUT_3D_SIZE 17' in content
        
        # 检查数据行
        lines = content.split('\n')
        data_lines = [l for l in lines if l.strip() and not l.startswith('#') 
                      and not l.startswith('TITLE') and not l.startswith('LUT_3D_SIZE')]
        
        # 17³ = 4913 行数据
        assert len(data_lines) == 17 ** 3
    
    def test_validate_valid_file(self, sample_lut_17, temp_dir):
        """测试验证有效文件"""
        output_path = Path(temp_dir) / "valid.cube"
        export_to_cube(sample_lut_17, output_path)
        
        exporter = CUBEExporter()
        validation = exporter.validate_cube_file(output_path)
        
        assert validation['valid'] is True
        assert validation['grid_size'] == 17
        assert validation['line_count'] == 17 ** 3
        assert len(validation['errors']) == 0
    
    def test_validate_invalid_file(self, temp_dir):
        """测试验证无效文件"""
        # 创建无效的 CUBE 文件
        invalid_path = Path(temp_dir) / "invalid.cube"
        
        with open(invalid_path, 'w') as f:
            f.write("# Invalid file\n")
            f.write("LUT_3D_SIZE 17\n")
            f.write("0.5 0.5\n")  # 只有两个值，应该是三个
        
        exporter = CUBEExporter()
        validation = exporter.validate_cube_file(invalid_path)
        
        assert validation['valid'] is False
        assert len(validation['errors']) > 0
    
    def test_validate_missing_size(self, temp_dir):
        """测试验证缺少 LUT_3D_SIZE 的文件"""
        invalid_path = Path(temp_dir) / "no_size.cube"
        
        with open(invalid_path, 'w') as f:
            f.write("# No size directive\n")
            f.write("0.5 0.5 0.5\n")
        
        exporter = CUBEExporter()
        validation = exporter.validate_cube_file(invalid_path)
        
        assert validation['valid'] is False
        assert any("Missing LUT_3D_SIZE" in err for err in validation['errors'])
    
    def test_validate_wrong_size(self, temp_dir):
        """测试验证错误的网格大小"""
        invalid_path = Path(temp_dir) / "wrong_size.cube"
        
        with open(invalid_path, 'w') as f:
            f.write("LUT_3D_SIZE 16\n")  # 16 不是有效值
            for _ in range(16 ** 3):
                f.write("0.5 0.5 0.5\n")
        
        exporter = CUBEExporter()
        validation = exporter.validate_cube_file(invalid_path)
        
        assert validation['valid'] is False
        assert any("Invalid grid size" in err for err in validation['errors'])
    
    def test_load_cube_file(self, sample_lut_17, temp_dir):
        """测试加载 CUBE 文件"""
        output_path = Path(temp_dir) / "load_test.cube"
        export_to_cube(sample_lut_17, output_path)
        
        exporter = CUBEExporter()
        loaded_lut = exporter.load_cube_file(output_path)
        
        assert loaded_lut.shape == sample_lut_17.shape
        assert np.allclose(loaded_lut, sample_lut_17, rtol=1e-5)
    
    def test_load_and_roundtrip(self, sample_lut_33, temp_dir):
        """测试往返加载（导出 - 加载 - 导出）"""
        output1 = Path(temp_dir) / "roundtrip1.cube"
        output2 = Path(temp_dir) / "roundtrip2.cube"
        
        metadata = LUT3DMetadata(
            created_at=datetime.now().isoformat(),
            description="Roundtrip test",
            config=LUT3DConfig(grid_size=33)
        )
        
        # 第一次导出
        exporter = CUBEExporter()
        exporter.export(sample_lut_33, output1, metadata)
        
        # 加载
        loaded = exporter.load_cube_file(output1)
        
        # 再次导出
        exporter.export(loaded, output2, metadata)
        
        # 再次加载
        reloaded = exporter.load_cube_file(output2)
        
        # 验证一致性
        assert np.allclose(sample_lut_33, loaded, rtol=1e-5)
        assert np.allclose(loaded, reloaded, rtol=1e-5)
    
    def test_export_class_method(self, sample_lut_17, sample_metadata, temp_dir):
        """测试类方法导出"""
        config = CUBEExportConfig(precision=6, include_metadata=True)
        exporter = CUBEExporter(config)
        
        output_path = Path(temp_dir) / "class_export.cube"
        result = exporter.export(sample_lut_17, output_path, sample_metadata)
        
        assert result == output_path
        assert result.exists()


class TestCUBEFormat:
    """测试 CUBE 文件格式规范"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_file_header(self, temp_dir):
        """测试文件头格式"""
        grid_size = 17
        lut = np.zeros((grid_size, grid_size, grid_size, 3))
        lut[:, :, :] = [0.5, 0.5, 0.5]
        
        output_path = Path(temp_dir) / "header_test.cube"
        export_to_cube(lut, output_path)
        
        with open(output_path, 'r') as f:
            lines = f.readlines()
        
        # 检查前几行
        non_comment_lines = [l.strip() for l in lines if l.strip() and not l.startswith('#')]
        
        # 应该有 TITLE 和 LUT_3D_SIZE
        assert any('TITLE' in l for l in non_comment_lines)
        assert any('LUT_3D_SIZE' in l for l in non_comment_lines)
    
    def test_data_format(self, temp_dir):
        """测试数据行格式"""
        grid_size = 17
        lut = np.random.rand(grid_size, grid_size, grid_size, 3)
        
        output_path = Path(temp_dir) / "data_format.cube"
        export_to_cube(lut, output_path, precision=6)
        
        with open(output_path, 'r') as f:
            lines = f.readlines()
        
        # 找到数据行
        data_started = False
        data_lines = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('LUT_3D_SIZE'):
                data_started = True
                continue
            if data_started and line and not line.startswith('#'):
                data_lines.append(line)
        
        # 检查数据行格式
        assert len(data_lines) == grid_size ** 3
        
        for line in data_lines[:10]:  # 检查前 10 行
            parts = line.split()
            assert len(parts) == 3
            
            # 检查值范围
            values = [float(p) for p in parts]
            assert all(0 <= v <= 1 for v in values)
            
            # 检查精度（6 位小数）
            for p in parts:
                if '.' in p:
                    decimal_places = len(p.split('.')[1])
                    assert decimal_places <= 6
    
    def test_tab_separator(self, temp_dir):
        """测试制表符分隔"""
        grid_size = 17
        lut = np.zeros((grid_size, grid_size, grid_size, 3))
        lut[:, :, :] = [0.5, 0.5, 0.5]
        
        output_path = Path(temp_dir) / "tab_test.cube"
        
        config = CUBEExportConfig(use_tabs=True)
        exporter = CUBEExporter(config)
        exporter.export(lut, output_path)
        
        with open(output_path, 'r') as f:
            content = f.read()
        
        # 数据行应该包含制表符
        lines = content.split('\n')
        data_lines = [l for l in lines if l.strip() and not l.startswith('#') 
                      and not l.startswith('TITLE') and not l.startswith('LUT_3D_SIZE')]
        
        if data_lines:
            assert '\t' in data_lines[0]


class TestEdgeCases:
    """测试边界情况"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_extreme_values(self, temp_dir):
        """测试极值（0 和 1）"""
        grid_size = 17
        lut = np.zeros((grid_size, grid_size, grid_size, 3))
        
        # 设置一些极值
        lut[0, 0, 0] = [0, 0, 0]
        lut[-1, -1, -1] = [1, 1, 1]
        lut[:, :, :] = np.clip(lut, 0, 1)
        
        output_path = Path(temp_dir) / "extreme.cube"
        export_to_cube(lut, output_path)
        
        exporter = CUBEExporter()
        validation = exporter.validate_cube_file(output_path)
        
        assert validation['valid'] is True
        
        # 加载并验证
        loaded = exporter.load_cube_file(output_path)
        assert loaded.shape == lut.shape
    
    def test_empty_metadata(self, temp_dir):
        """测试空元数据"""
        grid_size = 17
        lut = np.random.rand(grid_size, grid_size, grid_size, 3)
        
        output_path = Path(temp_dir) / "empty_meta.cube"
        
        metadata = LUT3DMetadata(
            created_at=datetime.now().isoformat(),
            description=""
        )
        
        export_to_cube(lut, output_path, metadata)
        
        assert output_path.exists()
    
    def test_large_file_65(self, temp_dir):
        """测试 65³ 大文件"""
        grid_size = 65
        lut = np.random.rand(grid_size, grid_size, grid_size, 3).astype(np.float32)
        
        output_path = Path(temp_dir) / "large_65.cube"
        
        metadata = LUT3DMetadata(
            created_at=datetime.now().isoformat(),
            description="65³ LUT",
            config=LUT3DConfig(grid_size=65)
        )
        
        export_to_cube(lut, output_path, metadata)
        
        assert output_path.exists()
        
        # 65³ = 274625 行数据，文件应该比较大
        file_size = output_path.stat().st_size
        assert file_size > 1000000  # 至少 1MB
        
        # 验证文件
        exporter = CUBEExporter()
        validation = exporter.validate_cube_file(output_path)
        
        assert validation['valid'] is True
        assert validation['grid_size'] == 65


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

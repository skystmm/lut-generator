"""
批量分析模块单元测试 - Test Batch Analyzer

测试覆盖：
- 目录扫描
- 单图分析（带异常处理）
- 批量分析（并行/串行）
- 结果聚合
- 文件保存
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import os
from typing import List

# 导入被测试模块
from batch_analyzer import (
    BatchAnalyzer, 
    ImageInfo, 
    BatchAnalysisResult,
    analyze_directory_batch
)
from color_analyzer import ColorAnalyzer, AnalysisResult, ColorStatistics


class TestImageInfo:
    """测试 ImageInfo 数据类"""
    
    def test_valid_image_info(self):
        """测试有效图片信息"""
        info = ImageInfo(
            path=Path('/test/image.jpg'),
            valid=True,
            analysis_result=None
        )
        
        assert info.valid is True
        assert info.error_message is None
        assert str(info.path) == '/test/image.jpg'
    
    def test_invalid_image_info(self):
        """测试无效图片信息"""
        info = ImageInfo(
            path=Path('/test/invalid.jpg'),
            valid=False,
            error_message='File not found'
        )
        
        assert info.valid is False
        assert info.error_message == 'File not found'
    
    def test_to_dict(self):
        """测试转换为字典"""
        info = ImageInfo(
            path=Path('/test/image.jpg'),
            valid=True,
            error_message=None
        )
        
        result = info.to_dict()
        assert result['path'] == '/test/image.jpg'
        assert result['valid'] is True
        assert 'error_message' not in result


class TestBatchAnalysisResult:
    """测试 BatchAnalysisResult 数据类"""
    
    def test_basic_stats(self):
        """测试基本统计"""
        result = BatchAnalysisResult(
            total_images=10,
            valid_images=8,
            failed_images=2
        )
        
        assert result.total_images == 10
        assert result.valid_images == 8
        assert result.failed_images == 2
    
    def test_get_valid_results_empty(self):
        """测试获取有效结果（空）"""
        result = BatchAnalysisResult(
            total_images=0,
            valid_images=0,
            failed_images=0,
            image_results=[]
        )
        
        valid = result.get_valid_results()
        assert len(valid) == 0
    
    def test_get_valid_paths(self):
        """测试获取有效路径"""
        results = [
            ImageInfo(path=Path('/test/1.jpg'), valid=True),
            ImageInfo(path=Path('/test/2.jpg'), valid=False, error_message='Error'),
            ImageInfo(path=Path('/test/3.jpg'), valid=True),
        ]
        
        batch_result = BatchAnalysisResult(
            total_images=3,
            valid_images=2,
            failed_images=1,
            image_results=results
        )
        
        paths = batch_result.get_valid_paths()
        assert len(paths) == 2
        assert Path('/test/1.jpg') in paths
        assert Path('/test/3.jpg') in paths
        assert Path('/test/2.jpg') not in paths


class TestBatchAnalyzer:
    """测试 BatchAnalyzer 类"""
    
    @pytest.fixture
    def analyzer(self):
        """创建分析器实例"""
        return BatchAnalyzer(use_colour=False, max_workers=2)
    
    @pytest.fixture
    def temp_image(self):
        """创建临时测试图片"""
        # 创建一个简单的测试图片
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            import cv2
            cv2.imwrite(f.name, img)
            temp_path = f.name
        
        yield Path(temp_path)
        
        # 清理
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def temp_directory(self, temp_image):
        """创建包含测试图片的临时目录"""
        temp_dir = tempfile.mkdtemp()
        
        # 复制图片到临时目录
        import shutil
        test_img_path = Path(temp_dir) / 'test1.jpg'
        shutil.copy(temp_image, test_img_path)
        
        # 创建第二张图片
        img2 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        test_img2_path = Path(temp_dir) / 'test2.jpg'
        import cv2
        cv2.imwrite(str(test_img2_path), img2)
        
        yield Path(temp_dir)
        
        # 清理
        import shutil
        shutil.rmtree(temp_dir)
    
    def test_scan_directory(self, analyzer, temp_directory):
        """测试目录扫描"""
        images = analyzer.scan_directory(temp_directory)
        
        assert len(images) == 2
        assert all(img.suffix.lower() in analyzer.SUPPORTED_FORMATS for img in images)
    
    def test_scan_directory_not_found(self, analyzer):
        """测试目录不存在"""
        with pytest.raises(FileNotFoundError):
            analyzer.scan_directory('/nonexistent/directory')
    
    def test_scan_directory_not_a_directory(self, analyzer, temp_image):
        """测试路径不是目录"""
        with pytest.raises(NotADirectoryError):
            analyzer.scan_directory(temp_image)
    
    def test_analyze_single_valid(self, analyzer, temp_image):
        """测试分析有效图片"""
        result = analyzer.analyze_single(temp_image)
        
        assert result.valid is True
        assert result.error_message is None
        assert result.analysis_result is not None
        assert isinstance(result.analysis_result, AnalysisResult)
    
    def test_analyze_single_not_found(self, analyzer):
        """测试分析不存在的图片"""
        result = analyzer.analyze_single('/nonexistent/image.jpg')
        
        assert result.valid is False
        assert result.error_message == 'File not found'
    
    def test_analyze_single_unsupported_format(self, analyzer):
        """测试分析不支持的格式"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'test')
            temp_path = f.name
        
        try:
            result = analyzer.analyze_single(temp_path)
            
            assert result.valid is False
            assert 'Unsupported format' in result.error_message
        finally:
            os.remove(temp_path)
    
    def test_analyze_batch_parallel(self, analyzer, temp_directory):
        """测试批量并行分析"""
        images = analyzer.scan_directory(temp_directory)
        result = analyzer.analyze_batch(images, parallel=True)
        
        assert result.total_images == 2
        assert result.valid_images == 2
        assert result.failed_images == 0
    
    def test_analyze_batch_serial(self, analyzer, temp_directory):
        """测试批量串行分析"""
        images = analyzer.scan_directory(temp_directory)
        result = analyzer.analyze_batch(images, parallel=False)
        
        assert result.total_images == 2
        assert result.valid_images == 2
        assert result.failed_images == 0
    
    def test_analyze_directory(self, analyzer, temp_directory):
        """测试分析整个目录"""
        result = analyzer.analyze_directory(temp_directory)
        
        assert result.total_images > 0
        assert result.valid_images == result.total_images
    
    def test_aggregate_statistics(self, analyzer, temp_directory):
        """测试统计聚合"""
        result = analyzer.analyze_directory(temp_directory)
        valid_results = result.get_valid_results()
        
        if len(valid_results) >= 2:
            aggregated = analyzer.aggregate_statistics(valid_results)
            
            assert 'mean' in aggregated
            assert 'std' in aggregated
            assert 'var' in aggregated
            assert len(aggregated['mean']) == 3  # L, a, b
            assert len(aggregated['std']) == 3
            assert len(aggregated['var']) == 3
    
    def test_aggregate_statistics_weighted(self, analyzer, temp_directory):
        """测试加权统计聚合"""
        result = analyzer.analyze_directory(temp_directory)
        valid_results = result.get_valid_results()
        
        if len(valid_results) >= 2:
            weights = [2.0, 1.0][:len(valid_results)]
            aggregated = analyzer.aggregate_statistics(valid_results, weights=weights)
            
            assert 'mean' in aggregated
            assert len(aggregated['mean']) == 3
    
    def test_save_results_json(self, analyzer, temp_directory, tmp_path):
        """测试保存结果为 JSON"""
        result = analyzer.analyze_directory(temp_directory)
        output_path = tmp_path / 'results.json'
        
        analyzer.save_results(result, output_path, format='json')
        
        assert output_path.exists()
        
        import json
        with open(output_path, 'r') as f:
            data = json.load(f)
        
        assert 'total_images' in data
        assert 'valid_images' in data
        assert 'image_results' in data
    
    def test_save_results_txt(self, analyzer, temp_directory, tmp_path):
        """测试保存结果为 TXT"""
        result = analyzer.analyze_directory(temp_directory)
        output_path = tmp_path / 'results.txt'
        
        analyzer.save_results(result, output_path, format='txt')
        
        assert output_path.exists()
        
        with open(output_path, 'r') as f:
            content = f.read()
        
        assert 'Total images' in content
        assert 'Valid images' in content


class TestAnalyzeDirectoryBatch:
    """测试便捷函数"""
    
    def test_analyze_directory_batch(self, temp_directory):
        """测试便捷函数"""
        result = analyze_directory_batch(temp_directory, max_workers=2, use_colour=False)
        
        assert isinstance(result, BatchAnalysisResult)
        assert result.total_images > 0
    
    @pytest.fixture
    def temp_directory(self):
        """创建临时目录包含测试图片"""
        temp_dir = tempfile.mkdtemp()
        
        # 创建测试图片
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        import cv2
        cv2.imwrite(str(Path(temp_dir) / 'test.jpg'), img)
        
        yield Path(temp_dir)
        
        # 清理
        import shutil
        shutil.rmtree(temp_dir)


class TestSupportedFormats:
    """测试支持的文件格式"""
    
    def test_supported_formats_set(self):
        """测试支持的格式集合"""
        formats = BatchAnalyzer.SUPPORTED_FORMATS
        
        assert '.jpg' in formats
        assert '.jpeg' in formats
        assert '.png' in formats
        assert '.bmp' in formats
        assert '.tiff' in formats
        assert '.webp' in formats


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

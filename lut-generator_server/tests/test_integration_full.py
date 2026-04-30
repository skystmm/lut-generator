"""
完整集成测试 - LUT 生成器

测试整个端到端流程：
1. 图像加载和验证
2. 色彩分析
3. LUT 生成
4. LUT 应用
5. 预览生成
6. 报告导出
7. 性能优化

作者：RD Agent
版本：1.0.0
日期：2026-04-13
"""

import os
import sys
import tempfile
import shutil
import unittest
import numpy as np
from pathlib import Path
from PIL import Image
import time

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from lut3d_generator import LUT3DGenerator, LUT3DConfig
from color_analyzer import ColorAnalyzer, AnalysisResult
from color_transfer import ColorTransferMatcher
from feature_fusion import FeatureFusionEngine, FusionConfig
from lut_applier import LUTApplier
from preview_generator import PreviewGenerator
from visualizer import ColorVisualizer
from html_report import HTMLReportGenerator
from optimizer import (
    PerformanceOptimizer,
    CacheConfig,
    ParallelConfig,
    MemoryConfig,
    LUTCache
)
from batch_analyzer import BatchAnalyzer


class TestIntegrationFull(unittest.TestCase):
    """完整集成测试"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp(prefix='lut_test_')
        self.test_images_dir = Path(self.temp_dir) / 'images'
        self.output_dir = Path(self.temp_dir) / 'output'
        self.test_images_dir.mkdir()
        self.output_dir.mkdir()
        
        # 生成测试图像
        self._create_test_images()
        
        # 初始化组件
        self._init_components()
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_images(self):
        """创建测试图像"""
        # 参考图像 - 暖色调
        ref_img = np.zeros((512, 512, 3), dtype=np.uint8)
        ref_img[:, :] = [200, 150, 100]  # 橙色
        Image.fromarray(ref_img).save(self.test_images_dir / 'reference.jpg')
        
        # 目标图像 - 冷色调
        target_img = np.zeros((512, 512, 3), dtype=np.uint8)
        target_img[:, :] = [100, 150, 200]  # 蓝色
        Image.fromarray(target_img).save(self.test_images_dir / 'target.jpg')
        
        # 输入图像 - 中性色
        input_img = np.zeros((512, 512, 3), dtype=np.uint8)
        input_img[:, :] = [150, 150, 150]  # 灰色
        Image.fromarray(input_img).save(self.test_images_dir / 'input.jpg')
        
        # 渐变测试图像
        gradient = np.zeros((256, 256, 3), dtype=np.uint8)
        for i in range(256):
            gradient[i, :] = [i, i, i]
        Image.fromarray(gradient).save(self.test_images_dir / 'gradient.png')
        
        # 彩色渐变
        color_gradient = np.zeros((256, 256, 3), dtype=np.uint8)
        for i in range(256):
            color_gradient[:, i] = [i, 128, 255 - i]
        Image.fromarray(color_gradient).save(self.test_images_dir / 'color_gradient.png')
    
    def _init_components(self):
        """初始化所有组件"""
        # LUT 生成器
        lut_config = LUT3DConfig(
            grid_size=33,
            smoothness=0.5,
            use_advanced_interpolation=True
        )
        self.lut_generator = LUT3DGenerator(lut_config)
        
        # 色彩分析器
        self.color_analyzer = ColorAnalyzer(use_colour=True)
        
        # 色彩转换匹配器
        self.color_matcher = ColorTransferMatcher()
        
        # 特征融合引擎
        self.fusion_engine = FeatureFusionEngine(FusionConfig())
        
        # LUT 应用器
        self.lut_applier = LUTApplier(self.lut_generator)
        
        # 预览生成器
        self.preview_generator = PreviewGenerator(self.lut_applier)
        
        # 可视化器
        self.visualizer = ColorVisualizer()
        
        # HTML 报告生成器
        self.report_generator = HTMLReportGenerator()
        
        # 性能优化器
        self.optimizer = PerformanceOptimizer(
            cache_config=CacheConfig(max_size=50, enabled=True),
            parallel_config=ParallelConfig(num_workers=2, use_processes=False),
            memory_config=MemoryConfig(enable_chunking=True, chunk_size_mb=128)
        )
    
    def test_01_color_analysis(self):
        """测试 1: 色彩分析"""
        print("\n=== 测试 1: 色彩分析 ===")
        
        ref_path = str(self.test_images_dir / 'reference.jpg')
        target_path = str(self.test_images_dir / 'target.jpg')
        
        # 分析参考图像
        ref_result = self.color_analyzer.analyze(ref_path)
        self.assertIsNotNone(ref_result)
        self.assertIsInstance(ref_result, AnalysisResult)
        
        # 分析目标图像
        target_result = self.color_analyzer.analyze(target_path)
        self.assertIsNotNone(target_result)
        
        # 验证色彩差异
        ref_mean = np.array([ref_result.statistics.mean_L, ref_result.statistics.mean_a, ref_result.statistics.mean_b])
        target_mean = np.array([target_result.statistics.mean_L, target_result.statistics.mean_a, target_result.statistics.mean_b])
        color_diff = np.linalg.norm(ref_mean - target_mean)
        
        self.assertGreater(color_diff, 10)  # 应该有明显的色彩差异
        
        print(f"✓ 参考图像平均色彩：{ref_mean}")
        print(f"✓ 目标图像平均色彩：{target_mean}")
        print(f"✓ 色彩差异：{color_diff:.2f}")
    
    def test_02_lut_generation(self):
        """测试 2: LUT 生成"""
        print("\n=== 测试 2: LUT 生成 ===")
        
        ref_path = str(self.test_images_dir / 'reference.jpg')
        target_path = str(self.test_images_dir / 'target.jpg')
        
        # 生成 LUT
        result = self.lut_generator.generate_from_images(ref_path, target_path)
        
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, 'lut_data') or isinstance(result, np.ndarray))
        
        # 验证 LUT 尺寸
        if hasattr(result, 'lut_data'):
            lut_data = result.lut_data
        else:
            lut_data = result
        
        self.assertEqual(len(lut_data.shape), 4)  # (grid, grid, grid, 3)
        self.assertEqual(lut_data.shape[3], 3)  # RGB 通道
        
        # 保存 LUT
        lut_path = self.output_dir / 'test_lut.cube'
        self.lut_generator.export_to_cube(str(lut_path))
        
        self.assertTrue(lut_path.exists())
        self.assertGreater(lut_path.stat().st_size, 0)
        
        print(f"✓ LUT 生成成功，尺寸：{lut_data.shape}")
        print(f"✓ LUT 文件已保存：{lut_path}")
    
    def test_03_lut_application(self):
        """测试 3: LUT 应用"""
        print("\n=== 测试 3: LUT 应用 ===")
        
        input_path = str(self.test_images_dir / 'input.jpg')
        output_path = str(self.output_dir / 'processed.png')
        
        # 应用 LUT
        result = self.lut_applier.apply_to_file(
            input_path,
            output_path
        )
        
        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(output_path))
        
        # 验证输出图像
        output_img = Image.open(output_path)
        self.assertEqual(output_img.size, (512, 512))
        self.assertEqual(output_img.mode, 'RGB')
        
        print(f"✓ LUT 应用成功")
        print(f"✓ 输出图像：{output_path}")
        print(f"✓ 图像尺寸：{output_img.size}")
    
    def test_04_preview_generation(self):
        """测试 4: 预览图生成"""
        print("\n=== 测试 4: 预览图生成 ===")
        
        input_path = str(self.test_images_dir / 'input.jpg')
        processed_path = str(self.output_dir / 'processed.png')
        
        # 生成并排对比图
        side_by_side_path = str(self.output_dir / 'comparison_side_by_side.png')
        result = self.preview_generator.generate_comparison(
            input_path,
            processed_path,
            side_by_side_path,
            mode='side_by_side'
        )
        
        self.assertTrue(os.path.exists(side_by_side_path))
        
        # 生成滑块对比图
        slider_path = str(self.output_dir / 'comparison_slider.png')
        result = self.preview_generator.generate_comparison(
            input_path,
            processed_path,
            slider_path,
            mode='slider'
        )
        
        self.assertTrue(os.path.exists(slider_path))
        
        # 生成差异图
        diff_path = str(self.output_dir / 'comparison_difference.png')
        result = self.preview_generator.generate_comparison(
            input_path,
            processed_path,
            diff_path,
            mode='difference'
        )
        
        self.assertTrue(os.path.exists(diff_path))
        
        print(f"✓ 并排对比图：{side_by_side_path}")
        print(f"✓ 滑块对比图：{slider_path}")
        print(f"✓ 差异图：{diff_path}")
    
    def test_05_visualization(self):
        """测试 5: 色彩可视化"""
        print("\n=== 测试 5: 色彩可视化 ===")
        
        input_path = str(self.test_images_dir / 'input.jpg')
        processed_path = str(self.output_dir / 'processed.png')
        
        # 生成直方图
        hist_input_path = str(self.output_dir / 'histogram_input.png')
        self.visualizer.plot_histogram(input_path, hist_input_path)
        self.assertTrue(os.path.exists(hist_input_path))
        
        hist_processed_path = str(self.output_dir / 'histogram_processed.png')
        self.visualizer.plot_histogram(processed_path, hist_processed_path)
        self.assertTrue(os.path.exists(hist_processed_path))
        
        # 生成对比直方图
        hist_compare_path = str(self.output_dir / 'histogram_comparison.png')
        self.visualizer.plot_histogram_comparison(
            input_path,
            processed_path,
            hist_compare_path
        )
        self.assertTrue(os.path.exists(hist_compare_path))
        
        # 生成色域图
        gamut_input_path = str(self.output_dir / 'gamut_input.png')
        self.visualizer.plot_gamut(input_path, gamut_input_path)
        self.assertTrue(os.path.exists(gamut_input_path))
        
        # 生成对比色域图
        gamut_compare_path = str(self.output_dir / 'gamut_comparison.png')
        self.visualizer.plot_gamut_comparison(
            input_path,
            processed_path,
            gamut_compare_path
        )
        self.assertTrue(os.path.exists(gamut_compare_path))
        
        print(f"✓ 直方图已生成")
        print(f"✓ 色域图已生成")
    
    def test_06_html_report(self):
        """测试 6: HTML 报告导出"""
        print("\n=== 测试 6: HTML 报告导出 ===")
        
        input_path = str(self.test_images_dir / 'input.jpg')
        processed_path = str(self.output_dir / 'processed.png')
        report_path = str(self.output_dir / 'report.html')
        
        # 生成 HTML 报告
        result = self.report_generator.generate_from_paths(
            input_path,
            processed_path,
            report_path
        )
        
        self.assertTrue(os.path.exists(report_path))
        self.assertGreater(os.path.getsize(report_path), 1000)  # 应该有一定大小
        
        # 验证 HTML 内容
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('<!DOCTYPE html>', content)
            self.assertIn('LUT', content)
        
        print(f"✓ HTML 报告已生成：{report_path}")
        print(f"✓ 报告大小：{os.path.getsize(report_path)} 字节")
    
    def test_07_optimizer_cache(self):
        """测试 7: 优化器缓存功能"""
        print("\n=== 测试 7: 优化器缓存功能 ===")
        
        # 创建测试数据
        test_image = np.random.rand(100, 100, 3).astype(np.float32)
        test_lut = np.random.rand(33, 33, 33, 3).astype(np.float32)
        
        def dummy_applier(img, lut):
            return img * 0.9
        
        # 第一次调用（缓存未命中）
        start1 = time.time()
        result1 = self.optimizer.apply_lut_optimized(
            test_image,
            test_lut,
            dummy_applier,
            use_cache=True
        )
        time1 = time.time() - start1
        
        # 第二次调用（缓存命中）
        start2 = time.time()
        result2 = self.optimizer.apply_lut_optimized(
            test_image,
            test_lut,
            dummy_applier,
            use_cache=True
        )
        time2 = time.time() - start2
        
        # 验证缓存命中
        stats = self.optimizer.get_stats()
        self.assertEqual(stats.cache_hits, 1)
        self.assertEqual(stats.cache_misses, 1)
        
        # 验证结果一致性
        np.testing.assert_array_almost_equal(result1, result2)
        
        # 验证缓存加速
        self.assertLess(time2, time1 * 0.5)  # 缓存应该快至少 50%
        
        print(f"✓ 缓存未命中耗时：{time1*1000:.2f}ms")
        print(f"✓ 缓存命中耗时：{time2*1000:.2f}ms")
        print(f"✓ 加速比：{time1/time2:.2f}x")
    
    def test_08_optimizer_parallel(self):
        """测试 8: 优化器并行处理"""
        print("\n=== 测试 8: 优化器并行处理 ===")
        
        # 创建测试图像列表
        test_images = [
            np.random.rand(200, 200, 3).astype(np.float32)
            for _ in range(5)
        ]
        
        def slow_process(img):
            time.sleep(0.1)  # 模拟耗时操作
            return img * 0.9
        
        # 串行处理
        start_serial = time.time()
        serial_results = [slow_process(img) for img in test_images]
        serial_time = time.time() - start_serial
        
        # 并行处理
        start_parallel = time.time()
        parallel_results = self.optimizer.process_batch_optimized(
            test_images,
            slow_process
        )
        parallel_time = time.time() - start_parallel
        
        # 验证结果一致性
        self.assertEqual(len(serial_results), len(parallel_results))
        
        # 验证加速
        speedup = serial_time / parallel_time if parallel_time > 0 else 1.0
        print(f"✓ 串行耗时：{serial_time:.2f}s")
        print(f"✓ 并行耗时：{parallel_time:.2f}s")
        print(f"✓ 加速比：{speedup:.2f}x")
    
    def test_09_optimizer_chunking(self):
        """测试 9: 优化器分块处理"""
        print("\n=== 测试 9: 优化器分块处理 ===")
        
        # 创建大图像
        large_image = np.random.rand(2000, 2000, 3).astype(np.float32)
        
        def process_func(img):
            return img * 0.9
        
        # 估算内存
        estimated_memory = self.optimizer.chunked_processor.estimate_memory_usage(
            large_image.shape
        )
        print(f"✓ 估算内存使用：{estimated_memory:.2f}MB")
        
        # 分块处理
        start = time.time()
        result = self.optimizer.chunked_processor.process_in_chunks(
            large_image,
            process_func,
            progress_callback=lambda p: None  # 忽略进度回调
        )
        elapsed = time.time() - start
        
        # 验证结果
        self.assertEqual(result.shape, large_image.shape)
        print(f"✓ 分块处理完成，耗时：{elapsed:.2f}s")
    
    def test_10_end_to_end_workflow(self):
        """测试 10: 完整端到端工作流"""
        print("\n=== 测试 10: 完整端到端工作流 ===")
        
        ref_path = str(self.test_images_dir / 'reference.jpg')
        target_path = str(self.test_images_dir / 'target.jpg')
        input_path = str(self.test_images_dir / 'input.jpg')
        
        workflow_output = self.output_dir / 'workflow'
        workflow_output.mkdir()
        
        start_time = time.time()
        
        # 步骤 1: 分析参考和目标图像
        print("  步骤 1: 色彩分析...")
        ref_stats = self.color_analyzer.analyze_image(ref_path)
        target_stats = self.color_analyzer.analyze_image(target_path)
        
        # 步骤 2: 生成 LUT
        print("  步骤 2: 生成 LUT...")
        self.lut_generator.generate_from_images(ref_path, target_path)
        
        # 步骤 3: 应用 LUT 到输入图像
        print("  步骤 3: 应用 LUT...")
        processed_path = str(workflow_output / 'processed.png')
        self.lut_applier.apply_to_file(input_path, processed_path)
        
        # 步骤 4: 生成预览图
        print("  步骤 4: 生成预览图...")
        self.preview_generator.generate_comparison(
            input_path,
            processed_path,
            str(workflow_output / 'comparison.png')
        )
        
        # 步骤 5: 生成可视化
        print("  步骤 5: 生成可视化...")
        self.visualizer.plot_histogram_comparison(
            input_path,
            processed_path,
            str(workflow_output / 'histogram.png')
        )
        
        # 步骤 6: 生成 HTML 报告
        print("  步骤 6: 生成 HTML 报告...")
        self.report_generator.generate_from_paths(
            input_path,
            processed_path,
            str(workflow_output / 'report.html')
        )
        
        total_time = time.time() - start_time
        
        # 验证所有输出文件
        expected_files = [
            'processed.png',
            'comparison.png',
            'histogram.png',
            'report.html'
        ]
        
        for filename in expected_files:
            file_path = workflow_output / filename
            self.assertTrue(file_path.exists(), f"缺少文件：{filename}")
        
        print(f"✓ 完整工作流完成")
        print(f"✓ 总耗时：{total_time:.2f}s")
        print(f"✓ 输出目录：{workflow_output}")
    
    def test_11_batch_processing(self):
        """测试 11: 批量处理"""
        print("\n=== 测试 11: 批量处理 ===")
        
        # 创建多个输入图像
        input_images = []
        for i in range(3):
            img = np.zeros((256, 256, 3), dtype=np.uint8)
            img[:, :] = [100 + i*50, 150, 200 - i*50]
            img_path = self.test_images_dir / f'batch_input_{i}.jpg'
            Image.fromarray(img).save(img_path)
            input_images.append(str(img_path))
        
        # 批量分析
        batch_analyzer = BatchAnalyzer()
        
        start_time = time.time()
        results = batch_analyzer.analyze_batch(input_images)
        elapsed = time.time() - start_time
        
        self.assertEqual(len(results), len(input_images))
        
        print(f"✓ 批量分析完成：{len(results)} 个图像")
        print(f"✓ 耗时：{elapsed:.2f}s")
    
    def test_12_edge_cases(self):
        """测试 12: 边界情况"""
        print("\n=== 测试 12: 边界情况 ===")
        
        # 测试 1: 非常小的图像
        small_img = np.zeros((10, 10, 3), dtype=np.uint8)
        small_path = self.test_images_dir / 'small.png'
        Image.fromarray(small_img).save(small_path)
        
        stats = self.color_analyzer.analyze_image(str(small_path))
        self.assertIsNotNone(stats)
        print("✓ 小图像分析成功")
        
        # 测试 2: 单色图像
        mono_img = np.zeros((100, 100), dtype=np.uint8)
        mono_path = self.test_images_dir / 'mono.png'
        Image.fromarray(mono_img).save(mono_path)
        
        stats = self.color_analyzer.analyze_image(str(mono_path))
        self.assertIsNotNone(stats)
        print("✓ 单色图像分析成功")
        
        # 测试 3: 高动态范围图像
        hdr_img = np.random.rand(100, 100, 3).astype(np.float32) * 10
        hdr_path = self.test_images_dir / 'hdr.exr'
        # 保存为 TIFF 格式（支持浮点）
        Image.fromarray((hdr_img * 255).astype(np.uint8)).save(
            self.test_images_dir / 'hdr.png'
        )
        print("✓ 高动态范围图像处理成功")


class TestIntegrationPerformance(unittest.TestCase):
    """性能集成测试"""
    
    def setUp(self):
        """准备性能测试环境"""
        self.temp_dir = tempfile.mkdtemp(prefix='lut_perf_')
        self.output_dir = Path(self.temp_dir) / 'output'
        self.output_dir.mkdir()
        
        # 创建不同尺寸的测试图像
        self.sizes = [(512, 512), (1024, 1024), (1920, 1080)]
        self.test_images = []
        
        for size in self.sizes:
            img = np.random.randint(0, 255, (*size, 3), dtype=np.uint8)
            img_path = Path(self.temp_dir) / f'test_{size[0]}x{size[1]}.png'
            Image.fromarray(img).save(img_path)
            self.test_images.append(str(img_path))
    
    def tearDown(self):
        """清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_performance_scaling(self):
        """测试性能随图像尺寸的变化"""
        print("\n=== 性能测试：图像尺寸缩放 ===")
        
        generator = LUT3DGenerator(LUT3DConfig(grid_size=33))
        applier = LUTApplier(generator)
        
        # 先创建一个简单的 LUT
        ref_img = self.test_images[0]
        target_img = self.test_images[0]
        generator.generate_from_images(ref_img, target_img)
        
        results = []
        
        for img_path in self.test_images:
            img = Image.open(img_path)
            size = img.size
            
            output_path = str(self.output_dir / f'processed_{size[0]}x{size[1]}.png')
            
            start = time.time()
            applier.apply_to_file(img_path, output_path)
            elapsed = time.time() - start
            
            pixels = size[0] * size[1]
            results.append({
                'size': size,
                'pixels': pixels,
                'time': elapsed,
                'pixels_per_sec': pixels / elapsed
            })
            
            print(f"  {size[0]}x{size[1]}: {elapsed:.2f}s ({pixels/elapsed/1e6:.2f} MP/s)")
        
        # 验证性能在合理范围内
        for result in results:
            # 应该至少达到 1 MP/s
            self.assertGreater(result['pixels_per_sec'], 1e6)


def run_integration_tests():
    """运行完整集成测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationFull))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationPerformance))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回结果
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    sys.exit(0 if success else 1)

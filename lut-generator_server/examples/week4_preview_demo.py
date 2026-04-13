#!/usr/bin/env python3
"""
第 4 周预览功能演示

演示如何使用新生成的预览模块：
1. LUT 应用
2. 对比图生成
3. 色彩分布可视化
4. HTML 报告导出

使用方法：
    python examples/week4_preview_demo.py <reference_image> <target_image> <input_image> <output_dir>
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from lut3d_generator import LUT3DGenerator, LUT3DConfig
from lut_applier import LUTApplier, ApplyConfig
from preview_generator import PreviewGenerator, ComparisonConfig
from visualizer import ColorVisualizer, VisualizationConfig
from html_report import HTMLReportGenerator, ReportConfig, ReportData


def print_header(text):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def print_step(step_num, text):
    """打印步骤"""
    print(f"\n[步骤 {step_num}] {text}")
    print("-" * 40)


def main():
    if len(sys.argv) < 5:
        print("LUT 预览功能演示")
        print("=" * 60)
        print("\n使用方法:")
        print("  python examples/week4_preview_demo.py <reference_image> <target_image> <input_image> <output_dir>")
        print("\n参数说明:")
        print("  reference_image: 参考图像（风格来源）")
        print("  target_image:    目标图像（待处理图像）")
        print("  input_image:     输入图像（应用 LUT 的图像）")
        print("  output_dir:      输出目录")
        print("\n示例:")
        print("  python examples/week4_preview_demo.py photos/ref.jpg photos/target.jpg photos/input.jpg output/")
        sys.exit(1)
    
    reference_path = Path(sys.argv[1])
    target_path = Path(sys.argv[2])
    input_path = Path(sys.argv[3])
    output_dir = Path(sys.argv[4])
    
    # 验证文件存在
    for path in [reference_path, target_path, input_path]:
        if not path.exists():
            print(f"错误：文件不存在 - {path}")
            sys.exit(1)
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print_header("LUT 预览功能演示 - 第 4 周")
    print(f"参考图像：{reference_path}")
    print(f"目标图像：{target_path}")
    print(f"输入图像：{input_path}")
    print(f"输出目录：{output_dir}")
    
    total_start = time.time()
    
    # ========== 步骤 1: 生成 LUT ==========
    print_step(1, "生成 3D LUT")
    
    start = time.time()
    config = LUT3DConfig(grid_size=33, interpolation='trilinear')
    generator = LUT3DGenerator(config)
    generator.generate_from_images(reference_path, target_path, strength=1.0)
    duration = time.time() - start
    
    print(f"✓ LUT 生成完成")
    print(f"  网格大小：{config.grid_size}³ = {config.grid_size**3} 个节点")
    print(f"  LUT 形状：{generator.lut_data.shape}")
    print(f"  内存占用：{generator.lut_data.nbytes / 1024:.2f} KB")
    print(f"  耗时：{duration:.2f}秒")
    
    # ========== 步骤 2: 应用 LUT ==========
    print_step(2, "应用 LUT 到图像")
    
    start = time.time()
    applier = LUTApplier(generator)
    apply_config = ApplyConfig(quality=95, output_format='png')
    
    processed_path = output_dir / "processed.png"
    apply_result = applier.apply_to_file(input_path, processed_path, apply_config)
    duration = time.time() - start
    
    if apply_result.success:
        print(f"✓ LUT 应用完成")
        print(f"  输出文件：{apply_result.output_path}")
        print(f"  输入尺寸：{apply_result.input_size[0]}x{apply_result.input_size[1]}")
        print(f"  输出尺寸：{apply_result.output_size[0]}x{apply_result.output_size[1]}")
        print(f"  处理时间：{apply_result.processing_time:.2f}秒")
        print(f"  总耗时：{duration:.2f}秒")
    else:
        print(f"✗ LUT 应用失败：{apply_result.error_message}")
        sys.exit(1)
    
    # ========== 步骤 3: 生成对比图 ==========
    print_step(3, "生成对比图")
    
    preview_gen = PreviewGenerator(applier)
    
    # 3.1 并排对比
    print("\n  3.1 生成并排对比图...")
    start = time.time()
    sbs_path = output_dir / "comparison_side_by_side.png"
    sbs_config = ComparisonConfig(mode='side_by_side', output_width=1920, add_labels=True)
    sbs_result = preview_gen.generate_comparison(input_path, processed_path, sbs_path, sbs_config)
    
    if sbs_result.success:
        print(f"  ✓ 并排对比图：{sbs_path}")
        print(f"    尺寸：{sbs_result.output_size[0]}x{sbs_result.output_size[1]}")
        print(f"    耗时：{sbs_result.generation_time:.2f}秒")
        
        # 打印统计信息
        if sbs_result.statistics:
            stats = sbs_result.statistics
            print(f"    亮度变化：{stats['brightness_change']:+.2f}%")
            print(f"    平均差异：{stats['difference']['mean_diff']:.2f}")
    
    # 3.2 滑块对比
    print("\n  3.2 生成滑块对比图...")
    start = time.time()
    slider_path = output_dir / "comparison_slider.png"
    slider_config = ComparisonConfig(mode='slider', slider_position=0.5)
    slider_result = preview_gen.generate_comparison(input_path, processed_path, slider_path, slider_config)
    
    if slider_result.success:
        print(f"  ✓ 滑块对比图：{slider_path}")
        print(f"    耗时：{slider_result.generation_time:.2f}秒")
    
    # 3.3 差异可视化
    print("\n  3.3 生成差异可视化图...")
    start = time.time()
    diff_path = output_dir / "comparison_difference.png"
    diff_config = ComparisonConfig(mode='difference')
    diff_result = preview_gen.generate_comparison(input_path, processed_path, diff_path, diff_config)
    
    if diff_result.success:
        print(f"  ✓ 差异可视化：{diff_path}")
        print(f"    耗时：{diff_result.generation_time:.2f}秒")
    
    # ========== 步骤 4: 色彩分布可视化 ==========
    print_step(4, "生成色彩分布可视化")
    
    viz_config = VisualizationConfig(width=1200, height=800)
    visualizer = ColorVisualizer(viz_config)
    
    # 4.1 原图直方图
    print("\n  4.1 原图 RGB 直方图...")
    hist_orig_path = output_dir / "histogram_original.png"
    hist_orig_result = visualizer.plot_histogram(input_path, hist_orig_path, "Original Image Histogram")
    if hist_orig_result.success:
        print(f"  ✓ {hist_orig_path}")
    
    # 4.2 处理后直方图
    print("\n  4.2 处理后 RGB 直方图...")
    hist_proc_path = output_dir / "histogram_processed.png"
    hist_proc_result = visualizer.plot_histogram(processed_path, hist_proc_path, "Processed Image Histogram")
    if hist_proc_result.success:
        print(f"  ✓ {hist_proc_path}")
    
    # 4.3 对比直方图
    print("\n  4.3 对比 RGB 直方图...")
    hist_comp_path = output_dir / "histogram_comparison.png"
    hist_comp_result = visualizer.plot_histogram_comparison(input_path, processed_path, hist_comp_path)
    if hist_comp_result.success:
        print(f"  ✓ {hist_comp_path}")
    
    # 4.4 原图色域图
    print("\n  4.4 原图色域图 (a*b 平面)...")
    gamut_orig_path = output_dir / "gamut_original.png"
    gamut_orig_result = visualizer.plot_gamut(input_path, gamut_orig_path, "Original Color Gamut")
    if gamut_orig_result.success:
        print(f"  ✓ {gamut_orig_path}")
    
    # 4.5 处理后色域图
    print("\n  4.5 处理后色域图...")
    gamut_proc_path = output_dir / "gamut_processed.png"
    gamut_proc_result = visualizer.plot_gamut(processed_path, gamut_proc_path, "Processed Color Gamut")
    if gamut_proc_result.success:
        print(f"  ✓ {gamut_proc_path}")
    
    # 4.6 对比色域图
    print("\n  4.6 对比色域图...")
    gamut_comp_path = output_dir / "gamut_comparison.png"
    gamut_comp_result = visualizer.plot_gamut_comparison(input_path, processed_path, gamut_comp_path)
    if gamut_comp_result.success:
        print(f"  ✓ {gamut_comp_path}")
    
    # ========== 步骤 5: 生成 HTML 报告 ==========
    print_step(5, "生成 HTML 报告")
    
    report_config = ReportConfig(
        title="LUT 处理报告",
        theme='dark',
        include_slider=True,
        include_histogram=True,
        include_gamut=True,
        include_statistics=True
    )
    
    report_generator = HTMLReportGenerator(report_config)
    
    report_data = ReportData(
        original_image=str(input_path),
        processed_image=str(processed_path),
        comparison_image=str(sbs_path),
        histogram_comparison=str(hist_comp_path),
        gamut_comparison=str(gamut_comp_path),
        statistics=sbs_result.statistics if sbs_result.success else None,
        lut_info=applier._get_metadata(),
        processing_time=apply_result.processing_time
    )
    
    report_path = output_dir / "report.html"
    report_result = report_generator.generate(report_data, report_path)
    
    if report_result.success:
        print(f"✓ HTML 报告生成完成")
        print(f"  报告文件：{report_path}")
        print(f"  文件大小：{report_result.file_size / 1024:.2f} KB")
        print(f"  生成时间：{report_result.generation_time:.2f}秒")
    else:
        print(f"✗ HTML 报告生成失败：{report_result.error_message}")
    
    # ========== 总结 ==========
    total_duration = time.time() - total_start
    
    print_header("演示完成")
    print(f"\n总耗时：{total_duration:.2f}秒")
    print(f"\n输出文件列表:")
    
    output_files = list(output_dir.glob("*"))
    for i, file in enumerate(sorted(output_files), 1):
        size = file.stat().st_size
        size_str = f"{size / 1024:.2f} KB" if size < 1024*1024 else f"{size / 1024/1024:.2f} MB"
        print(f"  {i:2d}. {file.name:<40} ({size_str})")
    
    print(f"\n提示：用浏览器打开 {report_path} 查看交互式报告")
    print(f"      file://{report_path.absolute()}")
    
    print("\n" + "=" * 60)
    print(" 第 4 周预览功能演示结束")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
基础使用示例 - Basic Usage Example

演示如何使用 color_analyzer 和 color_transfer 模块
"""

import sys
import numpy as np
from pathlib import Path

# 添加 src 目录到路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from color_analyzer import ColorAnalyzer, analyze_image
from color_transfer import ReinhardColorTransfer, TransferConfig, transfer_colors


def example_1_analyze_image():
    """示例 1：分析单张图像"""
    print("=" * 60)
    print("示例 1：分析单张图像")
    print("=" * 60)
    
    # 创建测试图像（如果没有真实图片）
    import cv2
    test_img = np.zeros((100, 100, 3), dtype=np.uint8)
    test_img[:50, :50] = [255, 0, 0]      # 红色
    test_img[:50, 50:] = [0, 255, 0]      # 绿色
    test_img[50:, :50] = [0, 0, 255]      # 蓝色
    test_img[50:, 50:] = [255, 255, 255]  # 白色
    
    # 保存测试图像
    test_path = "/tmp/test_image.png"
    cv2.imwrite(test_path, test_img[:, :, ::-1])  # BGR for OpenCV
    
    # 分析图像
    analyzer = ColorAnalyzer(use_colour=False)  # 使用 OpenCV 后端
    result = analyzer.analyze(test_path)
    
    print(f"\n图像尺寸：{result.image_shape}")
    print(f"\n色彩统计:")
    print(f"  均值 (L,a,b): {result.statistics.mean_array()}")
    print(f"  标准差 (L,a,b): {result.statistics.std_array()}")
    print(f"\n色彩分布:")
    print(f"  L 范围：{result.distribution.L_range}")
    print(f"  a 范围：{result.distribution.a_range}")
    print(f"  b 范围：{result.distribution.b_range}")
    print(f"  色域覆盖：{result.distribution.gamut_coverage:.2f}%")
    print(f"  色彩熵：{result.distribution.color_entropy:.2f}")
    print(f"  主色调 (L,a,b): {result.distribution.dominant_color}")


def example_2_color_transfer():
    """示例 2：色彩迁移"""
    print("\n" + "=" * 60)
    print("示例 2：色彩迁移")
    print("=" * 60)
    
    import cv2
    
    # 创建源图像（暖色调）
    source_img = np.zeros((100, 100, 3), dtype=np.uint8)
    source_img[:, :] = [200, 150, 100]  # 橙色
    
    # 创建目标图像（冷色调）
    target_img = np.zeros((100, 100, 3), dtype=np.uint8)
    target_img[:, :] = [100, 150, 200]  # 蓝色
    
    # 保存
    source_path = "/tmp/source.png"
    target_path = "/tmp/target.png"
    cv2.imwrite(source_path, source_img[:, :, ::-1])
    cv2.imwrite(target_path, target_img[:, :, ::-1])
    
    # 执行色彩迁移
    print("\n执行色彩迁移...")
    rgb_result, params = transfer_colors(source_path, target_path, strength=0.8)
    
    print(f"\n变换参数:")
    print(f"  源均值 (L,a,b): [{params['source_mean_L']:.2f}, {params['source_mean_a']:.2f}, {params['source_mean_b']:.2f}]")
    print(f"  目标均值 (L,a,b): [{params['target_mean_L']:.2f}, {params['target_mean_a']:.2f}, {params['target_mean_b']:.2f}]")
    print(f"  缩放因子 (L,a,b): [{params['scale_L']:.2f}, {params['scale_a']:.2f}, {params['scale_b']:.2f}]")
    print(f"  迁移强度：{params['strength']}")
    
    print(f"\n结果图像:")
    print(f"  形状：{rgb_result.shape}")
    print(f"  范围：[{rgb_result.min():.4f}, {rgb_result.max():.4f}]")
    
    # 保存结果
    output_path = "/tmp/result.png"
    result_bgr = (rgb_result[:, :, ::-1] * 255).astype(np.uint8)
    cv2.imwrite(output_path, result_bgr)
    print(f"\n结果已保存到：{output_path}")


def example_3_advanced_transfer():
    """示例 3：高级色彩迁移（独立通道控制）"""
    print("\n" + "=" * 60)
    print("示例 3：高级色彩迁移 - 独立通道控制")
    print("=" * 60)
    
    import cv2
    
    # 创建测试图像
    source_img = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
    target_img = np.random.randint(50, 200, (100, 100, 3), dtype=np.uint8)
    
    # 保存
    source_path = "/tmp/source_adv.png"
    target_path = "/tmp/target_adv.png"
    cv2.imwrite(source_path, source_img[:, :, ::-1])
    cv2.imwrite(target_path, target_img[:, :, ::-1])
    
    # 创建迁移器
    transfer = ReinhardColorTransfer()
    
    # 加载并转换图像
    analyzer = ColorAnalyzer()
    source_rgb = analyzer.load_image(source_path)
    target_rgb = analyzer.load_image(target_path)
    source_lab = analyzer.rgb_to_lab(source_rgb)
    target_lab = analyzer.rgb_to_lab(target_rgb)
    
    # 配置：只对 L 通道应用 50% 强度，a,b 通道应用 100% 强度
    config = TransferConfig(
        strength=1.0,
        L_strength=0.5,  # L 通道 50%
        a_strength=1.0,  # a 通道 100%
        b_strength=1.0   # b 通道 100%
    )
    
    result = transfer.transfer(source_lab, target_lab, config)
    
    print(f"\n配置:")
    print(f"  L 通道强度：{config.L_strength}")
    print(f"  a 通道强度：{config.a_strength}")
    print(f"  b 通道强度：{config.b_strength}")
    
    print(f"\n结果:")
    print(f"  RGB 范围：[{result.rgb_result.min():.4f}, {result.rgb_result.max():.4f}]")
    print(f"  输出类型：{result.to_rgb_uint8().dtype}")


def example_4_lut_transform_builder():
    """示例 4：LUT 变换构建器"""
    print("\n" + "=" * 60)
    print("示例 4：LUT 变换构建器")
    print("=" * 60)
    
    from color_analyzer import ColorStatistics
    from color_transfer import LUTTransformBuilder
    
    # 创建统计信息
    source_stats = ColorStatistics(
        mean_L=50.0, mean_a=30.0, mean_b=20.0,
        std_L=15.0, std_a=10.0, std_b=8.0,
        var_L=225.0, var_a=100.0, var_b=64.0
    )
    
    target_stats = ColorStatistics(
        mean_L=60.0, mean_a=10.0, mean_b=-10.0,
        std_L=20.0, std_a=15.0, std_b=12.0,
        var_L=400.0, var_a=225.0, var_b=144.0
    )
    
    # 构建变换函数
    builder = LUTTransformBuilder(source_stats, target_stats, strength=1.0)
    transform_func = builder.build_transform_func()
    
    # 测试变换
    test_colors = [
        np.array([0.0, 0.0, 0.0]),    # 黑色
        np.array([0.5, 0.5, 0.5]),    # 灰色
        np.array([1.0, 1.0, 1.0]),    # 白色
        np.array([1.0, 0.0, 0.0]),    # 红色
        np.array([0.0, 1.0, 0.0]),    # 绿色
        np.array([0.0, 0.0, 1.0]),    # 蓝色
    ]
    
    print("\n变换测试:")
    print(f"{'输入 RGB':<20} -> {'输出 RGB':<20}")
    print("-" * 45)
    
    for rgb in test_colors:
        result_rgb = transform_func(rgb)
        input_str = f"({rgb[0]:.2f}, {rgb[1]:.2f}, {rgb[2]:.2f})"
        output_str = f"({result_rgb[0]:.2f}, {result_rgb[1]:.2f}, {result_rgb[2]:.2f})"
        print(f"{input_str:<20} -> {output_str}")


if __name__ == "__main__":
    print("LUT Generator - 基础使用示例")
    print("=" * 60)
    
    # 运行所有示例
    example_1_analyze_image()
    example_2_color_transfer()
    example_3_advanced_transfer()
    example_4_lut_transform_builder()
    
    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)

#!/usr/bin/env python3
"""
LUT Generator CLI - 命令行工具

支持：
- 单图分析模式
- 批量分析模式
- 多图融合模式
- LUT 生成模式

用法：
    # 单图分析
    python cli.py analyze <image_path>
    
    # 批量分析目录
    python cli.py batch <directory> [-r] [-o output.json]
    
    # 多图融合
    python cli.py fuse <directory> [-w weights] [-s strategy] [-o output.json]
    
    # 生成 LUT
    python cli.py generate <source_dir> <target_dir> [-o output.cube]
"""

import argparse
import sys
import json
from pathlib import Path
from typing import List, Optional
import logging

# 导入模块
from color_analyzer import ColorAnalyzer, analyze_image
from batch_analyzer import BatchAnalyzer, analyze_directory_batch
from feature_fusion import FeatureFusion, FusionConfig, fuse_features, create_weight_config
from lut3d_generator import LUT3DGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_analyze(args):
    """单图分析命令"""
    image_path = Path(args.image)
    
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)
    
    print(f"Analyzing: {image_path}")
    
    try:
        result = analyze_image(image_path, use_colour=not args.fast)
        
        print("\n=== Analysis Result ===")
        print(f"Image shape: {result.image_shape}")
        print(f"\nStatistics:")
        print(f"  Mean (L,a,b): [{result.statistics.mean_L:.2f}, {result.statistics.mean_a:.2f}, {result.statistics.mean_b:.2f}]")
        print(f"  Std  (L,a,b): [{result.statistics.std_L:.2f}, {result.statistics.std_a:.2f}, {result.statistics.std_b:.2f}]")
        print(f"\nDistribution:")
        print(f"  L range: [{result.distribution.L_range[0]:.2f}, {result.distribution.L_range[1]:.2f}]")
        print(f"  a range: [{result.distribution.a_range[0]:.2f}, {result.distribution.a_range[1]:.2f}]")
        print(f"  b range: [{result.distribution.b_range[0]:.2f}, {result.distribution.b_range[1]:.2f}]")
        print(f"  Gamut coverage: {result.distribution.gamut_coverage:.2f}%")
        print(f"  Color entropy: {result.distribution.color_entropy:.2f}")
        print(f"  Dominant color (L,a,b): [{result.distribution.dominant_color[0]:.2f}, {result.distribution.dominant_color[1]:.2f}, {result.distribution.dominant_color[2]:.2f}]")
        
        # 保存结果
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"\nResults saved to: {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_batch(args):
    """批量分析命令"""
    directory = Path(args.directory)
    
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        sys.exit(1)
    
    if not directory.is_dir():
        print(f"Error: Not a directory: {directory}")
        sys.exit(1)
    
    print(f"Scanning directory: {directory}")
    print(f"Recursive: {args.recursive}")
    print(f"Parallel: {not args.serial}")
    
    try:
        analyzer = BatchAnalyzer(
            use_colour=not args.fast,
            max_workers=args.workers
        )
        
        result = analyzer.analyze_directory(
            directory,
            recursive=args.recursive,
            parallel=not args.serial
        )
        
        print(f"\n=== Batch Analysis Report ===")
        print(f"Total images: {result.total_images}")
        print(f"Valid: {result.valid_images}")
        print(f"Failed: {result.failed_images}")
        
        if result.valid_images > 0:
            print(f"\nValid images:")
            for img in result.image_results:
                if img.valid:
                    print(f"  ✓ {img.path.name}")
        
        if result.failed_images > 0:
            print(f"\nFailed images:")
            for img in result.image_results:
                if not img.valid:
                    print(f"  ✗ {img.path.name}: {img.error_message}")
        
        # 保存结果
        if args.output:
            output_path = Path(args.output)
            analyzer.save_results(result, output_path, format=args.format)
            print(f"\nResults saved to: {output_path}")
        
        # 计算聚合统计
        if result.valid_images > 0:
            valid_results = result.get_valid_results()
            aggregated = analyzer.aggregate_statistics(valid_results)
            print(f"\n=== Aggregated Statistics ===")
            print(f"Mean (L,a,b): {aggregated['mean']}")
            print(f"Std  (L,a,b): {aggregated['std']}")
            print(f"Avg gamut coverage: {aggregated['avg_gamut_coverage']:.2f}%")
            print(f"Avg color entropy: {aggregated['avg_color_entropy']:.2f}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def parse_weights(weight_str: str, num_images: int) -> Optional[List[float]]:
    """
    解析权重的字符串
    
    Args:
        weight_str: 权重字符串，如 "2,1,1" 或 "auto"
        num_images: 图片数量
        
    Returns:
        权重列表或 None（等权重）
    """
    if weight_str == 'auto' or weight_str is None:
        return None
    
    try:
        weights = [float(w.strip()) for w in weight_str.split(',')]
        if len(weights) != num_images:
            print(f"Warning: weights count ({len(weights)}) doesn't match images count ({num_images})")
            print("Using equal weights instead")
            return None
        return weights
    except ValueError:
        print(f"Warning: Invalid weights format: {weight_str}")
        print("Using equal weights instead")
        return None


def cmd_fuse(args):
    """多图融合命令"""
    directory = Path(args.directory)
    
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        sys.exit(1)
    
    if not directory.is_dir():
        print(f"Error: Not a directory: {directory}")
        sys.exit(1)
    
    print(f"Loading images from: {directory}")
    
    try:
        # 批量分析
        analyzer = BatchAnalyzer(use_colour=not args.fast)
        batch_result = analyzer.analyze_directory(directory, recursive=args.recursive)
        
        if batch_result.valid_images < 1:
            print("Error: No valid images found")
            sys.exit(1)
        
        results = batch_result.get_valid_results()
        valid_paths = batch_result.get_valid_paths()
        
        print(f"Loaded {len(results)} valid images")
        
        # 解析权重
        weights = parse_weights(args.weights, len(results))
        
        # 创建配置
        config = FusionConfig(
            strategy=args.strategy,
            weights=weights or [],
            histogram_method='average',
            distribution_method='average'
        )
        
        # 融合
        fusion = FeatureFusion(config)
        fused = fusion.fuse(results, weights)
        
        print(f"\n=== Fusion Result ===")
        print(f"Strategy: {args.strategy}")
        print(f"Weights: {fused.weights}")
        print(f"\nFused Statistics:")
        print(f"  Mean (L,a,b): [{fused.statistics.mean_L:.2f}, {fused.statistics.mean_a:.2f}, {fused.statistics.mean_b:.2f}]")
        print(f"  Std  (L,a,b): [{fused.statistics.std_L:.2f}, {fused.statistics.std_a:.2f}, {fused.statistics.std_b:.2f}]")
        print(f"\nFused Distribution:")
        print(f"  Gamut coverage: {fused.distribution.gamut_coverage:.2f}%")
        print(f"  Color entropy: {fused.distribution.color_entropy:.2f}")
        print(f"  Dominant color (L,a,b): [{fused.distribution.dominant_color[0]:.2f}, {fused.distribution.dominant_color[1]:.2f}, {fused.distribution.dominant_color[2]:.2f}]")
        
        # 保存结果
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(fused.to_dict(), f, indent=2)
            print(f"\nFusion result saved to: {output_path}")
        
        # 保存配置
        if args.save_config:
            config_path = Path(args.save_config)
            config.save(config_path)
            print(f"Fusion config saved to: {config_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_generate(args):
    """生成 LUT 命令"""
    source_dir = Path(args.source)
    target_dir = Path(args.target)
    
    if not source_dir.exists():
        print(f"Error: Source directory not found: {source_dir}")
        sys.exit(1)
    
    if not target_dir.exists():
        print(f"Error: Target directory not found: {target_dir}")
        sys.exit(1)
    
    print(f"Source directory: {source_dir}")
    print(f"Target directory: {target_dir}")
    print(f"LUT size: {args.size}")
    
    try:
        # 分析源目录
        print("\nAnalyzing source images...")
        source_analyzer = BatchAnalyzer(use_colour=not args.fast)
        source_result = source_analyzer.analyze_directory(source_dir, recursive=args.recursive)
        
        if source_result.valid_images < 1:
            print("Error: No valid source images found")
            sys.exit(1)
        
        source_results = source_result.get_valid_results()
        source_stats = source_analyzer.aggregate_statistics(source_results)
        print(f"Source: {len(source_results)} images analyzed")
        
        # 分析目标目录
        print("Analyzing target images...")
        target_analyzer = BatchAnalyzer(use_colour=not args.fast)
        target_result = target_analyzer.analyze_directory(target_dir, recursive=args.recursive)
        
        if target_result.valid_images < 1:
            print("Error: No valid target images found")
            sys.exit(1)
        
        target_results = target_result.get_valid_results()
        target_stats = target_analyzer.aggregate_statistics(target_results)
        print(f"Target: {len(target_results)} images analyzed")
        
        # 生成 LUT
        print(f"\nGenerating {args.size}x{args.size}x{args.size} LUT...")
        generator = LUT3DGenerator(size=args.size)
        
        # 使用聚合统计作为源和目标色彩特征
        source_mean = source_stats['mean']
        target_mean = target_stats['mean']
        
        # 生成色彩转换 LUT
        lut = generator.generate_style_transfer_lut(
            source_mean=source_mean,
            target_mean=target_mean
        )
        
        # 导出
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = Path.cwd() / 'output.cube'
        
        from cube_exporter_main import CUBEExporter
        exporter = CUBEExporter()
        exporter.export(lut, str(output_path))
        
        print(f"\nLUT generated successfully!")
        print(f"Output: {output_path}")
        print(f"Size: {args.size}x{args.size}x{args.size}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='LUT Generator CLI - 图片风格分析与 LUT 生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 单图分析
  python cli.py analyze photo.jpg
  
  # 批量分析目录
  python cli.py batch ./images -r -o results.json
  
  # 多图融合（等权）
  python cli.py fuse ./reference_images -o fused.json
  
  # 多图融合（加权）
  python cli.py fuse ./reference_images -w "2,1,1" -o fused.json
  
  # 生成 LUT
  python cli.py generate ./source ./target -o style.cube -s 32
        """
    )
    
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--fast', action='store_true', help='Use fast mode (OpenCV instead of colour-science)')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # analyze 命令
    analyze_parser = subparsers.add_parser('analyze', help='Analyze single image')
    analyze_parser.add_argument('image', help='Image path')
    analyze_parser.add_argument('-o', '--output', help='Output JSON file')
    analyze_parser.set_defaults(func=cmd_analyze)
    
    # batch 命令
    batch_parser = subparsers.add_parser('batch', help='Batch analyze directory')
    batch_parser.add_argument('directory', help='Directory path')
    batch_parser.add_argument('-r', '--recursive', action='store_true', help='Recursive scan')
    batch_parser.add_argument('-o', '--output', help='Output file')
    batch_parser.add_argument('-f', '--format', choices=['json', 'txt'], default='json', help='Output format')
    batch_parser.add_argument('-w', '--workers', type=int, default=4, help='Number of workers')
    batch_parser.add_argument('-s', '--serial', action='store_true', help='Serial processing')
    batch_parser.set_defaults(func=cmd_batch)
    
    # fuse 命令
    fuse_parser = subparsers.add_parser('fuse', help='Fuse multiple images')
    fuse_parser.add_argument('directory', help='Directory path')
    fuse_parser.add_argument('-w', '--weights', help='Weights (comma-separated, e.g., "2,1,1")')
    fuse_parser.add_argument('-s', '--strategy', choices=['weighted_average', 'equal_average', 'median'], 
                            default='weighted_average', help='Fusion strategy')
    fuse_parser.add_argument('-o', '--output', help='Output JSON file')
    fuse_parser.add_argument('--save-config', help='Save fusion config to file')
    fuse_parser.add_argument('-r', '--recursive', action='store_true', help='Recursive scan')
    fuse_parser.set_defaults(func=cmd_fuse)
    
    # generate 命令
    generate_parser = subparsers.add_parser('generate', help='Generate LUT')
    generate_parser.add_argument('source', help='Source directory')
    generate_parser.add_argument('target', help='Target directory')
    generate_parser.add_argument('-o', '--output', help='Output CUBE file')
    generate_parser.add_argument('-s', '--size', type=int, default=32, help='LUT size')
    generate_parser.add_argument('-r', '--recursive', action='store_true', help='Recursive scan')
    generate_parser.set_defaults(func=cmd_generate)
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    args.func(args)


if __name__ == '__main__':
    main()

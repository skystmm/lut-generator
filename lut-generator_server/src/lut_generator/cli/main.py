"""
LUT Generator CLI Entry Point

Command-line interface for generating 3D LUTs from reference images.
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Optional

from lut_generator.core.reinhard import ReinhardColorTransfer, TransferConfig
from lut_generator.core.style_extractor import StyleExtractor, NeutralBaseline, extract_style, analyze_style
from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig
from lut_generator.lut.exporter import LUTExporter
from lut_generator.analysis.analyzer import ColorAnalyzer


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='lut-generator',
        description='Generate 3D LUTs from reference images using Reinhard color transfer'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # generate 子命令
    gen_parser = subparsers.add_parser('generate', help='Generate 3D LUT from images')
    gen_parser.add_argument('-i', '--input', '--source', type=str, required=True,
                            dest='source', help='Source/reference image path')
    gen_parser.add_argument('-t', '--target', type=str, required=True,
                            help='Target image path')
    gen_parser.add_argument('-o', '--output', type=str, required=True,
                            help='Output LUT file path')
    gen_parser.add_argument('-f', '--format', type=str, default='cube',
                            choices=['cube', '3dl', 'clf'],
                            help='Output format (default: cube)')
    gen_parser.add_argument('-s', '--size', type=int, default=33,
                            choices=[17, 33, 65],
                            help='LUT grid size (default: 33)')
    gen_parser.add_argument('--strength', type=float, default=1.0,
                            help='Color transfer strength (0-1, default: 1.0)')
    gen_parser.add_argument('--title', type=str, default=None,
                            help='LUT title')
    gen_parser.add_argument('--description', type=str, default=None,
                            help='LUT description')
    
    # analyze 子命令
    analyze_parser = subparsers.add_parser('analyze', help='Analyze image color statistics')
    analyze_parser.add_argument('image', type=str, help='Image path to analyze')
    analyze_parser.add_argument('-o', '--output', type=str, default=None,
                                help='Output JSON file path (default: print to stdout)')
    analyze_parser.add_argument('--use-colour', action='store_true',
                                help='Use colour-science library for accurate conversion')
    
    # transfer 子命令
    transfer_parser = subparsers.add_parser('transfer', help='Apply color transfer to image')
    transfer_parser.add_argument('-i', '--input', '--source', type=str, required=True,
                                 dest='source', help='Source/reference image path')
    transfer_parser.add_argument('-t', '--target', type=str, required=True,
                                 help='Target image path')
    transfer_parser.add_argument('-o', '--output', type=str, required=True,
                                 help='Output image path')
    transfer_parser.add_argument('--strength', type=float, default=1.0,
                                 help='Color transfer strength (0-1, default: 1.0)')
    
    # video-generate 子命令 - 视频 LUT 生成
    video_gen_parser = subparsers.add_parser(
        'video-generate',
        help='Generate 3D LUT from video(s)'
    )
    video_gen_parser.add_argument(
        'source', type=str,
        help='Source video/image path'
    )
    video_gen_parser.add_argument(
        '-t', '--target', type=str, default=None,
        help='Target video/image path (omit for style extraction mode)'
    )
    video_gen_parser.add_argument(
        '-o', '--output', type=str, required=True,
        help='Output LUT file path'
    )
    video_gen_parser.add_argument(
        '-f', '--format', type=str, default='cube',
        choices=['cube', '3dl', 'clf'],
        help='Output format (default: cube)'
    )
    video_gen_parser.add_argument(
        '-s', '--size', type=int, default=33,
        choices=[17, 33, 65],
        help='LUT grid size (default: 33)'
    )
    video_gen_parser.add_argument(
        '--strength', type=float, default=1.0,
        help='Color transfer strength (0-1, default: 1.0)'
    )
    video_gen_parser.add_argument(
        '--sample-rate', type=float, default=1.0,
        help='Frame sampling rate (frames/sec, default: 1.0)'
    )
    video_gen_parser.add_argument(
        '--max-frames', type=int, default=100,
        help='Maximum frames to sample per video (default: 100)'
    )
    video_gen_parser.add_argument(
        '--scene-threshold', type=float, default=0.3,
        help='Scene detection threshold (0-1, default: 0.3)'
    )
    video_gen_parser.add_argument(
        '--strategy', type=str, default='adaptive',
        choices=['uniform', 'scene', 'adaptive'],
        help='Frame sampling strategy (default: adaptive)'
    )
    video_gen_parser.add_argument(
        '--title', type=str, default=None,
        help='LUT title'
    )
    
    # video-extract 子命令 - 单视频风格提取
    video_ext_parser = subparsers.add_parser(
        'video-extract',
        help='Extract style from a single graded video'
    )
    video_ext_parser.add_argument(
        'video', type=str,
        help='Graded video path'
    )
    video_ext_parser.add_argument(
        '-o', '--output', type=str, required=True,
        help='Output LUT file path'
    )
    video_ext_parser.add_argument(
        '-f', '--format', type=str, default='cube',
        choices=['cube', '3dl', 'clf'],
        help='Output format (default: cube)'
    )
    video_ext_parser.add_argument(
        '-s', '--size', type=int, default=33,
        choices=[17, 33, 65],
        help='LUT grid size (default: 33)'
    )
    video_ext_parser.add_argument(
        '--strength', type=float, default=1.0,
        help='Style intensity (0-1, default: 1.0)'
    )
    video_ext_parser.add_argument(
        '--sample-rate', type=float, default=1.0,
        help='Frame sampling rate (frames/sec, default: 1.0)'
    )
    video_ext_parser.add_argument(
        '--max-frames', type=int, default=100,
        help='Maximum frames to sample (default: 100)'
    )
    video_ext_parser.add_argument(
        '--scene-threshold', type=float, default=0.3,
        help='Scene detection threshold (default: 0.3)'
    )
    video_ext_parser.add_argument(
        '--analyze', action='store_true',
        help='Output style analysis JSON alongside LUT'
    )
    
    # extract 子命令 - 单图风格提取
    extract_parser = subparsers.add_parser('extract', 
                                           help='Extract style from single image and generate LUT')
    extract_parser.add_argument('image', type=str, 
                                help='Graded image path to extract style from')
    extract_parser.add_argument('-o', '--output', type=str, required=True,
                                help='Output LUT file path')
    extract_parser.add_argument('-f', '--format', type=str, default='cube',
                                choices=['cube', '3dl', 'clf'],
                                help='Output format (default: cube)')
    extract_parser.add_argument('-s', '--size', type=int, default=33,
                                choices=[17, 33, 65],
                                help='LUT grid size (default: 33)')
    extract_parser.add_argument('--strength', type=float, default=1.0,
                                help='Style intensity (0-1, default: 1.0)')
    extract_parser.add_argument('--title', type=str, default=None,
                                help='LUT title')
    extract_parser.add_argument('--description', type=str, default=None,
                                help='LUT description')
    extract_parser.add_argument('--analyze', action='store_true',
                                help='Output style analysis JSON alongside LUT')
    extract_parser.add_argument('--baseline-image', type=str, default=None,
                                help='Custom neutral baseline reference image')
    
    return parser


def cmd_generate(args: argparse.Namespace) -> int:
    """执行 generate 命令"""
    source_path = Path(args.source)
    target_path = Path(args.target)
    output_path = Path(args.output)
    
    if not source_path.exists():
        print(f"Error: Source image not found: {source_path}")
        return 1
    
    if not target_path.exists():
        print(f"Error: Target image not found: {target_path}")
        return 1
    
    print(f"Generating LUT from {source_path.name} -> {target_path.name}")
    print(f"Grid size: {args.size}, Strength: {args.strength}")
    
    # 生成 LUT
    lut_config = LUT3DConfig(grid_size=args.size)
    generator = LUT3DGenerator(lut_config)
    
    lut_data = generator.generate_from_images(source_path, target_path, args.strength)
    
    # 设置元数据
    metadata = {
        'title': args.title or f"{source_path.stem}_to_{target_path.stem}",
        'description': args.description or f"LUT generated from {source_path.name}"
    }
    
    # 导出 LUT
    exporter = LUTExporter(lut_data, metadata)
    
    # 根据格式自动添加扩展名
    if output_path.suffix == '':
        ext_map = {'cube': '.cube', '3dl': '.3dl', 'clf': '.clf'}
        output_path = output_path.with_suffix(ext_map[args.format])
    
    exporter.export(output_path, format=args.format)
    print(f"LUT saved to: {output_path}")
    
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """执行 analyze 命令"""
    image_path = Path(args.image)
    
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        return 1
    
    print(f"Analyzing: {image_path.name}")
    
    analyzer = ColorAnalyzer(use_colour=args.use_colour)
    result = analyzer.analyze(image_path)
    
    output = result.to_dict()
    
    if args.output:
        import json
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Analysis saved to: {output_path}")
    else:
        import json
        print(json.dumps(output, indent=2))
    
    return 0


def cmd_transfer(args: argparse.Namespace) -> int:
    """执行 transfer 命令"""
    import numpy as np
    import cv2
    
    source_path = Path(args.source)
    target_path = Path(args.target)
    output_path = Path(args.output)
    
    if not source_path.exists():
        print(f"Error: Source image not found: {source_path}")
        return 1
    
    if not target_path.exists():
        print(f"Error: Target image not found: {target_path}")
        return 1
    
    print(f"Applying color transfer: {source_path.name} -> {target_path.name}")
    
    transfer = ReinhardColorTransfer()
    config = TransferConfig(strength=args.strength)
    
    result = transfer.transfer_images(source_path, target_path, config)
    
    # 保存结果
    rgb_uint8 = result.to_rgb_uint8()
    rgb_bgr = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(output_path), rgb_bgr)
    
    print(f"Transfer result saved to: {output_path}")
    
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """执行 extract 命令 - 单图风格提取"""
    image_path = Path(args.image)
    output_path = Path(args.output)
    
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        return 1
    
    print(f"Extracting style from: {image_path.name}")
    print(f"Grid size: {args.size}, Strength: {args.strength}")
    
    # 创建自定义基准（如果指定）
    baseline = None
    if args.baseline_image:
        baseline_path = Path(args.baseline_image)
        if baseline_path.exists():
            baseline = NeutralBaseline.from_reference_image(baseline_path)
            print(f"Using custom baseline from: {baseline_path.name}")
        else:
            print(f"Warning: Baseline image not found: {baseline_path}, using default")
    
    # 提取风格并生成 LUT
    extractor = StyleExtractor(
        baseline=baseline,
        grid_size=args.size,
        strength=args.strength
    )
    
    result = extractor.generate_lut(image_path, args.strength)
    
    # 设置元数据
    metadata = {
        'title': args.title or f"Style_{image_path.stem}",
        'description': args.description or result.metadata.get('description', '')
    }
    
    # 导出 LUT
    exporter = LUTExporter(result.style_lut_data, metadata)
    
    # 根据格式自动添加扩展名
    if output_path.suffix == '':
        ext_map = {'cube': '.cube', '3dl': '.3dl', 'clf': '.clf'}
        output_path = output_path.with_suffix(ext_map[args.format])
    
    exporter.export(output_path, format=args.format)
    print(f"LUT saved to: {output_path}")
    
    # 输出风格分析（如果请求）
    if args.analyze:
        analysis_path = output_path.with_suffix('.json')
        analysis_data = extractor.analyze_image(image_path)
        with open(analysis_path, 'w') as f:
            json.dump(analysis_data, f, indent=2)
        print(f"Style analysis saved to: {analysis_path}")
    
    # 输出风格特征摘要
    print(f"\nStyle Summary:")
    print(f"  - Tone shift: L={result.features.tone_shift_L:.1f}, "
          f"a={result.features.tone_shift_a:.1f}, b={result.features.tone_shift_b:.1f}")
    print(f"  - Contrast ratio: {result.features.contrast:.2f}")
    print(f"  - Saturation: {result.features.saturation:.2f}")
    print(f"  - Warmth: {result.features.warmth:.2f} ({'warm' if result.features.warmth > 0.2 else 'cool' if result.features.warmth < -0.2 else 'neutral'})")
    print(f"  - Description: {result.metadata.get('description', 'N/A')}")
    
    return 0


def cmd_video_generate(args: argparse.Namespace) -> int:
    """执行 video-generate 命令"""
    from lut_generator.video.analyzer import VideoColorAnalyzer
    from lut_generator.video.frame_extractor import ExtractorConfig
    from lut_generator.lut.exporter import LUTExporter
    
    source_path = Path(args.source)
    target_path = Path(args.target) if args.target else None
    output_path = Path(args.output)
    
    if not source_path.exists():
        print(f"Error: Source not found: {source_path}")
        return 1
    
    if target_path and not target_path.exists():
        print(f"Error: Target not found: {target_path}")
        return 1
    
    # 配置帧提取
    ext_config = ExtractorConfig(
        strategy=args.strategy,
        sample_rate=args.sample_rate,
        max_frames=args.max_frames,
        scene_threshold=args.scene_threshold
    )
    
    analyzer = VideoColorAnalyzer(extractor_config=ext_config)
    
    # 判断输入类型
    video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
    source_is_video = source_path.suffix.lower() in video_exts
    target_is_video = target_path and target_path.suffix.lower() in video_exts
    
    print(f"Source: {source_path.name} ({'video' if source_is_video else 'image'})")
    if target_path:
        print(f"Target: {target_path.name} ({'video' if target_is_video else 'image'})")
    print(f"Strategy: {args.strategy} | Sample rate: {args.sample_rate}fps | Max frames: {args.max_frames}")
    print(f"Generating {args.size}x{args.size}x{args.size} LUT...")
    
    if source_is_video and target_is_video:
        # 视频→视频
        lut = analyzer.generate_lut_from_videos(
            source_path, target_path,
            lut_size=args.size,
            strength=args.strength
        )
    elif source_is_video and not target_is_video:
        # 视频→图片（视频为源）
        lut = analyzer.generate_lut_from_video_and_image(
            source_path, target_path,
            lut_size=args.size,
            strength=args.strength,
            video_is_source=True
        )
    elif not source_is_video and target_is_video:
        # 图片→视频
        lut = analyzer.generate_lut_from_video_and_image(
            target_path, source_path,
            lut_size=args.size,
            strength=args.strength,
            video_is_source=False
        )
    else:
        # 图片→图片（回退到普通 generate）
        print("Both inputs are images, using image generate mode...")
        return cmd_generate(args)
    
    # 导出 LUT
    metadata = {
        'title': args.title or f"Video_{source_path.stem}",
        'description': f"LUT from {source_path.name}" + (f" → {target_path.name}" if target_path else ""),
        'strategy': args.strategy,
        'sample_rate': args.sample_rate,
        'frames_sampled': analyzer.frame_extractor.config.max_frames
    }
    
    exporter = LUTExporter(lut, metadata)
    
    if output_path.suffix == '':
        ext_map = {'cube': '.cube', '3dl': '.3dl', 'clf': '.clf'}
        output_path = output_path.with_suffix(ext_map[args.format])
    
    exporter.export(output_path, format=args.format)
    print(f"LUT saved to: {output_path}")
    
    return 0


def cmd_video_extract(args: argparse.Namespace) -> int:
    """执行 video-extract 命令 - 单视频风格提取"""
    from lut_generator.video.analyzer import VideoColorAnalyzer
    from lut_generator.video.frame_extractor import ExtractorConfig
    from lut_generator.core.style_extractor import StyleExtractor, NeutralBaseline
    from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig
    from lut_generator.lut.exporter import LUTExporter
    
    video_path = Path(args.video)
    output_path = Path(args.output)
    
    if not video_path.exists():
        print(f"Error: Video not found: {video_path}")
        return 1
    
    # 配置帧提取
    ext_config = ExtractorConfig(
        strategy='scene' if args.scene_threshold > 0 else 'uniform',
        sample_rate=args.sample_rate,
        max_frames=args.max_frames,
        scene_threshold=args.scene_threshold
    )
    
    analyzer = VideoColorAnalyzer(extractor_config=ext_config)
    
    print(f"Extracting style from: {video_path.name}")
    print(f"Strategy: scene | Sample rate: {args.sample_rate}fps")
    
    # 分析视频
    video_stats = analyzer.analyze_video(video_path)
    print(f"Analyzed {video_stats.total_frames_analyzed} frames")
    print(f"Mean Lab: L={video_stats.mean_L:.1f}, a={video_stats.mean_a:.1f}, b={video_stats.mean_b:.1f}")
    
    # 使用 neutral baseline 生成 LUT
    baseline = NeutralBaseline()
    extractor = StyleExtractor(
        baseline=baseline,
        grid_size=args.size,
        strength=args.strength
    )
    
    # 从视频统计创建伪结果
    from lut_generator.analysis.analyzer import AnalysisResult
    from dataclasses import replace
    
    # 用视频聚合统计创建 ColorStatistics
    color_stats = video_stats.to_color_statistics()
    
    # 生成 LUT
    lut_config = LUT3DConfig(grid_size=args.size)
    generator = LUT3DGenerator(lut_config)
    
    # 使用 neutral baseline 的统计作为 source，视频统计作为 target
    from lut_generator.core.reinhard import ColorStatistics
    neutral_stats = ColorStatistics(
        mean_L=50.0, mean_a=0.0, mean_b=0.0,
        std_L=30.0, std_a=30.0, std_b=30.0,
        var_L=900.0, var_a=900.0, var_b=900.0
    )
    
    lut = generator.generate_from_stats(neutral_stats, color_stats, args.strength)
    
    # 导出
    metadata = {
        'title': f"VideoStyle_{video_path.stem}",
        'description': f"Style extracted from {video_path.name}",
        'frames_analyzed': video_stats.total_frames_analyzed
    }
    
    exporter = LUTExporter(lut, metadata)
    
    if output_path.suffix == '':
        ext_map = {'cube': '.cube', '3dl': '.3dl', 'clf': '.clf'}
        output_path = output_path.with_suffix(ext_map[args.format])
    
    exporter.export(output_path, format=args.format)
    print(f"LUT saved to: {output_path}")
    
    if args.analyze:
        analysis_path = output_path.with_suffix('.json')
        analysis_data = {
            'video': str(video_path),
            'total_frames_analyzed': video_stats.total_frames_analyzed,
            'mean': {'L': video_stats.mean_L, 'a': video_stats.mean_a, 'b': video_stats.mean_b},
            'std': {'L': video_stats.std_L, 'a': video_stats.std_a, 'b': video_stats.std_b},
            'var': {'L': video_stats.var_L, 'a': video_stats.var_a, 'b': video_stats.var_b}
        }
        with open(analysis_path, 'w') as f:
            json.dump(analysis_data, f, indent=2)
        print(f"Analysis saved to: {analysis_path}")
    
    return 0


def cli(args: Optional[list] = None) -> int:
    """
    CLI 入口函数
    
    Args:
        args: 命令行参数列表（用于测试），None 时使用 sys.argv
        
    Returns:
        退出码
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    if parsed_args.command is None:
        parser.print_help()
        return 0
    
    commands = {
        'generate': cmd_generate,
        'analyze': cmd_analyze,
        'transfer': cmd_transfer,
        'extract': cmd_extract,
        'video-generate': cmd_video_generate,
        'video-extract': cmd_video_extract,
    }
    
    return commands[parsed_args.command](parsed_args)


def main():
    """主入口"""
    try:
        exit_code = cli()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        exit_code = 130
    except Exception as e:
        print(f"Unhandled error: {e}")
        import traceback
        traceback.print_exc()
        exit_code = 1
    finally:
        # 确保所有资源被正确释放
        pass
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
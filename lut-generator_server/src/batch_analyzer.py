"""
批量图片分析模块 - Batch Analyzer

负责：
- 目录批量图片加载
- 并行/串行分析处理
- 异常处理（无效图片跳过 + 日志）
- 分析结果聚合

依赖：
- color_analyzer: 单图色彩分析
- pathlib: 路径处理
- logging: 日志记录
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Iterator
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from color_analyzer import ColorAnalyzer, AnalysisResult, ColorStatistics

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ImageInfo:
    """图片信息"""
    path: Path
    valid: bool
    error_message: Optional[str] = None
    analysis_result: Optional[AnalysisResult] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        result = {
            'path': str(self.path),
            'valid': self.valid,
        }
        if self.error_message:
            result['error_message'] = self.error_message
        if self.analysis_result:
            result['analysis_result'] = self.analysis_result.to_dict()
        return result


@dataclass
class BatchAnalysisResult:
    """批量分析结果"""
    total_images: int
    valid_images: int
    failed_images: int
    image_results: List[ImageInfo] = field(default_factory=list)
    
    # 聚合统计（仅针对有效图片）
    aggregated_statistics: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'total_images': self.total_images,
            'valid_images': self.valid_images,
            'failed_images': self.failed_images,
            'image_results': [img.to_dict() for img in self.image_results],
            'aggregated_statistics': self.aggregated_statistics
        }
    
    def get_valid_results(self) -> List[AnalysisResult]:
        """获取所有有效的分析结果"""
        return [
            img.analysis_result 
            for img in self.image_results 
            if img.valid and img.analysis_result is not None
        ]
    
    def get_valid_paths(self) -> List[Path]:
        """获取所有有效图片的路径"""
        return [
            img.path 
            for img in self.image_results 
            if img.valid
        ]


class BatchAnalyzer:
    """
    批量图片分析器
    
    支持：
    - 目录扫描
    - 多进程并行分析
    - 异常处理和日志记录
    - 结果聚合
    """
    
    # 支持的图片格式
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    
    def __init__(self, use_colour: bool = True, max_workers: int = 4):
        """
        初始化批量分析器
        
        Args:
            use_colour: 是否使用 colour-science 库
            max_workers: 最大并行工作线程数
        """
        self.use_colour = use_colour
        self.max_workers = max_workers
        self.analyzer = ColorAnalyzer(use_colour=use_colour)
        logger.info(f"BatchAnalyzer initialized (workers={max_workers}, use_colour={use_colour})")
    
    def scan_directory(self, directory: Union[str, Path], recursive: bool = False) -> List[Path]:
        """
        扫描目录获取所有图片文件
        
        Args:
            directory: 目录路径
            recursive: 是否递归扫描子目录
            
        Returns:
            图片文件路径列表
        """
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        
        image_paths = []
        
        if recursive:
            # 递归扫描
            for pattern in ['**/*' + ext for ext in self.SUPPORTED_FORMATS]:
                image_paths.extend(directory.glob(pattern))
        else:
            # 仅扫描当前目录
            for ext in self.SUPPORTED_FORMATS:
                image_paths.extend(directory.glob('*' + ext))
                # 同时支持大写扩展名
                image_paths.extend(directory.glob('*' + ext.upper()))
        
        # 去重并排序
        image_paths = sorted(set(image_paths))
        logger.info(f"Found {len(image_paths)} images in {directory}")
        
        return image_paths
    
    def analyze_single(self, image_path: Union[str, Path]) -> ImageInfo:
        """
        分析单张图片（带异常处理）
        
        Args:
            image_path: 图片路径
            
        Returns:
            ImageInfo 对象
        """
        image_path = Path(image_path)
        
        try:
            # 检查文件是否存在
            if not image_path.exists():
                logger.warning(f"File not found: {image_path}")
                return ImageInfo(
                    path=image_path,
                    valid=False,
                    error_message="File not found"
                )
            
            # 检查扩展名
            if image_path.suffix.lower() not in self.SUPPORTED_FORMATS:
                logger.warning(f"Unsupported format: {image_path}")
                return ImageInfo(
                    path=image_path,
                    valid=False,
                    error_message=f"Unsupported format: {image_path.suffix}"
                )
            
            # 执行分析
            result = self.analyzer.analyze(image_path)
            
            logger.info(f"Successfully analyzed: {image_path}")
            return ImageInfo(
                path=image_path,
                valid=True,
                analysis_result=result
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze {image_path}: {e}")
            return ImageInfo(
                path=image_path,
                valid=False,
                error_message=str(e)
            )
    
    def analyze_batch(
        self, 
        image_paths: List[Union[str, Path]], 
        parallel: bool = True
    ) -> BatchAnalysisResult:
        """
        批量分析多张图片
        
        Args:
            image_paths: 图片路径列表
            parallel: 是否并行处理
            
        Returns:
            BatchAnalysisResult 对象
        """
        logger.info(f"Starting batch analysis of {len(image_paths)} images")
        
        results: List[ImageInfo] = []
        
        if parallel and len(image_paths) > 1:
            # 并行处理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_path = {
                    executor.submit(self.analyze_single, path): path 
                    for path in image_paths
                }
                
                # 收集结果
                for future in as_completed(future_to_path):
                    result = future.result()
                    results.append(result)
        else:
            # 串行处理
            for path in image_paths:
                result = self.analyze_single(path)
                results.append(result)
        
        # 统计
        valid_count = sum(1 for r in results if r.valid)
        failed_count = len(results) - valid_count
        
        batch_result = BatchAnalysisResult(
            total_images=len(image_paths),
            valid_images=valid_count,
            failed_images=failed_count,
            image_results=results
        )
        
        logger.info(f"Batch analysis complete: {valid_count} valid, {failed_count} failed")
        
        return batch_result
    
    def analyze_directory(
        self, 
        directory: Union[str, Path], 
        recursive: bool = False,
        parallel: bool = True
    ) -> BatchAnalysisResult:
        """
        分析整个目录的图片
        
        Args:
            directory: 目录路径
            recursive: 是否递归扫描子目录
            parallel: 是否并行处理
            
        Returns:
            BatchAnalysisResult 对象
        """
        # 扫描目录
        image_paths = self.scan_directory(directory, recursive=recursive)
        
        if not image_paths:
            logger.warning(f"No images found in {directory}")
            return BatchAnalysisResult(
                total_images=0,
                valid_images=0,
                failed_images=0,
                image_results=[]
            )
        
        # 批量分析
        return self.analyze_batch(image_paths, parallel=parallel)
    
    def aggregate_statistics(
        self, 
        results: List[AnalysisResult],
        weights: Optional[List[float]] = None
    ) -> Dict:
        """
        聚合多个分析结果的统计信息
        
        Args:
            results: 分析结果列表
            weights: 权重列表（可选，用于加权平均）
            
        Returns:
            聚合后的统计字典
        """
        if not results:
            return {}
        
        if weights is None:
            # 等权重
            weights = [1.0] * len(results)
        
        if len(weights) != len(results):
            raise ValueError(f"weights length ({len(weights)}) must match results length ({len(results)})")
        
        # 归一化权重
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # 加权平均统计
        mean_L = sum(r.statistics.mean_L * w for r, w in zip(results, normalized_weights))
        mean_a = sum(r.statistics.mean_a * w for r, w in zip(results, normalized_weights))
        mean_b = sum(r.statistics.mean_b * w for r, w in zip(results, normalized_weights))
        
        std_L = sum(r.statistics.std_L * w for r, w in zip(results, normalized_weights))
        std_a = sum(r.statistics.std_a * w for r, w in zip(results, normalized_weights))
        std_b = sum(r.statistics.std_b * w for r, w in zip(results, normalized_weights))
        
        var_L = sum(r.statistics.var_L * w for r, w in zip(results, normalized_weights))
        var_a = sum(r.statistics.var_a * w for r, w in zip(results, normalized_weights))
        var_b = sum(r.statistics.var_b * w for r, w in zip(results, normalized_weights))
        
        # 平均色域覆盖
        avg_gamut = sum(r.distribution.gamut_coverage * w for r, w in zip(results, normalized_weights))
        
        # 平均色彩熵
        avg_entropy = sum(r.distribution.color_entropy * w for r, w in zip(results, normalized_weights))
        
        return {
            'mean': [mean_L, mean_a, mean_b],
            'std': [std_L, std_a, std_b],
            'var': [var_L, var_a, var_b],
            'avg_gamut_coverage': avg_gamut,
            'avg_color_entropy': avg_entropy,
            'num_images': len(results)
        }
    
    def save_results(
        self, 
        result: BatchAnalysisResult, 
        output_path: Union[str, Path],
        format: str = 'json'
    ) -> None:
        """
        保存分析结果到文件
        
        Args:
            result: 批量分析结果
            output_path: 输出文件路径
            format: 输出格式（'json' 或 'txt'）
        """
        output_path = Path(output_path)
        
        if format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to {output_path}")
        elif format == 'txt':
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"Total images: {result.total_images}\n")
                f.write(f"Valid images: {result.valid_images}\n")
                f.write(f"Failed images: {result.failed_images}\n\n")
                
                for img in result.image_results:
                    status = "✓" if img.valid else "✗"
                    f.write(f"{status} {img.path}\n")
                    if img.error_message:
                        f.write(f"  Error: {img.error_message}\n")
            logger.info(f"Results saved to {output_path}")
        else:
            raise ValueError(f"Unsupported format: {format}")


def analyze_directory_batch(
    directory: Union[str, Path],
    recursive: bool = False,
    parallel: bool = True,
    max_workers: int = 4,
    use_colour: bool = True
) -> BatchAnalysisResult:
    """
    便捷函数：批量分析目录中的所有图片
    
    Args:
        directory: 目录路径
        recursive: 是否递归扫描
        parallel: 是否并行处理
        max_workers: 最大工作线程数
        use_colour: 是否使用 colour-science
        
    Returns:
        BatchAnalysisResult 对象
    """
    analyzer = BatchAnalyzer(use_colour=use_colour, max_workers=max_workers)
    return analyzer.analyze_directory(directory, recursive=recursive, parallel=parallel)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        directory = sys.argv[1]
        recursive = '--recursive' in sys.argv or '-r' in sys.argv
        
        print(f"Analyzing directory: {directory}")
        if recursive:
            print("Mode: Recursive")
        
        result = analyze_directory_batch(directory, recursive=recursive)
        
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
    else:
        print("Usage: python batch_analyzer.py <directory> [-r|--recursive]")

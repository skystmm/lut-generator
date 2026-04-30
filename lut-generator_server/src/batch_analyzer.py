"""
批量图片分析模块 - Batch Analyzer

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.analysis.batch_analyzer` instead.
"""
import warnings
warnings.warn(
    "Importing from 'batch_analyzer' is deprecated. Use 'lut_generator.analysis.batch_analyzer' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.analysis.batch_analyzer import (
    BatchAnalyzer,
    BatchAnalysisResult,
    ImageInfo,
    analyze_directory_batch,
)

__all__ = [
    'BatchAnalyzer',
    'BatchAnalysisResult',
    'ImageInfo',
    'analyze_directory_batch',
]

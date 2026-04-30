"""
色彩分析模块 - Color Analyzer

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.analysis.analyzer` instead.
"""
import warnings
warnings.warn(
    "Importing from 'color_analyzer' is deprecated. Use 'lut_generator.analysis.analyzer' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.analysis.analyzer import (
    ColorAnalyzer,
    AnalysisResult,
    ColorHistogram,
    ColorDistribution,
    analyze_image,
)
from lut_generator.core.reinhard import ColorStatistics

__all__ = [
    'ColorAnalyzer',
    'AnalysisResult',
    'ColorHistogram',
    'ColorDistribution',
    'ColorStatistics',
    'analyze_image',
]

"""
LUT Generator - Image analysis based 3D LUT generator

A professional tool for generating 3D LUTs (.cube format) from reference images
using the Reinhard color transfer algorithm.
"""

import warnings

# 静默 colour-science 启动时的 ColourUsageWarning("Matplotlib" / "SciPy" not available)
# 这些是 `colour` 包对 optional 依赖的软提示,跟 lut_generator 实际功能无关;
# ColourUsageWarning 直接继承 Warning(不是 UserWarning),用 module 正则匹配。
warnings.filterwarnings(
    'ignore',
    category=Warning,
    module=r'colour\.utilities\.verbose',
)

__version__ = "0.2.0"
__author__ = "RD Agent"

from .core.color_space import ColorSpaceConverter
from .core.reinhard import ReinhardColorTransfer, ColorStatistics, TransferConfig
from .lut.lut3d import LUT3DGenerator, LUT3DConfig
from .lut.exporter import LUTExporter
from .analysis.analyzer import ColorAnalyzer, analyze_image

__all__ = [
    "ColorSpaceConverter",
    "ReinhardColorTransfer",
    "ColorStatistics",
    "TransferConfig",
    "LUT3DGenerator",
    "LUT3DConfig",
    "LUTExporter",
    "ColorAnalyzer",
    "analyze_image",
]
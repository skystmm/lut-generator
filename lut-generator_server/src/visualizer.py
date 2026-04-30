"""
可视化模块 - Visualizer

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.utils.visualizer` instead.
"""
import warnings
warnings.warn(
    "Importing from 'visualizer' is deprecated. Use 'lut_generator.utils.visualizer' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.utils.visualizer import (
    ColorVisualizer,
    VisualizationConfig,
    VisualizationResult,
)

__all__ = [
    'ColorVisualizer',
    'VisualizationConfig',
    'VisualizationResult',
]

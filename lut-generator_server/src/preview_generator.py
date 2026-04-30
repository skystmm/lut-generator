"""
预览图生成模块 - PreviewGenerator

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.preview.generator` instead.
"""
import warnings
warnings.warn(
    "Importing from 'preview_generator' is deprecated. Use 'lut_generator.preview.generator' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.preview.generator import (
    PreviewGenerator,
    ComparisonConfig,
    PreviewResult,
)

__all__ = [
    'PreviewGenerator',
    'ComparisonConfig',
    'PreviewResult',
]

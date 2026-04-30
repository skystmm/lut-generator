"""
3D LUT 生成器 - LUT3DGenerator

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.lut.lut3d` instead.
"""
import warnings
warnings.warn(
    "Importing from 'lut3d_generator' is deprecated. Use 'lut_generator.lut.lut3d' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.lut.lut3d import (
    LUT3DGenerator,
    LUT3DConfig,
    LUT3DMetadata,
    generate_lut_3d,
)

__all__ = [
    'LUT3DGenerator',
    'LUT3DConfig',
    'LUT3DMetadata',
    'generate_lut_3d',
]

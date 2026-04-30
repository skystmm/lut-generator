"""
LUT 应用模块 - LUTApplier

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.lut.applier` instead.
"""
import warnings
warnings.warn(
    "Importing from 'lut_applier' is deprecated. Use 'lut_generator.lut.applier' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.lut.applier import (
    LUTApplier,
    ApplyConfig,
    ApplyResult,
    apply_lut_to_image,
)

__all__ = [
    'LUTApplier',
    'ApplyConfig',
    'ApplyResult',
    'apply_lut_to_image',
]

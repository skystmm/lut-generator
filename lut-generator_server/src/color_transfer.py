"""
色彩迁移模块 - Color Transfer

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.core.reinhard` instead.
"""
import warnings
warnings.warn(
    "Importing from 'color_transfer' is deprecated. Use 'lut_generator.core.reinhard' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.core.reinhard import (
    ReinhardColorTransfer,
    TransferConfig,
    TransferResult,
    ColorStatistics,
    LUTTransformBuilder,
)
import numpy as np
from typing import Union, Tuple
from pathlib import Path


def transfer_colors(source_path: Union[str, Path],
                    target_path: Union[str, Path],
                    strength: float = 1.0) -> Tuple[np.ndarray, dict]:
    """Backward-compatible convenience function for color transfer."""
    config = TransferConfig(strength=strength)
    transfer = ReinhardColorTransfer(config)
    result = transfer.transfer_images(source_path, target_path)
    return result.rgb_result, result.transform_params


__all__ = [
    'ReinhardColorTransfer',
    'TransferConfig',
    'TransferResult',
    'ColorStatistics',
    'LUTTransformBuilder',
    'transfer_colors',
]

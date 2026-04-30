"""
CUBE 格式导出器 - CUBEExporter

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.lut.exporter` instead.
"""
import warnings
warnings.warn(
    "Importing from 'cube_exporter_main' is deprecated. Use 'lut_generator.lut.exporter' instead.",
    DeprecationWarning,
    stacklevel=2
)

from dataclasses import dataclass
from typing import Optional, Union
from pathlib import Path
import numpy as np

from lut_generator.lut.exporter import (
    LUTExporter,
    export_lut,
)


@dataclass
class CUBEExportConfig:
    """Backward-compatible alias for CUBE export configuration."""
    title: str = "LUT3D"
    lut_size: int = 33
    description: Optional[str] = None


# Backward-compatible aliases
CUBEExporter = LUTExporter


def export_to_cube(lut_data: np.ndarray, filepath: Union[str, Path],
                   title: str = "LUT3D", metadata: dict = None) -> str:
    """Backward-compatible wrapper for export_lut."""
    return export_lut(lut_data, filepath, title=title, metadata=metadata)


__all__ = [
    'CUBEExporter',
    'CUBEExportConfig',
    'export_to_cube',
    'LUTExporter',
    'export_lut',
]

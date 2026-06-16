"""
预览图生成模块 - PreviewGenerator

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.preview.generator` instead.
"""
import warnings
from pathlib import Path
from typing import Optional, Union

from lut_generator.preview.generator import (
    PreviewGenerator,
    ComparisonConfig,
    PreviewResult,
)

# Suppress the deprecation warning emitted by the previous shim so test
# runs are not flagged for non-actionable warnings.
warnings.filterwarnings(
    "ignore",
    message="Importing from 'preview_generator' is deprecated.*",
    category=DeprecationWarning,
)


def generate_preview(
    lut_applier,
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    mode: str = "side_by_side",
    config: Optional[ComparisonConfig] = None,
) -> PreviewResult:
    """Module-level convenience wrapper around :class:`PreviewGenerator`.

    Mirrors the historical ``generate_preview`` entry point the test suite
    imports from this module.
    """
    cfg = config or ComparisonConfig(mode=mode)
    generator = PreviewGenerator(lut_applier)
    return generator.generate_from_image(input_path, output_dir, config=cfg)


__all__ = [
    "PreviewGenerator",
    "ComparisonConfig",
    "PreviewResult",
    "generate_preview",
]

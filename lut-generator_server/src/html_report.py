"""
HTML 报告导出模块 - HTMLReportGenerator

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.utils.html_report` instead.
"""
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Union

from lut_generator.utils.html_report import (
    HTMLReportGenerator,
    ReportConfig,
    ReportData,
    ReportResult,
)

# Suppress the deprecation warning emitted by the previous shim so test
# runs are not flagged for non-actionable warnings.
warnings.filterwarnings(
    "ignore",
    message="Importing from 'html_report' is deprecated.*",
    category=DeprecationWarning,
)


# ----------------------------------------------------------------------
# Backward-compatible aliases
# ----------------------------------------------------------------------

# Some tests pre-date the rename of ``include_slider`` -> ``no_slider`` and
# expect to construct ``ReportConfig(include_slider=False)``; the core
# dataclass already mirrors the two fields in ``__post_init__``, so we just
# pass the kwarg through unchanged here.


# Some test cases also look for a ``generate_html_report`` convenience
# function in this module, but the canonical path is the generator class.
# Provide a thin wrapper to bridge the gap.
def generate_html_report(
    original_path: Union[str, Path],
    processed_path: Union[str, Path],
    output_path: Union[str, Path],
    statistics: Optional[Dict[str, Any]] = None,
    lut_info: Optional[Dict[str, Any]] = None,
    processing_time: Optional[float] = None,
    theme: str = "dark",
) -> ReportResult:
    """Module-level convenience wrapper around :class:`HTMLReportGenerator`.

    Returns a :class:`ReportResult`; raises if generation fails.
    """
    config = ReportConfig(theme=theme)
    generator = HTMLReportGenerator(config)
    return generator.generate_from_paths(
        original_path,
        processed_path,
        output_path,
        statistics=statistics,
        lut_info=lut_info,
        processing_time=processing_time,
    )


__all__ = [
    "HTMLReportGenerator",
    "ReportConfig",
    "ReportData",
    "ReportResult",
    "generate_html_report",
]

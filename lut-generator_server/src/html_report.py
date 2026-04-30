"""
HTML 报告导出模块 - HTMLReportGenerator

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.utils.html_report` instead.
"""
import warnings
warnings.warn(
    "Importing from 'html_report' is deprecated. Use 'lut_generator.utils.html_report' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.utils.html_report import (
    HTMLReportGenerator,
    ReportConfig,
    ReportData,
    ReportResult,
)

__all__ = [
    'HTMLReportGenerator',
    'ReportConfig',
    'ReportData',
    'ReportResult',
]

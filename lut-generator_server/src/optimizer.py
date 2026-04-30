"""
性能优化模块 - Optimizer

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.utils.optimizer` instead.
"""
import warnings
warnings.warn(
    "Importing from 'optimizer' is deprecated. Use 'lut_generator.utils.optimizer' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.utils.optimizer import (
    PerformanceOptimizer,
    LUTCache,
    ChunkedImageProcessor,
    ParallelProcessor,
    CacheConfig,
    ParallelConfig,
    MemoryConfig,
    OptimizerStats,
)

__all__ = [
    'PerformanceOptimizer',
    'LUTCache',
    'ChunkedImageProcessor',
    'ParallelProcessor',
    'CacheConfig',
    'ParallelConfig',
    'MemoryConfig',
    'OptimizerStats',
]

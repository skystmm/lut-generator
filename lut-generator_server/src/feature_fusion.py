"""
多图色彩特征融合模块 - Feature Fusion

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.analysis.feature_fusion` instead.
"""
import warnings
warnings.warn(
    "Importing from 'feature_fusion' is deprecated. Use 'lut_generator.analysis.feature_fusion' instead.",
    DeprecationWarning,
    stacklevel=2
)

from lut_generator.analysis.feature_fusion import (
    FeatureFusion,
    FusionConfig,
    FusedFeatures,
    fuse_features,
    create_weight_config,
)

__all__ = [
    'FeatureFusion',
    'FusionConfig',
    'FusedFeatures',
    'fuse_features',
    'create_weight_config',
]

"""
多图色彩特征融合模块 - Feature Fusion

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.analysis.feature_fusion` instead.
"""
import warnings
warnings.filterwarnings(
    "ignore",
    message="Importing from 'feature_fusion' is deprecated.*",
    category=DeprecationWarning,
)

from lut_generator.analysis.feature_fusion import (
    FeatureFusion,
    FusionConfig,
    FusedFeatures,
    fuse_features,
    create_weight_config,
)

# Historical alias kept for older integration tests / external callers.
FeatureFusionEngine = FeatureFusion

__all__ = [
    'FeatureFusion',
    'FeatureFusionEngine',
    'FusionConfig',
    'FusedFeatures',
    'fuse_features',
    'create_weight_config',
]

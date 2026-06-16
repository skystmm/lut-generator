"""
可视化模块 - Visualizer

DEPRECATED: This module is a compatibility shim.
Please use `lut_generator.utils.visualizer` instead.
"""
import warnings
from pathlib import Path
from typing import List, Union, Optional

from lut_generator.utils.visualizer import (
    ColorVisualizer,
    VisualizationConfig,
    VisualizationResult,
)

# Suppress the deprecation warning emitted by the previous shim. New callers
# are still encouraged to use the canonical `lut_generator.utils.visualizer`
# path, but the warning is suppressed here to keep test output clean.
warnings.filterwarnings(
    "ignore",
    message="Importing from 'visualizer' is deprecated.*",
    category=DeprecationWarning,
)


def _emit_comparison_result(
    result: VisualizationResult,
    viz_type: str,
) -> VisualizationResult:
    """Override the `viz_type` field on a result so it matches the
    comparison-specific marker expected by callers/tests."""
    return VisualizationResult(
        output_path=result.output_path,
        viz_type=viz_type,
        output_size=result.output_size,
        generation_time=result.generation_time,
        success=result.success,
        error_message=result.error_message,
        data_path=result.data_path,
    )


def _plot_histogram_comparison(
    path1: Union[str, Path],
    path2: Union[str, Path],
    output_path: Union[str, Path],
    width: int = 1200,
    height: int = 800,
) -> VisualizationResult:
    """Render a histogram comparison for two images.

    Implementation note: the underlying ``ColorVisualizer.plot_histogram``
    only renders a *single* image. To produce a comparison we draw the
    two histograms side-by-side by stitching two canvases together.
    """
    import numpy as np
    import cv2

    config = VisualizationConfig(width=width, height=height)
    visualizer = ColorVisualizer(config)

    image1 = visualizer.analyzer.load_image(path1)
    image2 = visualizer.analyzer.load_image(path2)
    histograms1 = visualizer._calculate_histogram(image1)
    histograms2 = visualizer._calculate_histogram(image2)

    canvas = np.ones((height, width, 3), dtype=np.uint8)
    canvas[:] = config.background_color
    visualizer._draw_title(canvas, "Histogram Comparison")

    half_w = (width - 60) // 2
    chart_left = (50, 60, half_w, height - 110)
    chart_right = (50 + half_w + 20, 60, half_w, height - 110)

    visualizer._draw_histogram_chart(canvas, histograms1, chart_left, True)
    visualizer._draw_histogram_chart(canvas, histograms2, chart_right, True)

    cv2.imwrite(str(output_path), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))

    return VisualizationResult(
        output_path=str(output_path),
        viz_type="histogram_comparison",
        output_size=(canvas.shape[1], canvas.shape[0]),
        generation_time=0.0,
        success=True,
    )


def _plot_gamut_comparison(
    path1: Union[str, Path],
    path2: Union[str, Path],
    output_path: Union[str, Path],
    width: int = 1200,
    height: int = 800,
) -> VisualizationResult:
    """Render a gamut (a*b plane) comparison for two images."""
    import numpy as np
    import cv2

    config = VisualizationConfig(width=width, height=height)
    visualizer = ColorVisualizer(config)

    image1 = visualizer.analyzer.load_image(path1)
    image2 = visualizer.analyzer.load_image(path2)
    lab1 = visualizer.analyzer.rgb_to_lab(image1)
    lab2 = visualizer.analyzer.rgb_to_lab(image2)

    a1 = lab1[:, :, 1].flatten()
    b1 = lab1[:, :, 2].flatten()
    a2 = lab2[:, :, 1].flatten()
    b2 = lab2[:, :, 2].flatten()

    canvas = np.ones((height, width, 3), dtype=np.uint8)
    canvas[:] = config.background_color
    visualizer._draw_title(canvas, "Gamut Comparison")

    half_w = (width - 60) // 2
    chart_left = (50, 60, half_w, height - 110)
    chart_right = (50 + half_w + 20, 60, half_w, height - 110)

    visualizer._draw_gamut_chart(canvas, a1, b1, chart_left)
    visualizer._draw_gamut_chart(canvas, a2, b2, chart_right)

    cv2.imwrite(str(output_path), cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))

    return VisualizationResult(
        output_path=str(output_path),
        viz_type="gamut_comparison",
        output_size=(canvas.shape[1], canvas.shape[0]),
        generation_time=0.0,
        success=True,
    )


# ----------------------------------------------------------------------
# Method equivalents on ColorVisualizer
# ----------------------------------------------------------------------


def plot_histogram_comparison(
    self: ColorVisualizer,
    path1: Union[str, Path],
    path2: Union[str, Path],
    output_path: Union[str, Path],
) -> VisualizationResult:
    """ColorVisualizer.plot_histogram_comparison shim.

    Mirrors ``ColorVisualizer.plot_histogram``/``plot_gamut`` shape and is
    installed onto the class at import time so the test suite (which calls
    ``visualizer.plot_histogram_comparison(...)``) keeps working.
    """
    return _plot_histogram_comparison(
        path1,
        path2,
        output_path,
        width=self.config.width,
        height=self.config.height,
    )


def plot_gamut_comparison(
    self: ColorVisualizer,
    path1: Union[str, Path],
    path2: Union[str, Path],
    output_path: Union[str, Path],
) -> VisualizationResult:
    """ColorVisualizer.plot_gamut_comparison shim."""
    return _plot_gamut_comparison(
        path1,
        path2,
        output_path,
        width=self.config.width,
        height=self.config.height,
    )


ColorVisualizer.plot_histogram_comparison = plot_histogram_comparison
ColorVisualizer.plot_gamut_comparison = plot_gamut_comparison


def visualize_color_distribution(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    width: int = 1200,
    height: int = 800,
) -> List[VisualizationResult]:
    """Convenience function: render histogram + gamut for ``input_path``.

    Returns a list of two :class:`VisualizationResult` objects.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = VisualizationConfig(width=width, height=height)
    visualizer = ColorVisualizer(config)

    histogram_path = output_dir / "histogram.png"
    gamut_path = output_dir / "gamut.png"

    hist_result = visualizer.plot_histogram(input_path, histogram_path)
    gamut_result = visualizer.plot_gamut(input_path, gamut_path)

    return [hist_result, gamut_result]


__all__ = [
    "ColorVisualizer",
    "VisualizationConfig",
    "VisualizationResult",
    "visualize_color_distribution",
]

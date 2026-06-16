"""
Lightroom .xmp 预设文件写入器 - PresetXMPWriter

把 :class:`ParamSpace` (Basic + Tone Curve) 序列化为 Lightroom 7.3+ .xmp 格式。

参考: 路径 B 调研报告 §4.1(LR 7.3+ 格式)
    - Adobe 官方 XMP spec
    - Thomas Fitzgerald 博客
    - PixelPeeper .xmp viewer
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .preset_extractor import ParamSpace


# XMP 命名空间常量
_CR_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_XMP_NS = "adobe:ns:meta/"


@dataclass
class PresetMetadata:
    """预设元数据,会嵌入到 .xmp 文件名 / ProfileName 节点。"""
    title: str = "lut-generator-extracted"
    group: str = "lut-generator:PoC"
    process_version: str = "15.0"  # LR 13/14
    crs_version: str = "15.0"


class PresetXMPWriter:
    """把 :class:`ParamSpace` 写成 Lightroom 兼容的 .xmp preset 文件。

    实现注意:
        - Tone Curve 控制点(8 个,值域 [0,1])映射到 0-255 的整数端点串
        - Basic 滑块值域 [-100, 100] 直接写入 crs:XXX2012 属性
        - 输出 .xmp 文件用 UTF-8 编码
    """

    def __init__(self, metadata: Optional[PresetMetadata] = None):
        self.metadata = metadata or PresetMetadata()

    @staticmethod
    def _format_basic_value(value: float) -> str:
        """Basic 滑块值格式化为 1 位小数字符串。"""
        if abs(value) < 0.05:
            return "0"
        return f"{value:+.1f}"

    @staticmethod
    def _format_curve_points(control_points: Tuple[float, ...]) -> str:
        """8 个 [0, 1] 控制点 → "0,0 32,32 ... 255,255" 形式的端点串。

        实际 LR 用 0-255 整数端点。这里把 [0, 1] 映射到 [0, 255] 四舍五入。
        """
        if len(control_points) != 8:
            raise ValueError(f"expected 8 control points, got {len(control_points)}")
        # 8 个控制点对应 8 个 x 位置(均匀分布)
        x_positions = [0, 36, 73, 109, 146, 182, 219, 255]
        points: List[str] = []
        for x, y_norm in zip(x_positions, control_points):
            y = int(round(max(0.0, min(1.0, y_norm)) * 255))
            points.append(f"{x},{y}")
        return " ".join(points)

    def build_xmp(self, params: ParamSpace) -> str:
        """生成 .xmp 文件内容(字符串)。

        字段(LR 7.3+ 全集,2026-06-16 Phase 1.2 扩展):
            - 7 Basic: Exposure/Contrast/Highlights/Shadows/Whites/Blacks/Saturation
            - 2 Temp/Tint: Temperature/Tint
            - 4 Presence: Vibrance/Texture/Clarity/Dehaze
            - 24 HSL: 8 色 × Hue/Sat/Lum
            - 6 Color Grading: Shadows/Midtones/Highlights × Hue/Sat
            - 24 Tone Curve: RGB × 8 控制点
        """
        m = self.metadata

        # ---- Basic 7 维 ----
        basic = (
            f' crs:Exposure2012="{self._format_basic_value(params.exposure)}"'
            f' crs:Contrast2012="{self._format_basic_value(params.contrast)}"'
            f' crs:Highlights2012="{self._format_basic_value(params.highlights)}"'
            f' crs:Shadows2012="{self._format_basic_value(params.shadows)}"'
            f' crs:Whites2012="{self._format_basic_value(params.whites)}"'
            f' crs:Blacks2012="{self._format_basic_value(params.blacks)}"'
            f' crs:Saturation="{self._format_basic_value(params.saturation)}"'
        )

        # ---- Temp/Tint 2 维 ----
        # Temperature 范围 -100..+100(Kelvin offset),Tint 范围 -100..+100(绿-品)
        temp_tint = (
            f' crs:Temperature="{self._format_basic_value(params.temperature)}"'
            f' crs:Tint="{self._format_basic_value(params.tint)}"'
        )

        # ---- Presence 4 维 ----
        presence = (
            f' crs:Vibrance="{self._format_basic_value(params.vibrance)}"'
            f' crs:Texture="{self._format_basic_value(params.texture)}"'
            f' crs:Clarity2012="{self._format_basic_value(params.clarity)}"'
            f' crs:Dehaze="{self._format_basic_value(params.dehaze)}"'
        )

        # ---- HSL 24 维 (8 色 × Hue/Sat/Lum) ----
        # Adobe 字段命名: Hue/Saturation/LuminanceAdjustmentRed/Orange/Yellow/Green/Aqua/Blue/Purple/Magenta
        hsl_colors = [
            ('Red',     params.hsl_red_hue,     params.hsl_red_sat,     params.hsl_red_lum),
            ('Orange',  params.hsl_orange_hue,  params.hsl_orange_sat,  params.hsl_orange_lum),
            ('Yellow',  params.hsl_yellow_hue,  params.hsl_yellow_sat,  params.hsl_yellow_lum),
            ('Green',   params.hsl_green_hue,   params.hsl_green_sat,   params.hsl_green_lum),
            ('Aqua',    params.hsl_aqua_hue,    params.hsl_aqua_sat,    params.hsl_aqua_lum),
            ('Blue',    params.hsl_blue_hue,    params.hsl_blue_sat,    params.hsl_blue_lum),
            ('Purple',  params.hsl_purple_hue,  params.hsl_purple_sat,  params.hsl_purple_lum),
            ('Magenta', params.hsl_magenta_hue, params.hsl_magenta_sat, params.hsl_magenta_lum),
        ]
        hsl_parts = []
        for name, h, s, l in hsl_colors:
            hsl_parts.append(
                f' crs:HueAdjustment{name}="{self._format_basic_value(h)}"'
                f' crs:SaturationAdjustment{name}="{self._format_basic_value(s)}"'
                f' crs:LuminanceAdjustment{name}="{self._format_basic_value(l)}"'
            )
        hsl = ''.join(hsl_parts)

        # ---- Color Grading 6 维 (3 区 × Hue/Sat) ----
        # Adobe 字段: SplitToningShadow/HighlightHue/Sat, plus Midtone (later CC version)
        # LR 13+: ColorGradingShadow/Midtones/HighlightHue/Sat
        cg = (
            f' crs:SplitToningShadowHue="{int(params.cg_shadows_hue) % 360}"'
            f' crs:SplitToningShadowSaturation="{self._format_basic_value(params.cg_shadows_sat)}"'
            f' crs:SplitToningHighlightHue="{int(params.cg_highlights_hue) % 360}"'
            f' crs:SplitToningHighlightSaturation="{self._format_basic_value(params.cg_highlights_sat)}"'
            f' crs:SplitToningBalance="0"'
        )

        # ---- Tone Curve 24 维 ----
        curve_main = self._format_curve_points(params.curve_r)
        curve_r = self._format_curve_points(params.curve_r)
        curve_g = self._format_curve_points(params.curve_g)
        curve_b = self._format_curve_points(params.curve_b)

        # 拼装 .xmp(LR 7.3+ 字段顺序: Basic → Temp/Tint → Presence → HSL → CG → Curve)
        xmp = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<x:xmpmeta xmlns:x="{_XMP_NS}" x:xmptk="lut-generator 1.0">\n'
            f' <rdf:RDF xmlns:rdf="{_RDF_NS}">\n'
            f'  <rdf:Description rdf:about=""\n'
            f'    xmlns:crs="{_CR_NS}"\n'
            f'    crs:Version="{m.crs_version}"\n'
            f'    crs:ProcessVersion="{m.process_version}"\n'
            f'    crs:PresetType="Normal"'
            f'{basic}'
            f'{temp_tint}'
            f'{presence}'
            f'{hsl}\n'
            f'    crs:ToneCurveName2012="Custom"\n'
            f'    crs:ToneCurvePV2012="{curve_main}"\n'
            f'    crs:ToneCurvePV2012Red="{curve_r}"\n'
            f'    crs:ToneCurvePV2012Green="{curve_g}"\n'
            f'    crs:ToneCurvePV2012Blue="{curve_b}"\n'
            f'{cg}\n'
            f'    crs:HasSettings="True">\n'
            f'   <crs:Name>\n'
            f'    <rdf:Alt><rdf:li xml:lang="x-default">{_xml_escape(m.title)}</rdf:li></rdf:Alt>\n'
            f'   </crs:Name>\n'
            f'   <crs:Group>\n'
            f'    <rdf:Alt><rdf:li xml:lang="x-default">{_xml_escape(m.group)}</rdf:li></rdf:Alt>\n'
            f'   </crs:Group>\n'
            f'   <crs:SupportsAmount>True</crs:SupportsAmount>\n'
            f'  </rdf:Description>\n'
            f' </rdf:RDF>\n'
            f'</x:xmpmeta>\n'
        )
        return xmp

    def write(self, params: ParamSpace, output_path: Union[str, Path]) -> Path:
        """写 .xmp 文件,返回最终路径。"""
        output_path = Path(output_path)
        if output_path.suffix.lower() != ".xmp":
            output_path = output_path.with_suffix(".xmp")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        xmp = self.build_xmp(params)
        output_path.write_text(xmp, encoding="utf-8")
        return output_path


def _xml_escape(s: str) -> str:
    """最小 XML 文本转义(用于 title/group)。"""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


__all__ = ["PresetMetadata", "PresetXMPWriter"]

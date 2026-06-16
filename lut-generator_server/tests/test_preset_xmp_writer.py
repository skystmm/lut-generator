"""
Lightroom .xmp 写入器单元测试
"""

import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lut_generator.analysis.preset_xmp_writer import (
    PresetMetadata,
    PresetXMPWriter,
)
from lut_generator.analysis.preset_extractor import ParamSpace


class TestXMPWriter:
    def test_basic_xmp_structure(self, tmp_path):
        """生成的 .xmp 应有正确的根节点和命名空间。"""
        ps = ParamSpace()
        ps.exposure = 0.5
        writer = PresetXMPWriter(PresetMetadata(title="TestPreset"))
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        assert content.startswith("<?xml version")
        assert "adobe:ns:meta/" in content
        assert "ns.adobe.com/camera-raw-settings/1.0/" in content
        assert "<x:xmpmeta" in content
        assert "</x:xmpmeta>" in content

    def test_basic_values_written(self, tmp_path):
        """Basic 滑块值应被序列化。"""
        ps = ParamSpace()
        ps.exposure = 0.5
        ps.contrast = 18.0
        ps.shadows = 25.0
        ps.saturation = 12.0
        writer = PresetXMPWriter()
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        assert "Exposure2012" in content
        assert "Contrast2012" in content
        assert "Shadows2012" in content
        assert "Saturation" in content

    def test_temp_tint_written(self, tmp_path):
        """Temp/Tint 应被序列化(Phase 1.2 新增)。"""
        ps = ParamSpace()
        ps.temperature = 30.0
        ps.tint = -10.0
        writer = PresetXMPWriter()
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        assert "Temperature=" in content
        assert "Tint=" in content
        assert "+30" in content  # temperature
        assert "-10" in content  # tint

    def test_presence_written(self, tmp_path):
        """Presence 4 维应被序列化(Phase 1.2 新增)。"""
        ps = ParamSpace()
        ps.vibrance = 20.0
        ps.texture = -10.0
        ps.clarity = 15.0
        ps.dehaze = 5.0
        writer = PresetXMPWriter()
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        assert "Vibrance=" in content
        assert "Texture=" in content
        assert "Clarity2012=" in content
        assert "Dehaze=" in content

    def test_hsl_written(self, tmp_path):
        """HSL 8 色 × 3 维 = 24 字段应被序列化(Phase 1.2 新增)。"""
        ps = ParamSpace()
        ps.hsl_orange_hue = -20.0
        ps.hsl_orange_sat = 30.0
        ps.hsl_blue_sat = -50.0
        writer = PresetXMPWriter()
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        # 8 个颜色 × 3 字段 = 24 个 HueAdjustment/Saturation/Luminance 字段
        for color in ['Red', 'Orange', 'Yellow', 'Green', 'Aqua', 'Blue', 'Purple', 'Magenta']:
            assert f"HueAdjustment{color}=" in content, f"missing HueAdjustment{color}"
            assert f"SaturationAdjustment{color}=" in content
            assert f"LuminanceAdjustment{color}=" in content
        # 检查具体值
        assert "HueAdjustmentOrange=\"-20" in content
        assert "SaturationAdjustmentBlue=\"-50" in content

    def test_color_grading_written(self, tmp_path):
        """Color Grading 6 维应被序列化(Phase 1.2 新增)。"""
        ps = ParamSpace()
        ps.cg_shadows_hue = 220.0     # 冷蓝
        ps.cg_shadows_sat = -20.0
        ps.cg_highlights_hue = 40.0   # 暖黄
        ps.cg_highlights_sat = 25.0
        writer = PresetXMPWriter()
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        assert "SplitToningShadowHue=" in content
        assert "SplitToningShadowSaturation=" in content
        assert "SplitToningHighlightHue=" in content
        assert "SplitToningHighlightSaturation=" in content
        # Hue 应该是整数(0..360)
        assert 'SplitToningShadowHue="220"' in content
        assert 'SplitToningHighlightHue="40"' in content

    def test_full_xmp_parseable(self, tmp_path):
        """67 维全字段写出的 .xmp 应能 XML 解析。"""
        import xml.etree.ElementTree as ET
        ps = ParamSpace()
        ps.exposure = 0.5
        ps.temperature = 30.0
        ps.vibrance = 20.0
        ps.hsl_orange_sat = 25.0
        ps.cg_shadows_hue = 220.0
        writer = PresetXMPWriter()
        out = tmp_path / "test_full.xmp"
        writer.write(ps, out)
        # ElementTree 解析应不抛异常
        tree = ET.parse(str(out))
        # 验证至少 67 个 crs: 属性被写出
        desc = tree.getroot().find('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
        attrs_with_crs = [k for k in desc.attrib if 'camera-raw-settings' in k]
        # 7 Basic + 2 Temp/Tint + 4 Presence + 24 HSL + 4 CG + 4 Curve + 4 fixed = ~50+ attrs
        assert len(attrs_with_crs) >= 40, f"only {len(attrs_with_crs)} crs attrs"

    def test_curve_serialized(self, tmp_path):
        """Tone Curve 应被序列化为端点串。"""
        ps = ParamSpace()
        # 把 R 曲线第 4 个控制点设为 0.5,期望 y ≈ 128
        ps.curve_r = (0.0, 0.2, 0.4, 0.5, 0.7, 0.8, 0.9, 1.0)
        writer = PresetXMPWriter()
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        assert "ToneCurvePV2012=" in content
        assert "ToneCurvePV2012Red=" in content
        # 验证端点串包含 0-255 的 y 坐标
        match = re.search(r'ToneCurvePV2012Red="([^"]+)"', content)
        assert match is not None
        endpoints = match.group(1).split()
        assert len(endpoints) == 8  # 8 个端点
        # 端点 x 位置固定 0/36/73/109/146/182/219/255
        x_positions = [0, 36, 73, 109, 146, 182, 219, 255]
        for ep, expected_x in zip(endpoints, x_positions):
            x, y = ep.split(",")
            assert int(x) == expected_x
        # 第 4 个端点(curve_r[3]=0.5)应映射到 y ≈ 128
        x_y = endpoints[3].split(",")
        assert 125 <= int(x_y[1]) <= 130  # 0.5 * 255 ≈ 128

    def test_title_in_xmp(self, tmp_path):
        """title 应出现在 Name 节点。"""
        ps = ParamSpace()
        writer = PresetXMPWriter(PresetMetadata(title="MyVibeStyle"))
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        assert "MyVibeStyle" in content
        assert "<crs:Name>" in content

    def test_xml_escapes_special_chars(self, tmp_path):
        """title 中的特殊字符应被 XML 转义。"""
        ps = ParamSpace()
        writer = PresetXMPWriter(PresetMetadata(title='My <Cool> "Style" & Co'))
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        # 验证转义: & < > " 都应被替换
        assert "&lt;Cool&gt;" in content
        assert "&quot;Style&quot;" in content
        assert "&amp; Co" in content
        # 同时不应有未转义的 <Cool> 出现在 Name 节点里
        assert "<Cool>" not in content

    def test_auto_xmp_extension(self, tmp_path):
        """无 .xmp 后缀时,write 应自动补全。"""
        ps = ParamSpace()
        writer = PresetXMPWriter()
        out = writer.write(ps, tmp_path / "no_extension")
        assert out.suffix == ".xmp"
        assert out.exists()

    def test_group_in_xmp(self, tmp_path):
        """group 应出现在 Group 节点。"""
        ps = ParamSpace()
        writer = PresetXMPWriter(PresetMetadata(group="MyGroup:Subgroup"))
        out = tmp_path / "test.xmp"
        writer.write(ps, out)
        content = out.read_text(encoding="utf-8")
        assert "MyGroup:Subgroup" in content
        assert "<crs:Group>" in content

    def test_default_writable(self, tmp_path):
        """默认参数(全 0 + 线性 curve)生成的 .xmp 应能解析。"""
        import xml.etree.ElementTree as ET
        ps = ParamSpace()
        writer = PresetXMPWriter()
        out = tmp_path / "default.xmp"
        writer.write(ps, out)
        # ElementTree 解析应不抛异常
        ET.parse(str(out))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

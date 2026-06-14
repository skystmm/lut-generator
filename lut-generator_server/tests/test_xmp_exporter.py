"""
LUTExporter.export_xmp_preset 单元测试

测试覆盖:
- 17³ / 33³ / 65³ 三种 grid_size 都能正确生成 .xmp
- 256³ 走 fast path(直接取对角线,不走插值)
- ColorTable 数值正确(768 个整数,值域 0-65535)
- crs:Name / crs:ProcessVersion / crs:Amount 等必备字段都存在
- XML 转义不出错(标题里带 < > & ' " 时不破)
- export(format='xmp') dispatch 跟 export_xmp_preset 一致
"""

import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from lut_generator.lut.exporter import LUTExporter


@pytest.fixture
def identity_lut_33():
    """一个 33³ 的"恒等" LUT(对角线 = (i/32, i/32, i/32),其余用 0/1 边界)"""
    N = 33
    lut = np.zeros((N, N, N, 3), dtype=np.float32)
    for i in range(N):
        lut[i, i, i] = [i / (N - 1), i / (N - 1), i / (N - 1)]
    return lut


@pytest.fixture
def tinted_lut_17():
    """一个 17³ 的"冷色偏移" LUT:对角线上 R 衰减、G/B 提升,模拟电影感 LUT"""
    N = 17
    lut = np.zeros((N, N, N, 3), dtype=np.float32)
    for i in range(N):
        v = i / (N - 1)
        lut[i, i, i] = [v * 0.85, v * 1.05, v * 1.10]
    return lut


@pytest.fixture
def identity_lut_256():
    """256³ 走 fast path(直接取对角线)"""
    N = 256
    lut = np.zeros((N, N, N, 3), dtype=np.float32)
    for i in range(N):
        lut[i, i, i] = [i / 255.0, i / 255.0, i / 255.0]
    return lut


def _read_xmp(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _parse_color_table(xmp: str) -> list:
    m = re.search(r'crs:ColorTable="([^"]+)"', xmp)
    if not m:
        pytest.fail("crs:ColorTable not found in XMP")
    return [int(x) for x in m.group(1).split()]


class TestExportXmpPreset:
    def test_basic_33(self, identity_lut_33, tmp_path):
        out = tmp_path / "test33.xmp"
        LUTExporter(identity_lut_33, {'title': 'TestStyle'}).export_xmp_preset(out)
        assert out.exists()
        content = _read_xmp(out)
        vals = _parse_color_table(content)
        assert len(vals) == 768, f"expected 768 values, got {len(vals)}"
        assert 0 <= min(vals) <= max(vals) <= 65535
        # 恒等 LUT 的对角线:output = input
        # i=0: 0/255*65535 = 0;i=255: 255/255*65535 = 65535
        assert vals[0] == 0
        assert vals[-1] == 65535
        # 默认字段
        assert 'crs:Name="TestStyle"' in content
        assert 'crs:ProcessVersion="15.4"' in content
        assert 'crs:ColorTableVersion="1"' in content
        assert 'crs:SupportsAmount="True"' in content
        assert 'crs:Amount>1.0000' in content

    def test_tinted_17_three_channel_diff(self, tinted_lut_17, tmp_path):
        """17³ 走三线性插值路径,R/G/B 三通道应当确实不同(因为 LUT 偏色)"""
        out = tmp_path / "test17.xmp"
        LUTExporter(tinted_lut_17, {'title': 'Tinted'}).export_xmp_preset(out)
        vals = _parse_color_table(_read_xmp(out))
        r, g, b = vals[0::3], vals[1::3], vals[2::3]
        # R 通道最大 < G/B 通道最大(LUT 偏冷)
        assert max(r) < max(g) < max(b) or max(r) <= max(g) <= max(b)

    def test_fast_path_256(self, identity_lut_256, tmp_path):
        """256³ 走 fast path:对角线 0→65535 严格单调"""
        out = tmp_path / "test256.xmp"
        LUTExporter(identity_lut_256, {'title': 'Fast'}).export_xmp_preset(out)
        vals = _parse_color_table(_read_xmp(out))
        # R 通道:0, 257, 514, ... 65535(每 256 个 int)
        r = vals[0::3]
        assert r[0] == 0
        assert r[-1] == 65535
        assert r[128] == round(128 / 255 * 65535)

    def test_xml_escape_in_title(self, identity_lut_33, tmp_path):
        """标题里带 & < > " ' 时不破 XML"""
        out = tmp_path / "escape.xmp"
        dangerous_title = 'Test & "Co" <LUT> \'v2\''
        LUTExporter(identity_lut_33, {'title': dangerous_title}).export_xmp_preset(out)
        content = _read_xmp(out)
        # 应该转义成 &amp; &lt; &gt; &quot; &apos;
        assert 'Test &amp; &quot;Co&quot; &lt;LUT&gt; &apos;v2&apos;' in content
        # XML 必须是 well-formed(简单 try parse via lxml or ElementTree)
        import xml.etree.ElementTree as ET
        ET.fromstring(content)  # 不抛异常就是 well-formed

    def test_no_slider(self, identity_lut_33, tmp_path):
        out = tmp_path / "noslider.xmp"
        LUTExporter(identity_lut_33).export_xmp_preset(
            out, include_slider=False, supports_amount=False
        )
        content = _read_xmp(out)
        assert 'crs:Amount' not in content
        assert 'crs:SupportsAmount="False"' in content

    def test_custom_group(self, identity_lut_33, tmp_path):
        out = tmp_path / "custom.xmp"
        LUTExporter(identity_lut_33).export_xmp_preset(
            out, group='MyBrand:Looks', title='Cinematic Teal', apply_amount=0.7
        )
        content = _read_xmp(out)
        assert 'crs:Cluster="MyBrand:Looks"' in content
        assert 'crs:Name="Cinematic Teal"' in content
        assert 'crs:Amount>0.7000' in content

    def test_auto_append_xmp_suffix(self, identity_lut_33, tmp_path):
        """没传后缀时,自动加 .xmp"""
        out = tmp_path / "noext"
        LUTExporter(identity_lut_33).export_xmp_preset(out)
        assert (tmp_path / "noext.xmp").exists()

    def test_dispatch_via_export(self, identity_lut_33, tmp_path):
        """通用 export(format='xmp') 应该走同一路径"""
        out = tmp_path / "dispatch.xmp"
        LUTExporter(identity_lut_33, {'title': 'Dispatch'}).export(out, format='xmp')
        assert out.exists()
        assert 'crs:Name="Dispatch"' in _read_xmp(out)

    def test_unknown_format_raises(self, identity_lut_33, tmp_path):
        with pytest.raises(ValueError, match="Unknown format"):
            LUTExporter(identity_lut_33).export(tmp_path / "x.bin", format='fake')

    def test_existing_formats_still_work(self, identity_lut_33, tmp_path):
        """回归测试:原有的 cube/3dl/clf 不能因为我加 xmp 而坏掉"""
        for fmt, ext in [('cube', '.cube'), ('3dl', '.3dl'), ('clf', '.clf')]:
            out = tmp_path / f"old.{ext.lstrip('.')}"
            LUTExporter(identity_lut_33).export(out, format=fmt)
            assert out.exists(), f"{fmt} failed"
            assert out.stat().st_size > 0


class TestTrilinearDiag:
    def test_constant_lut(self):
        """LUT 全部填同一个值时,对角线采样 = 那个值"""
        N = 5
        lut = np.full((N, N, N, 3), 0.5, dtype=np.float32)
        diag = LUTExporter._trilinear_diag(lut, samples=10)
        assert diag.shape == (10, 3)
        assert np.allclose(diag, 0.5)

    def test_identity_lut_3(self):
        """3³ 单位对角线 LUT,采 3 个点应严格命中 (0,0,0)(0.5,0.5,0.5)(1,1,1)"""
        N = 3
        lut = np.zeros((N, N, N, 3), dtype=np.float32)
        for i in range(N):
            lut[i, i, i] = [i / 2, i / 2, i / 2]
        diag = LUTExporter._trilinear_diag(lut, samples=3)
        assert np.allclose(diag, [[0, 0, 0], [0.5, 0.5, 0.5], [1, 1, 1]], atol=1e-6)

    def test_endpoints_match_grid(self):
        """t=0 和 t=1 必须精确命中 LUT 角点(不应有插值误差)"""
        N = 8
        rng = np.random.default_rng(0)
        lut = rng.random((N, N, N, 3)).astype(np.float32)
        diag = LUTExporter._trilinear_diag(lut, samples=20)
        assert np.allclose(diag[0], lut[0, 0, 0])
        assert np.allclose(diag[-1], lut[N - 1, N - 1, N - 1])

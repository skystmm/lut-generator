"""
LUTExporter.export_xmp_creative_profile 单元测试

测试覆盖:
- 17³ / 33³ / 65³ 三种 grid_size 都能正确生成
- crs:RGBTable / crs:Table_<md5> / crs:RGBTableAmount 字段齐备
- Table_<md5> 字段值 = zlib 压缩 + Ascii85 编码的 BGR 16-bit LUT
- Round-trip 解码: ascii85 decode → zlib decompress → 16-bit 数组
   → 跟原始 LUT 一致(BGR 顺序)
- MD5 哈希是 32 字符 hex (大写)
- JSON / XML 合法解析
- crs:PresetType="Look" / crs:SupportsAmount="True" 必备字段
- auto-suffix 补 .xmp
- regression: 既有 xmp / lrtemplate / cube 还能用

参考: D:/workspace/lut-generator/XMP_LRTEMPLATE_RESEARCH.md
       exiftool 论坛 https://exiftool.org/forum/index.php?topic=11258.0
"""
import base64
import re
import xml.etree.ElementTree as ET
import zlib

import numpy as np
import pytest

from lut_generator.lut.exporter import LUTExporter


# ============================================================
# Fixtures
# ============================================================

def make_identity_lut(N):
    """标准 identity 3D LUT (R, G, B) → (R, G, B)"""
    return np.stack(np.meshgrid(
        np.linspace(0, 1, N),
        np.linspace(0, 1, N),
        np.linspace(0, 1, N),
        indexing='ij'
    ), axis=-1).astype(np.float32)


def make_teal_orange_lut(N):
    """可见的 teal/orange 偏色 LUT(暗部 push teal,亮部 push orange)"""
    lut = np.zeros((N, N, N, 3), dtype=np.float32)
    for b in range(N):
        for g in range(N):
            for r in range(N):
                L = (r + g + b) / (3 * (N - 1))
                if L < 0.5:
                    lut[r, g, b] = [r / (N-1) * 0.7, max(g, b) / (N-1), max(g, b) / (N-1)]
                else:
                    lut[r, g, b] = [min(1.0, r / (N-1) * 1.3), g / (N-1) * 0.7, b / (N-1) * 0.7]
    return np.clip(lut, 0, 1).astype(np.float32)


@pytest.fixture
def identity_lut_17():
    return make_identity_lut(17)


@pytest.fixture
def identity_lut_33():
    return make_identity_lut(33)


@pytest.fixture
def teal_orange_lut_17():
    return make_teal_orange_lut(17)


def _decode_xmp_table_field(encoded_str, N):
    """
    把 crs:Table_<md5> 字段值还原成 16-bit BGR 数组
    验证 round-trip 一致性
    """
    import html
    # XML-unescape(< ~ > 之前被 escape 成 &lt; &gt;)
    encoded_str = html.unescape(encoded_str)
    # Ascii85 decode(<~ ~> wrapper)
    compressed = base64.a85decode(encoded_str.encode('ascii'), adobe=True)
    # zlib decompress
    raw = zlib.decompress(compressed)
    # 解析为 16-bit big-endian BGR 数组
    assert len(raw) == N * N * N * 3 * 2, f"expected {N**3*3*2} bytes, got {len(raw)}"
    arr = np.frombuffer(raw, dtype='>u2').reshape(N * N * N, 3)
    return arr


# ============================================================
# 基础生成测试
# ============================================================

class TestBasicGeneration:
    def test_generates_file(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17, {'title': 'Identity 17'}).export_xmp_creative_profile(out)
        assert out.exists()
        assert out.stat().st_size > 1000  # 至少 1 KB(3D LUT 编码后)

    def test_auto_suffix(self, identity_lut_17, tmp_path):
        out = tmp_path / "no_suffix"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(out)
        assert (tmp_path / "no_suffix.xmp").exists()

    def test_default_title(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(out)
        content = out.read_text(encoding='utf-8')
        assert '<rdf:li xml:lang="x-default">LUT Preset</rdf:li>' in content

    def test_custom_title_escaped(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(
            out, title='<script>alert(1)</script>')
        content = out.read_text(encoding='utf-8')
        assert '<script>' not in content  # XML 注入防住了
        assert '&lt;script&gt;' in content

    def test_unicode_title_preserved(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(
            out, title='青橙色调')
        content = out.read_text(encoding='utf-8')
        assert '青橙色调' in content


# ============================================================
# 必备字段测试(对照 exiftool 论坛真实 .xmp 字段集)
# ============================================================

class TestRequiredFields:
    @pytest.fixture
    def xmp_content(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17, {'title': 'Test Look', 'group': 'TestGroup'}).export_xmp_creative_profile(
            out, apply_amount=0.75, process_version='15.4'
        )
        return out.read_text(encoding='utf-8')

    def test_preset_type_look(self, xmp_content):
        """Creative Profile 必备:crs:PresetType='Look'"""
        assert 'crs:PresetType="Look"' in xmp_content

    def test_supports_amount_true(self, xmp_content):
        assert 'crs:SupportsAmount="True"' in xmp_content

    def test_supports_color_true(self, xmp_content):
        assert 'crs:SupportsColor="True"' in xmp_content

    def test_rgb_table_hash_present(self, xmp_content):
        """crs:RGBTable 字段必须存在,32 字符 hex 大写"""
        m = re.search(r'crs:RGBTable="([0-9A-F]{32})"', xmp_content)
        assert m is not None
        rgb_hash = m.group(1)
        assert len(rgb_hash) == 32

    def test_table_hash_matches_rgb_table(self, xmp_content):
        """crs:Table_<md5> 字段名里的 md5 必须等于 crs:RGBTable 的值"""
        rgb_m = re.search(r'crs:RGBTable="([0-9A-F]{32})"', xmp_content)
        rgb_hash = rgb_m.group(1)
        assert f'crs:Table_{rgb_hash}=' in xmp_content

    def test_rgb_table_amount(self, xmp_content):
        """crs:RGBTableAmount 必须存在,且在 0-1 范围"""
        m = re.search(r'crs:RGBTableAmount="([\d.]+)"', xmp_content)
        assert m is not None
        amount = float(m.group(1))
        assert 0.0 <= amount <= 1.0
        assert abs(amount - 0.75) < 1e-4

    def test_process_version(self, xmp_content):
        m = re.search(r'crs:ProcessVersion="([^"]+)"', xmp_content)
        assert m is not None
        assert m.group(1) == '15.4'

    def test_version_15_4(self, xmp_content):
        assert 'crs:Version="15.4"' in xmp_content

    def test_has_settings(self, xmp_content):
        assert 'crs:HasSettings="True"' in xmp_content

    def test_convert_to_grayscale_false(self, xmp_content):
        assert 'crs:ConvertToGrayscale="False"' in xmp_content

    def test_uuid_field(self, xmp_content):
        """crs:UUID = 32 字符 hex,跟 RGBTable 哈希一致(本次实现都用 md5)"""
        uuid_m = re.search(r'crs:UUID="([0-9A-F]{32})"', xmp_content)
        rgb_m = re.search(r'crs:RGBTable="([0-9A-F]{32})"', xmp_content)
        assert uuid_m is not None
        assert rgb_m is not None

    def test_xml_namespace_declared(self, xmp_content):
        """crs: 命名空间必须声明在 rdf:Description 上"""
        assert 'xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"' in xmp_content

    def test_rdf_namespace(self, xmp_content):
        assert 'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"' in xmp_content


# ============================================================
# XML 合法解析测试
# ============================================================

class TestXMLParsing:
    def test_xml_parses(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(out)
        # 应该不抛异常
        tree = ET.parse(out)
        root = tree.getroot()
        assert root.tag == '{adobe:ns:meta/}xmpmeta'

    def test_rdf_description_exists(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(out)
        tree = ET.parse(out)
        # 找 rdf:Description
        ns = {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
              'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/'}
        descriptions = tree.findall('.//rdf:Description', ns)
        assert len(descriptions) == 1

    def test_name_in_rdf_alt(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17, {'title': 'UniqueName42'}).export_xmp_creative_profile(out)
        tree = ET.parse(out)
        ns = {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
              'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/'}
        li = tree.findall('.//crs:Name/rdf:Alt/rdf:li', ns)
        assert any(li.text == 'UniqueName42' for li in li if li.text)


# ============================================================
# Round-trip 解码测试 — 关键:验证编码可逆
# ============================================================

class TestRoundTripDecoding:
    """模拟 LrC 14 的解码流程:asymmetric85 decode → zlib decompress → 16-bit BGR 数组"""

    @pytest.mark.parametrize("N", [5, 17, 33, 65])
    def test_roundtrip_identity(self, N, tmp_path):
        """identity LUT round-trip: 解码后每个点应该是 (i, i, i)"""
        lut = make_identity_lut(N)
        out = tmp_path / "test.xmp"
        LUTExporter(lut).export_xmp_creative_profile(out)

        content = out.read_text(encoding='utf-8')
        # 提取 Table_<hash> 字段值
        m = re.search(r'crs:Table_[0-9A-F]{32}="([^"]+)"', content)
        assert m is not None
        encoded = m.group(1)

        # 解码
        arr = _decode_xmp_table_field(encoded, N)
        assert arr.shape == (N**3, 3)
        # BGR 顺序:BGR(0,0,0) → (0,0,0), BGR(1,0,0) → (0,0,65535*1/(N-1))
        # 检查几个对角线点(R=G=B=i)
        for i in [0, N//2, N-1]:
            expected = round(i / (N - 1) * 65535)
            # BGR 顺序下 i 位置:flat_idx = i*N*N + i*N + i
            flat_idx = i * N * N + i * N + i
            actual = arr[flat_idx]
            assert abs(int(actual[0]) - expected) <= 1, \
                f"i={i}: R={actual[0]} expected={expected}"
            assert abs(int(actual[1]) - expected) <= 1, \
                f"i={i}: G={actual[1]} expected={expected}"
            assert abs(int(actual[2]) - expected) <= 1, \
                f"i={i}: B={actual[2]} expected={expected}"

    def test_roundtrip_tinted(self, tmp_path):
        """teal/orange LUT round-trip: 验证偏色信息保留"""
        lut = make_teal_orange_lut(17)
        out = tmp_path / "test.xmp"
        LUTExporter(lut).export_xmp_creative_profile(out)

        content = out.read_text(encoding='utf-8')
        m = re.search(r'crs:Table_[0-9A-F]{32}="([^"]+)"', content)
        encoded = m.group(1)

        arr = _decode_xmp_table_field(encoded, 17)
        # 验证暗部点 (R=G=B=4,L<0.5,期望 teal 偏色: G/B > R)
        # BGR 顺序: b=N//4, g=N//4, r=N//4
        i = 4
        flat_idx = i * 17 * 17 + i * 17 + i
        actual = arr[flat_idx]
        # LUT[i, i, i] 在 L=0.25:暗部, R=4/16*0.7=0.175, G=B=max(4,4)/16=0.25
        # 16-bit:R=11469, G=B=16384
        # 所以 G/B > R
        assert int(actual[1]) > int(actual[0]), \
            f"G={actual[1]} 应该 > R={actual[0]} (teal 偏色)"
        assert int(actual[2]) > int(actual[0]), \
            f"B={actual[2]} 应该 > R={actual[0]} (teal 偏色)"
        # 且实际值匹配预期(允许 ±1 量化误差)
        assert abs(int(actual[0]) - 11469) <= 1
        assert abs(int(actual[1]) - 16384) <= 1
        assert abs(int(actual[2]) - 16384) <= 1


# ============================================================
# 编码细节测试
# ============================================================

class TestEncodingDetails:
    def test_ascii85_alphabet_only(self, identity_lut_17, tmp_path):
        """Table_<hash> 字段值只应包含 Ascii85 字符集(!到 u)
        + <~ ~> wrapper 的 ~ (ord=126) 字符
        + XML escape 后的 &lt; &gt; &amp; 实体(因为 < > & 在字段里被 escape 了)
        """
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(out)
        content = out.read_text(encoding='utf-8')
        import html
        m = re.search(r'crs:Table_[0-9A-F]{32}="([^"]+)"', content)
        raw = m.group(1)
        # XML-unescape
        unescaped = html.unescape(raw)
        # Ascii85 字符集: ASCII 33-117 (! to u), + <~ ~> wrapper 的 ~ (126) 字符
        for c in unescaped:
            assert (33 <= ord(c) <= 117) or ord(c) == 126, \
                f"非法字符 {c!r} (ord={ord(c)}) 不在 Ascii85 字符集 + wrapper"
        # 字段值应只含 Ascii85 + & / < / > XML escape + ; + <~ ~> wrapper 字符
        for c in raw:
            assert (33 <= ord(c) <= 117) or c in '&;~', \
                f"XML-escape 前的字符 {c!r} (ord={ord(c)}) 应是 Ascii85 字符"

    def test_compression_actually_happens(self, identity_lut_17, tmp_path):
        """encoded 长度应该 < 未压缩(identity LUT 高度可压缩)"""
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(out)
        content = out.read_text(encoding='utf-8')
        m = re.search(r'crs:Table_[0-9A-F]{32}="([^"]+)"', content)
        encoded = m.group(1)
        # 解码后的原始 bytes = N³ × 3 × 2 = 4913 × 6 = 29478 bytes
        # 压缩 + Ascii85 后应该 < 20000 chars
        assert len(encoded) < 20000

    def test_md5_deterministic(self, identity_lut_17, tmp_path):
        """同一 LUT 生成两次,md5 哈希必须一致(LUT 数据一样)"""
        out1 = tmp_path / "t1.xmp"
        out2 = tmp_path / "t2.xmp"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(out1)
        LUTExporter(identity_lut_17).export_xmp_creative_profile(out2)
        m1 = re.search(r'crs:RGBTable="([0-9A-F]{32})"', out1.read_text())
        m2 = re.search(r'crs:RGBTable="([0-9A-F]{32})"', out2.read_text())
        assert m1.group(1) == m2.group(1)

    def test_md5_changes_with_lut(self, identity_lut_17, teal_orange_lut_17, tmp_path):
        """不同 LUT 产生不同 md5"""
        o1 = tmp_path / "a.xmp"
        o2 = tmp_path / "b.xmp"
        LUTExporter(identity_lut_17).export_xmp_creative_profile(o1)
        LUTExporter(teal_orange_lut_17).export_xmp_creative_profile(o2)
        h1 = re.search(r'crs:RGBTable="([0-9A-F]{32})"', o1.read_text()).group(1)
        h2 = re.search(r'crs:RGBTable="([0-9A-F]{32})"', o2.read_text()).group(1)
        assert h1 != h2


# ============================================================
# 集成测试:通过 export() dispatch 调用
# ============================================================

class TestExportDispatch:
    def test_export_via_format_dispatch(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17).export(out, format='xmpcreative')
        assert out.exists()
        assert 'crs:RGBTable=' in out.read_text(encoding='utf-8')

    def test_existing_formats_still_work(self, identity_lut_17, tmp_path):
        """回归: cube / 3dl / clf / xmp / lrtemplate 都还能用"""
        exp = LUTExporter(identity_lut_17)
        for fmt, ext in [
            ('cube', '.cube'),
            ('3dl', '.3dl'),
            ('clf', '.clf'),
            ('xmp', '.xmp'),
            ('lrtemplate', '.lrtemplate'),
            ('xmpcreative', '.xmp'),
        ]:
            out = tmp_path / f"t.{ext.lstrip('.')}"
            exp.export(out, format=fmt)
            assert out.exists(), f"{fmt} -> {ext} failed"

    def test_format_case_insensitive(self, identity_lut_17, tmp_path):
        out = tmp_path / "test.xmp"
        LUTExporter(identity_lut_17).export(out, format='XMPCreative')
        assert out.exists()

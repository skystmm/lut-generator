"""
LUTExporter.export_lrtemplate_preset 单元测试

测试覆盖:
- 17³ / 33³ / 65³ 三种 grid_size 都能正确生成 .lrtemplate
- LUT3D 字符串长度 = N³ × 3,值域 0-65535 (16-bit)
- BGR 顺序正确(最外层 B 变化最快,跟 .cube 一致)
- JSON 是合法 strict JSON(LrC 吃 strict JSON + JSON6)
- 必备字段都在(type/version/s.*)
- 字段值正确(SupportsAmount int 不是 bool,ToneCurveName2012 是 Linear 等)
- export(format='lrtemplate') dispatch 跟 export_lrtemplate_preset 一致
- 无后缀自动补 .lrtemplate
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from lut_generator.lut.exporter import LUTExporter


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------

@pytest.fixture
def identity_lut_33():
    """33³ 单位 LUT: lut[r, g, b] = (r/32, g/32, b/32) — 真正 3D 跨维度"""
    N = 33
    lut = np.zeros((N, N, N, 3), dtype=np.float32)
    for b in range(N):
        for g in range(N):
            for r in range(N):
                lut[r, g, b] = [r / (N - 1), g / (N - 1), b / (N - 1)]
    return lut


@pytest.fixture
def tinted_lut_17():
    """17³ teal/orange 偏色 LUT: r 衰减, b 提升, 模拟电影感"""
    N = 17
    lut = np.zeros((N, N, N, 3), dtype=np.float32)
    for b in range(N):
        for g in range(N):
            for r in range(N):
                # 任意 LUT 偏色,只要 R/B 不等,就能从 3D 中看出偏色
                rv, gv, bv = r / (N - 1), g / (N - 1), b / (N - 1)
                lut[r, g, b] = [rv * 0.85, gv, bv * 1.15]
    return lut


@pytest.fixture
def tiny_3d_lut():
    """3³ 最小 LUT,手工验证 BGR 顺序最清晰"""
    N = 3
    lut = np.zeros((N, N, N, 3), dtype=np.float32)
    for b in range(N):
        for g in range(N):
            for r in range(N):
                lut[r, g, b] = [r / 2.0, g / 2.0, b / 2.0]
    return lut


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _read_lrtemplate(path: Path) -> dict:
    """读 .lrtemplate 文件并解析为 dict(strict JSON,不是 JSON6)"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _parse_lut3d(data: dict) -> list:
    """从 dict 拿 LUT3D 字符串并解成 int 列表"""
    s = data['s']['LUT3D']
    return [int(x) for x in s.split()]


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------

class TestExportLrtemplatePreset:
    def test_basic_33(self, identity_lut_33, tmp_path):
        """33³ 单位 LUT 端到端:文件存在 + JSON 合法 + 字段齐"""
        out = tmp_path / "test33.lrtemplate"
        LUTExporter(identity_lut_33, {'title': 'TestStyle'}).export_lrtemplate_preset(out)
        assert out.exists()

        data = _read_lrtemplate(out)

        # Schema 头
        assert data['type'] == 'Develop'
        assert data['version'] == 1

        # 必备 settings 字段
        s = data['s']
        assert s['Name'] == 'TestStyle'
        assert s['Group'] == 'lut-generator:UserPresets'
        assert s['PresetType'] == 'Normal'
        assert s['ProcessVersion'] == '15.4'
        assert s['SupportsAmount'] == 1
        assert abs(s['Amount'] - 1.0) < 1e-9
        assert s['ToneCurveName2012'] == 'Linear'
        assert s['LUT3DSize'] == 33
        assert s['LUT3DIntent'] == 0
        assert s['LUT3DMixing'] == 0.5

    def test_lut3d_33_length_and_range(self, identity_lut_33, tmp_path):
        """LUT3D 字符串长度 = N³ × 3,值域 0-65535"""
        out = tmp_path / "test33.lrtemplate"
        LUTExporter(identity_lut_33).export_lrtemplate_preset(out)
        data = _read_lrtemplate(out)

        vals = _parse_lut3d(data)
        N = 33
        assert len(vals) == N ** 3 * 3, f"expected {N**3*3} values, got {len(vals)}"
        assert 0 <= min(vals) <= max(vals) <= 65535, \
            f"LUT3D must be 16-bit (0-65535), got range [{min(vals)}, {max(vals)}]"

    def test_lut3d_17(self, tinted_lut_17, tmp_path):
        """17³ tinted LUT 端到端"""
        out = tmp_path / "test17.lrtemplate"
        LUTExporter(tinted_lut_17, {'title': 'Tinted'}).export_lrtemplate_preset(out)
        data = _read_lrtemplate(out)
        assert data['s']['LUT3DSize'] == 17
        assert data['s']['Name'] == 'Tinted'

    def test_lut3d_65(self, identity_lut_33, tmp_path):
        """65³(大尺寸)走 numpy 路径"""
        N = 65
        lut = np.zeros((N, N, N, 3), dtype=np.float32)
        for b in range(N):
            for g in range(N):
                for r in range(N):
                    lut[r, g, b] = [r / (N - 1), g / (N - 1), b / (N - 1)]
        out = tmp_path / "test65.lrtemplate"
        LUTExporter(lut).export_lrtemplate_preset(out)
        data = _read_lrtemplate(out)
        assert data['s']['LUT3DSize'] == 65
        vals = _parse_lut3d(data)
        assert len(vals) == N ** 3 * 3

    def test_bgr_order_tiny(self, tiny_3d_lut, tmp_path):
        """3³ 验证 BGR 顺序(B 最外层,变化最快,跟 .cube 一致):
        - i=0 (b=0,g=0,r=0) → lut[0,0,0] = (0, 0, 0)
        - i=1 (b=0,g=0,r=1) → lut[1,0,0] = (0.5, 0, 0) → (32768, 0, 0)
        - i=N (b=0,g=1,r=0) → lut[0,1,0] = (0, 0.5, 0) → (0, 32768, 0)
        - i=N² (b=1,g=0,r=0) → lut[0,0,1] = (0, 0, 0.5) → (0, 0, 32768)
        - i=N³-1 (b=2,g=2,r=2) → lut[2,2,2] = (1, 1, 1) → (65535, 65535, 65535)
        """
        out = tmp_path / "tiny.lrtemplate"
        LUTExporter(tiny_3d_lut).export_lrtemplate_preset(out)
        data = _read_lrtemplate(out)
        vals = _parse_lut3d(data)
        N = 3

        assert vals[0:3] == [0, 0, 0], f"i=0 expected (0,0,0), got {vals[0:3]}"
        assert vals[3:6] == [32768, 0, 0], f"i=1 expected (32768,0,0), got {vals[3:6]}"
        assert vals[3*N:3*N+3] == [0, 32768, 0], \
            f"i=N expected (0,32768,0), got {vals[3*N:3*N+3]}"
        assert vals[3*N*N:3*N*N+3] == [0, 0, 32768], \
            f"i=N² expected (0,0,32768), got {vals[3*N*N:3*N*N+3]}"
        assert vals[-3:] == [65535, 65535, 65535], \
            f"i=N³-1 expected (65535,65535,65535), got {vals[-3:]}"

    def test_clamp_out_of_range(self, tmp_path):
        """LUT 值超过 [0,1] 时被 clip 到 65535(避免 LrC 渲染异常)"""
        N = 3
        lut = np.zeros((N, N, N, 3), dtype=np.float32)
        # 故意填个 > 1 的值
        lut[2, 2, 2] = [1.5, -0.3, 2.0]  # R clip, G clip 到 0, B clip
        out = tmp_path / "clamp.lrtemplate"
        LUTExporter(lut).export_lrtemplate_preset(out)
        vals = _parse_lut3d(_read_lrtemplate(out))
        assert max(vals) == 65535
        assert min(vals) == 0

    def test_no_amount(self, identity_lut_33, tmp_path):
        """supports_amount=False 时 SupportsAmount=0"""
        out = tmp_path / "noamt.lrtemplate"
        LUTExporter(identity_lut_33).export_lrtemplate_preset(
            out, supports_amount=False
        )
        data = _read_lrtemplate(out)
        assert data['s']['SupportsAmount'] == 0

    def test_custom_group_and_amount(self, identity_lut_33, tmp_path):
        """自定义 group / amount / title"""
        out = tmp_path / "custom.lrtemplate"
        LUTExporter(identity_lut_33).export_lrtemplate_preset(
            out, group='MyBrand:Looks', title='Cinematic Teal', apply_amount=0.7
        )
        data = _read_lrtemplate(out)
        s = data['s']
        assert s['Group'] == 'MyBrand:Looks'
        assert s['Name'] == 'Cinematic Teal'
        assert abs(s['Amount'] - 0.7) < 1e-9

    def test_auto_append_lrtemplate_suffix(self, identity_lut_33, tmp_path):
        """没传后缀时,自动加 .lrtemplate"""
        out = tmp_path / "noext"
        LUTExporter(identity_lut_33).export_lrtemplate_preset(out)
        assert (tmp_path / "noext.lrtemplate").exists()

    def test_dispatch_via_export(self, identity_lut_33, tmp_path):
        """通用 export(format='lrtemplate') 应该走同一路径"""
        out = tmp_path / "dispatch.lrtemplate"
        LUTExporter(identity_lut_33, {'title': 'Dispatch'}).export(
            out, format='lrtemplate'
        )
        assert out.exists()
        data = _read_lrtemplate(out)
        assert data['s']['Name'] == 'Dispatch'

    def test_unknown_format_raises(self, identity_lut_33, tmp_path):
        with pytest.raises(ValueError, match="Unknown format"):
            LUTExporter(identity_lut_33).export(tmp_path / "x.bin", format='fake')

    def test_json_is_strict_compliant(self, identity_lut_33, tmp_path):
        """生成的 .lrtemplate 是 strict JSON(标准 json.load 能解析),
        不是 JSON6(LrC 也吃 strict JSON,无需注释)"""
        out = tmp_path / "strict.lrtemplate"
        LUTExporter(identity_lut_33).export_lrtemplate_preset(out)
        # 二次读解析
        with open(out, 'r', encoding='utf-8') as f:
            content = f.read()
        # 不能有 JSON6 注释(//  或 #)
        assert '//' not in content
        # 必须是合法 strict JSON
        parsed = json.loads(content)
        assert 'type' in parsed
        assert 's' in parsed

    def test_existing_formats_still_work(self, identity_lut_33, tmp_path):
        """回归测试:原有的 cube/3dl/clf/xmp 不能因为加 lrtemplate 而坏掉"""
        for fmt, ext in [
            ('cube', '.cube'),
            ('3dl', '.3dl'),
            ('clf', '.clf'),
            ('xmp', '.xmp'),
            ('lrtemplate', '.lrtemplate'),
        ]:
            out = tmp_path / f"old.{ext.lstrip('.')}"
            LUTExporter(identity_lut_33).export(out, format=fmt)
            assert out.exists(), f"{fmt} failed"
            assert out.stat().st_size > 0

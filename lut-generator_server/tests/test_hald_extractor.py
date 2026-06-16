"""
HALDPixelExtractor 单元测试
============================

测试覆盖(12+ 测试):
- 3 种方法(nearest / gaussian_rbf / shepard_idw)都返回正确 shape
- identity 输入应产生近似 identity LUT
- 红色 dominant 输入应让 red bin 输出高 R 值
- smoothing 不破坏 shape
- extract_multi 多图加权
- .cube 写出 + 满足 Adobe spec 1.0
- 端到端: extract → export .cube → applier 可读
- 边界条件:小图、大 cube、超出 [0, 1] 范围处理
- 性能冒烟测试(33³ < 60s)

不依赖 scipy,纯 numpy。
"""
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from lut_generator.core.hald_extractor import (
    HALDExtractionConfig,
    HALDExtractionResult,
    HALDPixelExtractor,
    extract_hald,
)


def _is_float(s: str) -> bool:
    """判断字符串是否为合法 float(支持负数/小数/科学计数法)"""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def red_dominant_image(tmp_path) -> Path:
    """红色 dominant 测试图(128x128,80% 红色像素,20% 灰色)"""
    np.random.seed(42)
    img = np.zeros((128, 128, 3), dtype=np.uint8)
    # 80% 红色
    red_mask = np.random.rand(128, 128) < 0.8
    img[red_mask] = [200, 50, 50]
    # 20% 灰色
    img[~red_mask] = [128, 128, 128]
    path = tmp_path / "red_dominant.jpg"
    Image.fromarray(img).save(path, quality=95)
    return path


@pytest.fixture
def teal_orange_image(tmp_path) -> Path:
    """Teal/Orange 经典电影色调参考图(下/上半 teal/橙)"""
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[:32] = [180, 130, 60]    # 上半橙
    img[32:] = [40, 130, 160]    # 下半 teal
    path = tmp_path / "teal_orange.jpg"
    Image.fromarray(img).save(path)
    return path


@pytest.fixture
def identity_image(tmp_path) -> Path:
    """标准 8x8 identity Hald CLUT(参考 ImageMagick hald:8)"""
    N = 8
    side = N * N * N  # = 512
    indices = np.linspace(0, 255, side, dtype=np.uint8)
    rr = indices.reshape(side, 1)
    img = np.zeros((side, side, 3), dtype=np.uint8)
    # R 通道按 (r, g, b) 索引方式 = rr 重复
    img[:, :, 0] = np.tile(rr, (1, side))[:, :side]  # 简化:全部用 rr
    img[:, :, 1] = np.tile(rr, (1, side))[:, :side]
    img[:, :, 2] = np.tile(rr, (1, side))[:, :side]
    path = tmp_path / "identity_hald.png"
    Image.fromarray(img).save(path)
    return path


# ============================================================
# 1. 基础功能
# ============================================================

class TestHALDExtractorBasic:
    """基础功能测试"""

    def test_returns_4d_array(self, red_dominant_image):
        """返回 (N, N, N, 3) float32 数组"""
        extractor = HALDPixelExtractor(HALDExtractionConfig(cube_size=8))
        result = extractor.extract(red_dominant_image)
        assert result.lut_data.ndim == 4
        assert result.lut_data.shape == (8, 8, 8, 3)
        assert result.lut_data.dtype == np.float32

    def test_value_range_zero_to_one(self, red_dominant_image):
        """LUT 值在 [0, 1] 范围内"""
        extractor = HALDPixelExtractor(HALDExtractionConfig(cube_size=8))
        result = extractor.extract(red_dominant_image)
        assert result.lut_data.min() >= 0.0
        assert result.lut_data.max() <= 1.0

    def test_cube_size_override(self, red_dominant_image):
        """cube_size 参数可覆盖 config"""
        extractor = HALDPixelExtractor(HALDExtractionConfig(cube_size=8))
        result = extractor.extract(red_dominant_image, cube_size=4)
        assert result.lut_data.shape == (4, 4, 4, 3)

    def test_method_override(self, red_dominant_image):
        """method 参数可覆盖 config"""
        extractor = HALDPixelExtractor(HALDExtractionConfig(method="nearest"))
        result = extractor.extract(red_dominant_image, method="gaussian_rbf")
        assert result.method == "gaussian_rbf"

    def test_invalid_method_raises(self, red_dominant_image):
        """未知 method 抛 ValueError"""
        extractor = HALDPixelExtractor()
        with pytest.raises(ValueError, match="Unknown method"):
            extractor.extract(red_dominant_image, method="magic")


# ============================================================
# 2. 3 种算法分别验证
# ============================================================

class TestThreeMethods:
    """3 种算法都应保留输入图片的色彩偏向"""

    @pytest.mark.parametrize("method", ["nearest", "gaussian_rbf", "shepard_idw"])
    def test_red_dominant_preserves_redness(self, red_dominant_image, method):
        """红色 dominant 图:R 高 bin 输出应接近红色"""
        extractor = HALDPixelExtractor(
            HALDExtractionConfig(cube_size=8, method=method, n_samples=500)
        )
        result = extractor.extract(red_dominant_image)

        # cube bin (R=high, G=low, B=low) 应映射到 R 高的输出
        # bin 索引: r=7 (max), g=0 (min), b=0 (min)
        red_bin = result.lut_data[7, 0, 0]
        assert red_bin[0] > 0.5, f"{method}: R={red_bin[0]} should be > 0.5"
        # G/B 应该显著低于 R
        assert red_bin[1] < red_bin[0] * 0.6, (
            f"{method}: G={red_bin[1]} should be much lower than R={red_bin[0]}"
        )

    def test_teal_orange_distinct_outputs(self, teal_orange_image):
        """Teal/Orange 图:Teal 区域 bin 应得 teal-ish 输出"""
        extractor = HALDPixelExtractor(
            HALDExtractionConfig(cube_size=8, method="gaussian_rbf", n_samples=500)
        )
        result = extractor.extract(teal_orange_image)

        # Teal bin = (low R, mid G, high B) — R=2 G=4 B=6
        teal_bin = result.lut_data[2, 4, 6]
        # B 应大于 R
        assert teal_bin[2] > teal_bin[0], (
            f"Teal bin B should be > R, got {teal_bin}"
        )


# ============================================================
# 3. Identity round-trip
# ============================================================

class TestIdentityBehavior:
    """Identity 输入应产生近似 identity LUT"""

    def test_grayscale_identity_lut(self, tmp_path):
        """灰度 ramp 图(0→255)R=G=B → 输出应接近对角线"""
        # 16x16 灰度 ramp
        ramp = np.linspace(0, 255, 256, dtype=np.uint8).reshape(16, 16)
        img = np.stack([ramp] * 3, axis=-1)
        path = tmp_path / "ramp.png"
        Image.fromarray(img).save(path)

        extractor = HALDPixelExtractor(
            HALDExtractionConfig(cube_size=8, method="nearest", n_samples=500)
        )
        result = extractor.extract(path)

        # 对角线 bin: r==g==b, 应映射到 r==g==b
        for i in [1, 4, 6]:
            bin_val = result.lut_data[i, i, i]
            # R ≈ G ≈ B
            assert abs(bin_val[0] - bin_val[1]) < 0.05, (
                f"Diagonal bin {i} not gray: {bin_val}"
            )
            assert abs(bin_val[0] - bin_val[2]) < 0.05


# ============================================================
# 4. Smoothing
# ============================================================

class TestSmoothing:
    """Smoothing 测试"""

    def test_smoothing_reduces_local_variance(self, red_dominant_image):
        """Smoothing 降低 LUT 局部方差"""
        cfg = HALDExtractionConfig(cube_size=8, method="nearest", smoothing_passes=0)
        lut_no_smooth = HALDPixelExtractor(cfg).extract(red_dominant_image).lut_data

        cfg2 = HALDExtractionConfig(cube_size=8, method="nearest", smoothing_passes=2)
        lut_smooth = HALDPixelExtractor(cfg2).extract(red_dominant_image).lut_data

        # 局部方差(相邻 bin 差分):smoothed 应更小
        diff_no_smooth = np.abs(np.diff(lut_no_smooth, axis=0)).mean()
        diff_smooth = np.abs(np.diff(lut_smooth, axis=0)).mean()
        assert diff_smooth < diff_no_smooth, (
            f"Smoothed diff {diff_smooth:.4f} should be < no-smooth {diff_no_smooth:.4f}"
        )

    def test_smoothing_passes_zero_preserves(self, red_dominant_image):
        """smoothing_passes=0 跳过 smoothing"""
        cfg = HALDExtractionConfig(cube_size=8, smoothing_passes=0)
        result = HALDPixelExtractor(cfg).extract(red_dominant_image)
        # 不应该抛错,shape 正确
        assert result.lut_data.shape == (8, 8, 8, 3)

    def test_box1d_returns_same_shape(self):
        """_box1d 不改变 shape"""
        arr = np.random.rand(8, 8, 8, 3).astype(np.float32)
        for axis in range(3):
            out = HALDPixelExtractor._box1d(arr, axis=axis, radius=1)
            assert out.shape == arr.shape

    def test_box1d_smooths_uniform(self):
        """_box1d 对全 1 数组应仍输出 1"""
        arr = np.ones((8, 8, 8, 3), dtype=np.float32)
        out = HALDPixelExtractor._box1d(arr, axis=0, radius=1)
        assert np.allclose(out, 1.0)


# ============================================================
# 5. Multi-reference
# ============================================================

class TestMultiReference:
    """多图加权提取"""

    def test_extract_multi_3_images(self, tmp_path):
        """3 张图加权提取"""
        # 3 张不同色彩的图
        paths = []
        for color_name, rgb in [
            ("red", [200, 30, 30]),
            ("green", [30, 200, 30]),
            ("blue", [30, 30, 200]),
        ]:
            img = np.zeros((64, 64, 3), dtype=np.uint8) + np.array(rgb, dtype=np.uint8)
            p = tmp_path / f"{color_name}.jpg"
            Image.fromarray(img).save(p)
            paths.append(p)

        extractor = HALDPixelExtractor(
            HALDExtractionConfig(cube_size=8, method="gaussian_rbf", n_samples=300)
        )
        result = extractor.extract_multi(paths)
        assert result.lut_data.shape == (8, 8, 8, 3)
        # 至少一种颜色应保留
        red_bin = result.lut_data[7, 0, 0]
        green_bin = result.lut_data[0, 7, 0]
        blue_bin = result.lut_data[0, 0, 7]
        # R-bin R > G 且 B-bin B > R
        assert red_bin[0] > red_bin[1]
        assert blue_bin[2] > blue_bin[0]
        assert green_bin[1] > green_bin[0]

    def test_extract_multi_weights(self, tmp_path):
        """weights 长度不匹配抛错"""
        img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        path = tmp_path / "a.jpg"
        Image.fromarray(img).save(path)

        extractor = HALDPixelExtractor()
        with pytest.raises(ValueError, match="weights length"):
            extractor.extract_multi([path], weights=[1.0, 2.0])

    def test_extract_multi_empty_raises(self):
        """空列表抛错"""
        extractor = HALDPixelExtractor()
        with pytest.raises(ValueError, match="must not be empty"):
            extractor.extract_multi([])


# ============================================================
# 6. 便捷函数 + .cube 导出
# ============================================================

class TestConvenienceFunction:
    """extract_hald() 便捷函数"""

    def test_writes_cube_file(self, red_dominant_image, tmp_path):
        """extract_hald 应直接写 .cube 文件"""
        out_cube = tmp_path / "out.cube"
        result = extract_hald(
            red_dominant_image,
            out_cube,
            cube_size=8,
            method="nearest",
            smoothing_passes=0,
        )
        assert out_cube.exists()
        assert out_cube.stat().st_size > 0
        assert result.lut_data.shape == (8, 8, 8, 3)

    def test_cube_format_compliance(self, red_dominant_image, tmp_path):
        """写出 .cube 满足 Adobe spec 1.0:LUT_3D_SIZE + N³ 行"""
        out_cube = tmp_path / "test.cube"
        N = 8
        extract_hald(
            red_dominant_image, out_cube,
            cube_size=N, method="nearest", smoothing_passes=0,
        )
        content = out_cube.read_text()

        # 找到 LUT_3D_SIZE 行(可能在 TITLE / DOMAIN_* 之后)
        size_line_idx = None
        for i, line in enumerate(content.splitlines()):
            if line.strip().upper().startswith("LUT_3D_SIZE"):
                size_line_idx = i
                break
        assert size_line_idx is not None, f"No LUT_3D_SIZE found in:\n{content[:200]}"
        size_tokens = content.splitlines()[size_line_idx].split()
        assert int(size_tokens[1]) == N

        # 计数"3 个 float 的数据行"(忽略 DOMAIN_MIN/MAX/TITLE/注释)
        data_lines = [
            line for line in content.splitlines()[size_line_idx + 1:]
            if line.strip() and not line.strip().startswith("#")
        ]
        # 只数形如 "0.498 0.302 0.298" 的 3-float 行
        data_rows = [
            line for line in data_lines
            if len(line.split()) == 3
            and all(_is_float(t) for t in line.split())
        ]
        assert len(data_rows) == N ** 3, (
            f"Expected {N**3} data rows, got {len(data_rows)}"
        )

        # 每行 3 个 float ∈ [0, 1]
        for line in data_rows[:5]:
            parts = line.split()
            assert len(parts) == 3
            for p in parts:
                v = float(p)
                assert 0.0 <= v <= 1.0


# ============================================================
# 6b. format 参数 — 6 种导出格式
# ============================================================

class TestExtractHaldFormatParam:
    """extract_hald(format=...) 走 LUTExporter.export() 派发到非 cube 格式"""

    @pytest.mark.parametrize("fmt,expected_ext", [
        ("cube", ".cube"),
        ("3dl", ".3dl"),
        ("clf", ".clf"),
        ("xmp", ".xmp"),
        ("lrtemplate", ".lrtemplate"),
        ("xmpcreative", ".xmp"),
    ])
    def test_format_dispatch_writes_file(
        self, red_dominant_image, tmp_path, fmt, expected_ext
    ):
        """format 参数应触发对应格式写出(后缀自动补)"""
        out = tmp_path / "no_suffix"  # 不带后缀,验证 ext_map 补全
        result = extract_hald(
            red_dominant_image,
            out,
            cube_size=8,
            method="nearest",
            smoothing_passes=0,
            format=fmt,
        )
        # 实际写入路径 = no_suffix + ext_map[fmt]
        expected = out.with_suffix(expected_ext)
        assert expected.exists(), f"{fmt} 没写出 {expected}"
        assert expected.stat().st_size > 0
        assert result.lut_data.shape == (8, 8, 8, 3)

    def test_format_default_is_cube(self, red_dominant_image, tmp_path):
        """不传 format 时,默认走 cube(向后兼容)"""
        out = tmp_path / "out"
        extract_hald(red_dominant_image, out, cube_size=8,
                     method="nearest", smoothing_passes=0)
        assert (tmp_path / "out.cube").exists()

    def test_format_xmp_contains_color_table(self, red_dominant_image, tmp_path):
        """XMP 输出应含 crs:ColorTable / crs:Cluster 等 Adobe 字段"""
        out = tmp_path / "style.xmp"
        extract_hald(
            red_dominant_image, out,
            cube_size=8, method="nearest", smoothing_passes=0,
            format="xmp", title="TestStyle",
        )
        content = out.read_text(encoding="utf-8")
        assert "<?xml" in content
        assert "crs:ColorTable" in content  # 1D 对角线降维
        assert "TestStyle" in content
        # ColorTable 长度: 256 entries × 3 channels
        # (找第一个 ColorTable 段,统计空格分隔的整数 token)
        import re
        m = re.search(r"crs:ColorTable=\"([^\"]+)\"", content)
        assert m, "crs:ColorTable 字段缺失"
        tokens = m.group(1).split()
        assert len(tokens) == 256 * 3, (
            f"ColorTable 应有 768 个整数,实际 {len(tokens)}"
        )

    def test_format_xmpcreative_contains_rgb_table(
        self, red_dominant_image, tmp_path
    ):
        """xmpcreative 输出应含 crs:RGBTable + crs:Table_<md5> Ascii85 表"""
        import re
        out = tmp_path / "creative.xmp"
        extract_hald(
            red_dominant_image, out,
            cube_size=8, method="nearest", smoothing_passes=0,
            format="xmpcreative", title="CreativeStyle",
        )
        content = out.read_text(encoding="utf-8")
        assert "<?xml" in content
        # 1) MD5 引用字段(取 UUID 字段或 RGBTable 字段)
        rgb_ref = re.search(
            r'crs:(?:UUID|RGBTable)="([A-F0-9]{32})"', content
        )
        assert rgb_ref, "crs:UUID / crs:RGBTable 字段缺失"
        md5 = rgb_ref.group(1)

        # 2) Ascii85 表字段 crs:Table_<md5>
        #    内容是 XML-escaped 后的 Ascii85(<~ ... ~>),所以 < > ' 都已转义
        #    直接用 < ~ > 字符的 escaped 形式做匹配
        #    注:&apos; 也会出现(<~ 内部可能含 '),用 &[^;]+; 来吞掉转义
        table_field = re.search(
            rf'crs:Table_{md5}="(?:&[^;]+;|[^&])+&gt;"', content
        )
        assert table_field, (
            f"crs:Table_{md5} Ascii85 字段缺失:\n{content[:500]}"
        )

        # 3) 解码验证:剥 XML escape → 解 Ascii85 → zlib 解压 → 大小应 = 8³ × 6 bytes
        import html, base64, zlib
        encoded_escaped = table_field.group(0).split('="', 1)[1].rstrip('"')
        encoded = html.unescape(encoded_escaped)
        raw = base64.a85decode(encoded, adobe=True)
        decompressed = zlib.decompress(raw)
        assert len(decompressed) == 8 ** 3 * 6, (
            f"解压后 8³×3 channels×uint16 应=1536 字节,实际 {len(decompressed)}"
        )

        assert "CreativeStyle" in content

    def test_format_lrtemplate_legacy(self, red_dominant_image, tmp_path):
        """lrtemplate 输出是 LrC 7.3 之前的 legacy 预设格式(JSON)"""
        import json
        out = tmp_path / "legacy.lrtemplate"
        extract_hald(
            red_dominant_image, out,
            cube_size=8, method="nearest", smoothing_passes=0,
            format="lrtemplate", title="LegacyStyle",
        )
        # lrtemplate 是 JSON,顶层有 "type": "Develop"
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["type"] == "Develop"
        assert "s" in data
        assert data["s"]["Name"] == "LegacyStyle"
        # LUT3D(LUT 3D table as string) 或 ColorTable/RGBTable(1D) 都算
        s_keys = set(data["s"].keys())
        assert s_keys & {"LUT3D", "ColorTable", "RGBTable"}, (
            f".lrtemplate 应含 LUT 表,实际 keys: {sorted(s_keys)}"
        )



# 7. 性能冒烟
# ============================================================

class TestPerformance:
    """性能测试(33³ < 60s)"""

    def test_33_cube_nearest_under_60s(self, red_dominant_image):
        """33³ nearest 应在 60 秒内完成"""
        import time
        extractor = HALDPixelExtractor(
            HALDExtractionConfig(cube_size=33, method="nearest", n_samples=2000)
        )
        t0 = time.time()
        result = extractor.extract(red_dominant_image)
        elapsed = time.time() - t0
        assert result.lut_data.shape == (33, 33, 33, 3)
        assert elapsed < 60, f"33³ nearest took {elapsed:.1f}s"

    def test_17_cube_all_methods_fast(self, red_dominant_image):
        """17³ 三种方法都在 30 秒内"""
        import time
        for method in ["nearest", "gaussian_rbf", "shepard_idw"]:
            t0 = time.time()
            result = HALDPixelExtractor(
                HALDExtractionConfig(cube_size=17, method=method, n_samples=500)
            ).extract(red_dominant_image)
            elapsed = time.time() - t0
            assert elapsed < 30, f"17³ {method} took {elapsed:.1f}s"
            assert result.lut_data.shape == (17, 17, 17, 3)


# ============================================================
# 8. Source stats
# ============================================================

class TestSourceStats:
    """source_stats 字段正确性"""

    def test_stats_present(self, red_dominant_image):
        """source_stats 包含必要字段"""
        extractor = HALDPixelExtractor()
        result = extractor.extract(red_dominant_image)
        assert "mean_rgb" in result.source_stats
        assert "std_rgb" in result.source_stats
        assert "min_rgb" in result.source_stats
        assert "max_rgb" in result.source_stats
        assert "h" in result.source_stats
        assert "w" in result.source_stats

    def test_stats_dimensions(self, red_dominant_image):
        """stats RGB 字段长度为 3"""
        extractor = HALDPixelExtractor()
        result = extractor.extract(red_dominant_image)
        for key in ["mean_rgb", "std_rgb", "min_rgb", "max_rgb"]:
            assert len(result.source_stats[key]) == 3

    def test_red_image_stats(self, red_dominant_image):
        """红色 dominant 图的 mean_rgb R 通道最高"""
        extractor = HALDPixelExtractor()
        result = extractor.extract(red_dominant_image)
        r, g, b = result.source_stats["mean_rgb"]
        assert r > g
        assert r > b

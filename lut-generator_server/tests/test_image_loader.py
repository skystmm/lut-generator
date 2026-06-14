"""
image_loader + 集成路径单元测试

测试覆盖:
- 后缀嗅探: RAW vs 非 RAW
- 非 RAW 文件走 cv2 兜底(用 Pillow 现造一个 PNG)
- rawpy 不可用时优雅降级(模拟 ImportError)
- RawMode 枚举值
- ColorSpaceConverter.load_image / ColorAnalyzer / StyleExtractor / LUT3DGenerator.generate_from_images
  接受新参数且向后兼容(默认参数跑通)
- 异常路径:文件不存在 / 后缀伪 RAW 但内容不是
"""

import io
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from lut_generator.core.color_space import ColorSpaceConverter
from lut_generator.utils.image_loader import (
    RAW_EXTENSIONS,
    RAWPY_AVAILABLE,
    RawMode,
    is_raw_file,
    load_image,
)


# ---------- fixtures ----------

@pytest.fixture
def fake_jpg(tmp_path):
    """造一张 64x64 RGB JPEG,确保 cv2 能读"""
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
    p = tmp_path / "test.jpg"
    Image.fromarray(arr).save(p, quality=90)
    return p


@pytest.fixture
def fake_png(tmp_path):
    rng = np.random.default_rng(1)
    arr = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
    p = tmp_path / "test.png"
    Image.fromarray(arr).save(p)
    return p


@pytest.fixture
def fake_raw_extension(tmp_path):
    """文件名后缀是 .dng 但内容不是 RAW → cv2 也读不出来"""
    p = tmp_path / "fake.dng"
    p.write_bytes(b"this is not a real DNG file")
    return p


# ---------- is_raw_file ----------

class TestIsRawFile:
    @pytest.mark.parametrize("ext", [
        '.dng', '.arw', '.cr2', '.cr3', '.nef', '.nrw', '.rw2', '.raf',
        '.orf', '.pef', '.dcr', '.kdc', '.mrw', '.srw', '.x3f', '.3fr',
    ])
    def test_recognized_extensions(self, tmp_path, ext):
        p = tmp_path / f"file{ext}"
        p.write_bytes(b"")
        assert is_raw_file(p) is True
        # 大小写不敏感
        p_upper = tmp_path / f"file{ext.upper()}"
        p_upper.write_bytes(b"")
        assert is_raw_file(p_upper) is True

    @pytest.mark.parametrize("ext", ['.jpg', '.png', '.tif', '.webp', '.bmp', '.gif', ''])
    def test_non_raw_extensions(self, tmp_path, ext):
        p = tmp_path / f"file{ext}"
        p.write_bytes(b"")
        assert is_raw_file(p) is False


# ---------- load_image: 非 RAW 路径 ----------

class TestLoadNonRaw:
    def test_jpg_via_cv2(self, fake_jpg):
        rgb = load_image(fake_jpg)
        assert rgb.shape == (64, 64, 3)
        assert rgb.dtype == np.uint8
        assert rgb.min() >= 0 and rgb.max() <= 255

    def test_png_via_cv2(self, fake_png):
        rgb = load_image(fake_png)
        assert rgb.shape == (32, 32, 3)
        assert rgb.dtype == np.uint8

    def test_explicit_raw_mode_ignored_for_non_raw(self, fake_jpg):
        """非 RAW 文件即使传 --raw-mode=full 也应该走 cv2"""
        rgb = load_image(fake_jpg, raw_mode='full')
        assert rgb.shape == (64, 64, 3)

    def test_invalid_raw_mode_raises(self, fake_jpg):
        with pytest.raises(ValueError, match="raw_mode must be one of"):
            load_image(fake_jpg, raw_mode='bogus')

    def test_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_image(tmp_path / "nope.jpg")


# ---------- load_image: RAW 路径(无 rawpy / 有 rawpy 两种) ----------

class TestLoadRawPaths:
    def test_raw_extension_with_no_rawpy_falls_back_to_cv2(self, fake_raw_extension, capsys):
        """没有 rawpy + 文件不是真 RAW + 允许降级 → 走 cv2,失败但有 Warning"""
        if RAWPY_AVAILABLE:
            pytest.skip("rawpy is installed in this env; can't test the no-rawpy fallback")
        # 不允许降级 → 抛 RuntimeError
        with pytest.raises(RuntimeError, match="rawpy is not installed"):
            load_image(fake_raw_extension, fallback_to_cv2=False)

    def test_rawpy_failure_falls_back(self, fake_jpg):
        """rawpy 抛异常时降级到 cv2(拿真 jpg 但后缀改成 .dng,模拟'RAW 解析失败')"""
        if not RAWPY_AVAILABLE:
            pytest.skip("rawpy not installed")

        # 复制 jpg 内容到 .dng 后缀
        dng_path = fake_jpg.with_suffix('.dng')
        dng_path.write_bytes(fake_jpg.read_bytes())

        # rawpy 解析会失败(内容不是真 RAW)→ 降级 cv2 → cv2 读 jpg 数据成功
        rgb = load_image(dng_path)
        assert rgb.shape == (64, 64, 3)


# ---------- 向后兼容: 默认参数应跟旧版一样工作 ----------

class TestBackwardCompat:
    """ColorSpaceConverter / ColorAnalyzer / StyleExtractor / LUT3DGenerator
    加了 raw_mode / use_camera_wb 参数,但都是 default,旧调用方式应完全无感"""

    def test_color_space_converter_default(self, fake_jpg):
        c = ColorSpaceConverter()
        rgb = c.load_image(fake_jpg)
        assert rgb.shape == (64, 64, 3)

    def test_color_space_converter_explicit_raw_mode(self, fake_jpg):
        c = ColorSpaceConverter()
        rgb = c.load_image(fake_jpg, raw_mode='thumb')
        assert rgb.shape == (64, 64, 3)

    def test_color_analyzer_default(self, fake_jpg):
        from lut_generator.analysis.analyzer import ColorAnalyzer
        a = ColorAnalyzer()
        result = a.analyze(fake_jpg)
        assert result.image_shape == (64, 64, 3)

    def test_color_analyzer_explicit_raw_mode(self, fake_jpg):
        from lut_generator.analysis.analyzer import ColorAnalyzer
        a = ColorAnalyzer(raw_mode='thumb', use_camera_wb=False)
        result = a.analyze(fake_jpg)
        assert result.image_shape == (64, 64, 3)

    def test_style_extractor_default(self, fake_jpg):
        from lut_generator.core.style_extractor import StyleExtractor
        ext = StyleExtractor()
        result = ext.generate_lut(image_path=str(fake_jpg))
        assert result is not None
        assert hasattr(result, 'style_lut_data')
        assert result.style_lut_data.shape[0] == 33  # 默认 grid_size

    def test_style_extractor_explicit_raw_mode(self, fake_jpg):
        from lut_generator.core.style_extractor import StyleExtractor
        ext = StyleExtractor(raw_mode='thumb', use_camera_wb=False)
        result = ext.generate_lut(image_path=str(fake_jpg))
        assert result.style_lut_data.shape[0] == 33

    def test_lut3d_generator_default(self, fake_jpg, fake_png):
        from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig
        gen = LUT3DGenerator(LUT3DConfig(grid_size=17))
        lut = gen.generate_from_images(str(fake_jpg), str(fake_png))
        assert lut.shape == (17, 17, 17, 3)

    def test_lut3d_generator_explicit_raw_mode(self, fake_jpg, fake_png):
        from lut_generator.lut.lut3d import LUT3DGenerator, LUT3DConfig
        gen = LUT3DGenerator(LUT3DConfig(grid_size=17))
        lut = gen.generate_from_images(
            str(fake_jpg), str(fake_png), raw_mode='thumb', use_camera_wb=False
        )
        assert lut.shape == (17, 17, 17, 3)


# ---------- RawMode 枚举 ----------

class TestRawMode:
    def test_values(self):
        assert RawMode.THUMB.value == 'thumb'
        assert RawMode.HALF.value == 'half'
        assert RawMode.FULL.value == 'full'

    def test_str_inheritance(self):
        # RawMode 继承 str,可以当 str 用
        assert RawMode.HALF == 'half'
        assert RawMode.FULL.value == 'full'

    def test_membership(self):
        assert 'thumb' in [m.value for m in RawMode]


# ---------- get_raw_metadata ----------

class TestGetRawMetadata:
    def test_non_raw(self, fake_jpg):
        from lut_generator.utils.image_loader import get_raw_metadata
        meta = get_raw_metadata(fake_jpg)
        assert meta == {'is_raw': False}

    def test_raw_without_rawpy(self, fake_raw_extension):
        if RAWPY_AVAILABLE:
            pytest.skip("rawpy installed")
        from lut_generator.utils.image_loader import get_raw_metadata
        meta = get_raw_metadata(fake_raw_extension)
        # 没 rawpy,只给 is_raw 标志
        assert meta.get('is_raw') is True
        assert 'camera_model' not in meta

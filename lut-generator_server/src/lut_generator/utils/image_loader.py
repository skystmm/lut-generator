"""
RAW 图像读取 - image_loader

把相机 RAW (.dng / .arw / .cr2 / .cr3 / .nef / .rw2 / .raf / .orf / .pef 等
600+ 机型) 转成 numpy RGB uint8。

依赖 rawpy(LibRaw 的 Python 绑定,事实标准)。
非 RAW 格式 (.jpg / .png / .tif / .webp ...) 直接走 OpenCV 兜底。

设计要点:
- 后缀嗅探 + rawpy.open() 异常检测 —— 失败优雅降级到 cv2
- 3 档输出质量:
    thumb  — 相机內建 JPEG 缩略图, ~10ms, 适合"快速提取风格"
    half   — 半尺寸 demosaic + 8-bit RGB, ~200ms/24MP, **默认**
    full   — 全尺寸 demosaic + 16-bit RGB(返回 8-bit), ~1-2s/24MP
- 不做白平衡/曝光/曲线调整(那些是 LUT 之后用户自己搞的事)
  唯一例外:用相机內建白平衡(white_balance='auto' 默认)以避免极端偏色
"""

import os
from enum import Enum
from pathlib import Path
from typing import Union

import cv2
import numpy as np

try:
    import rawpy
    RAWPY_AVAILABLE = True
except ImportError:
    RAWPY_AVAILABLE = False


# LibRaw / 主流相机 RAW 后缀 —— 嗅探用(不区分大小写)
RAW_EXTENSIONS = frozenset({
    '.dng',   # Adobe Digital Negative
    '.arw',   # Sony Alpha Raw
    '.cr2',   # Canon Raw v2
    '.cr3',   # Canon Raw v3
    '.nef',   # Nikon Electronic Format
    '.nrw',   # Nikon Coolpix
    '.rw2',   # Panasonic Raw
    '.raf',   # Fuji Raw
    '.orf',   # Olympus Raw
    '.pef',   # Pentax Electronic Format
    '.dcr',   # Kodak Raw
    '.kdc',   # Kodak
    '.mrw',   # Minolta Raw
    '.srw',   # Samsung Raw
    '.x3f',   # Sigma Foveon
    '.3fr',   # Hasselblad
    '.fff',   # Hasselblad
    '.iiq',   # Phase One
    '.ari',   # ARRIRAW
})


class RawMode(str, Enum):
    """RAW 解码档位"""
    THUMB = 'thumb'   # 內建 JPEG 缩略图,最快,精度低
    HALF = 'half'     # 半尺寸 demosaic + 8-bit,默认
    FULL = 'full'     # 全尺寸 demosaic + 16-bit(返回 8-bit)


def is_raw_file(path: Union[str, Path]) -> bool:
    """根据后缀判断是否 RAW 文件(不区分大小写)"""
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def load_image(image_path: Union[str, Path],
               raw_mode: Union[str, RawMode] = RawMode.HALF,
               use_camera_wb: bool = True,
               fallback_to_cv2: bool = True) -> np.ndarray:
    """
    加载图像(支持相机 RAW),返回 RGB uint8 (H, W, 3)。

    Args:
        image_path: 图像路径
        raw_mode: 'thumb' / 'half' / 'full'
            - thumb:相机內建 JPEG 缩略图(几 ms)
            - half:半尺寸 demosaic + 8-bit RGB(默认,~200ms/24MP)
            - full:全尺寸 demosaic + 16-bit(自动转 8-bit,~1-2s/24MP)
        use_camera_wb: 是否用相机內建白平衡(默认 True 避免 RAW 偏色极端)
        fallback_to_cv2: RAW 解析失败时是否降级到 cv2.imread(默认 True)

    Returns:
        RGB uint8 数组,shape=(H, W, 3)

    Raises:
        FileNotFoundError: 路径不存在
        ValueError: 文件无法被任何后端读取
        RuntimeError: RAW 文件但 rawpy 未安装且未允许降级
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # 0) 先校验 raw_mode(不管文件是不是 RAW,都先验,免得 typo 静默通过)
    if isinstance(raw_mode, str):
        try:
            raw_mode = RawMode(raw_mode.lower())
        except ValueError as e:
            raise ValueError(
                f"raw_mode must be one of {[m.value for m in RawMode]}, got {raw_mode!r}"
            ) from e
    elif not isinstance(raw_mode, RawMode):
        raise TypeError(f"raw_mode must be str or RawMode, got {type(raw_mode).__name__}")

    # 1) 非 RAW → 直接走 OpenCV(最稳)
    if not is_raw_file(image_path):
        return _load_with_cv2(image_path)

    # 2) RAW → rawpy
    if not RAWPY_AVAILABLE:
        if fallback_to_cv2:
            # 提示但不抛错,让用户有降级路径
            print(f"Warning: rawpy not installed, falling back to cv2 for {image_path.name}.")
            return _load_with_cv2(image_path)
        raise RuntimeError(
            f"RAW file detected ({image_path.suffix}) but rawpy is not installed. "
            f"Install with: pip install rawpy"
        )

    return _load_with_rawpy(image_path, raw_mode, use_camera_wb, fallback_to_cv2)


def _load_with_rawpy(image_path: Path,
                     raw_mode: RawMode,
                     use_camera_wb: bool,
                     fallback_to_cv2: bool) -> np.ndarray:
    """rawpy 解码 + 后处理"""
    try:
        with rawpy.imread(str(image_path)) as raw:
            if raw_mode == RawMode.THUMB:
                # 內建缩略图:LibRaw 解析后存在 raw.thumbnail
                # 极少数 RAW 不带缩略图 → 降级到 half
                try:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        arr = np.frombuffer(thumb.data, dtype=np.uint8)
                        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if bgr is None:
                            raise ValueError("cv2.imdecode returned None for thumbnail")
                        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                    raise ValueError(f"Unsupported thumbnail format: {thumb.format}")
                except Exception as e:
                    if not fallback_to_cv2:
                        raise
                    print(f"Warning: thumbnail unavailable ({e}), falling back to half mode")
                    return _demosaic(raw, RawMode.HALF, use_camera_wb)

            return _demosaic(raw, raw_mode, use_camera_wb)

    except Exception as e:
        if not fallback_to_cv2:
            raise RuntimeError(f"rawpy failed to read {image_path}: {e}") from e
        print(f"Warning: rawpy failed ({e}), falling back to cv2 for {image_path.name}")
        return _load_with_cv2(image_path)


def _demosaic(raw, raw_mode: RawMode, use_camera_wb: bool) -> np.ndarray:
    """rawpy.postprocess() 调 demosaic,做后处理"""
    # half 模式:num_bits=8 + half_size=True,4 倍快、内存 1/4
    if raw_mode == RawMode.HALF:
        rgb16 = raw.postprocess(
            demosaic_algorithm=rawpy.DemosaicAlgorithm.LINEAR,
            half_size=True,
            use_camera_wb=use_camera_wb,
            no_auto_bright=True,
            output_bps=8,
        )
        return rgb16  # 已经是 uint8

    # full 模式:num_bits=16 + 4 通道(去掉 alpha) + 高质量 demosaic
    rgb16 = raw.postprocess(
        demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,    # AHD 是最准的
        use_camera_wb=use_camera_wb,
        no_auto_bright=True,
        output_bps=16,
    )
    # 16-bit → 8-bit 简单降位(gamma 留给 LUT 之后)
    return (rgb16 >> 8).astype(np.uint8)


def _load_with_cv2(image_path: Path) -> np.ndarray:
    """非 RAW 后备路径(原 cv2.imread + BGR→RGB)"""
    img_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(
            f"Failed to load image: {image_path}. "
            f"If this is a RAW file, install rawpy: pip install rawpy"
        )
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def get_raw_metadata(image_path: Union[str, Path]) -> dict:
    """
    读 RAW 文件的元数据(机型/ISO/快门/光圈/白平衡等)。
    非 RAW 文件返回空 dict。

    Returns:
        dict 含 keys:
            - is_raw: bool
            - camera_make / camera_model: str
            - raw_width / raw_height: int(原始 RAW 像素,通常 > 输出尺寸)
            - num_colors: int(通常 3=RGB 或 4=RGBG)
            - iso_speed / shutter / aperture: float|None
    """
    if not is_raw_file(image_path) or not RAWPY_AVAILABLE:
        return {'is_raw': is_raw_file(image_path)}

    with rawpy.imread(str(image_path)) as raw:
        return {
            'is_raw': True,
            'camera_make': raw.camera_make or '',
            'camera_model': raw.camera_model or '',
            'raw_width': raw.sizes.raw_width,
            'raw_height': raw.sizes.raw_height,
            'num_colors': raw.num_colors,
            'iso_speed': getattr(raw, 'iso_speed', None),
            'shutter': getattr(raw, 'shutter', None),
            'aperture': getattr(raw, 'aperture', None),
        }

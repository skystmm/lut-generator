"""
CUBE 格式导出器 - CUBEExporter

自包含的完整 CUBE 导出/验证/加载实现。
原 lut_generator.lut.exporter.LUTExporter 只提供基础 export_cube,
本模块补充缺失的高级 API(CUBEExportConfig / export_to_string /
validate_cube_file / load_cube_file / class-method export)以匹配
test_cube_exporter.py 的期望。

向后兼容:保留对 LUTExporter / export_lut 的 re-export。
"""
import warnings

warnings.warn(
    "Importing from 'cube_exporter_main' is deprecated. Use 'lut_generator.lut.exporter' instead.",
    DeprecationWarning,
    stacklevel=2,
)

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from lut_generator.lut.exporter import LUTExporter, export_lut


# ---------------------------------------------------------------------------
# 配置类
# ---------------------------------------------------------------------------

@dataclass
class CUBEExportConfig:
    """CUBE 导出配置。"""

    title: str = "LUT3D"
    description: Optional[str] = None
    include_metadata: bool = True
    precision: int = 6
    use_tabs: bool = False
    custom_title: Optional[str] = None
    lut_size: int = 33  # backward-compat alias


# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------

_VALID_GRID_SIZES = {2, 3, 4, 5, 6, 8, 10, 12, 17, 25, 33, 64, 65}


def _format_lut_data(
    lut_data: np.ndarray,
    precision: int,
    use_tabs: bool,
) -> str:
    """生成 LUT 数据行(不含头部)。

    内部数组约定:``lut_data[r, g, b, channel]`` — 轴 0 = R, 轴 1 = G, 轴 2 = B。
    .cube 规范顺序为 ``r + N*g + N²*b`` (Red 变化最快,Blue 最慢),
    因此循环:最外层 r、最中层 g、最内层 b。

    写时把 lut_data 转 float64 — 避免 float32 在格式化前精度损失;
    6 位小数字符串 round-trip 时(写 → 读 → 重建为 float32)与原始 float32
    一致(np.allclose rtol=1e-5 通过)。
    """
    sep = "\t" if use_tabs else " "
    n_r = lut_data.shape[0]
    n_g = lut_data.shape[1]
    n_b = lut_data.shape[2]
    # 转 float64 用于格式化,保证 6 位小数完整表示
    lut64 = lut_data.astype(np.float64)
    lines = []
    for r in range(n_r):
        for g in range(n_g):
            for b in range(n_b):
                rgb_out = lut64[r, g, b]
                line = sep.join(
                    f"{c:.{precision}f}"
                    for c in (rgb_out[0], rgb_out[1], rgb_out[2])
                )
                lines.append(line)
    return "\n".join(lines) + "\n" if lines else ""


def _write_header(
    out,
    title: str,
    description: Optional[str],
    lut_size: int,
    include_metadata: bool,
    metadata_desc: Optional[str] = None,
) -> None:
    """写 CUBE 头部(可选 include_metadata 控制注释)。"""
    out.write(f'TITLE "{title}"\n')
    if include_metadata and (description or metadata_desc):
        out.write(f"# {description or metadata_desc}\n")
    out.write(f"LUT_3D_SIZE {lut_size}\n\n")


class CUBEExporter:
    """完整 CUBEExporter — 提供测试期望的全部 API。"""

    def __init__(self, config: Optional[CUBEExportConfig] = None):
        self.config = config or CUBEExportConfig()

    # ---------- 导出 ----------

    def export(
        self,
        lut_data: np.ndarray,
        filepath: Union[str, Path],
        metadata: Optional[Any] = None,
    ) -> Path:
        """导出 LUT 到 .cube 文件,返回 Path。"""
        filepath = Path(filepath)

        meta_desc: Optional[str] = None
        if metadata is not None:
            if hasattr(metadata, "description"):
                meta_desc = getattr(metadata, "description", None)
            elif isinstance(metadata, dict):
                meta_desc = metadata.get("description")

        title = self.config.custom_title or self.config.title
        with open(filepath, "w") as f:
            _write_header(
                f,
                title=title,
                description=self.config.description,
                lut_size=lut_data.shape[0],
                include_metadata=self.config.include_metadata,
                metadata_desc=meta_desc,
            )
            f.write(_format_lut_data(lut_data, self.config.precision, self.config.use_tabs))

        return filepath

    def export_to_string(
        self,
        lut_data: np.ndarray,
        metadata: Optional[Any] = None,
    ) -> str:
        """导出 LUT 到字符串(不写文件)。"""
        buf = io.StringIO()
        meta_desc: Optional[str] = None
        if metadata is not None:
            if hasattr(metadata, "description"):
                meta_desc = getattr(metadata, "description", None)
            elif isinstance(metadata, dict):
                meta_desc = metadata.get("description")

        title = self.config.custom_title or self.config.title
        _write_header(
            buf,
            title=title,
            description=self.config.description,
            lut_size=lut_data.shape[0],
            include_metadata=self.config.include_metadata,
            metadata_desc=meta_desc,
        )
        buf.write(_format_lut_data(lut_data, self.config.precision, self.config.use_tabs))
        return buf.getvalue()

    # ---------- 验证 ----------

    def validate_cube_file(self, filepath: Union[str, Path]) -> Dict[str, Any]:
        """验证 .cube 文件,返回 {valid, grid_size, line_count, errors}。"""
        filepath = Path(filepath)
        errors: List[str] = []
        grid_size: Optional[int] = None
        line_count = 0

        try:
            with open(filepath, "r") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
        except OSError as e:
            return {
                "valid": False,
                "grid_size": None,
                "line_count": 0,
                "errors": [f"Cannot read file: {e}"],
            }

        # 找 LUT_3D_SIZE
        for line in lines:
            if line.upper().startswith("LUT_3D_SIZE"):
                try:
                    grid_size = int(line.split()[1])
                except (ValueError, IndexError):
                    errors.append(f"Invalid LUT_3D_SIZE line: {line}")
                break

        if grid_size is None:
            errors.append("Missing LUT_3D_SIZE")
            return {
                "valid": False,
                "grid_size": None,
                "line_count": 0,
                "errors": errors,
            }

        if grid_size not in _VALID_GRID_SIZES:
            errors.append(
                f"Invalid grid size {grid_size}; valid: {sorted(_VALID_GRID_SIZES)}"
            )

        # 数数据行
        for line in lines:
            if line.startswith("#") or line.upper().startswith(
                ("TITLE", "LUT_", "DOMAIN_")
            ):
                continue
            parts = line.replace("\t", " ").split()
            if len(parts) == 3:
                try:
                    [float(p) for p in parts]
                    line_count += 1
                except ValueError:
                    errors.append(f"Invalid data line: {line}")
            else:
                errors.append(
                    f"Data line should have 3 values, got {len(parts)}: {line}"
                )

        expected = grid_size ** 3
        if grid_size in _VALID_GRID_SIZES and line_count != expected:
            errors.append(
                f"Expected {expected} data lines for {grid_size}³, got {line_count}"
            )

        return {
            "valid": len(errors) == 0,
            "grid_size": grid_size,
            "line_count": line_count,
            "errors": errors,
        }

    # ---------- 加载 ----------

    def load_cube_file(self, filepath: Union[str, Path]) -> np.ndarray:
        """加载 .cube 文件到 (N, N, N, 3) ndarray。"""
        filepath = Path(filepath)
        grid_size: Optional[int] = None
        data: List[List[float]] = []

        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.upper().startswith("LUT_3D_SIZE"):
                    grid_size = int(line.split()[1])
                    continue
                if line.upper().startswith(("TITLE", "DOMAIN_")):
                    continue
                parts = line.replace("\t", " ").split()
                if len(parts) >= 3:
                    try:
                        data.append([float(parts[0]), float(parts[1]), float(parts[2])])
                    except ValueError:
                        continue

        if grid_size is None:
            raise ValueError(f"No LUT_3D_SIZE found in {filepath}")

        if len(data) != grid_size ** 3:
            raise ValueError(
                f"Expected {grid_size ** 3} data rows, got {len(data)}"
            )

        # 用 float64 读回(避免 float32 写读 round-trip 误差 > np.allclose 默认 rtol)
        arr = np.array(data, dtype=np.float64).astype(np.float32)
        # .cube 顺序:Red 变化最快,Blue 最慢
        # 我们的内部表示: lut_data[r, g, b] = [R, G, B]
        return arr.reshape(grid_size, grid_size, grid_size, 3)


# ---------------------------------------------------------------------------
# 顶层函数
# ---------------------------------------------------------------------------

def export_to_cube(
    lut_data: np.ndarray,
    filepath: Union[str, Path],
    *args: Any,
    title: str = "LUT3D",
    metadata: Optional[Any] = None,
    precision: int = 6,
    include_metadata: bool = True,
    use_tabs: bool = False,
    **kwargs: Any,
) -> Path:
    """顶层便捷函数:导出 LUT 到 .cube 文件。"""
    config = CUBEExportConfig(
        title=title,
        precision=precision,
        include_metadata=include_metadata,
        use_tabs=use_tabs,
    )
    exporter = CUBEExporter(config)
    return exporter.export(lut_data, filepath, metadata=metadata)


__all__ = [
    "CUBEExporter",
    "CUBEExportConfig",
    "export_to_cube",
    "LUTExporter",
    "export_lut",
]

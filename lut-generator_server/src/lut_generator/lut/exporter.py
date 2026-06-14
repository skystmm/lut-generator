"""
LUT 导出模块 - LUTExporter

支持多种 LUT 格式导出：
- CUBE (Adobe)
- 3DL (Autodesk Lustre)
- clf (ACES)
"""

import numpy as np
from typing import Union
from pathlib import Path
from datetime import datetime


class LUTExporter:
    """
    LUT 导出器
    
    支持多种专业软件兼容的 LUT 格式
    """
    
    def __init__(self, lut_data: np.ndarray, metadata: dict = None):
        """
        初始化导出器
        
        Args:
            lut_data: 3D LUT 数据，shape=(N, N, N, 3)
            metadata: 元数据字典
        """
        self.lut_data = lut_data
        self.metadata = metadata or {}
        self.grid_size = lut_data.shape[0]
    
    def export_cube(self, filepath: Union[str, Path], 
                    title: str = None,
                    description: str = None) -> None:
        """
        导出为 CUBE 格式 (Adobe)
        
        Args:
            filepath: 输出文件路径
            title: LUT 标题
            description: LUT 描述
        """
        filepath = Path(filepath)
        
        title = title or self.metadata.get('title', 'LUT')
        description = description or self.metadata.get('description', '')
        
        try:
            with open(filepath, 'w') as f:
                # 写入头部信息
                f.write(f"TITLE \"{title}\"\n")
                if description:
                    f.write(f"# {description}\n")
                f.write(f"# Created: {datetime.now().isoformat()}\n")
                f.write(f"# LUT size: {self.grid_size}^3\n\n")
                
                # 写入 LUT 维度
                f.write(f"LUT_3D_SIZE {self.grid_size}\n\n")
                
                # 写入数据范围
                f.write("DOMAIN_MIN 0.0 0.0 0.0\n")
                f.write("DOMAIN_MAX 1.0 1.0 1.0\n\n")
                
                # 写入 LUT 数据
                # CUBE 格式顺序：B, G, R (从低到高)
                for b in range(self.grid_size):
                    for g in range(self.grid_size):
                        for r in range(self.grid_size):
                            rgb_out = self.lut_data[r, g, b]
                            f.write(f"{rgb_out[0]:.6f} {rgb_out[1]:.6f} {rgb_out[2]:.6f}\n")
        except IOError as e:
            raise IOError(f"Failed to write CUBE file to {filepath}: {e}") from e
        except OSError as e:
            raise OSError(f"OS error while writing CUBE file to {filepath}: {e}") from e
    
    def export_3dl(self, filepath: Union[str, Path],
                   bit_depth: int = 10,
                   title: str = None) -> None:
        """
        导出为 3DL 格式 (Autodesk Lustre)
        
        Args:
            filepath: 输出文件路径
            bit_depth: 位深度 (8, 10, 12, 16)
            title: LUT 标题
        """
        filepath = Path(filepath)
        
        title = title or self.metadata.get('title', 'LUT')
        max_val = (1 << bit_depth) - 1
        
        try:
            with open(filepath, 'w') as f:
                # 写入头部
                f.write(f"3DL lut\n")
                f.write(f"# {title}\n")
                f.write(f"# Created: {datetime.now().isoformat()}\n")
                f.write(f"# Bit depth: {bit_depth}\n\n")
                
                # 写入维度和位深度
                f.write(f"Input {bit_depth} {bit_depth} {bit_depth}\n")
                f.write(f"Output {bit_depth} {bit_depth} {bit_depth}\n")
                f.write(f"Size {self.grid_size} {self.grid_size} {self.grid_size}\n\n")
                
                # 写入 LUT 数据
                # 3DL 格式顺序：R, G, B (从高到低)
                lut_scaled = (self.lut_data * max_val).astype(np.uint16)
                
                for r in range(self.grid_size):
                    for g in range(self.grid_size):
                        for b in range(self.grid_size):
                            rgb_out = lut_scaled[r, g, b]
                            f.write(f"{rgb_out[0]} {rgb_out[1]} {rgb_out[2]}\n")
        except IOError as e:
            raise IOError(f"Failed to write 3DL file to {filepath}: {e}") from e
        except OSError as e:
            raise OSError(f"OS error while writing 3DL file to {filepath}: {e}") from e
    
    def export_clf(self, filepath: Union[str, Path],
                   title: str = None) -> None:
        """
        导出为 clf 格式 (ACES Common LUT Format)
        
        Args:
            filepath: 输出文件路径
            title: LUT 标题
        """
        filepath = Path(filepath)
        title = title or self.metadata.get('title', 'LUT')
        
        # clf 是 XML 格式
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<ProcessList version="1.3" id="{title}">
    <Description>{self.metadata.get('description', '')}</Description>
    <InputDescriptor>sRGB</InputDescriptor>
    <OutputDescriptor>sRGB</OutputDescriptor>
    <LUT3D id="{title}_3d" interpolation="trilinear">
        <Array dimension="{self.grid_size} {self.grid_size} {self.grid_size} 3">
'''
        
        # 写入数据
        for b in range(self.grid_size):
            for g in range(self.grid_size):
                row_values = []
                for r in range(self.grid_size):
                    rgb_out = self.lut_data[r, g, b]
                    row_values.append(f"{rgb_out[0]:.6f} {rgb_out[1]:.6f} {rgb_out[2]:.6f}")
                xml_content += "            " + " ".join(row_values) + "\n"
        
        xml_content += '''        </Array>
    </LUT3D>
</ProcessList>
'''
        
        try:
            with open(filepath, 'w') as f:
                f.write(xml_content)
        except IOError as e:
            raise IOError(f"Failed to write CLF file to {filepath}: {e}") from e
        except OSError as e:
            raise OSError(f"OS error while writing CLF file to {filepath}: {e}") from e
    
    def export_xmp_preset(self,
                          filepath: Union[str, Path],
                          title: str = None,
                          group: str = 'lut-generator:UserPresets',
                          preset_type: str = 'Normal',
                          apply_amount: float = 1.0,
                          process_version: str = '15.4',
                          include_slider: bool = True,
                          supports_amount: bool = True,
                          copy_to_clipboard: bool = False) -> None:
        """
        导出为 Adobe XMP 预设 (.xmp),可被 Lightroom / Lightroom Classic /
        Adobe Camera Raw / Photoshop (经 ACR) 加载应用。

        原理:把 3D LUT 沿主对角线 (i, i, i) 降维成 3 条 256 点的 1D 映射
        (R/G/B 各 256),写入 XMP `crs:ColorTable`(空格分隔的 0-65535 整数)。
        这是 Adobe 创意预设(包含「颜色查找表」/LUT 类)的标准存放位置。

        Args:
            filepath: 输出 .xmp 路径
            title: 预设名称(同时作为 .xmp 文件名建议)
            group: 在 LR 预设面板中的分组(默认 `lut-generator:UserPresets`)
            preset_type: `Normal` / `Auto` / `Video` (LR 分类)
            apply_amount: 0.0-1.0,预设应用强度
            process_version: `crs:ProcessVersion`,LR 用 15.4 (CC 2020+)
            include_slider: 是否带 Amount 滑块
            supports_amount: `crs:SupportsAmount`
            copy_to_clipboard: 仅在 XMP 里写 `crs:Cluster` 提示,不影响功能
        """
        filepath = Path(filepath)
        if filepath.suffix == '':
            filepath = filepath.with_suffix('.xmp')

        title = title or self.metadata.get('title', 'LUT Preset')
        title = self._xml_escape(title)
        group = self._xml_escape(group)
        preset_type = self._xml_escape(preset_type)

        # 1) 沿主对角线 (i, i, i) 采样 → 3 条 1D 256-entry 映射
        r_table, g_table, b_table = self._lut_to_color_table()

        # 2) 拼成 768 个空格分隔的 0-65535 整数
        color_table = ' '.join(
            f"{r_table[i]:d} {g_table[i]:d} {b_table[i]:d}"
            for i in range(256)
        )

        # 3) 拼 XMP(参照 Lightroom Classic 创意预设的字段集合)
        xmp = self._build_xmp_preset_xml(
            title=title,
            group=group,
            preset_type=preset_type,
            color_table=color_table,
            apply_amount=apply_amount,
            process_version=process_version,
            include_slider=include_slider,
            supports_amount=supports_amount,
            copy_to_clipboard=copy_to_clipboard,
        )

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(xmp)
        except IOError as e:
            raise IOError(f"Failed to write XMP preset to {filepath}: {e}") from e
        except OSError as e:
            raise OSError(f"OS error while writing XMP preset to {filepath}: {e}") from e

    def _lut_to_color_table(self) -> tuple:
        """
        沿主对角线 (i, i, i) 采样 3D LUT,得到 3 条 1D 256-entry 映射。
        输入坐标 = (i/255, i/255, i/255) → 输出 RGB 截到 [0,1] → 量化到 16-bit。

        当 grid_size == 256 时,直接取对角线;否则用 numpy 三线性插值
        沿对角线采 256 点(避免强依赖 scipy)。
        """
        if self.grid_size == 256:
            diag = self.lut_data[np.arange(256), np.arange(256), np.arange(256)]
        else:
            diag = self._trilinear_diag(self.lut_data, 256)

        diag = np.clip(diag, 0.0, 1.0)
        diag_int = np.round(diag * 65535).astype(np.uint32)
        return diag_int[:, 0].tolist(), diag_int[:, 1].tolist(), diag_int[:, 2].tolist()

    @staticmethod
    def _trilinear_diag(lut: np.ndarray, samples: int) -> np.ndarray:
        """
        沿主对角线方向做三线性插值。纯 numpy 实现,不依赖 scipy。

        把对角线方向归一化到 0..1,在 0..1 上等距采 `samples` 个点,
        然后逐点三线性插值。
        """
        N = lut.shape[0]  # grid_size
        if N == 1:
            return np.broadcast_to(lut[0, 0, 0], (samples, 3)).copy()

        t = np.linspace(0.0, 1.0, samples)  # (samples,)
        # 在 N³ 网格坐标里 = t * (N-1)
        pos = t * (N - 1)                    # (samples,)
        idx0 = np.floor(pos).astype(np.int64)
        idx1 = np.minimum(idx0 + 1, N - 1)
        frac = (pos - idx0).astype(np.float32)  # (samples,)

        # 在三个维度上同时插值(因为对角线 r=g=b,所以每维都是 frac)
        f = frac  # (samples,)
        f0 = 1.0 - f

        # 取 8 个角的 RGB
        v000 = lut[idx0, idx0, idx0]   # (samples, 3)
        v100 = lut[idx1, idx0, idx0]
        v010 = lut[idx0, idx1, idx0]
        v110 = lut[idx1, idx1, idx0]
        v001 = lut[idx0, idx0, idx1]
        v101 = lut[idx1, idx0, idx1]
        v011 = lut[idx0, idx1, idx1]
        v111 = lut[idx1, idx1, idx1]

        # 8 角分别加权
        c000 = f0 * f0 * f0
        c100 = f  * f0 * f0
        c010 = f0 * f  * f0
        c110 = f  * f  * f0
        c001 = f0 * f0 * f
        c101 = f  * f0 * f
        c011 = f0 * f  * f
        c111 = f  * f  * f

        # (samples, 1) 广播到 (samples, 3)
        out = (
            v000 * c000[:, None] + v100 * c100[:, None] +
            v010 * c010[:, None] + v110 * c110[:, None] +
            v001 * c001[:, None] + v101 * c101[:, None] +
            v011 * c011[:, None] + v111 * c111[:, None]
        )
        return out

    @staticmethod
    def _xml_escape(s: str) -> str:
        return (s.replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;')
                 .replace('"', '&quot;')
                 .replace("'", '&apos;'))

    def _build_xmp_preset_xml(self,
                              title: str,
                              group: str,
                              preset_type: str,
                              color_table: str,
                              apply_amount: float,
                              process_version: str,
                              include_slider: bool,
                              supports_amount: bool,
                              copy_to_clipboard: bool) -> str:
        amount_block = (
            f'   <crs:Amount>{apply_amount:.4f}</crs:Amount>\n'
            if include_slider else ''
        )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="lut-generator 1.0">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
    crs:PresetType="{preset_type}"
    crs:Cluster="{group}"
    crs:Name="{title}"
    crs:SupportsAmount="{'True' if supports_amount else 'False'}"
    crs:ProcessVersion="{process_version}"
    crs:ColorTableVersion="1"
    crs:ColorTable="{color_table}">
{amount_block}  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
'''

    def export(self, filepath: Union[str, Path], 
               format: str = 'cube',
               **kwargs) -> None:
        """
        通用导出方法
        
        Args:
            filepath: 输出文件路径
            format: 输出格式 ('cube', '3dl', 'clf', 'xmp')
            **kwargs: 格式特定参数
                - xmp: title / group / preset_type / apply_amount / process_version
        """
        format = format.lower()
        
        if format == 'cube':
            self.export_cube(filepath, **kwargs)
        elif format == '3dl':
            self.export_3dl(filepath, **kwargs)
        elif format == 'clf':
            self.export_clf(filepath, **kwargs)
        elif format == 'xmp':
            self.export_xmp_preset(filepath, **kwargs)
        else:
            raise ValueError(f"Unknown format: {format}")


def export_lut(lut_data: np.ndarray, filepath: Union[str, Path],
               format: str = 'cube', **kwargs) -> None:
    """
    便捷函数：导出 LUT
    
    Args:
        lut_data: LUT 数据
        filepath: 输出路径
        format: 输出格式
        **kwargs: 其他参数
    """
    exporter = LUTExporter(lut_data)
    exporter.export(filepath, format, **kwargs)
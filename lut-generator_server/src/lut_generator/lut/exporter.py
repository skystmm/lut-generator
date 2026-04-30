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
    
    def export(self, filepath: Union[str, Path], 
               format: str = 'cube',
               **kwargs) -> None:
        """
        通用导出方法
        
        Args:
            filepath: 输出文件路径
            format: 输出格式 ('cube', '3dl', 'clf')
            **kwargs: 格式特定参数
        """
        format = format.lower()
        
        if format == 'cube':
            self.export_cube(filepath, **kwargs)
        elif format == '3dl':
            self.export_3dl(filepath, **kwargs)
        elif format == 'clf':
            self.export_clf(filepath, **kwargs)
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
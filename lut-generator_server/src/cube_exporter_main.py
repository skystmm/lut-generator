"""
CUBE 格式导出器 - CUBEExporter

导出 3D LUT 为标准的 .cube 文件格式
兼容 DaVinci Resolve、Premiere Pro、Final Cut Pro、Photoshop 等专业软件

.cube 文件格式规范：
- 标题行以 # 开头（注释）
- TITLE 标题
- LUT_3D_SIZE 网格大小
- 数据行：R G B（空格分隔，值范围 0-1）
"""

import numpy as np
from typing import Optional, Union, Dict, Any
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from lut3d_generator import LUT3DConfig, LUT3DMetadata


@dataclass
class CUBEExportConfig:
    """CUBE 导出配置"""
    # 是否包含元数据注释
    include_metadata: bool = True
    
    # 浮点数精度（小数位数）
    precision: int = 6
    
    # 是否使用制表符分隔（默认空格）
    use_tabs: bool = False
    
    # 每行注释的最大长度
    comment_max_length: int = 80
    
    # 自定义标题
    custom_title: Optional[str] = None
    
    # 自定义注释列表
    custom_comments: Optional[list] = None


class CUBEExporter:
    """
    CUBE 格式导出器
    
    将 3D LUT 导出为标准的 .cube 文件格式
    支持所有标准网格尺寸（17/33/65）
    """
    
    # CUBE 文件幻数（文件签名）
    MAGIC_HEADER = "# Created by LUT Generator"
    
    def __init__(self, config: CUBEExportConfig = None):
        """
        初始化 CUBE 导出器
        
        Args:
            config: 导出配置
        """
        self.config = config or CUBEExportConfig()
    
    def export(self, lut_data: np.ndarray,
               output_path: Union[str, Path],
               metadata: LUT3DMetadata = None,
               config: CUBEExportConfig = None) -> Path:
        """
        导出 LUT 为 .cube 文件
        
        Args:
            lut_data: 3D LUT 数组，shape=(N, N, N, 3)
            output_path: 输出文件路径
            metadata: LUT 元数据（可选）
            config: 导出配置（可选，覆盖实例配置）
            
        Returns:
            输出文件路径
        """
        cfg = config or self.config
        output_path = Path(output_path)
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 生成文件内容
        content = self._generate_cube_content(lut_data, metadata, cfg)
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return output_path
    
    def _generate_cube_content(self, lut_data: np.ndarray,
                                metadata: LUT3DMetadata,
                                config: CUBEExportConfig) -> str:
        """
        生成 CUBE 文件内容
        
        Args:
            lut_data: 3D LUT 数组
            metadata: LUT 元数据
            config: 导出配置
            
        Returns:
            CUBE 文件内容字符串
        """
        lines = []
        
        # 添加文件头注释
        if config.include_metadata:
            lines.append(f"# {self.MAGIC_HEADER}")
            lines.append(f"# Generated at: {datetime.now().isoformat()}")
        
        # 添加自定义注释
        if config.custom_comments:
            for comment in config.custom_comments:
                # 限制每行长度
                if len(comment) > config.comment_max_length:
                    # 简单换行处理
                    for i in range(0, len(comment), config.comment_max_length):
                        chunk = comment[i:i + config.comment_max_length]
                        lines.append(f"# {chunk}")
                else:
                    lines.append(f"# {comment}")
        
        # 添加元数据注释
        if config.include_metadata and metadata:
            if metadata.description:
                lines.append(f"# Description: {metadata.description}")
            
            if metadata.source_stats and metadata.target_stats:
                lines.append("#")
                lines.append("# Source Statistics:")
                lines.append(f"#   Mean (L,a,b): {metadata.source_stats.mean_array()}")
                lines.append(f"#   Std  (L,a,b): {metadata.source_stats.std_array()}")
                lines.append("#")
                lines.append("# Target Statistics:")
                lines.append(f"#   Mean (L,a,b): {metadata.target_stats.mean_array()}")
                lines.append(f"#   Std  (L,a,b): {metadata.target_stats.std_array()}")
            
            if metadata.transform_params:
                lines.append("#")
                lines.append("# Transform Parameters:")
                for key, value in metadata.transform_params.items():
                    if isinstance(value, float):
                        lines.append(f"#   {key}: {value:.6f}")
                    else:
                        lines.append(f"#   {key}: {value}")
        
        # 添加空行分隔
        lines.append("")
        
        # 添加标题
        title = config.custom_title or "LUT3D"
        lines.append(f"TITLE {title}")
        
        # 添加 LUT 尺寸
        grid_size = lut_data.shape[0]
        lines.append(f"LUT_3D_SIZE {grid_size}")
        
        # 添加数据
        # CUBE 格式要求：R G B 每行一个值，顺序遍历
        # 遍历顺序：B 最外层，G 中间，R 最内层
        separator = '\t' if config.use_tabs else ' '
        
        # 向量化生成数据行（高性能）
        # 重塑为 (N³, 3)
        lut_flat = lut_data.reshape(-1, 3)
        
        # 格式化为字符串
        format_str = f"%.{config.precision}f"
        
        # 批量格式化（比逐行循环快）
        data_lines = []
        for row in lut_flat:
            formatted = separator.join([format_str % val for val in row])
            data_lines.append(formatted)
        
        lines.extend(data_lines)
        
        # 合并为完整内容
        return '\n'.join(lines)
    
    def export_to_string(self, lut_data: np.ndarray,
                         metadata: LUT3DMetadata = None,
                         config: CUBEExportConfig = None) -> str:
        """
        导出 LUT 为 CUBE 格式字符串
        
        Args:
            lut_data: 3D LUT 数组
            metadata: LUT 元数据
            config: 导出配置
            
        Returns:
            CUBE 格式字符串
        """
        cfg = config or self.config
        return self._generate_cube_content(lut_data, metadata, cfg)
    
    def validate_cube_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        验证 CUBE 文件格式
        
        Args:
            file_path: CUBE 文件路径
            
        Returns:
            验证结果字典：
            - valid: bool，是否有效
            - grid_size: int，网格大小（如果有效）
            - line_count: int，数据行数
            - errors: list，错误列表
        """
        file_path = Path(file_path)
        result = {
            'valid': False,
            'grid_size': None,
            'line_count': 0,
            'errors': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            result['errors'].append(f"Failed to read file: {e}")
            return result
        
        # 查找 LUT_3D_SIZE
        grid_size = None
        data_start = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue
            
            # 查找 LUT_3D_SIZE
            if line.startswith('LUT_3D_SIZE'):
                try:
                    grid_size = int(line.split()[1])
                    data_start = i + 1
                    break
                except (IndexError, ValueError) as e:
                    result['errors'].append(f"Invalid LUT_3D_SIZE: {line}")
                    return result
        
        if grid_size is None:
            result['errors'].append("Missing LUT_3D_SIZE directive")
            return result
        
        # 验证网格大小
        valid_sizes = [17, 33, 65]
        if grid_size not in valid_sizes:
            result['errors'].append(f"Invalid grid size {grid_size}. Must be one of {valid_sizes}")
            return result
        
        # 计算期望的数据行数
        expected_lines = grid_size ** 3
        
        # 统计实际数据行数
        data_lines = 0
        for line in lines[data_start:]:
            line = line.strip()
            if line and not line.startswith('#'):
                data_lines += 1
        
        result['grid_size'] = grid_size
        result['line_count'] = data_lines
        
        # 验证数据行数
        if data_lines != expected_lines:
            result['errors'].append(
                f"Expected {expected_lines} data lines, got {data_lines}"
            )
            return result
        
        # 验证数据格式（抽样检查）
        sample_size = min(10, data_lines)
        for i, line in enumerate(lines[data_start:data_start + sample_size]):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) != 3:
                result['errors'].append(f"Line {data_start + i + 1}: Expected 3 values, got {len(parts)}")
                return result
            
            try:
                values = [float(p) for p in parts]
                if not all(0 <= v <= 1 for v in values):
                    result['errors'].append(
                        f"Line {data_start + i + 1}: Values must be in range [0, 1]"
                    )
                    return result
            except ValueError as e:
                result['errors'].append(f"Line {data_start + i + 1}: Invalid float value: {e}")
                return result
        
        result['valid'] = True
        return result
    
    def load_cube_file(self, file_path: Union[str, Path]) -> np.ndarray:
        """
        加载 CUBE 文件为 LUT 数组
        
        Args:
            file_path: CUBE 文件路径
            
        Returns:
            3D LUT 数组，shape=(N, N, N, 3)
        """
        file_path = Path(file_path)
        
        # 先验证
        validation = self.validate_cube_file(file_path)
        if not validation['valid']:
            raise ValueError(f"Invalid CUBE file: {validation['errors']}")
        
        grid_size = validation['grid_size']
        
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 找到数据起始位置
        data_start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('LUT_3D_SIZE'):
                data_start = i + 1
                break
        
        # 解析数据
        data_values = []
        for line in lines[data_start:]:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = [float(p) for p in line.split()]
                data_values.append(parts)
        
        # 转换为 numpy 数组
        lut_data = np.array(data_values, dtype=np.float32)
        
        # 重塑为 3D 网格
        lut_data = lut_data.reshape(grid_size, grid_size, grid_size, 3)
        
        return lut_data


def export_to_cube(lut_data: np.ndarray,
                   output_path: Union[str, Path],
                   metadata: LUT3DMetadata = None,
                   precision: int = 6,
                   include_metadata: bool = True) -> Path:
    """
    便捷函数：导出 LUT 为 .cube 文件
    
    Args:
        lut_data: 3D LUT 数组
        output_path: 输出文件路径
        metadata: LUT 元数据
        precision: 浮点数精度
        include_metadata: 是否包含元数据注释
        
    Returns:
        输出文件路径
    """
    config = CUBEExportConfig(
        precision=precision,
        include_metadata=include_metadata
    )
    exporter = CUBEExporter(config)
    return exporter.export(lut_data, output_path, metadata)


if __name__ == "__main__":
    # 简单测试
    import sys
    
    print("CUBE Exporter Test")
    print("=" * 50)
    
    # 创建测试 LUT 数据
    grid_size = 17
    lut_data = np.random.rand(grid_size, grid_size, grid_size, 3).astype(np.float32)
    
    # 创建元数据
    metadata = LUT3DMetadata(
        created_at=datetime.now().isoformat(),
        description="Test LUT for CUBE export",
        config=LUT3DConfig(grid_size=grid_size)
    )
    
    # 导出到文件
    output_path = Path("/tmp/test_lut.cube")
    exported_path = export_to_cube(
        lut_data,
        output_path,
        metadata,
        precision=6
    )
    
    print(f"Exported to: {exported_path}")
    print(f"File size: {exported_path.stat().st_size} bytes")
    
    # 验证文件
    exporter = CUBEExporter()
    validation = exporter.validate_cube_file(exported_path)
    
    print(f"\nValidation result:")
    print(f"  Valid: {validation['valid']}")
    print(f"  Grid size: {validation['grid_size']}")
    print(f"  Line count: {validation['line_count']}")
    if validation['errors']:
        print(f"  Errors: {validation['errors']}")
    
    # 重新加载
    loaded_lut = exporter.load_cube_file(exported_path)
    print(f"\nLoaded LUT shape: {loaded_lut.shape}")
    print(f"Data match: {np.allclose(lut_data, loaded_lut)}")
    
    # 显示文件前几行
    print(f"\nFile preview (first 20 lines):")
    with open(exported_path, 'r') as f:
        for i, line in enumerate(f):
            if i >= 20:
                break
            print(f"  {line.rstrip()}")

"""
LUT 导出模块 - LUTExporter

支持多种 LUT 格式导出：
- CUBE (Adobe)
- 3DL (Autodesk Lustre)
- clf (ACES)
"""

import base64
import json
import zlib
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

    def export_lrtemplate_preset(self,
                                 filepath: Union[str, Path],
                                 title: str = None,
                                 group: str = 'lut-generator:UserPresets',
                                 preset_type: str = 'Normal',
                                 apply_amount: float = 1.0,
                                 process_version: str = '15.4',
                                 supports_amount: bool = True) -> None:
        """
        导出为 Adobe Lightroom Classic `.lrtemplate` 预设(JSON6 风格),
        可被 LrC 12/13/14 通过 `Presets panel → + → Import Preset` 加载。

        核心优势: 能把 **完整 3D LUT**(R×G×B×3) 塞进 LrC 内部,
        跳过 XMP `crs:ColorTable` 的 1D 压缩问题(后者把 3D 信息丢光,
        应用到照片几乎无变化)。

        字段说明(基于 LrC 12-14 导出的实际 preset 字段集):
        - `type=Develop` + `version=1`: 必备 schema 头
        - `s.Name` / `s.Group` / `s.PresetType`: 元数据
        - `s.ProcessVersion="15.4"`: LrC 14 推荐(CC 2020+)
        - `s.SupportsAmount` / `s.Amount`: 0-1 强度
        - `s.ToneCurveName2012="Linear"`: 占位,避免 LrC 强制要求曲线
        - `s.LUT3D` / `s.LUT3DSize`: **核心** — 完整 3D LUT
        - `s.LUT3DIntent=0` / `s.LUT3DMixing`: 渲染相关

        `LUT3D` 字符串编码: N³ 个 RGB 三元组,每分量 16-bit (0-65535)
        整数,空格分隔,顺序按 BGR(蓝变化最快,跟 `.cube` 文件一致)。

        Args:
            filepath: 输出 .lrtemplate 路径(无后缀自动补)
            title: 预设名称
            group: LrC 预设分组
            preset_type: `Normal` / `Auto` / `Video`
            apply_amount: 0.0-1.0,应用强度
            process_version: `s.ProcessVersion`,LrC 14 用 15.4
            supports_amount: 是否带 Amount 滑块
        """
        filepath = Path(filepath)
        if filepath.suffix == '':
            filepath = filepath.with_suffix('.lrtemplate')

        title = title or self.metadata.get('title', 'LUT Preset')
        # group 优先用 metadata 里的(允许调用方覆盖默认值)
        group = self.metadata.get('group', group)

        # 1) 量化 3D LUT 到 16-bit 整数
        lut_clipped = np.clip(self.lut_data, 0.0, 1.0)
        lut_int = np.round(lut_clipped * 65535).astype(np.uint32)

        # 2) 展平成 BGR 顺序的 1D 字符串("r0 g0 b0 r1 g1 b1 ...")
        #    BGR 顺序: 最外层 B 变化最快(跟 .cube 文件一致,
        #    LrC 内部存储习惯)
        #    原 lut_data 形状 (N, N, N, 3),索引 [r, g, b, k](k=通道)
        #    要展平成 BGR 顺序,需要把 [b, g, r, k] 这个轴顺序
        #    → 用 transpose(2, 1, 0, 3) 把 b 放到最外层
        N = self.grid_size
        lut_bgr = lut_int.transpose(2, 1, 0, 3)  # (N, N, N, 3) → 轴序 [b, g, r, k]
        # 现在 C-order reshape: 按 [b, g, r, channel] 展平 = BGR 顺序 ✓
        flat = lut_bgr.reshape(N * N * N, 3)
        lut_str = ' '.join(
            f"{flat[i, 0]:d} {flat[i, 1]:d} {flat[i, 2]:d}"
            for i in range(N * N * N)
        )

        # 3) 拼 JSON6 兼容的 dict
        preset = {
            'type': 'Develop',
            'version': 1,
            's': {
                'Name': title,
                'Group': group,
                'PresetType': preset_type,
                'ProcessVersion': process_version,
                'SupportsAmount': 1 if supports_amount else 0,
                'Amount': float(apply_amount),
                'ToneCurveName2012': 'Linear',
                'LUT3DSize': N,
                'LUT3D': lut_str,
                'LUT3DIntent': 0,
                'LUT3DMixing': 0.5,
            }
        }

        # 4) 写文件(JSON 严格模式,LrC 也吃;JSON6 是其超集,标准 JSON 是其子集)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(preset, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise IOError(f"Failed to write LRTEMPLATE preset to {filepath}: {e}") from e
        except OSError as e:
            raise OSError(f"OS error while writing LRTEMPLATE preset to {filepath}: {e}") from e

    def export_xmp_creative_profile(self,
                                    filepath: Union[str, Path],
                                    title: str = None,
                                    group: str = 'lut-generator:UserPresets',
                                    apply_amount: float = 1.0,
                                    process_version: str = '15.4') -> None:
        """
        导出为 Adobe Lightroom Classic / ACR **Creative Profile** (.xmp),
        这是 LrC 14 官方 3D LUT 路线(2018+ 取代 .lrtemplate)。

        优势 vs .lrtemplate:
        - .lrtemplate 是 LrC 7.3 之前的 legacy 格式, LrC 14 自动隐藏
        - .xmp Creative Profile 是 LrC 14 官方 Profile Browser 加载路径
        - 完整 3D LUT 通过 `crs:RGBTable` 字段内嵌,不丢维度

        LUT 编码方式(基于 exiftool 论坛真实 .xmp 反推 + DNG spec 1.4):
        1. 3D LUT 量化到 16-bit big-endian (0-65535)
        2. 按 BGR 顺序展平(B 最外层,跟 .cube 一致)
        3. **zlib 压缩**(level 9,最大压缩)
        4. **Adobe Ascii85 编码**(PostScript Level 2)
        5. 包裹成 `crs:Table_<md5>="<encoded>"` 字段
        6. `crs:RGBTable="<md5>"` 引用

        ⚠️ [EXPERIMENTAL] Adobe 的 asymmetric85 编码细节没公开,本实现
           走标准 Ascii85 + zlib 路线。LrC 14 的 XMP parser 通常宽容
           接受任何合法 Ascii85 编码;若不工作可微调编码方案。

        Args:
            filepath: 输出 .xmp 路径(无后缀自动补)
            title: 预设名称
            group: 在 LrC Profile Browser 中的分组
            apply_amount: 0.0-1.0, 3D LUT 应用强度(写入 `crs:RGBTableAmount`)
            process_version: `crs:ProcessVersion`,LrC 14 用 15.4

        安装路径(让 LrC 发现):
        - Mac: `/Library/Application Support/Adobe/CameraRaw/Settings/`
        - Win: `C:\\ProgramData\\Adobe\\CameraRaw\\Settings\\`(需要管理员)
        """
        import hashlib
        filepath = Path(filepath)
        if filepath.suffix == '':
            filepath = filepath.with_suffix('.xmp')

        title = title or self.metadata.get('title', 'LUT Preset')
        group = self.metadata.get('group', group)
        title = self._xml_escape(title)
        group = self._xml_escape(group)

        # 1) 量化 3D LUT 到 16-bit big-endian
        lut_clipped = np.clip(self.lut_data, 0.0, 1.0)
        lut_int = np.round(lut_clipped * 65535).astype('>u2')  # big-endian uint16

        # 2) 按 BGR 顺序展平(B 最外层,跟 .cube / LrC 约定一致)
        N = self.grid_size
        lut_bgr = lut_int.transpose(2, 1, 0, 3)  # axis 顺序 [b, g, r, channel]
        flat = lut_bgr.reshape(N * N * N, 3)
        data_bytes = flat.tobytes()

        # 3) zlib 压缩(level 9,最大压缩)
        compressed = zlib.compress(data_bytes, 9)

        # 4) Adobe Ascii85 编码(用 <~ ~> wrapper 标准化,base64.a85decode 必须这样)
        encoded_bytes = base64.a85encode(compressed, adobe=True)
        encoded_str = encoded_bytes.decode('ascii')
        # 5) XML-escape: Ascii85 输出含 < > & ' " 等 XML 特殊字符,
        #    必须在写入 XML 字段前 escape
        encoded_str_escaped = self._xml_escape(encoded_str)

        # 6) 算 MD5 hash 作为表名引用(用未 escape 的字符串算,跟 LrC 实际数据格式一致)
        md5_hash = hashlib.md5(encoded_str.encode('ascii')).hexdigest().upper()
        table_field = f'crs:Table_{md5_hash}'

        # 6) 拼 XMP(参照 exiftool 论坛 Boyd 帖真实 .xmp)
        xmp = f'''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="lut-generator 1.0">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
    crs:PresetType="Look"
    crs:Cluster="{group}"
    crs:UUID="{md5_hash}"
    crs:SupportsAmount="True"
    crs:SupportsColor="True"
    crs:SupportsMonochrome="False"
    crs:SupportsHighDynamicRange="True"
    crs:SupportsNormalDynamicRange="True"
    crs:SupportsSceneReferred="True"
    crs:SupportsOutputReferred="True"
    crs:Version="15.4"
    crs:ProcessVersion="{process_version}"
    crs:ConvertToGrayscale="False"
    crs:RGBTable="{md5_hash}"
    {table_field}="{encoded_str_escaped}"
    crs:RGBTableAmount="{apply_amount:.4f}"
    crs:HasSettings="True">
   <crs:Name>
    <rdf:Alt><rdf:li xml:lang="x-default">{title}</rdf:li></rdf:Alt>
   </crs:Name>
   <crs:Group>
    <rdf:Alt><rdf:li xml:lang="x-default">{group}</rdf:li></rdf:Alt>
   </crs:Group>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
'''

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(xmp)
        except IOError as e:
            raise IOError(f"Failed to write XMP Creative Profile to {filepath}: {e}") from e
        except OSError as e:
            raise OSError(f"OS error while writing XMP Creative Profile to {filepath}: {e}") from e

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
            format: 输出格式 ('cube', '3dl', 'clf', 'xmp', 'lrtemplate', 'xmpcreative')
            **kwargs: 格式特定参数
                - xmp: title / group / preset_type / apply_amount / process_version
                - lrtemplate: 同 xmp
                - xmpcreative: title / group / apply_amount / process_version
                  (LrC 14 官方 3D LUT Creative Profile 路线)
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
        elif format == 'lrtemplate':
            self.export_lrtemplate_preset(filepath, **kwargs)
        elif format == 'xmpcreative':
            self.export_xmp_creative_profile(filepath, **kwargs)
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
# LUT Generator - 技术设计文档

**文档版本**: v1.0  
**创建日期**: 2026-04-13  
**项目 ID**: 【图片分析风格生成 LUT 工具_标准版_20260413153500】

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户接口层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   CLI       │  │    API      │  │   GUI(未来) │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    业务逻辑层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ 图像分析器  │  │  LUT 生成器  │  │  预览引擎   │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    核心算法层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │色彩空间转换 │  │Reinhard 算法 │  │  插值计算   │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    数据层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │  图片文件   │  │  LUT 文件    │  │  配置文件   │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

### 1.2 模块依赖关系

```
lut_generator/
├── core/              # 核心算法
│   ├── color_space.py    # 色彩空间转换
│   ├── reinhard.py       # Reinhard 色彩迁移
│   └── interpolation.py  # 插值计算
├── analysis/          # 图像分析
│   ├── feature_extractor.py  # 特征提取
│   └── batch_processor.py    # 批量处理
├── lut/               # LUT 生成
│   ├── generator.py        # LUT 生成器
│   ├── exporter.py         # 文件导出
│   └── importer.py         # 文件导入
├── preview/           # 预览功能
│   ├── renderer.py         # 渲染引擎
│   └── comparator.py       # 对比查看
├── utils/             # 工具函数
│   ├── io.py               # 文件 IO
│   ├── config.py           # 配置管理
│   └── validators.py       # 参数验证
└── cli/               # 命令行接口
    └── main.py             # 入口程序
```

---

## 2. 核心模块设计

### 2.1 色彩空间转换模块 (color_space.py)

**职责**: 负责 RGB ↔ Lab 色彩空间转换

**关键类**:
```python
class ColorSpaceConverter:
    """色彩空间转换器"""
    
    def __init__(self, illuminant: str = "D65", observer: str = "2"):
        self.illuminant = illuminant
        self.observer = observer
    
    def rgb_to_lab(self, rgb: np.ndarray) -> np.ndarray:
        """RGB 转 Lab (sRGB → XYZ → Lab)"""
        pass
    
    def lab_to_rgb(self, lab: np.ndarray) -> np.ndarray:
        """Lab 转 RGB (Lab → XYZ → sRGB)"""
        pass
```

**技术要点**:
- 使用 colour-science 库进行精确转换
- 处理色域外颜色（裁剪或压缩）
- 支持批量转换（numpy 向量化）

### 2.2 Reinhard 算法模块 (reinhard.py)

**职责**: 实现 Reinhard 色彩迁移算法

**关键类**:
```python
class ReinhardColorTransfer:
    """Reinhard 色彩迁移"""
    
    def __init__(self, strength: float = 1.0):
        self.strength = strength  # 迁移强度 0.0-1.0
    
    def compute_statistics(self, lab_image: np.ndarray) -> dict:
        """计算 Lab 空间统计特征"""
        return {
            'mean': np.mean(lab_image, axis=(0, 1)),      # [L, a, b]
            'std': np.std(lab_image, axis=(0, 1))         # [L, a, b]
        }
    
    def transfer(self, source_stats: dict, target_stats: dict) -> np.ndarray:
        """
        执行色彩迁移
        
        公式:
        L_new = (L - mean_L_source) * (std_L_target / std_L_source) + mean_L_target
        a_new = (a - mean_a_source) * (std_a_target / std_a_source) + mean_a_target
        b_new = (b - mean_b_source) * (std_b_target / std_b_source) + mean_b_target
        """
        pass
    
    def build_transformation_matrix(self, source_stats: dict, 
                                     target_stats: dict) -> np.ndarray:
        """构建色彩变换矩阵（用于 LUT 生成）"""
        pass
```

**算法流程**:
1. 将源图片（参考图）转换到 Lab 空间
2. 计算源图片的 L, a, b 均值和标准差
3. 将目标图片（待处理图）转换到 Lab 空间
4. 计算目标图片的 L, a, b 均值和标准差
5. 应用 Reinhard 变换公式
6. 转换回 RGB 空间

### 2.3 LUT 生成器模块 (generator.py)

**职责**: 生成 3D LUT

**关键类**:
```python
class LUT3DGenerator:
    """3D LUT 生成器"""
    
    def __init__(self, lut_size: int = 33):
        """
        初始化
        
        Args:
            lut_size: LUT 维度 (17, 33, 或 65)
        """
        if lut_size not in [17, 33, 65]:
            raise ValueError("lut_size must be 17, 33, or 65")
        self.lut_size = lut_size
    
    def generate(self, transform_func: Callable) -> np.ndarray:
        """
        生成 3D LUT
        
        Args:
            transform_func: 色彩变换函数，输入 RGB(0-1)，输出 RGB(0-1)
        
        Returns:
            3D LUT 数组，shape: (lut_size, lut_size, lut_size, 3)
        """
        lut = np.zeros((self.lut_size, self.lut_size, self.lut_size, 3))
        
        for r in range(self.lut_size):
            for g in range(self.lut_size):
                for b in range(self.lut_size):
                    # 归一化到 0-1
                    rgb_in = np.array([
                        r / (self.lut_size - 1),
                        g / (self.lut_size - 1),
                        b / (self.lut_size - 1)
                    ])
                    # 应用变换
                    rgb_out = transform_func(rgb_in)
                    lut[r, g, b] = rgb_out
        
        return lut
```

**优化策略**:
- 使用 numpy 向量化替代三重循环
- 支持并行计算（multiprocessing）
- 缓存中间结果

### 2.4 LUT 导出模块 (exporter.py)

**职责**: 导出 .cube 格式文件

**关键类**:
```python
class CUBEExporter:
    """.cube 格式导出器"""
    
    def __init__(self, lut_size: int = 33):
        self.lut_size = lut_size
    
    def export(self, lut: np.ndarray, filepath: str, 
               title: str = "LUT_Generator") -> None:
        """
        导出 LUT 到 .cube 文件
        
        .cube 格式:
        TITLE "name"
        LUT_3D_SIZE 33
        R G B (每行一个颜色点，值范围 0-1)
        """
        with open(filepath, 'w') as f:
            f.write(f'TITLE "{title}"\n')
            f.write(f'LUT_3D_SIZE {self.lut_size}\n')
            
            # 遍历顺序：B 最快，G 次之，R 最慢
            for b in range(self.lut_size):
                for g in range(self.lut_size):
                    for r in range(self.lut_size):
                        rgb = lut[r, g, b]
                        f.write(f'{rgb[0]:.6f} {rgb[1]:.6f} {rgb[2]:.6f}\n')
```

---

## 3. 数据结构设计

### 3.1 核心数据结构

```python
@dataclass
class ColorStatistics:
    """色彩统计信息"""
    mean_L: float
    mean_a: float
    mean_b: float
    std_L: float
    std_a: float
    std_b: float
    
    def to_array(self) -> np.ndarray:
        """转换为 numpy 数组"""
        return np.array([
            [self.mean_L, self.mean_a, self.mean_b],
            [self.std_L, self.std_a, self.std_b]
        ])

@dataclass
class LUTMetadata:
    """LUT 元数据"""
    title: str
    lut_size: int
    created_at: str
    source_images: List[str]
    algorithm: str = "Reinhard"
    strength: float = 1.0
    
    def to_json(self) -> str:
        """导出为 JSON"""
        return json.dumps(asdict(self), indent=2)

@dataclass
class AnalysisResult:
    """分析结果"""
    lut: np.ndarray
    metadata: LUTMetadata
    statistics: ColorStatistics
    preview_image: Optional[np.ndarray] = None
```

### 3.2 配置数据结构

```python
@dataclass
class GeneratorConfig:
    """生成器配置"""
    lut_size: int = 33
    strength: float = 1.0
    output_format: str = "cube"
    output_path: str = "./output"
    preview_enabled: bool = False
    batch_mode: bool = False
    
    @classmethod
    def from_yaml(cls, filepath: str) -> 'GeneratorConfig':
        """从 YAML 文件加载配置"""
        pass
    
    def to_yaml(self, filepath: str) -> None:
        """保存配置到 YAML 文件"""
        pass
```

---

## 4. 接口设计

### 4.1 公共 API

```python
# 主入口模块
from lut_generator import LUTGenerator, analyze_image, analyze_images

# 核心类
class LUTGenerator:
    """LUT 生成器主类"""
    
    def __init__(self, config: GeneratorConfig = None):
        pass
    
    def analyze_image(self, image_path: str) -> AnalysisResult:
        """分析单张图片"""
        pass
    
    def analyze_images(self, image_paths: List[str]) -> AnalysisResult:
        """分析多张图片（平均）"""
        pass
    
    def apply_lut(self, image_path: str, lut: np.ndarray, 
                  output_path: str) -> None:
        """应用 LUT 到图片"""
        pass
    
    def export_lut(self, lut: np.ndarray, filepath: str, 
                   metadata: LUTMetadata = None) -> None:
        """导出 LUT 文件"""
        pass
```

### 4.2 命令行接口

```bash
# 命令结构
lut-generator <command> [options]

# 命令列表
analyze          # 分析图片生成 LUT
apply            # 应用 LUT 到图片
preview          # 预览 LUT 效果
info             # 查看 LUT 信息
convert          # 转换 LUT 格式
```

```python
# CLI 参数定义
@click.group()
def cli():
    pass

@cli.command()
@click.option('--input', '-i', required=True, help='输入图片路径')
@click.option('--output', '-o', required=True, help='输出 LUT 路径')
@click.option('--size', '-s', default=33, type=click.Choice(['17', '33', '65']))
@click.option('--strength', default=1.0, type=click.FloatRange(0, 1))
@click.option('--batch', is_flag=True, help='批量模式（目录输入）')
@click.option('--preview', is_flag=True, help='生成预览图')
def analyze(input, output, size, strength, batch, preview):
    """分析图片生成 LUT"""
    pass
```

---

## 5. 测试策略

### 5.1 单元测试

```python
# tests/test_color_space.py
def test_rgb_to_lab_conversion():
    """测试 RGB 到 Lab 转换"""
    converter = ColorSpaceConverter()
    rgb = np.array([[[1.0, 0.0, 0.0]]])  # 纯红
    lab = converter.rgb_to_lab(rgb)
    assert lab.shape == (1, 1, 3)
    
# tests/test_reinhard.py
def test_reinhard_statistics():
    """测试 Reinhard 统计计算"""
    transfer = ReinhardColorTransfer()
    lab_image = np.random.rand(100, 100, 3) * 100
    stats = transfer.compute_statistics(lab_image)
    assert 'mean' in stats
    assert 'std' in stats
    
# tests/test_lut_generator.py
def test_lut_generation():
    """测试 LUT 生成"""
    generator = LUT3DGenerator(lut_size=17)
    identity_func = lambda x: x
    lut = generator.generate(identity_func)
    assert lut.shape == (17, 17, 17, 3)
    assert 0 <= lut.min() <= 1
    assert 0 <= lut.max() <= 1
```

### 5.2 集成测试

```python
# tests/test_integration.py
def test_full_pipeline():
    """测试完整流程"""
    generator = LUTGenerator(lut_size=33)
    result = generator.analyze_image("test_data/reference.jpg")
    generator.export_lut(result.lut, "test_output.cube")
    assert os.path.exists("test_output.cube")
```

### 5.3 性能测试

```python
# tests/test_performance.py
def test_analysis_performance():
    """测试分析性能"""
    import time
    generator = LUTGenerator()
    start = time.time()
    generator.analyze_image("test_data/1080p.jpg")
    elapsed = time.time() - start
    assert elapsed < 5.0  # 要求 < 5 秒
```

---

## 6. 依赖管理

### 6.1 Python 依赖 (pyproject.toml)

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "lut-generator"
version = "0.1.0"
description = "Image analysis based 3D LUT generator"
requires-python = ">=3.11"
dependencies = [
    "colour-science>=0.4.0",
    "opencv-python>=4.8.0",
    "numpy>=1.24.0",
    "scipy>=1.10.0",
    "click>=8.1.0",
    "pyyaml>=6.0",
    "pillow>=10.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
]

[project.scripts]
lut-generator = "lut_generator.cli.main:cli"
```

### 6.2 开发环境

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v --cov=lut_generator

# 代码检查
ruff check src/
mypy src/
```

---

## 7. 文件组织

```
projects/lut-generator/
├── lut-generator_prd.md           # PRD 文档
├── lut-generator_tech-design.md   # 技术设计文档
├── lut-generator_server/          # Python 后端
│   ├── pyproject.toml             # 项目配置
│   ├── README.md                  # 使用说明
│   ├── src/
│   │   └── lut_generator/
│   │       ├── __init__.py
│   │       ├── core/
│   │       │   ├── __init__.py
│   │       │   ├── color_space.py
│   │       │   ├── reinhard.py
│   │       │   └── interpolation.py
│   │       ├── analysis/
│   │       │   ├── __init__.py
│   │       │   ├── feature_extractor.py
│   │       │   └── batch_processor.py
│   │       ├── lut/
│   │       │   ├── __init__.py
│   │       │   ├── generator.py
│   │       │   ├── exporter.py
│   │       │   └── importer.py
│   │       ├── preview/
│   │       │   ├── __init__.py
│   │       │   ├── renderer.py
│   │       │   └── comparator.py
│   │       ├── utils/
│   │       │   ├── __init__.py
│   │       │   ├── io.py
│   │       │   ├── config.py
│   │       │   └── validators.py
│   │       └── cli/
│   │           ├── __init__.py
│   │           └── main.py
│   └── tests/
│       ├── __init__.py
│       ├── test_color_space.py
│       ├── test_reinhard.py
│       ├── test_lut_generator.py
│       └── test_integration.py
└── lut-generator_skill/           # OpenClaw Skill
    └── SKILL.md
```

---

## 8. 开发计划细化

### 第 1 周：核心算法
- [ ] 搭建项目骨架
- [ ] 实现 ColorSpaceConverter
- [ ] 实现 ReinhardColorTransfer
- [ ] 编写单元测试
- [ ] 算法验证（与论文结果对比）

### 第 2 周：LUT 生成
- [ ] 实现 LUT3DGenerator
- [ ] 实现 CUBEExporter
- [ ] 支持三种精度（17/33/65）
- [ ] 性能优化（向量化）
- [ ] 单元测试

### 第 3 周：批量处理
- [ ] 实现 BatchProcessor
- [ ] 多图平均算法
- [ ] 进度条显示
- [ ] 错误处理
- [ ] 集成测试

### 第 4 周：预览功能
- [ ] 实现 PreviewRenderer
- [ ] 实现 Comparator
- [ ] CLI 预览参数
- [ ] 预览图生成
- [ ] 用户测试

### 第 5 周：优化测试
- [ ] 性能 profiling
- [ ] 内存优化
- [ ] 完整测试套件
- [ ] 文档完善
- [ ] 代码审查

---

## 9. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| Reinhard 算法效果不佳 | 高 | 中 | 预留其他算法接口（如 Lattice） |
| 65³ LUT 生成过慢 | 中 | 高 | 并行计算 + 进度显示 |
| 色域外颜色处理 | 中 | 中 | 提供多种处理策略（裁剪/压缩） |
| 色彩空间转换误差 | 高 | 低 | 使用 colour-science 权威库 |

---

**文档结束**

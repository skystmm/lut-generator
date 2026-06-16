"""
VGG-11 Perceptual Feature Extractor - Path B 专用

职责:
1. 加载 VGG-11 (ImageNet 预训练, 用 features.* 序列)
2. 暴露 5 个浅层 feature map (relu1_1, relu2_1, relu3_1, relu4_1, relu5_1)
3. 支持 (a) 直接 feature map 抽取 (b) Gram 矩阵用于风格 loss

设计原则:
- 单职责: 加载 + 前向 + Gram 矩阵。不做 loss 计算 (留给调用方)
- 冻结参数: 仅做特征抽取
- ImageNet 标准化: 内置 mean/std, 调用方无需预处理
- 设备透明: 自动选 cuda (有) / cpu
- 错误友好: weights 路径错误时给出明确提示

约定:
- 输入: torch.Tensor [B, 3, H, W], 范围 [0, 1] (RGB)
- 输出: dict[str, Tensor] (key = 层名, value = feature map)
- Gram: torch.Tensor [B, C, C] (C = 该层通道数)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import torch
import torch.nn as nn
from torchvision import models
from torchvision.models import VGG11_Weights


# ImageNet normalization — VGG 训练时的标准预处理
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

# VGG-11 features 切分点 — 经 torchvision 0.27 VGG11_Weights.IMAGENET1K_V1 实证
#   relu1_1 = features[1]   (block1, 64ch)
#   relu2_1 = features[4]   (block2, 128ch, 经过 maxpool)
#   relu3_1 = features[8]   (block3, 256ch)
#   relu4_1 = features[11]  (block4, 512ch)
#   relu5_1 = features[14]  (block5, 512ch)
DEFAULT_FEATURE_LAYERS: Dict[str, int] = {
    "relu1_1": 1,
    "relu2_1": 4,
    "relu3_1": 8,
    "relu4_1": 11,
    "relu5_1": 14,
}


class VGGPerceptualExtractor(nn.Module):
    """
    VGG-11 感知特征提取器。

    用法:
        >>> ext = VGGPerceptualExtractor()                    # 默认下载 weights
        >>> x = torch.rand(1, 3, 224, 224)
        >>> feats = ext(x)                                     # dict[str, Tensor]
        >>> grams = ext.gram_dict(feats)                       # dict[str, Tensor]
    """

    def __init__(
        self,
        weights_path: Optional[str] = None,
        layers: Optional[Dict[str, int]] = None,
        device: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.layers = dict(layers or DEFAULT_FEATURE_LAYERS)

        # Phase 1.4: 不再触发 torchvision 自动下载(沙盒封 huggingface)
        # 改为空初始化,然后 load_local_weights() 加载本地 .pth
        vgg = models.vgg11(weights=None)
        self.features = vgg.features
        # 默认行为: 若未提供 weights_path, 尝试默认位置
        if weights_path is None:
            for cand in [
                Path("D:/workspace/lut-generator/models/vgg11-bbd30ac9.pth"),
                Path("D:/workspace/models/vgg11-bbd30ac9.pth"),
                Path("models/vgg11-bbd30ac9.pth"),
            ]:
                if cand.exists():
                    weights_path = str(cand)
                    break
        if weights_path is not None and Path(weights_path).exists():
            self.load_local_weights(weights_path)
        else:
            raise FileNotFoundError(
                f"VGG-11 weights not found in any default location. "
                f"Download: curl -L -o models/vgg11-bbd30ac9.pth "
                f"'https://download.pytorch.org/models/vgg11-bbd30ac9.pth'"
            )

        # 冻结 — 仅作特征抽取
        for p in self.features.parameters():
            p.requires_grad = False
        self.features.eval()

        # 设备
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.to(self.device)

        # ImageNet 标准化 buffer (跟随 .to(device) 移动)
        mean = torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1)
        std = torch.tensor(IMAGENET_STD).view(1, 3, 1, 1)
        self.register_buffer("mean", mean)
        self.register_buffer("std", std)

    def _normalize(self, x: torch.Tensor) -> torch.Tensor:
        """[0,1] RGB -> ImageNet 标准化"""
        return (x - self.mean) / self.std

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        抽取指定层的 feature maps(可微)。

        Args:
            x: [B, 3, H, W], 范围 [0, 1], RGB

        Returns:
            dict: {layer_name: feature_map [B, C_i, H_i, W_i]}

        Note:
            Phase 1.4: 移除 @torch.no_grad() 装饰,支持 perceptual loss 反向传播。
            Gram matrix 也是 (C, C),对 batch 维度需要 batch bmm。
        """
        if x.dim() != 4 or x.shape[1] != 3:
            raise ValueError(f"期望 [B,3,H,W], 收到 {tuple(x.shape)}")
        # Phase 1.4: 放宽范围检查 — perceptual loss 中 rendered 可能短时间溢出 [0,1]

        x = x.to(self.device)
        x = self._normalize(x)

        # 累计执行, 按需截取 (每个目标层只存一次)
        target_indices = set(self.layers.values())
        out: Dict[str, torch.Tensor] = {}
        for i, layer in enumerate(self.features):
            x = layer(x)
            if i in target_indices:
                for name, idx in self.layers.items():
                    if idx == i and name not in out:
                        out[name] = x
                        break
        return out

    @staticmethod
    def gram(features: torch.Tensor) -> torch.Tensor:
        """
        计算 Gram 矩阵 — 风格 loss 标准做法 (Gatys 2015)。

        Args:
            features: [B, C, H, W]

        Returns:
            [B, C, C] Gram 矩阵
        """
        B, C, H, W = features.shape
        f = features.view(B, C, H * W)
        return torch.bmm(f, f.transpose(1, 2)) / (C * H * W)

    def gram_dict(self, feats: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        """对每个 feature map 计算 Gram"""
        return {name: self.gram(fm) for name, fm in feats.items()}

    def load_local_weights(self, weights_path: str) -> "VGGPerceptualExtractor":
        """
        加载本地 .pth weights (用于没网或指定特定 snapshot)。

        注意: torchvision VGG11_Weights.IMAGENET1K_V1 的 state_dict
              key 形如 'features.0.weight' — 但 self.features 是 Sequential
              (key 是 '0.weight' 而非 'features.0.weight')。
              Phase 1.4: 自动 strip 'features.' 前缀以正确加载。
        """
        path = Path(weights_path)
        if not path.exists():
            raise FileNotFoundError(f"weights 不存在: {path}")
        state = torch.load(str(path), map_location="cpu")
        # Strip 'features.' prefix to match Sequential keys
        fixed_state = {}
        for k, v in state.items():
            if k.startswith("features."):
                fixed_state[k[len("features."):]] = v
            else:
                fixed_state[k] = v
        missing, unexpected = self.features.load_state_dict(fixed_state, strict=False)
        if missing or unexpected:
            print(
                f"[VGGPerceptualExtractor] load 警告: "
                f"missing={len(missing)} unexpected={len(unexpected)}"
            )
        self.features.eval()
        for p in self.features.parameters():
            p.requires_grad = False
        return self

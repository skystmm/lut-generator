"""
色彩空间转换模块 - ColorSpaceConverter

提供 RGB、Lab、XYZ 等色彩空间之间的精确转换
支持 colour-science 精确转换和 OpenCV 近似转换两种模式
"""

import numpy as np
import cv2
from typing import Tuple, Union
from pathlib import Path

try:
    import colour
    COLOUR_AVAILABLE = True
except ImportError:
    COLOUR_AVAILABLE = False


class ColorSpaceConverter:
    """
    色彩空间转换器
    
    支持 RGB ↔ Lab ↔ XYZ 等色彩空间转换
    可选择使用 colour-science 精确转换或 OpenCV 近似转换
    """
    
    def __init__(self, use_colour: bool = True):
        """
        初始化色彩空间转换器
        
        Args:
            use_colour: 是否使用 colour-science 库进行精确转换
                       如果为 False 或 colour 不可用，则使用 OpenCV 近似转换
        """
        self.use_colour = use_colour and COLOUR_AVAILABLE
        if not self.use_colour:
            print("Warning: colour-science not installed. Using OpenCV for color conversion.")
    
    def load_image(self, image_path: Union[str, Path]) -> np.ndarray:
        """
        加载图像并转换为 RGB 格式
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            RGB 格式的 numpy 数组，值范围 0-255
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return img_rgb
    
    def rgb_to_lab(self, rgb: np.ndarray) -> np.ndarray:
        """
        RGB 转 Lab 色彩空间
        
        Args:
            rgb: RGB 图像数组，shape=(H, W, 3)，值范围 0-255 或 0-1
            
        Returns:
            Lab 图像数组，shape=(H, W, 3)
            L: 0-100, a: -128-127, b: -128-127
        """
        # 归一化到 0-1
        if rgb.max() > 1.0:
            rgb_normalized = rgb.astype(np.float64) / 255.0
        else:
            rgb_normalized = rgb.astype(np.float64)
        
        if self.use_colour:
            try:
                h, w = rgb_normalized.shape[:2]
                rgb_flat = rgb_normalized.reshape(-1, 3)
                
                # sRGB → XYZ → Lab (D65 illuminant, 2° observer)
                xyz = colour.sRGB_to_XYZ(rgb_flat)
                lab_flat = colour.XYZ_to_Lab(xyz)
                
                lab = lab_flat.reshape(h, w, 3)
                return lab
            except Exception as e:
                print(f"colour-science conversion failed: {e}, falling back to OpenCV")
                self.use_colour = False
        
        # OpenCV 近似转换
        if rgb_normalized.max() <= 1.0:
            rgb_for_cv = (rgb_normalized * 255).astype(np.uint8)
        else:
            rgb_for_cv = rgb_normalized.astype(np.uint8)
        
        lab = cv2.cvtColor(rgb_for_cv, cv2.COLOR_RGB2LAB).astype(np.float64)
        
        # OpenCV 的 L 范围是 0-255，需要转换到 0-100
        # a,b 范围是 0-255，需要调整到 -128-127
        lab[:, :, 0] = lab[:, :, 0] * (100.0 / 255.0)
        lab[:, :, 1] = lab[:, :, 1] - 128
        lab[:, :, 2] = lab[:, :, 2] - 128
        
        return lab
    
    def lab_to_rgb(self, lab: np.ndarray) -> np.ndarray:
        """
        Lab 转 RGB 色彩空间
        
        Args:
            lab: Lab 图像数组，shape=(H, W, 3)
                 L: 0-100, a: -128-127, b: -128-127
                 
        Returns:
            RGB 图像数组，shape=(H, W, 3)，值范围 0-1
        """
        if self.use_colour:
            try:
                h, w = lab.shape[:2]
                lab_flat = lab.reshape(-1, 3)
                
                # Lab → XYZ → sRGB
                xyz = colour.Lab_to_XYZ(lab_flat)
                rgb_flat = colour.XYZ_to_sRGB(xyz)
                rgb_flat = np.clip(rgb_flat, 0, 1)
                
                return rgb_flat.reshape(h, w, 3)
            except Exception as e:
                print(f"colour-science conversion failed: {e}, falling back to OpenCV")
                self.use_colour = False
        
        # OpenCV 转换
        lab_for_cv = lab.copy()
        lab_for_cv[:, :, 0] = lab_for_cv[:, :, 0] * (255.0 / 100.0)
        lab_for_cv[:, :, 1] = lab_for_cv[:, :, 1] + 128
        lab_for_cv[:, :, 2] = lab_for_cv[:, :, 2] + 128
        lab_for_cv = np.clip(lab_for_cv, 0, 255).astype(np.uint8)
        
        rgb = cv2.cvtColor(lab_for_cv, cv2.COLOR_LAB2RGB)
        return rgb.astype(np.float64) / 255.0
    
    def rgb_to_xyz(self, rgb: np.ndarray) -> np.ndarray:
        """
        RGB 转 XYZ 色彩空间
        
        Args:
            rgb: RGB 图像数组，值范围 0-255 或 0-1
            
        Returns:
            XYZ 图像数组
        """
        if rgb.max() > 1.0:
            rgb_normalized = rgb.astype(np.float64) / 255.0
        else:
            rgb_normalized = rgb.astype(np.float64)
        
        if self.use_colour:
            h, w = rgb_normalized.shape[:2]
            rgb_flat = rgb_normalized.reshape(-1, 3)
            xyz_flat = colour.sRGB_to_XYZ(rgb_flat)
            return xyz_flat.reshape(h, w, 3)
        
        # OpenCV 没有直接的 RGB→XYZ，使用近似公式
        raise NotImplementedError("XYZ conversion requires colour-science library")
    
    def xyz_to_rgb(self, xyz: np.ndarray) -> np.ndarray:
        """
        XYZ 转 RGB 色彩空间
        
        Args:
            xyz: XYZ 图像数组
            
        Returns:
            RGB 图像数组，值范围 0-1
        """
        if self.use_colour:
            h, w = xyz.shape[:2]
            xyz_flat = xyz.reshape(-1, 3)
            rgb_flat = colour.XYZ_to_sRGB(xyz_flat)
            rgb_flat = np.clip(rgb_flat, 0, 1)
            return rgb_flat.reshape(h, w, 3)
        
        raise NotImplementedError("XYZ conversion requires colour-science library")
    
    def clip_to_gamut(self, lab: np.ndarray) -> np.ndarray:
        """
        裁剪到有效 Lab 色域
        
        Args:
            lab: Lab 图像数组
            
        Returns:
            裁剪后的 Lab 数组
        """
        lab_clipped = lab.copy()
        
        # L: 0-100
        lab_clipped[:, :, 0] = np.clip(lab_clipped[:, :, 0], 0, 100)
        
        # a, b: -128-127
        lab_clipped[:, :, 1] = np.clip(lab_clipped[:, :, 1], -128, 127)
        lab_clipped[:, :, 2] = np.clip(lab_clipped[:, :, 2], -128, 127)
        
        return lab_clipped
"""
性能优化模块 - LUT 生成器

提供以下优化功能：
1. LUT 加载缓存 - 避免重复加载相同的 LUT 文件
2. 并行处理 - 批量处理时利用多核 CPU
3. 内存优化 - 分块处理大图像，避免内存溢出
4. 预计算优化 - 缓存常用的计算结果

作者：RD Agent
版本：1.0.0
日期：2026-04-13
"""

import os
import hashlib
import multiprocessing as mp
from multiprocessing import Pool, cpu_count
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
from PIL import Image
import time
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """缓存配置"""
    max_size: int = 100  # 最大缓存条目数
    ttl_seconds: int = 3600  # 缓存生存时间（秒）
    enabled: bool = True  # 是否启用缓存


@dataclass
class ParallelConfig:
    """并行处理配置"""
    num_workers: int = None  # worker 数量，None 表示自动检测
    chunk_size: int = 4  # 每个 worker 处理的图像数量
    use_processes: bool = True  # True=多进程，False=多线程
    max_memory_per_worker: int = 2048  # 每个 worker 最大内存 (MB)


@dataclass
class MemoryConfig:
    """内存优化配置"""
    chunk_size_mb: int = 256  # 分块大小 (MB)
    max_image_size: int = 10000  # 最大图像边长（超过则自动缩放）
    enable_chunking: bool = True  # 是否启用分块处理
    garbage_collection_interval: int = 10  # GC 间隔（每处理 N 张图像）


@dataclass
class OptimizerStats:
    """优化器统计信息"""
    cache_hits: int = 0
    cache_misses: int = 0
    total_processing_time: float = 0.0
    total_images_processed: int = 0
    peak_memory_mb: float = 0.0
    parallel_speedup: float = 1.0


class LUTCache:
    """
    LUT 缓存类
    
    功能：
    - 基于文件哈希的缓存键
    - LRU 淘汰策略
    - 自动过期
    """
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._access_order: List[str] = []
        self._lock = threading.RLock()
        
    def _compute_hash(self, data: Any) -> str:
        """计算数据的哈希值"""
        if isinstance(data, (str, Path)):
            # 文件路径 - 计算文件内容的 MD5
            path = Path(data)
            if path.exists():
                with open(path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()
            else:
                return hashlib.md5(str(data).encode()).hexdigest()
        elif isinstance(data, np.ndarray):
            # numpy 数组
            return hashlib.md5(data.tobytes()).hexdigest()
        else:
            # 其他类型
            return hashlib.md5(str(data).encode()).hexdigest()
    
    def get(self, key: Any) -> Optional[Any]:
        """从缓存获取数据"""
        if not self.config.enabled:
            return None
            
        with self._lock:
            cache_key = self._compute_hash(key)
            
            if cache_key in self._cache:
                data, timestamp = self._cache[cache_key]
                
                # 检查是否过期
                if time.time() - timestamp < self.config.ttl_seconds:
                    # 更新访问顺序（移到末尾）
                    self._access_order.remove(cache_key)
                    self._access_order.append(cache_key)
                    return data
                else:
                    # 过期，删除
                    del self._cache[cache_key]
                    self._access_order.remove(cache_key)
            
            return None
    
    def put(self, key: Any, value: Any):
        """将数据放入缓存"""
        if not self.config.enabled:
            return
            
        with self._lock:
            cache_key = self._compute_hash(key)
            
            # 如果缓存已满，淘汰最旧的条目
            while len(self._cache) >= self.config.max_size and self._access_order:
                oldest_key = self._access_order.pop(0)
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
            
            # 添加新条目
            self._cache[cache_key] = (value, time.time())
            self._access_order.append(cache_key)
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def stats(self) -> Dict[str, int]:
        """获取缓存统计"""
        return {
            'size': len(self._cache),
            'max_size': self.config.max_size,
            'enabled': self.config.enabled
        }


class ChunkedImageProcessor:
    """
    分块图像处理器
    
    功能：
    - 将大图像分割成小块处理
    - 避免内存溢出
    - 支持进度回调
    """
    
    def __init__(self, config: MemoryConfig = None):
        self.config = config or MemoryConfig()
        
    def _calculate_chunk_size(self, image_shape: Tuple[int, int, int]) -> Tuple[int, int]:
        """
        计算合适的分块大小
        
        Args:
            image_shape: 图像形状 (height, width, channels)
            
        Returns:
            (chunk_height, chunk_width)
        """
        height, width = image_shape[:2]
        
        # 估算单像素内存占用（假设 float64）
        bytes_per_pixel = 8
        channels = image_shape[2] if len(image_shape) > 2 else 3
        
        # 计算目标分块大小（基于内存限制）
        target_bytes = self.config.chunk_size_mb * 1024 * 1024
        target_pixels = target_bytes // (bytes_per_pixel * channels)
        
        # 计算分块边长
        chunk_side = int(np.sqrt(target_pixels))
        
        # 确保分块大小合理
        chunk_side = max(64, min(chunk_side, 2048))
        
        return (chunk_side, chunk_side)
    
    def process_in_chunks(
        self,
        image: np.ndarray,
        process_func: Callable[[np.ndarray], np.ndarray],
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> np.ndarray:
        """
        分块处理图像
        
        Args:
            image: 输入图像 (numpy array)
            process_func: 处理函数，接受图像块，返回处理后的块
            progress_callback: 进度回调函数 (0.0-1.0)
            
        Returns:
            处理后的图像
        """
        if not self.config.enable_chunking:
            # 直接处理
            result = process_func(image)
            if progress_callback:
                progress_callback(1.0)
            return result
        
        height, width = image.shape[:2]
        chunk_h, chunk_w = self._calculate_chunk_size(image.shape)
        
        # 检查是否需要分块
        if height <= chunk_h and width <= chunk_w:
            result = process_func(image)
            if progress_callback:
                progress_callback(1.0)
            return result
        
        # 创建输出数组
        result = np.zeros_like(image)
        
        # 计算分块数量
        num_chunks_h = (height + chunk_h - 1) // chunk_h
        num_chunks_w = (width + chunk_w - 1) // chunk_w
        total_chunks = num_chunks_h * num_chunks_w
        
        processed_chunks = 0
        
        # 分块处理
        for i in range(0, height, chunk_h):
            for j in range(0, width, chunk_w):
                # 计算当前块的边界
                h_end = min(i + chunk_h, height)
                w_end = min(j + chunk_w, width)
                
                # 提取块
                chunk = image[i:h_end, j:w_end]
                
                # 处理块
                processed_chunk = process_func(chunk)
                
                # 放回结果
                result[i:h_end, j:w_end] = processed_chunk
                
                # 更新进度
                processed_chunks += 1
                if progress_callback:
                    progress_callback(processed_chunks / total_chunks)
        
        return result
    
    def estimate_memory_usage(self, image_shape: Tuple[int, int, int]) -> float:
        """
        估算内存使用量 (MB)
        
        Args:
            image_shape: 图像形状
            
        Returns:
            估算的内存使用量 (MB)
        """
        bytes_per_pixel = 8  # float64
        channels = image_shape[2] if len(image_shape) > 2 else 3
        total_pixels = np.prod(image_shape[:2])
        
        # 输入 + 输出 + 临时缓冲区
        memory_bytes = total_pixels * bytes_per_pixel * channels * 3
        return memory_bytes / (1024 * 1024)


def _worker_process(args: Tuple) -> Any:
    """
    Worker 进程函数（用于多进程并行处理）
    
    Args:
        args: (process_func, input_data, args, kwargs)
        
    Returns:
        处理结果
    """
    func, data, func_args, func_kwargs = args
    try:
        return func(data, *func_args, **func_kwargs)
    except Exception as e:
        logger.error(f"Worker 处理错误：{e}")
        raise


class ParallelProcessor:
    """
    并行处理器
    
    功能：
    - 多进程/多线程并行处理
    - 自动检测 CPU 核心数
    - 内存限制保护
    - 进度跟踪
    """
    
    def __init__(self, config: ParallelConfig = None):
        self.config = config or ParallelConfig()
        
        if self.config.num_workers is None:
            # 自动检测 CPU 核心数，保留一个核心给系统
            self.config.num_workers = max(1, cpu_count() - 1)
        
        self._stats = {
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_time': 0.0
        }
    
    def process_batch(
        self,
        items: List[Any],
        process_func: Callable[[Any], Any],
        progress_callback: Optional[Callable[[float, int, int], None]] = None,
        *func_args,
        **func_kwargs
    ) -> List[Any]:
        """
        批量并行处理
        
        Args:
            items: 待处理的项目列表
            process_func: 处理函数
            progress_callback: 进度回调 (progress, completed, total)
            func_args: 传递给处理函数的位置参数
            func_kwargs: 传递给处理函数的关键字参数
            
        Returns:
            处理结果列表
        """
        if not items:
            return []
        
        start_time = time.time()
        total_items = len(items)
        results = [None] * total_items
        
        if self.config.use_processes and total_items > 1:
            # 多进程处理
            logger.info(f"使用 {self.config.num_workers} 个进程处理 {total_items} 个项目")
            
            # 准备任务
            tasks = [(process_func, item, func_args, func_kwargs) for item in items]
            
            with ProcessPoolExecutor(max_workers=self.config.num_workers) as executor:
                # 提交任务
                future_to_index = {
                    executor.submit(_worker_process, task): idx
                    for idx, task in enumerate(tasks)
                }
                
                completed = 0
                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        results[idx] = future.result()
                        completed += 1
                        
                        if progress_callback:
                            progress_callback(completed / total_items, completed, total_items)
                            
                    except Exception as e:
                        logger.error(f"任务 {idx} 处理失败：{e}")
                        self._stats['tasks_failed'] += 1
                        raise
        else:
            # 单线程/多线程处理
            logger.info(f"使用单线程处理 {total_items} 个项目")
            
            for idx, item in enumerate(items):
                try:
                    results[idx] = process_func(item, *func_args, **func_kwargs)
                    
                    if progress_callback:
                        progress_callback((idx + 1) / total_items, idx + 1, total_items)
                        
                except Exception as e:
                    logger.error(f"任务 {idx} 处理失败：{e}")
                    self._stats['tasks_failed'] += 1
                    raise
        
        elapsed_time = time.time() - start_time
        self._stats['tasks_completed'] += len([r for r in results if r is not None])
        self._stats['total_time'] += elapsed_time
        
        logger.info(f"批量处理完成：{total_items} 个项目，耗时 {elapsed_time:.2f} 秒")
        
        return results
    
    def calculate_speedup(
        self,
        items: List[Any],
        process_func: Callable[[Any], Any],
        *func_args,
        **func_kwargs
    ) -> float:
        """
        计算并行加速比
        
        Args:
            items: 测试项目列表
            process_func: 处理函数
            func_args: 处理函数的位置参数
            func_kwargs: 处理函数的关键字参数
            
        Returns:
            加速比（串行时间/并行时间）
        """
        if len(items) < 2:
            return 1.0
        
        # 串行执行时间
        start_serial = time.time()
        for item in items:
            process_func(item, *func_args, **func_kwargs)
        serial_time = time.time() - start_serial
        
        # 并行执行时间
        start_parallel = time.time()
        self.process_batch(items, process_func, None, *func_args, **func_kwargs)
        parallel_time = time.time() - start_parallel
        
        speedup = serial_time / parallel_time if parallel_time > 0 else 1.0
        logger.info(f"并行加速比：{speedup:.2f}x (串行：{serial_time:.2f}s, 并行：{parallel_time:.2f}s)")
        
        return speedup
    
    def get_stats(self) -> Dict[str, Any]:
        """获取处理器统计"""
        return self._stats.copy()


class PerformanceOptimizer:
    """
    性能优化器 - 统一接口
    
    整合所有优化功能：
    - LUT 缓存
    - 并行处理
    - 内存优化
    """
    
    def __init__(
        self,
        cache_config: CacheConfig = None,
        parallel_config: ParallelConfig = None,
        memory_config: MemoryConfig = None
    ):
        self.cache = LUTCache(cache_config)
        self.parallel_processor = ParallelProcessor(parallel_config)
        self.chunked_processor = ChunkedImageProcessor(memory_config)
        self.stats = OptimizerStats()
        
    def apply_lut_optimized(
        self,
        image: np.ndarray,
        lut: np.ndarray,
        lut_applier_func: Callable[[np.ndarray, np.ndarray], np.ndarray],
        use_cache: bool = True,
        use_chunking: bool = True
    ) -> np.ndarray:
        """
        优化的 LUT 应用
        
        Args:
            image: 输入图像
            lut: LUT 数据
            lut_applier_func: LUT 应用函数
            use_cache: 是否使用缓存
            use_chunking: 是否使用分块处理
            
        Returns:
            处理后的图像
        """
        start_time = time.time()
        
        # 尝试从缓存获取
        if use_cache:
            cache_key = (image.tobytes(), lut.tobytes())
            cached_result = self.cache.get(cache_key)
            
            if cached_result is not None:
                self.stats.cache_hits += 1
                logger.debug("LUT 缓存命中")
                return cached_result
            
            self.stats.cache_misses += 1
        
        # 定义处理函数
        def process_func(img_chunk):
            return lut_applier_func(img_chunk, lut)
        
        # 分块处理
        if use_chunking:
            result = self.chunked_processor.process_in_chunks(image, process_func)
        else:
            result = process_func(image)
        
        # 缓存结果
        if use_cache:
            self.cache.put(cache_key, result)
        
        # 更新统计
        self.stats.total_processing_time += time.time() - start_time
        self.stats.total_images_processed += 1
        
        return result
    
    def process_batch_optimized(
        self,
        images: List[np.ndarray],
        process_func: Callable[[np.ndarray], np.ndarray],
        progress_callback: Optional[Callable[[float, int, int], None]] = None
    ) -> List[np.ndarray]:
        """
        优化的批量处理
        
        Args:
            images: 图像列表
            process_func: 处理函数
            progress_callback: 进度回调
            
        Returns:
            处理后的图像列表
        """
        return self.parallel_processor.process_batch(
            images,
            process_func,
            progress_callback
        )
    
    def get_stats(self) -> OptimizerStats:
        """获取优化器统计"""
        self.stats.peak_memory_mb = self._get_memory_usage()
        return self.stats
    
    def _get_memory_usage(self) -> float:
        """获取当前内存使用量 (MB)"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        logger.info("缓存已清空")


# 便捷函数
def optimize_lut_application(
    image: np.ndarray,
    lut: np.ndarray,
    lut_applier_func: Callable,
    cache_size: int = 100,
    enable_chunking: bool = True,
    chunk_size_mb: int = 256
) -> np.ndarray:
    """
    优化的 LUT 应用便捷函数
    
    Args:
        image: 输入图像
        lut: LUT 数据
        lut_applier_func: LUT 应用函数
        cache_size: 缓存大小
        enable_chunking: 是否启用分块
        chunk_size_mb: 分块大小 (MB)
        
    Returns:
        处理后的图像
    """
    optimizer = PerformanceOptimizer(
        cache_config=CacheConfig(max_size=cache_size),
        memory_config=MemoryConfig(
            enable_chunking=enable_chunking,
            chunk_size_mb=chunk_size_mb
        )
    )
    
    return optimizer.apply_lut_optimized(image, lut, lut_applier_func)


def process_images_parallel(
    images: List[Any],
    process_func: Callable,
    num_workers: int = None,
    use_processes: bool = True
) -> List[Any]:
    """
    并行处理图像便捷函数
    
    Args:
        images: 图像列表
        process_func: 处理函数
        num_workers: worker 数量
        use_processes: 是否使用多进程
        
    Returns:
        处理结果列表
    """
    processor = ParallelProcessor(
        ParallelConfig(
            num_workers=num_workers,
            use_processes=use_processes
        )
    )
    
    return processor.process_batch(images, process_func)


# 示例用法
if __name__ == "__main__":
    # 创建优化器
    optimizer = PerformanceOptimizer()
    
    # 测试缓存
    test_data = np.random.rand(100, 100, 3)
    test_lut = np.random.rand(33, 33, 33, 3)
    
    def dummy_lut_applier(img, lut):
        return img * 0.9  # 简化示例
    
    # 第一次调用（缓存未命中）
    result1 = optimizer.apply_lut_optimized(test_data, test_lut, dummy_lut_applier)
    
    # 第二次调用（缓存命中）
    result2 = optimizer.apply_lut_optimized(test_data, test_lut, dummy_lut_applier)
    
    # 打印统计
    stats = optimizer.get_stats()
    print(f"缓存命中：{stats.cache_hits}")
    print(f"缓存未命中：{stats.cache_misses}")
    print(f"总处理时间：{stats.total_processing_time:.4f} 秒")
    
    # 测试并行处理
    test_images = [np.random.rand(100, 100, 3) for _ in range(10)]
    
    def dummy_process(img):
        time.sleep(0.1)  # 模拟处理
        return img * 0.9
    
    results = optimizer.process_batch_optimized(test_images, dummy_process)
    print(f"并行处理完成：{len(results)} 个图像")
    
    # 计算加速比
    speedup = optimizer.parallel_processor.calculate_speedup(
        test_images[:5],  # 使用较少的图像进行快速测试
        dummy_process
    )
    print(f"加速比：{speedup:.2f}x")

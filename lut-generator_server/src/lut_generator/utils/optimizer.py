"""
性能优化模块 - LUT 生成器

提供以下优化功能：
1. LUT 加载缓存 - 避免重复加载相同的 LUT 文件
2. 并行处理 - 批量处理时利用多核 CPU
3. 内存优化 - 分块处理大图像，避免内存溢出
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

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """缓存配置"""
    max_size: int = 100
    ttl_seconds: int = 3600
    enabled: bool = True


@dataclass
class ParallelConfig:
    """并行处理配置"""
    num_workers: int = None
    chunk_size: int = 4
    use_processes: bool = True
    max_memory_per_worker: int = 2048


@dataclass
class MemoryConfig:
    """内存优化配置"""
    chunk_size_mb: int = 256
    max_image_size: int = 10000
    enable_chunking: bool = True
    garbage_collection_interval: int = 10


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
    """LUT 缓存类"""
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._access_order: List[str] = []
        self._lock = threading.RLock()
        
    def _compute_hash(self, data: Any) -> str:
        """计算数据的哈希值"""
        if isinstance(data, (str, Path)):
            path = Path(data)
            if path.exists():
                with open(path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()
            else:
                return hashlib.md5(str(data).encode()).hexdigest()
        elif isinstance(data, np.ndarray):
            return hashlib.md5(data.tobytes()).hexdigest()
        else:
            return hashlib.md5(str(data).encode()).hexdigest()
    
    def get(self, key: Any) -> Optional[Any]:
        """从缓存获取数据"""
        if not self.config.enabled:
            return None
            
        with self._lock:
            cache_key = self._compute_hash(key)
            
            if cache_key in self._cache:
                data, timestamp = self._cache[cache_key]
                
                if time.time() - timestamp < self.config.ttl_seconds:
                    self._access_order.remove(cache_key)
                    self._access_order.append(cache_key)
                    return data
                else:
                    del self._cache[cache_key]
                    self._access_order.remove(cache_key)
            
            return None
    
    def put(self, key: Any, value: Any):
        """将数据放入缓存"""
        if not self.config.enabled:
            return
            
        with self._lock:
            cache_key = self._compute_hash(key)
            
            while len(self._cache) >= self.config.max_size and self._access_order:
                oldest_key = self._access_order.pop(0)
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
            
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
    """分块图像处理器"""
    
    def __init__(self, config: MemoryConfig = None):
        self.config = config or MemoryConfig()
        
    def _calculate_chunk_size(self, image_shape: Tuple[int, int, int]) -> Tuple[int, int]:
        """计算合适的分块大小"""
        height, width = image_shape[:2]
        
        bytes_per_pixel = 8
        channels = image_shape[2] if len(image_shape) > 2 else 3
        
        target_bytes = self.config.chunk_size_mb * 1024 * 1024
        target_pixels = target_bytes // (bytes_per_pixel * channels)
        
        chunk_side = int(np.sqrt(target_pixels))
        chunk_side = max(64, min(chunk_side, 2048))
        
        return (chunk_side, chunk_side)
    
    def process_in_chunks(
        self,
        image: np.ndarray,
        process_func: Callable[[np.ndarray], np.ndarray],
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> np.ndarray:
        """分块处理图像"""
        if not self.config.enable_chunking:
            result = process_func(image)
            if progress_callback:
                progress_callback(1.0)
            return result
        
        height, width = image.shape[:2]
        chunk_h, chunk_w = self._calculate_chunk_size(image.shape)
        
        if height <= chunk_h and width <= chunk_w:
            result = process_func(image)
            if progress_callback:
                progress_callback(1.0)
            return result
        
        result = np.zeros_like(image)
        
        num_chunks_h = (height + chunk_h - 1) // chunk_h
        num_chunks_w = (width + chunk_w - 1) // chunk_w
        total_chunks = num_chunks_h * num_chunks_w
        
        processed_chunks = 0
        
        for i in range(0, height, chunk_h):
            for j in range(0, width, chunk_w):
                h_end = min(i + chunk_h, height)
                w_end = min(j + chunk_w, width)
                
                chunk = image[i:h_end, j:w_end]
                processed_chunk = process_func(chunk)
                
                result[i:h_end, j:w_end] = processed_chunk
                
                processed_chunks += 1
                if progress_callback:
                    progress_callback(processed_chunks / total_chunks)
        
        return result
    
    def estimate_memory_usage(self, image_shape: Tuple[int, int, int]) -> float:
        """估算内存使用量 (MB)"""
        bytes_per_pixel = 8
        channels = image_shape[2] if len(image_shape) > 2 else 3
        total_pixels = np.prod(image_shape[:2])
        
        memory_bytes = total_pixels * bytes_per_pixel * channels * 3
        return memory_bytes / (1024 * 1024)


def _worker_process(args: Tuple) -> Any:
    """Worker 进程函数"""
    func, data, func_args, func_kwargs = args
    try:
        return func(data, *func_args, **func_kwargs)
    except (ValueError, TypeError, IOError, OSError, RuntimeError, KeyError, IndexError) as e:
        logger.error(f"Worker 处理错误：{e}")
        raise


class ParallelProcessor:
    """并行处理器"""
    
    def __init__(self, config: ParallelConfig = None):
        self.config = config or ParallelConfig()
        
        if self.config.num_workers is None:
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
        """批量并行处理"""
        if not items:
            return []
        
        start_time = time.time()
        total_items = len(items)
        results = [None] * total_items
        
        if self.config.use_processes and total_items > 1:
            logger.info(f"使用 {self.config.num_workers} 个进程处理 {total_items} 个项目")
            
            tasks = [(process_func, item, func_args, func_kwargs) for item in items]
            
            with ProcessPoolExecutor(max_workers=self.config.num_workers) as executor:
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
                            
                    except (ValueError, TypeError, IOError, OSError, RuntimeError, KeyError, IndexError) as e:
                        logger.error(f"任务 {idx} 处理失败：{e}")
                        self._stats['tasks_failed'] += 1
                        raise
        else:
            logger.info(f"使用单线程处理 {total_items} 个项目")
            
            for idx, item in enumerate(items):
                try:
                    results[idx] = process_func(item, *func_args, **func_kwargs)
                    
                    if progress_callback:
                        progress_callback((idx + 1) / total_items, idx + 1, total_items)
                        
                except (ValueError, TypeError, IOError, OSError, RuntimeError, KeyError, IndexError) as e:
                    logger.error(f"任务 {idx} 处理失败：{e}")
                    self._stats['tasks_failed'] += 1
                    raise
        
        elapsed_time = time.time() - start_time
        self._stats['tasks_completed'] += len([r for r in results if r is not None])
        self._stats['total_time'] += elapsed_time
        
        logger.info(f"批量处理完成：{total_items} 个项目，耗时 {elapsed_time:.2f} 秒")
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取处理器统计"""
        return self._stats.copy()


class PerformanceOptimizer:
    """性能优化器 - 统一接口"""
    
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
        """优化的 LUT 应用"""
        start_time = time.time()
        
        if use_cache:
            cache_key = (image.tobytes(), lut.tobytes())
            cached_result = self.cache.get(cache_key)
            
            if cached_result is not None:
                self.stats.cache_hits += 1
                return cached_result
        
        if use_chunking:
            def process_chunk(chunk):
                return lut_applier_func(chunk, lut)
            
            result = self.chunked_processor.process_in_chunks(image, process_chunk)
        else:
            result = lut_applier_func(image, lut)
        
        if use_cache:
            cache_key = (image.tobytes(), lut.tobytes())
            self.cache.put(cache_key, result)
        
        elapsed_time = time.time() - start_time
        self.stats.total_processing_time += elapsed_time
        self.stats.total_images_processed += 1
        
        return result

from typing import Any, Dict, List, Optional
import threading
import time
from dataclasses import dataclass

@dataclass
class VersionedItem:
    """带版本号的数据项"""
    data: Any
    version: int
    timestamp: float  # 写入时间戳，用于调试或清理
    
class RingBuffer:
    def __init__(self, size: int = 1000):
        """
        初始化环形缓冲区
        
        Args:
            size: 缓冲区大小
        """
        if size <= 0:
            raise ValueError("Buffer size must be positive")
            
        self.size = size
        self.buffer: List[Optional[VersionedItem]] = [None] * size
        
        # 读写指针
        self.write_idx = 0
        self.write_version = 0  # 全局版本号
        
        # 读者管理
        self.readers: Dict[int, Dict[str, Any]] = {}
        self.next_reader_id = 0
        
        # 线程安全
        self.lock = threading.RLock()
        self.reader_lock = threading.RLock()
        
        # 统计信息
        self.stats = {
            'writes': 0,
            'overwrites': 0,
            'total_reads': 0
        }
        
    def register(self, reader_name: Optional[str] = None) -> int:
        """
        注册一个新读者
        
        Args:
            reader_name: 读者名称，用于标识
            
        Returns:
            读者ID
        """
        with self.reader_lock:
            reader_id = self.next_reader_id
            self.next_reader_id += 1
            
            self.readers[reader_id] = {
                'name': reader_name or f"reader_{reader_id}",
                'read_idx': 0,  # 该读者的读指针
                'last_version': -1,  # 最后读取的版本号
                'read_count': 0,  # 该读者读取次数
                'last_read_time': None,  # 最后读取时间
                'registered_time': time.time()
            }
            
            return reader_id
            
    def unregister(self, reader_id: int) -> bool:
        """
        注销读者
        
        Args:
            reader_id: 读者ID
            
        Returns:
            是否成功注销
        """
        with self.reader_lock:
            if reader_id in self.readers:
                del self.readers[reader_id]
                return True
            return False
            
    def write(self, data: Any) -> int:
        """
        写入数据到缓冲区
        
        Args:
            data: 要写入的数据
            
        Returns:
            写入的版本号
        """
        with self.lock:
            # 创建带版本号的数据项
            item = VersionedItem(
                data=data,
                version=self.write_version,
                timestamp=time.time()
            )
            
            # 检查是否要覆盖旧数据
            old_item = self.buffer[self.write_idx]
            if old_item is not None:
                self.stats['overwrites'] += 1
                
                # 检查是否有读者还没读过这个将被覆盖的数据
                self._check_overwrite_safety(old_item.version)
            
            # 写入缓冲区
            self.buffer[self.write_idx] = item
            
            # 更新写指针和版本号
            self.write_idx = (self.write_idx + 1) % self.size
            self.write_version += 1
            self.stats['writes'] += 1
            
            return item.version
            
    def _check_overwrite_safety(self, version_to_overwrite: int) -> None:
        """
        检查覆盖指定版本的数据是否安全
        
        Args:
            version_to_overwrite: 将被覆盖的版本号
        """
        with self.reader_lock:
            for reader_id, reader_info in self.readers.items():
                if reader_info['last_version'] < version_to_overwrite:
                    # 这个读者还没读过这个版本
                    # 在实际应用中，可能需要更复杂的处理逻辑
                    # 这里只是打印警告
                    print(f"Warning: Overwriting data (version {version_to_overwrite}) "
                          f"not yet read by reader '{reader_info['name']}'")
                    
    def read(self, reader_id: int, max_items: int = 1) -> List[Any]:
        """
        为指定读者读取数据
        
        Args:
            reader_id: 读者ID
            max_items: 最多读取多少项数据
            
        Returns:
            读取到的数据列表
        """
        if reader_id not in self.readers:
            raise ValueError(f"Reader {reader_id} not registered")
            
        with self.lock:
            reader_info = self.readers[reader_id]
            read_idx = reader_info['read_idx']
            read_version = reader_info['last_version']
            
            # 计算可读取的数据
            items_to_read = []
            
            for _ in range(max_items):
                # 如果读指针追上了写指针，表示没有新数据
                if read_idx == self.write_idx and self.buffer[read_idx] is None:
                    break
                    
                item = self.buffer[read_idx]
                if item is None:
                    # 当前位置没有数据
                    break
                    
                # 只读取比读者最后版本号新的数据
                if item.version > read_version:
                    items_to_read.append(item.data)
                    read_version = item.version
                    
                    # 移动到下一个位置
                    read_idx = (read_idx + 1) % self.size
                else:
                    # 读者已经读过这个版本了
                    # 直接跳过，但不移动读指针（等待新数据）
                    break
            
            # 更新读者状态
            if items_to_read:
                reader_info['read_idx'] = read_idx
                reader_info['last_version'] = read_version
                reader_info['read_count'] += len(items_to_read)
                reader_info['last_read_time'] = time.time()
                
                self.stats['total_reads'] += len(items_to_read)
            
            return items_to_read
            
    def read_with_metadata(self, reader_id: int, max_items: int = 1) -> List[Dict]:
        """
        读取数据并包含元数据（版本号、时间戳等）
        
        Args:
            reader_id: 读者ID
            max_items: 最多读取多少项数据
            
        Returns:
            包含数据和元数据的字典列表
        """
        if reader_id not in self.readers:
            raise ValueError(f"Reader {reader_id} not registered")
            
        with self.lock:
            reader_info = self.readers[reader_id]
            read_idx = reader_info['read_idx']
            read_version = reader_info['last_version']
            
            items_to_read = []
            
            for _ in range(max_items):
                if read_idx == self.write_idx and self.buffer[read_idx] is None:
                    break
                    
                item = self.buffer[read_idx]
                if item is None:
                    break
                    
                if item.version > read_version:
                    items_to_read.append({
                        'data': item.data,
                        'version': item.version,
                        'timestamp': item.timestamp,
                        'reader_name': reader_info['name']
                    })
                    read_version = item.version
                    read_idx = (read_idx + 1) % self.size
                else:
                    break
            
            # 更新读者状态
            if items_to_read:
                reader_info['read_idx'] = read_idx
                reader_info['last_version'] = read_version
                reader_info['read_count'] += len(items_to_read)
                reader_info['last_read_time'] = time.time()
                self.stats['total_reads'] += len(items_to_read)
            
            return items_to_read
            
    def get_reader_info(self, reader_id: Optional[int] = None) -> Dict:
        """
        获取读者信息
        
        Args:
            reader_id: 读者ID，如果为None则返回所有读者信息
            
        Returns:
            读者信息字典
        """
        with self.reader_lock:
            if reader_id is not None:
                if reader_id in self.readers:
                    return self.readers[reader_id].copy()
                else:
                    raise ValueError(f"Reader {reader_id} not registered")
            else:
                return {rid: info.copy() for rid, info in self.readers.items()}
                
    def get_buffer_status(self) -> Dict:
        """
        获取缓冲区状态信息
        
        Returns:
            状态信息字典
        """
        with self.lock:
            # 统计有效数据数量
            valid_items = sum(1 for item in self.buffer if item is not None)
            
            return {
                'size': self.size,
                'write_idx': self.write_idx,
                'write_version': self.write_version,
                'valid_items': valid_items,
                'buffer_usage': valid_items / self.size * 100,
                'total_readers': len(self.readers),
                'stats': self.stats.copy()
            }
            
    def get_pending_data_for_reader(self, reader_id: int) -> List[Dict]:
        """
        获取指定读者待读取的数据（不实际读取）
        
        Args:
            reader_id: 读者ID
            
        Returns:
            待读取的数据信息
        """
        if reader_id not in self.readers:
            raise ValueError(f"Reader {reader_id} not registered")
            
        with self.lock:
            reader_info = self.readers[reader_id]
            read_idx = reader_info['read_idx']
            read_version = reader_info['last_version']
            
            pending_data = []
            current_idx = read_idx
            
            # 遍历缓冲区直到写指针
            while True:
                if current_idx == self.write_idx and self.buffer[current_idx] is None:
                    break
                    
                item = self.buffer[current_idx]
                if item is None:
                    break
                    
                if item.version > read_version:
                    pending_data.append({
                        'data': item.data,
                        'version': item.version,
                        'timestamp': item.timestamp,
                        'buffer_position': current_idx
                    })
                    
                current_idx = (current_idx + 1) % self.size
                if current_idx == read_idx:  # 避免无限循环
                    break
                    
            return pending_data
            
    def cleanup_old_readers(self, timeout_seconds: float = 3600) -> int:
        """
        清理长时间未活动的读者
        
        Args:
            timeout_seconds: 超时时间（秒）
            
        Returns:
            清理的读者数量
        """
        with self.reader_lock:
            current_time = time.time()
            readers_to_remove = []
            
            for reader_id, reader_info in self.readers.items():
                last_read = reader_info['last_read_time']
                if last_read is not None:
                    if current_time - last_read > timeout_seconds:
                        readers_to_remove.append(reader_id)
                else:
                    # 从未读取过的读者，检查注册时间
                    if current_time - reader_info['registered_time'] > timeout_seconds:
                        readers_to_remove.append(reader_id)
            
            for reader_id in readers_to_remove:
                del self.readers[reader_id]
                
            return len(readers_to_remove)


# 使用示例
def usage_example():
    """使用示例"""
    # 创建环形缓冲区
    buffer = RingBuffer(size=5)
    
    # 注册两个读者
    reader1 = buffer.register("consumer_1")
    reader2 = buffer.register("consumer_2")
    
    print(f"Reader 1 ID: {reader1}")
    print(f"Reader 2 ID: {reader2}")
    
    # 写入一些数据
    for i in range(10):
        version = buffer.write(f"Message {i}")
        print(f"Wrote message {i}, version: {version}")
    
    # 读者1读取数据
    print("\nReader 1 reading:")
    data1 = buffer.read(reader1, max_items=3)
    for item in data1:
        print(f"  Got: {item}")
    
    # 读者2读取数据
    print("\nReader 2 reading:")
    data2 = buffer.read(reader2, max_items=5)
    for item in data2:
        print(f"  Got: {item}")
    
    # 读者1再次读取
    print("\nReader 1 reading again:")
    data1 = buffer.read(reader1, max_items=5)
    for item in data1:
        print(f"  Got: {item}")
    
    # 获取状态信息
    print("\nBuffer status:")
    status = buffer.get_buffer_status()
    for key, value in status.items():
        if key == 'stats':
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    
    # 获取待读取数据
    print("\nPending data for reader 2:")
    pending = buffer.get_pending_data_for_reader(reader2)
    for item in pending:
        print(f"  Version {item['version']}: {item['data']}")


if __name__ == "__main__":
    usage_example()
from common import ringbuffer
from scapy.all import TCP, IP, IPv6
import ipaddress
import threading
from common import interceptor
import time

class TCPRadar:
    def __init__(self, kwargs):
        self.buffer: ringbuffer.RingBuffer = kwargs['buffer']
        self.src_net: ipaddress.ip_network = ipaddress.ip_network(kwargs['src'])
        self.dst_net: ipaddress.ip_network = ipaddress.ip_network(kwargs['dst'])
        self.iface = kwargs['iface']
        self.dst_mac = kwargs['dst_mac']
        self.reader = self.buffer.register()
        self.radar_thread = None
        self.stopFlag = False
        # 新增：用于追踪已拦截的连接，防止重复操作
        self.intercepted_conns = set()
        self.conn_timestamps = {}  # 新增: 记录拦截时间

    def get_tcp_info(self,packet):
        # 结果字典，用于存储提取的信息
        info = {
            "version": None,
            "src_addr": None,
            "dst_addr": None,
            "tcp_details": {}
        }

        # 1. 判断网络层 (IPv4 或 IPv6)
        if packet.haslayer(IP):
            info["version"] = "IPv4"
            info["src_addr"] = packet[IP].src
            info["dst_addr"] = packet[IP].dst
        elif packet.haslayer(IPv6):
            info["version"] = "IPv6"
            info["src_addr"] = packet[IPv6].src
            info["dst_addr"] = packet[IPv6].dst
        else:
            return None  # 非 IP 报文，直接跳过

        # 2. 判断传输层是否为 TCP
        if packet.haslayer(TCP):
            tcp = packet[TCP]
            info["tcp_details"] = {
                "sport": tcp.sport,
                "dport": tcp.dport,
                "seq": tcp.seq,
                "ack": tcp.ack,
                "flags": tcp.underlayer.sprintf("%TCP.flags%"), # 易读格式化标志位
                "window": tcp.window
            }
            
            return info
    
    def _cleanup_old_connections(self, timeout=300):
        """清理5分钟前的连接记录"""
        current_time = time.time()
        old_conns = [conn for conn, ts in self.conn_timestamps.items() 
                    if current_time - ts > timeout]
        for conn in old_conns:
            self.intercepted_conns.discard(conn)
            del self.conn_timestamps[conn]

    def detection(self):
        while not self.stopFlag:
            # 定期清理旧连接记录 (每1000次循环清理一次)
            if hasattr(self, 'loop_count'):
                self.loop_count += 1
                if self.loop_count % 1000 == 0:
                    self._cleanup_old_connections()
            else:
                self.loop_count = 0
            try:
                pkt_list = self.buffer.read(self.reader, max_items=1)
                if not pkt_list:
                    time.sleep(0.001)  # 避免空转
                    continue
            
                pkt = pkt_list[0]
                if not pkt.haslayer(TCP):
                    continue

                pkt_info = self.get_tcp_info(pkt)
                if not pkt_info:
                    continue

                # 提取连接四元组作为 Key
                conn_key = (
                    pkt_info['src_addr'], pkt_info['tcp_details']['sport'],
                    pkt_info['dst_addr'], pkt_info['tcp_details']['dport']
                )

                # 提取标志位
                flags = pkt[TCP].flags
                
                # --- 连接追踪逻辑 ---
                # 1. 如果是 SYN (S)，说明刚开始握手，记录但不拦截
                # 2. 我们选择在看到第一个 ACK (A) 且不是 SYN-ACK 时，
                #    或者在有数据传输 (PA) 时进行拦截，这确保了握手基本完成。
                
                if "S" in flags:
                    continue  # 跳过握手前两个阶段

                if conn_key in self.intercepted_conns:
                    continue  # 已经拦截过了，不再处理

                src_addr = ipaddress.ip_address(pkt_info['src_addr'])
                dst_addr = ipaddress.ip_address(pkt_info['dst_addr'])

                if src_addr in self.src_net and dst_addr in self.dst_net:
                    print(f"[Triggered] {pkt.summary()}")
                    
                    # 执行拦截
                    interception = interceptor.TCPInterceptor({
                        'src_addr': src_addr,
                        'dst_addr': dst_addr,
                        'src_port': pkt_info['tcp_details']['sport'],
                        'dst_port': pkt_info['tcp_details']['dport'],
                        'seq': pkt_info['tcp_details']['seq'],
                        'ack': pkt_info['tcp_details']['ack'],
                        'dst_mac': self.dst_mac,
                        'iface': self.iface
                    })
                    interception.intercept()
                    
                    # 标记该连接已处理
                    self.intercepted_conns.add(conn_key)

            except Exception as e:
                print(f"Error in detection: {e}")
                time.sleep(0.001)
                continue

    def run(self):
        self.stopFlag = False
        self.radar_thread = threading.Thread(target=self.detection, daemon=True)
        self.radar_thread.start()
        print('TCP radar stared')

    def stop(self):
        self.stopFlag = True
        self.radar_thread.join(5)
        print('TCP radar stopped')

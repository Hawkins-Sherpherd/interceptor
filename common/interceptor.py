import ipaddress
import threading
from scapy.all import *
from scapy.layers.inet import IP, TCP
from scapy.layers.l2 import Ether

class Interceptor:
    src_addr: ipaddress.ip_address
    dst_addr: ipaddress.ip_address
    src_port: int
    dst_port: int
    dst_mac: str
    iface: str
    proto: str

class TCPInterceptor(Interceptor):
    _socket_cache = {}  # 类级别的 socket 缓存
    _socket_lock = threading.Lock()
    def __init__(self, kwargs):
        super().__init__()
        self.src_addr = ipaddress.ip_address(kwargs['src_addr'])
        self.dst_addr = ipaddress.ip_address(kwargs['dst_addr'])
        self.src_port = kwargs['src_port']
        self.dst_port = kwargs['dst_port']
        self.seq = kwargs.get('seq', 0)
        self.ack = kwargs.get('ack', 0)
        self.dst_mac = kwargs.get('dst_mac', None)
        self.iface = kwargs.get('iface', None)
        self.proto = 'tcp'
        self.intercept_thread = None

    def _get_socket(self):
        """获取或创建 socket"""
        with self._socket_lock:
            if self.iface not in self._socket_cache:
                try:
                    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 
                                       socket.ntohs(0x0003))
                    sock.bind((self.iface, 0))
                    sock.setblocking(False)  # 设置非阻塞
                    self._socket_cache[self.iface] = sock
                except Exception as e:
                    print(f"Failed to create socket: {e}")
                    return None
            return self._socket_cache[self.iface]

    def intercept(self):
        # 创建 raw socket
        raw_socket = self._get_socket()
        if not raw_socket:
            return

        # 构造客户端方向的 RST 报文（从 src 到 dst）
        client_rst_pkt = Ether() / IP(src=str(self.src_addr), dst=str(self.dst_addr)) / TCP(
            sport=self.src_port,
            dport=self.dst_port,
            flags="R",  # RST 标志
            seq=self.seq,
            ack=self.ack
        )

        # 构造服务器方向的 RST 报文（从 dst 到 src）
        server_rst_pkt = Ether() / IP(src=str(self.dst_addr), dst=str(self.src_addr)) / TCP(
            sport=self.dst_port,
            dport=self.src_port,
            flags="R",  # RST 标志
            seq=self.ack,  # 使用对端的 ack 作为 seq
            ack=self.seq + 1  # 假设 RST 是对应于下一个序列号
        )

        # 如果提供了目标 MAC 地址，则设置 Ethernet 层
        if self.dst_mac:
            client_rst_pkt[Ether].dst = self.dst_mac
            server_rst_pkt[Ether].dst = self.dst_mac

        for pkt in [client_rst_pkt, server_rst_pkt]:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    raw_socket.send(bytes(pkt))
                    break
                except BlockingIOError:
                    if attempt < max_retries - 1:
                        time.sleep(0.001)
                    else:
                        print(f"Failed to send after {max_retries} retries")
                except Exception as e:
                    print(f"Send error: {e}")
                    break

    def run(self):
        self.intercept_thread = threading.Thread(target=self.intercept,daemon=True)
        self.intercept_thread.start()
        print('Interception engaged')
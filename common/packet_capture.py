from scapy.all import sniff
from common import ringbuffer
import threading

class PacketCapture:
    pkt_buffer = ringbuffer.RingBuffer(1024)

    def __init__(self,kwargs):
        self.sniff_if = kwargs['sniff_if']
        self.capture_thread = None
        self.stop_flag = False

    def packet_callback(self,packet):
        self.pkt_buffer.write(packet)

    def run_sniff(self):
        sniff(filter='ip or ip6', iface=self.sniff_if, prn=self.packet_callback, store=0, stop_filter=lambda x: self.stop_flag)

    def run(self):
        self.stop_flag = False
        self.capture_thread = threading.Thread(target=self.run_sniff, daemon=True)
        self.capture_thread.start()
        print('Capture started')

    def stop(self):
        self.stop_flag = True
        self.capture_thread.join(5)
        print('Capture stopped')
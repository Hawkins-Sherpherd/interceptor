from scapy.all import sniff

def packet_callback(packet):
    print(packet.summary())

sniff(iface='eth2', prn=packet_callback)
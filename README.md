# Interceptor - A side-channel traffic sniffer & interceptor
***Interceptor*** is a side-channel security appliance which is capable of:
- Packet Capture & Multithread Analysis
- Interest traffic interception through packet spoofing

Since it send packet through raw_socket, currently Linux is only platform capable running this.

## Implementation
The main working logic of ***Interceptor*** consists of two parts:
- Radar: The traffic analyzer
- Interceptor: The interception implementation

Every rule in rule set creates a Radar thread, every matched interest traffic invokes corresponding interception in Radar thread.

Currently, ***Interceptor*** has implemented:
- Radar
    - TCP Radar
        - Match
            - Source Network
            - Destination Network
- Interceptor
    - TCP Interceptor
        - Intercept TCP traffic through spoofing RST message

## Configuration
The deployment platform of ***Interceptor*** is recommended have 2 interfaces, one for sniffing, one for sending spoofed packet.

Theoretically, ***Interceptor*** can run with only one network interface, but I haven't tested.

Don't use default configuration in config.json, this is not ought to work outside my testbench.

Configuration of ***Interceptor*** is mainly stored in:
- config.json
    - sniff_if: The sniffing interface settings
        - ifname: The name of sniffing interface
    - egress_if: The settings of interface sending spoofed packet
        - ifname: The name of egress interface
        - dst_mac: Destination MAC address, the destination should be a gateway you will send packet to
- ruleset.json
    - The ruleset.json stored rules of matching interested traffic
    - Common field of rule:
        - proto: The protocol of rule, currently support:
            - tcp
    - Fields for proto:tcp
        - source: The source network of rule, should be a IPv4/IPv6 CIDR
        - destiantion: The destination network of rule, should be a IPv4/IPv6 CIDR

Inside common/packet_capture.py, the ring buffer pkt_buffer stores captured packet, its size can be modified. By default the size if 1024.
```
pkt_buffer = ringbuffer.RingBuffer(1024)
```

## How to run
- Create your own virtual environment
- Switch to it
- Install dependencies
```
pip install -r requirements.txt
```
- Run interceptord.py
```
python3 interceptord.py
```

## TO-DO List
- Add destination port match for TCP Radar
- Add DNS Radar
- Add HTTP Radar
- Add DNS Interceptor
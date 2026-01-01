from common import config
from common import ruleset
from common import packet_capture
from common import radar
import time

configuration = config.Config('config.json')
rule_set = ruleset.RuleSet('ruleset.json').rule_set
radars = []

if __name__ == '__main__':
    capture = packet_capture.PacketCapture({'sniff_if':configuration.sniff_if})
    capture.run()
    for rule in rule_set:
        if rule.proto == 'tcp':
            radars.append(radar.TCPRadar({'buffer':capture.pkt_buffer,'src':rule.src,'dst':rule.dst,'iface':configuration.egress_if,'dst_mac':configuration.dst_mac}))
            radars[-1].run()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('Terminating......')
        for radar_instance in radars:
            radar_instance.stop()
        capture.stop()
        print("Terminated")
        exit(0)
    finally:
        exit(0)
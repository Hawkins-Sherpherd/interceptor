from common import load

class Config:
    egress_if:str
    sniff_if:str
    dst_mac:str
    raw_config:dict

    def __init__(self,path:str):
        self.raw_config = load.load(path)
        self.egress_if = self.raw_config['egress_if']['ifname']
        self.sniff_if = self.raw_config['sniff_if']['ifname']
        self.dst_mac = self.raw_config['egress_if']['dst_mac']
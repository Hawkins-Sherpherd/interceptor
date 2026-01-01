from common import load

class Rule:
    src:str
    dst:str
    proto:str

    def __init__(self,rule:dict):
        self.src = rule['source']
        self.dst = rule['destination']
        self.proto = rule['proto']

class RuleSet:
    raw_config:dict
    rule_set:tuple

    def __init__(self,path:str):
        self.raw_config = load.load(path)
        self.rule_set = tuple(Rule(i) for i in self.raw_config['ruleset'])
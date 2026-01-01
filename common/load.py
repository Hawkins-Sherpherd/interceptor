import json

def load(path:str):
    try:
        with open(path,'r',encoding='utf-8') as fp:
            return json.load(fp)
    except FileNotFoundError as e:
        return str(e)
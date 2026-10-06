import copy
from idea_parallax.cli import DEFAULT_CONFIG
from idea_parallax.demo import demo_output

def config():
    c = copy.deepcopy(DEFAULT_CONFIG)
    c['provider'] = {'type': 'demo'}
    c['reviewer'] = {'type': 'demo'}
    c['retries'] = 0
    return c

def brief():
    return {'topic': '如何检索缺失证据？', 'language': 'zh-CN', 'constraints': ['仅公开数据']}

def batch():
    return demo_output('generate', {'strategy_id': 'orchestra', 'brief': brief()})

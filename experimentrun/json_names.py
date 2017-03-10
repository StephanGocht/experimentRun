class JsonName(object):
    def __init__(self, text, description):
        self.text = text
        self.description = description


expload = JsonName(
    r"%expload",
    r'This is used to indicate you want to have on entry of the given list'
    r'in each configuration file.'
    r'Usage: "YourProperty": {"%expload":["data", "to", "expload"]}')

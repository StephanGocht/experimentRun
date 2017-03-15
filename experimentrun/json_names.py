class JsonName(object):
    def __init__(self, text, description):
        self.text = text
        self.description = description


explode = JsonName(
    r"%explode",
    r'This is used to indicate you want to have on entry of the given list'
    r'in each configuration file.'
    r'Usage: "YourProperty": {"%expload":["data", "to", "expload"]}')

limitsConfig = JsonName(
    r"/%limits",
    r'This is used to limit commands executed with the RunShell tool.'
    r'Usage: "%limits":{"RLIMIT_CPU":[5,6]}')

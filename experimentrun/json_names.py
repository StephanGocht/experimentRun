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

evaluate = JsonName(
    r"%eval",
    r'This is used to indicate you want to eval a python expression'
    r'Usage: "YourProperty": {"%eval":"list(range(3))"}')

link = JsonName(
    r"%link",
    r'This is used to indicate you want the value of another place in the json'
    r'Usage: "YourProperty": {"%link":"/path/to/value"}')

linkFile = JsonName(
    r"%linkFile",
    r'This is used to indicate you want the json of another file in here.'
    r'Usage: "YourProperty": {"%linkFile":"/os/path/to/value"}')

exrunConfDir = JsonName(
    r"EXRUN_CONF_DIR",
    r"""This is a value in the json that is supposed to be set by bootstrapping
        process and is used as a string replacement to get the directory of the
        initial configuration file.
        Usage: "YourProperty":"some text of yours ${/EXRUN_CONF_DIR}"
    """)

import sys
import os

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))
from experimentrun.tools import Tool


class LoadFile(Tool):
    def __init__(self, regex, names):
        super(LoadFile, self).__init__()
        print("Loaded LoadFile: %s %s" % (regex, names))


class MultiAndNamedArgs(Tool):
    def __init__(self, name, value=0, priority=0):
        super(MultiAndNamedArgs, self).__init__()
        print("Loaded LoadFile: %s, %d, %d" % (name, value, priority))

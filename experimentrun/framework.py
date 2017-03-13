import re
import sys
import ast
from pydoc import locate

from . import tools


class Metadata(object):
    def __init__(self, config):
        self.config = config
        self.registration = list()

    def runAll(self):
        for tool in self.registration:
            tool.run()

    def loadAndAddTool(self, classString):
        match = re.match(r"([^\(\{]*)(([\{\(])(.*)[\)\}])?\s*$", classString)

        if (match):
            className = match.group(1)
            parameterType = match.group(3)
            parameterString = match.group(4)

            userClass = locate(className)
            instance = None
            if (userClass is None):
                sys.exit("Failed to load class %s (value: %s)."
                         % (className, classString))

            if not issubclass(userClass, tools.Tool):
                sys.exit("Failed to load class %s: Not inherited from "
                         "compbench.tools.Tool."
                         % (className))

            if parameterType == '(':
                if not parameterString or parameterString.isspace():
                    instance = userClass()
                else:
                    print("dbg: parameter >", parameterString, "<")
                    parameterString = '({},)'.format(parameterString)
                    parameter = ast.literal_eval(parameterString)
                    instance = userClass(*parameter)
            elif parameterType == '{':
                parameterString = '{%s}' % (parameterString)
                parameter = ast.literal_eval(parameterString)
                instance = userClass(**parameter)

            instance.setup(self)
        else:
            sys.exit("Failed parse class (value: %s)." % (classString))


def bootstrap(config):
    metadata = Metadata(config)
    for classString in config.get("tools", list()):
        metadata.loadAndAddTool(classString)
    metadata.runAll()

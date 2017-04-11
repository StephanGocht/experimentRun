import re
import sys
import ast
import json
from enum import Enum
from pydoc import locate

from . import tools
from . import json_names


def removeComments(text):
    """Remove lines starting with //"""
    return re.sub(r"(^|\n)\s*//[^\n]*", "\n", text)


def loadJson(jsonPath):
    with open(jsonPath, 'r') as jsonFile:
        text = removeComments(jsonFile.read())
        try:
            config = json.loads(text)
        except json.JSONDecodeError as e:
            sys.exit("Error in json file %s:%d:%d: %s"
                     % (jsonPath, e.lineno, e.colno, e.msg))
    return config


class Metadata(object):
    def __init__(self, config, imports="experimentrun.tools"):
        self.config = config
        self.registration = list()

    def runAll(self):
        for tool in self.registration:
            tool.run()

    def loadAndAddTool(self, className, parameter):
        klass = locate(className)
        instance = None
        if (klass is None):
            sys.exit("Failed to load class %s."
                     % (className))

        if not issubclass(klass, tools.Tool):
            sys.exit("Failed to load class %s: Not inherited from "
                     "compbench.tools.Tool."
                     % (klass.__name__))

        if parameter is None:
            instance = klass()
        elif isinstance(parameter, tuple):
            instance = klass(*parameter)
        elif isinstance(parameter, dict):
            instance = klass(**parameter)
        else:
            raise TypeError(
                "For parameter 'parameter': Expected %s or %s but got %s" %
                (tuple.__name__, dict.__name__, parameter.__class__.__name__))

        instance.setup(self)

    def loadAndAddToolFromString(self, classString):
        match = re.match(r"([^\(\{]*)(([\{\(])(.*)[\)\}])?\s*$", classString)

        if (match):
            className = match.group(1)
            parameterType = match.group(3)
            parameterString = match.group(4)

            if parameterType == '(':
                if not parameterString or parameterString.isspace():
                    parameter = None
                else:
                    parameterString = '({},)'.format(parameterString)
                    parameter = ast.literal_eval(parameterString)
            elif parameterType == '{':
                parameterString = '{%s}' % (parameterString)
                parameter = ast.literal_eval(parameterString)

            self.loadAndAddTool(className, parameter)
        else:
            sys.exit("Failed parse class (value: %s)." % (classString))


def bootstrap(config):
    metadata = Metadata(config)
    for constructor in config.get("tools", list()):
        if isinstance(constructor, str):
            metadata.loadAndAddToolFromString(constructor)
        else:
            metadata.loadAndAddTool(
                constructor["name"],
                constructor["parameters"])

    metadata.runAll()
    return metadata.config


class ExploadState(Enum):
    normal = 1
    exploaded = 2


def _createExploadedCopies(exploadedSubEntries, config):
    result = list()
    result.append(config)
    for key, valueList in exploadedSubEntries:
        exploadedResult = list()
        for value in valueList:
            for config in result:
                copy = config.copy()
                copy[key] = value
                exploadedResult.append(copy)

        result = exploadedResult

    return result


def _explodeConfig(config, explodeString):
    exploadedSubEntries = list()

    if isinstance(config, dict):
        for key, value in config.items():
            if key == explodeString:
                if type(value) is not list:
                    sys.exit(
                        "Tried to expload value but no list was provided."
                        "Got '%s' instead" % value)
                else:
                    variants = list()
                    for entry in value:
                        state, subConfig = _explodeConfig(entry, explodeString)
                        if (state == ExploadState.exploaded):
                            variants.extend(subConfig)
                        else:
                            variants.append(subConfig)
                    return (ExploadState.exploaded, variants)

            else:
                state, subConfig = _explodeConfig(value, explodeString)
                if (state == ExploadState.exploaded):
                    exploadedSubEntries.append((key, subConfig))

    elif isinstance(config, list):
        for idx, value in enumerate(config):
            state, subConfig = _explodeConfig(value, explodeString)
            if (state == ExploadState.exploaded):
                exploadedSubEntries.append((idx, subConfig))

    if len(exploadedSubEntries) == 0:
        return (ExploadState.normal, config)
    else:
        exploaded = _createExploadedCopies(exploadedSubEntries, config)
        return (ExploadState.exploaded, exploaded)


def explodeConfig(config, explodeString=json_names.explode.text):
    state, confs = _explodeConfig(config, explodeString)
    if (state == ExploadState.normal):
        confs = list([confs])

    return confs

import re
import sys
import ast
import json
import logging
import inspect
import os
from enum import Enum
from pydoc import locate
from copy import deepcopy
from copy import copy

from . import tools
from . import json_names

includes = list()


def exrun(file, toIncludes):
    global includes
    includes.append(os.path.dirname(file))
    for include in toIncludes:
        includes.append(os.path.abspath(include))

    sys.path.extend(includes)
    config = loadJson(file)

    bootstrap(config, str(os.path.dirname(file)))


def removeComments(text):
    """Remove lines starting with //"""
    return re.sub(r"(^|\n)(\s*)//[^\n]*", "\g<1>\g<2>", text)

def removeTrailingComma(text):
    """Remove comma at end of line if it is the last item"""
    return re.sub(r",(\s*\n\s*)([\]}])", "\g<1>\g<2>", text)


def loadJson(jsonPath):
    with open(jsonPath, 'r') as jsonFile:
        text = removeComments(jsonFile.read())
        text = removeTrailingComma(text)
        try:
            config = json.loads(text)
        except json.JSONDecodeError as e:
            sys.exit("Error in json file %s:%d:%d: %s"
                     % (jsonPath, e.lineno, e.colno, e.msg))
    return config


class Metadata(object):
    def __init__(self, config=dict(), imports="experimentrun.tools"):
        self.config = config
        self.registration = list()
        self.exceptionHandler = list()
        self.context = tools.Tool()
        self.context.setup(self)

    def loadAndRunTool(self, className, parameter):
        klass = locate(className)
        instance = None
        if (klass is None):
            logging.debug("sys.path = " + str(sys.path))
            sys.exit("Failed to load %s."
                     % (className))

        if not inspect.isclass(klass):
            if callable(klass):
                try:
                    if parameter is None:
                        klass(self.context)
                    elif isinstance(parameter, tuple):
                        klass(self.context,*parameter)
                    elif isinstance(parameter, dict):
                        klass(self.context,**parameter)
                    else:
                        raise TypeError(
                            "For parameter 'parameter': Expected %s or %s but got %s" %
                            (tuple.__name__, dict.__name__, parameter.__class__.__name__))
                except Exception as e:
                    handled = False
                    for handler in self.exceptionHandler:
                        handled |= handler.handleExceptionOnRun(e)
                        if handled:
                            break

                    if not handled:
                        raise
            else:
                sys.exit("Failed to load %s: Neither a class nor callable."
                         % (klass.__name__))
        else:
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

            try:
                instance.setup(self)
                instance.run()
            except Exception as e:
                handled = False
                for handler in self.exceptionHandler:
                    handled |= handler.handleExceptionOnRun(e)
                    if handled:
                        break

                if not handled:
                    raise

    def loadAndRunToolFromString(self, classString):
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
                    try:
                        parameter = ast.literal_eval(parameterString)
                    except ValueError as e:
                        logging.error("Malformed parameter string, the following should be valid python code: %s"%parameterString )
                        raise e
            elif parameterType == '{':
                parameterString = '{%s}' % (parameterString)
                try:
                    parameter = ast.literal_eval(parameterString)
                except ValueError as e:
                    logging.error("Malformed parameter string, the following should be valid python code: %s"%parameterString )


            self.loadAndRunTool(className, parameter)
        else:
            sys.exit("Failed parse class (value: %s)." % (classString))

    def runConstructorList(self, constructorList):
        while (len(constructorList) > 0):
            constructor = constructorList.pop(0)

            if isinstance(constructor, list):
                self.runConstructorList(constructor)
            elif constructor is not None:
                logging.debug('Load and running tool: %s', constructor)
                if isinstance(constructor, str):
                    self.loadAndRunToolFromString(constructor)
                else:
                    self.loadAndRunTool(
                        constructor["name"],
                        constructor["parameters"])

    def runAllTools(self):
        self.runConstructorList(self.config.get("tools", list()))


def bootstrap(config, configPath):
    config[json_names.exrunConfDir.text] = configPath

    metadata = Metadata(config)
    try:
        metadata.runAllTools()
    except Exception as e:
        handled = False
        for handler in metadata.exceptionHandler:
            handled |= handler.handleExceptionOnRunAll(e)
            if handled:
                break

        if not handled:
            raise
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
                cop = copy(config)
                cop[key] = value
                exploadedResult.append(cop)
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

    return [deepcopy(conf) for conf in confs]

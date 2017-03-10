import json
import sys
from enum import Enum

from . import json_names
from . import framework


class Tool(object):
    def __init__(self, priority=0):
        self.priority = priority

    def setup(self, metadata):
        print("Registered new Tool: %s" % (self.__class__.__name__))
        metadata.registration.append(self)
        self.config = metadata.config

    def run(self):
        pass


class PrintCurrentJson(Tool):
    def __init__(self):
        super(PrintCurrentJson, self).__init__(self)

    def run(self):
        print(json.dumps(self.config, indent=4))


def mergeConfig(default, additional):
    result = default.copy()
    for key, value in additional.items():
        if type(value) is list and type(result[key]) is list:
            result[key].extend(value)
        else:
            result[key] = value
    return result


class ExploadState(Enum):
    normal = 1
    exploaded = 2


def createExploadedCopies(exploadedSubEntries, config):
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

    print(result)
    return result


def exploadConfig(config):
    if type(config) is dict:
        exploadedSubEntries = list()

        for key, value in config.items():
            if key == json_names.expload.text:
                if type(value) is not list:
                    sys.exit(
                        "Tried to expload value but no list was provided."
                        "Got '%s' instead" % value)
                else:
                    return (ExploadState.exploaded, value)

            else:
                state, subConfig = exploadConfig(value)
                if (state == ExploadState.exploaded):
                    exploadedSubEntries.append((key, subConfig))

        if len(exploadedSubEntries) == 0:
            return (ExploadState.normal, config)
        else:
            print(exploadedSubEntries)
            exploaded = createExploadedCopies(exploadedSubEntries, config)
            return (ExploadState.exploaded, exploaded)

    elif type(config) is list:
        pass

    return (ExploadState.normal, config)


class ExploadNBootstrap(Tool):
    def __init__(self):
        super(ExploadNBootstrap, self).__init__(self)

    def run(self):
        for config in self.config["configurations"]:
            config = mergeConfig(
                self.config["default_configuration"], config)
            _, confs = exploadConfig(config)
            for conf in confs:
                framework.bootstrap(conf)


class SearchFilesNames(Tool):
    def __init__(self):
        pass

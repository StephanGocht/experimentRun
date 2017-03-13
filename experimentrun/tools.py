import json
import sys
import subprocess
import psutil
import time
import resource

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

    def substitute(self, text):
        """Substitute text with data from the json file."""
        # TODO
        return text

    def access(self, accessorString, createMissing=False):
        """Gets data from json using a dotted accessor-string.
           Array access not jey supported"""
        current_data = self.config
        for chunk in accessorString.split('.'):
            if createMissing and chunk not in current_data:
                current_data[chunk] = dict()
            current_data = current_data[chunk]
        return current_data

    def run(self):
        pass


class PrintCurrentJson(Tool):
    def __init__(self):
        super(PrintCurrentJson, self).__init__(self)

    def run(self):
        print(json.dumps(self.config, indent=4))


def mergeConfig(default, additional):
    if (default is None):
        return additional
    else:
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
        for config in self.config.get("configurations", list()):
            config = mergeConfig(
                self.config.get("default_configuration", None), config)
            state, confs = exploadConfig(config)
            if (state == ExploadState.normal):
                confs = list([confs])
            for conf in confs:
                framework.bootstrap(conf)


class RunShell(Tool):
    def __init__(self, command, timeResult=None,
                 limitsConfig=json_names.limitsConfig.text):
        self.command = command
        self.limitsConfig = limitsConfig
        self.timeResult = timeResult

    def setLimits(self):
        try:
            limits = self.access(self.limitsConfig)
        except KeyError:
            limits = None

        if limits is not None:
            for key, value in limits.items():
                if key.startswith("RLIMIT_"):
                    try:
                        resource.setrlimit(getattr(resource, key), value)
                    except AttributeError:
                        print(
                            "Warning: Invalid resource limit",
                            key, "will be ignored.")

        p = psutil.Process()
        p.cpu_affinity([1])

    def run(self):
        startTime = time.perf_counter()
        startInfo = resource.getrusage(resource.RUSAGE_CHILDREN)

        process = subprocess.Popen(
            self.substitute(self.command),
            shell=True,
            preexec_fn=self.setLimits,
            executable='/bin/bash')

        try:
            timeout = self.access(self.limitsConfig)["timeout"]
            try:
                process.wait(timeout)
            except subprocess.TimeoutExpired:
                process.kill()
        except KeyError:
            process.wait()

        info = resource.getrusage(resource.RUSAGE_CHILDREN)

        if (self.timeResult is not None):
            timeData = self.access(self.timeResult, createMissing=True)
            timeData["userTime"] = info.ru_utime - startInfo.ru_utime
            timeData["systemTime"] = info.ru_stime - startInfo.ru_stime
            timeData["wallClockTime"] = time.perf_counter() - startTime


class SearchFilesNames(Tool):
    def __init__(self):
        pass

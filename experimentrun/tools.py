import json
import subprocess
import psutil
import time
import resource

import tempfile
import os
import re

import jsonpointer

from multiprocessing import Pool

from . import json_names
from . import framework


class Tool(object):
    def __init__(self):
        super().__init__()

    def registerSubTool(self, subtool):
        if not hasattr(self, '_subtools'):
            self._subtools = list()

        self._subtools.append(subtool)
        return subtool

    def setup(self, metadata, register=True):
        # print("Registered new Tool: %s" % (self.__class__.__name__))
        if register:
            metadata.registration.append(self)
        self.metadata = metadata

        if hasattr(self, '_subtools'):
            for tool in self._subtools:
                tool.setup(metadata, False)

    @property
    def config(self):
        return self.metadata.config

    @config.setter
    def config(self, config):
        self.metadata.config = config

    def substitute(self, text):
        """Substitute text with data from the json file."""
        pattern = re.compile(r"(.*)\${([^{}]*)}(.*)")
        while True:
            match = pattern.match(text)
            if (match):
                replacement = self.access(match.group(2))
                text = match.group(1) + replacement + match.group(3)
            else:
                break
        return text

    def access(self, accessorString, createMissing=False):
        """Gets data from json using a jsonpointer.
           Array and Array element creation is not jey supported"""
        pointer = jsonpointer.JsonPointer(accessorString)
        if not createMissing:
            try:
                return pointer.resolve(self.config)
            except:
                raise KeyError(
                    "Tried to access '%s' in json file."
                    % (accessorString))
        else:
            doc = self.config
            for part in pointer.parts:
                try:
                    doc = pointer.walk(doc, part)
                except jsonpointer.JsonPointerException:
                    doc[part] = dict()
                    doc = doc[part]
            return doc

    def run(self):
        pass


class PrintExplodedJsons(Tool):
    def __init__(self):
        super().__init__()

    def run(self):
        print(json.dumps(framework.explodeConfig(self.config), indent=4))


class PrintCurrentJson(Tool):
    def __init__(self):
        super().__init__()

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


class ExploadNBootstrap(Tool):
    def __init__(self):
        super().__init__()

    def run(self):
        # TODO use multiproecssing.Pool.map to parallelize
        # for cluster parallelism use http://stackoverflow.com/questions/5181949/using-the-multiprocessing-module-for-cluster-computing
        # p = psutil.Process()
        # p.cpu_affinity([1])

        for config in self.config.get("configurations", list()):
            config = mergeConfig(
                self.config.get("default_configuration", None), config)

            runResults = list()

            confs = framework.explodeConfig(config)
            cwd = os.getcwd()
            for conf in confs:
                os.chdir(cwd)
                runResults.append(framework.bootstrap(conf))

            self.config["runResults"] = runResults


class RunShell(Tool):
    def __init__(self, command, timesTo=None,
                 limitsConfig=json_names.limitsConfig.text,
                 externalUsedConfig=None):
        super().__init__()
        self.command = command
        self.limitsConfigPath = limitsConfig
        self.timesTo = timesTo

        if externalUsedConfig is not None:
            self.wrtieConfig = self.registerSubTool(
                WriteConfigToFile(externalUsedConfig))
            self.readConfig = self.registerSubTool(
                ReplaceConfigFromFile(externalUsedConfig))
        else:
            # do nothing, when called
            self.wrtieConfig = Tool()
            self.readConfig = Tool()

    def loadLimits(self):
        try:
            limitsConfig = self.access(self.limitsConfigPath)
        except KeyError:
            limitsConfig = None

        self.limits = list()
        if limitsConfig is not None:
            for key, value in limitsConfig.items():
                if key.startswith("RLIMIT_"):
                    self.limits.append((key, value))

    def setLimits(self):
        for key, value in self.limits:
            try:
                resource.setrlimit(getattr(resource, key), value)
            except AttributeError:
                print(
                    "Warning: Invalid resource limit",
                    key, "will be ignored.")

    def run(self):
        self.wrtieConfig.run()
        self.loadLimits()

        startTime = time.perf_counter()
        startInfo = resource.getrusage(resource.RUSAGE_CHILDREN)

        process = subprocess.Popen(
            self.substitute(self.command),
            shell=True,
            preexec_fn=self.setLimits,
            executable='/bin/bash')

        try:
            timeout = self.access(self.limitsConfigPath)["timeout"]
            try:
                process.wait(timeout)
            except subprocess.TimeoutExpired:
                process.kill()
        except KeyError:
            process.wait()

        info = resource.getrusage(resource.RUSAGE_CHILDREN)

        self.readConfig.run()

        if (self.timesTo is not None):
            timeData = self.access(self.timesTo, createMissing=True)
            timeData["userTime"] = info.ru_utime - startInfo.ru_utime
            timeData["systemTime"] = info.ru_stime - startInfo.ru_stime
            timeData["wallClockTime"] = time.perf_counter() - startTime


class WriteConfigToFile(Tool):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def run(self):
        with open(self.filename, 'w') as jsonFile:
            json.dump(self.config, jsonFile, indent=4)


class ReplaceConfigFromFile(Tool):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def run(self):
        self.config = framework.loadJson(self.filename)


class MakeAndCdTempDir(Tool):
    def __init__(self, prefix="", hasRandomPart=True):
        super().__init__()
        self.prefix = prefix
        self.hasRandomPart = hasRandomPart

    def run(self):
        if self.hasRandomPart:
            path = tempfile.mkdtemp(prefix=self.prefix, dir="./")
        else:
            if not os.path.exists(self.prefix):
                os.makedirs(self.prefix)
            path = self.prefix
        print("changed directory to", path)
        os.chdir(path)


class SearchFilesNames(Tool):
    def __init__(self):
        super().__init__()

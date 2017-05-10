import json
import subprocess
import psutil
import time
import resource
import logging

import tempfile
import os
import re

import jsonpointer

import multiprocessing

from copy import deepcopy

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

    def setup(self, metadata):
        # print("Registered new Tool: %s" % (self.__class__.__name__))
        self.metadata = metadata

        if hasattr(self, '_subtools'):
            for tool in self._subtools:
                tool.setup(metadata)

    @property
    def config(self):
        return self.metadata.config

    @config.setter
    def config(self, config):
        self.metadata.config = config

    def substitute(self, text):
        """Substitute text with data from the json file."""
        pattern = re.compile(r"(.*)(\$|%){([^{}]*)}(.*)")
        while True:
            match = pattern.match(text)
            if (match):
                if match.group(2) == "$":
                    replacement = str(self.access(match.group(3)))
                elif match.group(2) == "%":
                    replacement = str(eval(match.group(3)))
                text = match.group(1) + replacement + match.group(4)
            else:
                break
        return text

    def setValue(self, accessorString, value):
        pointer = jsonpointer.JsonPointer(accessorString)
        doc = self.config
        parts = pointer.parts
        for part in parts[:-1]:
            try:
                doc = pointer.walk(doc, part)
            except jsonpointer.JsonPointerException:
                doc[part] = dict()
                doc = doc[part]
        doc[parts[-1]] = value

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


class Eval(Tool):
    def __init__(self, basePtr=""):
        super().__init__()
        self.basePtr = basePtr

    def evaluate(self, data):
        if isinstance(data, dict):
            if json_names.evaluate.text in data:
                return eval(self.substitute(data[json_names.evaluate.text]))
            else:
                for key, value in data.items():
                    result = self.evaluate(value)
                    if result is not None:
                        data[key] = result

        elif isinstance(data, list):
            for idx, value in enumerate(data):
                result = self.evaluate(value)
                if result is not None:
                    data[idx] = result

        return None

    def run(self):
        self.evaluate(self.access(self.basePtr))


class ResolveLinks(Tool):
    def __init__(self, basePtr=""):
        super().__init__()
        self.basePtr = basePtr

    def recurse(self, data):
        if isinstance(data, dict):
            key = json_names.link.text
            if key in data:
                try:
                    refData = deepcopy(self.access(self.substitute(data[key])))
                    _, result = self.recurse(refData)
                    return (True, result)
                except KeyError:
                    return (True, None)
            else:
                for key, value in data.items():
                    replaced, result = self.recurse(value)
                    if replaced:
                        data[key] = result

        elif isinstance(data, list):
            for idx, value in enumerate(data):
                replaced, result = self.recurse(value)
                if replaced:
                    data[idx] = result

        return (False, data)

    def run(self):
        self.recurse(self.access(self.basePtr))


class ExplodeNBootstrap(Tool):
    processor = None

    def __init__(self, settings=None, parallel=False, processors=None):
        super().__init__()
        self.settings = settings
        self.parallel = parallel
        self.processors = processors
        print("Use Processors: ", self.processors)

    def initialize(processors):
        if processors is not None:
            processorId = processors.get()
            process = psutil.Process()
            process.cpu_affinity([processorId])
            print("initialized process")

    def doWork(config, cwd):
        os.chdir(cwd)
        return framework.bootstrap(config)

    def run(self):
        if self.settings is not None:
            setting = self.access(self.settings)
            self.parallel = setting.get("parallel", None)
            self.processors = setting.get("processors", None)

        if self.config.get("configurations", list()) is not list:
            logging.critical(
                "The entrie for \"configurations\" should be a list, "
                "i.e. use [{..},{..},..].")

        runResults = list()
        for config in self.config.get("configurations", list()):
            config = mergeConfig(
                self.config.get("default_configuration", None), config)

            confs = framework.explodeConfig(config)
            cwd = os.getcwd()

            if not self.parallel:
                runResults.extend([
                    ExplodeNBootstrap.doWork(conf, cwd)
                    for conf in confs])
            else:

                if self.processors is None:
                    queue = None
                    numProcessors = None  # use default i.e. num procs
                else:
                    numProcessors = len(self.processors)
                    manager = multiprocessing.Manager()
                    queue = manager.Queue()
                    for i in self.processors:
                        queue.put(i)

                # for cluster parallelism use http://stackoverflow.com/questions/5181949/using-the-multiprocessing-module-for-cluster-computing
                p = multiprocessing.Pool(
                    processes=numProcessors,
                    initializer=ExplodeNBootstrap.initialize,
                    initargs=(queue,))
                runResults.extend(p.starmap(
                    ExplodeNBootstrap.doWork,
                    [(conf, cwd) for conf in confs]))

        self.config["runResults"] = runResults


class RunShell(Tool):
    def __init__(self, command, runInfoTo=None,
                 limitsConfig=json_names.limitsConfig.text,
                 externalUsedConfig=None):
        super().__init__()
        self.command = command
        self.limitsConfigPath = limitsConfig
        self.runInfoTo = runInfoTo

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

        commandString = self.substitute(self.command)
        logging.info('RunShell: %s', commandString)
        process = subprocess.Popen(
            commandString,
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

        if (self.runInfoTo is not None):
            timeData = self.access(self.runInfoTo, createMissing=True)
            timeData["userTime"] = info.ru_utime - startInfo.ru_utime
            timeData["systemTime"] = info.ru_stime - startInfo.ru_stime
            timeData["wallClockTime"] = time.perf_counter() - startTime
            timeData["returnCode"] = process.returncode


class WriteConfigToFile(Tool):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def run(self):
        self.filename = self.substitute(self.filename)
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
        os.chdir(path)
        self.config["path"] = path


class SearchFilesNames(Tool):
    def __init__(self):
        super().__init__()

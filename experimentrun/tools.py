import json
import subprocess
import psutil
import time
import resource
import logging
import traceback

import tempfile
import os
import re

import jsonpointer

import multiprocessing
import Pyro4
import threading

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

    def deleteEntry(self, accessorString):
        pointer = jsonpointer.JsonPointer(accessorString)
        doc = self.config
        parts = pointer.parts
        for part in parts[:-1]:
            try:
                doc = pointer.walk(doc, part)
            except jsonpointer.JsonPointerException:
                doc[part] = dict()
                doc = doc[part]
        del doc[parts[-1]]

    def getValue(self, accessorString, createMissing=False):
        return self.access(accessorString, createMissing)

    def access(self, accessorString, createMissing=False):
        """Gets data from json using a jsonpointer.
           Array and Array element creation is not jey supported"""
        if isinstance(accessorString, jsonpointer.JsonPointer):
            pointer = accessorString
        else:
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


class ExceptionHandler(Tool):
    def __init__(self):
        super().__init__()

    def run(self):
        self.metadata.exceptionHandler.append(self)

    def handleExceptionOnRun(self, e):
        """Overwrite this method to try to handle the exception e, which
           canceled the execution of a single tool.
           Returns True if the exception was handled and should not be
           reraised, this causes later tools to go on normally"""
        return False

    def handleExceptionOnRunAll(self, e):
        """Overwrite this method to try to handle the exception e, which
           canceled the execution of following tools.
           Returns True if the exception was handled and should not be
           reraised."""
        return False


class ExceptionToConfigAndCancelToolExecution(ExceptionHandler):
    def __init__(self, filename=None):
        """ If filename is provided the config will be written to the specified
        file.
        """
        super().__init__()
        self.filename = filename

    def handleExceptionOnRunAll(self, e):
        logging.info("Cought exception %s: %s"% (type(e).__name__, str(e)))
        logging.debug(traceback.format_exc())
        info = dict()
        info["name"] = type(e).__name__
        info["message"] = str(e)
        info["trace"] = traceback.format_exc()
        self.config["exception"] = info

        if self.filename is not None:
            self.filename = self.substitute(self.filename)
            with open(self.filename, 'w') as jsonFile:
                json.dump(self.config, jsonFile, indent=4)

        return True


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


class LoopInLinksException(Exception):
    pass


class ResolveLinks(Tool):
    def __init__(self, basePtr=""):
        super().__init__()
        self.basePtr = basePtr

    def isLink(self, data, key):
        if isinstance(data[key], dict):
            linkText = json_names.link.text
            if linkText in data[key]:
                return True
        return False

    def isLinkFile(self, data, key):
        if isinstance(data[key], dict):
            linkText = json_names.linkFile.text
            if linkText in data[key]:
                return True
        return False

    def resolveLink(self, data, key):
        if "visited" in data[key]:
            raise LoopInLinksException()
        else:
            data[key]["vistied"] = True

        linkText = json_names.link.text
        path = data[key][linkText]

        pointer = jsonpointer.JsonPointer(self.substitute(path))
        current = self.config
        parts = pointer.parts
        try:
            for part in parts:
                part = pointer.get_part(current, part)
                if self.isLink(current, part):
                    self.resolveLink(current, part)
                current = current[part]

            self.search(current)
            data[key] = current
        except (KeyError, TypeError):
            if "default" in data[key]:
                data[key] = data[key]["default"]
            else:
                raise KeyError(path)

    def loadData(self, data, key):
        linkText = json_names.linkFile.text
        file = self.substitute(data[key][linkText])
        data[key] = framework.loadJson(file)
        self.search(data[key])

    def handleKey(self, data, key):
        if self.isLink(data, key):
            self.resolveLink(data, key)
        elif self.isLinkFile(data, key):
            self.loadData(data, key)
        else:
            self.search(data[key])

    def search(self, data):
        if isinstance(data, dict):
            for key, value in data.items():
                self.handleKey(data, key)

        elif isinstance(data, list):
            for idx, value in enumerate(data):
                self.handleKey(data, idx)
        else:
            # constant term nothing to be done here
            pass

    def run(self):
        ptr = jsonpointer.JsonPointer(self.basePtr)
        if len(ptr.parts) > 0:
            last = ptr.parts.pop()
            self.handleKey(self.access(ptr), last)
        else:
            self.search(self.access(ptr))


class ClusterDispatcher(object):
    def __init__(self, resultStorage):
        self.resultStorage = resultStorage
        self.storageLock = threading.Lock()

        logging.getLogger("Pyro4").setLevel(logging.WARN)
        logging.getLogger("Pyro4.core").setLevel(logging.WARN)
        ns = Pyro4.locateNS()
        self.aviableDispatchers = set()
        self.freeDispatchers = list()

        lookup = ns.list(metadata_all={"jobdispatcher"})
        for uri in lookup.values():
            proxy = Pyro4.Proxy(uri)
            Pyro4.async(proxy)
            proxy.setIncludes(framework.includes)
            self.aviableDispatchers.add(proxy)
            self.freeDispatchers.append(proxy)

        self.cv = threading.Condition()

    def release(self, result, dispatcher):
        with self.cv:
            self.freeDispatchers.append(dispatcher)
            self.cv.notify()
        return result

    def store(self, result):
        with self.storageLock:
            self.resultStorage.append(result)

    def handleException(self, exception, config, cwd, dispatcher):
        logging.error("Got Remote Exception: " + str(exception))

        # todo: this might be improved, i.e. look for aviable servers
        # now and then
        # make sure that the program knows when to terminate
        self.aviableDispatchers.remove(dispatcher)

        # reshedule
        self.run(config, cwd)

    def run(self, config, cwd):
        with self.cv:
            while len(self.freeDispatchers) == 0:
                self.cv.wait()
            dispatcher = self.freeDispatchers.pop()
        dispatcher.run(config, cwd) \
            .then(self.store) \
            .then(self.release, dispatcher) \
            .iferror(
                (lambda config, cwd, dispatcher:
                 lambda x: self.handleException(x, config, cwd, dispatcher)
                )(config, cwd, dispatcher)
            )

    def wait(self):
        with self.cv:
            while len(self.freeDispatchers) != len(self.aviableDispatchers):
                self.cv.wait()

class ExplodeNBootstrap(Tool):
    processor = None

    def __init__(self, parallel=False, processors=None,
                 cluster=False):
        super().__init__()
        self.parallel = parallel
        self.processors = processors
        self.cluster = cluster

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
        logging.info("Using processors %s." % (str(self.processors)))

        configurations = self.config.get("configurations", list())
        if not isinstance(configurations, list):
            logging.critical(
                "The entrie for \"configurations\" should be a list, "
                "i.e. use [{..},{..},..]. Got %s" % (type(configurations)))
            raise RuntimeError("Critical log")

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
                if self.cluster:
                    print("runing on cluster")
                    cp = ClusterDispatcher(runResults)
                    for conf in confs:
                        cp.run(conf, cwd)
                    cp.wait()
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

            # reset working directory
            os.chdir(cwd)
        self.config["runResults"] = runResults


class NonZeroExitCodeException(Exception):
    pass


class RunShell(Tool):
    def __init__(self, command, runInfoTo=None,
                 limitsConfig=json_names.limitsConfig.text,
                 externalUsedConfig=None,
                 requireNormalExit=False):
        super().__init__()
        self.command = command
        self.limitsConfigPath = limitsConfig
        self.runInfoTo = runInfoTo
        self.requireNormalExit = requireNormalExit
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

        self.limits = dict()
        if limitsConfig is not None:
            for key, value in limitsConfig.items():
                if key.startswith("RLIMIT_"):
                    self.limits[key] = value

    def setLimits(self):
        for key, value in self.limits.items():
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
            "exec " + commandString,
            shell=True,
            preexec_fn=self.setLimits,
            executable='/bin/bash')

        try:
            timeout = self.access(self.limitsConfigPath)["timeout"]
        except KeyError:
            timeout = None

        if timeout is None:
            process.wait()
        else:
            try:
                process.wait(timeout)
            except subprocess.TimeoutExpired:
                process.kill()

        info = resource.getrusage(resource.RUSAGE_CHILDREN)

        self.readConfig.run()

        if (self.runInfoTo is not None):
            timeData = self.access(self.runInfoTo, createMissing=True)
            timeData["userTime"] = info.ru_utime - startInfo.ru_utime
            timeData["systemTime"] = info.ru_stime - startInfo.ru_stime
            timeData["wallClockTime"] = time.perf_counter() - startTime
            timeData["returnCode"] = process.returncode

        if (self.requireNormalExit and process.returncode != 0):
            raise NonZeroExitCodeException(
                'During execution of ' + commandString)


class RunJava(RunShell):
    def __init__(self, command, runInfoTo=None,
                 limitsConfig=json_names.limitsConfig.text,
                 externalUsedConfig=None,
                 requireNormalExit=False):
        command = "exec java -jar " + command
        super().__init__(
            command, runInfoTo,
            limitsConfig,
            externalUsedConfig,
            requireNormalExit)

    def loadLimits(self):
        super().loadLimits()
        if "RLIMIT_AS" in self.limits:
            self.command = "exec java -jar -Xmx" \
                + str(self.limits["RLIMIT_AS"][0]) \
                + " " + self.command[10:]
            del self.limits["RLIMIT_AS"]


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
        logging.debug("cd to %s" % (path))
        os.chdir(path)
        self.config["path"] = path


class SearchFilesNames(Tool):
    def __init__(self):
        super().__init__()

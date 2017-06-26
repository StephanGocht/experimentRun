import Pyro4
import os
import psutil
import socket
import logging
import sys

from multiprocessing import Process

from . import framework

# start nameserver using: python -m Pyro4.naming


@Pyro4.expose
class JobDispatcher():
    def run(self, config, workingDirectory):
        os.chdir(workingDirectory)
        return framework.bootstrap(config)

    def setIncludes(self, includes):
        sys.path.extend(includes)


def start(core):
    name = socket.gethostname()
    process = psutil.Process()
    process.cpu_affinity([core])

    daemon = Pyro4.Daemon(host=name)
    ns = Pyro4.locateNS()
    uri = daemon.register(JobDispatcher)
    ns.register(
        name + "-" + str(core) +
        ".jobdispatcher", uri, metadata=['jobdispatcher'])
    print("listening" + name)
    daemon.requestLoop()


def main():
    logging.getLogger("Pyro4").setLevel(logging.WARN)
    logging.getLogger("Pyro4.core").setLevel(logging.WARN)

    p1 = Process(target=start, args=(0,))
    p1.start()

    p2 = Process(target=start, args=(4,))
    p2.start()

    p1.join()
    p2.join()


if __name__ == "__main__":
    main()
